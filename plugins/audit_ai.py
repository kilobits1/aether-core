# plugins/audit_ai.py
# Auditoría / Arquitectura (solo texto). NO ejecuta cambios. NO internet.

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def can_handle(text: str, state: Dict[str, Any] | None = None) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("audit:") or t.startswith("auditar:")

def run(text: str, state: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Devuelve un diagnóstico de arquitectura basado SOLO en el state que ya expone el core.
    No ejecuta nada, no llama internet, no toca archivos.
    """
    cmd = (text or "").strip()
    q = cmd.split(":", 1)[1].strip().lower() if ":" in cmd else ""

    st = state or {}
    modules = st.get("modules") or st.get("loaded_modules") or []
    kill = st.get("kill_switch") or {}
    version = st.get("version") or st.get("AETHER_VERSION") or "unknown"
    status = st.get("status") or "unknown"
    data_dir = st.get("data_dir") or st.get("DATA_DIR") or "unknown"

    # Señales comunes (robustas ante state incompleto)
    trust_zone = st.get("trust_zone") or st.get("policy", {}).get("trust_zone") or "unknown"
    http_allow = st.get("allowed_http_domains") if "allowed_http_domains" in st else "unknown"
    shell_allow = st.get("allowed_shell_cmds") if "allowed_shell_cmds" in st else "unknown"

    # Diagnóstico en texto (arquitecto senior)
    lines = []
    lines.append("ARQUITECTURA (AUDIT) — MODO SOLO LECTURA")
    lines.append(f"- ts: {_now()}")
    lines.append(f"- version: {version}")
    lines.append(f"- status: {status}")
    lines.append(f"- data_dir: {data_dir}")
    lines.append("")
    lines.append("CAPAS OBSERVADAS")
    lines.append("1) Core/Runtime: orquestación, cola/worker, estado persistente (state/memory/logs).")
    lines.append("2) Plugins: módulos *_ai.py con can_handle/run, cargados dinámicamente.")
    lines.append("3) Safety Gates: trust-zone / policy gate / kill-switch (bloquean acciones sensibles).")
    lines.append("")
    lines.append("MÓDULOS CARGADOS")
    if modules:
        for m in modules:
            lines.append(f"- {m}")
    else:
        lines.append("- (no visible en state)")

    lines.append("")
    lines.append("CONTROLES DE SEGURIDAD (SEÑALES)")
    lines.append(f"- kill_switch: {kill if kill else 'unknown'}")
    lines.append(f"- trust_zone: {trust_zone}")
    lines.append(f"- allowed_http_domains: {http_allow}")
    lines.append(f"- allowed_shell_cmds: {shell_allow}")

    lines.append("")
    lines.append("DEBILIDADES MÁS PROBABLES (TOP 3)")
    lines.append("1) Observabilidad incompleta: si status/version aparecen como 'unknown', el state no está cableado.")
    lines.append("2) Separación de roles limitada: planner_only impide análisis narrativo; falta un canal 'analysis-only'.")
    lines.append("3) Controles por usuario: si el Space es público, faltan roles/owner-only para comandos sensibles (aunque haya gates).")

    lines.append("")
    lines.append("RECOMENDACIÓN INMEDIATA (BAJO RIESGO)")
    lines.append("- Cablear 'status/version' a un state real (solo lectura) para eliminar 'unknown'.")
    lines.append("- Mantener HTTP bloqueado (allowed_http_domains vacío) hasta tener allowlist + logs + rate-limit.")
    lines.append("- Añadir comando audit como este para diagnóstico sin tocar ejecución.")

    # Respuesta
    return {
        "ok": True,
        "ts": _now(),
        "mode": "audit_readonly",
        "query": q or "arquitectura",
        "report": "\n".join(lines),
        "note": "Solo lectura. Sin ejecución. Sin internet."
    }

