"""
operateur_app.py - Interface Opérateur (Mode Automatique)
==========================================================
Ce fichier remplace l'ancienne version avec boutons manuels.
Les fonctionnalités :
- Plus de boutons "Lancer production" ni "Terminer"
- Affichage automatique de l'état de la machine et du compteur
- Le bouton "Lancer" devient visuellement "Démarré automatiquement" quand la prod est lancée
- Connexion à l'API pour lire l'état en temps réel
"""

import streamlit as st
import sqlite3
import pandas as pd
import os
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ==================== CONFIGURATION ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gestion_production.db")

# ⚠️ IMPORTANT: L'IP sera détectée automatiquement par ESP32
# Pour l'affichage dans Streamlit, on utilise localhost car le navigateur est sur le même PC
API_URL = "http://localhost:8501"

st.set_page_config(page_title="Poste Soudure Ultrasons - Mode Auto")
st_autorefresh(interval=2000, key="auto_refresh")  # Rafraîchir toutes les 2 secondes

# ==================== INIT SESSION ====================
if 'task_counter' not in st.session_state:
    st.session_state.task_counter = 0

def generate_unique_key(base_name):
    st.session_state.task_counter += 1
    return f"{base_name}_{st.session_state.task_counter}"

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("👤 Identification")
    id_op_saisie = st.text_input("ID Opérateur (Saisie)", key="operateur_id")
    shift = st.radio("Shift", ["A", "B"], key="shift_selection", horizontal=True)
    
    # Afficher l'état de la connexion à l'API
    try:
        response = requests.get(f"{API_URL}/api/etat", params={"shift": shift}, timeout=1)
        if response.status_code == 200:
            st.success("✅ Connecté au serveur")
        else:
            st.warning("⚠️ Serveur API lent")
    except:
        st.error("❌ Serveur API inaccessible")
    
    st.markdown("---")
    
    # Signalement de panne
    st.subheader("⚠️ Signalement Panne")
    with st.expander("Déclarer une Panne"):
        cause = st.text_input("Cause de la panne", key="panne_cause")
        
        if st.button("Signaler Panne", key="signal_panne_btn"):
            if cause and id_op_saisie:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("""
                        INSERT INTO Pannes (operateur_id, cause, debut_panne, statut)
                        VALUES (?, ?, datetime('now'), '🔴 Ouvert')
                    """, (id_op_saisie, cause))
                    conn.commit()
                    st.error("🚨 Panne signalée au superviseur !")
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
                finally:
                    conn.close()
            else:
                st.warning("Saisir ID opérateur + cause")

    # Historique des tâches terminées
    st.markdown("---")
    with st.expander("📜 Historique"):
        try:
            conn = sqlite3.connect(DB_PATH)
            query = """
            SELECT 
                p.module, 
                d.operateur_id,
                d.debut_production,
                d.fin_production,
                (strftime('%s', d.fin_production) - strftime('%s', d.debut_production)) as duree_sec,
                p.pression,
                p.temps,
                p.amplitude
            FROM Demandes d
            JOIN Produits p ON d.reference = p.reference
            WHERE d.shift = ?
            AND d.statut = 'Terminé'
            ORDER BY d.fin_production DESC
            LIMIT 20
            """
            hist = conn.execute(query, (shift,)).fetchall()

            if hist:
                df = pd.DataFrame(hist, columns=[
                    "Module","Opérateur","Début","Fin","Durée(s)","Pression","Temps","Amplitude"
                ])
                st.dataframe(df, use_container_width=True)

                if st.button("Effacer l'historique", key="clear_history_btn"):
                    conn.execute("""
                    UPDATE Demandes 
                    SET statut = 'Archivé' 
                    WHERE shift = ? AND statut = 'Terminé'
                    """, (shift,))
                    conn.commit()
                    st.rerun()
            else:
                st.info("Aucune tâche terminée récemment")
        except Exception as e:
            st.error(f"Erreur base de données: {str(e)}")
        finally:
            conn.close()

# ==================== INTERFACE PRINCIPALE ====================
st.title(f"🔧 Poste Soudure Ultrasons - Shift {shift}")
st.markdown("### Mode Automatique (Contrôle par pédale)")

