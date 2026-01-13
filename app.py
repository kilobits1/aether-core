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
EXECUTION_MODE = "SIMULATION"  # cambiar a REAL cuando quieras
DEFAULT_SESSION = "default"

def is_real_mode():
    return EXECUTION_MODE == "REAL"

# ======================================================
# 3. MISIONES (VOLUNTAD ARTIFICIAL)
# ======================================================
MISSIONS = {
    "principal": "Diseñar y optimizar sistemas inteligentes reales",
    "secundarias": [
        "Aprender de interacciones",
        "Recordar contexto",
        "Optimizar decisiones",
        "Orquestar herramientas externas"
    ]
}

# ======================================================
# 4. ONTOLOGÍA MULTIDOMINIO
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion"],
    "fisica": ["fuerza", "energia", "movimiento"],
    "electronica": ["sensor", "esp32", "pcb", "rele", "relay"],
    "mecatronica": ["robot", "actuador", "control"],
    "medicina": ["diagnostico", "tratamiento"],
    "ia": ["modelo", "red", "inteligencia"],
    "multimedia": ["video", "musica", "audio", "imagen", "animacion"],
    "software": ["app", "aplicacion", "backend", "frontend"]
}

# ======================================================
# 5. HARDWARE KNOWLEDGE BASE
# ======================================================
HARDWARE_LIBRARY = {
    "sensor temperatura": "// Arduino DHT\n#include <DHT.h>\nDHT dht(2, DHT11);",
    "rele": "// Relé\nvoid setup(){ pinMode(5, OUTPUT); }",
    "ultrasonico": "// HC-SR04\nconst int trig=9, echo=10;"
}

# ======================================================
# 6. PLUGIN SYSTEM (MODULAR)
# ======================================================
PLUGINS = {}

def load_plugins():
    if not os.path.exists("plugins"):
        return
    for file in os.listdir("plugins"):
        if file.endswith(".py"):
            name = file[:-3]
            module = __import__(f"plugins.{name}", fromlist=[name])
            if hasattr(module, "run"):
                PLUGINS[name] = module.run

load_plugins()

def select_plugin(command):
    c = command.lower()
    if "video" in c:
        return "video"
    if "musica" in c or "música" in c:
        return "music"
    if "app" in c:
        return "app"
    return None

# ======================================================
# 7. FUNCIONES COGNITIVAS
# ======================================================
def think(command):
    return [
        "comprender",
        "analizar",
        "recordar",
        "planificar",
        "ejecutar",
        "evaluar"
    ]

def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["calcular", "analizar", "simular"]):
        return "scientific"
    if any(k in t for k in ["crear", "diseñar", "construir"]):
        return "engineering"
    return "general"

def detect_domains(command):
    t = command.lower()
    domains = [d for d, k in DOMAIN_MAP.items() if any(x in t for x in k)]
    return domains if domains else ["general"]

def classify_command(command):
    t = command.lower()
    if "estado" in t:
        return "system"
    return "task"

# ======================================================
# 8. MEMORIA SEMÁNTICA
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
# 9. PLANIFICADOR AUTÓNOMO
# ======================================================
def task_planner(goal):
    g = goal.lower()
    if "video" in g or "musica" in g:
        return [
            "Definir concepto",
            "Crear guion",
            "Diseñar estilo",
            "Generar contenido",
            "Renderizar",
            "Exportar"
        ]
    if "app" in g:
        return [
            "Definir funciones",
            "Diseñar interfaz",
            "Programar backend",
            "Integrar IA",
            "Probar",
            "Desplegar"
        ]
    return [
        "Analizar objetivo",
        "Diseñar solución",
        "Ejecutar",
        "Evaluar"
    ]

def execute_plan(steps):
    log = "🛠️ PLAN DE EJECUCIÓN:\n"
    for i, step in enumerate(steps, 1):
        log += f"{i}. {step}\n"
    return log

# ======================================================
# 10. AUTOEVALUACIÓN
# ======================================================
def self_evaluate(output):
    score = 0
    if len(output) > 200: score += 1
    if "PLAN" in output: score += 1
    if "Objetivo" in output: score += 1
    if "Diseño" in output or "Modelo" in output: score += 1
    return score

# ======================================================
# 11. EXPORTACIÓN
# ======================================================
def export_pdf(content, filename="aether_output.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, content)
    pdf.output(filename)

# ======================================================
# 12. GENERADORES
# ======================================================
def generate_output(cmd, domains):
    return f"""🧠 RESULTADO DE AETHER
Objetivo: {cmd}
Dominios: {", ".join(domains)}

1. Análisis
2. Diseño
3. Ejecución
4. Evaluación
"""

# ======================================================
# 13. CORE BRAIN
# ======================================================
def aether(command, session=DEFAULT_SESSION):

    plugin = select_plugin(command)
    if plugin and plugin in PLUGINS:
        return PLUGINS[plugin](command)

    memories = retrieve_similar_memories(command)
    memory_context = ""
    if memories:
        memory_context = "🧠 CONTEXTO RECORDADO:\n"
        for m in memories:
            memory_context += f"- {m['command']} ({m['domains']})\n"

    domains = detect_domains(command)
    output = generate_output(command, domains)

    plan_steps = task_planner(command)
    plan_log = execute_plan(plan_steps)

    final_output = memory_context + "\n" + output + "\n" + plan_log
    quality = self_evaluate(final_output)

    store_memory(command, final_output, domains, session, quality)

    if is_real_mode():
        export_pdf(final_output)

    return final_output + f"\n🔍 Autoevaluación: {quality}/4"

# ======================================================
# 14. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — Sistema Cognitivo Autónomo")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()


