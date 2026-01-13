import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
import numpy as np
import ezdxf  # Librería para generar planos DXF (AutoCAD)

# ======================================================
# 1. FIREBASE INIT
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
# 2. CONFIG & ONTOLOGÍA (Sin tocar nada)
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

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

HARDWARE_LIBRARY = {
    "temperatura": "// Firmware Arduino\n#include \"DHT.h\"\nvoid setup() { dht.begin(); }",
    "distancia": "// Firmware Arduino\nconst int trig = 5; void setup() { pinMode(trig, OUTPUT); }",
    "movimiento": "// Firmware Arduino\nconst int pir = 13; void setup() { pinMode(pir, INPUT); }"
}

# ======================================================
# 3. LÓGICA DE DETECCIÓN (Tus originales)
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
    if any(k in t for k in ["hardware", "codigo", "plano", "cad"]): return "engineering"
    return "order"

def decide_output_artifact(mode, domains):
    if "nanotecnologia" in domains or "medicina" in domains: return "scientific_design"
    if "electronica" in domains or "mecatronica" in domains or "mecanica" in domains: return "engineering_design"
    if mode == "scientific": return "mathematical_model"
    return "technical_plan"

# ======================================================
# 4. GENERADORES DE ARTEFACTOS (CAD e Ingeniería)
# ======================================================
def create_dxf_blueprint(title):
    doc = ezdxf.new()
    msp = doc.modelspace()
    # Dibujar un contorno base de 100x100mm para el plano
    msp.add_lwline([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    path = f"{title}.dxf"
    doc.saveas(path)
    return path

def generate_engineering_design(command, domains):
    h_code = next((code for hw, code in HARDWARE_LIBRARY.items() if hw in command.lower()), "")
    
    # Lógica de Planos CAD descriptivos (Tu nueva solicitud)
    cad_specs = f"""
--- ESPECIFICACIONES CAD / PLANOS ---
Entidad: Pieza Mecánica / Gabinete
Formato Sugerido: DXF / STEP
Capas (Layers): 
  - 0: Contorno General
  - 1: Perforaciones (Sensores/Pines)
  - 2: Anotaciones Técnicas
Coordenadas Base: (0,0,0) a (100,100,50) mm
"""
    
    # Módulo Multi-Lenguaje
    python_java = f"""
--- SOFTWARE ADICIONAL ---
[Python]: import serial; ser = serial.Serial('/dev/ttyUSB0', 115200)
[Java]: public class AetherControl {{ public static void main(String[] args) {{}} }}
"""
    
    base = f"⚙️ DISEÑO DE INGENIERÍA COMPLETO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n"
    base += cad_specs
    
    if h_code: 
        base += f"\n--- FIRMWARE ESP32 (Arduino) ---\n{h_code}"
    
    base += python_java
    return base

# (Mantenemos tus otros generadores intactos)
def generate_scientific_design(command, domains):
    return f"📄 DISEÑO CIENTÍFICO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n\n1. Fundamentación\n2. Principios\n3. Aplicación"

def generate_mathematical_model(command):
    t_vals = np.linspace(0, 10, 5)
    return f"📐 MODELO MATEMÁTICO\nProblema: {command}\n\nSimulación: {t_vals.tolist()}\nEstado: Calculado."

def generate_technical_plan(command):
    return f"🧠 PLAN TÉCNICO\nObjetivo: {command}\n\n1. Definición\n2. Pasos técnicos."

# ======================================================
# 5. CORE BRAIN & PDF
# ======================================================
def create_pdf(content, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=content)
    path = f"{title}.pdf"
    pdf.output(path)
    return path

def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_output_artifact(mode, domains)

    if artifact == "engineering_design":
        output = generate_engineering_design(command, domains)
    elif artifact == "scientific_design":
        output = generate_scientific_design(command, domains)
    elif artifact == "mathematical_model":
        output = generate_mathematical_model(command)
    else:
        output = generate_technical_plan(command)

    # Generar archivos de salida
    pdf_path = create_pdf(output, f"Reporte_{session}")
    dxf_path = create_dxf_blueprint(f"Plano_{session}") # Genera el archivo .dxf real

    return output, pdf_path, dxf_path

# ======================================================
# 6. UI (Gradio con 3 Salidas)
# ======================================================
with gr.Blocks(title="AETHER CORE CAD") as demo:
    gr.Markdown("## 🧠 Aether Core — Ingeniería, CAD y Software")
    with gr.Row():
        with gr.Column():
            inp = gr.Textbox(label="Orden", lines=3)
            sess = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
            btn = gr.Button("GENERAR TODO", variant="primary")
        with gr.Column():
            out_txt = gr.Textbox(label="Vista Previa", lines=10)
            out_pdf = gr.File(label="Descargar Reporte PDF")
            out_dxf = gr.File(label="Descargar Plano CAD (.DXF)")

    btn.click(aether, inputs=[inp, sess], outputs=[out_txt, out_pdf, out_dxf])

demo.launch()