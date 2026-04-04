from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

def get_db_connection():
    return sqlite3.connect('gestion_production.db')

@app.route('/get_task_info', methods=['GET'])
def get_task_info():
    conn = get_db_connection()
    # On cherche la tâche "En cours" ou la prochaine "En attente"
    task = conn.execute("SELECT id, quantite FROM Demandes WHERE statut='En cours' OR statut='En attente' LIMIT 1").fetchone()
    conn.close()
    if task:
        return jsonify({"id": task[0], "quantite_cible": task[1]})
    return jsonify({"error": "Pas de tâche"}), 404

@app.route('/lancer_tache', methods=['POST'])
def lancer():
    # Code pour changer le statut en 'En cours' dans la DB
    return jsonify({"status": "Success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) # 0.0.0.0 permet d'être vu par l'ESP32 plus tard