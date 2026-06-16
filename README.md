# Seebug AI - Sistema de Monitoreo e Identificación de Insectos

Este proyecto consiste en un sistema completo de monitoreo biológico en tiempo real utilizando una cámara **ESP32-CAM** en una trampa de insectos, un backend en Python impulsado por **FastAPI** e Inteligencia Artificial (**YOLO**), y un **Dashboard Web** interactivo de diseño premium.

El sistema identifica y registra tres clases principales de insectos: **Abejas**, **Escarabajos** y **Avispas**.

---

## Estructura del Proyecto

```text
seebug/
├── README.md               # Esta guía explicativa
├── esp32cam/
│   └── esp32cam.ino        # Firmware de Arduino para la ESP32-CAM
└── backend/
    ├── app.py              # Servidor FastAPI principal y controlador de flujos
    ├── detector.py         # Motor de IA (modo simulado o inferencia YOLO)
    ├── database.py         # Gestor de base de datos SQLite y analíticas
    ├── requirements.txt    # Librerías de Python requeridas
    ├── static/             # Archivos de la interfaz web
    │   ├── index.html      # Página web del Dashboard
    │   ├── style.css       # Diseño Glassmorphism
    │   └── app.js          # Lógica de WebSockets, Chart.js y galería
    └── data/               # Carpeta generada automáticamente
        ├── database.db     # Base de datos SQLite
        └── detections/     # Registro de imágenes de insectos detectados
```

---

## 🚀 Inicio Rápido (Modo Simulación)

Puedes ejecutar e interactuar con el sistema inmediatamente sin tener la ESP32-CAM física. El backend generará insectos animados en movimiento en un video interactivo y simulará la detección automática por IA.

### 1. Preparar el entorno de Python
Abre una terminal o consola de comandos en la carpeta `backend/` e instala las dependencias:

```bash
cd backend
pip install -r requirements.txt
```

### 2. Levantar el servidor en Modo Simulación
Ejecuta el backend con la bandera `--mock-camera` para iniciar la cámara virtual:

```bash
python app.py --mock-camera
```

### 3. Abrir el Dashboard Web
Abre tu navegador de preferencia e ingresa a:
👉 [**http://localhost:8000**](http://localhost:8000)

**¿Qué verás en modo simulación?**
- **Video en vivo:** Insectos simulados con colores y formas representativas moviéndose por una trampa virtual.
- **Detección automática:** Cuando un insecto se acerque al centro y la IA simulada supere el 75% de confianza, se dibujará un recuadro naranja.
- **Alertas y base de datos:** Al detectarse, se recortará el insecto del frame y se guardará en `data/detections/`, notificándolo en la web al instante con un sonido y un banner emergente (Toast).
- **Gráficos interactivos:** Se actualizarán las gráficas de Chart.js y los contadores en tiempo real.

---

## 🔌 Configuración con Hardware Real (ESP32-CAM)

Una vez que tengas tu ESP32-CAM física, sigue estos pasos:

### 1. Cargar el Firmware
1. Abre el archivo [esp32cam.ino](esp32cam/esp32cam.ino) en el IDE de Arduino.
2. Configura tu Wi-Fi reemplazando las siguientes variables:
   ```cpp
   const char* ssid = "TU_REDE_WIFI";
   const char* password = "TU_CONTRASEÑA";
   ```
3. En el IDE de Arduino, ve a **Herramientas > Placa** y selecciona **ESP32 Wrover Module** (o **AI Thinker ESP32-CAM**).
4. Asegúrate de tener habilitada la opción de **PSRAM** en la configuración de la placa (selecciona *Enabled*).
5. Sube el programa a tu placa.
6. Abre el monitor serie a **115200 baudios**, presiona el botón *RESET* de la placa y espera a que muestre la IP local. Ejemplo:
   `El stream está listo. Usa la URL: http://192.168.1.50/stream`

### 2. Ejecutar el Backend apuntando a la Cámara
Detén el backend de simulación y ejecútalo apuntando a la URL del stream de tu ESP32-CAM:

```bash
python app.py --camera-url http://192.168.1.50/stream
```
*(Reemplaza `192.168.1.50` por la IP real que te arrojó tu placa).*

---

## 🧠 Entrenamiento del Modelo de IA (YOLOv8)

Por defecto, cuando utilizas una cámara real, el sistema buscará un archivo llamado `best.pt` en la carpeta `backend/` para hacer la detección real con YOLOv8. Si no lo encuentra, usará el modo simulación para evitar que el software falle.

Para entrenar tu propia red neuronal de forma gratuita para reconocer **Abejas**, **Escarabajos** y **Avispas**, sigue estos sencillos pasos:

### 1. Recolección de Datos
Puedes recopilar tus propias fotos de los insectos o descargar un dataset ya existente en plataformas gratuitas como **Roboflow Universe**:
- Busca datasets públicos con etiquetas como `bee`, `beetle`, `wasp` o `insects`.
- Exporta el dataset en formato **YOLOv8** (esto te descargará un archivo `.zip` con las imágenes y las etiquetas en formato `.txt`, junto con un archivo `data.yaml`).

### 2. Entrenamiento en Google Colab (Gratis con GPU)
Crea un cuaderno de Google Colab e instala `ultralytics`. Ejecuta las siguientes celdas:

```python
# 1. Instalar la librería de YOLO
!pip install ultralytics

# 2. Subir tu archivo .zip del dataset de Roboflow y descomprimirlo
!unzip dataset.zip -d dataset/

# 3. Entrenar el modelo
from ultralytics import YOLO
# Cargamos un modelo preentrenado muy liviano (nano), ideal para correr en computador personal
model = YOLO('yolov8n.pt') 

# Entrenamos por 50 épocas a una resolución de 640px
model.train(data='dataset/data.yaml', epochs=50, imgsz=640, device=0)
```

### 3. Exportar y usar tu Modelo
Una vez finalizado el entrenamiento en Google Colab:
1. Navega a la barra lateral izquierda de archivos en Colab.
2. Descarga el archivo generado en: `runs/detect/train/weights/best.pt`.
3. Copia el archivo `best.pt` dentro de la carpeta `backend/` de este proyecto.
4. Al arrancar el programa con `python app.py --camera-url ...`, el detector detectará el archivo `best.pt` e iniciará la inferencia en tiempo real sobre tu ESP32-CAM de manera automática.

---

## 🛠️ Solución de Problemas

- **La imagen del stream de la ESP32-CAM se ve cortada o lenta:**
  Asegúrate de que la señal Wi-Fi donde está ubicada la trampa sea buena. Puedes cambiar la resolución de la cámara en el sketch de Arduino de `FRAMESIZE_SVGA` (800x600) a `FRAMESIZE_VGA` (640x480) para hacerla más ligera.
- **Error "CORS" en la consola web al capturar fotos:**
  Asegúrate de que estás ingresando a través del puerto configurado (`http://localhost:8000`). El servidor FastAPI incluye cabeceras CORS permisivas para el stream.
- **La cámara real se desconecta ocasionalmente:**
  El backend incluye un reconectador automático en segundo plano. Si la cámara pierde energía o señal Wi-Fi, la web mostrará un mensaje de reconexión y volverá al flujo de video en cuanto la ESP32-CAM se reincorpore a la red, sin colapsar el programa de Python.
