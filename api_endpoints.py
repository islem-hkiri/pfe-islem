"""
api_endpoints.py - API pour communication avec ESP32
Version sans uvicorn (compatible avec tout environnement)
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sqlite3
import os
from datetime import datetime
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gestion_production.db")

class APIHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == "/api/etat":
            query = urllib.parse.parse_qs(parsed_path.query)
            shift = query.get("shift", ["A"])[0]
            self.send_etat(shift)
            
        elif parsed_path.path == "/api/health":
            self.send_health()
        else:
            self.send_error(404, "Not found")
    
    def do_POST(self):
        if self.path == "/api/increment":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            shift = data.get("shift", "A")
            self.send_increment(shift)
            
        elif self.path == "/api/decrement":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            shift = data.get("shift", "A")
            self.send_decrement(shift)
        else:
            self.send_error(404, "Not found")
    
    def send_response_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def send_etat(self, shift):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, reference, quantite, statut
            FROM Demandes
            WHERE shift = ? AND statut IN ('🟢En cours', '🟠En attente')
            ORDER BY CASE WHEN statut = '🟢En cours' THEN 1 ELSE 2 END, id ASC
            LIMIT 1
        """, (shift,))
        demande = cursor.fetchone()
        
        if not demande:
            conn.close()
            self.send_response_json({
                "machine_disponible": True,
                "demande_id": None,
                "quantite_requise": 0,
                "compteur_actuel": 0
            })
            return
        
        demande_id, reference, quantite_requise, statut = demande
        
        cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
        etat = cursor.fetchone()
        compteur_actuel = etat[0] if etat else 0
        
        machine_disponible = (statut != '🟢En cours')
        
        conn.close()
        self.send_response_json({
            "machine_disponible": machine_disponible,
            "demande_id": demande_id,
            "quantite_requise": quantite_requise,
            "compteur_actuel": compteur_actuel
        })
    
    def send_increment(self, shift):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, quantite, reference
            FROM Demandes
            WHERE shift = ? AND statut = '🟢En cours'
            ORDER BY id ASC LIMIT 1
        """, (shift,))
        demande = cursor.fetchone()
        
        if not demande:
            conn.close()
            self.send_response_json({"success": False, "message": "Aucune production en cours", "termine": False, "compteur": 0})
            return
        
        demande_id, quantite_requise, reference = demande
        
        cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
        etat = cursor.fetchone()
        if etat:
            compteur_actuel = etat[0] + 1
            cursor.execute("UPDATE EtatMachine SET compteur_actuel = ?, last_update = datetime('now') WHERE shift = ?", (compteur_actuel, shift))
        else:
            compteur_actuel = 1
            cursor.execute("INSERT INTO EtatMachine (shift, compteur_actuel, last_update) VALUES (?, ?, datetime('now'))", (shift, compteur_actuel))
        
        termine = (compteur_actuel >= quantite_requise)
        
        if termine:
            cursor.execute("""
                UPDATE Demandes
                SET statut = 'Terminé', fin_production = datetime('now')
                WHERE id = ?
            """, (demande_id,))
            
            cursor.execute("""
                UPDATE Stock
                SET quantite = quantite + ?
                WHERE reference = ?
            """, (quantite_requise, reference))
            
            cursor.execute("UPDATE EtatMachine SET compteur_actuel = 0 WHERE shift = ?", (shift,))
            
            cursor.execute("""
                SELECT id
                FROM Demandes
                WHERE shift = ? AND statut = '🟠En attente'
                ORDER BY 
                    CASE urgence WHEN 'Critique' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END,
                    id ASC
                LIMIT 1
            """, (shift,))
            next_demande = cursor.fetchone()
            
            if next_demande:
                cursor.execute("""
                    UPDATE Demandes
                    SET statut = '🟢En cours', debut_production = datetime('now')
                    WHERE id = ?
                """, (next_demande[0],))
                cursor.execute("UPDATE EtatMachine SET demande_id = ? WHERE shift = ?", (next_demande[0], shift))
        
        conn.commit()
        conn.close()
        
        self.send_response_json({
            "success": True,
            "termine": termine,
            "compteur": compteur_actuel
        })
    
    def send_decrement(self, shift):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
        etat = cursor.fetchone()
        
        if etat and etat[0] > 0:
            nouveau = etat[0] - 1
            cursor.execute("UPDATE EtatMachine SET compteur_actuel = ?, last_update = datetime('now') WHERE shift = ?", (nouveau, shift))
            conn.commit()
            conn.close()
            self.send_response_json({"success": True, "compteur": nouveau})
        else:
            conn.close()
            self.send_response_json({"success": False, "compteur": 0})
    
    def send_health(self):
        self.send_response_json({"status": "OK", "timestamp": datetime.now().isoformat()})
    
    def log_message(self, format, *args):
        pass  # Désactiver les logs du serveur HTTP

def run_api():
    port = 8502
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"[API] Serveur démarré sur le port {port}")
    server.serve_forever()