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
# AETHER CONFIG
# ======================================================
AGENT_NAME = "aether-core"
DEFAULT_SESSION = "default"

# ======================================================
# COGNITIVE LAYERS
# ======================================================
def classify_command(text):
    t = text.lower().strip()
    if t.startswith("crear"):
        return "task"
    if t.startswith("estado"):
        return "system"
    if t.startswith("ejecutar"):
        return "execute"
    if t.startswith("analizar"):
        return "analysis"
    return "order"

def infer_intent(cmd_type):
    return {
        "task": "long_job",
        "execute": "action",
        "analysis": "reasoning",
        "system": "inspection",
        "order": "conversation"
    }.get(cmd_type, "conversation")

def choose_ai(intent):
    if intent == "reasoning":
        return "gpt-like"
    if intent == "analysis":
        return "gemini-like"
    if intent == "long_job":
        return "planner"
    return "symbolic"

# ======================================================
# MEMORY
# ======================================================
def store_event(command, cmd_type, intent, ai, session):
    ts = datetime.datetime.utcnow().isoformat()
    data = {
        "time": ts,
        "command": command,
        "type": cmd_type,
        "intent": intent,
        "ai_selected": ai,
        "agent": AGENT_NAME,
        "session": session,
        "source": "huggingface"
    }
    db.collection("aether_memory").add(data)
    return ts

def read_recent_memory(limit=5):
    docs = (
        db.collection("aether_memory")
        .order_by("time", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]

# ======================================================
# JOB ENGINE
# ======================================================
def create_job(command, session):
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "created": datetime.datetime.utcnow().isoformat(),
        "command": command,
        "status": "planned",
        "progress": 0,
        "phases": [
            "análisis",
            "diseño",
            "descomposición",
            "ejecución",
            "validación"
        ],
        "current_phase": "análisis",
        "agent": AGENT_NAME,
        "session": session
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

    ts = store_event(command, cmd_type, intent, ai, session)
    recent = read_recent_memory()

    # -------- SYSTEM STATUS --------
    if cmd_type == "system":
        last = recent[1] if len(recent) > 1 else {}
        return (
            "🧠 ESTADO DE AETHER\n\n"
            f"Agente: {AGENT_NAME}\n"
            f"Sesión: {session}\n"
            f"Hora UTC: {ts}\n\n"
            f"Último comando:\n"
            f"- {last.get('command','N/A')}\n"
            f"- Intento: {last.get('intent','N/A')}\n"
            f"- IA asignada: {last.get('ai_selected','N/A')}"
        )

    # -------- LONG JOB --------
    if intent == "long_job":
        job_id = create_job(command, session)
        return (
            "🧠 JOB CREADO\n\n"
            f"Comando: {command}\n"
            f"Job ID: {job_id}\n"
            f"IA planificadora: {ai}\n\n"
            "Fases:\n"
            "- análisis\n- diseño\n- descomposición\n- ejecución\n- validación\n\n"
            "Estado: planificado"
        )

    # -------- DEFAULT --------
    return (
        "🧠 AETHER ONLINE\n\n"
        f"Hora UTC: {ts}\n"
        f"Sesión: {session}\n\n"
        f"Comando: \"{command}\"\n"
        f"Tipo: {cmd_type}\n"
        f"Intento: {intent}\n"
        f"IA seleccionada: {ai}\n\n"
        "Estado: estable · listo para escalar"
    )

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro de Cerebros")
    gr.Markdown("Router de IA · Jobs largos · Cognición persistente · 24/7")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)

    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: crear un juego / analizar sistema / estado",
        lines=4
    )

    out = gr.Textbox(label="Respuesta", lines=16)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()



