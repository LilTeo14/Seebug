import cv2
import numpy as np
import os
import random
import time
from datetime import datetime
from PIL import Image

# Intentar importar Ultralytics YOLO, si no está instalado o falla, se usará simulación.
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

class MockInsect:
    def __init__(self, insect_id: int):
        self.id = insect_id
        self.type = random.choice(["Abeja", "Escarabajo", "Avispa"])
        self.x = random.randint(100, 700)
        self.y = random.randint(100, 500)
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-3, 3)
        
        # Tamaño
        if self.type == "Abeja":
            self.w, self.h = 45, 35
        elif self.type == "Avispa":
            self.w, self.h = 50, 25
        else: # Escarabajo
            self.w, self.h = 40, 50
            
        self.confidence = 0.0
        self.detected_saved = False
        self.focus_factor = random.uniform(0.7, 0.95)

    def update(self):
        # Mover
        self.x += self.vx
        self.y += self.vy

        # Rebotar en los bordes
        if self.x - self.w/2 < 50 or self.x + self.w/2 > 750:
            self.vx *= -1
        if self.y - self.h/2 < 50 or self.y + self.h/2 > 550:
            self.vy *= -1

        # Variar confianza según distancia al centro (simulando enfoque)
        dist_to_center = np.sqrt((self.x - 400)**2 + (self.y - 300)**2)
        # Cuanto más cerca del centro, mayor confianza
        self.confidence = max(0.3, 1.0 - (dist_to_center / 600.0))
        self.confidence = min(self.confidence * self.focus_factor, 0.99)

        # De vez en cuando cambiar de dirección
        if random.random() < 0.02:
            self.vx = random.uniform(-4, 4)
            self.vy = random.uniform(-4, 4)

