import streamlit as st

# ← AJOUT : Importer et démarrer le serveur UDP pour découverte automatique
from udp_server import start_udp_server
start_udp_server()

# ← AJOUT : Importer et démarrer l'API FastAPI dans un thread séparé
import threading
import uvicorn
from api_endpoints import app as api_app

def run_fastapi():
    uvicorn.run(api_app, host="0.0.0.0", port=8502, log_level="warning")

threading.Thread(target=run_fastapi, daemon=True).start()

# ========== LE RESTE DE TON CODE ORIGINAL ==========
if "role" not in st.session_state:
    st.session_state.role = None

def login():
    st.title("Connexion")
    user = st.text_input("Utilisateur (Logistique ou Opérateur)")
    password = st.text_input("Mot de passe", type="password")
    
    if st.button("Se connecter"):
        if user.lower() == "logistique" and password == "log123":
            st.session_state.role = "Logistique"
            st.rerun()
        elif user.lower() == "operateur" and password == "op123":
            st.session_state.role = "Opérateur"
            st.rerun()
        else:
            st.error("mot de passe incorrecte")

if st.session_state.role is None:
    login()
else:
    if st.sidebar.button("Déconnexion"):
        st.session_state.role = None
        st.rerun()

    if st.session_state.role == "Logistique":
        st.sidebar.success("Connecté : Logistique")
        exec(open("logistique_app.py").read())
        
    elif st.session_state.role == "Opérateur":
        st.sidebar.info("Connecté : Opérateur")
        exec(open("operateur_app.py").read())