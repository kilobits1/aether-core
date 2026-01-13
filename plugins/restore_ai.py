# plugins/restore_ai.py
import os
import shutil

def can_handle(command: str) -> bool:
    c = (command or "").strip().lower()
    return c.startswith("restore ") or c in ("exports", "list exports", "listar exports")

def run(command: str):
    c = (command or "").strip()
    cl = c.lower().strip()

    data_dir = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
    export_root = os.path.join(data_dir, "exports")
    os.makedirs(export_root, exist_ok=True)

    # ---- listar exports ----
    if cl in ("exports", "list exports", "listar exports"):
        names = []
        try:
            for n in os.listdir(export_root):
                p = os.path.join(export_root, n)
                if os.path.isdir(p):
                    names.append(n)
        except Exception:
            pass
        names.sort()
        return {"ok": True, "exports_dir": export_root, "snapshots": names}

    # ---- restore <name> ----
    parts = c.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        return {"ok": False, "error": "Uso: restore <snapshot_name> | exports"}

    name = parts[1].strip()
    snap_dir = os.path.join(export_root, name)

    if not os.path.isdir(snap_dir):
        return {"ok": False, "error": f"Snapshot no existe: {name}", "exports_dir": export_root}

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

