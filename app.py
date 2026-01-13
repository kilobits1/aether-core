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
# 2. CORE CONFIG & ONTOLOGÍA (Tus 11 dominios originales)
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
    "movimiento": "// Firmware PIR\nconst int pir = 13; void setup() { pinMode(pir, INPUT); }",
    "rele": "// Código para Relé\nvoid setup() { pinMode(5, OUTPUT); }\nvoid loop() { digitalWrite(5, HIGH); delay(1000); }"
}

# ======================================================
# 3. LÓGICA DE CLASIFICACIÓN (Tus funciones originales)
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
    if t.startswith("crear") or t.startswith("diseñar"): return "task"
    return "order"

def decide_output_artifact(mode, domains):
    if "nanotecnologia" in domains or "medicina" in domains: return "scientific_design"
    if "electronica" in domains or "mecatronica" in domains or "mecanica" in domains: return "engineering_design"
    if mode == "scientific": return "mathematical_model"
    return "technical_plan"

# ======================================================
# 4. EXPORTACIÓN DE ARCHIVOS (CAD y PDF)
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
    # Método seguro add_line para evitar errores de versión
    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 100))
    msp.add_line((100, 100), (0, 100))
    msp.add_line((0, 100), (0, 0))
    msp.add_circle((50, 50), radius=10)
    path = f"Plano_{title}.dxf"
    doc.saveas(path)
    return path

# ======================================================
# 5. GENERADORES DE ARTEFACTOS (Todos tus originales + CAD)
# ======================================================
def generate_scientific_design(command, domains):
    return f"📄 DISEÑO CIENTÍFICO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n\n1. Fundamentación\n2. Principios\n3. Modelo\n4. Supuestos\n5. Aplicación"

def generate_engineering_design(command, domains):
    h_code = next((code for hw, code in HARDWARE_LIBRARY.items() if hw in command.lower()), "")
    cad_specs = "\n--- ESPECIFICACIONES CAD ---\nEntidad: Pieza/Gabinete\nFormato: DXF\nCapas: Contorno, Perforaciones.\n"
    soft_specs = "\n--- SOFTWARE ADICIONAL ---\n[Python]: import serial\n[Java]: public class Aether {}\n[C++]: Serial.println(\"Aether Core Active\");\n"
    
    base = f"⚙️ DISEÑO DE INGENIERÍA COMPLETO\nObjetivo: {command}\nDominios: {', '.join(domains)}\n"
    base += cad_specs
    if h_code: base += f"\n--- FIRMWARE GENERADO ---\n{h_code}"
    base += soft_specs
    return base

def generate_mathematical_model(command):
    t_vals = np.linspace(0, 10, 5)
    return f"📐 MODELO MATEMÁTICO & SIMULACIÓN\nProblema: {command}\n\n1. Variables\n2. Ecuaciones\n3. Simulación: {t_vals.tolist()}\n4. Interpretación"

def generate_technical_plan(command):
    return f"🧠 PLAN TÉCNICO MASTER\nObjetivo: {command}\n\n1. Definición\n2. Estrategia\n3. Recursos\n4. Próximos pasos"

# ======================================================
# 6. CORE BRAIN (Aether Pro Unificado)
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_output_artifact(mode, domains)

    if cmd_type == "system":
        output = f"🧠 ESTADO DE AETHER\nAgente: {AGENT_NAME}\nModo: {EXECUTION_MODE}\nEstado: OPERATIVO"
    elif artifact == "scientific_design":
        output = generate_scientific_design(command, domains)
    elif artifact == "engineering_design":
        output = generate_engineering_design(command, domains)
    elif artifact == "mathematical_model":
        output = generate_mathematical_model(command)
    else:
        output = generate_technical_plan(command)

    # Firebase log
    if db:
        try:
            db.collection("aether_memory").add({
                "time": datetime.datetime.utcnow().isoformat(),
                "command": command,
                "session": session,
                "domains": domains
            })
        except: pass

    # Generación de Archivos
    pdf_path = create_pdf(output, session)
    dxf_path = create_dxf(session)
    
    return output, pdf_path, dxf_path

# ======================================================
# 7. UI (Gradio)
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 Aether Core — Ingeniería, CAD y Software")
    with gr.Row():
        with gr.Column():
            inp = gr.Textbox(label="Orden Técnica", lines=4)
            sess = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
            btn = gr.Button("GENERAR TODO", variant="primary")
        with gr.Column():
            out_txt = gr.Textbox(label="Vista Previa", lines=12)
            out_pdf = gr.File(label="📄 Descargar Reporte PDF")
            out_dxf = gr.File(label="📐 Descargar Plano CAD (.DXF)")

    btn.click(aether, inputs=[inp, sess], outputs=[out_txt, out_pdf, out_dxf])

demo.launch()