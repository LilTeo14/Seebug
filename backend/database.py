import sqlite3
import os
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, db_path="data/database.db"):
        self.db_path = db_path
        # Asegurar que las carpetas existan
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs("data/detections", exist_ok=True)
        self.init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insect_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    image_path TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_detection(self, insect_type: str, confidence: float, image_path: str) -> dict:
        timestamp = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO detections (insect_type, confidence, timestamp, image_path) VALUES (?, ?, ?, ?)",
                (insect_type, confidence, timestamp, image_path)
            )
            conn.commit()
            detection_id = cursor.lastrowid
            
        return {
            "id": detection_id,
            "insect_type": insect_type,
            "confidence": confidence,
            "timestamp": timestamp,
            "image_path": image_path
        }

    def get_recent_detections(self, limit: int = 50, offset: int = 0) -> list:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM detections ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """
        Retorna estadísticas agregadas:
        - Totales por tipo de insecto.
        - Historial por hora (últimas 24 horas).
        - Historial por día (últimos 7 días).
        """
        with self._get_connection() as conn:
            # 1. Totales por especie
            cursor = conn.execute(
                "SELECT insect_type, COUNT(*) as count FROM detections GROUP BY insect_type"
            )
            totals = {row["insect_type"]: row["count"] for row in cursor.fetchall()}
            for insect in ["Abeja", "Escarabajo", "Avispa"]:
                if insect not in totals:
                    totals[insect] = 0

            # 2. Historial de las últimas 24 horas (agrupado por hora)
            now = datetime.now()
            twenty_four_hours_ago = (now - timedelta(hours=24)).isoformat()
            
            cursor = conn.execute(
                """
                SELECT strftime('%Y-%m-%dT%H:00:00', timestamp) as hour_bucket, 
                       insect_type, 
                       COUNT(*) as count 
                FROM detections 
                WHERE timestamp >= ?
                GROUP BY hour_bucket, insect_type
                ORDER BY hour_bucket ASC
                """,
                (twenty_four_hours_ago,)
            )
            
            hourly_raw = cursor.fetchall()
            
            # Formatear el historial por hora para Chart.js
            # Queremos generar una lista de las últimas 24 horas y rellenar con 0 si no hay registros
            hourly_data = []
            for i in range(24):
                h = now - timedelta(hours=23 - i)
                h_str = h.strftime('%Y-%m-%dT%H:00:00')
                label = h.strftime('%H:00')
                
                # Buscar conteos
                counts = {"Abeja": 0, "Escarabajo": 0, "Avispa": 0}
                for row in hourly_raw:
                    if row["hour_bucket"] == h_str:
                        counts[row["insect_type"]] = row["count"]
                
                hourly_data.append({
                    "label": label,
                    "Abeja": counts["Abeja"],
                    "Escarabajo": counts["Escarabajo"],
                    "Avispa": counts["Avispa"]
                })

            # 3. Historial de los últimos 7 días (agrupado por día)
            seven_days_ago = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            cursor = conn.execute(
                """
                SELECT date(timestamp) as date_bucket, 
                       insect_type, 
                       COUNT(*) as count 
                FROM detections 
                WHERE timestamp >= ?
                GROUP BY date_bucket, insect_type
                ORDER BY date_bucket ASC
                """,
                (seven_days_ago,)
            )
            daily_raw = cursor.fetchall()
            
            daily_data = []
            # Días de la semana en español
            dias_semana = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
            
            for i in range(7):
                d = now - timedelta(days=6 - i)
                d_str = d.strftime('%Y-%m-%d')
                label = dias_semana[d.weekday()] + f" {d.day}"
                
                counts = {"Abeja": 0, "Escarabajo": 0, "Avispa": 0}
                for row in daily_raw:
                    if row["date_bucket"] == d_str:
                        counts[row["insect_type"]] = row["count"]
                        
                daily_data.append({
                    "label": label,
                    "Abeja": counts["Abeja"],
                    "Escarabajo": counts["Escarabajo"],
                    "Avispa": counts["Avispa"]
                })

            return {
                "totals": totals,
                "hourly": hourly_data,
                "daily": daily_data
            }
