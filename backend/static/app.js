// ==========================================================================
// CONFIGURACIÓN E INICIALIZACIÓN GLOBAL
// ==========================================================================
let trendsChart = null;
let currentChartPeriod = 'hourly'; // 'hourly' o 'daily'
let socket = null;
let soundEnabled = false;

// Elementos del DOM
const elTimeDisplay = document.getElementById('time-display');
const elConnectionBadge = document.getElementById('connection-badge');
const elConnectionText = document.getElementById('connection-text');
const elCameraSourceInfo = document.getElementById('camera-source-info');
const elHudMode = document.getElementById('hud-mode');
const elHudFps = document.getElementById('hud-fps');
const elBtnSoundToggle = document.getElementById('btn-sound-toggle');
const elSoundIcon = document.getElementById('sound-icon');
const elAlertSound = document.getElementById('alert-sound');

const elCountAbeja = document.getElementById('count-abeja');
const elCountEscarabajo = document.getElementById('count-escarabajo');
const elCountAvispa = document.getElementById('count-avispa');

const elBtnChartHourly = document.getElementById('btn-chart-hourly');
const elBtnChartDaily = document.getElementById('btn-chart-daily');
const elGalleryGrid = document.getElementById('gallery-grid');
const elGalleryEmpty = document.getElementById('gallery-empty');
const elGalleryFilters = document.querySelectorAll('.filter-btn');

const elImageModal = document.getElementById('image-modal');
const elModalImg = document.getElementById('modal-img');
const elModalCaption = document.getElementById('modal-caption');
const elModalClose = document.querySelector('.modal-close');

const elBtnSnap = document.getElementById('btn-snap');
const elBtnFullscreen = document.getElementById('btn-fullscreen');
const elVideoStream = document.getElementById('video-stream');

// ==========================================================================
// RELOJ DEL SISTEMA
// ==========================================================================
function updateClock() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const secs = String(now.getSeconds()).padStart(2, '0');
    elTimeDisplay.textContent = `${hrs}:${mins}:${secs}`;
}
setInterval(updateClock, 1000);
updateClock();

// ==========================================================================
// CONTROLES DE LA CÁMARA
// ==========================================================================
// Capturar snapshot de la transmisión (canvas en memoria)
elBtnSnap.addEventListener('click', () => {
    try {
        const canvas = document.createElement('canvas');
        canvas.width = elVideoStream.naturalWidth || 800;
        canvas.height = elVideoStream.naturalHeight || 600;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(elVideoStream, 0, 0, canvas.width, canvas.height);
        
        // Descargar la imagen
        const dataURL = canvas.toDataURL('image/jpeg');
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        link.download = `seebug-snapshot-${timestamp}.jpg`;
        link.href = dataURL;
        link.click();
        
        showToastNotification({
            insect_type: "Captura",
            confidence: 1.0,
            image_path: dataURL,
            timestamp: new Date().toISOString()
        }, "Foto guardada en tu PC");
    } catch (e) {
        console.error("Error al capturar foto:", e);
        alert("No se pudo capturar la foto (probablemente debido a restricciones de origen CORS de la imagen del stream).");
    }
});

// Pantalla Completa del Stream
elBtnFullscreen.addEventListener('click', () => {
    if (elVideoStream.requestFullscreen) {
        elVideoStream.requestFullscreen();
    } else if (elVideoStream.webkitRequestFullscreen) { /* Safari */
        elVideoStream.webkitRequestFullscreen();
    } else if (elVideoStream.msRequestFullscreen) { /* IE11 */
        elVideoStream.msRequestFullscreen();
    }
});

// ==========================================================================
// MANEJO DE SONIDO DE ALERTA
// ==========================================================================
elBtnSoundToggle.addEventListener('click', () => {
    soundEnabled = !soundEnabled;
    if (soundEnabled) {
        elBtnSoundToggle.classList.remove('muted');
        elSoundIcon.setAttribute('data-lucide', 'volume-2');
        // Pequeña vibración auditiva para confirmar activación
        elAlertSound.volume = 0.3;
        elAlertSound.play().catch(() => {});
    } else {
        elBtnSoundToggle.classList.add('muted');
        elSoundIcon.setAttribute('data-lucide', 'volume-x');
    }
    lucide.createImages(); // Recargar iconos
});

