# plugins/restore_ai.py
import os
import shutil

def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c.startswith("restore ")

def run(command: str):
    parts = command.strip().split(" ", 1)
    if len(parts) < 2:
        return {"ok": False, "error": "Uso: restore <snapshot_name>"}

    name = parts[1].strip()
    data_dir = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
    snap_dir = os.path.join(data_dir, "exports", name)

    if not os.path.isdir(snap_dir):
        return {"ok": False, "error": f"Snapshot no existe: {name}"}

    restored = []
    for fn in os.listdir(snap_dir):
        src = os.path.join(snap_dir, fn)
        dst = os.path.join(data_dir, fn)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            restored.append(fn)

    return {
        "ok": True,
        "msg": "Snapshot restaurado",
        "snapshot": name,
        "restored": restored,
        "note": "Reinicia el Space para aplicar completamente."
    }
