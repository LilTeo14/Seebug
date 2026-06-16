import argparse
import asyncio
import cv2
import numpy as np
import os
import queue
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import DatabaseManager
from detector import InsectDetector

# Argumentos de Consola
parser = argparse.ArgumentParser(description="Servidor de Monitoreo de Insectos Seebug AI")
parser.add_argument("--mock-camera", action="store_true", default=False, help="Usar cámara de simulación")
parser.add_argument("--camera-url", type=str, default="http://192.168.1.100/stream", help="URL de la cámara real")
parser.add_argument("--model-path", type=str, default="best.pt", help="Ruta del archivo de pesos de YOLO (best.pt)")
parser.add_argument("--port", type=int, default=8000, help="Puerto para levantar el servidor web")

# Parsear argumentos de manera segura para evitar errores en Uvicorn
try:
    args, unknown = parser.parse_known_args()
except Exception:
    class Args:
        mock_camera = True
        camera_url = "http://192.168.1.100/stream"
        model_path = "best.pt"
        port = 8000
    args = Args()

# Configurar el servidor FastAPI
app = FastAPI(title="Seebug AI", description="Sistema de Monitoreo e Identificación de Insectos")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cola e inicializaciones globales
detection_queue = queue.Queue()
latest_frame_jpeg = None
frame_lock = threading.Lock()
is_running = True

# Inicializar Base de Datos
db = DatabaseManager()

# Inicializar Detector de Insectos
detector = InsectDetector(db_manager=db, use_mock=args.mock_camera, model_path=args.model_path)

# Gestor de conexiones WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Cliente WebSocket conectado. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Cliente WebSocket desconectado. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

def camera_thread_worker():
    """
    Hilo dedicado a leer de la cámara (real o simulación) y correr la inferencia.
    """
    global latest_frame_jpeg, is_running
    
    print(f"Iniciando hilo de lectura de cámara. Modo Simulación: {detector.use_mock}")
    
    cap = None
    if not detector.use_mock:
        print(f"Intentando conectar a la cámara en: {args.camera_url}")
        cap = cv2.VideoCapture(args.camera_url)
        
    last_reconnect_time = 0
    
    while is_running:
        if detector.use_mock:
            # Procesar frame simulado
            processed_frame, nueva_det = detector.process_frame(None)
            
            # Codificar a JPEG para streaming
            ret, jpeg = cv2.imencode('.jpg', processed_frame)
            if ret:
                with frame_lock:
                    latest_frame_jpeg = jpeg.tobytes()
                    
            if nueva_det:
                detection_queue.put(nueva_det)
                
            time.sleep(0.04) # ~25 FPS
        else:
            # Modo Cámara Real
            if cap is None or not cap.isOpened():
                now = time.time()
                if now - last_reconnect_time > 5.0: # Reintentar cada 5 segundos
                    print(f"Reconectando a la cámara en {args.camera_url}...")
                    cap = cv2.VideoCapture(args.camera_url)
                    last_reconnect_time = now
                
                # Generar una imagen de error de conexión
                err_frame = np.zeros((600, 800, 3), dtype=np.uint8)
                err_frame[:] = (50, 50, 50)
                cv2.putText(err_frame, "CONECTANDO A ESP32-CAM...", (120, 280),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 255), 2)
                cv2.putText(err_frame, f"URL: {args.camera_url}", (120, 340),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
                
                ret, jpeg = cv2.imencode('.jpg', err_frame)
                if ret:
                    with frame_lock:
                        latest_frame_jpeg = jpeg.tobytes()
                        
                time.sleep(0.1)
                continue
                
            ret, frame = cap.read()
            if not ret:
                print("Error al leer frame de la cámara. Reseteando conexión...")
                cap.release()
                cap = None
                continue
                
            # Procesar el frame real mediante YOLO
            processed_frame, nueva_det = detector.process_frame(frame)
            
            # Codificar a JPEG
            ret_enc, jpeg = cv2.imencode('.jpg', processed_frame)
            if ret_enc:
                with frame_lock:
                    latest_frame_jpeg = jpeg.tobytes()
                    
            if nueva_det:
                detection_queue.put(nueva_det)

    if cap:
        cap.release()
    print("Hilo de cámara finalizado.")

# Iniciar hilo de la cámara
camera_thread = threading.Thread(target=camera_thread_worker, daemon=True)
camera_thread.start()

# Tarea de fondo en FastAPI para procesar las nuevas detecciones y enviarlas por WebSocket
async def websocket_broadcaster():
    while True:
        try:
            # Revisar si hay nuevas detecciones en la cola sin bloquear
            while not detection_queue.empty():
                detection = detection_queue.get_nowait()
                await manager.broadcast({
                    "type": "new_detection",
                    "data": detection
                })
                detection_queue.task_done()
        except Exception as e:
            print(f"Error en el broadcast de detecciones: {e}")
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    # Iniciar el consumidor de la cola de detecciones
    asyncio.create_task(websocket_broadcaster())

@app.on_event("shutdown")
def shutdown_event():
    global is_running
    is_running = False
    camera_thread.join(timeout=2.0)

# ====================
# ENDPOINTS DE LA API
# ====================

@app.get("/api/video_feed")
def video_feed():
    """
    Retorna el video procesado en vivo codificado en formato multipart/x-mixed-replace (MJPEG)
    """
    def gen():
        global latest_frame_jpeg
        while is_running:
            if latest_frame_jpeg is not None:
                with frame_lock:
                    frame = latest_frame_jpeg
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.04)
            
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/detections")
def get_detections(limit: int = 50, offset: int = 0):
    """
    Retorna la lista de detecciones recientes
    """
    return db.get_recent_detections(limit=limit, offset=offset)

@app.get("/api/stats")
def get_stats():
    """
    Retorna las estadísticas necesarias para los gráficos del dashboard
    """
    return db.get_stats()

@app.get("/data/detections/{filename}")
def get_detection_image(filename: str):
    """
    Servicio de imágenes de insectos recortadas
    """
    filepath = f"data/detections/{filename}"
    if os.path.exists(filepath):
        return FileResponse(filepath)
    return FileResponse(np.zeros((100, 100, 3), dtype=np.uint8)) # fallback

# ============================
# ENDPOINT DE WEBSOCKETS
# ============================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Mantener conexión abierta
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# Montar archivos estáticos para la interfaz de usuario web
# NOTA: Debe ir al final para no interferir con las rutas específicas de la API
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print(f"Iniciando Seebug AI en http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
