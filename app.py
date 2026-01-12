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
    firebase_key = json.load(open("llave.json"))  # solo local

cred = credentials.Certificate(firebase_key)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# AETHER – COGNITIVE CORE
# ======================================================

AGENT_NAME = "aether-core"
DEFAULT_SESSION = "default"

# ----------------------
# Clasificación básica
# ----------------------
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

# ----------------------
# Leer memoria reciente
# ----------------------
def read_recent_memory(limit: int = 5):
    docs = (
        db.collection("aether_memory")
        .order_by("time", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]

# ----------------------
# Guardar evento
# ----------------------
def store_event(command, cmd_type, session):
    ts = datetime.datetime.utcnow().isoformat()

    data = {
        "time": ts,
        "command": command,
        "type": cmd_type,
        "agent": AGENT_NAME,
        "session": session,
        "source": "huggingface"
    }

    db.collection("aether_memory").add(data)
    return ts

# ======================================================
# MAIN LOOP
# ======================================================
def aether(command: str, session: str = DEFAULT_SESSION):
    cmd_type = classify_command(command)
    ts = store_event(command, cmd_type, session)
    recent = read_recent_memory()

    # ----------------------
    # COMANDO: ESTADO
    # ----------------------
    if cmd_type == "system":
        last = recent[1] if len(recent) > 1 else {}

        return (
            "🧠 ESTADO DE AETHER\n\n"
            f"Agente: {AGENT_NAME}\n"
            f"Sesión: {session}\n"
            f"Hora actual (UTC): {ts}\n\n"
            f"Eventos en memoria: {len(recent)}\n"
            f"Última orden:\n"
            f"- Comando: {last.get('command', 'N/A')}\n"
            f"- Tipo: {last.get('type', 'N/A')}\n"
            f"- Hora: {last.get('time', 'N/A')}"
        )

    # ----------------------
    # RESPUESTA GENERAL
    # ----------------------
    return (
        "🧠 AETHER ONLINE\n\n"
        f"Hora (UTC): {ts}\n"
        f"Sesión: {session}\n\n"
        f"Comando recibido:\n\"{command}\"\n\n"
        f"Clasificación: {cmd_type}\n"
        f"Contexto cargado: {len(recent)} eventos\n\n"
        "Estado: operativo\n"
        "Siguiente fase: razonamiento / ejecución"
    )

# ======================================================
# UI – GRADIO
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro Central")
    gr.Markdown("Memoria persistente · Arquitectura cognitiva · 24/7")

    session = gr.Textbox(
        label="Sesión",
        value=DEFAULT_SESSION,
        interactive=True
    )

    inp = gr.Textbox(
        label="Orden para Aether",
        placeholder="Ej: crear un sistema / estado / ejecutar tarea",
        lines=4
    )

    out = gr.Textbox(label="Respuesta de Aether", lines=14)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()


