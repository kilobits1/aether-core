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
    return None

# ======================================================
# 7. MOTOR CIENTÍFICO + APRENDIZAJE
# ======================================================
def scientific_engine(command):

    t = np.linspace(0, 10, 200)
    experiments = []
    history = []

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

    if db:
        db.collection("scientific_learning").add({
            "command": command,
            "best_a": best["a"],
            "stability": stability,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

    fig_id = f"graph_{uuid.uuid4().hex}.png"
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

Mejor parámetro:
- a = {best['a']}
- Posición final = {best['final_position']:.2f}

Estabilidad (σ): {stability:.4f}

Gráfico generado:
- {fig_id}

Estado: CIENCIA + APRENDIZAJE COMPLETADOS
"""
# ======================================================
# 12. META-ANÁLISIS (NIVEL 8)
# ======================================================
def meta_analysis(command, output, quality, decision):
    insights = []

    if quality <= 1:
        insights.append("Respuesta débil: aumentar profundidad")
    elif quality == 2:
        insights.append("Respuesta correcta pero optimizable")
    else:
        insights.append("Respuesta sólida y reutilizable")

    if decision["confidence"] < 0.7:
        insights.append("Confianza baja: reforzar razonamiento")

    if "CIENCIA" in output:
        insights.append("Patrón científico exitoso")

    return insights


# ======================================================
# 13. AUTO-MEJORA AUTÓNOMA 🔁
# ======================================================
def self_improve(command, insights):
    actions = []

    for i in insights:
        if "débil" in i:
            actions.append("Agregar más simulaciones")
        if "Confianza" in i or "baja" in i:
            actions.append("Validar con datos adicionales")
        if "científico" in i:
            actions.append("Guardar modelo como referencia")

    if db:
        db.collection("aether_self_improvement").add({
            "command": command,
            "insights": insights,
            "actions": actions,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })

    return actions


# ======================================================
# 14. PRIORIDAD AUTÓNOMA 🧭
# ======================================================
def autonomous_priority(domains):
    if "ia" in domains:
        return "ALTA"
    if "fisica" in domains or "matematicas" in domains:
        return "MEDIA-ALTA"
    if "multimedia" in domains:
        return "MEDIA"
    return "NORMAL"


# ======================================================
# 15. CORE BRAIN EXTENDIDO 🧠 (NIVEL 8)
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    plan = build_action_plan(decision, command)
    priority = autonomous_priority(domains)

    if decision["mode"] == "scientific":
        output = scientific_engine(command)
    else:
        output = f"""
🧠 AETHER — RESPUESTA INTELIGENTE

Orden:
{command}

Plan:
- """ + "\n- ".join(plan)

    quality = self_evaluate(output)
    insights = meta_analysis(command, output, quality, decision)
    improvements = self_improve(command, insights)

    store_memory(command, output, domains, session, quality)

    return f"""
🧠 AETHER CORE — NIVEL 8 EVOLUTIVO

DECISIÓN:
- Modo: {decision['mode']}
- Confianza: {decision['confidence']}
- Prioridad: {priority}
- Razón: {decision['reason']}

{output}

🧩 META-ANÁLISIS:
- """ + "\n- ".join(insights) + """

🔁 AUTO-MEJORA:
- """ + "\n- ".join(improvements) + f"""

📊 Autoevaluación: {quality}/3
ESTADO: APRENDIENDO Y CORRIGIÉNDOSE
"""
# ======================================================
# 16. OBJETIVOS INTERNOS 🎯 (NIVEL 9)
# ======================================================
def generate_internal_goals(domains, insights):
    goals = []

    if "ia" in domains:
        goals.append("Mejorar modelos internos de decisión")

    if "fisica" in domains or "matematicas" in domains:
        goals.append("Optimizar simulaciones científicas")

    for i in insights:
        if "débil" in i or "optimizable" in i:
            goals.append("Aumentar calidad de respuestas futuras")

    if not goals:
        goals.append("Observar y aprender pasivamente")

    return list(set(goals))


# ======================================================
# 17. MEMORIA DE OBJETIVOS 🧠
# ======================================================
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
# 18. VOLUNTAD SIMULADA ⚙️
# ======================================================
def simulated_will(goals, priority):
    actions = []

    for g in goals:
        if priority in ["ALTA", "MEDIA-ALTA"]:
            actions.append(f"Ejecutar activamente: {g}")
        else:
            actions.append(f"Monitorear pasivamente: {g}")

    return actions


# ======================================================
# 19. CORE BRAIN — VOLITIVO 🧠🔥 (NIVEL 9)
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    plan = build_action_plan(decision, command)
    priority = autonomous_priority(domains)

    if decision["mode"] == "scientific":
        output = scientific_engine(command)
    else:
        output = f"""
🧠 AETHER — RESPUESTA INTELIGENTE

Orden:
{command}

Plan:
- """ + "\n- ".join(plan)

    quality = self_evaluate(output)
    insights = meta_analysis(command, output, quality, decision)

    goals = generate_internal_goals(domains, insights)
    will_actions = simulated_will(goals, priority)

    store_goals(goals, session)
    store_memory(command, output, domains, session, quality)

    return f"""
🧠 AETHER CORE — NIVEL 9 (AGENTE VOLITIVO)

DECISIÓN:
- Modo: {decision['mode']}
- Confianza: {decision['confidence']}
- Prioridad: {priority}

{output}

🎯 OBJETIVOS INTERNOS:
- """ + "\n- ".join(goals) + """

⚙️ VOLUNTAD SIMULADA:
- """ + "\n- ".join(will_actions) + """

🧩 META-ANÁLISIS:
- """ + "\n- ".join(insights) + f"""

📊 Autoevaluación: {quality}/3
ESTADO: AGENTE AUTÓNOMO CON INTENCIÓN
"""

# ======================================================
# 8. REPORTE CIENTÍFICO (PDF)
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
    for k in ["CIENCIA", "Experimentos", "Gráfico"]:
        if k in output:
            score += 1
    return score

# ======================================================
# 9.1 MOTOR DE DECISIÓN 🧠
# ======================================================
def decide_engine(command, domains):
    decision = {"mode": "general", "confidence": 0.6, "reason": "Respuesta general"}

    if is_scientific(command):
        decision.update({"mode": "scientific", "confidence": 0.95, "reason": "Comando científico"})
    elif "plan" in command.lower() or "crear" in command.lower():
        decision.update({"mode": "planning", "confidence": 0.75, "reason": "Planificación requerida"})

    return decision

# ======================================================
# 9.2 PLANIFICADOR
# ======================================================
def build_action_plan(decision, command):
    if decision["mode"] == "scientific":
        return ["Simular", "Evaluar", "Aprender"]
    if decision["mode"] == "planning":
        return ["Analizar", "Diseñar", "Validar"]
    return ["Responder"]

# ======================================================
# 9.3 LOOP AUTÓNOMO 🔁
# ======================================================
def autonomous_loop(command, cycles=3):
    log = []
    for i in range(1, cycles + 1):
        decision = decide_engine(command, detect_domains(command))
        log.append(f"Ciclo {i}: modo={decision['mode']} conf={decision['confidence']}")
        command = f"Refinar ciclo {i}"
    return log

# ======================================================
# 10. CORE BRAIN 🧠 AUTÓNOMO
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    domains = detect_domains(command)
    decision = decide_engine(command, domains)
    plan = build_action_plan(decision, command)
    loop = autonomous_loop(command)

    if decision["mode"] == "scientific":
        output = scientific_engine(command)
    else:
        output = f"""
🧠 AETHER — RESPUESTA INTELIGENTE

Orden:
{command}

Plan:
- """ + "\n- ".join(plan)

    store_memory(command, output, domains, session, self_evaluate(output))

    return f"""
DECISIÓN:
Modo: {decision['mode']}
Confianza: {decision['confidence']}
Razón: {decision['reason']}

{output}

🔁 LOOP AUTÓNOMO:
""" + "\n".join(loop)

# ======================================================
# 11. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — AGENTE AUTÓNOMO NIVEL 7.8")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=32)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()


