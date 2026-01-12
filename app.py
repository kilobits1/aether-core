import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# -------------------------
# INIT FIREBASE
# -------------------------
# En Hugging Face usa la variable de entorno FIREBASE_KEY
# En local usa el archivo llave.json
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    firebase_key = json.load(open("llave.json"))

cred = credentials.Certificate(firebase_key)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------------------------
# AETHER CORE – COGNITIVE LAYER
# -------------------------

def classify_command(text: str) -> str:
    t = text.lower().strip()

    if t.startswith("crear"):
        return "task"
    if t.startswith("estado"):
        return "system"
    if t.startswith("recordar"):
        return "memory"

    return "order"


def read_recent_memory(limit: int = 5):
    docs = (
        db.collection("aether_memory")
        .order_by("time", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )

    events = []
    for d in docs:
        events.append(d.to_dict())

    return events


def aether(command: str):
    ts = datetime.datetime.utcnow().isoformat()
    cmd_type = classify_command(command)

    data = {
        "time": ts,
        "command": command,
        "type": cmd_type,
        "agent": "aether-core",
        "session": "default",
        "source": "huggingface"
    }

    # Guardar evento en Firebase
    db.collection("aether_memory").add(data)

    # Leer memoria reciente
    recent = read_recent_memory()

    # Comando especial: estado
    if cmd_type == "system":
        last = recent[0] if recent else {}
        return (
            "🧠 ESTADO DEL SISTEMA\n\n"
            f"Eventos recientes: {len(recent)}\n"
            f"Última orden: {last.get('command', 'N/A')}\n"
            f"Tipo: {last.get('type', 'N/A')}\n"
            f"Hora (UTC): {last.get('time', 'N/A')}"
        )

    return (
        "🧠 AETHER ONLINE\n\n"
        f"Time (UTC): {ts}\n\n"
        f"Command: \"{command}\"\n"
        f"Type: {cmd_type}\n\n"
        f"Memoria reciente cargada: {len(recent)} eventos\n"
        "Status: OK"
    )

# -------------------------
# UI (GRADIO)
# -------------------------
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro Central")
    gr.Markdown("Sistema privado · Memoria persistente · 24/7")

    inp = gr.Textbox(
        label="Orden para Aether",
        placeholder="Ej: crear un sistema de prueba / estado",
        lines=4
    )

    out = gr.Textbox(label="Respuesta de Aether", lines=12)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inp, out)

demo.launch()

