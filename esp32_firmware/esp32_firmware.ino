/*
 * ESP32 Firmware - Poste Soudure Ultrasons
 * =========================================
 * Fonctionnalités :
 * - Lecture d'un limit switch (pédale) pour incrémenter le compteur
 * - Lecture d'un bouton d'annulation pour décrémenter
 * - Contrôle de 3 LEDs (Vert, Orange, Rouge)
 * - Découverte automatique du serveur via UDP broadcast
 * - Communication HTTP avec l'API FastAPI
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiUDP.h>

// ==================== CONFIGURATION WiFi ====================
const char* ssid = "VOTRE_SSID";        // ⚠️ À modifier
const char* password = "VOTRE_MDP";     // ⚠️ À modifier

// ==================== UDP Discovery ====================
WiFiUDP udp;
const int UDP_PORT = 12345;
IPAddress serverIP;                     // Sera découverte automatiquement
bool serverFound = false;
unsigned long lastDiscovery = 0;
const unsigned long DISCOVERY_INTERVAL = 30000;  // Chercher serveur toutes les 30s

// ==================== Pins ====================
const int PIN_LIMIT_SWITCH = 13;    // Pédale (entrée avec pull-up)
const int PIN_CANCEL_BUTTON = 12;   // Bouton annulation
const int PIN_LED_ROUGE = 14;       // LED rouge (production en cours)
const int PIN_LED_ORANGE = 27;      // LED orange (demande en attente)
const int PIN_LED_VERTE = 26;       // LED verte (machine disponible)

// ==================== Variables ====================
String currentShift = "A";           // Shift par défaut (peut être changé via API)
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;
bool lastLimitState = HIGH;
bool lastCancelState = HIGH;

// ==================== Setup ====================
void setup() {
  Serial.begin(115200);
  
  // Configuration des pins
