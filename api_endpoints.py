"""
api_endpoints.py - API pour communication avec ESP32
=====================================================
Ce fichier expose des endpoints HTTP que l'ESP32 utilise pour :
- Récupérer l'état actuel de la machine
- Incrémenter/décrémenter le compteur
- Démarrer automatiquement la production suivante
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
import threading
import uvicorn

# ==================== CONFIGURATION ====================
app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gestion_production.db")

# ==================== MODÈLES DE DONNÉES ====================
class IncrementRequest(BaseModel):
    shift: str

class DecrementRequest(BaseModel):
    shift: str

# ==================== FONCTIONS UTILITAIRES ====================
def get_db():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect(DB_PATH)

def get_current_demande(shift):
    """Récupère la demande en cours ou la première en attente pour un shift"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Chercher d'abord une demande en cours
    cursor.execute("""
        SELECT id, reference, quantite, statut
        FROM Demandes
        WHERE shift = ? AND statut = '🟢En cours'
        ORDER BY id ASC LIMIT 1
    """, (shift,))
    demande = cursor.fetchone()
    
    # Sinon, prendre la première en attente
    if not demande:
        cursor.execute("""
            SELECT id, reference, quantite, statut
            FROM Demandes
            WHERE shift = ? AND statut = '🟠En attente'
            ORDER BY 
                CASE urgence WHEN 'Critique' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END,
                id ASC
            LIMIT 1
        """, (shift,))
        demande = cursor.fetchone()
    
    conn.close()
    return demande

# ==================== ENDPOINTS API ====================

@app.get("/api/etat")
def get_etat(shift: str):
    """
    Endpoint pour ESP32 : retourne l'état actuel de la machine
    - machine_disponible: True si pas de production en cours
    - demande_id: ID de la demande active (ou None)
    - quantite_requise: Quantité totale à produire
    - compteur_actuel: Nombre de pièces déjà produites
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Chercher demande en cours ou en attente
    demande = get_current_demande(shift)
    
    if not demande:
        conn.close()
        return {
            "machine_disponible": True,
            "demande_id": None,
            "quantite_requise": 0,
            "compteur_actuel": 0
        }
    
    demande_id, reference, quantite_requise, statut = demande
    
    # Lire compteur actuel depuis EtatMachine
    cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
    etat = cursor.fetchone()
    compteur_actuel = etat[0] if etat else 0
    
    # Si une demande est en attente et qu'on a appelé cet endpoint,
    # on ne lance pas automatiquement ici (c'est l'ESP32 qui décide)
    machine_disponible = (statut != '🟢En cours')
    
    conn.close()
    return {
        "machine_disponible": machine_disponible,
        "demande_id": demande_id,
        "quantite_requise": quantite_requise,
        "compteur_actuel": compteur_actuel
    }

@app.post("/api/increment")
def increment_counter(req: IncrementRequest):
    """
    Endpoint pour ESP32 : incrémente le compteur de +1
    Retourne:
    - success: True/False
    - termine: True si la quantité est atteinte
    - compteur: Nouvelle valeur du compteur
    """
    conn = get_db()
    cursor = conn.cursor()
    shift = req.shift
    
    # Chercher demande en cours
    cursor.execute("""
        SELECT id, quantite, reference
        FROM Demandes
        WHERE shift = ? AND statut = '🟢En cours'
        ORDER BY id ASC LIMIT 1
    """, (shift,))
    demande = cursor.fetchone()
    
    if not demande:
        conn.close()
        return {"success": False, "message": "Aucune production en cours", "termine": False, "compteur": 0}
    
    demande_id, quantite_requise, reference = demande
    
    # Lire et incrémenter le compteur
    cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
    etat = cursor.fetchone()
    if etat:
        compteur_actuel = etat[0] + 1
        cursor.execute("UPDATE EtatMachine SET compteur_actuel = ?, last_update = datetime('now') WHERE shift = ?", 
                      (compteur_actuel, shift))
    else:
        compteur_actuel = 1
        cursor.execute("INSERT INTO EtatMachine (shift, compteur_actuel, last_update) VALUES (?, ?, datetime('now'))", 
                      (shift, compteur_actuel))
    
    termine = (compteur_actuel >= quantite_requise)
    
    if termine:
        # 1. Terminer la demande actuelle
        cursor.execute("""
            UPDATE Demandes
            SET statut = 'Terminé', fin_production = datetime('now')
            WHERE id = ?
        """, (demande_id,))
        
        # 2. Mettre à jour le stock
        cursor.execute("""
            UPDATE Stock
            SET quantite = quantite + ?
            WHERE reference = ?
        """, (quantite_requise, reference))
        
        # 3. Remettre le compteur à 0
        cursor.execute("UPDATE EtatMachine SET compteur_actuel = 0 WHERE shift = ?", (shift,))
        
        # 4. Démarrer automatiquement la prochaine demande (si elle existe)
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
            # Lancer automatiquement la prochaine demande
            cursor.execute("""
                UPDATE Demandes
                SET statut = '🟢En cours', debut_production = datetime('now')
                WHERE id = ?
            """, (next_demande[0],))
            
            # Mettre à jour EtatMachine avec le nouvel ID
            cursor.execute("UPDATE EtatMachine SET demande_id = ? WHERE shift = ?", (next_demande[0], shift))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True, 
        "termine": termine, 
        "compteur": compteur_actuel
    }

@app.post("/api/decrement")
def decrement_counter(req: DecrementRequest):
    """
    Endpoint pour ESP32 : décrémente le compteur de -1 (annulation)
    """
    conn = get_db()
    cursor = conn.cursor()
    shift = req.shift
    
    cursor.execute("SELECT compteur_actuel FROM EtatMachine WHERE shift = ?", (shift,))
    etat = cursor.fetchone()
    
    if etat and etat[0] > 0:
        nouveau = etat[0] - 1
        cursor.execute("UPDATE EtatMachine SET compteur_actuel = ?, last_update = datetime('now') WHERE shift = ?", 
                      (nouveau, shift))
        conn.commit()
        conn.close()
        return {"success": True, "compteur": nouveau}
    
    conn.close()
    return {"success": False, "compteur": 0}

@app.get("/api/health")
def health_check():
    """Endpoint simple pour vérifier que l'API fonctionne"""
    return {"status": "OK", "timestamp": datetime.now().isoformat()}

# ==================== LANCEMENT DU SERVEUR API ====================
def run_api():
    """Lance le serveur FastAPI sur le port 8502 (pour ne pas conflit avec Streamlit)"""
    uvicorn.run(app, host="0.0.0.0", port=8502)

if __name__ == "__main__":
    run_api()