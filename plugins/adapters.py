# adapters.py
import os
import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

class PolicyError(Exception):
    pass

class Adapters:
    """
    Adaptadores de acciones externas con políticas (allowlists).
    """
    def __init__(
        self,
        base_dir: str,
        allowed_shell_cmds: Optional[List[str]] = None,
        allowed_http_domains: Optional[List[str]] = None,
    ):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.allowed_shell_cmds = allowed_shell_cmds or ["python", "pip", "node", "npm"]
        self.allowed_http_domains = allowed_http_domains or []  # si vacío, bloquea http

    # ------------------ FILES ------------------
    def write_text(self, rel_path: str, text: str) -> Dict[str, Any]:
        path = self._safe_path(rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {"ok": True, "path": path, "bytes": len(text.encode("utf-8"))}

    def read_text(self, rel_path: str, max_bytes: int = 200_000) -> Dict[str, Any]:
        path = self._safe_path(rel_path)
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        data = data[:max_bytes]
        return {"ok": True, "path": path, "text": data.decode("utf-8", errors="replace"), "truncated": truncated}

    def list_dir(self, rel_path: str = "") -> Dict[str, Any]:
        path = self._safe_path(rel_path)
        if not os.path.isdir(path):
            return {"ok": False, "error": "not_a_directory", "path": path}
        items = []
        for name in sorted(os.listdir(path)):
            p = os.path.join(path, name)
            items.append({"name": name, "is_dir": os.path.isdir(p), "size": os.path.getsize(p) if os.path.isfile(p) else None})
        return {"ok": True, "path": path, "items": items}

    def _safe_path(self, rel_path: str) -> str:
        rel_path = rel_path.lstrip("/").replace("\\", "/")
        full = os.path.abspath(os.path.join(self.base_dir, rel_path))
        base = os.path.abspath(self.base_dir)
        if not full.startswith(base):
            raise PolicyError("Path traversal blocked")
        return full

    # ------------------ SHELL ------------------
    def shell(self, cmd: List[str], timeout_s: int = 60, cwd_rel: str = "") -> Dict[str, Any]:
        if not cmd:
            raise PolicyError("Empty command blocked")
        exe = cmd[0]
        if exe not in self.allowed_shell_cmds:
            raise PolicyError(f"Command not allowed: {exe}")
        cwd = self._safe_path(cwd_rel) if cwd_rel else self.base_dir

        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
            "cmd": cmd,
        }

    # ------------------ HTTP ------------------
    def http_json(self, url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None, timeout_s: int = 30) -> Dict[str, Any]:
        # política: permitir solo dominios explícitos
        if not self.allowed_http_domains:
            raise PolicyError("HTTP blocked by policy (no allowed_http_domains set)")

        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        if host not in [d.lower() for d in self.allowed_http_domains]:
            raise PolicyError(f"HTTP domain not allowed: {host}")

        data = None
        hdrs = headers or {}
        hdrs.setdefault("User-Agent", "aether-core/1.0")
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")

        req = Request(url=url, method=method.upper(), headers=hdrs, data=data)
        with urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if "application/json" in ct:
                return {"ok": True, "status": resp.status, "json": json.loads(raw.decode("utf-8"))}
            return {"ok": True, "status": resp.status, "text": raw.decode("utf-8", errors="replace")}
