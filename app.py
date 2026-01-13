import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# ======================================================
# 1. FIREBASE INIT
# ======================================================
firebase_key = None
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
elif os.path.exists("llave.json"):
    firebase_key = json.load(open("llave.json"))

if firebase_key and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client() if firebase_key else None

# ======================================================
# 2. CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"  # REAL en el futuro
DEFAULT_SESSION = "default"

# ======================================================
# 3. ONTOLOGÍA MULTIDOMINIO
# ======================================================
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
    "ambiental": ["contaminacion", "agua", "energia limpia"],
    "aeroespacial": ["orbita", "satelite", "cohete", "nasa"]
}

# ======================================================
# 4. HARDWARE KNOWLEDGE BASE
# ======================================================
HARDWARE_LIBRARY = {
    "sensor temperatura": "// Arduino DHT\n#include <DHT.h>\nDHT dht(2, DHT11);\nvoid setup(){ dht.begin(); }",
    "rele": "// Relé básico\nvoid setup(){ pinMode(5, OUTPUT); }\nvoid loop(){ digitalWrite(5, HIGH); }",
    "ultrasonico": "// HC-SR04\nconst int trig=9, echo=10;\nvoid setup(){ pinMode(trig,OUTPUT); pinMode(echo,INPUT); }"
}

# ======================================================
# 5. COGNITIVE FUNCTIONS
# ======================================================
def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular", "demostrar", "simular"]):
        return "scientific"
    if any(k in t for k in ["diseñar", "crear", "construir"]):
        return "engineering"
    return "general"

def detect_domains(command):
    t = command.lower()
    domains = [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)]
    return domains if domains else ["general"]

def classify_command(command):
    t = command.lower()
    if "estado" in t:
        return "system"
    if any(k in t for k in ["hardware", "sensor", "rele", "pcb"]):
        return "engineering"
    if t.startswith(("crear", "diseñar")):
        return "task"
    return "order"

def decide_artifact(mode, domains):
    if any(d in domains for d in ["medicina", "nanotecnologia"]):
        return "scientific_design"
    if any(d in domains for d in ["electronica", "mecatronica", "mecanica"]):
        return "engineering_design"
    if mode == "scientific":
        return "mathematical_model"
    return "technical_plan"

# ======================================================
# 6. MEMORY SYSTEM
# ======================================================
def log_event(data):
    if not db:
        return
    data.update({
        "agent": AGENT_NAME,
        "execution_mode": EXECUTION_MODE,
        "time": datetime.datetime.utcnow().isoformat()
    })
    db.collection("aether_memory").add(data)

# ======================================================
# 7. ARTIFACT GENERATORS
# ======================================================
def generate_scientific_design(cmd, domains):
    return f"""📄 DISEÑO CIENTÍFICO AVANZADO
Objetivo: {cmd}
Dominios: {", ".join(domains)}

1. Fundamentación teórica
2. Principios científicos
3. Modelo conceptual
4. Supuestos críticos
5. Aplicaciones reales
Estado: Listo para simulación.
"""

def generate_engineering_design(cmd, domains):
    firmware = next((v for k, v in HARDWARE_LIBRARY.items() if k in cmd.lower()), "")
    return f"""⚙️ DISEÑO DE INGENIERÍA
Objetivo: {cmd}
Dominios: {", ".join(domains)}

1. Arquitectura del sistema
2. Componentes clave
3. Lógica de control
4. Seguridad y límites
5. Preparación para prototipo

--- FIRMWARE BASE ---
{firmware if firmware else "No requerido"}
"""

def generate_mathematical_model(cmd):
    return f"""📐 MODELO MATEMÁTICO
Problema: {cmd}

1. Variables
2. Ecuaciones
3. Supuestos
4. Método numérico
5. Interpretación
"""

def generate_technical_plan(cmd):
    return f"""🧠 PLAN TÉCNICO GENERAL
Objetivo: {cmd}

1. Definición del problema
2. Estrategia
3. Recursos
4. Riesgos
5. Próximos pasos
"""

# ======================================================
# 8. CORE BRAIN
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_artifact(mode, domains)

    log_event({
        "command": command,
        "session": session,
        "type": cmd_type,
        "mode": mode,
        "domains": domains,
        "artifact": artifact
    })

    if cmd_type == "system":
        return f"""🧠 ESTADO DE AETHER
Agente: {AGENT_NAME}
Modo: {EXECUTION_MODE}
Sesión: {session}
Capacidades: Cognición · Ingeniería · Ciencia · Memoria
Estado: OPERATIVO
"""

    if artifact == "scientific_design":
        return generate_scientific_design(command, domains)
    if artifact == "engineering_design":
        return generate_engineering_design(command, domains)
    if artifact == "mathematical_model":
        return generate_mathematical_model(command)

    return generate_technical_plan(command)

# ======================================================
# 9. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — Inteligencia Técnica Autónoma")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()
