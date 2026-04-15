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
/*
 * ESP32 Firmware - Poste Soudure Ultrasons
 * Version complète avec HTTP requests et LEDs
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiUDP.h>

// ==================== WiFi Configuration ====================
const char* ssid = "BEE HUAWEI-1CB0";        // ⚠️ Modifier
const char* password = "485754439C621CB0";     // ⚠️ Modifier

// ==================== UDP Discovery ====================
WiFiUDP udp;
const int UDP_PORT = 12345;
IPAddress serverIP;
bool serverFound = false;
unsigned long lastDiscovery = 0;
const unsigned long DISCOVERY_INTERVAL = 30000;

// ==================== Pins ====================
const int PIN_LIMIT_SWITCH = 13;
const int PIN_CANCEL_BUTTON = 12;
const int PIN_LED_ROUGE = 14;
const int PIN_LED_ORANGE = 27;
const int PIN_LED_VERTE = 26;

// ==================== Variables ====================
String currentShift = "A";
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;
bool lastLimitState = HIGH;
bool lastCancelState = HIGH;
unsigned long lastBlinkTime = 0;
bool blinkState = false;
unsigned long lastLEDUpdate = 0;
const unsigned long LED_UPDATE_INTERVAL = 1000;

// ==================== Setup ====================
void setup() {
  Serial.begin(115200);
  Serial.println("\n\n╔════════════════════════════════════╗");
  Serial.println("║   ESP32 - Poste Soudure Ultrasons  ║");
  Serial.println("╚════════════════════════════════════╝\n");
  
  // Configuration des pins
  pinMode(PIN_LIMIT_SWITCH, INPUT_PULLUP);
  pinMode(PIN_CANCEL_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED_ROUGE, OUTPUT);
  pinMode(PIN_LED_ORANGE, OUTPUT);
  pinMode(PIN_LED_VERTE, OUTPUT);
  
  // Éteindre toutes les LEDs
  digitalWrite(PIN_LED_ROUGE, LOW);
  digitalWrite(PIN_LED_ORANGE, LOW);
  digitalWrite(PIN_LED_VERTE, LOW);
  
  // Connexion WiFi
  Serial.print("📡 Connexion au WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connecté !");
    Serial.print("📡 IP locale: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ Échec de connexion WiFi");
  }
  
  // Démarrer UDP
  udp.begin(UDP_PORT);
  Serial.print("📡 UDP démarré sur port: ");
  Serial.println(UDP_PORT);
  
  // Découverte du serveur
  discoverServer();
}

// ==================== UDP Discovery ====================
void discoverServer() {
  Serial.println("🔍 Recherche du serveur Streamlit...");
  
  IPAddress broadcastIp = ~WiFi.subnetMask() | WiFi.gatewayIP();
  Serial.print("📡 Broadcast IP: ");
  Serial.println(broadcastIp);
  
  // Envoyer requête UDP
  udp.beginPacket(broadcastIp, UDP_PORT);
  const char* message = "WHO_IS_STREAMLIT_SERVER";
  udp.write((const uint8_t*)message, strlen(message));
  udp.endPacket();
  
  // Attendre réponse (3 secondes)
  unsigned long startTime = millis();
  while (millis() - startTime < 3000) {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      char buffer[255];
      int len = udp.read(buffer, 255);
      if (len > 0) {
        buffer[len] = '\0';
        if (strcmp(buffer, "STREAMLIT_SERVER_HERE") == 0) {
          serverIP = udp.remoteIP();
          serverFound = true;
          Serial.print("✅ Serveur trouvé ! IP: ");
          Serial.println(serverIP);
          
          // Clignotement LED verte pour confirmer
          for (int i = 0; i < 3; i++) {
            digitalWrite(PIN_LED_VERTE, HIGH);
            delay(200);
            digitalWrite(PIN_LED_VERTE, LOW);
            delay(200);
          }
          return;
        }
      }
    }
  }
  
  Serial.println("❌ Serveur non trouvé (réessai dans 30s)");
  serverFound = false;
}

// ==================== Incrémentation ====================
void incrementerProduction() {
  if (!serverFound) {
    Serial.println("⚠️ Pas de serveur - incrément ignoré");
    return;
  }
  
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":8502/api/increment";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  String body = "{\"shift\":\"" + currentShift + "\"}";
  Serial.print("📤 POST /api/increment -> ");
  Serial.println(body);
  
  int httpCode = http.POST(body);
  
  if (httpCode > 0) {
    String response = http.getString();
    Serial.print("📥 Réponse (" + String(httpCode) + "): ");
    Serial.println(response);
    
    if (response.indexOf("\"termine\":true") > 0) {
      Serial.println("🎉 Production terminée !");
    }
  } else {
    Serial.println("❌ Erreur HTTP: " + String(httpCode));
  }
  
  http.end();
}

// ==================== Décrémentation ====================
void decrementerProduction() {
  if (!serverFound) {
    Serial.println("⚠️ Pas de serveur - décrément ignoré");
    return;
  }
  
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":8502/api/decrement";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  
  String body = "{\"shift\":\"" + currentShift + "\"}";
  Serial.print("📤 POST /api/decrement -> ");
  Serial.println(body);
  
  int httpCode = http.POST(body);
  
  if (httpCode > 0) {
    String response = http.getString();
    Serial.print("📥 Réponse (" + String(httpCode) + "): ");
    Serial.println(response);
  } else {
    Serial.println("❌ Erreur HTTP: " + String(httpCode));
  }
  
  http.end();
}

// ==================== Mise à jour des LEDs ====================
void mettreAJourLEDs() {
  if (!serverFound) {
    // LED orange clignotante = recherche serveur
    if (millis() - lastBlinkTime > 500) {
      blinkState = !blinkState;
      digitalWrite(PIN_LED_ORANGE, blinkState);
      digitalWrite(PIN_LED_VERTE, LOW);
      digitalWrite(PIN_LED_ROUGE, LOW);
      lastBlinkTime = millis();
    }
    return;
  }
  
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":8502/api/etat?shift=" + currentShift;
  http.begin(url);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String payload = http.getString();
    
    if (payload.indexOf("\"machine_disponible\":true") > 0) {
      digitalWrite(PIN_LED_VERTE, HIGH);
      digitalWrite(PIN_LED_ROUGE, LOW);
      
      if (payload.indexOf("\"demande_id\":null") == -1 && 
          payload.indexOf("\"demande_id\":0") == -1) {
        digitalWrite(PIN_LED_ORANGE, HIGH);
      } else {
        digitalWrite(PIN_LED_ORANGE, LOW);
      }
    } else {
      digitalWrite(PIN_LED_VERTE, LOW);
      digitalWrite(PIN_LED_ROUGE, HIGH);
      digitalWrite(PIN_LED_ORANGE, LOW);
    }
  } else {
    Serial.print("❌ Erreur GET /api/etat: ");
    Serial.println(httpCode);
  }
  
  http.end();
}

// ==================== Loop Principal ====================
void loop() {
  // Lecture des entrées
  bool limitState = digitalRead(PIN_LIMIT_SWITCH);
  bool cancelState = digitalRead(PIN_CANCEL_BUTTON);
  
  // Debounce et détection des appuis
  if ((millis() - lastDebounceTime) > debounceDelay) {
    
    // Pédale appuyée (HIGH -> LOW)
    if (lastLimitState == HIGH && limitState == LOW) {
      Serial.println("\n🔘 [ACTION] Pédale appuyée");
      incrementerProduction();
    }
    
    // Bouton annulation appuyé (HIGH -> LOW)
    if (lastCancelState == HIGH && cancelState == LOW) {
      Serial.println("\n🔘 [ACTION] Annulation appuyée");
      decrementerProduction();
    }
    
    lastDebounceTime = millis();
  }
  
  lastLimitState = limitState;
  lastCancelState = cancelState;
  
  // Découverte périodique du serveur
  if (millis() - lastDiscovery > DISCOVERY_INTERVAL) {
    discoverServer();
    lastDiscovery = millis();
  }
  
  // Mise à jour périodique des LEDs
  if (millis() - lastLEDUpdate > LED_UPDATE_INTERVAL) {
    mettreAJourLEDs();
    lastLEDUpdate = millis();
  }
  
  delay(50);
}