// ==========================================================================
// CONEXIÓN DE WEBSOCKETS (ALERTAS EN TIEMPO REAL)
// ==========================================================================
function connectWebSocket() {
    const loc = window.location;
    let wsUri;
    if (loc.protocol === "https:") {
        wsUri = "wss:";
    } else {
        wsUri = "ws:";
    }
    wsUri += `//${loc.host}/ws`;

    console.log("Conectando WebSocket en " + wsUri);
    socket = new WebSocket(wsUri);

    socket.onopen = () => {
        console.log("Conexión WebSocket establecida.");
        elConnectionBadge.className = "status-badge connected";
        elConnectionText.textContent = "Sistema Online";
        
        // Traer datos frescos al iniciar/reconectar
        fetchStats();
        fetchDetections();
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "new_detection") {
            handleNewDetection(msg.data);
        }
    };

    socket.onclose = () => {
        console.warn("WebSocket cerrado. Reintentando en 5 segundos...");
        elConnectionBadge.className = "status-badge disconnected";
        elConnectionText.textContent = "Reconectando backend...";
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = (err) => {
        console.error("Error en WebSocket:", err);
        socket.close();
    };
}

// ==========================================================================
// PROCESAMIENTO DE NUEVAS DETECCIONES
// ==========================================================================
function handleNewDetection(detection) {
    // 1. Reproducir sonido si está habilitado
    if (soundEnabled) {
        elAlertSound.currentTime = 0;
        elAlertSound.volume = 0.5;
        elAlertSound.play().catch(e => console.log("Permiso de reproducción requerido:", e));
    }

    // 2. Incrementar contadores en el DOM con animación
    incrementSpeciesCounter(detection.insect_type);

    // 3. Agregar elemento a la galería en tiempo real
    addInsectToGallery(detection, true);

    // 4. Mostrar notificación Toast
    showToastNotification(detection);

    // 5. Actualizar los gráficos refrescando estadísticas
    fetchStats();
}

function incrementSpeciesCounter(type) {
    let el = null;
    let card = null;
    if (type === "Abeja") {
        el = elCountAbeja;
        card = document.getElementById('counter-abeja-card');
    } else if (type === "Escarabajo") {
        el = elCountEscarabajo;
        card = document.getElementById('counter-escarabajo-card');
    } else if (type === "Avispa") {
        el = elCountAvispa;
        card = document.getElementById('counter-avispa-card');
    }

    if (el && card) {
        let current = parseInt(el.textContent) || 0;
        el.textContent = current + 1;
        
        // Animación de rebote (escala) de la tarjeta
        card.style.transform = "scale(1.08)";
        card.style.filter = "brightness(1.2)";
        setTimeout(() => {
            card.style.transform = "";
            card.style.filter = "";
        }, 300);
    }
}

// ==========================================================================
// NOTIFICACIONES TOAST (POPUPS EMERGENGENTES)
// ==========================================================================
function showToastNotification(detection, customTitle = null) {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    // Convertir ruta local del backend a URL relativa para la web
    const imgSrc = detection.image_path.startsWith('data:') 
        ? detection.image_path 
        : `/${detection.image_path}`;
        
    const timeStr = new Date(detection.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const confPercent = Math.round(detection.confidence * 100);

    const titleClass = `toast-${detection.insect_type.toLowerCase()}`;
    const badgeEmoji = detection.insect_type === "Abeja" ? "🐝" : detection.insect_type === "Escarabajo" ? "🪲" : detection.insect_type === "Avispa" ? "🐝" : "📸";
    const titleText = customTitle || `¡Nueva Detección! ${badgeEmoji}`;

    toast.innerHTML = `
        <img src="${imgSrc}" class="toast-img" alt="insect-crop">
        <div class="toast-body">
            <div class="toast-title ${titleClass}">${titleText}</div>
            <div class="toast-message">${detection.insect_type} - Confianza: ${confPercent}%</div>
            <div class="toast-time">${timeStr}</div>
        </div>
    `;

    container.appendChild(toast);

    // Reproducir la animación de entrada
    setTimeout(() => {
        toast.classList.add('removing');
        // Eliminar del DOM después de la animación de salida
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4500); // Duración de visualización del toast
}

// ==========================================================================
// PETICIONES API (HISTÓRICO Y ESTADÍSTICAS)
// ==========================================================================
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        
        // Actualizar contadores totales
        elCountAbeja.textContent = data.totals.Abeja || 0;
        elCountEscarabajo.textContent = data.totals.Escarabajo || 0;
        elCountAvispa.textContent = data.totals.Avispa || 0;
        
        // Actualizar el gráfico
        updateChartData(data);
    } catch (e) {
        console.error("Error consultando estadísticas:", e);
    }
}

