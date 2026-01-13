# plugins/tasks_ai.py
from plugins.aether_core import enqueue_task, store

def _msg(text: str):
    return [{"text": text, "type": "text"}]

def _logic(user_text: str, state: dict):
    t = (user_text or "").strip().lower()

    if t in ("task a", "tarea a"):
        tid = enqueue_task(
            "files.write_text",
            {"path": "test/hello.txt", "text": "AETHER v26 OK\n"},
            priority=10
        )
        return _msg(f"OK. Encolé TASK A: {tid}")

    if t in ("task b", "tarea b"):
        tid = enqueue_task(
            "files.list_dir",
            {"path": ""},
            priority=20
        )
        return _msg(f"OK. Encolé TASK B: {tid}")

    if t in ("task c", "tarea c"):
        tid = enqueue_task(
            "shell.exec",
            {"cmd": ["python", "-c", "print('runner ok')"]},
            timeout_s=30,
            priority=5
        )
        return _msg(f"OK. Encolé TASK C: {tid}")

    if t in ("task last", "task recent"):
        return _msg(str(store.list_recent(10)))

    if t.startswith("task show "):
        tid = t.replace("task show ", "").strip()
        return _msg(str(store.get_task(tid)))

    return None

# Compatibilidad: algunos routers llaman run(), otros handle()
def run(user_text: str, state: dict):
    return _logic(user_text, state)

def handle(user_text: str, state: dict):
    return _logic(user_text, state)