class InsectDetector:
    def __init__(self, db_manager, use_mock=True, model_path="best.pt"):
        self.db = db_manager
        self.use_mock = use_mock
        self.model = None
        
        # Diccionario de cooldowns para cámara real (tipo_insecto -> timestamp del último guardado)
        self.cooldowns = {
            "Abeja": 0,
            "Escarabajo": 0,
            "Avispa": 0
        }
        self.cooldown_duration = 8.0 # Segundos entre guardados de la misma clase

        if not self.use_mock and YOLO_AVAILABLE:
            if os.path.exists(model_path):
                try:
                    self.model = YOLO(model_path)
                    print(f"Modelo YOLO cargado exitosamente desde {model_path}")
                except Exception as e:
                    print(f"Error cargando el modelo YOLO ({e}). Usando modo simulación.")
                    self.use_mock = True
            else:
                print(f"Archivo de modelo '{model_path}' no encontrado. Se usará simulación por defecto.")
                self.use_mock = True
        else:
            self.use_mock = True
            
        if self.use_mock:
            print("Detector inicializado en MODO SIMULACIÓN.")
            # Inicializar insectos simulados
            self.simulated_insects = [MockInsect(1), MockInsect(2)]
            self.next_insect_id = 3
            self.background = self._create_trap_background()

    def _create_trap_background(self):
        # Crear un fondo que simula una trampa para insectos
        bg = np.zeros((600, 800, 3), dtype=np.uint8)
        # Llenar de color verde-amarillento (típico color atrayente de trampas)
        bg[:] = (200, 240, 200) # BGR
        
        # Dibujar rejilla/patrón de la trampa
        cv2.circle(bg, (400, 300), 250, (170, 220, 170), 3)
        cv2.circle(bg, (400, 300), 150, (170, 220, 170), 2)
        cv2.circle(bg, (400, 300), 50, (150, 200, 150), -1)
        
        # Texto de fondo
        cv2.putText(bg, "TRAMPA ACTIVA - SEBUG AI", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 150, 100), 2)
        
        return bg

    def _draw_mock_insect(self, frame, insect: MockInsect):
        x, y = int(insect.x), int(insect.y)
        w, h = insect.w, insect.h
        
        # Color del cuerpo
        if insect.type == "Abeja":
            # Abeja: Amarilla con rayas negras
            cv2.ellipse(frame, (x, y), (w//2, h//2), 0, 0, 360, (0, 220, 255), -1) # BGR Amarillo
            # Rayas negras
            for offset in [-10, 0, 10]:
                cv2.line(frame, (x + offset, y - h//2), (x + offset, y + h//2), (0, 0, 0), 3)
            # Ojito
            cv2.circle(frame, (x + w//3, y - h//5), 3, (0, 0, 0), -1)
            # Alitas
            cv2.ellipse(frame, (x - 5, y - h//2), (10, 15), -30, 0, 360, (240, 240, 240), -1)
            cv2.ellipse(frame, (x + 5, y - h//2), (8, 12), 30, 0, 360, (240, 240, 240), -1)

        elif insect.type == "Avispa":
            # Avispa: Cuerpo más alargado y colores más contrastados
            cv2.ellipse(frame, (x, y), (w//2, h//2), 15, 0, 360, (0, 180, 230), -1)
            # Rayas negras oblicuas
            for offset in [-15, -5, 5, 15]:
                cv2.line(frame, (x + offset - 3, y - h//2), (x + offset + 3, y + h//2), (0, 0, 0), 2)
            # Alas transparentes más grandes
            cv2.ellipse(frame, (x - 10, y - h), (15, 8), 60, 0, 360, (220, 220, 220), -1)
            cv2.ellipse(frame, (x, y - h), (12, 6), 40, 0, 360, (200, 200, 200), -1)

        else: # Escarabajo
            # Escarabajo: Café/Rojizo, patas
            # Patas
            for leg_x in [-15, 0, 15]:
                cv2.line(frame, (x + leg_x, y), (x + leg_x * 1.5, y - 25), (30, 40, 60), 2)
                cv2.line(frame, (x + leg_x, y), (x + leg_x * 1.5, y + 25), (30, 40, 60), 2)
            # Cuerpo
            cv2.ellipse(frame, (x, y), (w//2, h//2), 0, 0, 360, (30, 45, 100), -1) # Café oscuro
            # Línea central
            cv2.line(frame, (x - w//2, y), (x + w//2, y), (15, 20, 50), 2)
            # Cabeza
            cv2.circle(frame, (x + w//2 - 5, y), 8, (20, 30, 80), -1)

    def process_frame(self, frame=None):
        """
        Procesa un frame de la cámara o genera uno simulado.
        Retorna:
          - frame_dibujado: Imagen con bounding boxes y etiquetas
          - nueva_deteccion: Diccionario de detección (si se guardó una nueva), si no, None
        """
        nueva_deteccion = None
        
        if self.use_mock:
            # 1. MODO SIMULACIÓN
            frame_out = self.background.copy()
            
            # Gestionar cantidad de insectos
            if len(self.simulated_insects) < 2 and random.random() < 0.05:
                self.simulated_insects.append(MockInsect(self.next_insect_id))
                self.next_insect_id += 1
                
            insects_to_keep = []
            
            for insect in self.simulated_insects:
                insect.update()
                
                # Ocasionalmente un insecto sale del área y es removido
                # Si está muy cerca de los bordes extremos, hay probabilidad de que se vaya
                dist_to_center = np.sqrt((insect.x - 400)**2 + (insect.y - 300)**2)
                if dist_to_center > 450 and random.random() < 0.01:
                    continue
                    
                insects_to_keep.append(insect)
                
                # Dibujar insecto físico
                self._draw_mock_insect(frame_out, insect)
                
                # Lógica de detección de IA simulada (confianza > 75%)
                if insect.confidence > 0.75:
                    x, y = int(insect.x), int(insect.y)
                    w, h = insect.w, insect.h
                    x1, y1 = max(0, x - w//2 - 10), max(0, y - h//2 - 10)
                    x2, y2 = min(799, x + w//2 + 10), min(599, y + h//2 + 10)
                    
                    # Dibujar bounding box
                    color = (0, 165, 255) # Naranja para detecciones activas
                    cv2.rectangle(frame_out, (x1, y1), (x2, y2), color, 2)
                    
                    # Dibujar etiqueta
                    label = f"{insect.type} {int(insect.confidence * 100)}%"
                    cv2.putText(frame_out, label, (x1, y1 - 8), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Guardar detección si no se ha guardado ya para este insecto
                    if not insect.detected_saved:
                        insect.detected_saved = True
                        
                        # Recortar imagen del insecto
                        crop = frame_out[y1:y2, x1:x2].copy()
                        
                        # Guardar imagen física
                        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"insect_{insect.type.lower()}_{timestamp_str}.jpg"
                        filepath = f"data/detections/{filename}"
                        cv2.imwrite(filepath, crop)
                        
                        # Registrar en Base de Datos
                        nueva_deteccion = self.db.add_detection(
                            insect_type=insect.type,
                            confidence=float(insect.confidence),
                            image_path=filepath
                        )
            
            self.simulated_insects = insects_to_keep
            return frame_out, nueva_deteccion
            
        else:
            # 2. MODO REAL (YOLOv8/v11)
            if frame is None:
                # Si por alguna razón el frame es None, retornar vacío
                return np.zeros((600, 800, 3), dtype=np.uint8), None
                
            frame_out = frame.copy()
            h_f, w_f, _ = frame.shape
            
            # Ejecutar inferencia de YOLO
            results = self.model(frame_out, verbose=False)[0]
            
            for box in results.boxes:
                conf = float(box.conf[0])
                # Umbral de confianza mínimo
                if conf < 0.50:
                    continue
                    
                # Obtener clase
                class_id = int(box.cls[0])
                class_name = results.names[class_id]
                
                # Mapear las clases detectadas a nuestras clases de interés.
                # Asumimos que el modelo personalizado está entrenado con etiquetas en español o inglés.
                insect_map = {
                    "abeja": "Abeja", "bee": "Abeja",
                    "escarabajo": "Escarabajo", "beetle": "Escarabajo",
                    "avispa": "Avispa", "wasp": "Avispa"
                }
                
                mapped_name = insect_map.get(class_name.lower())
                if not mapped_name:
                    continue # Ignorar clases que no corresponden a nuestro interés
                
                # Obtener coordenadas
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                
                # Dibujar bounding box
                color = (0, 255, 0) # Verde para IA Real
                cv2.rectangle(frame_out, (x1, y1), (x2, y2), color, 2)
                
                label = f"{mapped_name} {int(conf * 100)}%"
                cv2.putText(frame_out, label, (x1, y1 - 8), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                # Verificar cooldown para evitar saturar la base de datos con frames seguidos
                now_ts = time.time()
                if now_ts - self.cooldowns[mapped_name] > self.cooldown_duration:
                    self.cooldowns[mapped_name] = now_ts
                    
                    # Recortar el insecto
                    # Añadir un pequeño margen al recorte
                    margin = 15
                    x1_c = max(0, x1 - margin)
                    y1_c = max(0, y1 - margin)
                    x2_c = min(w_f - 1, x2 + margin)
                    y2_c = min(h_f - 1, y2 + margin)
                    
                    crop = frame[y1_c:y2_c, x1_c:x2_c].copy()
                    
                    # Guardar archivo
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    filename = f"insect_{mapped_name.lower()}_{timestamp_str}.jpg"
                    filepath = f"data/detections/{filename}"
                    cv2.imwrite(filepath, crop)
                    
                    # Guardar en base de datos
                    nueva_deteccion = self.db.add_detection(
                        insect_type=mapped_name,
                        confidence=conf,
                        image_path=filepath
                    )
            
            return frame_out, nueva_deteccion
