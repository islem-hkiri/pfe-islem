import streamlit as st
import threading

# Importer et démarrer le serveur UDP
from udp_server import start_udp_server
start_udp_server()

# Importer et démarrer l'API (sans uvicorn)
from api_endpoints import run_api
threading.Thread(target=run_api, daemon=True).start()

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