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
# DOMAIN MAP (ONTOLOGÍA BASE)
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion"],
    "fisica": ["fuerza", "energia", "movimiento", "termodinamica"],
    "quimica": ["reaccion", "molecula", "compuesto", "quimico"],
    "electronica": ["voltaje", "corriente", "sensor", "esp32", "pcb", "relay"],
    "mecanica": ["estructura", "movimiento", "engranaje", "fuerza"],
    "mecatronica": ["robot", "control", "actuador", "sensor"],
    "medicina": ["tratamiento", "diagnostico", "farmaco", "paciente"],
    "biologia": ["celula", "organismo", "genetica"],
    "nanotecnologia": ["nanobot", "nano", "molecular"],
    "ambiental": ["contaminacion", "agua", "energia limpia"],
    "aeroespacial": ["nasa", "orbita", "cohete", "satelite"]
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
        for k in keywords:
            if k in t:
                domains.append(domain)
                break
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
# HARDWARE ENGINE (EJEMPLO)
# ======================================================
def design_interruptor_inteligente():
    return """
🔌 DISEÑO: INTERRUPTOR INTELIGENTE (FÍSICO + VOZ)

Componentes:
- ESP32
- Relé SSR AC
- Fuente AC-DC
- Pulsador
- Micrófono digital
- Protección eléctrica

Arquitectura:
AC → Fuente → ESP32 → Relé → Carga

Lógica:
- Pulsador físico
- Comando de voz
- Estado persistente

Aplicable a:
IoT · Domótica · Industria · Educación
"""

# ======================================================
# CORE BRAIN
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)

    log_event({
        "command": command,
        "type": cmd_type,
        "session": session,
        "mode": mode,
        "domains": domains
    })

    if cmd_type == "system":
        return f"""
🧠 ESTADO DE AETHER

Agente: {AGENT_NAME}
Modo ejecución: {EXECUTION_MODE}
Sesión: {session}

Capacidades activas:
- Multidominio
- Memoria persistente
- Diseño técnico
- Análisis científico

Estado: OPERATIVO
"""

    if cmd_type == "hardware":
        return design_interruptor_inteligente()

    return f"""
🧠 AETHER ACTIVO

Comando: {command}

Tipo: {cmd_type}
Modo cognitivo: {mode}
Dominios detectados: {", ".join(domains)}

Estado:
Listo para análisis, diseño y expansión multidisciplinaria.
"""

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Sistema Multidisciplinario")
    gr.Markdown("Ciencia · Ingeniería · Robótica · Medicina · Electrónica")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: Diseñar nanobot médico / estado",
        lines=4
    )
    out = gr.Textbox(label="Respuesta", lines=24)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()




