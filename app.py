import gradio as gr
import datetime
import json
import os
import firebase_admin
from firebase_admin import credentials, firestore
import numpy as np

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
EXECUTION_MODE = "SIMULATION"  # REAL en el futuro
DEFAULT_SESSION = "default"

# ======================================================
# 3. OBJETIVOS PERMANENTES (VOLUNTAD)
# ======================================================
GOALS = [
    "expandir_conocimiento",
    "mejorar_precision",
    "recordar_contexto",
    "optimizar_respuestas"
]

# ======================================================
# 4. ONTOLOGÍA MULTIDOMINIO
# ======================================================
DOMAIN_MAP = {
    "matematicas": ["ecuacion", "calculo", "modelo", "optimizacion"],
    "fisica": ["fuerza", "energia", "movimiento", "termodinamica"],
    "quimica": ["reaccion", "molecula", "compuesto"],
    "electronica": ["voltaje", "corriente", "sensor", "esp32", "pcb", "relay", "rele"],
    "mecanica": ["estructura", "engranaje", "dinamica"],
    "mecatronica": ["robot", "control", "actuador"],
    "medicina": ["tratamiento", "diagnostico", "farmaco"],
    "biologia": ["celula", "genetica", "organismo"],
    "nanotecnologia": ["nanobot", "nano", "molecular"],
    "ambiental": ["contaminacion", "agua", "energia limpia"],
    "aeroespacial": ["orbita", "satelite", "cohete", "nasa"]
}

# ======================================================
# 5. HARDWARE KNOWLEDGE BASE
# ======================================================
HARDWARE_LIBRARY = {
    "sensor temperatura": "// Arduino DHT\n#include <DHT.h>\nDHT dht(2, DHT11);\nvoid setup(){ dht.begin(); }",
    "rele": "// Relé básico\nvoid setup(){ pinMode(5, OUTPUT); }\nvoid loop(){ digitalWrite(5, HIGH); }",
    "ultrasonico": "// HC-SR04\nconst int trig=9, echo=10;\nvoid setup(){ pinMode(trig,OUTPUT); pinMode(echo,INPUT); }"
}

# ======================================================
# 6. PLUGIN SYSTEM (IA MODULAR)
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

# ======================================================
# 7. COGNITIVE FUNCTIONS
# ======================================================
def think(command):
    return [
        "comprender_problema",
        "detectar_dominio",
        "seleccionar_estrategia",
        "generar_solucion",
        "verificar_coherencia"
    ]

def select_mode(command):
    t = command.lower()
    if any(k in t for k in ["analizar", "calcular", "demostrar", "simular"]):
        return "scientific"
    if any(k in t for k in ["diseñar", "crear", "construir"]):
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
    if any(k in t for k in ["hardware", "sensor", "rele", "pcb"]):
        return "engineering"
    if t.startswith(("crear", "diseñar")):
        return "task"
    return "order"

def decide_artifact(mode, domains):
    if any(d in domains for d in ["medicina", "nanotecnologia"]):
        return "scientific_design"
    if any(d in domains for d in ["electronica", "mecatronica", "mecanica"]):
        return "engineering_design"
    if mode == "scientific":
        return "mathematical_model"
    return "technical_plan"

# ======================================================
# 8. MEMORY SYSTEM (SEMÁNTICA)
# ======================================================
def text_to_vector(text, dim=128):
    np.random.seed(abs(hash(text)) % (2**32))
    return np.random.rand(dim).tolist()

def cosine_similarity(v1, v2):
    v1, v2 = np.array(v1), np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def store_memory(command, response, domains, session):
    if not db:
        return
    db.collection("aether_semantic_memory").add({
        "command": command,
        "response": response,
        "domains": domains,
        "session": session,
        "vector": text_to_vector(command),
        "time": datetime.datetime.utcnow().isoformat()
    })

