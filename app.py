import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np
from fpdf import FPDF

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
        "Recordar contexto",
        "Optimizar decisiones",
        "Ejecutar modelos científicos",
        "Experimentar y evaluar hipótesis"
    ]
}

# ======================================================
# 4. DOMINIOS
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "ia": ["modelo", "red", "inteligencia"],
    "multimedia": ["video", "musica", "audio"],
    "software": ["app", "aplicacion"]
}

# ======================================================
# 5. MEMORIA SEMÁNTICA
# ======================================================
def text_to_vector(text, dim=128):
    np.random.seed(abs(hash(text)) % (2**32))
    return np.random.rand(dim).tolist()

def cosine_similarity(v1, v2):
    v1, v2 = np.array(v1), np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

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
# 6. MEMORIA CIENTÍFICA 🔬
# ======================================================
def store_scientific_result(data):
    if not db:
        return
    db.collection("aether_science").add({
        **data,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

# ======================================================
# 7. MOTOR CIENTÍFICO AVANZADO
# ======================================================
def scientific_engine(command):

    t = np.linspace(0, 10, 200)
    experiments = []
    hypotheses = []

    # Hipótesis automática
    for a in [1.0, 2.0, 3.0]:
        hypotheses.append(f"Si a = {a}, la posición final aumenta proporcionalmente")

        v0 = 1.0
        x0 = 0.0

        v = v0 + a * t
        x = x0 + v0 * t + 0.5 * a * t**2

        experiments.append({
            "a": a,
            "final_velocity": float(v[-1]),
            "final_position": float(x[-1]),
            "max_position": float(np.max(x))
        })

    # Evaluación científica
    best = max(experiments, key=lambda e: e["final_position"])
    stability = np.std([e["final_position"] for e in experiments])

    store_scientific_result({
        "command": command,
        "experiments": experiments,
        "best_model": best,
        "stability": stability
    })

    result = "🔬 MOTOR CIENTÍFICO AVANZADO\n\n"
    result += "Hipótesis generadas:\n"
    for h in hypotheses:
        result += f"- {h}\n"

    result += "\nResultados experimentales:\n"
    for e in experiments:
        result += f"a={e['a']} → pos_final={e['final_position']:.2f}\n"

    result += f"""
Evaluación:
- Mejor modelo: a = {best['a']}
- Posición final óptima: {best['final_position']:.2f}
- Estabilidad (σ): {stability:.4f}

Estado: EXPERIMENTACIÓN COMPLETA
"""

    return result

# ======================================================
# 8. UTILIDADES
# ======================================================
def detect_domains(command):
    t = command.lower()
    domains = [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)]
    return domains if domains else ["general"]

def is_scientific(command):
    return any(k in command.lower() for k in ["calcular", "simular", "modelo", "fisica", "experimento"])

def self_evaluate(output):
    score = 0
    if "Hipótesis" in output: score += 1
    if "Resultados" in output: score += 1
    if "Evaluación" in output: score += 1
    if "EXPERIMENTACIÓN" in output: score += 1
    return score

# ======================================================
# 9. CORE BRAIN 🧠
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    domains = detect_domains(command)

    if is_scientific(command):
        output = scientific_engine(command)
    else:
        output = f"""🧠 RESULTADO GENERAL
Objetivo: {command}
Dominios: {", ".join(domains)}

1. Análisis
2. Diseño
3. Ejecución
4. Evaluación
"""

    quality = self_evaluate(output)
    store_memory(command, output, domains, session, quality)

    return output + f"\n🔍 Autoevaluación: {quality}/4"

# ======================================================
# 10. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — IA Científica Autónoma")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()