async function fetchDetections() {
    try {
        const res = await fetch('/api/detections?limit=60');
        const detections = await res.json();
        
        elGalleryGrid.innerHTML = ''; // Limpiar galería
        
        if (detections.length === 0) {
            elGalleryEmpty.classList.remove('hidden');
        } else {
            elGalleryEmpty.classList.add('hidden');
            detections.forEach(det => {
                addInsectToGallery(det, false);
            });
        }
        filterGalleryItems(); // Aplicar el filtro activo actualmente
    } catch (e) {
        console.error("Error consultando galería:", e);
    }
}

// Agregar tarjeta de insecto al DOM
function addInsectToGallery(detection, prepend = false) {
    elGalleryEmpty.classList.add('hidden');
    
    const card = document.createElement('div');
    card.className = 'insect-card';
    card.setAttribute('data-species', detection.insect_type);
    
    const dateObj = new Date(detection.timestamp);
    const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const dateStr = dateObj.toLocaleDateString([], { day: 'numeric', month: 'short' });
    const confPercent = Math.round(detection.confidence * 100);
    const imgSrc = `/${detection.image_path}`;

    let badgeClass = '';
    let emoji = '';
    if (detection.insect_type === "Abeja") { badgeClass = 'badge-abeja'; emoji = '🐝'; }
    else if (detection.insect_type === "Escarabajo") { badgeClass = 'badge-escarabajo'; emoji = '🪲'; }
    else if (detection.insect_type === "Avispa") { badgeClass = 'badge-avispa'; emoji = '📐'; }

    card.innerHTML = `
        <div class="insect-img-container">
            <span class="insect-badge ${badgeClass}">${emoji} ${detection.insect_type}</span>
            <span class="insect-conf-tag">${confPercent}%</span>
            <img src="${imgSrc}" alt="${detection.insect_type}" loading="lazy">
        </div>
        <div class="insect-details">
            <span class="time"><i data-lucide="clock" class="icon-small text-muted"></i> ${timeStr}</span>
            <span class="date">${dateStr}</span>
        </div>
    `;

    // Evento de click para expandir imagen en modal
    card.querySelector('.insect-img-container').addEventListener('click', () => {
        openImageModal(imgSrc, `${detection.insect_type} (${confPercent}% de confianza) - Detectado a las ${timeStr} del ${dateStr}`);
    });

    if (prepend) {
        elGalleryGrid.insertBefore(card, elGalleryGrid.firstChild);
    } else {
        elGalleryGrid.appendChild(card);
    }
    
    lucide.createImages(); // Inicializar iconos de Lucide en la tarjeta
}

// ==========================================================================
// FILTRADO DE LA GALERÍA
// ==========================================================================
elGalleryFilters.forEach(button => {
    button.addEventListener('click', () => {
        elGalleryFilters.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        filterGalleryItems();
    });
});

function filterGalleryItems() {
    const activeFilter = document.querySelector('.filter-btn.active').getAttribute('data-filter');
    const cards = elGalleryGrid.querySelectorAll('.insect-card');
    let visibleCount = 0;

    cards.forEach(card => {
        const species = card.getAttribute('data-species');
        if (activeFilter === 'all' || species === activeFilter) {
            card.style.display = 'flex';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });

    if (visibleCount === 0 && cards.length > 0) {
        elGalleryEmpty.classList.remove('hidden');
    } else if (cards.length === 0) {
        elGalleryEmpty.classList.remove('hidden');
    } else {
        elGalleryEmpty.classList.add('hidden');
    }
}

// ==========================================================================
// GRAFICOS DE TENDENCIAS (CHART.JS)
// ==========================================================================
function initChart() {
    const ctx = document.getElementById('trendsChart').getContext('2d');
    
    // Configuración base de Chart.js con estilos oscuros premium
    Chart.defaults.color = '#a0aec0';
    Chart.defaults.font.family = "'Inter', sans-serif";

    trendsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Abejas',
                    borderColor: '#ffb800',
                    backgroundColor: 'rgba(255, 184, 0, 0.05)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    data: []
                },
                {
                    label: 'Escarabajos',
                    borderColor: '#a0522d',
                    backgroundColor: 'rgba(160, 82, 45, 0.05)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    data: []
                },
                {
                    label: 'Avispas',
                    borderColor: '#ff4500',
                    backgroundColor: 'rgba(255, 69, 0, 0.05)',
                    borderWidth: 3,
                    tension: 0.4,
                    fill: true,
                    data: []
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        padding: 15,
                        font: { size: 12, weight: 500 }
                    }
                },
                tooltip: {
                    backgroundColor: '#161a25',
                    titleColor: '#fff',
                    bodyColor: '#a0aec0',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 8,
                    displayColors: true
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { stepSize: 1, precision: 0 }
                }
            }
        }
    });
}

