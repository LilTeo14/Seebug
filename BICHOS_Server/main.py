import asyncio
import cv2
import requests
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import database
from ai_vision import BugDetector

app = FastAPI(title="Servidor BICHOS")

# Configurar motor de plantillas HTML
templates = Jinja2Templates(directory="templates")

# Inicializar Base de Datos y Modelo de IA
database.init_db()
detector = BugDetector()

# ==========================================
# CONFIGURACIÓN DE LA ESP32-CAM
# ==========================================
# CAMBIA ESTA IP POR LA IP QUE TE DE EL ARDUINO IDE
ESP32_IP = "http://192.168.1.100" 
STREAM_URL = f"{ESP32_IP}/stream"
ACTION_URL = f"{ESP32_IP}/action"

# Gestor de WebSockets para actualizar el Dashboard en vivo
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# ==========================================
# RUTAS WEB (FRONTEND)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    stats = database.get_stats()
    logs = database.get_recent_detections()
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "stats": stats,
        "logs": logs,
        "esp32_stream": STREAM_URL
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==========================================
# TAREA EN SEGUNDO PLANO: PROCESAR VIDEO
# ==========================================
async def process_video_stream():
    """Esta tarea corre en el servidor, lee el video y lo pasa a la IA."""
    print(f"Intentando conectar al stream de video: {STREAM_URL}")
    
    # Inicializamos OpenCV para capturar el stream MJPEG
    cap = cv2.VideoCapture(STREAM_URL)
    
    if not cap.isOpened():
        print("Advertencia: No se pudo conectar a la cámara ESP32-CAM. ¿Está encendida y en la misma red?")
    
    while True:
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # 1. Pasar el modelo de IA
                detection = detector.predict(frame)
                
                if detection:
                    species, role, action = detection
                    print(f"¡INSECTO DETECTADO! {species} ({role})")
                    
                    # 2. Guardar en Base de Datos
                    database.log_detection(species, role, action)
                    
                    # 3. Accionar Servomotor si es Nativo
                    if role == "Nativo":
                        try:
                            print("Enviando señal de liberación a la ESP32-CAM...")
                            requests.get(ACTION_URL, timeout=3)
                        except Exception as e:
                            print(f"Error al conectar con ESP32-CAM para mover rampa: {e}")
                    
                    # 4. Actualizar el Dashboard en tiempo real (WebSockets)
                    stats = database.get_stats()
                    new_log = {"timestamp": "Ahora", "species": species, "ecological_role": role, "action": action}
                    await manager.broadcast({
                        "type": "new_detection",
                        "stats": stats,
                        "log": new_log
                    })
        else:
            # Reintentar conexión si se pierde
            cap = cv2.VideoCapture(STREAM_URL)
            await asyncio.sleep(2)
            
        # Pequeña pausa para no saturar el CPU (Aprox 10 FPS de procesamiento)
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    # Iniciar la lectura del stream de video en paralelo al arrancar el servidor
    asyncio.create_task(process_video_stream())

if __name__ == "__main__":
    import uvicorn
    # Lanzar el servidor en el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
