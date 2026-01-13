# plugins/tasks_ai.py
from plugins.aether_core import enqueue_task, store

def run(command: str, state: dict):
    c = (command or "").strip().lower()

    if c == "task a":
        tid = enqueue_task(
            "files.write_text",
            {"path": "test/hello.txt", "text": "AETHER v26 OK\n"},
            priority=10
        )
        return [{"text": f"OK. Encolé TASK A: {tid}", "type": "text"}]

    if c == "task b":
        tid = enqueue_task(
            "files.list_dir",
            {"path": ""},
            priority=20
        )
        return [{"text": f"OK. Encolé TASK B: {tid}", "type": "text"}]

    if c == "task c":
        tid = enqueue_task(
            "shell.exec",
            {"cmd": ["python", "-c", "print('runner ok')"]},
            timeout_s=30,
            priority=5
        )
        return [{"text": f"OK. Encolé TASK C: {tid}", "type": "text"}]

    if c == "task last":
        return [{"text": str(store.list_recent(10)), "type": "text"}]

    return None
