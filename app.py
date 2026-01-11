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
    firebase_key = json.load(open("llave.json")) # Cambia "llave.json" por el nombre de tu archivo

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
        "source": "huggingface"
    }
    db.collection("aether_memory").add(data)
    return f"🧠 AETHER ONLINE\n\nTime (UTC): {ts}\n\nCommand received:\n\"{command}\"\n\nStatus: Stored in Firebase"

with gr.Blocks() as demo:
    gr.Markdown("## 🧠 Aether Core — Cerebro Central")
    inp = gr.Textbox(label="Orden")
    out = gr.Textbox(label="Respuesta")
    btn = gr.Button("Enviar")
    btn.click(aether, inp, out)

demo.launch()