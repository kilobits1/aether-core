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

def is_real_mode():
    return EXECUTION_MODE == "REAL"

# ======================================================
# 3. MISIONES
# ======================================================
MISSIONS = {
    "principal": "Diseñar y optimizar sistemas inteligentes reales",
    "secundarias": [
        "Aprender de interacciones",
        "Recordar contexto",
        "Optimizar decisiones",
        "Ejecutar modelos científicos"
    ]
}

# ======================================================
# 4. DOMINIOS
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "electronica": ["sensor", "esp32", "rele"],
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

def retrieve_similar_memories(command, top_k=3):
    if not db:
        return []
    qv = text_to_vector(command)
    memories = []
    for doc in db.collection("aether_memory").stream():
        data = doc.to_dict()
        sim = cosine_similarity(qv, data["vector"])
        memories.append((sim, data))
    memories.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in memories[:top_k]]

# ======================================================
# 6. MOTOR CIENTÍFICO REAL 🔬
# ======================================================
def scientific_engine(command):
    """
    Motor científico básico ejecutable.
    Simula un sistema físico simple: movimiento con aceleración constante.
    """

    # Variables del modelo
    t = np.linspace(0, 10, 100)
    a = 2.0        # aceleración
    v0 = 1.0       # velocidad inicial
    x0 = 0.0       # posición inicial

    # Modelo físico
    v = v0 + a * t
    x = x0 + v0 * t + 0.5 * a * t**2

    # Evaluación
    max_pos = float(np.max(x))
    final_vel = float(v[-1])

    result = f"""🔬 MOTOR CIENTÍFICO EJECUTADO
Modelo: Movimiento rectilíneo uniformemente acelerado

Ecuaciones:
v(t) = v0 + a·t
x(t) = x0 + v0·t + ½·a·t²

Parámetros:
a = {a}
v0 = {v0}
x0 = {x0}

Resultados:
- Velocidad final: {final_vel:.2f}
- Posición máxima: {max_pos:.2f}

Estado: SIMULACIÓN COMPLETADA
"""

    return result

# ======================================================
# 7. UTILIDADES COGNITIVAS
# ======================================================
def detect_domains(command):
    t = command.lower()
    domains = [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)]
    return domains if domains else ["general"]

def is_scientific(command):
    return any(k in command.lower() for k in ["calcular", "simular", "modelo", "fisica", "ecuacion"])

# ======================================================
# 8. AUTOEVALUACIÓN
# ======================================================
def self_evaluate(output):
    score = 0
    if len(output) > 200: score += 1
    if "Modelo" in output: score += 1
    if "Resultados" in output: score += 1
    if "SIMULACIÓN" in output: score += 1
    return score

# ======================================================
# 9. EXPORTACIÓN
# ======================================================
def export_pdf(content, filename="aether_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, content)
    pdf.output(filename)

# ======================================================
# 10. CORE BRAIN 🧠
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    memories = retrieve_similar_memories(command)
    memory_context = ""
    if memories:
        memory_context = "🧠 CONTEXTO RECORDADO:\n"
        for m in memories:
            memory_context += f"- {m['command']} ({m['domains']})\n"

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

    final_output = memory_context + "\n" + output
    quality = self_evaluate(final_output)

    store_memory(command, final_output, domains, session, quality)

    if is_real_mode():
        export_pdf(final_output)

    return final_output + f"\n🔍 Autoevaluación: {quality}/4"

# ======================================================
# 11. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — Núcleo Cognitivo + Motor Científico")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()



