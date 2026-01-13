import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
import uuid

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
# COGNITIVE FUNCTIONS
# ======================================================
def classify_command(text: str) -> str:
    t = text.lower().strip()
    if t.startswith("crear"):
        return "task"
    if t.startswith("estado"):
        return "system"
    if t.startswith("recordar"):
        return "memory"
    if t.startswith("ejecutar"):
        return "execute"
    return "order"

def infer_intent(cmd_type: str) -> str:
    if cmd_type == "task":
        return "long_job"
    if cmd_type == "execute":
        return "action"
    if cmd_type == "system":
        return "inspection"
    return "conversation"

def read_recent_memory(limit=5):
    docs = (
        db.collection("aether_memory")
        .order_by("time", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]

def store_event(command, cmd_type, intent, session):
    ts = datetime.datetime.utcnow().isoformat()
    data = {
        "time": ts,
        "command": command,
        "type": cmd_type,
        "intent": intent,
        "agent": AGENT_NAME,
        "session": session,
        "source": "huggingface"
    }
    db.collection("aether_memory").add(data)
    return ts

# ======================================================
# JOB SYSTEM (CRÍTICO)
# ======================================================
def create_job(command, session):
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "created": datetime.datetime.utcnow().isoformat(),
        "command": command,
        "status": "pending",
        "progress": 0,
        "agent": AGENT_NAME,
        "session": session
    }
    db.collection("aether_jobs").document(job_id).set(job)
    return job_id

# ======================================================
# MAIN LOOP
# ======================================================
def aether(command: str, session: str = DEFAULT_SESSION):
    cmd_type = classify_command(command)
    intent = infer_intent(cmd_type)
    ts = store_event(command, cmd_type, intent, session)
    recent = read_recent_memory()

    # ---------------- SYSTEM STATUS ----------------
    if cmd_type == "system":
        last = recent[1] if len(recent) > 1 else {}
        return (
            "🧠 ESTADO DE AETHER\n\n"
            f"Agente: {AGENT_NAME}\n"
            f"Sesión: {session}\n"
            f"Hora UTC: {ts}\n\n"
            f"Eventos recientes: {len(recent)}\n"
            f"Último comando:\n"
            f"- {last.get('command','N/A')}\n"
            f"- Tipo: {last.get('type','N/A')}\n"
            f"- Intento: {last.get('intent','N/A')}"
        )

    # ---------------- LONG TASK ----------------
    if intent == "long_job":
        job_id = create_job(command, session)
        return (
            "🧠 TAREA LARGA DETECTADA\n\n"
            f"Comando: {command}\n"
            f"Job ID: {job_id}\n"
            "Estado: creado\n\n"
            "Aether ejecutará este trabajo por fases.\n"
            "Puedes consultar su estado más adelante."
        )

    # ---------------- DEFAULT ----------------
    return (
        "🧠 AETHER ONLINE\n\n"
        f"Hora UTC: {ts}\n"
        f"Sesión: {session}\n\n"
        f"Comando: \"{command}\"\n"
        f"Tipo: {cmd_type}\n"
        f"Intento: {intent}\n\n"
        f"Contexto cargado: {len(recent)} eventos\n"
        "Estado: estable y operativo"
    )

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro Central")
    gr.Markdown("Cognición · Jobs largos · Memoria persistente · 24/7")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)

    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: crear un juego / estado / ejecutar análisis",
        lines=4
    )

    out = gr.Textbox(label="Respuesta de Aether", lines=15)

    btn = gr.Button("Enviar")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()



