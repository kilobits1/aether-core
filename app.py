import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
import numpy as np

# ======================================================
# 1. FIREBASE INIT (Tu configuración original)
# ======================================================
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
else:
    try:
        firebase_key = json.load(open("llave.json"))
    except:
        firebase_key = None

if firebase_key and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ======================================================
# 2. CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

# ======================================================
# 3. DOMAIN MAP (ONTOLOGÍA COMPLETA - SIN TOCAR)
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion", "simular"],
    "fisica": ["fuerza", "energia", "movimiento", "termodinamica"],
    "quimica": ["reaccion", "molecula", "compuesto"],
    "electronica": ["voltaje", "corriente", "sensor", "esp32", "pcb", "relay", "rele"],
    "mecanica": ["estructura", "engranaje", "dinamica"],
    "mecatronica": ["robot", "control", "actuador"],
    "medicina": ["tratamiento", "diagnostico", "farmaco"],
    "biologia": ["celula", "genetica", "organismo"],
    "nanotecnologia": ["nanobot", "nano", "molecular"],
    "ambiental": ["contaminacion", "agua", "energia limpia"],
    "aeroespacial": ["nasa", "orbita", "satelite", "cohete"]
}

# Librería de Hardware para el Paso 3
HARDWARE_LIBRARY = {
    "temperatura": "// Firmware DHT22\n#include \"DHT.h\"\n#define DHTPIN 4\nDHT dht(DHTPIN, DHT22);\nvoid setup() { Serial.begin(115200); dht.begin(); }",
    "distancia": "// Firmware Ultrasonico\nconst int trig = 5; const int echo = 18;\nvoid setup() { pinMode(trig, OUTPUT); pinMode(echo, INPUT); }",
    "movimiento": "// Firmware PIR\nconst int pir = 13;\nvoid setup() { pinMode(pir, INPUT); }"
}

# ======================================================
# 4. FUNCIONES LÓGICAS (Tus funciones originales)
# ======================================================
def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular", "demostrar", "simular"]): return "scientific"
    if any(k in t for k in ["diseñar", "crear", "construir"]): return "engineering"
    return "general"

def detect_domains(command):
    t = command.lower()
    domains = [d for d, keywords in DOMAIN_MAP.items() if any(k in t for k in keywords)]
    return domains if domains else ["general"]

def classify_command(text):
    t = text.lower()
    if "estado" in t: return "system"
    if any(k in t for k in ["interruptor", "hardware", "codigo", "firmware"]): return "hardware"
    if t.startswith("crear") or t.startswith("diseñar"): return "task"
    return "order"

def decide_output_artifact(mode, domains):
    if "nanotecnologia" in domains or "medicina" in domains: return "scientific_design"
    if "electronica" in domains or "mecatronica" in domains: return "engineering_design"
    if mode == "scientific": return "mathematical_model"
    return "technical_plan"

def log_event(data):
    data["time"] = datetime.datetime.utcnow().isoformat()
    data["agent"] = AGENT_NAME
    data["execution_mode"] = EXECUTION_MODE
    db.collection("aether_memory").add(data)

# ======================================================
# 5. GENERADORES DE ARTEFACTOS (Tus originales + Mejoras)
# ======================================================
def create_pdf(content, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="AETHER CORE - REPORTE TÉCNICO", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.multi_cell(0, 10, txt=content)
    file_path = f"{title}.pdf"
    pdf.output(file_path)
    return file_path

def generate_scientific_design(command, domains):
    return f"📄 DISEÑO CIENTÍFICO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n\n1. Fundamentación\n2. Principios\n3. Modelo\n4. Supuestos\n5. Aplicación"

def generate_engineering_design(command, domains):
    h_code = next((code for hw, code in HARDWARE_LIBRARY.items() if hw in command.lower()), "")
    base = f"⚙️ DISEÑO DE INGENIERÍA\nObjetivo: {command}\nDominios: {', '.join(domains)}\n\n1. Arquitectura\n2. Componentes\n3. Lógica\n4. Seguridad"
    if h_code: base += f"\n\n--- FIRMWARE ESP32 (Paso 3) ---\n{h_code}"
    return base

def generate_mathematical_model(command):
    # Paso 2: Simulación real incorporada
    t_vals = np.linspace(0, 5, 10)
    sim_data = np.exp(t_vals).round(2)
    return f"📐 MODELO MATEMÁTICO & SIMULACIÓN (Paso 2)\nProblema: {command}\n\n1. Variables\n2. Ecuaciones\n3. Simulación Numérica:\n   Tiempo: {t_vals.tolist()}\n   Crecimiento: {sim_data.tolist()}\n4. Interpretación"

def generate_technical_plan(command):
    return f"🧠 PLAN TÉCNICO\nObjetivo: {command}\n\n1. Definición\n2. Estrategia\n3. Recursos\n4. Próximos pasos"

# ======================================================
# 6. CORE BRAIN (UNIFICACIÓN FINAL)
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_output_artifact(mode, domains)

    if cmd_type == "system":
        output = f"🧠 ESTADO DE AETHER\nAgente: {AGENT_NAME}\nModo: {EXECUTION_MODE}\nSesión: {session}\nEstado: OPERATIVO"
    elif artifact == "scientific_design":
        output = generate_scientific_design(command, domains)
    elif artifact == "engineering_design":
        output = generate_engineering_design(command, domains)
    elif artifact == "mathematical_model":
        output = generate_mathematical_model(command)
    else:
        output = generate_technical_plan(command)

    log_event({"command": command, "type": cmd_type, "session": session, "domains": domains, "artifact": artifact})

    # Paso 1: Generación de PDF
    pdf_path = create_pdf(output, f"Reporte_{session}")
    
    return output, pdf_path

# ======================================================
# 7. UI (Gradio)
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Sistema Total Unificado")
    with gr.Row():
        with gr.Column():
            session_id = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
            inp = gr.Textbox(label="Orden Técnica", lines=4)
            btn = gr.Button("Ejecutar Núcleo", variant="primary")
        with gr.Column():
            out_txt = gr.Textbox(label="Vista Previa", lines=15)
            out_pdf = gr.File(label="Descargar PDF")

    btn.click(aether, inputs=[inp, session_id], outputs=[out_txt, out_pdf])

demo.launch()