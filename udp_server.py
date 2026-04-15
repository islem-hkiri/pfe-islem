"""
udp_server.py - Découverte automatique du serveur
===================================================
Ce serveur UDP permet à l'ESP32 de trouver automatiquement l'IP du serveur
sans avoir à la configurer manuellement.
"""

import socket
import threading
import time

UDP_PORT = 12345
BROADCAST_MESSAGE = b"STREAMLIT_SERVER_HERE"

def udp_listener():
    """Écoute les requêtes UDP et répond avec l'IP du serveur"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', UDP_PORT))
    print(f"[UDP] Serveur de découverte lancé sur le port {UDP_PORT}")
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            if data == b"WHO_IS_STREAMLIT_SERVER":
                print(f"[UDP] Requête de découverte reçue de {addr[0]}")
                sock.sendto(BROADCAST_MESSAGE, addr)
        except Exception as e:
            print(f"[UDP] Erreur: {e}")

def start_udp_server():
    """Démarre le serveur UDP dans un thread séparé"""
    thread = threading.Thread(target=udp_listener, daemon=True)
    thread.start()
    print("[UDP] Serveur de découverte démarré")

if __name__ == "__main__":
    start_udp_server()
    print("[UDP] Serveur en fonctionnement. Appuyez sur Ctrl+C pour arrêter.")
    while True:
        time.sleep(1)