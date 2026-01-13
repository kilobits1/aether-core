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
# DOMAIN MAP (ONTOLOGÍA MULTIDISCIPLINARIA)
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
# MODE SELECTION (TIPO DE RAZONAMIENTO)
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
# MEMORY
# ======================================================
def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["execution_mode"] = EXECUTION_MODE
    db.collection("aether_memory").add(data)

# ======================================================
# PLAN DE SALIDA (DECISIÓN CLAVE)
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
📄 ARTEFACTO: DISEÑO CIENTÍFICO TEÓRICO

Objetivo:
{command}

Dominios involucrados:
{", ".join(domains)}

Estructura:
1️⃣ Fundamentación teórica
2️⃣ Principios físicos/químicos
3️⃣ Modelo conceptual
4️⃣ Supuestos y limitaciones
5️⃣ Posibles aplicaciones reales

Estado:
Diseño base listo para simulación o validación experimental.
"""

def generate_engineering_design(command, domains):
    return f"""
⚙️ ARTEFACTO: DISEÑO DE INGENIERÍA

Objetivo:
{command}

Dominios:
{", ".join(domains)}

Contenido:
1️⃣ Arquitectura del sistema
2️⃣ Componentes principales
3️⃣ Lógica de control
4️⃣ Seguridad y restricciones
5️⃣ Preparación para prototipo

Estado:
Listo para firmware, PCB o integración física.
"""

def generate_mathematical_model(command):
    return f"""
📐 ARTEFACTO: MODELO MATEMÁTICO

Problema:
{command}

Incluye:
1️⃣ Variables del sistema
2️⃣ Ecuaciones base
3️⃣ Supuestos
4️⃣ Método de resolución
5️⃣ Interpretación física

Estado:
Modelo preparado para simulación numérica.
"""

def generate_technical_plan(command):
    return f"""
🧠 ARTEFACTO: PLAN TÉCNICO GENERAL

Objetivo:
{command}

Plan:
1️⃣ Definición del problema
2️⃣ Dominio de aplicación
3️⃣ Estrategia de solución
4️⃣ Recursos necesarios
5️⃣ Siguientes pasos técnicos

Estado:
Plan maestro generado.
"""

# ======================================================
# CORE BRAIN
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact_type = decide_output_artifact(mode, domains)

    log_event({
        "command": command,
        "type": cmd_type,
        "session": session,
        "mode": mode,
        "domains": domains,
        "artifact": artifact_type
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
- Análisis científico
- Diseño de ingeniería
- Generación de artefactos

Estado: OPERATIVO
"""

    if artifact_type == "scientific_design":
        return generate_scientific_design(command, domains)

    if artifact_type == "engineering_design":
        return generate_engineering_design(command, domains)

    if artifact_type == "mathematical_model":
        return generate_mathematical_model(command)

    return generate_technical_plan(command)

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Sistema Productivo Multidisciplinario")
    gr.Markdown(
        "Ciencia · Ingeniería · Medicina · Nanotecnología · Robótica · Aeroespacial"
    )

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: Diseñar nanobot para administrar fármacos / Analizar fuerzas en un sistema mecánico",
        lines=4
    )
    out = gr.Textbox(label="Salida (Artefacto generado)", lines=30)

    btn = gr.Button("Ejecutar")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()





