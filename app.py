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
    if any(k in t for k in ["codigo", "programa", "firmware"]):
        return "code"
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
# DECISIÓN DE PRODUCTO
# ======================================================
def decide_output_artifact(cmd_type, mode, domains):
    if cmd_type == "code":
        return "code"
    if "electronica" in domains or "mecatronica" in domains:
        return "engineering_design"
    if mode == "scientific":
        return "mathematical_model"
    return "scientific_design"

# ======================================================
# CODE GENERATORS
# ======================================================
def generate_code(command, domains):
    if "electronica" in domains:
        return """
💻 CÓDIGO ARDUINO / ESP32 (BASE)

```cpp
#define RELAY_PIN 5

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
}

void loop() {
  digitalWrite(RELAY_PIN, HIGH);
  delay(1000);
  digitalWrite(RELAY_PIN, LOW);
  delay(1000);
}
Estado: Código base funcional para ESP32.
"""
if "matematicas" in domains or "fisica" in domains:
return """
💻 CÓDIGO PYTHON (MODELO CIENTÍFICO)

python
Copiar código
import numpy as np

t = np.linspace(0, 10, 100)
x = np.sin(t)

print("Modelo generado")
Estado: Listo para simulación.
"""
return """
💻 CÓDIGO GENERAL (PSEUDOCÓDIGO)

text
Copiar código
INICIO
  leer variables
  procesar modelo
  generar salida
FIN
"""

======================================================
ARTEFACT GENERATORS
======================================================
def generate_scientific_design(command, domains):
return f"""
📄 DISEÑO CIENTÍFICO

Objetivo:
{command}

Dominios:
{", ".join(domains)}

Incluye:

Base teórica

Supuestos

Aplicaciones
"""

def generate_engineering_design(command, domains):
return f"""
⚙️ DISEÑO DE INGENIERÍA

Objetivo:
{command}

Dominios:
{", ".join(domains)}

Incluye:

Arquitectura

Componentes

Control
"""

def generate_mathematical_model(command):
return f"""
📐 MODELO MATEMÁTICO

Problema:
{command}

Incluye:

Variables

Ecuaciones

Método
"""

======================================================
CORE BRAIN
======================================================
def aether(command, session=DEFAULT_SESSION):
cmd_type = classify_command(command)
mode = select_mode(command)
domains = detect_domains(command)
artifact = decide_output_artifact(cmd_type, mode, domains)

bash
Copiar código
log_event({
    "command": command,
    "type": cmd_type,
    "mode": mode,
    "domains": domains,
    "artifact": artifact,
    "session": session
})

if cmd_type == "system":
    return f"""
🧠 ESTADO AETHER

Agente: {AGENT_NAME}
Modo: {EXECUTION_MODE}
Sesión: {session}

Capacidades:

Ciencia

Ingeniería

Código

Modelado
"""

if artifact == "code":
return generate_code(command, domains)

if artifact == "engineering_design":
return generate_engineering_design(command, domains)

if artifact == "mathematical_model":
return generate_mathematical_model(command)

return generate_scientific_design(command, domains)

======================================================
UI
======================================================
with gr.Blocks(title="AETHER CORE") as demo:
gr.Markdown("## 🧠 Aether Core — Generador de Artefactos Reales")
gr.Markdown("Código · Ciencia · Ingeniería · Robótica · Medicina")

makefile
Copiar código
session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
inp = gr.Textbox(
    label="Orden",
    placeholder="Ej: Generar código ESP32 para relé / Diseñar nanobot médico",
    lines=4
)
out = gr.Textbox(label="Artefacto generado", lines=30)

btn = gr.Button("Ejecutar")
btn.click(aether, inputs=[inp, session], outputs=out)
demo.launch()



