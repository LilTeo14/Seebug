const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const REGISTROS_DIR = path.join(__dirname, 'registros');

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' })); // Permitir payloads grandes para Base64

// Asegurar que la carpeta de registros exista
if (!fs.existsSync(REGISTROS_DIR)) {
    fs.mkdirSync(REGISTROS_DIR);
}

// Servir la carpeta de registros estáticamente para poder ver las imágenes
app.use('/registros', express.static(REGISTROS_DIR));

// Ruta principal: Servir el Dashboard
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'BICHOS_Dashboard.html'));
});

// Endpoint para guardar una nueva detección con foto
app.post('/api/save-detection', (req, res) => {
    const { species, role, imageBase64 } = req.body;
    
    if (!species || !imageBase64) {
        return res.status(400).json({ error: "Faltan datos (species o imageBase64)" });
    }

    try {
        const timestamp = Date.now();
        const safeSpeciesName = species.replace(/[^a-zA-Z0-9]/g, '_');
        const filename = `${timestamp}_${safeSpeciesName}.jpg`;
        const filepath = path.join(REGISTROS_DIR, filename);

        // Guardar el archivo físico
        const imageBuffer = Buffer.from(imageBase64, 'base64');
        fs.writeFileSync(filepath, imageBuffer);

        // Opcional: También podríamos guardar un JSON con metadatos si quisieramos
        const metadataFilename = `${timestamp}_${safeSpeciesName}.json`;
        const metadataPath = path.join(REGISTROS_DIR, metadataFilename);
        const metadata = {
            timestamp,
            species,
            role,
            filename
        };
        fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));

        console.log(`✅ Registro guardado: ${filename}`);
        res.json({ success: true, filename });
    } catch (err) {
        console.error("Error guardando imagen:", err);
        res.status(500).json({ error: "Error interno del servidor" });
    }
});

// Endpoint para listar la galería
app.get('/api/gallery', (req, res) => {
    try {
        const files = fs.readdirSync(REGISTROS_DIR);
        // Filtrar solo los JSON para leer metadatos, o armar la info desde los JPG
        const metadataFiles = files.filter(f => f.endsWith('.json'));
        
        let galleryData = metadataFiles.map(file => {
            const data = JSON.parse(fs.readFileSync(path.join(REGISTROS_DIR, file)));
            return data;
        });

        // Ordenar de más reciente a más antiguo
        galleryData.sort((a, b) => b.timestamp - a.timestamp);
        
        res.json(galleryData);
    } catch (err) {
        console.error("Error leyendo galería:", err);
        res.status(500).json({ error: "Error leyendo galería" });
    }
});

app.listen(PORT, () => {
    console.log(`\n========================================`);
    console.log(`🚀 Servidor Local BICHOS iniciado`);
    console.log(`👉 Abre tu navegador en: http://localhost:${PORT}`);
    console.log(`========================================\n`);
});
