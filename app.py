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
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

# ======================================================
# CLASSIFICATION
# ======================================================
def classify_command(text):
    t = text.lower()
    if "estado" in t:
        return "system"
    if "interruptor" in t or "hardware" in t:
        return "hardware"
    if t.startswith("crear"):
        return "task"
    return "order"

# ======================================================
# MEMORY
# ======================================================
def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["mode"] = EXECUTION_MODE
    db.collection("aether_memory").add(data)

# ======================================================
# HARDWARE DESIGN ENGINE
# ======================================================
def design_interruptor_inteligente():
    return """
🔌 DISEÑO: INTERRUPTOR INTELIGENTE CON VOZ + FÍSICO

1️⃣ COMPONENTES PRINCIPALES (BOM)
- ESP32 (WiFi + Bluetooth)
- Relé SSR 5V (carga AC)
- Fuente AC-DC 220V → 5V
- Pulsador físico (interruptor)
- Micrófono digital (INMP441 o similar)
- Foco LED AC 220V
- Optoacoplador (seguridad)
- Fusible + varistor (protección)

2️⃣ ARQUITECTURA ELECTRÓNICA
[ AC 220V ]
   |
[Fusible]
   |
[Fuente AC-DC 5V] ----> ESP32 ----> Relé SSR ----> FOCO
                          |
                     Micrófono
                          |
                     Pulsador

3️⃣ LÓGICA DE CONTROL
- Pulsador → GPIO → Toggle relé
- Comando de voz → ESP32 → Validación → Relé
- Estado guardado en memoria flash

4️⃣ COMANDOS DE VOZ (EJEMPLO)
- "Aether, enciende la luz"
- "Aether, apaga el foco"

5️⃣ SEGURIDAD
✔ Aislamiento AC / DC
✔ Relé de estado sólido
✔ Protección de sobrecorriente

6️⃣ LISTO PARA:
- PCB
- Firmware
- Integración con app móvil
"""

# ======================================================
# CORE
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)

    log_event({
        "command": command,
        "type": cmd_type,
        "session": session
    })

    if cmd_type == "system":
        return f"""
🧠 ESTADO AETHER

Agente: {AGENT_NAME}
Modo: {EXECUTION_MODE}
Sesión: {session}
Estado: operativo · estable · técnico
"""

    if cmd_type == "hardware":
        return design_interruptor_inteligente()

    return f"""
🧠 AETHER ACTIVO

Comando recibido: {command}
Tipo detectado: {cmd_type}
Estado: listo para diseño, planificación y expansión
"""

# ======================================================
# UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Generador Técnico")
    gr.Markdown("Diseño · Arquitectura · Hardware · Seguridad")

    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(
        label="Orden",
        placeholder="Ej: diseñar interruptor inteligente / estado",
        lines=4
    )
    out = gr.Textbox(label="Respuesta", lines=22)

    btn = gr.Button("Enviar orden")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()




