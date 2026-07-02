#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

const char* ssid = "ElMateooo";
const char* password = "12345678";

// Pin del Flash LED (GPIO 4 en la mayoría de ESP32-CAM)
#define FLASH_LED_PIN 4
#define LEDC_CHANNEL_1 1
#define LEDC_TIMER_8_BIT 8
#define LEDC_BASE_FREQ 5000

#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;
httpd_handle_t camera_httpd = NULL;

static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    size_t _jpg_buf_len = 0;
    uint8_t * _jpg_buf = NULL;
    char * part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if(res != ESP_OK){ return res; }

    while(true){
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Error al capturar la imagen");
            res = ESP_FAIL;
        } else {
            if(fb->format != PIXFORMAT_JPEG){
                bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
                esp_camera_fb_return(fb);
                fb = NULL;
                if(!jpeg_converted){
                    Serial.println("Falló la conversión a JPEG");
                    res = ESP_FAIL;
                }
            } else {
                _jpg_buf_len = fb->len;
                _jpg_buf = fb->buf;
            }
        }
        if(res == ESP_OK){
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
            res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
        }
        if(res == ESP_OK){
            res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
        }
        if(res == ESP_OK){
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
        }
        if(fb){ esp_camera_fb_return(fb); fb = NULL; _jpg_buf = NULL; }
        else if(_jpg_buf){ free(_jpg_buf); _jpg_buf = NULL; }
        if(res != ESP_OK){ break; }
    }
    return res;
}

static esp_err_t capture_handler(httpd_req_t *req) {
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;

    fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("Error al capturar la imagen");
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");

    size_t out_len;
    uint8_t * out_buf;
    if(fb->format == PIXFORMAT_JPEG){
        out_len = fb->len;
        out_buf = fb->buf;
    } else {
        bool jpeg_converted = frame2jpg(fb, 80, &out_buf, &out_len);
        if(!jpeg_converted){
            Serial.println("Falló la conversión a JPEG");
            esp_camera_fb_return(fb);
            httpd_resp_send_500(req);
            return ESP_FAIL;
        }
    }

    res = httpd_resp_send(req, (const char *)out_buf, out_len);
    
    if(fb->format != PIXFORMAT_JPEG){
        free(out_buf);
    }
    esp_camera_fb_return(fb);
    return res;
}

// Handler para controlar la intensidad del LED
static esp_err_t led_handler(httpd_req_t *req) {
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    
    char buf[64];
    int intensity = 0;
    
    if (httpd_req_get_url_query_str(req, buf, sizeof(buf)) == ESP_OK) {
        char param[32];
        if (httpd_query_key_value(buf, "v", param, sizeof(param)) == ESP_OK) {
            intensity = atoi(param);
            if (intensity < 0) intensity = 0;
            if (intensity > 255) intensity = 255;
            // API V3 ESP32 Core
            ledcWrite(FLASH_LED_PIN, intensity);
            Serial.printf("Intensidad LED ajustada a: %d\n", intensity);
        }
    }
    
    httpd_resp_send(req, "LED OK", HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

void startCameraServer(){
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;

    httpd_uri_t led_uri = {
        .uri       = "/led",
        .method    = HTTP_GET,
        .handler   = led_handler,
        .user_ctx  = NULL
    };

    httpd_uri_t capture_uri = {
        .uri       = "/capture",
        .method    = HTTP_GET,
        .handler   = capture_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&camera_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(camera_httpd, &led_uri);
        httpd_register_uri_handler(camera_httpd, &capture_uri);
    }

    config.server_port += 1;
    config.ctrl_port += 1;

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
    }
}

void setup() {
    Serial.begin(115200);
    
    // Iniciar Flash LED con API Core 3.x
    ledcAttach(FLASH_LED_PIN, LEDC_BASE_FREQ, LEDC_TIMER_8_BIT);
    ledcWrite(FLASH_LED_PIN, 0); // Iniciar apagado

    // Configuración AI THINKER
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = 5;
    config.pin_d1 = 18;
    config.pin_d2 = 19;
    config.pin_d3 = 21;
    config.pin_d4 = 36;
    config.pin_d5 = 39;
    config.pin_d6 = 34;
    config.pin_d7 = 35;
    config.pin_xclk = 0;
    config.pin_pclk = 22;
    config.pin_vsync = 25;
    config.pin_href = 23;
    config.pin_sscb_sda = 26;
    config.pin_sscb_scl = 27;
    config.pin_pwdn = 32;
    config.pin_reset = -1;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_QVGA; 
    config.jpeg_quality = 12;
    config.fb_count = 2;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("Error cámara 0x%x", err);
        return;
    }

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWi-Fi conectado.");
    
    startCameraServer();
    Serial.print("Servidor en: http://");
    Serial.println(WiFi.localIP());
}

void loop() { delay(10000); }
