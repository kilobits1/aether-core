import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# ======================================================
# INIT FIREBASE (Enlace persistente)
# ======================================================
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    try:
        firebase_key = json.load(open("llave.json"))
    except:
        firebase_key = None

if firebase_key and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# LIBRERÍA DE SENSORES (Hardware Real)
# ======================================================
HARDWARE_LIBRARY = {
    "temperatura": """// Sensor DHT11/22
#include "DHT.h"
#define DHTPIN 4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);
void setup() { Serial.begin(115200); dht.begin(); }
void loop() { float t = dht.readTemperature(); Serial.println(t); delay(2000); }""",
    
    "distancia": """// Sensor Ultrasonico HC-SR04
const int trigPin = 5; const int echoPin = 18;
void setup() { pinMode(trigPin, OUTPUT); pinMode(echoPin, INPUT); Serial.begin(115200); }
void loop() { digitalWrite(trigPin, LOW); delayMicroseconds(2); digitalWrite(trigPin, HIGH); delayMicroseconds(10); digitalWrite(trigPin, LOW); 
long duration = pulseIn(echoPin, HIGH); float distance = duration * 0.034 / 2; Serial.println(distance); delay(500); }""",

    "movimiento": """// Sensor PIR
const int pirPin = 13;
void setup() { pinMode(pirPin, INPUT); Serial.begin(115200); }
void loop() { if(digitalRead(pirPin) == HIGH) { Serial.println("Movimiento detectado!"); } delay(100); }"""
}

# ======================================================
# CORE LOGIC
# ======================================================
def aether_advanced(command, session="default"):
    t = command.lower()
    
    # Detección de Hardware
    found_sensor = None
    for sensor in HARDWARE_LIBRARY.keys():
        if sensor in t:
            found_sensor = sensor
            break
    
    # Registro en Firebase (Memoria)
    event_data = {
        "time": datetime.datetime.utcnow().isoformat(),
        "command": command,
        "type": "hardware_dev" if found_sensor else "general_order",
        "agent": "aether-core",
        "session": session
    }
    db.collection("aether_memory").add(event_data)

    # Generación de Salida
    if found_sensor:
        return f"⚙️ GENERADOR DE HARDWARE AETHER\n\nSensor detectado: {found_sensor.upper()}\n\nCódigo para ESP32:\n\n{HARDWARE_LIBRARY[found_sensor]}\n\nEstado: Código de ingeniería listo para cargar."
    
    return f"📄 ORDEN RECIBIDA: {command}\n\nEstado: No se detectó un sensor específico. Especifica 'temperatura', 'distancia' o 'movimiento' para generar firmware."

# ======================================================
# INTERFAZ (Gradio)
# ======================================================
with gr.Blocks(title="AETHER ADVANCED HW") as demo:
    gr.Markdown("## 🧠 Aether Core - Fase 3: Ingeniería de Sensores")
    with gr.Row():
        inp = gr.Textbox(label="Orden Técnica", placeholder="Ej: Generar código para sensor de temperatura")
        sess = gr.Textbox(label="Sesión", value="default")
    out = gr.Textbox(label="Firmware / Artefacto", lines=15)
    btn = gr.Button("Ejecutar Ingeniería")
    btn.click(aether_advanced, inputs=[inp, sess], outputs=out)

demo.launch()
