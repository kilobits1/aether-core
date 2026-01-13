import gradio as gr
import datetime
import json
import os
import uuid
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
# CONFIG
# ======================================================
AGENT_NAME = "aether-core"
DEFAULT_SESSION = "default"
EXECUTION_MODE = "SIMULATION"  # SIMULATION | REAL (futuro)

# ======================================================
# CLASSIFICATION
# ======================================================
def classify_command(text):
    t = text.lower().strip()
    if t.startswith("crear"):
        return "task"
    if t.startswith("estado"):
        return "system"
    if t.startswith("analizar"):
        return "analysis"
    if t.startswith("ejecutar"):
        return "execute"
    return "order"

def infer_intent(cmd_type):
    return {
        "task": "long_job",
        "analysis": "reasoning",
        "execute": "action",
        "system": "inspection",
        "order": "conversation"
    }.get(cmd_type, "conversation")

# ======================================================
# IA ROUTER (CEREBRO DE CEREBROS)
# ======================================================
def choose_ai(intent):
    if intent == "reasoning":
        return "gpt"
    if intent == "long_job":
        return "planner"
    if intent == "action":
        return "executor"
    return "symbolic"

# ======================================================
# TOOL REGISTRY (HERRAMIENTAS)
# ======================================================
TOOLS = {
    "create_game": {
        "description": "Diseñar estructura lógica de un juego",
        "allowed": True
    },
    "create_apk": {
        "description": "Planificar APK Android",
        "allowed": True
    },
    "design_hardware": {
        "description": "Diseño electrónico de hardware",
        "allowed": True
    },
    "render_video": {
        "description": "Render de video (externo)",
        "allowed": False  # bloqueado por seguridad
    }
}

def select_tool(command):
    c = command.lower()
    if "juego" in c:
        return "create_game"
    if "apk" in c:
        return "create_apk"
    if "interruptor" in c or "hardware" in c:
        return "design_hardware"
    if "video" in c or "película" in c:
        return "render_video"
    return None

# ======================================================
# MEMORY
# ======================================================
def store_event(command, cmd_type, intent, ai, tool, session):
    ts = datetime.datetime.utcnow().isoformat()
    data = {
        "time": ts,
        "command": command,
        "type": cmd_type,
        "intent": intent,
        "ai_selected": ai,
        "tool": tool,
        "agent": AGENT_NAME,
        "session": session,
        "mode": EXECUTION_MODE,
        "source": "huggingface"
    }
    db.collection("aether_memory").add(data)
    return ts

# ======================================================
# JOB ENGINE
# ======================================================
def create_job(command, tool, session):
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "command": command,
        "tool": tool,
        "status": "planned",
        "progress": 0,
        "phases": [
            "análisis",
            "arquitectura",
            "descomposición",
            "simulación",
            "validación"
        ],
        "current_phase": "análisis",
        "agent": AGENT_NAME,
        "session": session,
        "created": datetime.datetime.utcnow().isoformat()
    }
    db.collection("aether_jobs").document(job_id).set(job)
    return job_id

# ======================================================
# MAIN LOOP
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    intent = infer_intent(cmd_type)
    ai = choose_ai(intent)
    tool = select_tool(command)

    ts = store_event(command, cmd_type, intent, ai, tool, session)

    # -------- SYSTEM --------
    if cmd_type == "system":
        return (
            "🧠 ESTADO DE AETHER\n\n"
            f"Agente: {AGENT_NAME}\n"
            f"Modo ejecución: {EXECUTION_MODE}\n"
            f"Sesión: {session}\n"
            f"Hora UTC: {ts}\n\n"
            f"Herramientas disponibles:\n" +
            "\n".join([f"- {k}: {v['description']}" for k,v in TOOLS.items()])
        )

    # -------- LONG JOB --------
    if intent == "long_job":
        if tool and TOOLS.get(tool, {}).get("allowed"):
            job_id = create_job(command, tool, session)
            return (
                "🧠 JOB PLANIFICADO\n\n"
                f"Comando: {command}\n"
                f"Herramienta: {tool}\n"
                f"Job ID: {job_id}\n\n"
                "Estado: listo para simulación\n"
                "Ejecución REAL deshabilitada por seguridad"
            )
        else:
            return (
                "⛔ ACCIÓN BLOQUEADA\n\n"
                "La herramienta solicitada no está permitida\n"
                "Modo actual: SIMULATION"
            )

    # -------- DEFAULT --------
    return (
        "🧠 AETHER ONLINE\n\n"
        f"Comando: {command}\n"
        f"Tipo: {cmd_type}\n"
        f"Intento: {intent}\n"
        f"IA asignada: {ai}\n"
        f"Herramienta: {tool or 'N/A'}\n\n"
        "Estado: estable · seguro · expandible"
    )

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Sistema Central")
    gr.Markdown("Cerebro · Orquestador · Seguridad activa · 24/7")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)

    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: crear un juego / diseñar interruptor inteligente / estado",
        lines=4
    )

    out = gr.Textbox(label="Respuesta", lines=18)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()