function updateChartData(statsData) {
    if (!trendsChart) return;

    const periodData = currentChartPeriod === 'hourly' ? statsData.hourly : statsData.daily;
    
    const labels = periodData.map(item => item.label);
    const abejas = periodData.map(item => item.Abeja);
    const escarabajos = periodData.map(item => item.Escarabajo);
    const avispas = periodData.map(item => item.Avispa);

    trendsChart.data.labels = labels;
    trendsChart.data.datasets[0].data = abejas;
    trendsChart.data.datasets[1].data = escarabajos;
    trendsChart.data.datasets[2].data = avispas;

    // Cambiar tipo de gráfico según período para mejor legibilidad visual
    if (currentChartPeriod === 'hourly') {
        trendsChart.config.type = 'line';
        // Habilitar suavizado e interpolado para líneas
        trendsChart.data.datasets.forEach(dataset => {
            dataset.tension = 0.4;
            dataset.fill = true;
        });
    } else {
        trendsChart.config.type = 'bar';
        // Para barra desactivamos rellenos de línea
        trendsChart.data.datasets.forEach(dataset => {
            dataset.fill = false;
        });
    }

    trendsChart.update('active');
}

// Botones de cambio de período
elBtnChartHourly.addEventListener('click', () => {
    elBtnChartHourly.classList.add('active');
    elBtnChartDaily.classList.remove('active');
    currentChartPeriod = 'hourly';
    fetchStats();
});

elBtnChartDaily.addEventListener('click', () => {
    elBtnChartDaily.classList.add('active');
    elBtnChartHourly.classList.remove('active');
    currentChartPeriod = 'daily';
    fetchStats();
});

// ==========================================================================
// MODAL DE VISUALIZACIÓN DE IMÁGENES AMPLIADAS
// ==========================================================================
function openImageModal(imgSrc, captionText) {
    elImageModal.style.display = "flex";
    elModalImg.src = imgSrc;
    elModalCaption.textContent = captionText;
}

elModalClose.addEventListener('click', () => {
    elImageModal.style.display = "none";
});

// Cerrar al hacer click fuera de la imagen
elImageModal.addEventListener('click', (e) => {
    if (e.target === elImageModal) {
        elImageModal.style.display = "none";
    }
});

// ==========================================================================
// CONTROL DE ORIGEN DE VIDEO E INFO
// ==========================================================================
async function detectCameraMode() {
    // Consultar el origen de la cámara
    // En una SPA real, podemos deducir si es simulación o real a partir de la API
    // En este caso, haremos una inferencia simple.
    // El backend corre en modo mock si pasamos --mock-camera. 
    // Podemos deducir el modo pidiendo la información en la carga
    try {
        const res = await fetch('/api/stats');
        // Un chequeo rápido para actualizar textos HUD descriptivos
        // El script se adapta al backend automáticamente
    } catch(e) {}
    
    // Leemos los parámetros URL para dar detalles del modo
    const urlParams = new URLSearchParams(window.location.search);
    const mockParam = urlParams.get('mock');
    
    // Configuramos HUD informativos
    const isMock = true; // Por defecto asumido para la simulación inicial
    elHudMode.textContent = "MODE: SEBUG AI ACTIVE";
    elCameraSourceInfo.textContent = "Fuente: Stream procesado por IA";
}

// ==========================================================================
// INICIALIZACIÓN
// ==========================================================================
window.addEventListener('DOMContentLoaded', () => {
    lucide.createImages();
    initChart();
    detectCameraMode();
    
    // Conectar WebSocket (esto gatillará la carga inicial de datos)
    connectWebSocket();
});
