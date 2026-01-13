import gradio as gr
import datetime
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

# ======================================================
# FIREBASE INIT
# ======================================================
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    firebase_key = json.load(open("llave.json"))

cred = credentials.Certificate(firebase_key)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

# ======================================================
# DOMAIN MAP (ONTOLOGÍA)
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion"],
    "fisica": ["fuerza", "energia", "movimiento", "termodinamica"],
    "quimica": ["reaccion", "molecula", "compuesto"],
    "electronica": ["voltaje", "corriente", "sensor", "esp32", "pcb", "relay"],
    "mecanica": ["estructura", "engranaje", "dinamica"],
    "mecatronica": ["robot", "control", "actuador"],
    "medicina": ["tratamiento", "diagnostico", "farmaco"],
    "biologia": ["celula", "genetica", "organismo"],
    "nanotecnologia": ["nanobot", "nano", "molecular"],
    "ambiental": ["contaminacion", "agua", "energia limpia"],
    "aeroespacial": ["nasa", "orbita", "satelite", "cohete"]
}

# ======================================================
# MODE SELECTION
# ======================================================
def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular", "demostrar"]):
        return "scientific"
    if any(k in t for k in ["diseñar", "crear", "construir"]):
        return "engineering"
    return "general"

# ======================================================
# DOMAIN DETECTION
# ======================================================
def detect_domains(command):
    t = command.lower()
    domains = []
    for domain, keywords in DOMAIN_MAP.items():
        if any(k in t for k in keywords):
            domains.append(domain)
    return domains if domains else ["general"]

# ======================================================
# COMMAND TYPE
# ======================================================
def classify_command(text):
    t = text.lower()
    if "estado" in t:
        return "system"
    if "interruptor" in t or "hardware" in t:
        return "hardware"
    if t.startswith("crear") or t.startswith("diseñar"):
        return "task"
    return "order"

# ======================================================
# MEMORY LOG
# ======================================================
def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["execution_mode"] = EXECUTION_MODE
    db.collection("aether_memory").add(data)

# ======================================================
# OUTPUT DECISION
# ======================================================
def decide_output_artifact(mode, domains):
    if "nanotecnologia" in domains or "medicina" in domains:
        return "scientific_design"
    if "electronica" in domains or "mecatronica" in domains:
        return "engineering_design"
    if mode == "scientific":
        return "mathematical_model"
    return "technical_plan"

# ======================================================
# ARTEFACT GENERATORS
# ======================================================
def generate_scientific_design(command, domains):
    return f"""
📄 DISEÑO CIENTÍFICO
Objetivo: {command}
Dominios: {", ".join(domains)}

1️⃣ Fundamentación teórica  
2️⃣ Principios científicos  
3️⃣ Modelo conceptual  
4️⃣ Supuestos  
5️⃣ Aplicaciones

Estado: listo para validación.
"""

def generate_engineering_design(command, domains):
    return f"""
⚙️ DISEÑO DE INGENIERÍA
Objetivo: {command}
Dominios: {", ".join(domains)}

1️⃣ Arquitectura del sistema  
2️⃣ Componentes electrónicos  
3️⃣ Lógica de control  
4️⃣ Seguridad  
5️⃣ Preparación de prototipo

Estado: listo para firmware / PCB.
"""

def generate_mathematical_model(command):
    return f"""
📐 MODELO MATEMÁTICO
Problema: {command}

1️⃣ Variables  
2️⃣ Ecuaciones  
3️⃣ Supuestos  
4️⃣ Método  
5️⃣ Interpretación

Estado: listo para simulación.
"""

def generate_technical_plan(command):
    return f"""
🧠 PLAN TÉCNICO
Objetivo: {command}

1️⃣ Definición  
2️⃣ Dominio  
3️⃣ Estrategia  
4️⃣ Recursos  
5️⃣ Próximos pasos

Estado: plan maestro generado.
"""

# ======================================================
# CORE BRAIN
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_output_artifact(mode, domains)

    log_event({
        "command": command,
        "type": cmd_type,
        "session": session,
        "mode": mode,
        "domains": domains,
        "artifact": artifact
    })

    if cmd_type == "system":
        return f"""
🧠 ESTADO DE AETHER
Agente: {AGENT_NAME}
Modo: {EXECUTION_MODE}
Sesión: {session}

Capacidades:
- Multidominio
- Memoria persistente
- Diseño científico
- Diseño de ingeniería

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
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core")
    gr.Markdown("Sistema cognitivo multidisciplinario")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Salida", lines=30)

    btn = gr.Button("Ejecutar")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()
