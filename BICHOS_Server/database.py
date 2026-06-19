import sqlite3
from datetime import datetime

DB_NAME = "bichos.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            species TEXT,
            ecological_role TEXT,
            action TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_detection(species: str, role: str, action: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO detections (timestamp, species, ecological_role, action)
        VALUES (?, ?, ?, ?)
    ''', (timestamp, species, role, action))
    conn.commit()
    conn.close()

def get_recent_detections(limit=10):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, species, ecological_role, action FROM detections ORDER BY id DESC LIMIT ?', (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {"timestamp": r[0], "species": r[1], "ecological_role": r[2], "action": r[3]}
        for r in rows
    ]

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM detections WHERE ecological_role='Plaga'")
    plagas = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM detections WHERE ecological_role='Nativo'")
    nativos = cursor.fetchone()[0]
    conn.close()
    return {"plagas": plagas, "nativos": nativos, "total": plagas + nativos}