def retrieve_similar_memories(command, top_k=3):
    if not db:
        return []
    qv = text_to_vector(command)
    memories = []
    for doc in db.collection("aether_semantic_memory").stream():
        data = doc.to_dict()
        sim = cosine_similarity(qv, data["vector"])
        memories.append((sim, data))
    memories.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in memories[:top_k]]

# ======================================================
# 9. EVENT LOG
# ======================================================
def log_event(data):
    if not db:
        return
    data.update({
        "agent": AGENT_NAME,
        "execution_mode": EXECUTION_MODE,
        "time": datetime.datetime.utcnow().isoformat()
    })
    db.collection("aether_memory").add(data)

# ======================================================
# 10. ARTIFACT GENERATORS
# ======================================================
def generate_scientific_design(cmd, domains):
    return f"""📄 DISEÑO CIENTÍFICO AVANZADO
Objetivo: {cmd}
Dominios: {", ".join(domains)}
1. Fundamentación
2. Principios
3. Modelo
4. Supuestos
5. Aplicaciones
"""

def generate_engineering_design(cmd, domains):
    firmware = next((v for k, v in HARDWARE_LIBRARY.items() if k in cmd.lower()), "")
    return f"""⚙️ DISEÑO DE INGENIERÍA
Objetivo: {cmd}
Dominios: {", ".join(domains)}
1. Arquitectura
2. Componentes
3. Control
4. Seguridad
5. Prototipo

--- FIRMWARE ---
{firmware if firmware else "No requerido"}
"""

def generate_mathematical_model(cmd):
    return f"""📐 MODELO MATEMÁTICO
Problema: {cmd}
1. Variables
2. Ecuaciones
3. Supuestos
4. Método
5. Interpretación
"""

def generate_technical_plan(cmd):
    return f"""🧠 PLAN TÉCNICO
Objetivo: {cmd}
1. Definición
2. Estrategia
3. Recursos
4. Riesgos
5. Próximos pasos
"""

# ======================================================
# 11. CORE BRAIN (AETHER)
# ======================================================
def aether(command, session=DEFAULT_SESSION):
    for name, plugin in PLUGINS.items():
        if name in command.lower():
            return plugin(command)

    steps = think(command)

    memories = retrieve_similar_memories(command)
    memory_context = ""
    if memories:
        memory_context = "🧠 CONTEXTO RECORDADO:\n"
        for m in memories:
            memory_context += f"- {m['command']} ({m['domains']})\n"

    cmd_type = classify_command(command)
    mode = select_mode(command)
    domains = detect_domains(command)
    artifact = decide_artifact(mode, domains)

    log_event({
        "command": command,
        "session": session,
        "type": cmd_type,
        "mode": mode,
        "domains": domains,
        "artifact": artifact,
        "steps": steps
    })

    if cmd_type == "system":
        output = f"""🧠 ESTADO DE AETHER
Agente: {AGENT_NAME}
Modo: {EXECUTION_MODE}
Sesión: {session}
Objetivos: {", ".join(GOALS)}
Estado: OPERATIVO
"""
    elif artifact == "scientific_design":
        output = generate_scientific_design(command, domains)
    elif artifact == "engineering_design":
        output = generate_engineering_design(command, domains)
    elif artifact == "mathematical_model":
        output = generate_mathematical_model(command)
    else:
        output = generate_technical_plan(command)

    final_output = memory_context + "\n" + output
    store_memory(command, final_output, domains, session)
    return final_output

# ======================================================
# 12. UI
# ======================================================
with gr.Blocks(title="AETHER CORE") as demo:
    gr.Markdown("## 🧠 AETHER CORE — Sistema Cognitivo Autónomo")
    session = gr.Textbox(label="Sesión", value=DEFAULT_SESSION)
    inp = gr.Textbox(label="Orden", lines=4)
    out = gr.Textbox(label="Resultado", lines=30)
    btn = gr.Button("EJECUTAR AETHER", variant="primary")
    btn.click(aether, inputs=[inp, session], outputs=out)

demo.launch()

