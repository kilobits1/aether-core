import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore

# --- INIT FIREBASE ---
# En Hugging Face usa la variable de entorno, en PC busca el archivo local
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    firebase_key = json.load(open("llave.json"))  # solo para uso local

cred = credentials.Certificate(firebase_key)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- AETHER CORE ---
def aether(command):
    ts = datetime.datetime.utcnow().isoformat()

    data = {
        "time": ts,
        "command": command,
        "type": "order",
        "agent": "aether-core",
        "session": "default",
        "source": "huggingface"
    }

    db.collection("aether_memory").add(data)

    return (
        "🧠 AETHER ONLINE\n\n"
        f"Time (UTC): {ts}\n\n"
        "Command received:\n"
        f"\"{command}\"\n\n"
        "Status:\n"
        "- Stored in Firebase\n"
        "- Structured memory created\n"
        "- Awaiting next instruction"
    )

# --- UI ---
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro Central")
    gr.Markdown("Sistema privado · Memoria persistente · 24/7")

    inp = gr.Textbox(
        label="Orden para Aether",
        placeholder="Ej: analizar estado del sistema",
        lines=4
    )

    out = gr.Textbox(label="Respuesta de Aether", lines=10)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inp, out)

demo.launch()
