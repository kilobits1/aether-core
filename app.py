# ======================================================
# IMPORTS
# ======================================================
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
# 2. CONFIG
# ======================================================
DEFAULT_SESSION = "default"

DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "ia": ["modelo", "red", "inteligencia"],
    "multimedia": ["video", "musica"],
    "hardware": ["sensor", "arduino", "esp32"]
}

# ======================================================
# 3. UTILIDADES
# ======================================================
def detect_domains(command):
    t = command.lower()
    return [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)] or ["general"]

def is_scientific(command):
    return any(k in command.lower() for k in ["modelo", "simular", "experimento", "fisica"])

def self_evaluate(output):
    score = 0
    for k in ["CIENCIA", "Experimentos", "Gráfico"]:
        if k in output:
            score += 1
    return score

def decide_engine(command, domains):
    decision = {"mode": "general", "confidence": 0.6, "reason": "Respuesta general"}
    if is_scientific(command):
        decision.update({"mode": "scientific", "confidence": 0.95, "reason": "Comando científico"})
    elif "plan" in command.lower() or "crear" in command.lower():
        decision.update({"mode": "planning", "confidence": 0.75, "reason": "Planificación requerida"})
    return decision

def build_action_plan(decision, command):
    if decision["mode"] == "scientific":
        return ["Simular", "Evaluar", "Aprender"]
    if decision["mode"] == "planning":
        return ["Analizar", "Diseñar", "Validar"]
    return ["Responder"]

# ======================================================
# 4. MEMORIA
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

def store_goals(goals, session):
    if not db:
        return
    for g in goals:
        db.collection("aether_goals").add({
            "goal": g,
            "session": session,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

# ======================================================
# 5. CIENCIA
# ======================================================
def generate_scientific_report(command, experiments, best, stability):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 8, f"""
AETHER SCIENTIFIC REPORT
Command: {command}
Experiments: {experiments}
Best: {best}
Stability: {stability}
Date: {datetime.datetime.utcnow().isoformat()}
""")
    pdf.output("aether_scientific_report.pdf")

def scientific_engine(command):
    t = np.linspace(0, 10, 200)
    experiments, history = [], []

    for a in [1, 2, 3, 4]:
        v0, x0 = 1.0, 0.0
        v = v0 + a * t
        x = x0 + v0 * t + 0.5 * a * t**2
        experiments.append({"a": a, "final_position": float(x[-1])})
        history.append(x)

    best = max(experiments, key=lambda e: e["final_position"])
    stability = np.std([e["final_position"] for e in experiments])

    fig = f"graph_{uuid.uuid4().hex}.png"
    for i, x in enumerate(history):
        plt.plot(t, x, label=f"a={experiments[i]['a']}")
    plt.legend()
    plt.savefig(fig)
    plt.close()

    generate_scientific_report(command, experiments, best, stability)

    return f"""
🔬 AETHER — CIENCIA
Experimentos: {len(experiments)}
Mejor a: {best['a']}
Estabilidad σ: {stability:.4f}
Gráfico: {fig}
"""

# ======================================================
# 6. META / OBJETIVOS
# ======================================================
def meta_analysis(command, output, quality, decision):
    insights = []
    if quality < 2:
        insights.append("Respuesta débil")
    if decision["confidence"] < 0.7:
        insights.append("Confianza baja")
    if "CIENCIA" in output:
        insights.append("Patrón científico")
    return insights or ["Respuesta estable"]

def generate_internal_goals(domains, insights):
    goals = []
    if "ia" in domains:
        goals.append("Mejorar decisiones")
    if "fisica" in domains:
        goals.append("Optimizar simulaciones")
    for i in insights:
        if "débil" in i:
            goals.append("Aumentar calidad")
    return list(set(goals)) or ["Observar"]

def simulated_will(goals, focus):
    return [f"Ejecutar: {g}" if focus == "EXPANSION" else f"Monitorear: {g}" for g in goals]

# ======================================================
# 7. ESTADO VITAL (NIVEL 10)
# ======================================================
AETHER_STATE = {
    "energy": 100,
    "focus": "EXPANSION",
    "last_cycle": None
}

def life_cycle():
    AETHER_STATE["energy"] -= 1
    AETHER_STATE["last_cycle"] = datetime.datetime.utcnow().isoformat()
    AETHER_STATE["focus"] = "RECOVERY" if AETHER_STATE["energy"] < 30 else "EXPANSION"

def adaptive_role(domains):
    if "fisica" in domains:
        return "CIENTÍFICO"
    if "ia" in domains:
        return "ARQUITECTO IA"
    return "ASISTENTE"

def operational_awareness(decision, quality):
    a = []
    if quality < 2:
        a.append("Mejorar razonamiento")
    if decision["confidence"] < 0.7:
        a.append("Aprender más")
    return a or ["Estado estable"]

# ======================================================
# 8. VERSIONES DE AETHER (SIN PISARSE)
# ======================================================
def aether_v8(command, session):
    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    output = scientific_engine(command) if decision["mode"] == "scientific" else command
    store_memory(command, output, domains, session, self_evaluate(output))
    return f"AETHER V8\n{output}"

def aether_v9(command, session):
    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    output = scientific_engine(command) if decision["mode"] == "scientific" else command
    insights = meta_analysis(command, output, self_evaluate(output), decision)
    goals = generate_internal_goals(domains, insights)
    store_goals(goals, session)
    store_memory(command, output, domains, session, self_evaluate(output))
    return f"AETHER V9\n{output}\nGOALS:\n" + "\n".join(goals)

def aether_v10(command, session):
    life_cycle()
    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    output = scientific_engine(command) if decision["mode"] == "scientific" else command
    quality = self_evaluate(output)
    awareness = operational_awareness(decision, quality)
    goals = generate_internal_goals(domains, awareness)
    store_goals(goals, session)
    store_memory(command, output, domains, session, quality)
    return f"""
AETHER V10
Energía: {AETHER_STATE['energy']}
Enfoque: {AETHER_STATE['focus']}
{output}
CONCIENCIA:
- """ + "\n- ".join(awareness)

# ======================================================
# 9. AETHER GENERAL (DISPATCHER)
# ======================================================
def aether(command, session=DEFAULT_SESSION, level=10):
    if level == 8:
        return aether_v8(command, session)
    if level == 9:
        return aether_v9(command, session)
    return aether_v10(command, session)

# ======================================================
# 10. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — GENERAL")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR")
    btn.click(lambda c, s: aether(c, s, level=10), inputs=[inp, session], outputs=out)
# ======================================================
# 11. COLA DE TAREAS AUTÓNOMA
# ======================================================
from collections import deque

AETHER_TASK_QUEUE = deque()

def enqueue_task(command, reason="internal"):
    AETHER_TASK_QUEUE.append({
        "command": command,
        "reason": reason,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

def dequeue_task():
    if AETHER_TASK_QUEUE:
        return AETHER_TASK_QUEUE.popleft()
    return None

demo.launch()

