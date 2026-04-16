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

// ==================== WiFi Configuration ====================
const char* ssid = "BEE HUAWEI-1CB0";        // ⚠️ Modifier
const char* password = "485754439C621CB0";     // ⚠️ Modifier

// ==================== Serveur fixe (plus de UDP) ====================
IPAddress serverIP(192, 168, 100, 5);        // ⚠️ Mettez l'IP de votre serveur ici
const int SERVER_PORT = 8502;                 // Port du serveur Streamlit

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
unsigned long lastLEDUpdate = 0;
const unsigned long LED_UPDATE_INTERVAL = 1000;

// ==================== Setup ====================
void setup() {
  Serial.begin(115200);
  Serial.println("\n\n╔════════════════════════════════════╗");
  Serial.println("║   ESP32 - Poste Soudure Ultrasons  ║");
  Serial.println("╚════════════════════════════════════╝\n");
  
  pinMode(PIN_LIMIT_SWITCH, INPUT_PULLUP);
  pinMode(PIN_CANCEL_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED_ROUGE, OUTPUT);
  pinMode(PIN_LED_ORANGE, OUTPUT);
  pinMode(PIN_LED_VERTE, OUTPUT);
  
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
  
  Serial.print("🌐 Serveur configuré à: ");
  Serial.println(serverIP);
}

// ==================== Incrémentation ====================
void incrementerProduction() {
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":" + String(SERVER_PORT) + "/api/increment";
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
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":" + String(SERVER_PORT) + "/api/decrement";
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

// ==================== Mise à jour des LEDs (sans UDP) ====================
void mettreAJourLEDs() {
  HTTPClient http;
  String url = "http://" + serverIP.toString() + ":" + String(SERVER_PORT) + "/api/etat?shift=" + currentShift;
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
    // Si erreur, on éteint tout sauf rouge clignotant ? (optionnel)
    digitalWrite(PIN_LED_VERTE, LOW);
    digitalWrite(PIN_LED_ORANGE, LOW);
    digitalWrite(PIN_LED_ROUGE, HIGH);
  }
  
  http.end();
}

// ==================== Loop Principal ====================
void loop() {
  bool limitState = digitalRead(PIN_LIMIT_SWITCH);
  bool cancelState = digitalRead(PIN_CANCEL_BUTTON);
  
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (lastLimitState == HIGH && limitState == LOW) {
      Serial.println("\n🔘 [ACTION] Pédale appuyée");
      incrementerProduction();
    }
    
    if (lastCancelState == HIGH && cancelState == LOW) {
      Serial.println("\n🔘 [ACTION] Annulation appuyée");
      decrementerProduction();
    }
    
    lastDebounceTime = millis();
  }
  
  lastLimitState = limitState;
  lastCancelState = cancelState;
  
  // Mise à jour périodique des LEDs
  if (millis() - lastLEDUpdate > LED_UPDATE_INTERVAL) {
    mettreAJourLEDs();
    lastLEDUpdate = millis();
  }
  
  delay(50);
}
