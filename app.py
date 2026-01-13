import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# ======================================================
# INIT FIREBASE
# ======================================================
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    # Intento local si no hay variable de entorno
    try:
        firebase_key = json.load(open("llave.json"))
    except:
        firebase_key = None

if firebase_key and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion"],
    "fisica": ["fuerza", "energia", "movimiento", "termodinamica"],
    "quimica": ["reaccion", "molecula", "compuesto"],
    "electronica": ["voltaje", "corriente", "sensor", "esp32", "pcb", "relay", "rele"],
    "mecanica": ["estructura", "engranaje", "dinamica"],
    "mecatronica": ["robot", "control", "actuador"],
    "medicina": ["tratamiento", "diagnostico", "farmaco"],
    "biologia": ["celula", "genetica", "organismo"],
    "nanotecnologia": ["nanobot", "nano", "molecular"],
    "aeroespacial": ["nasa", "orbita", "satelite", "cohete"]
}

def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular", "demostrar"]): return "scientific"
    if any(k in t for k in ["diseñar", "crear", "construir"]): return "engineering"
    return "general"

def detect_domains(command):
    t = command.lower()
    domains = [d for d, keywords in DOMAIN_MAP.items() if any(k in t for k in keywords)]
    return domains if domains else ["general"]

def classify_command(text):
    t = text.lower()
    if "estado" in t: return "system"
    if any(k in t for k in ["codigo", "programa", "firmware"]): return "code"
    if t.startswith("crear") or t.startswith("diseñar"): return "task"
    return "order"

def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["execution_mode"] = EXECUTION_MODE
    db.collection("aether_memory").add(data)

def decide_output_artifact(cmd_type, mode, domains):
    if cmd_type == "code": return "code"
    if "electronica" in domains or "mecatronica" in domains: return "engineering_design"
    if mode == "scientific": return "mathematical_model"
    return "scientific_design"

def generate_code(command, domains):
    if "electronica" in domains:
        return "💻 CÓDIGO ARDUINO / ESP32 (BASE)\n\n```cpp\n#define RELAY_PIN 5\nvoid setup() { pinMode(RELAY_PIN, OUTPUT); }\nvoid loop() { digitalWrite(RELAY_PIN, HIGH); delay(1000); digitalWrite(RELAY_PIN, LOW); delay(1000); }\n```\nEstado: Código base listo."
    if "matematicas" in domains or "fisica" in domains:
        return "💻 CÓDIGO PYTHON (MODELO CIENTÍFICO)\n\nimport numpy as np\nt = np.linspace(0, 10, 100)\nprint('Modelo generado')\nEstado: Listo para simulación."
    return "💻 CÓDIGO GENERAL (PSEUDOCÓDIGO)\n\nINICIO\n  procesar modelo\nFIN"

def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_output_artifact(cmd_type, mode, domains)

    log_event({"command": command, "type": cmd_type, "mode": mode, "domains": domains, "artifact": artifact, "session": session})

    if cmd_type == "system":
        return f"🧠 ESTADO AETHER\nAgente: {AGENT_NAME}\nModo: {EXECUTION_MODE}\nSesión: {session}\nCapacidades: Ciencia, Ingeniería, Código."

    if artifact == "code": return generate_code(command, domains)
    return f"📄 ARTEFACTO GENERADO: {artifact.upper()}\n\nObjetivo: {command}\nDominios: {', '.join(domains)}\n\nEstado: Estructura generada y guardada en Firebase."

with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Generador de Artefactos Reales")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", placeholder="Ej: Generar código ESP32 para relé", lines=4)
    out = gr.Textbox(label="Artefacto generado", lines=20)
    btn = gr.Button("Ejecutar")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()
