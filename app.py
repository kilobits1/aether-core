import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
from fpdf import FPDF
import numpy as np
import ezdxf

# ======================================================
# 1. INIT FIREBASE
# ======================================================
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
    if not firebase_admin._apps:
        cred = credentials.Certificate(firebase_key)
        firebase_admin.initialize_app(cred)
    db = firestore.client()
else:
    db = None

# ======================================================
# 2. ONTOLOGÍA (Tus 11 dominios originales)
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

HARDWARE_LIBRARY = {
    "temperatura": "// Firmware Arduino\n#include \"DHT.h\"\nvoid setup() { dht.begin(); }",
    "distancia": "// Firmware Arduino\nconst int trig = 5; void setup() { pinMode(trig, OUTPUT); }",
    "movimiento": "// Firmware PIR\nconst int pir = 13; void setup() { pinMode(pir, INPUT); }",
    "rele": "// Código para Relé\nvoid setup() { pinMode(5, OUTPUT); }\nvoid loop() { digitalWrite(5, HIGH); delay(1000); }"
}

# ======================================================
# 3. GENERADORES DE ARTEFACTOS
# ======================================================
def generate_engineering_design(command, domains):
    h_code = ""
    for hw, code in HARDWARE_LIBRARY.items():
        if hw in command.lower():
            h_code = code
            break
            
    base = f"⚙️ DISEÑO DE INGENIERÍA COMPLETO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n"
    base += "\n--- ESPECIFICACIONES CAD ---\nFormato: DXF (AutoCAD)\nPlano generado con contorno de 100x100mm.\n"
    
    if h_code: base += f"\n--- FIRMWARE GENERADO ---\n{h_code}"
    
    base += "\n--- SOFTWARE ---\n[Python]: import serial; ser = serial.Serial('/dev/ttyUSB0', 115200)\n"
    return base

# ======================================================
# 4. EXPORTACIÓN: PDF Y DXF (Aquí arreglamos el error)
# ======================================================
def create_pdf(content, title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    clean_text = content.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 8, txt=clean_text)
    path = f"Reporte_{title}.pdf"
    pdf.output(path)
    return path

def create_dxf(title):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # SOLUCIÓN AL ERROR: Usamos add_polyline (comando correcto)
    puntos = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    msp.add_polyline(puntos)
    
    # Círculo técnico para sensor
    msp.add_circle((50, 50), 10)
    
    path = f"Plano_{title}.dxf"
    doc.saveas(path)
    return path

# ======================================================
# 5. CORE BRAIN
# ======================================================
def aether_pro(command, session="default"):
    t = command.lower()
    domains = [d for d, keywords in DOMAIN_MAP.items() if any(k in t for k in keywords)]
    if not domains: domains = ["general"]
    
    output_text = generate_engineering_design(command, domains)
    
    # Crear archivos físicos
    try:
        pdf_file = create_pdf(output_text, session)
        dxf_file = create_dxf(session)
        return output_text, pdf_file, dxf_file
    except Exception as e:
        return f"Error en generación: {str(e)}", None, None

# ======================================================
# 6. INTERFAZ (Gradio)
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("# 🧠 Aether Core — Ingeniería, CAD y Software")
    with gr.Row():
        with gr.Column():
            inp = gr.Textbox(label="Orden Técnica", placeholder="Ej: Diseñar gabinete para sensor", lines=3)
            sess = gr.Textbox(label="Sesión", value="default")
            btn = gr.Button("GENERAR TODO", variant="primary")
        with gr.Column():
            out_txt = gr.Textbox(label="Vista Previa", lines=10)
            out_pdf = gr.File(label="📄 Descargar Reporte PDF")
            out_dxf = gr.File(label="📐 Descargar Plano AutoCAD (.DXF)")

    btn.click(aether_pro, inputs=[inp, sess], outputs=[out_txt, out_pdf, out_dxf])

demo.launch()