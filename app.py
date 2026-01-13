# ===================== FIXES PARA HUGGING FACE =====================
import matplotlib
matplotlib.use("Agg")

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
# 1. FIREBASE INIT (SEGURO PARA HF)
# ======================================================
db = None
try:
    firebase_key = None
    if "FIREBASE_KEY" in os.environ:
        firebase_key = json.loads(os.environ["FIREBASE_KEY"])
    elif os.path.exists("llave.json"):
        firebase_key = json.load(open("llave.json"))

    if firebase_key and not firebase_admin._apps:
        cred = credentials.Certificate(firebase_key)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
except Exception as e:
    print("Firebase desactivado:", e)
    db = None

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
    "hardware": ["sensor", "arduino", "esp32"],
    "software": ["app", "aplicacion"]
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
# 6. PLUGIN APP (INTEGRADO)
# ======================================================
def app_plugin(command):
    return f"""📱 AETHER APP ENGINE

Objetivo:
{command}

1. Definición de la aplicación
2. Funciones clave
3. Arquitectura (frontend / backend)
4. Diseño UI/UX
5. Integración de IA
6. Deploy y escalado

Estado: PLAN DE APP GENERADO
"""

# ======================================================
# 7. MOTOR CIENTÍFICO EVOLUTIVO
# ======================================================
def scientific_engine(command):

    os.makedirs("outputs", exist_ok=True)

    t = np.linspace(0, 10, 200)
    experiments = []
    history = []

    for a in [1.0, 2.0, 3.0, 4.0]:
        v0, x0 = 1.0, 0.0
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

    if db:
        db.collection("scientific_learning").add({
            "command": command,
            "best_a": best["a"],
            "stability": stability,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

    fig_id = f"outputs/graph_{uuid.uuid4().hex}.png"
    for i, x in enumerate(history):
        plt.plot(t, x, label=f"a={experiments[i]['a']}")
    plt.legend()
    plt.title("Simulación científica AETHER")
    plt.xlabel("Tiempo")
    plt.ylabel("Posición")
    plt.savefig(fig_id)
    plt.close()

    generate_scientific_report(command, experiments, best, stability)

    return f"""
🔬 AETHER — CIENCIA EVOLUTIVA

Experimentos ejecutados: {len(experiments)}

Mejor modelo:
- a = {best['a']}
- Posición final = {best['final_position']:.2f}

Estabilidad del sistema (σ):
- {stability:.4f}

Aprendizaje:
- Modelo almacenado

Gráfico generado:
- {fig_id}

Estado: CIENCIA COMPLETADA
"""

# ======================================================
# 8. REPORTE PDF (HF SAFE)
# ======================================================
def generate_scientific_report(command, experiments, best, stability):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

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

    pdf.output("outputs/aether_scientific_report.pdf")

# ======================================================
# 9. UTILIDADES
# ======================================================
def detect_domains(command):
    t = command.lower()
    return [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)] or ["general"]

def is_scientific(_


