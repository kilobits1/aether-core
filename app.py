import gradio as gr
import datetime
import json
import os

# ======================================================
# FIREBASE (OPCIONAL, NO ROMPE SI NO EXISTE)
# ======================================================
USE_FIREBASE = False
db = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if "FIREBASE_KEY" in os.environ:
        firebase_key = json.loads(os.environ["FIREBASE_KEY"])
        cred = credentials.Certificate(firebase_key)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        USE_FIREBASE = True
except Exception as e:
    print("Firebase desactivado:", e)

# ======================================================
# CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

# ======================================================
# DOMAIN MAP
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "quimica": ["reaccion", "molecula"],
    "electronica": ["voltaje", "corriente", "esp32", "relay"],
    "mecatronica": ["robot", "control", "actuador"],
    "medicina": ["tratamiento", "farmaco"],
    "nanotecnologia": ["nanobot", "nano"]
}

# ======================================================
# MODE SELECTION
# ======================================================
def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular"]):
        return "scientific"
    if any(k in t for k in ["diseñar", "crear", "generar"]):
        return "engineering"
    return "general"

# ======================================================
# DOMAIN DETECTION
# ======================================================
def detect_domains(command):
    t = command.lower()
    domains = []
    for domain, keys in DOMAIN_MAP.items():
        if any(k in t for k in keys):
            domains.append(domain)
    return domains if domains else ["general"]

# ======================================================
# COMMAND TYPE
# ======================================================
def classify_command(text):
    t = text.lower()
    if "estado" in t:
        return "system"
    if any(k in t for k in ["codigo", "programa", "firmware"]):
        return "code"
    if t.startswith(("crear", "diseñar", "generar")):
        return "task"
    return "order"

# ======================================================
# MEMORY
# ======================================================
def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["execution_mode"] = EXECUTION_MODE

    if USE_FIREBASE and db:
        db.collection("aether_memory").add(data)

# ======================================================
# DECISIÓN DE ARTEFACTO
# ======================================================
def decide_artifact(cmd_type, mode, domains):
    if cmd_type == "code":
        return "code"
    if "electronica" in domains or "mecatronica" in domains:
        return "engineering"
    if mode == "scientific":
        return "math"
    return "design"

# ======================================================
# GENERADORES
# ======================================================
def generate_code(domains):
    if "electronica" in domains:
        return """💻 CÓDIGO ESP32 (ARDUINO)

```cpp
#define RELAY_PIN 5

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
}

void loop() {
  digitalWrite(RELAY_PIN, HIGH);
  delay(1000);
  digitalWrite(RELAY_PIN, LOW);
  delay(1000);
}

