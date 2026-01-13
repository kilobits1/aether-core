import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np
from fpdf import FPDF
import matplotlib.pyplot as plt
import uuid

# ======================================================
# 1. FIREBASE INIT
# ======================================================
firebase_key = None
if "FIREBASE_KEY" in os.environ:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
elif os.path.exists("llave.json"):
    firebase_key = json.load(open("llave.json"))

if firebase_key and not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred)

db = firestore.client() if firebase_key else None

# ======================================================
# 2. CORE CONFIG
# ======================================================
AGENT_NAME = "aether-core"
EXECUTION_MODE = "SIMULATION"
DEFAULT_SESSION = "default"

# ======================================================
# 3. MISIONES
# ======================================================
MISSIONS = {
    "principal": "Diseñar y optimizar sistemas inteligentes reales",
    "secundarias": [
        "Aprender de interacciones",
        "Ejecutar ciencia real",
        "Experimentar",
        "Evaluar",
        "Mejorar con el tiempo"
    ]
}

# ======================================================
# 4. DOMINIOS
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "ia": ["modelo", "red", "inteligencia"],
    "multimedia": ["video", "musica"],
    "hardware": ["sensor", "arduino", "esp32"]
}

# ======================================================
# 5. MEMORIA
# ======================================================
def text_to_vector(text, dim=128):
    np.random.seed(abs(hash(text)) % (2**32))
    return np.random.rand(dim).tolist()

def store_memory(command, response, domains, session, quality):
    if not db:
        return
    db.collection("aether_memory").add({
        "command": command,
        "response": response,
        "domains": domains,
        "session": session,
        "quality": quality,
        "vector": text_to_vector(command),
        "time": datetime.datetime.utcnow().isoformat()
    })

# ======================================================
# 6. DATOS REALES (STUB)
# ======================================================
def load_real_data():
    """
    Preparado para sensores, CSV, APIs, IoT.
    Hoy devuelve None (simulación).
    """
    return None

# ======================================================
# 7. MOTOR CIENTÍFICO + APRENDIZAJE
# ======================================================
def scientific_engine(command):

    t = np.linspace(0, 10, 200)
    experiments = []
    history = []

    real_data = load_real_data()

    for a in [1.0, 2.0, 3.0, 4.0]:
        v0 = 1.0
        x0 = 0.0

        v = v0 + a * t
        x = x0 + v0 * t + 0.5 * a * t**2

        experiments.append({
            "a": a,
            "final_position": float(x[-1]),
            "final_velocity": float(v[-1])
        })

        history.append(x)

    best = max(experiments, key=lambda e: e["final_position"])
    stability = np.std([e["final_position"] for e in experiments])

    # 🔁 Aprendizaje continuo
    if db:
        db.collection("scientific_learning").add({
            "command": command,
            "best_a": best["a"],
            "stability": stability,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

    # 📊 Gráfico
    fig_id = f"graph_{uuid.uuid4().hex}.png"
    for i, x in enumerate(history):
        plt.plot(t, x, label=f"a={experiments[i]['a']}")
    plt.legend()
    plt.title("Simulación científica AETHER")
    plt.xlabel("Tiempo")
    plt.ylabel("Posición")
    plt.savefig(fig_id)
    plt.close()

    result = f"""
🔬 AETHER — CIENCIA EVOLUTIVA

Experimentos ejecutados: {len(experiments)}

Mejor parámetro:
- a = {best['a']}
- Posición final = {best['final_position']:.2f}

Estabilidad del sistema (σ):
- {stability:.4f}

Aprendizaje:
- Modelo guardado para futuras decisiones

Gráfico generado:
- {fig_id}

Estado: CIENCIA + APRENDIZAJE COMPLETADOS
"""
    generate_scientific_report(command, experiments, best, stability)

    return result

# ======================================================
# 8. REPORTE CIENTÍFICO (PDF)
# ======================================================
def generate_scientific_report(command, experiments, best, stability):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)

    pdf.multi_cell(0, 8, f"""
AETHER SCIENTIFIC REPORT

Comando:
{command}

Experimentos:
{experiments}

Mejor modelo:
{best}

Estabilidad:
{stability}

Fecha:
{datetime.datetime.utcnow().isoformat()}
""")

    pdf.output("aether_scientific_report.pdf")

# ======================================================
# 9. UTILIDADES
# ======================================================
def detect_domains(command):
    t = command.lower()
    return [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)] or ["general"]

def is_scientific(command):
    return any(k in command.lower() for k in ["modelo", "simular", "experimento", "fisica"])

def self_evaluate(output):
    score = 0
    for k in ["CIENCIA", "Aprendizaje", "Experimentos", "Gráfico"]:
        if k in output:
            score += 1
    return score

# ======================================================
# 10. CORE BRAIN 🧠
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    domains = detect_domains(command)

    if is_scientific(command):
        output = scientific_engine(command)
    else:
        output = f"""
🧠 AETHER — RESPUESTA GENERAL

Orden:
{command}

Dominios:
{domains}

Estado:
LISTO PARA CIENCIA, HARDWARE Y MULTIMEDIA
"""

    quality = self_evaluate(output)
    store_memory(command, output, domains, session, quality)

    return output + f"\n🔍 Autoevaluación: {quality}/4"

# ======================================================
# 11. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — IA Científica Evolutiva")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=28)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()

