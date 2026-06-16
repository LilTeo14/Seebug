#include "esp_camera.h"
#include <WiFi.h>

// ===================
// CONFIGURACIÓN WI-FI
// ===================
const char* ssid = "TU_REDE_WIFI";
const char* password = "TU_CONTRASEÑA";

// ==========================================
// DEFINICIÓN DE PINES (Modelo AI-Thinker)
// ==========================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Pin del LED Flash integrado (GPIO 4)
#define FLASH_GPIO_NUM     4

WiFiServer server(80);

void startCameraServer();

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  // Configurar pin del Flash
  pinMode(FLASH_GPIO_NUM, OUTPUT);
  digitalWrite(FLASH_GPIO_NUM, LOW); // Apagado por defecto

  // Configuración de la Cámara
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Ajustes de calidad y resolución
  // SVGA (800x600) es un excelente balance entre resolución para IA y framerate
  if(psramFound()){
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12; // 0-63, menor número es mayor calidad
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_VGA; // Fallback a 640x480 si no hay PSRAM
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  // Inicializar cámara
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Error al inicializar la cámara: 0x%x", err);
    return;
  }

  // Optimizar sensor para exteriores / trampa
  sensor_t * s = esp_camera_sensor_get();
  s->set_brightness(s, 1);     // -2 a 2
  s->set_contrast(s, 1);       // -2 a 2
  s->set_saturation(s, 0);     // -2 a 2
  s->set_whitebal(s, 1);       // Auto balance de blancos (0 = off, 1 = on)
  s->set_awb_gain(s, 1);       // Ganancia AWB (0 = off, 1 = on)
  s->set_wb_mode(s, 0);        // Modo balance: 0=Auto, 1=Sunny, 2=Cloudy, 3=Office, 4=Home
  s->set_exposure_control(s, 1); // Control de exposición automática
  s->set_gain_control(s, 1);   // Ganancia automática

  // Conectar a Wi-Fi
  Serial.printf("Conectando a %s ", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("¡Conectado a Wi-Fi!");

  // Iniciar servidor de streaming
  startCameraServer();

  Serial.print("El stream está listo. Usa la URL: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/stream");
}

// Handler para la transmisión MJPEG
void handleStream(WiFiClient client) {
  // Enviar cabeceras HTTP para multipart/x-mixed-replace (Streaming MJPEG)
  client.println("HTTP/1.1 200 OK");
  client.println("Content-Type: multipart/x-mixed-replace; boundary=123456789000000000000987654321");
  client.println("Access-Control-Allow-Origin: *");
  client.println();

  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  
  unsigned long last_frame_time = 0;

  while (client.connected()) {
    // Capturar frame de la cámara
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Fallo al capturar frame");
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
    }

    if (res == ESP_OK) {
      // Cabecera del boundary para cada frame
      client.print("--123456789000000000000987654321\r\n");
      client.print("Content-Type: image/jpeg\r\n");
      client.print("Content-Length: " + String(_jpg_buf_len) + "\r\n\r\n");
      
      // Enviar el JPEG binario
      client.write(_jpg_buf, _jpg_buf_len);
      client.print("\r\n");
    }

    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
      _jpg_buf = NULL;
    } else if (res != ESP_OK) {
      break;
    }
    
    // Pequeño delay para no saturar el canal (aprox. 15-20 fps máximo)
    delay(30);
  }
}

void startCameraServer() {
  server.begin();
}

void loop() {
  WiFiClient client = server.available();
  if (client) {
    String req = client.readStringUntil('\r');
    client.flush();

    // Responder sólo si la petición es a /stream o a la raíz
    if (req.indexOf("GET /stream") != -1 || req.indexOf("GET / ") != -1) {
      handleStream(client);
    } else {
      client.println("HTTP/1.1 404 Not Found");
      client.println("Content-Type: text/plain");
      client.println();
      client.println("404 Not Found. Usa /stream para ver el video.");
      client.stop();
    }
  }
}