# ==================== AFFICHAGE ÉTAT MACHINE ====================
try:
    response = requests.get(f"{API_URL}/api/etat", params={"shift": shift}, timeout=2)
    
    if response.status_code == 200:
        etat = response.json()
        demande_id = etat.get("demande_id")
        quantite_requise = etat.get("quantite_requise", 0)
        compteur_actuel = etat.get("compteur_actuel", 0)
        machine_disponible = etat.get("machine_disponible", True)
        
        # ========== AFFICHAGE DU COMPTEUR ==========
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if quantite_requise > 0:
                st.metric("📊 Production en cours", f"{compteur_actuel} / {quantite_requise}")
                # Barre de progression
                st.progress(compteur_actuel / quantite_requise)
            else:
                st.metric("📊 Production en cours", "Aucune demande")
        
        # ========== AFFICHAGE DES LEDS VIRTUELLES ==========
        with col2:
            if machine_disponible:
                st.success("🟢 Machine disponible")
            else:
                st.warning("🔴 Production en cours")
        
        with col3:
            if quantite_requise > 0 and not machine_disponible:
                st.info("🟡 En cours...")
            elif quantite_requise > 0 and machine_disponible:
                st.info("🟠 En attente")
        
        # ========== BOUTON "LANCER" AUTOMATIQUE (visuel seulement) ==========
        st.markdown("---")
        st.subheader("🎮 Contrôle production")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            # Ce bouton n'est plus cliquable pour lancer - il montre juste l'état
            if not machine_disponible and quantite_requise > 0:
                # Production en cours - bouton vert avec coche
                st.success("✅ Production lancée automatiquement")
            elif machine_disponible and quantite_requise > 0:
                # Demande en attente - bouton orange
                st.warning("⏳ En attente (appuyez sur pédale)")
            else:
                # Pas de demande
                st.info("📭 Aucune demande")
        
        with col_btn2:
            # Affichage de la référence en cours
            if demande_id:
                try:
                    conn = sqlite3.connect(DB_PATH)
                    ref_cursor = conn.execute("""
                        SELECT p.module, p.reference 
                        FROM Demandes d 
                        JOIN Produits p ON d.reference = p.reference 
                        WHERE d.id = ?
                    """, (demande_id,))
                    ref_info = ref_cursor.fetchone()
                    if ref_info:
                        st.metric("📦 Référence", ref_info[0])
                    conn.close()
                except:
                    pass
        
        with col_btn3:
            # Bouton d'annulation (manuel) - toujours présent
            if st.button("↩️ Annuler dernière pièce", key="cancel_btn", use_container_width=True):
                try:
                    cancel_response = requests.post(
                        f"{API_URL}/api/decrement",
                        json={"shift": shift},
                        timeout=2
                    )
                    if cancel_response.status_code == 200:
                        st.success("✅ Annulation envoyée")
                        st.rerun()
                    else:
                        st.error("❌ Erreur annulation")
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
        
        # ========== AFFICHAGE DES PARAMÈTRES DE SOUDURE ==========
        if demande_id:
            try:
                conn = sqlite3.connect(DB_PATH)
                params = conn.execute("""
                    SELECT p.pression, p.temps, p.amplitude
                    FROM Demandes d
                    JOIN Produits p ON d.reference = p.reference
                    WHERE d.id = ?
                """, (demande_id,)).fetchone()
                
                if params:
                    st.markdown("---")
                    st.subheader("⚙️ Paramètres soudure")
                    col_p1, col_p2, col_p3 = st.columns(3)
                    with col_p1:
                        st.metric("Pression", f"{params[0] if params[0] else '~'} bar")
                    with col_p2:
                        st.metric("Temps", f"{params[1] if params[1] else '~'} s")
                    with col_p3:
                        st.metric("Amplitude", f"{params[2] if params[2] else '~'} %")
                conn.close()
            except:
                pass
                
    else:
        st.error(f"Erreur API: Code {response.status_code}")
        
except requests.exceptions.ConnectionError:
    st.error("❌ Impossible de se connecter à l'API. Vérifiez que le serveur est lancé.")
except Exception as e:
    st.error(f"Erreur: {str(e)}")

# ==================== LISTE DES DEMANDES (Lecture seule) ====================
st.markdown("---")
st.subheader("📋 Liste des demandes en attente")

try:
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT 
        p.module,
        d.quantite,
        d.statut,
        d.id,
        d.urgence
    FROM Demandes d
    JOIN Produits p ON d.reference = p.reference
    WHERE d.shift = ?
    AND d.statut != 'Terminé'
    AND d.statut != 'Archivé'
    ORDER BY 
        CASE WHEN d.statut = '🟢En cours' THEN 1 ELSE 2 END,
        CASE d.urgence WHEN 'Critique' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END,
        d.id ASC
    """
    tasks = conn.execute(query, (shift,)).fetchall()
    
    if tasks:
        for mod, qte, statut, id_d, urgence in tasks:
            # Choisir la couleur selon le statut
            if statut == '🟢En cours':
                status_color = "🟢"
            elif statut == '🟠En attente':
                status_color = "🟠"
            else:
                status_color = "⚪"
            
            # Afficher chaque demande
            st.markdown(f"{status_color} **{mod}** | Qté: {qte} | Urgence: {urgence} | {statut}")
    else:
        st.success("✅ Aucune demande en attente")
        
except Exception as e:
    st.error(f"Erreur chargement demandes: {e}")
finally:
    conn.close()

# ==================== INSTRUCTIONS POUR L'OPÉRATEUR ====================
with st.expander("📖 Instructions"):
    st.markdown("""
    ### Comment utiliser ce poste (Mode Automatique)
    
    1. **Sélectionnez votre Shift (A ou B)** dans la barre latérale
    2. **Entrez votre ID Opérateur**
    3. **La machine gère automatiquement** le lancement et l'arrêt des productions
    
    ### Contrôle par pédale :
    - **Appuyez sur la pédale** → +1 pièce produite
    - **Bouton Annulation** → -1 pièce (en cas d'erreur)
    
    ### Signalisation lumineuse :
    - 🟢 **Vert** : Machine disponible, prête à produire
    - 🟠 **Orange** : Demande en attente (appuyez sur pédale pour démarrer)
    - 🔴 **Rouge** : Production en cours
    
    ### En cas de panne :
    Utilisez le formulaire dans la barre latérale pour signaler immédiatement le problème.
    """)