import time

class BugDetector:
    def __init__(self):
        # Aquí cargarías el modelo YOLO real:
        # from ultralytics import YOLO
        # self.model = YOLO('yolov8n.pt') 
        print("Modelo de IA inicializado.")
        # Variable para evitar detectar el mismo bicho 100 veces por segundo
        self.last_detection_time = 0

    def predict(self, frame):
        """
        Recibe un frame (imagen) de OpenCV.
        Devuelve (Especie, Rol Ecológico, Acción) o None si no hay detección.
        """
        # --- LÓGICA SIMULADA POR AHORA ---
        # En la realidad, harías: results = self.model(frame)
        # y extraerías las clases detectadas.
        
        current_time = time.time()
        
        # Simulamos que detecta algo cada 15 segundos para propósitos de prueba
        if current_time - self.last_detection_time > 15:
            self.last_detection_time = current_time
            # Aleatoriamente decide si es plaga o nativo (Solo para maqueta)
            import random
            if random.choice([True, False]):
                return ("Adalia angulifera", "Nativo", "Liberado (Rampa abierta)")
            else:
                return ("Agrotis ipsilon", "Plaga", "Retenido")
        
        return None
