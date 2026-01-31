# ======================================================
# AETHER CORE — HF SPACES SAFE (GRADIO ONLY, NO FASTAPI)
# Objetivo: 0 runtime-crash en HF.
#
# Incluye:
#   - Chat compatible con gradio clásico (lista de tuplas user/bot)
#   - Cola + worker thread (budget por tick)
#   - Scheduler/heartbeat thread (opcional)
#   - Plugins hot-reload: plugins/*_ai.py (can_handle/run)
#   - Logs + dashboard (JSON atomic)
#   - v28: Snapshots create/restore/export/import (incluye plugins)
#   - v28.2: Réplica portable (1 JSON) + checksum + apply
#   - v29: Project Orchestrator (projects/tasks + policy gate)
#   - v30: Task lifecycle (PENDING/RUNNING/DONE/FAILED)
#   - v31: Retry + Budget
#   - v32: Planning (subtasks propuesta, NO auto-run) con "plan:"
#   - v35: Autonomy gate (freeze + budget)
#   - v36-37: Watchdog + Safe Mode
#   - v38: Events log JSONL + rotación
#   - v39: UI Tick HF-safe (auto-refresh)
# ======================================================

import os
import sys
import time
import json
import uuid
import hashlib
import hmac
import threading
import importlib.util
import copy
import traceback
import shutil
from queue import PriorityQueue
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import gradio as gr
from plugins.adapters import Adapters


SUPPORTED_LANGS = ("es", "en", "pt-BR", "pt-PT")
LANGUAGE_CHOICES = [
    ("Español", "es"),
    ("English", "en"),
    ("Português (Brasil)", "pt-BR"),
    ("Português (Portugal)", "pt-PT"),
]
LANG = {
    "es": {
        "app_title": "AETHER CORE — HF SAFE",
        "header_beta": "Aether — Beta cerrada",
        "boot_label": "Boot",
        "new_chat": "Nuevo chat",
        "chats": "Chats",
        "chat_label": "AETHER Chat",
        "message_label": "Mensaje",
        "message_placeholder": "Describe lo que quieres hacer...",
        "send_chat": "Enviar (Chat)",
        "reload_modules": "Reload Modules",
        "export_demo1": "Export demo1",
        "refresh_status": "Refresh Status",
        "btn_builder": "🛠️ Crear tu Web / App",
        "btn_scientific": "🔬 Científico",
        "admin_ops": "Operaciones avanzadas (Admin)",
        "task_queue_title": "### Cola de tareas",
        "task_cmd_label": "Comando para cola",
        "task_cmd_placeholder": "Ej: revisar estado interno",
        "priority_label": "Prioridad (1=alta · 20=baja)",
        "enqueue_task": "Enqueue Task (cola)",
        "orchestrator_title": "### v29 — Project Orchestrator",
        "project_name_label": "Nuevo proyecto",
        "project_name_placeholder": "Nombre del proyecto",
        "create_project": "Crear proyecto",
        "project_label": "Proyecto",
        "task_command_label": "Nueva tarea (comando)",
        "task_command_placeholder": "Ej: revisar estado interno",
        "add_task": "Agregar tarea",
        "task_label": "Tarea",
        "run_task": "Run Task (policy/freeze)",
        "orchestrator_output": "Orchestrator output",
        "status_json": "Status JSON",
        "logs_last_n": "Logs últimos N",
        "tail_logs": "Tail Logs",
        "refresh_logs": "Refresh Logs",
        "export_demo1_label": "Export demo1",
        "snapshots_title": "### v28 — Snapshots (v28.3 incluye plugins)",
        "snapshot_name_label": "Snapshot name",
        "create_snapshot": "Create Snapshot",
        "restore_snapshot": "Restore Snapshot",
        "list_snapshots": "List Snapshots",
        "export_snapshot": "Export Snapshot",
        "snapshot_output": "Snapshot output",
        "import_snapshot_json": "Import Snapshot JSON",
        "import_snapshot": "Import Snapshot",
        "replica_title": "### v28.2 — Réplica portable (1 JSON)",
        "replica_name_label": "Replica name",
        "export_replica": "Export Replica (JSON)",
        "replica_json": "Replica JSON",
        "import_replica_json": "Import Replica JSON",
        "import_replica_apply": "Import Replica (apply)",
        "replica_import_result": "Replica import result",
        "home_button": "⬅️ Home",
        "builder_title": "## Crear tu Web / App / Sistema",
        "builder_subtitle": "Diseña y estructura proyectos en distintas tecnologías.",
        "builder_tags": "**Web · Móvil · Escritorio · Embebidos**  \n(Python · Java · C++ · JavaScript · Arduino · y más)",
        "builder_desc": (
            "Aether puede ayudarte a diseñar proyectos y generar código base, "
            "para que los pruebes y continúes el desarrollo en tu propio entorno."
        ),
        "project_id_label": "Project ID",
        "export_zip_label": "Export ZIP",
        "export_button": "Exportar",
        "builder_chat_label": "Builder Chat",
        "builder_message_placeholder": "Describe lo que quieres construir...",
        "send_button": "Enviar",
        "scientific_title": "## Modo Científico",
        "scientific_subtitle": "Resuelve problemas reales de ciencia e investigación con método y claridad",
        "scientific_desc": (
            "Aether te ayuda a estructurar investigaciones científicas, "
            "analizar métodos, definir modelos y explorar escenarios, "
            "para que tomes mejores decisiones antes de simular o experimentar."
        ),
        "scientific_chat_label": "Scientific Chat",
        "scientific_message_placeholder": "Describe tu consulta científica...",
        "config_title": "## Configuración",
        "config_account_title": "### Cuenta",
        "account_status_label": "Estado",
        "account_status_guest": "Invitado",
        "account_status_admin": "Admin",
        "username_label": "Usuario",
        "username_placeholder": "Tu usuario",
        "pin_label": "Pin / Código",
        "pin_placeholder": "Código de acceso",
        "login": "Login",
        "logout": "Cerrar sesión",
        "config_language_title": "### Idioma",
        "language_selector_label": "Selecciona idioma",
        "config_plans_title": "### Plan y precios",
        "plans_accordion_label": "Planes",
        "plan_free_text": (
            "### FREE — S/ 0\n"
            "**CREAR**\n"
            "- 1 proyecto activo\n"
            "- Guía paso a paso (idea → estructura → checklist)\n"
            "- Código base simple (cuando aplique)\n"
            "- Export MD (documento editable)\n\n"
            "**CIENTÍFICO**\n"
            "- Método científico guiado (problema → hipótesis → método)\n"
            "- Escenarios básicos\n"
            "- Conclusiones y limitaciones claras\n"
            "- Export MD (documento editable)\n\n"
            "**EXTRAS**\n"
            "- Chat y proyecto persistente\n"
            "- Interfaz simple y fácil de usar"
        ),
        "plan_pro_text": (
            "### PRO — S/ 49 (promo) → luego S/ 149\n"
            "**CREAR**\n"
            "- Hasta 5 proyectos\n"
            "- Plan más detallado (arquitectura, módulos, flujo)\n"
            "- Código base más completo\n"
            "- Export PDF + MD (documento editable)\n\n"
            "**CIENTÍFICO**\n"
            "- Escenarios comparativos\n"
            "- Análisis más profundo y ordenado\n"
            "- Mejor continuidad del proyecto\n"
            "- Export PDF + MD (documento editable)\n\n"
            "**EXTRAS**\n"
            "- Historial ampliado\n"
            "- Mejor organización de proyectos"
        ),
        "plan_lab_text": (
            "### LAB — S/ 299 (promo) → luego S/ 799\n"
            "**CREAR**\n"
            "- Proyectos ilimitados\n"
            "- Entregables completos (documentación, checklist, estructura para equipo)\n"
            "- Código base avanzado (cuando aplique)\n"
            "- Export avanzado (ZIP cuando aplique)\n\n"
            "**CIENTÍFICO**\n"
            "- Estudios completos y reproducibles\n"
            "- Escenarios complejos\n"
            "- Mayor rigor y trazabilidad\n"
            "- Export avanzado (cuando aplique)\n\n"
            "**EXTRAS**\n"
            "- Historial completo\n"
            "- Prioridad de recursos"
        ),
        "plan_upgrade": "Actualizar (próximamente)",
        "plan_footer": (
            "Aether te ayuda a pensar, analizar y crear con orden, "
            "para que continúes el trabajo en tu propio entorno."
        ),
    },
    "en": {
        "app_title": "AETHER CORE — HF SAFE",
        "header_beta": "Aether — Closed beta",
        "boot_label": "Boot",
        "new_chat": "New chat",
        "chats": "Chats",
        "chat_label": "Aether Chat",
        "message_label": "Message",
        "message_placeholder": "Describe what you want to do...",
        "send_chat": "Send (Chat)",
        "reload_modules": "Reload Modules",
        "export_demo1": "Export demo1",
        "refresh_status": "Refresh Status",
        "btn_builder": "🛠️ Build your Web / App",
        "btn_scientific": "🔬 Scientific",
        "admin_ops": "Advanced operations (Admin)",
        "task_queue_title": "### Task queue",
        "task_cmd_label": "Queue command",
        "task_cmd_placeholder": "e.g. review internal status",
        "priority_label": "Priority (1=high · 20=low)",
        "enqueue_task": "Enqueue Task (queue)",
        "orchestrator_title": "### v29 — Project Orchestrator",
        "project_name_label": "New project",
        "project_name_placeholder": "Project name",
        "create_project": "Create project",
        "project_label": "Project",
        "task_command_label": "New task (command)",
        "task_command_placeholder": "e.g. review internal status",
        "add_task": "Add task",
        "task_label": "Task",
        "run_task": "Run Task (policy/freeze)",
        "orchestrator_output": "Orchestrator output",
        "status_json": "Status JSON",
        "logs_last_n": "Logs last N",
        "tail_logs": "Tail Logs",
        "refresh_logs": "Refresh Logs",
        "export_demo1_label": "Export demo1",
        "snapshots_title": "### v28 — Snapshots (v28.3 includes plugins)",
        "snapshot_name_label": "Snapshot name",
        "create_snapshot": "Create Snapshot",
        "restore_snapshot": "Restore Snapshot",
        "list_snapshots": "List Snapshots",
        "export_snapshot": "Export Snapshot",
        "snapshot_output": "Snapshot output",
        "import_snapshot_json": "Import Snapshot JSON",
        "import_snapshot": "Import Snapshot",
        "replica_title": "### v28.2 — Portable replica (1 JSON)",
        "replica_name_label": "Replica name",
        "export_replica": "Export Replica (JSON)",
        "replica_json": "Replica JSON",
        "import_replica_json": "Import Replica JSON",
        "import_replica_apply": "Import Replica (apply)",
        "replica_import_result": "Replica import result",
        "home_button": "⬅️ Home",
        "builder_title": "## Build your Web / App / System",
        "builder_subtitle": "Design and structure projects in different technologies.",
        "builder_tags": "**Web · Mobile · Desktop · Embedded**  \n(Python · Java · C++ · JavaScript · Arduino · and more)",
        "builder_desc": (
            "Aether can help you design projects and generate starter code "
            "so you can test and continue development in your own environment."
        ),
        "project_id_label": "Project ID",
        "export_zip_label": "Export ZIP",
        "export_button": "Export",
        "builder_chat_label": "Builder Chat",
        "builder_message_placeholder": "Describe what you want to build...",
        "send_button": "Send",
        "scientific_title": "## Scientific Mode",
        "scientific_subtitle": "Solve real science and research problems with method and clarity",
        "scientific_desc": (
            "Aether helps you structure scientific research, analyze methods, define models, "
            "and explore scenarios so you can make better decisions before simulating or experimenting."
        ),
        "scientific_chat_label": "Scientific Chat",
        "scientific_message_placeholder": "Describe your scientific question...",
        "config_title": "## Settings",
        "config_account_title": "### Account",
        "account_status_label": "Status",
        "account_status_guest": "Guest",
        "account_status_admin": "Admin",
        "username_label": "User",
        "username_placeholder": "Your username",
        "pin_label": "PIN / Code",
        "pin_placeholder": "Access code",
        "login": "Login",
        "logout": "Log out",
        "config_language_title": "### Language",
        "language_selector_label": "Select language",
        "config_plans_title": "### Plans and pricing",
        "plans_accordion_label": "Plans",
        "plan_free_text": (
            "### FREE — S/ 0\n"
            "**BUILD**\n"
            "- 1 active project\n"
            "- Step-by-step guide (idea → structure → checklist)\n"
            "- Simple starter code (when applicable)\n"
            "- Export MD (editable document)\n\n"
            "**SCIENTIFIC**\n"
            "- Guided scientific method (problem → hypothesis → method)\n"
            "- Basic scenarios\n"
            "- Clear conclusions and limitations\n"
            "- Export MD (editable document)\n\n"
            "**EXTRAS**\n"
            "- Persistent chat and project\n"
            "- Simple, easy-to-use interface"
        ),
        "plan_pro_text": (
            "### PRO — S/ 49 (promo) → then S/ 149\n"
            "**BUILD**\n"
            "- Up to 5 projects\n"
            "- More detailed plan (architecture, modules, flow)\n"
            "- More complete starter code\n"
            "- Export PDF + MD (editable document)\n\n"
            "**SCIENTIFIC**\n"
            "- Comparative scenarios\n"
            "- Deeper, more organized analysis\n"
            "- Better project continuity\n"
            "- Export PDF + MD (editable document)\n\n"
            "**EXTRAS**\n"
            "- Expanded history\n"
            "- Better project organization"
        ),
        "plan_lab_text": (
            "### LAB — S/ 299 (promo) → then S/ 799\n"
            "**BUILD**\n"
            "- Unlimited projects\n"
            "- Full deliverables (documentation, checklist, team structure)\n"
            "- Advanced starter code (when applicable)\n"
            "- Advanced export (ZIP when applicable)\n\n"
            "**SCIENTIFIC**\n"
            "- Complete, reproducible studies\n"
            "- Complex scenarios\n"
            "- Greater rigor and traceability\n"
            "- Advanced export (when applicable)\n\n"
            "**EXTRAS**\n"
            "- Full history\n"
            "- Resource priority"
        ),
        "plan_upgrade": "Upgrade (coming soon)",
        "plan_footer": (
            "Aether helps you think, analyze, and create with order "
            "so you can continue your work in your own environment."
        ),
    },
    "pt-BR": {
        "app_title": "AETHER CORE — HF SAFE",
        "header_beta": "Aether — Beta fechada",
        "boot_label": "Boot",
        "new_chat": "Novo chat",
        "chats": "Chats",
        "chat_label": "Chat Aether",
        "message_label": "Mensagem",
        "message_placeholder": "Descreva o que você quer fazer...",
        "send_chat": "Enviar (Chat)",
        "reload_modules": "Recarregar módulos",
        "export_demo1": "Exportar demo1",
        "refresh_status": "Atualizar status",
        "btn_builder": "🛠️ Criar sua Web / App",
        "btn_scientific": "🔬 Científico",
        "admin_ops": "Operações avançadas (Admin)",
        "task_queue_title": "### Fila de tarefas",
        "task_cmd_label": "Comando da fila",
        "task_cmd_placeholder": "Ex: revisar status interno",
        "priority_label": "Prioridade (1=alta · 20=baixa)",
        "enqueue_task": "Enfileirar tarefa (fila)",
        "orchestrator_title": "### v29 — Orquestrador de Projetos",
        "project_name_label": "Novo projeto",
        "project_name_placeholder": "Nome do projeto",
        "create_project": "Criar projeto",
        "project_label": "Projeto",
        "task_command_label": "Nova tarefa (comando)",
        "task_command_placeholder": "Ex: revisar status interno",
        "add_task": "Adicionar tarefa",
        "task_label": "Tarefa",
        "run_task": "Executar tarefa (policy/freeze)",
        "orchestrator_output": "Saída do orquestrador",
        "status_json": "Status JSON",
        "logs_last_n": "Últimos logs N",
        "tail_logs": "Logs finais",
        "refresh_logs": "Atualizar logs",
        "export_demo1_label": "Exportar demo1",
        "snapshots_title": "### v28 — Snapshots (v28.3 inclui plugins)",
        "snapshot_name_label": "Nome do snapshot",
        "create_snapshot": "Criar Snapshot",
        "restore_snapshot": "Restaurar Snapshot",
        "list_snapshots": "Listar Snapshots",
        "export_snapshot": "Exportar Snapshot",
        "snapshot_output": "Saída do snapshot",
        "import_snapshot_json": "Importar Snapshot JSON",
        "import_snapshot": "Importar Snapshot",
        "replica_title": "### v28.2 — Réplica portátil (1 JSON)",
        "replica_name_label": "Nome da réplica",
        "export_replica": "Exportar réplica (JSON)",
        "replica_json": "Réplica JSON",
        "import_replica_json": "Importar réplica JSON",
        "import_replica_apply": "Importar réplica (aplicar)",
        "replica_import_result": "Resultado da importação",
        "home_button": "⬅️ Início",
        "builder_title": "## Criar sua Web / App / Sistema",
        "builder_subtitle": "Desenhe e estruture projetos em diferentes tecnologias.",
        "builder_tags": "**Web · Móvel · Desktop · Embarcados**  \n(Python · Java · C++ · JavaScript · Arduino · e mais)",
        "builder_desc": (
            "Aether pode ajudar você a desenhar projetos e gerar código base "
            "para testar e continuar o desenvolvimento no seu próprio ambiente."
        ),
        "project_id_label": "ID do projeto",
        "export_zip_label": "Exportar ZIP",
        "export_button": "Exportar",
        "builder_chat_label": "Chat Builder",
        "builder_message_placeholder": "Descreva o que você quer construir...",
        "send_button": "Enviar",
        "scientific_title": "## Modo Científico",
        "scientific_subtitle": "Resolva problemas reais de ciência e pesquisa com método e clareza",
        "scientific_desc": (
            "Aether ajuda você a estruturar pesquisas científicas, analisar métodos, "
            "definir modelos e explorar cenários para tomar melhores decisões antes "
            "de simular ou experimentar."
        ),
        "scientific_chat_label": "Chat Científico",
        "scientific_message_placeholder": "Descreva sua pergunta científica...",
        "config_title": "## Configurações",
        "config_account_title": "### Conta",
        "account_status_label": "Status",
        "account_status_guest": "Convidado",
        "account_status_admin": "Admin",
        "username_label": "Usuário",
        "username_placeholder": "Seu usuário",
        "pin_label": "PIN / Código",
        "pin_placeholder": "Código de acesso",
        "login": "Login",
        "logout": "Sair",
        "config_language_title": "### Idioma",
        "language_selector_label": "Selecionar idioma",
        "config_plans_title": "### Planos e preços",
        "plans_accordion_label": "Planos",
        "plan_free_text": (
            "### FREE — S/ 0\n"
            "**CRIAR**\n"
            "- 1 projeto ativo\n"
            "- Guia passo a passo (ideia → estrutura → checklist)\n"
            "- Código base simples (quando aplicável)\n"
            "- Exportar MD (documento editável)\n\n"
            "**CIENTÍFICO**\n"
            "- Método científico guiado (problema → hipótese → método)\n"
            "- Cenários básicos\n"
            "- Conclusões e limitações claras\n"
            "- Exportar MD (documento editável)\n\n"
            "**EXTRAS**\n"
            "- Chat e projeto persistente\n"
            "- Interface simples e fácil de usar"
        ),
        "plan_pro_text": (
            "### PRO — S/ 49 (promo) → depois S/ 149\n"
            "**CRIAR**\n"
            "- Até 5 projetos\n"
            "- Plano mais detalhado (arquitetura, módulos, fluxo)\n"
            "- Código base mais completo\n"
            "- Exportar PDF + MD (documento editável)\n\n"
            "**CIENTÍFICO**\n"
            "- Cenários comparativos\n"
            "- Análise mais profunda e organizada\n"
            "- Melhor continuidade do projeto\n"
            "- Exportar PDF + MD (documento editável)\n\n"
            "**EXTRAS**\n"
            "- Histórico ampliado\n"
            "- Melhor organização de projetos"
        ),
        "plan_lab_text": (
            "### LAB — S/ 299 (promo) → depois S/ 799\n"
            "**CRIAR**\n"
            "- Projetos ilimitados\n"
            "- Entregáveis completos (documentação, checklist, estrutura para equipe)\n"
            "- Código base avançado (quando aplicável)\n"
            "- Exportação avançada (ZIP quando aplicável)\n\n"
            "**CIENTÍFICO**\n"
            "- Estudos completos e reproduzíveis\n"
            "- Cenários complexos\n"
            "- Maior rigor e rastreabilidade\n"
            "- Exportação avançada (quando aplicável)\n\n"
            "**EXTRAS**\n"
            "- Histórico completo\n"
            "- Prioridade de recursos"
        ),
        "plan_upgrade": "Atualizar (em breve)",
        "plan_footer": (
            "Aether ajuda você a pensar, analisar e criar com ordem "
            "para continuar o trabalho no seu próprio ambiente."
        ),
    },
    "pt-PT": {
        "app_title": "AETHER CORE — HF SAFE",
        "header_beta": "Aether — Beta fechada",
        "boot_label": "Boot",
        "new_chat": "Novo chat",
        "chats": "Chats",
        "chat_label": "Chat Aether",
        "message_label": "Mensagem",
        "message_placeholder": "Descreve o que queres fazer...",
        "send_chat": "Enviar (Chat)",
        "reload_modules": "Recarregar módulos",
        "export_demo1": "Exportar demo1",
        "refresh_status": "Atualizar estado",
        "btn_builder": "🛠️ Criar a tua Web / App",
        "btn_scientific": "🔬 Científico",
        "admin_ops": "Operações avançadas (Admin)",
        "task_queue_title": "### Fila de tarefas",
        "task_cmd_label": "Comando da fila",
        "task_cmd_placeholder": "Ex: rever estado interno",
        "priority_label": "Prioridade (1=alta · 20=baixa)",
        "enqueue_task": "Enfileirar tarefa (fila)",
        "orchestrator_title": "### v29 — Orquestrador de Projetos",
        "project_name_label": "Novo projeto",
        "project_name_placeholder": "Nome do projeto",
        "create_project": "Criar projeto",
        "project_label": "Projeto",
        "task_command_label": "Nova tarefa (comando)",
        "task_command_placeholder": "Ex: rever estado interno",
        "add_task": "Adicionar tarefa",
        "task_label": "Tarefa",
        "run_task": "Executar tarefa (policy/freeze)",
        "orchestrator_output": "Saída do orquestrador",
        "status_json": "Status JSON",
        "logs_last_n": "Últimos logs N",
        "tail_logs": "Logs finais",
        "refresh_logs": "Atualizar logs",
        "export_demo1_label": "Exportar demo1",
        "snapshots_title": "### v28 — Snapshots (v28.3 inclui plugins)",
        "snapshot_name_label": "Nome do snapshot",
        "create_snapshot": "Criar Snapshot",
        "restore_snapshot": "Restaurar Snapshot",
        "list_snapshots": "Listar Snapshots",
        "export_snapshot": "Exportar Snapshot",
        "snapshot_output": "Saída do snapshot",
        "import_snapshot_json": "Importar Snapshot JSON",
        "import_snapshot": "Importar Snapshot",
        "replica_title": "### v28.2 — Réplica portátil (1 JSON)",
        "replica_name_label": "Nome da réplica",
        "export_replica": "Exportar réplica (JSON)",
        "replica_json": "Réplica JSON",
        "import_replica_json": "Importar réplica JSON",
        "import_replica_apply": "Importar réplica (aplicar)",
        "replica_import_result": "Resultado da importação",
        "home_button": "⬅️ Início",
        "builder_title": "## Criar a tua Web / App / Sistema",
        "builder_subtitle": "Desenha e estrutura projetos em diferentes tecnologias.",
        "builder_tags": "**Web · Móvel · Desktop · Embarcados**  \n(Python · Java · C++ · JavaScript · Arduino · e mais)",
        "builder_desc": (
            "Aether pode ajudar-te a desenhar projetos e gerar código base "
            "para testares e continuares o desenvolvimento no teu próprio ambiente."
        ),
        "project_id_label": "ID do projeto",
        "export_zip_label": "Exportar ZIP",
        "export_button": "Exportar",
        "builder_chat_label": "Chat Builder",
        "builder_message_placeholder": "Descreve o que queres construir...",
        "send_button": "Enviar",
        "scientific_title": "## Modo Científico",
        "scientific_subtitle": "Resolve problemas reais de ciência e investigação com método e clareza",
        "scientific_desc": (
            "Aether ajuda-te a estruturar investigações científicas, analisar métodos, "
            "definir modelos e explorar cenários para tomares melhores decisões antes "
            "de simular ou experimentar."
        ),
        "scientific_chat_label": "Chat Científico",
        "scientific_message_placeholder": "Descreve a tua questão científica...",
        "config_title": "## Configurações",
        "config_account_title": "### Conta",
        "account_status_label": "Estado",
        "account_status_guest": "Convidado",
        "account_status_admin": "Admin",
        "username_label": "Utilizador",
        "username_placeholder": "O teu utilizador",
        "pin_label": "PIN / Código",
        "pin_placeholder": "Código de acesso",
        "login": "Login",
        "logout": "Terminar sessão",
        "config_language_title": "### Idioma",
        "language_selector_label": "Selecionar idioma",
        "config_plans_title": "### Planos e preços",
        "plans_accordion_label": "Planos",
        "plan_free_text": (
            "### FREE — S/ 0\n"
            "**CRIAR**\n"
            "- 1 projeto ativo\n"
            "- Guia passo a passo (ideia → estrutura → checklist)\n"
            "- Código base simples (quando aplicável)\n"
            "- Exportar MD (documento editável)\n\n"
            "**CIENTÍFICO**\n"
            "- Método científico guiado (problema → hipótese → método)\n"
            "- Cenários básicos\n"
            "- Conclusões e limitações claras\n"
            "- Exportar MD (documento editável)\n\n"
            "**EXTRAS**\n"
            "- Chat e projeto persistente\n"
            "- Interface simples e fácil de usar"
        ),
        "plan_pro_text": (
            "### PRO — S/ 49 (promo) → depois S/ 149\n"
            "**CRIAR**\n"
            "- Até 5 projetos\n"
            "- Plano mais detalhado (arquitetura, módulos, fluxo)\n"
            "- Código base mais completo\n"
            "- Exportar PDF + MD (documento editável)\n\n"
            "**CIENTÍFICO**\n"
            "- Cenários comparativos\n"
            "- Análise mais profunda e organizada\n"
            "- Melhor continuidade do projeto\n"
            "- Exportar PDF + MD (documento editável)\n\n"
            "**EXTRAS**\n"
            "- Histórico ampliado\n"
            "- Melhor organização de projetos"
        ),
        "plan_lab_text": (
            "### LAB — S/ 299 (promo) → depois S/ 799\n"
            "**CRIAR**\n"
            "- Projetos ilimitados\n"
            "- Entregáveis completos (documentação, checklist, estrutura para equipa)\n"
            "- Código base avançado (quando aplicável)\n"
            "- Exportação avançada (ZIP quando aplicável)\n\n"
            "**CIENTÍFICO**\n"
            "- Estudos completos e reproduzíveis\n"
            "- Cenários complexos\n"
            "- Maior rigor e rastreabilidade\n"
            "- Exportação avançada (quando aplicável)\n\n"
            "**EXTRAS**\n"
            "- Histórico completo\n"
            "- Prioridade de recursos"
        ),
        "plan_upgrade": "Atualizar (em breve)",
        "plan_footer": (
            "Aether ajuda-te a pensar, analisar e criar com ordem "
            "para continuares o trabalho no teu próprio ambiente."
        ),
    },
}


def normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return "es"
    norm = str(lang).replace("_", "-").strip()
    lower = norm.lower()
    if lower.startswith("es"):
        return "es"
    if lower.startswith("en"):
        return "en"
    if lower.startswith("pt-br"):
        return "pt-BR"
    if lower.startswith("pt-pt"):
        return "pt-PT"
    if lower.startswith("pt"):
        return "pt-BR"
    return "es"


def detect_language_from_header(accept_language: Optional[str]) -> str:
    if not accept_language:
        return "es"
    for part in accept_language.split(","):
        code = part.split(";")[0].strip()
        if not code:
            continue
        normalized = normalize_lang(code)
        if normalized in SUPPORTED_LANGS:
            return normalized
    return "es"


def t(lang: str, key: str) -> str:
    resolved = normalize_lang(lang)
    return LANG.get(resolved, LANG["es"]).get(key, LANG["es"].get(key, key))

# -----------------------------
# TIME (timezone-aware)
# -----------------------------

def safe_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# -----------------------------
# ENV HELPERS
# -----------------------------

def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    v = str(raw).strip().lower()
    if v in {"1", "true", "yes", "y", "on", "t"}:
        return True
    if v in {"0", "false", "no", "n", "off", "f"}:
        return False
    return bool(default)

def sha256_text(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

ALLOW_NETWORK = (os.environ.get("AETHER_ALLOW_NETWORK", "1") == "1") and not os.environ.get(
    "AETHER_SANDBOX_DIR"
)

def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MODULES_DIR, exist_ok=True)
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# -----------------------------
# PATHS (HF-safe)
# -----------------------------
DATA_DIR = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
UI_DATA_DIR = "/tmp/aether_ui"

MODULES_DIR = "plugins"

SNAPSHOT_DIR = os.path.join(DATA_DIR, "snapshots")
SNAPSHOT_INDEX_FILE = os.path.join(SNAPSHOT_DIR, "index.json")

# -----------------------------
# VERSION + FILES
# -----------------------------
AETHER_VERSION = "3.10.0-hf-v39-stable"
APP_VERSION = AETHER_VERSION

STATE_FILE = os.path.join(DATA_DIR, "aether_state.json")
MEMORY_FILE = os.path.join(DATA_DIR, "aether_memory.json")
STRATEGIC_FILE = os.path.join(DATA_DIR, "aether_strategic.json")
LOG_FILE = os.path.join(DATA_DIR, "aether_log.json")
DASHBOARD_FILE = os.path.join(DATA_DIR, "aether_dashboard.json")
EVENTS_LOG_FILE = os.path.join(DATA_DIR, "events.log")

DEMO1_FILE = os.path.join(DATA_DIR, "demo1.json")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

# -----------------------------
# LIMITS
# -----------------------------
MAX_MEMORY_ENTRIES = 500
MAX_LOG_ENTRIES = 1000
MAX_STRATEGY_HISTORY = 1000
MAX_DEDUP_KEYS = 5000

# -----------------------------
# EVENTS LOG
# -----------------------------
AETHER_EVENTS_LOG_MAX_BYTES = int(os.environ.get("AETHER_EVENTS_LOG_MAX_BYTES", "1000000"))

# -----------------------------
# HEARTBEAT / RUNNER CONFIG
# -----------------------------
HEARTBEAT_CMD = "revisar estado interno"
HEARTBEAT_INTERVAL_SEC = int(os.environ.get("AETHER_HEARTBEAT_SEC", "120"))
HEARTBEAT_MIN_ENERGY = int(os.environ.get("AETHER_HEARTBEAT_MIN_ENERGY", "40"))
AETHER_HEARTBEAT_ENABLED = env_bool("AETHER_HEARTBEAT_ENABLED", True)

AETHER_TASK_RUNNER_ENABLED = env_bool("AETHER_TASK_RUNNER_ENABLED", True)
AETHER_TASK_MAX_RETRIES = int(os.environ.get("AETHER_TASK_MAX_RETRIES", "2"))
AETHER_TASK_BUDGET = int(os.environ.get("AETHER_TASK_BUDGET", "3"))
AETHER_TASK_TIMEOUT_SEC = int(os.environ.get("AETHER_TASK_TIMEOUT_SEC", "20"))
AETHER_TASK_BUDGET_MAX = int(os.environ.get("AETHER_TASK_BUDGET_MAX", str(max(1, int(AETHER_TASK_BUDGET)))))

# -----------------------------
# INTERNAL TASKS (v43)
# -----------------------------
AETHER_INTERNAL_TASK_INTERVAL_SEC = int(os.environ.get("AETHER_INTERNAL_TASK_INTERVAL_SEC", "180"))
AETHER_INTERNAL_TASK_BUDGET = int(os.environ.get("AETHER_INTERNAL_TASK_BUDGET", "1"))

# -----------------------------
# TASK SECURITY (v40-v42)
# -----------------------------
AETHER_TASK_SECRET = os.environ.get("AETHER_TASK_SECRET", "")

PERMISSIONS = {
    "read_only": {"manual": True, "auto": True},
    "analysis": {"manual": True, "auto": True},
    "write_state": {"manual": True, "auto": False},
    "io_export": {"manual": True, "auto": False},
    "system": {"manual": False, "auto": False},
}

_SIGNATURE_WARNED = False

# -----------------------------
# TRUST ZONES (v48)
# -----------------------------
TRUST_ZONES = {"UI", "CHAT", "INTERNAL", "ORCH"}
TRUST_ZONE_DEFAULT = "CHAT"
TRUST_ZONE_BLOCK_WINDOW = 50
OWNER_ONLY_SPECIALS = {"reload_plugins", "snapshot_create", "snapshot_export", "snapshot_import", "snapshot_restore"}

# Policy matrix (explicit allowlist, default deny).
# How to test (manual):
# - Try "reload plugins" in chat -> must be blocked.
# - Try "snapshot restore demo1" in chat -> blocked.
# - Try same actions from UI buttons -> allowed only where explicitly permitted.
# - Verify logs show TRUST_ZONE_* events.
# - Verify heartbeat internal tasks still run read_only.
TRUST_ZONE_POLICIES = {
    "UI": {
        "task_types": {"read_only", "analysis", "write_state", "io_export"},
        "special": {"reload_plugins", "snapshot_restore", "snapshot_import", "snapshot_export", "snapshot_create"},
    },
    "CHAT": {
        "task_types": {"read_only", "analysis"},
        "special": set(),
    },
    "INTERNAL": {
        "task_types": {"read_only"},
        "special": set(),
    },
    "ORCH": {
        "task_types": {"read_only", "analysis", "write_state", "io_export"},
        "special": set(),
    },
}

def resolve_zone(source: str, origin: Optional[str]) -> str:
    src = (source or "").strip().lower()
    org = (origin or "").strip().lower()
    if org in {"run_project_task", "orchestrator"} or src == "orchestrator":
        return "ORCH"
    if src == "internal" or org.startswith("scheduler"):
        return "INTERNAL"
    if src == "ui" or org.startswith("ui_"):
        return "UI"
    if src == "chat" or org.startswith("chat_"):
        return "CHAT"
    if src == "external":
        return "CHAT"
    return TRUST_ZONE_DEFAULT

def _detect_special_commands(command: str) -> List[str]:
    cmd = (command or "").lower()
    specials = set()
    if "reload" in cmd and "plugin" in cmd:
        specials.add("reload_plugins")
    if "snapshot restore" in cmd or ("snapshot" in cmd and "restore" in cmd):
        specials.add("snapshot_restore")
    if "snapshot import" in cmd or ("snapshot" in cmd and "import" in cmd):
        specials.add("snapshot_import")
    if "snapshot export" in cmd or ("snapshot" in cmd and "export" in cmd):
        specials.add("snapshot_export")
    if "snapshot create" in cmd or ("snapshot" in cmd and "create" in cmd):
        specials.add("snapshot_create")
    if "replica apply" in cmd:
        specials.add("replica_apply")
    if "replica import" in cmd:
        specials.add("replica_import")
    return sorted(specials)

def _parse_owner_prefix(text: str) -> Tuple[bool, str, bool]:
    owner_key = os.environ.get("AETHER_OWNER_KEY", "").strip()
    raw = (text or "")
    if not raw.startswith("owner:"):
        return False, text, False
    remainder = raw[len("owner:") :]
    if " " in remainder:
        key, rest = remainder.split(" ", 1)
    else:
        key, rest = remainder, ""
    key = key.strip()
    rest = rest.lstrip()
    if not owner_key or key != owner_key:
        return False, rest, True
    return True, rest, True

def _owner_only_gate(command: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    is_owner, stripped, had_prefix = _parse_owner_prefix(command)
    inspect_command = stripped if had_prefix else command
    specials = _detect_special_commands(inspect_command)
    needs_owner = any(special in OWNER_ONLY_SPECIALS for special in specials)
    if not needs_owner:
        if is_owner and had_prefix:
            return True, stripped, None
        return True, command, None
    if not is_owner:
        return False, command, {"ok": False, "error": "owner-only: blocked", "hint": "use owner:<KEY> <cmd>"}
    return True, stripped, None

def _trust_zone_allowed(zone: str, task_type: str, command: str) -> Tuple[bool, str, List[str]]:
    if zone not in TRUST_ZONES:
        return False, "invalid_zone", []
    policy = TRUST_ZONE_POLICIES.get(zone) or {}
    allowed_types = policy.get("task_types") or set()
    allowed_special = policy.get("special") or set()
    specials = _detect_special_commands(command)

    if task_type == "system":
        return False, "system_blocked", specials
    if task_type not in allowed_types:
        return False, "task_type_blocked", specials
    if specials:
        for special in specials:
            if special not in allowed_special:
                return False, f"special_blocked:{special}", specials
    return True, "", specials

def _summarize_trust_zone_blocks() -> Dict[str, Any]:
    counts = {z: 0 for z in TRUST_ZONES}
    total = 0
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        if total >= TRUST_ZONE_BLOCK_WINDOW:
            break
        if entry.get("type") not in {"TRUST_ZONE_BLOCK_ENQUEUE", "TRUST_ZONE_BLOCK_EXEC"}:
            continue
        info = entry.get("info", {})
        zone = info.get("zone")
        if zone in counts:
            counts[zone] += 1
        total += 1
    return {"window": TRUST_ZONE_BLOCK_WINDOW, "total": total, "by_zone": counts}

def _trust_zone_policy_snapshot() -> Dict[str, Any]:
    snap: Dict[str, Any] = {}
    for zone, policy in TRUST_ZONE_POLICIES.items():
        snap[zone] = {
            "task_types": sorted(policy.get("task_types") or []),
            "special": sorted(policy.get("special") or []),
        }
    return snap

def _collect_recent_errors(max_items: int = 8) -> List[Dict[str, Any]]:
    # Deterministic error sampling: newest-first with fixed cap, no side effects.
    recent: List[Dict[str, Any]] = []
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        if len(recent) >= max_items:
            break
        if entry.get("type") in THROTTLE_ERROR_TYPES:
            recent.append(entry)
    return recent

def _collect_recent_trust_zone_blocks(max_items: int = 8) -> List[Dict[str, Any]]:
    recent: List[Dict[str, Any]] = []
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        if len(recent) >= max_items:
            break
        if entry.get("type") in {"TRUST_ZONE_BLOCK_ENQUEUE", "TRUST_ZONE_BLOCK_EXEC"}:
            recent.append(entry)
    return recent

def diagnose_system() -> Dict[str, Any]:
    # Deterministic, side-effect-free diagnosis based only on in-memory state.
    issues: List[Dict[str, Any]] = []
    evidence: List[str]

    with state_lock:
        state_snapshot = dict(AETHER_STATE)
    with throttle_lock:
        throttle_snapshot = dict(THROTTLE_STATE)

    safe_mode = dict(SAFE_MODE)
    freeze_state = dict(FREEZE_STATE)
    queue_size = int(TASK_QUEUE.qsize())
    energy = int(state_snapshot.get("energy", 0))
    last_cycle = state_snapshot.get("last_cycle")
    now_ts = time.time()
    last_cycle_ts = _parse_iso_ts(last_cycle)
    watchdog_limit = max(0, int(AETHER_WATCHDOG_SEC))
    watchdog_grace = max(0, int(AETHER_WATCHDOG_GRACE_SEC))

    # SAFE_MODE classification: distinguish env-enabled vs. runtime triggers.
    if safe_mode.get("enabled"):
        reason = safe_mode.get("reason") or "unknown"
        category = "SAFE_MODE_ENV" if reason == "ENV_ENABLED" else "UNKNOWN"
        severity = "WARN" if category == "SAFE_MODE_ENV" else "CRITICAL"
        evidence = [f"safe_mode_enabled={safe_mode.get('enabled')}", f"reason={reason}"]
        issues.append(
            {
                "category": category,
                "severity": severity,
                "evidence": evidence,
                "recommended_action": "Review SAFE_MODE reason and disable only after resolving root cause.",
            }
        )

    # Manual freeze classification based on FREEZE_STATE.
    if freeze_state.get("enabled"):
        evidence = [f"freeze_enabled={freeze_state.get('enabled')}", f"since={freeze_state.get('since')}"]
        issues.append(
            {
                "category": "MANUAL_FREEZE",
                "severity": "WARN",
                "evidence": evidence,
                "recommended_action": "Unset AETHER_FREEZE_MODE to resume normal execution.",
            }
        )

    # Watchdog stall detection uses last_cycle timestamps and watchdog config.
    if watchdog_limit > 0 and last_cycle_ts is not None:
        elapsed = now_ts - last_cycle_ts
        if elapsed >= (watchdog_limit + watchdog_grace):
            evidence = [
                f"elapsed_since_last_cycle_sec={round(elapsed, 2)}",
                f"watchdog_limit_sec={watchdog_limit}",
                f"watchdog_grace_sec={watchdog_grace}",
            ]
            issues.append(
                {
                    "category": "WATCHDOG_STALL",
                    "severity": "CRITICAL",
                    "evidence": evidence,
                    "recommended_action": "Inspect worker/scheduler loops and logs for stalls.",
                }
            )

    # Throttle health and resource pressure assessment.
    throttle_mode = throttle_snapshot.get("mode")
    throttle_score = float(throttle_snapshot.get("score", 1.0) or 0.0)
    if throttle_mode in {"throttled", "burst"} or throttle_score < 0.6:
        evidence = [
            f"throttle_mode={throttle_mode}",
            f"throttle_score={round(throttle_score, 3)}",
            f"queue_size={queue_size}",
            f"energy={energy}",
        ]
        issues.append(
            {
                "category": "RESOURCE_EXHAUSTION",
                "severity": "WARN",
                "evidence": evidence,
                "recommended_action": "Reduce load or wait for throttle recovery.",
            }
        )

    # Trust zone violations from recent logs.
    tz_blocks = _collect_recent_trust_zone_blocks()
    if tz_blocks:
        evidence = [f"trust_zone_blocks_recent={len(tz_blocks)}"]
        issues.append(
            {
                "category": "TRUST_ZONE_VIOLATION",
                "severity": "WARN",
                "evidence": evidence,
                "recommended_action": "Validate zone/origin metadata and policy allowlists.",
            }
        )

    # Policy violations inferred from permission denials.
    policy_denied = 0
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        if entry.get("type") == "TASK_PERMISSION_DENIED":
            policy_denied += 1
            if policy_denied >= 3:
                break
    if policy_denied:
        issues.append(
            {
                "category": "POLICY_VIOLATION",
                "severity": "WARN",
                "evidence": [f"permission_denied_recent={policy_denied}"],
                "recommended_action": "Review task_type permissions and caller mode.",
            }
        )

    # Task timeouts and IO instability signals.
    timeout_count = 0
    io_errors = 0
    for entry in reversed(entries):
        etype = entry.get("type")
        if etype == "TASK_TIMEOUT":
            timeout_count += 1
        if etype == "JSON_WRITE_ERROR":
            io_errors += 1
        if timeout_count >= 3 and io_errors >= 3:
            break
    if timeout_count:
        issues.append(
            {
                "category": "TASK_TIMEOUTS",
                "severity": "WARN",
                "evidence": [f"task_timeouts_recent={timeout_count}"],
                "recommended_action": "Increase timeout or reduce workload complexity.",
            }
        )
    if io_errors:
        issues.append(
            {
                "category": "IO_INSTABILITY",
                "severity": "WARN",
                "evidence": [f"io_write_errors_recent={io_errors}"],
                "recommended_action": "Check filesystem health and storage capacity.",
            }
        )

    if not issues:
        issues.append(
            {
                "category": "UNKNOWN",
                "severity": "INFO",
                "evidence": ["no_anomalies_detected"],
                "recommended_action": "Monitor system status and logs for changes.",
            }
        )

    # Deterministic ordering by category for stable output.
    issues_sorted = sorted(issues, key=lambda item: item.get("category", ""))
    return {
        "timestamp": safe_now(),
        "state": {
            "status": state_snapshot.get("status"),
            "energy": energy,
            "queue_size": queue_size,
            "last_cycle": last_cycle,
        },
        "safe_mode": safe_mode,
        "freeze": freeze_state,
        "watchdog": {
            "watchdog_sec": int(AETHER_WATCHDOG_SEC),
            "watchdog_grace_sec": int(AETHER_WATCHDOG_GRACE_SEC),
            "last_cycle": last_cycle,
        },
        "throttle": {
            "mode": throttle_snapshot.get("mode"),
            "score": throttle_snapshot.get("score"),
            "reasons": throttle_snapshot.get("reasons"),
        },
        "recent_errors": _collect_recent_errors(),
        "recent_trust_zone_blocks": tz_blocks,
        "issues": issues_sorted,
    }

def get_self_diagnosis() -> Dict[str, Any]:
    # Wrapper to allow future expansion without changing callers.
    return diagnose_system()

def _diagnosis_summary(diagnosis: Dict[str, Any]) -> Dict[str, Any]:
    issues = diagnosis.get("issues") if isinstance(diagnosis, dict) else []
    categories = []
    severity_rank = {"INFO": 0, "WARN": 1, "CRITICAL": 2}
    max_sev = 0
    if isinstance(issues, list):
        for issue in issues:
            category = issue.get("category")
            if isinstance(category, str) and category not in categories:
                categories.append(category)
            sev = severity_rank.get(issue.get("severity", "INFO"), 0)
            max_sev = max(max_sev, sev)
    overall = "OK" if max_sev == 0 else ("DEGRADED" if max_sev == 1 else "CRITICAL")
    return {"overall_health": overall, "top_issues": categories[:5], "last_updated": safe_now()}

# -----------------------------
# STABILITY CONTROLLER (v50)
# -----------------------------
STABILITY_STATE = {"mode": "NORMAL", "since": safe_now(), "reasons": []}

def _recent_recovery_count(max_items: int = 10) -> int:
    count = 0
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        if count >= max_items:
            break
        if entry.get("type") == "RECOVERY_EVENT":
            count += 1
    return count

def evaluate_stability() -> Dict[str, Any]:
    # Conservative evaluation: prefer safety over throughput; no side effects.
    diagnosis = get_self_diagnosis()
    summary = _diagnosis_summary(diagnosis)
    overall_health = summary.get("overall_health")
    reasons = summary.get("top_issues") if isinstance(summary, dict) else []
    recovery_count = _recent_recovery_count()
    with throttle_lock:
        throttle_mode = THROTTLE_STATE.get("mode")

    if safe_mode_enabled() or is_frozen():
        mode = "PAUSED"
        reason_list = ["SAFE_MODE" if safe_mode_enabled() else "FROZEN"]
        action = "Pause external execution; internal maintenance only."
    elif overall_health == "CRITICAL" and recovery_count >= 2:
        mode = "NEEDS_HUMAN"
        reason_list = list(reasons) + ["RECOVERY_REPEAT"]
        action = "Request human intervention; block execution until reviewed."
    elif "RESOURCE_EXHAUSTION" in (reasons or []) or (throttle_mode in {"throttled", "burst"}):
        mode = "DEGRADED"
        reason_list = list(reasons) or ["THROTTLED"]
        action = "Degrade to read-only/planner; avoid state mutations."
    else:
        mode = "NORMAL"
        reason_list = list(reasons)
        action = "Operate normally."

    current = STABILITY_STATE.get("mode")
    if current != mode:
        STABILITY_STATE["mode"] = mode
        STABILITY_STATE["since"] = safe_now()
        STABILITY_STATE["reasons"] = reason_list
        log_event("STABILITY_MODE_CHANGE", {"mode": mode, "reasons": reason_list})
    return {"mode": mode, "reasons": reason_list, "recommended_action": action, "since": STABILITY_STATE.get("since")}

# -----------------------------
# SAFE MODE + WATCHDOG
# -----------------------------
AETHER_SAFE_MODE_ENABLED = env_bool("AETHER_SAFE_MODE_ENABLED", True)
AETHER_WATCHDOG_SEC = int(os.environ.get("AETHER_WATCHDOG_SEC", "180"))
AETHER_WATCHDOG_GRACE_SEC = int(os.environ.get("AETHER_WATCHDOG_GRACE_SEC", "30"))

SAFE_MODE = {
    "enabled": bool(AETHER_SAFE_MODE_ENABLED),
    "since": safe_now() if AETHER_SAFE_MODE_ENABLED else None,
    "reason": "ENV_ENABLED" if AETHER_SAFE_MODE_ENABLED else "",
}
SAFE_MODE_LOGGED = False

# -----------------------------
# FREEZE + POLICY
# -----------------------------
AETHER_FREEZE_MODE = env_bool("AETHER_FREEZE_MODE", True)
AETHER_ORCHESTRATOR_ALLOW_RUN = env_bool("AETHER_ORCHESTRATOR_ALLOW_RUN", True)

ROOT_GOAL = "EXECUTE_USER_COMMANDS_ONLY"
KILL_SWITCH = {"enabled": True, "status": "ARMED"}

FREEZE_STATE = {"enabled": bool(AETHER_FREEZE_MODE), "since": safe_now() if AETHER_FREEZE_MODE else None}

def is_frozen() -> bool:
    return bool(FREEZE_STATE.get("enabled"))

ORCHESTRATOR_POLICY = {"allow_run": bool(AETHER_ORCHESTRATOR_ALLOW_RUN)}

# -----------------------------
# LOCKS
# -----------------------------
memory_lock = threading.Lock()
log_lock = threading.Lock()
state_lock = threading.Lock()
strategic_lock = threading.Lock()
modules_lock = threading.Lock()
dedup_lock = threading.Lock()
queue_lock = threading.Lock()
projects_lock = threading.Lock()
tasks_lock = threading.Lock()
snap_lock = threading.Lock()
events_log_lock = threading.Lock()
throttle_lock = threading.Lock()

# -----------------------------
# JSON IO (atomic)
# -----------------------------

IO_BACKOFF_THRESHOLD = 3
IO_BACKOFF_BASE_SEC = 0.25
IO_BACKOFF_MAX_SEC = 5.0
IO_WRITE_COALESCE_DELAY_SEC = 0.0

_path_state_lock = threading.Lock()
_path_states: Dict[str, Dict[str, Any]] = {}

def _get_path_state(path: str) -> Dict[str, Any]:
    abs_path = os.path.abspath(path)
    with _path_state_lock:
        state = _path_states.get(abs_path)
        if state is None:
            state = {
                "lock": threading.Lock(),
                "in_progress": False,
                "pending_data": None,
                "fail_count": 0,
                "backoff_until": 0.0,
            }
            _path_states[abs_path] = state
        return state

def load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read().strip()
            if not txt:
                return default
            return json.loads(txt)
    except Exception:
        return default

def safe_json_load(path: str, default: Any = None) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return default
        return json.loads(raw)
    except Exception:
        return default

def save_json_atomic(path: str, data: Any) -> bool:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)

    base = os.path.basename(path)
    tmp = os.path.join(d, f".{base}.{uuid.uuid4().hex}.tmp")
    state = _get_path_state(path)

    with state["lock"]:
        if state["in_progress"]:
            # Prefer last-writer-wins to avoid overlapping writes from threads.
            state["pending_data"] = data
            return True
        state["in_progress"] = True

    def _write_once(payload: Any) -> bool:
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp, path)
            return True
        except Exception as e:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            # Evitar recursión si falla el LOG_FILE
            if "LOG_FILE" in globals() and path != LOG_FILE and "log_event" in globals():
                try:
                    log_event("JSON_WRITE_ERROR", {"file": path, "error": str(e)})
                except Exception:
                    pass
            return False

    payload = data
    ok = True
    while True:
        now_ts = time.time()
        with state["lock"]:
            backoff_until = float(state.get("backoff_until") or 0.0)
        if backoff_until and now_ts < backoff_until:
            time.sleep(max(0.0, backoff_until - now_ts))

        ok = _write_once(payload)
        with state["lock"]:
            if ok:
                state["fail_count"] = 0
                state["backoff_until"] = 0.0
            else:
                state["fail_count"] = int(state.get("fail_count", 0)) + 1
                if state["fail_count"] >= IO_BACKOFF_THRESHOLD:
                    backoff = min(IO_BACKOFF_MAX_SEC, IO_BACKOFF_BASE_SEC * (2 ** (state["fail_count"] - IO_BACKOFF_THRESHOLD)))
                    state["backoff_until"] = time.time() + backoff
                    if "LOG_FILE" in globals() and path != LOG_FILE and "log_event" in globals():
                        try:
                            log_event(
                                "IO_BACKOFF_TRIGGERED",
                                {"file": path, "attempts": state["fail_count"], "backoff_sec": backoff},
                            )
                        except Exception:
                            pass
            pending = state.get("pending_data")
            if pending is None:
                state["in_progress"] = False
                break
            # Only keep the latest queued payload to avoid redundant writes.
            state["pending_data"] = None
            payload = pending
        if IO_WRITE_COALESCE_DELAY_SEC > 0:
            time.sleep(IO_WRITE_COALESCE_DELAY_SEC)
    return ok

# -----------------------------
# INITIAL STATE
# -----------------------------
DEFAULT_STATE: Dict[str, Any] = {
    "id": "AETHER",
    "version": AETHER_VERSION,
    "status": "IDLE",
    "energy": 100,
    "focus": "STANDBY",
    "created_at": safe_now(),
    "last_cycle": None,
    "last_heartbeat_ts": None,
    "last_internal_task_ts": None,
    "last_stable_snapshot": None,
}

_STATE_INITIALIZED = False

AETHER_STATE: Dict[str, Any] = dict(DEFAULT_STATE)
AETHER_MEMORY: List[Dict[str, Any]] = []
STRATEGIC_MEMORY: Dict[str, Any] = {"patterns": {}, "failures": {}, "history": [], "last_update": None}
AETHER_LOGS: List[Dict[str, Any]] = []

# -----------------------------
# ADAPTIVE THROTTLING (v47)
# -----------------------------
# Policy: compute a lightweight health score from recent errors, queue pressure,
# energy, and safety flags. Apply conservative scaling with hysteresis and cooldown
# to avoid oscillations. No new threads; called inside existing loops.
THROTTLE_ERROR_WINDOW_SEC = 90
THROTTLE_BURST_WINDOW_SEC = 30
THROTTLE_BURST_COUNT = 3
THROTTLE_DOWN_THRESHOLD = 0.5
THROTTLE_UP_THRESHOLD = 0.75
THROTTLE_STABLE_SEC = 30
THROTTLE_COOLDOWN_SEC = 15
THROTTLE_STATE_LOG_SEC = 60

THROTTLE_ERROR_TYPES = {
    "WORKER_ERROR",
    "SCHEDULER_ERROR",
    "MODULE_RUN_ERROR",
    "JSON_WRITE_ERROR",
    "TASK_TIMEOUT",
}

BASE_WORKER_TICK_SEC = 0.25
BASE_SCHED_SLEEP_SEC = 2.0
WORKER_TICK_MIN_SEC = 0.1
WORKER_TICK_MAX_SEC = 2.5
SCHED_SLEEP_MIN_SEC = 0.5
SCHED_SLEEP_MAX_SEC = 6.0
HEARTBEAT_INTERVAL_MIN_SEC = 30
HEARTBEAT_INTERVAL_MAX_SEC = 600

THROTTLE_STATE: Dict[str, Any] = {
    "score": 1.0,
    "mode": "normal",
    "effective_budget": max(1, int(AETHER_TASK_BUDGET)),
    "effective_tick_sec": float(BASE_WORKER_TICK_SEC),
    "effective_sched_sleep_sec": float(BASE_SCHED_SLEEP_SEC),
    "effective_heartbeat_interval": int(HEARTBEAT_INTERVAL_SEC),
    "last_change": safe_now(),
    "last_change_ts": 0.0,
    "stable_since_ts": None,
    "cooldown_until_ts": 0.0,
    "last_state_log_ts": 0.0,
    "reasons": [],
}

DEFAULT_PROJECTS = [{"id": "default", "name": "Default", "created_at": safe_now()}]
AETHER_PROJECTS: List[Dict[str, Any]] = []
AETHER_TASKS: List[Dict[str, Any]] = []

def init_state() -> None:
    global _STATE_INITIALIZED, AETHER_STATE, AETHER_MEMORY, STRATEGIC_MEMORY, AETHER_LOGS, AETHER_PROJECTS, AETHER_TASKS
    if _STATE_INITIALIZED:
        return
    ensure_dirs()
    AETHER_STATE = load_json(STATE_FILE, dict(DEFAULT_STATE))
    AETHER_MEMORY = load_json(MEMORY_FILE, [])
    STRATEGIC_MEMORY = load_json(
        STRATEGIC_FILE,
        {"patterns": {}, "failures": {}, "history": [], "last_update": None},
    )
    AETHER_LOGS = load_json(LOG_FILE, [])
    AETHER_PROJECTS = load_json(PROJECTS_FILE, [])
    AETHER_TASKS = load_json(TASKS_FILE, [])
    if "last_heartbeat_ts" not in AETHER_STATE:
        AETHER_STATE["last_heartbeat_ts"] = None
        save_json_atomic(STATE_FILE, AETHER_STATE)
    _STATE_INITIALIZED = True

# -----------------------------
# DEMO1
# -----------------------------

def ensure_demo1() -> bool:
    if os.path.exists(DEMO1_FILE):
        return True
    return save_json_atomic(
        DEMO1_FILE,
        {"name": "demo1", "created_at": safe_now(), "events": [], "notes": "auto-created"},
    )

def export_demo1() -> str:
    try:
        ensure_demo1()
        payload = load_json(DEMO1_FILE, {"ok": False, "error": "demo1_missing"})
        return json.dumps({"ok": True, "demo": payload}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False)

def export_builder_project(project_id: Optional[str] = None) -> Tuple[str, str]:
    export_id = (project_id or "").strip() or uuid.uuid4().hex[:8]
    export_dir = os.path.join(DATA_DIR, "exports", export_id)
    os.makedirs(export_dir, exist_ok=True)
    spec_path = os.path.join(export_dir, "spec.md")
    plan_path = os.path.join(export_dir, "plan.md")
    timestamp = safe_now()
    with open(spec_path, "w", encoding="utf-8") as spec_file:
        spec_file.write(
            "# Especificación (V1)\n\n"
            f"- Proyecto: {export_id}\n"
            f"- Generado: {timestamp}\n\n"
            "Placeholder de especificación. Completar con los requisitos del usuario.\n"
        )
    with open(plan_path, "w", encoding="utf-8") as plan_file:
        plan_file.write(
            "# Plan (V1)\n\n"
            f"- Proyecto: {export_id}\n"
            f"- Generado: {timestamp}\n\n"
            "Placeholder de plan. Completar con tareas y milestones.\n"
        )
    zip_base = os.path.join(export_dir, f"aether_export_{export_id}")
    zip_path = shutil.make_archive(zip_base, "zip", root_dir=export_dir)
    return export_id, zip_path

# -----------------------------
# EVENTS LOG (JSONL)
# -----------------------------

def _rotate_events_log_if_needed() -> None:
    try:
        if os.path.exists(EVENTS_LOG_FILE) and os.path.getsize(EVENTS_LOG_FILE) > AETHER_EVENTS_LOG_MAX_BYTES:
            try:
                os.replace(EVENTS_LOG_FILE, f"{EVENTS_LOG_FILE}.1")
            except Exception:
                pass
    except Exception:
        pass

def _append_events_log(entry: Dict[str, Any]) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with events_log_lock:
            _rotate_events_log_if_needed()
            with open(EVENTS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

# -----------------------------
# LOGS + DASHBOARD
# -----------------------------

def log_event(t: str, info: Any) -> None:
    entry = {"timestamp": safe_now(), "type": t, "info": info}
    with log_lock:
        AETHER_LOGS.append(entry)
        if len(AETHER_LOGS) > MAX_LOG_ENTRIES:
            AETHER_LOGS[:] = AETHER_LOGS[-MAX_LOG_ENTRIES:]
        save_json_atomic(LOG_FILE, AETHER_LOGS)
    _append_events_log(entry)

TASK_STATUSES = {"PENDING", "RUNNING", "DONE", "FAILED", "RECOVERED"}

def _task_status_counts() -> Dict[str, int]:
    counts = {"PENDING": 0, "RUNNING": 0, "DONE": 0, "FAILED": 0, "RECOVERED": 0}
    with tasks_lock:
        for t in AETHER_TASKS:
            s = t.get("status")
            if s in counts:
                counts[s] += 1
    return counts

LOADED_MODULES: Dict[str, Any] = {}

def update_dashboard() -> None:
    with state_lock:
        snap = dict(AETHER_STATE)
    with modules_lock:
        modules_loaded = len(LOADED_MODULES)
    with projects_lock:
        projects_count = len(AETHER_PROJECTS)
    with tasks_lock:
        tasks_count = len(AETHER_TASKS)

    dash = {
        "energy": snap.get("energy", 0),
        "focus": snap.get("focus", "STANDBY"),
        "status": snap.get("status", "IDLE"),
        "queue_size": TASK_QUEUE.qsize(),
        "last_cycle": snap.get("last_cycle"),
        "version": AETHER_VERSION,
        "data_dir": DATA_DIR,
        "modules_loaded": modules_loaded,
        "freeze_mode": bool(is_frozen()),
        "safe_mode": dict(SAFE_MODE),
        "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
        "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
        "task_budget": max(1, int(AETHER_TASK_BUDGET)),
        "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
        "orchestrator_policy": dict(ORCHESTRATOR_POLICY),
        "projects_count": projects_count,
        "tasks_count": tasks_count,
        "tasks_status": _task_status_counts(),
        "snapshots": [],  # se completa en ui_status()
    }
    ok = save_json_atomic(DASHBOARD_FILE, dash)
    if not ok:
        log_event("DASHBOARD_WRITE_FAIL", {"file": DASHBOARD_FILE})

# -----------------------------
# SAFE MODE HELPERS
# -----------------------------

def safe_mode_enabled() -> bool:
    return bool(SAFE_MODE.get("enabled"))

def enable_safe_mode(reason: str) -> None:
    global SAFE_MODE_LOGGED
    if not safe_mode_enabled():
        SAFE_MODE["enabled"] = True
        SAFE_MODE["since"] = safe_now()
        SAFE_MODE["reason"] = reason
    elif not SAFE_MODE.get("since"):
        SAFE_MODE["since"] = safe_now()
        SAFE_MODE["reason"] = reason
    if not SAFE_MODE_LOGGED:
        SAFE_MODE_LOGGED = True
        log_event("SAFE_MODE_ON", {"reason": SAFE_MODE.get("reason"), "since": SAFE_MODE.get("since")})
    with state_lock:
        AETHER_STATE["status"] = "SAFE_MODE"
        save_json_atomic(STATE_FILE, AETHER_STATE)

# -----------------------------
# INTERNAL TASKS (v43)
# -----------------------------

_INTERNAL_TASK_LAST_TS = 0.0

def _internal_task_should_run(now_ts: float) -> bool:
    interval = max(10, int(AETHER_INTERNAL_TASK_INTERVAL_SEC))
    return (now_ts - _INTERNAL_TASK_LAST_TS) >= interval

def _snapshot_name_from_ts(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_prefix = "".join(ch for ch in (prefix or "").strip().lower() if ch.isalnum() or ch in ("-", "_"))
    if not safe_prefix:
        safe_prefix = "stable"
    return f"{safe_prefix}-{stamp}"

def _resolve_stable_snapshot_name() -> Optional[str]:
    with state_lock:
        name = AETHER_STATE.get("last_stable_snapshot")
    if isinstance(name, str) and name in snapshot_list():
        return name
    payload, fallback = _latest_snapshot_payload()
    if payload and fallback:
        return fallback
    return None

def _ensure_stable_snapshot() -> Optional[str]:
    name = _resolve_stable_snapshot_name()
    if name:
        return name
    snap_name = _snapshot_name_from_ts("stable-bootstrap")
    res = snapshot_create(snap_name)
    if res.get("ok"):
        with state_lock:
            AETHER_STATE["last_stable_snapshot"] = snap_name
            save_json_atomic(STATE_FILE, AETHER_STATE)
        log_event("INTERNAL_TASK_STABLE_SNAPSHOT_CREATED", {"name": snap_name})
        return snap_name
    log_event("INTERNAL_TASK_STABLE_SNAPSHOT_FAIL", {"name": snap_name, "error": res.get("error")})
    return None

def _capture_state_snapshot() -> Dict[str, Any]:
    with state_lock:
        return dict(AETHER_STATE)

def _rollback_to_stable_snapshot(reason: str, task_name: str, pre_state: Dict[str, Any]) -> None:
    stable_name = _resolve_stable_snapshot_name()
    if not stable_name:
        log_event(
            "INTERNAL_TASK_ROLLBACK_MISSING",
            {"task": task_name, "reason": reason, "previous_state": pre_state, "timestamp": safe_now()},
        )
        return
    res = snapshot_restore(stable_name)
    post_state = _capture_state_snapshot()
    log_event(
        "INTERNAL_TASK_ROLLBACK",
        {
            "task": task_name,
            "reason": reason,
            "snapshot": stable_name,
            "restore_ok": bool(res.get("ok")),
            "previous_state": pre_state,
            "restored_state": post_state,
            "timestamp": safe_now(),
        },
    )

def _validate_state_payload(state: Any) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    if not isinstance(state, dict):
        return False, ["state_not_dict"]
    required = ["id", "version", "status", "energy", "focus", "created_at"]
    for key in required:
        if key not in state:
            issues.append(f"missing_{key}")
    energy = state.get("energy")
    if not isinstance(energy, int):
        issues.append("energy_not_int")
    elif energy < 0:
        issues.append("energy_negative")
    return not issues, issues

def _validate_memory_payload(mem: Any) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    if not isinstance(mem, list):
        return False, ["memory_not_list"]
    for idx, entry in enumerate(mem[:10]):
        if not isinstance(entry, dict):
            issues.append(f"memory_entry_{idx}_not_dict")
            break
    return not issues, issues

def _validate_tasks_payload(tasks: Any) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    if not isinstance(tasks, list):
        return False, ["tasks_not_list"]
    for idx, task in enumerate(tasks[:10]):
        if not isinstance(task, dict):
            issues.append(f"task_{idx}_not_dict")
            break
    return not issues, issues

def _internal_prevalidate_state() -> Tuple[bool, List[str]]:
    with state_lock:
        return _validate_state_payload(dict(AETHER_STATE))

def _internal_postvalidate_state() -> Tuple[bool, List[str]]:
    return _internal_prevalidate_state()

def _internal_prevalidate_memory() -> Tuple[bool, List[str]]:
    with memory_lock:
        return _validate_memory_payload(list(AETHER_MEMORY))

def _internal_postvalidate_memory() -> Tuple[bool, List[str]]:
    return _internal_prevalidate_memory()

def _internal_prevalidate_planning() -> Tuple[bool, List[str]]:
    with tasks_lock:
        return _validate_tasks_payload(list(AETHER_TASKS))

def _internal_postvalidate_planning() -> Tuple[bool, List[str]]:
    return _internal_prevalidate_planning()

def _internal_prevalidate_snapshots() -> Tuple[bool, List[str]]:
    return True, []

def _internal_postvalidate_snapshots() -> Tuple[bool, List[str]]:
    return True, []

def _internal_task_state_integrity() -> Dict[str, Any]:
    changed = False
    with state_lock:
        for key, value in DEFAULT_STATE.items():
            if key not in AETHER_STATE:
                AETHER_STATE[key] = value
                changed = True
        if not isinstance(AETHER_STATE.get("energy"), int):
            raw_energy = AETHER_STATE.get("energy")
            try:
                AETHER_STATE["energy"] = int(raw_energy)
            except (TypeError, ValueError):
                AETHER_STATE["energy"] = 0
            changed = True
        if int(AETHER_STATE.get("energy", 0)) < 0:
            AETHER_STATE["energy"] = 0
            changed = True
        if not AETHER_STATE.get("status"):
            AETHER_STATE["status"] = "IDLE"
            changed = True
        if changed:
            save_json_atomic(STATE_FILE, AETHER_STATE)
    return {"ok": True, "changed": changed}

def _internal_task_memory_hygiene() -> Dict[str, Any]:
    changed = False
    with memory_lock:
        cleaned = [m for m in AETHER_MEMORY if isinstance(m, dict)]
        if len(cleaned) != len(AETHER_MEMORY):
            changed = True
        if len(cleaned) > MAX_MEMORY_ENTRIES:
            cleaned = cleaned[-MAX_MEMORY_ENTRIES:]
            changed = True
        if changed:
            AETHER_MEMORY.clear()
            AETHER_MEMORY.extend(cleaned)
            save_json_atomic(MEMORY_FILE, AETHER_MEMORY)
    return {"ok": True, "changed": changed}

def _internal_task_planning_hygiene() -> Dict[str, Any]:
    changed = False
    with tasks_lock:
        for task in AETHER_TASKS:
            if not isinstance(task, dict):
                continue
            subtasks = task.get("subtasks")
            if subtasks is None:
                task["subtasks"] = []
                changed = True
                continue
            if not isinstance(subtasks, list):
                task["subtasks"] = []
                changed = True
                continue
            cleaned = [str(s).strip() for s in subtasks if str(s).strip()]
            cleaned = cleaned[:50]
            if cleaned != subtasks:
                task["subtasks"] = cleaned
                changed = True
        if changed:
            save_json_atomic(TASKS_FILE, AETHER_TASKS)
    return {"ok": True, "changed": changed}

def _internal_task_snapshot_hygiene() -> Dict[str, Any]:
    changed = False
    entries = _load_snapshot_index()
    if not entries:
        _rebuild_snapshot_index()
        changed = True
    stable = _resolve_stable_snapshot_name()
    if not stable:
        stable = _ensure_stable_snapshot()
        changed = True if stable else changed
    if not stable:
        return {"ok": False, "changed": changed, "stable_snapshot": None, "error": "no_stable_snapshot"}
    return {"ok": True, "changed": changed, "stable_snapshot": stable}

INTERNAL_TASKS = [
    {
        "name": "state_integrity",
        "pre": _internal_prevalidate_state,
        "execute": _internal_task_state_integrity,
        "post": _internal_postvalidate_state,
    },
    {
        "name": "memory_hygiene",
        "pre": _internal_prevalidate_memory,
        "execute": _internal_task_memory_hygiene,
        "post": _internal_postvalidate_memory,
    },
    {
        "name": "planning_hygiene",
        "pre": _internal_prevalidate_planning,
        "execute": _internal_task_planning_hygiene,
        "post": _internal_postvalidate_planning,
    },
    {
        "name": "snapshot_hygiene",
        "pre": _internal_prevalidate_snapshots,
        "execute": _internal_task_snapshot_hygiene,
        "post": _internal_postvalidate_snapshots,
    },
]

def _run_internal_task(task_def: Dict[str, Any]) -> None:
    if KILL_SWITCH.get("status") != "ARMED":
        log_event("INTERNAL_TASK_BLOCKED", {"task": task_def.get("name"), "reason": "KILL_SWITCH"})
        return
    if safe_mode_enabled():
        log_event("INTERNAL_TASK_BLOCKED", {"task": task_def.get("name"), "reason": "SAFE_MODE"})
        return
    if is_frozen():
        log_event("INTERNAL_TASK_BLOCKED", {"task": task_def.get("name"), "reason": "FROZEN"})
        return
    stable_name = _ensure_stable_snapshot()
    pre_state = _capture_state_snapshot()
    log_event(
        "INTERNAL_TASK_START",
        {"task": task_def.get("name"), "stable_snapshot": stable_name, "timestamp": safe_now()},
    )
    pre_ok, pre_issues = task_def["pre"]()
    if not pre_ok:
        log_event(
            "INTERNAL_TASK_PRECHECK_FAIL",
            {"task": task_def.get("name"), "issues": pre_issues, "timestamp": safe_now()},
        )
        _rollback_to_stable_snapshot("pre_validation_failed", task_def.get("name"), pre_state)
        return

    result = task_def["execute"]()
    if not result.get("ok", True):
        log_event(
            "INTERNAL_TASK_EXEC_FAIL",
            {"task": task_def.get("name"), "error": result.get("error"), "timestamp": safe_now()},
        )
        _rollback_to_stable_snapshot("execution_failed", task_def.get("name"), pre_state)
        return
    post_ok, post_issues = task_def["post"]()
    if not post_ok:
        log_event(
            "INTERNAL_TASK_POSTCHECK_FAIL",
            {"task": task_def.get("name"), "issues": post_issues, "timestamp": safe_now()},
        )
        _rollback_to_stable_snapshot("post_validation_failed", task_def.get("name"), pre_state)
        return

    if result.get("changed"):
        snap_name = _snapshot_name_from_ts(f"stable-{task_def.get('name')}")
        snap_res = snapshot_create(snap_name)
        if not snap_res.get("ok"):
            log_event(
                "INTERNAL_TASK_SNAPSHOT_FAIL",
                {"task": task_def.get("name"), "snapshot": snap_name, "error": snap_res.get("error")},
            )
            _rollback_to_stable_snapshot("snapshot_create_failed", task_def.get("name"), pre_state)
            return
        with state_lock:
            AETHER_STATE["last_stable_snapshot"] = snap_name
            save_json_atomic(STATE_FILE, AETHER_STATE)

    log_event(
        "INTERNAL_TASK_DONE",
        {"task": task_def.get("name"), "changed": bool(result.get("changed")), "timestamp": safe_now()},
    )

def run_internal_tasks(throttle: Optional[Dict[str, Any]] = None) -> None:
    global _INTERNAL_TASK_LAST_TS
    now_ts = time.time()
    if KILL_SWITCH.get("status") != "ARMED":
        return
    if safe_mode_enabled() or is_frozen():
        return
    if not _internal_task_should_run(now_ts):
        return
    budget = min(
        max(1, int(AETHER_INTERNAL_TASK_BUDGET)),
        max(1, int((throttle or {}).get("effective_budget", AETHER_TASK_BUDGET))),
    )
    ran = 0
    for task_def in INTERNAL_TASKS:
        if ran >= budget:
            break
        _run_internal_task(task_def)
        ran += 1
    _INTERNAL_TASK_LAST_TS = now_ts
    with state_lock:
        AETHER_STATE["last_internal_task_ts"] = safe_now()
        save_json_atomic(STATE_FILE, AETHER_STATE)

# -----------------------------
# QUEUE + DEDUP
# -----------------------------
TASK_QUEUE: PriorityQueue = PriorityQueue()
QUEUE_SET = set()

TASK_DEDUP: List[str] = []
TASK_DEDUP_SET = set()

def tasks_queue_contains(command: str) -> bool:
    c = (command or "").strip()
    if not c:
        return False
    with queue_lock:
        return c in QUEUE_SET

def _dedup_prune_if_needed() -> None:
    with dedup_lock:
        if len(TASK_DEDUP) <= MAX_DEDUP_KEYS:
            return
        keep = int(MAX_DEDUP_KEYS * 0.7)
        old = TASK_DEDUP[:-keep]
        TASK_DEDUP[:] = TASK_DEDUP[-keep:]
        for k in old:
            TASK_DEDUP_SET.discard(k)

def compute_priority(base: int) -> int:
    with state_lock:
        e = int(AETHER_STATE.get("energy", 0))
    return int(base) + (3 if e < 20 else 0)

def _infer_task_type(command: str, source: str) -> str:
    cmd = (command or "").lower()
    if source == "internal":
        return "read_only"
    if any(k in cmd for k in ["export", "snapshot export", "replica export"]):
        return "io_export"
    if any(k in cmd for k in ["restore", "import", "snapshot restore", "replica import"]):
        return "write_state"
    if any(k in cmd for k in ["reload", "plugin", "plugins"]):
        return "system"
    return "analysis"

def _task_mode(task: Dict[str, Any]) -> str:
    source = (task.get("source") or "").strip().lower()
    if source in {"ui", "external", "chat"}:
        return "manual"
    return "auto"

def can_execute(task_type: str, mode: str) -> bool:
    policy = PERMISSIONS.get(task_type or "analysis", {})
    return bool(policy.get(mode))

def _canonical_task_payload(task: Dict[str, Any]) -> str:
    payload = dict(task or {})
    payload.pop("signature", None)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sign_task(task: Dict[str, Any]) -> Optional[str]:
    if not AETHER_TASK_SECRET:
        return None
    msg = _canonical_task_payload(task)
    return hmac.new(AETHER_TASK_SECRET.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

def verify_task(task: Dict[str, Any]) -> bool:
    global _SIGNATURE_WARNED
    if not AETHER_TASK_SECRET:
        if not _SIGNATURE_WARNED:
            _SIGNATURE_WARNED = True
            log_event("TASK_SIGNATURE_SKIPPED", {"reason": "AETHER_TASK_SECRET_EMPTY"})
        return True
    expected = sign_task(task)
    provided = task.get("signature")
    if not expected or not isinstance(provided, str):
        return False
    return hmac.compare_digest(expected, provided)

def enqueue_task(
    command: str,
    priority: int = 5,
    source: str = "external",
    task_type: Optional[str] = None,
    origin: Optional[str] = None,
) -> Dict[str, Any]:
    command = (command or "").strip()
    if not command:
        return {"ok": False, "error": "empty_command"}

    allowed_owner, owner_command, owner_block = _owner_only_gate(command)
    if not allowed_owner:
        log_event(
            "OWNER_ONLY_BLOCK_ENQUEUE",
            {"command": command, "source": source, "origin": origin, "reason": "owner_only"},
        )
        return owner_block
    command = owner_command

    zone = resolve_zone(source, origin)
    blocked_zones_in_safe = {"CHAT"}
    if safe_mode_enabled() and zone in blocked_zones_in_safe:
        log_event("SAFE_MODE_BLOCK_ENQUEUE", {"command": command, "source": source, "zone": zone})
        return {"ok": False, "blocked": True, "reason": "SAFE_MODE_ON"}

    blocked_zones_in_freeze = {"CHAT"}
    if is_frozen() and zone in blocked_zones_in_freeze:
        log_event("FREEZE_BLOCK_ENQUEUE", {"command": command, "source": source, "zone": zone})
        return {"ok": False, "blocked": True, "reason": "SYSTEM_FROZEN"}

    if (not AETHER_HEARTBEAT_ENABLED) and command.lower().strip() == HEARTBEAT_CMD:
        log_event("HEARTBEAT_DISABLED", {"message": "Heartbeat disabled: blocked enqueue"})
        return {"ok": False, "blocked": True, "reason": "heartbeat_disabled"}

    # dedup only external
    if source != "internal":
        key = f"{command}:{source}"
        with dedup_lock:
            if key in TASK_DEDUP_SET:
                return {"ok": False, "dedup": True}
            TASK_DEDUP_SET.add(key)
            TASK_DEDUP.append(key)
        _dedup_prune_if_needed()

    dyn = compute_priority(int(priority))
    resolved_type = (task_type or "").strip() or _infer_task_type(command, source)
    allowed, reason, specials = _trust_zone_allowed(zone, resolved_type, command)
    if not allowed:
        log_event(
            "TRUST_ZONE_BLOCK_ENQUEUE",
            {
                "command": command,
                "source": source,
                "origin": origin,
                "zone": zone,
                "task_type": resolved_type,
                "reason": reason,
                "special": specials,
            },
        )
        return {"ok": False, "blocked": True, "reason": reason}
    task = {
        "id": str(uuid.uuid4()),
        "command": command,
        "source": source,
        "created_at": safe_now(),
        "task_type": resolved_type,
        "status": "PENDING",
        "zone": zone,
    }
    if origin:
        task["origin"] = origin
    signature = sign_task(task)
    if signature:
        task["signature"] = signature

    with queue_lock:
        if command in QUEUE_SET:
            return {"ok": False, "dedup": True}
        TASK_QUEUE.put((dyn, task))
        QUEUE_SET.add(command)

    log_event(
        "ENQUEUE",
        {"command": command, "priority": dyn, "source": source, "task_type": resolved_type, "zone": zone, "origin": origin},
    )
    update_dashboard()
    return {"ok": True, "task_id": task["id"], "priority": dyn}

# -----------------------------
# STRATEGY
# -----------------------------

def record_strategy(command: str, mode: str, success: bool) -> None:
    sig = f"{mode}:{len((command or '').split())}"
    target = "patterns" if success else "failures"
    with strategic_lock:
        if not isinstance(STRATEGIC_MEMORY.get("patterns"), dict):
            STRATEGIC_MEMORY["patterns"] = {}
        if not isinstance(STRATEGIC_MEMORY.get("failures"), dict):
            STRATEGIC_MEMORY["failures"] = {}
        if not isinstance(STRATEGIC_MEMORY.get("history"), list):
            STRATEGIC_MEMORY["history"] = []

        STRATEGIC_MEMORY[target][sig] = STRATEGIC_MEMORY[target].get(sig, 0) + 1
        STRATEGIC_MEMORY["history"].append(
            {"timestamp": safe_now(), "command": command, "mode": mode, "success": bool(success)}
        )
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = safe_now()
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

# -----------------------------
# PLUGINS HOT-RELOAD (*_ai.py)
# -----------------------------

def _list_plugin_files() -> List[str]:
    try:
        files = [f for f in os.listdir(MODULES_DIR) if f.endswith("_ai.py") and not f.startswith("_")]
        files.sort()
        return files
    except Exception:
        return []

def reload_ai_modules() -> List[str]:
    loaded: Dict[str, Any] = {}
    for fn in _list_plugin_files():
        name = fn[:-3]
        path = os.path.join(MODULES_DIR, fn)
        try:
            mod_name = f"plugins.{name}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

            if callable(getattr(mod, "can_handle", None)) and callable(getattr(mod, "run", None)):
                loaded[name] = mod
            else:
                log_event("MODULE_SKIPPED", {"module": name, "reason": "missing can_handle/run"})
        except Exception as e:
            log_event("MODULE_LOAD_ERROR", {"module": name, "error": str(e)})

    with modules_lock:
        LOADED_MODULES.clear()
        LOADED_MODULES.update(loaded)

    log_event("MODULES_RELOADED", {"modules": list(LOADED_MODULES.keys())})
    update_dashboard()
    return list(LOADED_MODULES.keys())

def _any_module_can_handle(command: str) -> bool:
    c = (command or "").strip()
    if not c:
        return False
    with modules_lock:
        mods = list(LOADED_MODULES.values())
    for mod in mods:
        try:
            if callable(getattr(mod, "can_handle", None)) and mod.can_handle(c):
                return True
        except Exception:
            continue
    return False

def _read_plugin_state() -> Dict[str, Any]:
    # STATE PLUMBING: read-only best-effort state for plugins, safe fallback to {} on failure.
    def _inject_v40_observability(state_obj: Dict[str, Any]) -> None:
        # v40 observability injection (read-only)
        try:
            if not isinstance(state_obj, dict):
                return
            if "allowed_shell_cmds" not in state_obj:
                allowed_shell_cmds = []
                try:
                    adapters_obj = globals().get("adapters")
                    if adapters_obj is not None:
                        allowed_shell_cmds = getattr(adapters_obj, "allowed_shell_cmds", []) or []
                except Exception:
                    allowed_shell_cmds = []
                state_obj["allowed_shell_cmds"] = allowed_shell_cmds
            if "allowed_http_domains" not in state_obj:
                allowed_http_domains = []
                try:
                    adapters_obj = globals().get("adapters")
                    if adapters_obj is not None:
                        allowed_http_domains = getattr(adapters_obj, "allowed_http_domains", []) or []
                except Exception:
                    allowed_http_domains = []
                state_obj["allowed_http_domains"] = allowed_http_domains
            if "watchdog" not in state_obj:
                watchdog_payload = {"last_cycle": state_obj.get("last_cycle")}
                try:
                    watchdog_sec = globals().get("AETHER_WATCHDOG_SEC")
                    watchdog_grace_sec = globals().get("AETHER_WATCHDOG_GRACE_SEC")
                    if watchdog_sec is not None:
                        watchdog_payload["watchdog_sec"] = int(watchdog_sec)
                    if watchdog_grace_sec is not None:
                        watchdog_payload["watchdog_grace_sec"] = int(watchdog_grace_sec)
                except Exception:
                    pass
                state_obj["watchdog"] = watchdog_payload
            if "throttle" not in state_obj:
                state_obj["throttle"] = {"mode": "normal", "score": None, "reasons": []}
        except Exception:
            pass

    try:
        with state_lock:
            state_snapshot = dict(AETHER_STATE)
        _inject_v40_observability(state_snapshot)
        with modules_lock:
            mods = list(LOADED_MODULES.keys())
        with strategic_lock:
            patterns = STRATEGIC_MEMORY.get("patterns", {})
            failures = STRATEGIC_MEMORY.get("failures", {})
            hist = STRATEGIC_MEMORY.get("history", [])
            strategic = {
                "patterns": len(patterns) if isinstance(patterns, dict) else 0,
                "failures": len(failures) if isinstance(failures, dict) else 0,
                "last_update": STRATEGIC_MEMORY.get("last_update"),
                "history_len": len(hist) if isinstance(hist, list) else 0,
            }
        trust_zone_summary = {
            "blocks": _summarize_trust_zone_blocks(),
            "policy": _trust_zone_policy_snapshot(),
        }
        watchdog_payload = state_snapshot.get("watchdog")
        if not isinstance(watchdog_payload, dict):
            watchdog_payload = {
                "watchdog_sec": int(AETHER_WATCHDOG_SEC),
                "watchdog_grace_sec": int(AETHER_WATCHDOG_GRACE_SEC),
            }
        return {
            "state": state_snapshot,
            "queue_size": TASK_QUEUE.qsize(),
            "memory_len": len(AETHER_MEMORY),
            "strategic": strategic,
            "kill_switch": KILL_SWITCH,
            "modules": mods,
            "data_dir": DATA_DIR,
            "modules_dir": MODULES_DIR,
            "version": AETHER_VERSION,
            "freeze": FREEZE_STATE,
            "watchdog": watchdog_payload,
            "safe_mode": dict(SAFE_MODE),
            "trust_zone": trust_zone_summary,
            "recent_errors": _collect_recent_errors(),
        }
    except Exception:
        pass

    data_dir = os.environ.get("AETHER_DATA_DIR", "/tmp/aether")
    candidates = (
        os.path.join(data_dir, "aether_state.json"),
        os.path.join(data_dir, "dashboard.json"),
        os.path.join(data_dir, "status.json"),
    )
    for path in candidates:
        payload = load_json(path, None)
        if isinstance(payload, dict) and payload:
            if "state" in payload:
                state_payload = payload.get("state")
                if isinstance(state_payload, dict):
                    _inject_v40_observability(state_payload)
                return payload
            _inject_v40_observability(payload)
            return {"state": payload}
    return {}

def execute_ai_module(command: str) -> Dict[str, Any]:
    with modules_lock:
        items = list(LOADED_MODULES.items())
    for name, mod in items:
        try:
            if mod.can_handle(command):
                st = _read_plugin_state()
                data_dir = None
                if isinstance(st, dict):
                    state_data_dir = st.get("data_dir")
                    if isinstance(state_data_dir, str) and state_data_dir.strip():
                        data_dir = state_data_dir
                if not data_dir:
                    env_data_dir = os.environ.get("AETHER_DATA_DIR")
                    if isinstance(env_data_dir, str) and env_data_dir.strip():
                        data_dir = env_data_dir
                    else:
                        data_dir = "/tmp/aether"
                adapters = Adapters(
                    base_dir=data_dir,
                    allowed_shell_cmds=[],
                    allowed_http_domains=[],
                )
                ctx = {
                    "data_dir": data_dir,
                    "adapters": adapters,
                    "state": st,
                }
                try:
                    return {"success": True, "module": name, "result": mod.run(command, ctx=ctx, state=st)}
                except TypeError:
                    return {"success": True, "module": name, "result": mod.run(command, state=st)}
        except Exception as e:
            log_event("MODULE_RUN_ERROR", {"module": name, "error": str(e)})
            return {"success": False, "error": f"{name}: {e}"}
    return {"success": False, "error": "No suitable AI module found"}

# -----------------------------
# SNAPSHOTS (v28 + v28.3 plugins)
# -----------------------------

def _snapshot_path(name: str) -> str:
    safe = "".join(ch for ch in (name or "").strip() if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        safe = "snapshot"
    return os.path.join(SNAPSHOT_DIR, f"{safe}.json")

def _snapshot_entry_from_payload(payload: Dict[str, Any], fallback_name: str) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    name = (payload.get("name") or fallback_name or "").strip()
    if not name:
        return None
    ts = payload.get("created_at") or payload.get("ts")
    version = payload.get("version") or payload.get("app_version")
    checksum = payload.get("checksum_sha256") or payload.get("checksum")
    entry: Dict[str, Any] = {"name": name, "ts": ts, "version": version}
    if checksum:
        entry["checksum"] = checksum
    return entry

def _snapshot_index_payload(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ok": True,
        "format": "aether-snapshot-index-v1",
        "updated_at": safe_now(),
        "snapshots": entries,
    }

def _snapshot_index_entries(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("snapshots")
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        entry: Dict[str, Any] = {"name": name, "ts": item.get("ts"), "version": item.get("version")}
        if item.get("checksum"):
            entry["checksum"] = item.get("checksum")
        entries.append(entry)
    return entries

def _rebuild_snapshot_index() -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    try:
        files = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")]
        files.sort()
    except Exception:
        files = []
    for fn in files:
        if fn == os.path.basename(SNAPSHOT_INDEX_FILE):
            continue
        name = fn[:-5]
        payload = load_json(os.path.join(SNAPSHOT_DIR, fn), None)
        entry = _snapshot_entry_from_payload(payload, name)
        if entry is None:
            try:
                mtime = os.path.getmtime(os.path.join(SNAPSHOT_DIR, fn))
                entry = {"name": name, "ts": datetime.fromtimestamp(mtime, timezone.utc).isoformat(), "version": None}
            except Exception:
                entry = {"name": name, "ts": None, "version": None}
        entries.append(entry)
    entries.sort(key=lambda item: item.get("name") or "")
    save_json_atomic(SNAPSHOT_INDEX_FILE, _snapshot_index_payload(entries))
    return entries

def _load_snapshot_index() -> List[Dict[str, Any]]:
    payload = load_json(SNAPSHOT_INDEX_FILE, None)
    entries = _snapshot_index_entries(payload)
    if not entries:
        return _rebuild_snapshot_index()
    valid = []
    for entry in entries:
        name = entry.get("name")
        if not name:
            continue
        if os.path.exists(_snapshot_path(name)):
            valid.append(entry)
    if len(valid) != len(entries):
        save_json_atomic(SNAPSHOT_INDEX_FILE, _snapshot_index_payload(valid))
    return valid

def _update_snapshot_index(name: str, payload: Dict[str, Any]) -> None:
    entries = _load_snapshot_index()
    entry = _snapshot_entry_from_payload(payload, name)
    if entry is None:
        return
    updated = False
    for idx, existing in enumerate(entries):
        if existing.get("name") == entry.get("name"):
            entries[idx] = entry
            updated = True
            break
    if not updated:
        entries.append(entry)
    entries.sort(key=lambda item: item.get("name") or "")
    save_json_atomic(SNAPSHOT_INDEX_FILE, _snapshot_index_payload(entries))

def snapshot_list() -> List[str]:
    try:
        entries = _load_snapshot_index()
        return [item.get("name") for item in entries if item.get("name")]
    except Exception:
        return []

def _read_text_file(path: str, limit_bytes: int = 250_000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            txt = f.read()
        b = txt.encode("utf-8", errors="ignore")
        if len(b) > limit_bytes:
            b = b[:limit_bytes]
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def snapshot_pack_plugins() -> Dict[str, str]:
    packed: Dict[str, str] = {}
    for fn in _list_plugin_files():
        p = os.path.join(MODULES_DIR, fn)
        packed[f"{MODULES_DIR}/{fn}"] = _read_text_file(p)
    return packed

def snapshot_apply_plugins(packed: Dict[str, str]) -> Dict[str, Any]:
    if not isinstance(packed, dict):
        return {"ok": False, "error": "plugins_invalid"}
    try:
        os.makedirs(MODULES_DIR, exist_ok=True)
        wrote = 0
        for rel, txt in packed.items():
            if not isinstance(rel, str) or not rel.startswith(f"{MODULES_DIR}/") or not rel.endswith(".py"):
                continue
            base = os.path.basename(rel)
            if not base.endswith("_ai.py"):
                continue
            out_path = os.path.join(MODULES_DIR, base)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(txt if isinstance(txt, str) else "")
            wrote += 1
        return {"ok": True, "wrote": wrote}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def snapshot_create(name: str = "demo1") -> Dict[str, Any]:
    name = (name or "demo1").strip()
    path = _snapshot_path(name)

    with snap_lock, state_lock, memory_lock, strategic_lock, log_lock, projects_lock, tasks_lock, modules_lock:
        payload = {
            "ok": True,
            "name": name,
            "created_at": safe_now(),
            "version": AETHER_VERSION,
            "env": {
                "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
                "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
                "freeze_mode": bool(is_frozen()),
                "safe_mode": dict(SAFE_MODE),
                "data_dir": DATA_DIR,
                "task_budget": max(1, int(AETHER_TASK_BUDGET)),
                "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            },
            "files": {
                "state": dict(AETHER_STATE),
                "memory": list(AETHER_MEMORY),
                "strategic": dict(STRATEGIC_MEMORY),
                "logs": list(AETHER_LOGS),
                "modules": list(LOADED_MODULES.keys()),
                "projects": list(AETHER_PROJECTS),
                "tasks": list(AETHER_TASKS),
            },
            "plugins": {"format": "plugins-text-v1", "files": snapshot_pack_plugins()},
            "notes": "snapshot includes plugins + projects/tasks + lifecycle/retry/budget/planning",
        }

    ok = save_json_atomic(path, payload)
    if ok:
        _update_snapshot_index(name, payload)
        log_event("SNAPSHOT_CREATED", {"name": name, "file": path, "plugins": len(payload["plugins"]["files"])})
        update_dashboard()
        return {"ok": True, "name": name, "file": path}
    log_event("SNAPSHOT_CREATE_FAIL", {"name": name, "file": path})
    return {"ok": False, "error": "snapshot_write_failed", "file": path}

def snapshot_restore(name: str = "demo1") -> Dict[str, Any]:
    name = (name or "demo1").strip()
    entries = _load_snapshot_index()
    entry = next((item for item in entries if item.get("name") == name), None)
    path = _snapshot_path(entry.get("name") if entry else name)
    payload = load_json(path, None)
    if not payload or not isinstance(payload, dict) or not payload.get("ok"):
        fallback_path = _snapshot_path(name)
        if fallback_path != path:
            payload = load_json(fallback_path, None)
            if payload and isinstance(payload, dict) and payload.get("ok"):
                path = fallback_path
            else:
                available = [item.get("name") for item in entries if item.get("name")]
                return {
                    "ok": False,
                    "error": "snapshot_missing_or_invalid",
                    "file": fallback_path,
                    "available": available,
                }
        else:
            available = [item.get("name") for item in entries if item.get("name")]
            return {
                "ok": False,
                "error": "snapshot_missing_or_invalid",
                "file": path,
                "available": available,
            }

    files = payload.get("files", {}) if isinstance(payload, dict) else {}
    st = files.get("state", dict(DEFAULT_STATE))
    mem = files.get("memory", [])
    strat = files.get("strategic", {"patterns": {}, "failures": {}, "history": [], "last_update": None})
    logs = files.get("logs", [])
    projects = files.get("projects", [])
    tasks = files.get("tasks", [])

    with state_lock:
        AETHER_STATE.clear()
        AETHER_STATE.update(st if isinstance(st, dict) else dict(DEFAULT_STATE))
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["status"] = "FROZEN" if is_frozen() else AETHER_STATE.get("status", "IDLE")
        save_json_atomic(STATE_FILE, AETHER_STATE)

    with memory_lock:
        AETHER_MEMORY.clear()
        if isinstance(mem, list):
            AETHER_MEMORY.extend(mem)
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    with strategic_lock:
        STRATEGIC_MEMORY.clear()
        STRATEGIC_MEMORY.update(strat if isinstance(strat, dict) else {"patterns": {}, "failures": {}, "history": [], "last_update": None})
        if not isinstance(STRATEGIC_MEMORY.get("history"), list):
            STRATEGIC_MEMORY["history"] = []
        if len(STRATEGIC_MEMORY["history"]) > MAX_STRATEGY_HISTORY:
            STRATEGIC_MEMORY["history"] = STRATEGIC_MEMORY["history"][-MAX_STRATEGY_HISTORY:]
        STRATEGIC_MEMORY["last_update"] = safe_now()
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

    with log_lock:
        AETHER_LOGS.clear()
        if isinstance(logs, list):
            AETHER_LOGS.extend(logs)
        save_json_atomic(LOG_FILE, AETHER_LOGS)

    with projects_lock:
        AETHER_PROJECTS.clear()
        if isinstance(projects, list) and projects:
            AETHER_PROJECTS.extend(projects)
        else:
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)

    with tasks_lock:
        AETHER_TASKS.clear()
        if isinstance(tasks, list):
            AETHER_TASKS.extend(tasks)
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    plug = payload.get("plugins", {}) if isinstance(payload, dict) else {}
    if isinstance(plug, dict) and isinstance(plug.get("files"), dict):
        res = snapshot_apply_plugins(plug.get("files"))
        log_event("SNAPSHOT_PLUGINS_APPLIED", res)

    reload_ai_modules()
    update_dashboard()
    log_event("SNAPSHOT_RESTORED", {"name": name, "file": path})
    return {"ok": True, "name": name, "file": path}

def snapshot_export(name: str = "demo1") -> str:
    name = (name or "demo1").strip()
    entries = _load_snapshot_index()
    entry = next((item for item in entries if item.get("name") == name), None)
    path = _snapshot_path(entry.get("name") if entry else name)
    payload = load_json(path, None)
    if not payload:
        fallback_path = _snapshot_path(name)
        if fallback_path != path:
            payload = load_json(fallback_path, None)
        if not payload:
            available = [item.get("name") for item in entries if item.get("name")]
            return json.dumps(
                {"ok": False, "error": "snapshot_not_found", "name": name, "available": available},
                indent=2,
                ensure_ascii=False,
            )
    return json.dumps(payload, indent=2, ensure_ascii=False)

def snapshot_import(json_text: str) -> Dict[str, Any]:
    try:
        payload = json.loads(json_text or "")
        if not isinstance(payload, dict) or not payload.get("ok"):
            return {"ok": False, "error": "invalid_payload"}
        name = (payload.get("name") or "imported").strip()
        if not payload.get("created_at"):
            return {"ok": False, "error": "invalid_payload_missing_created_at"}
        path = _snapshot_path(name)
        ok = save_json_atomic(path, payload)
        if ok:
            _update_snapshot_index(name, payload)
            log_event("SNAPSHOT_IMPORTED", {"name": name, "file": path})
            update_dashboard()
            return {"ok": True, "name": name, "file": path}
        return {"ok": False, "error": "write_failed", "file": path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -----------------------------
# REPLICA (v28.2)
# -----------------------------
REPLICA_FORMAT = "aether-replica-v28.2"

def replica_export(name: str = "replica") -> str:
    name = (name or "replica").strip()

    with state_lock:
        st = dict(AETHER_STATE)
    with memory_lock:
        mem = list(AETHER_MEMORY)
    with strategic_lock:
        strat = dict(STRATEGIC_MEMORY)
    with log_lock:
        logs = list(AETHER_LOGS)
    with projects_lock:
        projects = list(AETHER_PROJECTS)
    with tasks_lock:
        tasks = list(AETHER_TASKS)

    demo1 = load_json(DEMO1_FILE, {"name": "demo1", "created_at": safe_now(), "events": [], "notes": "missing"})

    snaps: Dict[str, Any] = {}
    for sname in snapshot_list():
        snaps[sname] = load_json(_snapshot_path(sname), None)

    payload = {
        "ok": True,
        "format": REPLICA_FORMAT,
        "name": name,
        "created_at": safe_now(),
        "app_version": AETHER_VERSION,
        "env": {
            "data_dir": DATA_DIR,
            "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
            "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
            "freeze_mode": bool(is_frozen()),
            "safe_mode": dict(SAFE_MODE),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
        },
        "bundle": {
            "state": st,
            "memory": mem,
            "strategic": strat,
            "logs": logs,
            "demo1": demo1,
            "snapshots": snaps,
            "projects": projects,
            "tasks": tasks,
            "plugins": {"format": "plugins-text-v1", "files": snapshot_pack_plugins()},
        },
    }

    copy = dict(payload)
    txt = json.dumps(copy, indent=2, ensure_ascii=False, sort_keys=True)
    payload["checksum_sha256"] = sha256_text(txt)
    return json.dumps(payload, indent=2, ensure_ascii=False)

def replica_apply(payload: Dict[str, Any]) -> Dict[str, Any]:
    bundle = (payload or {}).get("bundle", {}) or {}
    st = bundle.get("state", dict(DEFAULT_STATE))
    mem = bundle.get("memory", [])
    strat = bundle.get("strategic", {"patterns": {}, "failures": {}, "history": [], "last_update": None})
    logs = bundle.get("logs", [])
    demo1 = bundle.get("demo1", None)
    projects = bundle.get("projects", [])
    tasks = bundle.get("tasks", [])
    plugins = bundle.get("plugins", {})

    with state_lock:
        AETHER_STATE.clear()
        AETHER_STATE.update(st if isinstance(st, dict) else dict(DEFAULT_STATE))
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["status"] = "FROZEN" if is_frozen() else AETHER_STATE.get("status", "IDLE")
        save_json_atomic(STATE_FILE, AETHER_STATE)

    with memory_lock:
        AETHER_MEMORY.clear()
        if isinstance(mem, list):
            AETHER_MEMORY.extend(mem)
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    with strategic_lock:
        STRATEGIC_MEMORY.clear()
        STRATEGIC_MEMORY.update(strat if isinstance(strat, dict) else {"patterns": {}, "failures": {}, "history": [], "last_update": None})
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

    with log_lock:
        AETHER_LOGS.clear()
        if isinstance(logs, list):
            AETHER_LOGS.extend(logs)
        save_json_atomic(LOG_FILE, AETHER_LOGS)

    if demo1 is not None:
        save_json_atomic(DEMO1_FILE, demo1)

    snaps = bundle.get("snapshots", {}) or {}
    if isinstance(snaps, dict):
        for sname, snap_payload in snaps.items():
            if sname and snap_payload:
                save_json_atomic(_snapshot_path(str(sname)), snap_payload)
        _rebuild_snapshot_index()

    with projects_lock:
        AETHER_PROJECTS.clear()
        if isinstance(projects, list) and projects:
            AETHER_PROJECTS.extend(projects)
        else:
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)

    with tasks_lock:
        AETHER_TASKS.clear()
        if isinstance(tasks, list):
            AETHER_TASKS.extend(tasks)
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    if isinstance(plugins, dict) and isinstance(plugins.get("files"), dict):
        res = snapshot_apply_plugins(plugins["files"])
        log_event("REPLICA_PLUGINS_APPLIED", res)

    reload_ai_modules()
    update_dashboard()
    log_event("REPLICA_APPLIED", {"name": payload.get("name"), "format": payload.get("format")})
    return {"ok": True, "applied": True, "snapshots": snapshot_list()}

def replica_import(replica_json_text: str, apply_now: bool = True) -> Dict[str, Any]:
    try:
        payload = json.loads(replica_json_text or "")
        if not isinstance(payload, dict) or not payload.get("ok"):
            return {"ok": False, "error": "invalid_payload"}
        if payload.get("format") != REPLICA_FORMAT:
            return {"ok": False, "error": "invalid_format", "expected": REPLICA_FORMAT, "got": payload.get("format")}

        checksum = payload.get("checksum_sha256")
        if not checksum or not isinstance(checksum, str):
            return {"ok": False, "error": "missing_checksum"}

        copy = dict(payload)
        copy.pop("checksum_sha256", None)
        txt = json.dumps(copy, indent=2, ensure_ascii=False, sort_keys=True)
        if sha256_text(txt) != checksum:
            return {"ok": False, "error": "checksum_mismatch"}

        if apply_now:
            return replica_apply(payload)
        return {"ok": True, "applied": False}
    except Exception as e:
        log_event("REPLICA_IMPORT_ERROR", {"error": str(e)})
        return {"ok": False, "error": str(e)}

# -----------------------------
# ORCHESTRATOR (v29+)
# -----------------------------

def _normalize_task(task: Dict[str, Any]) -> None:
    if not isinstance(task, dict):
        return
    if task.get("status") not in TASK_STATUSES:
        task["status"] = "PENDING"
    try:
        task["retry_count"] = max(0, int(task.get("retry_count", 0)))
    except Exception:
        task["retry_count"] = 0
    if not task.get("task_type"):
        task["task_type"] = _infer_task_type(task.get("command") or "", "orchestrator")
    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list):
        subtasks = []
    task["subtasks"] = [str(s).strip() for s in subtasks if str(s).strip()]

def _normalize_tasks_locked() -> None:
    for t in AETHER_TASKS:
        _normalize_task(t)

def ensure_projects() -> None:
    with projects_lock:
        if not isinstance(AETHER_PROJECTS, list) or not AETHER_PROJECTS:
            AETHER_PROJECTS.clear()
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)
    with tasks_lock:
        if not isinstance(AETHER_TASKS, list):
            AETHER_TASKS.clear()
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

def list_projects() -> List[Dict[str, Any]]:
    with projects_lock:
        return list(AETHER_PROJECTS)

def list_tasks(project_id: str) -> List[Dict[str, Any]]:
    with tasks_lock:
        return [t for t in AETHER_TASKS if t.get("project_id") == project_id]

def add_project(name: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "project_name_required"}
    pid = f"proj-{uuid.uuid4().hex[:10]}"
    proj = {"id": pid, "name": name, "created_at": safe_now()}
    with projects_lock:
        AETHER_PROJECTS.append(proj)
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)
    log_event("PROJECT_CREATED", {"id": pid, "name": name})
    update_dashboard()
    return {"ok": True, "project": proj}

def add_task(project_id: str, command: str) -> Dict[str, Any]:
    project_id = (project_id or "").strip()
    command = (command or "").strip()
    if not project_id:
        return {"ok": False, "error": "project_required"}
    if not command:
        return {"ok": False, "error": "command_required"}

    tid = f"task-{uuid.uuid4().hex[:10]}"
    task = {
        "id": tid,
        "project_id": project_id,
        "command": command,
        "created_at": safe_now(),
        "last_run": None,
        "last_success": None,
        "last_result": None,
        "status": "PENDING",
        "retry_count": 0,
        "subtasks": [],  # v32 planning output (propuestas)
        "task_type": _infer_task_type(command, "orchestrator"),
    }
    with tasks_lock:
        AETHER_TASKS.append(task)
        save_json_atomic(TASKS_FILE, AETHER_TASKS)
    log_event("PROJECT_TASK_CREATED", {"id": tid, "project_id": project_id})
    update_dashboard()
    return {"ok": True, "task": task}

def _extract_subtasks_from_result(result: Dict[str, Any]) -> List[str]:
    if not isinstance(result, dict):
        return []
    payload = result.get("result")
    if not isinstance(payload, dict):
        return []
    subtasks = payload.get("subtasks")
    if not isinstance(subtasks, list):
        return []
    out = [str(s).strip() for s in subtasks if str(s).strip()]
    return out[:50]

def can_run_project_task(task: Dict[str, Any]) -> Tuple[bool, str]:
    if safe_mode_enabled():
        return False, "SAFE_MODE_ON"
    if is_frozen():
        return False, "SYSTEM_FROZEN"
    if not ORCHESTRATOR_POLICY.get("allow_run", True):
        return False, "POLICY_BLOCKED"
    if task.get("status") == "FAILED" and int(task.get("retry_count", 0)) >= max(0, int(AETHER_TASK_MAX_RETRIES)):
        return False, "MAX_RETRIES_EXCEEDED"
    return True, ""

# -----------------------------
# ROUTING / EXECUTION
# -----------------------------

def detect_domains(command: str) -> List[str]:
    c = (command or "").lower()
    d = set()
    if any(k in c for k in ["física", "ecuación", "modelo", "simulación", "simular"]):
        d.add("science")
    if any(k in c for k in ["reload", "plugin", "plugins", "task "]):
        d.add("ai")
    if any(k in c for k in ["snapshot", "snap", "restore", "export", "import", "replica"]):
        d.add("persistence")
    return list(d) or ["general"]

def decide_engine(command: str, domains: List[str]) -> Dict[str, Any]:
    if _any_module_can_handle(command):
        return {"mode": "ai_module", "confidence": 0.99}
    if "science" in domains:
        return {"mode": "scientific", "confidence": 0.8}
    if "ai" in domains:
        return {"mode": "ai_module", "confidence": 0.7}
    return {"mode": "general", "confidence": 0.7}

REPLAY_SNAPSHOT_WINDOW_SEC = 15 * 60

def _copy_memory_entries() -> List[Dict[str, Any]]:
    # Copy under lock so replay reads a consistent view without blocking writers for long.
    with memory_lock:
        return list(AETHER_MEMORY)

def _copy_log_entries() -> List[Dict[str, Any]]:
    # Copy under lock to avoid replay racing with log appenders.
    with log_lock:
        return list(AETHER_LOGS)

def _find_memory_entry(task_id: str, memory_entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in memory_entries:
        if entry.get("task_id") == task_id:
            return entry
    return None

def _find_log_command(task_id: str, log_entries: List[Dict[str, Any]]) -> Optional[str]:
    for entry in reversed(log_entries):
        info = entry.get("info")
        if isinstance(info, dict) and info.get("task_id") == task_id:
            command = info.get("command")
            if isinstance(command, str) and command.strip():
                return command
    return None

def _snapshot_meta(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": payload.get("name"),
        "created_at": payload.get("created_at"),
        "version": payload.get("version"),
    }

def _find_snapshot_for_replay(target_ts: Optional[float]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if target_ts is None:
        return None, None
    best_payload = None
    best_delta = None
    for name in snapshot_list():
        payload = load_json(_snapshot_path(name), None)
        if not isinstance(payload, dict):
            continue
        created_ts = _parse_iso_ts(payload.get("created_at"))
        if created_ts is None:
            continue
        delta = abs(created_ts - target_ts)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_payload = payload
    if best_payload is None or best_delta is None or best_delta > REPLAY_SNAPSHOT_WINDOW_SEC:
        return None, None
    return best_payload, {"delta_sec": best_delta, **_snapshot_meta(best_payload)}

def _memory_entry_from_snapshot(payload: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
    files = payload.get("files") if isinstance(payload, dict) else None
    memory_entries = files.get("memory") if isinstance(files, dict) else None
    if not isinstance(memory_entries, list):
        return None
    return _find_memory_entry(task_id, memory_entries)

def _decision_diff(original: Dict[str, Any], replayed: Dict[str, Any]) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    keys = set(original.keys()) | set(replayed.keys())
    for key in sorted(keys):
        if original.get(key) != replayed.get(key):
            diff[key] = {"original": original.get(key), "replayed": replayed.get(key)}
    return diff

def replay_task(task_id: str, dry_run: bool = True) -> Dict[str, Any]:
    task_id = (task_id or "").strip()
    if not task_id:
        return {"ok": False, "error": "task_id_required"}

    # Replay never executes commands to preserve audit safety across environments.
    memory_entries = _copy_memory_entries()
    log_entries = _copy_log_entries()
    memory_entry = _find_memory_entry(task_id, memory_entries)
    command = memory_entry.get("command") if memory_entry else None

    if not isinstance(command, str) or not command.strip():
        command = _find_log_command(task_id, log_entries)

    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "error": "task_not_found"}

    original_ts = _parse_iso_ts(memory_entry.get("timestamp")) if isinstance(memory_entry, dict) else None
    snapshot_payload, snapshot_info = _find_snapshot_for_replay(original_ts)

    if memory_entry is None and snapshot_payload:
        memory_entry = _memory_entry_from_snapshot(snapshot_payload, task_id)

    original_decision = memory_entry.get("decision") if isinstance(memory_entry, dict) else None
    original_domains = memory_entry.get("domains") if isinstance(memory_entry, dict) else None

    domains = detect_domains(command)
    replayed_decision = decide_engine(command, domains)

    diff = _decision_diff(original_decision or {}, replayed_decision or {})

    snapshot_modules = None
    if isinstance(snapshot_payload, dict):
        files = snapshot_payload.get("files")
        if isinstance(files, dict):
            snapshot_modules = files.get("modules")

    with modules_lock:
        current_modules = list(LOADED_MODULES.keys())

    deterministic = snapshot_payload is not None
    deterministic_reason = "snapshot_matched" if snapshot_payload else "no_snapshot"
    if snapshot_modules is not None and isinstance(snapshot_modules, list):
        if sorted(snapshot_modules) != sorted(current_modules):
            deterministic = False
            deterministic_reason = "modules_changed"

    return {
        "ok": True,
        "task_id": task_id,
        "dry_run": bool(dry_run),
        # Ensure audits can explain non-determinism without touching runtime state.
        "deterministic": bool(deterministic),
        "deterministic_reason": deterministic_reason,
        "command": command,
        "domain_detection": {
            "original": original_domains,
            "replayed": domains,
        },
        "decision_trace": {
            "original": original_decision,
            "replayed": replayed_decision,
            "differences": diff,
        },
        "snapshot": {
            "used": snapshot_payload is not None,
            "info": snapshot_info,
        },
        "modules": {
            "original": snapshot_modules,
            "current": current_modules,
        },
    }

def _is_plan_command(command: str) -> bool:
    return (command or "").strip().lower().startswith("plan:")

def _clean_plan_subject(command: str) -> str:
    raw = (command or "").strip()
    if raw.lower().startswith("plan:"):
        raw = raw[5:]
    return raw.strip()

def _split_plan_items(subject: str) -> List[str]:
    if not subject:
        return []
    normalized = subject.replace("\n", " ").replace("\t", " ")
    parts: List[str] = []
    for chunk in normalized.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts.extend([c.strip() for c in chunk.split(".") if c.strip()])
    if not parts:
        parts = [subject.strip()]
    return parts

def generate_plan(command: str) -> List[str]:
    subject = _clean_plan_subject(command)
    items = _split_plan_items(subject)
    if not items:
        return ["Clarificar el objetivo y alcance exacto."]
    plan: List[str] = []
    for item in items:
        lowered = item.lower()
        if "revisar" in lowered or "analizar" in lowered:
            plan.append(f"Revisar contexto y requisitos: {item}.")
            plan.append("Identificar restricciones y dependencias clave.")
        elif "implementar" in lowered or "crear" in lowered:
            plan.append(f"Definir pasos de implementación para: {item}.")
            plan.append("Validar resultados con una comprobación rápida.")
        else:
            plan.append(f"Desglosar tarea: {item}.")
            plan.append("Verificar entregables mínimos esperados.")
    return [p for p in plan if p][:50]

def execute_scientific(command: str) -> Dict[str, Any]:
    return {"success": True, "result": {"echo": command, "note": "scientific_stub_ok"}}

def execute_general(command: str) -> Dict[str, Any]:
    return {"success": True, "result": (command or "").strip()}

def execute(command: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    mode = (decision or {}).get("mode", "general")
    if mode == "scientific":
        return execute_scientific(command)
    if mode == "ai_module":
        return execute_ai_module(command)
    return execute_general(command)

def obedient_execution(command: str, decision: Dict[str, Any]) -> Dict[str, Any]:
    if KILL_SWITCH.get("status") != "ARMED":
        return {"success": False, "error": "SYSTEM_HALTED"}
    if ROOT_GOAL != "EXECUTE_USER_COMMANDS_ONLY":
        KILL_SWITCH["status"] = "TRIGGERED"
        log_event("KILL_SWITCH", {"reason": "ROOT_GOAL_VIOLATION"})
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}

    with state_lock:
        AETHER_STATE["energy"] = max(0, int(AETHER_STATE.get("energy", 0)) - 1)
        AETHER_STATE["last_cycle"] = safe_now()
        AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
        save_json_atomic(STATE_FILE, AETHER_STATE)

    return execute(command, decision)

def run_now(
    command: str,
    source: str = "chat",
    origin: Optional[str] = None,
    task_type_override: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    command = (command or "").strip()
    # NIVEL 49: guard de decisión central (tarea válida o bloqueo seguro)
    if not command or not any(ch.isalnum() for ch in command):
        log_event(
            "DECISION_GUARD_BLOCK",
            {"command": command, "source": source, "origin": origin, "reason": "invalid_or_incomplete"},
        )
        update_dashboard()
        return {"mode": "blocked"}, {"success": False, "error": "invalid_task"}
    allowed_owner, owner_command, owner_block = _owner_only_gate(command)
    if not allowed_owner:
        log_event(
            "OWNER_ONLY_BLOCK_EXEC",
            {"command": command, "source": source, "origin": origin, "reason": "owner_only"},
        )
        update_dashboard()
        return {"mode": "blocked"}, {"success": False, "error": owner_block.get("error"), "hint": owner_block.get("hint")}
    command = owner_command
    zone = resolve_zone(source, origin)
    inferred_type = (task_type_override or "").strip() or _infer_task_type(command, source)
    stability = evaluate_stability()
    stability_mode = stability.get("mode")
    if stability_mode == "NEEDS_HUMAN":
        return {"mode": "blocked"}, {"success": False, "error": "STABILITY_NEEDS_HUMAN"}
    if stability_mode == "PAUSED":
        return {"mode": "blocked"}, {"success": False, "error": "STABILITY_PAUSED"}
    if stability_mode == "DEGRADED":
        if not _is_plan_command(command) and inferred_type != "read_only":
            return {"mode": "blocked"}, {"success": False, "error": "STABILITY_DEGRADED"}
    allowed, reason, specials = _trust_zone_allowed(zone, inferred_type, command)
    if not allowed:
        log_event(
            "TRUST_ZONE_BLOCK_EXEC",
            {
                "command": command,
                "source": source,
                "origin": origin,
                "zone": zone,
                "task_type": inferred_type,
                "reason": reason,
                "special": specials,
            },
        )
        update_dashboard()
        return {"mode": "blocked"}, {"success": False, "error": "TRUST_ZONE_BLOCKED"}

    if _is_plan_command(command):
        subtasks = generate_plan(command)
        decision = {"mode": "planner", "confidence": 1.0}
        result = {"success": True, "result": {"subtasks": subtasks, "note": "planner_only"}}
        record_strategy(command, "planner", True)

        with memory_lock:
            AETHER_MEMORY.append(
                {
                    "task_id": str(uuid.uuid4()),
                    "command": command,
                    "domains": ["planner"],
                    "decision": decision,
                    "results": [result],
                    "timestamp": safe_now(),
                    "source": source,
                }
            )
            if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
                AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
            save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

        log_event("PLANNER_RUN", {"command": command, "subtasks": len(subtasks)})
        update_dashboard()
        return decision, result

    if is_frozen():
        log_event("FREEZE_BLOCK_CHAT", {"command": command})
        update_dashboard()
        return {"mode": "frozen"}, {"success": False, "error": "SYSTEM_FROZEN"}

    domains = detect_domains(command)
    decision = decide_engine(command, domains)

    if safe_mode_enabled() and decision.get("mode") != "ai_module":
        log_event("SAFE_MODE_BLOCK_RUN", {"command": command, "source": source, "mode": decision.get("mode")})
        update_dashboard()
        return {"mode": "safe_mode"}, {"success": False, "error": "SAFE_MODE_ON"}

    result = obedient_execution(command, decision)
    success = bool(result.get("success"))

    record_strategy(command, decision.get("mode", "unknown"), success)

    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": str(uuid.uuid4()),
                "command": command,
                "domains": domains,
                "decision": decision,
                "results": [result],
                "timestamp": safe_now(),
                "source": source,
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    log_event("CHAT_RUN", {"command": command, "success": success, "mode": decision.get("mode")})
    update_dashboard()
    return decision, result

def run_project_task(task_id: str) -> Dict[str, Any]:
    task: Optional[Dict[str, Any]] = None
    with tasks_lock:
        for t in AETHER_TASKS:
            if t.get("id") == task_id:
                task = t
                break
    if not task:
        return {"ok": False, "error": "task_not_found"}

    allowed, reason = can_run_project_task(task)
    if not allowed:
        log_event("PROJECT_TASK_BLOCKED", {"task_id": task_id, "reason": reason})
        update_dashboard()
        return {"ok": False, "error": reason}

    with tasks_lock:
        task["status"] = "RUNNING"
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    decision, result = run_now(
        task.get("command") or "",
        source="orchestrator",
        origin="run_project_task",
        task_type_override=task.get("task_type"),
    )
    success = bool(result.get("success"))
    subtasks = _extract_subtasks_from_result(result)

    with tasks_lock:
        task["last_run"] = safe_now()
        task["last_success"] = success
        task["last_result"] = result
        task["subtasks"] = subtasks
        if success:
            task["status"] = "DONE"
        else:
            task["retry_count"] = int(task.get("retry_count", 0)) + 1
            task["status"] = "FAILED"
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

    log_event("PROJECT_TASK_RUN", {"task_id": task_id, "success": success, "subtasks": len(subtasks)})
    update_dashboard()
    return {"ok": True, "decision": decision, "result": result, "subtasks": subtasks}

# -----------------------------
# WORKER + SCHEDULER (threads)
# -----------------------------
STOP_EVENT = threading.Event()

def _store_memory_event(task_id: str, command: str, decision: Dict[str, Any], result: Dict[str, Any], source: str) -> None:
    with memory_lock:
        AETHER_MEMORY.append(
            {
                "task_id": task_id,
                "command": command,
                "decision": decision,
                "results": [result],
                "timestamp": safe_now(),
                "source": source,
            }
        )
        if len(AETHER_MEMORY) > MAX_MEMORY_ENTRIES:
            AETHER_MEMORY[:] = AETHER_MEMORY[-MAX_MEMORY_ENTRIES:]
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

class IsolatedWorker(threading.Thread):
    def __init__(self, task: Dict[str, Any]):
        super().__init__(daemon=True)
        self.task = copy.deepcopy(task)
        self.result: Dict[str, Any] = {}

    def run(self) -> None:
        try:
            command = (self.task.get("command") or "").strip()
            domains = detect_domains(command)
            decision = decide_engine(command, domains)
            execution = obedient_execution(command, decision)
            self.result = {
                "decision": decision,
                "domains": domains,
                "result": execution,
                "error": None,
            }
        except Exception as e:
            self.result = {
                "decision": {"mode": "error"},
                "domains": [],
                "result": {"success": False, "error": str(e)},
                "error": str(e),
            }

def _preflight_execution(command: str) -> Optional[Dict[str, Any]]:
    if KILL_SWITCH.get("status") != "ARMED":
        return {"success": False, "error": "SYSTEM_HALTED"}
    if ROOT_GOAL != "EXECUTE_USER_COMMANDS_ONLY":
        KILL_SWITCH["status"] = "TRIGGERED"
        log_event("KILL_SWITCH", {"reason": "ROOT_GOAL_VIOLATION"})
        return {"success": False, "error": "ROOT_GOAL_VIOLATION"}
    return None

def process_task(task: Dict[str, Any]) -> None:
    command = (task.get("command") or "").strip()
    task_id = task.get("id", "unknown")
    task_type = (task.get("task_type") or "analysis").strip()
    mode = _task_mode(task)
    zone = (task.get("zone") or "").strip()
    origin = task.get("origin")
    stability = evaluate_stability()
    stability_mode = stability.get("mode")
    if stability_mode in {"NEEDS_HUMAN", "PAUSED", "DEGRADED"}:
        allow_internal = stability_mode == "PAUSED" and zone == "INTERNAL" and task_type == "read_only"
        allow_degraded = stability_mode == "DEGRADED" and task_type == "read_only"
        if not (allow_internal or allow_degraded):
            result = {"success": False, "error": f"STABILITY_{stability_mode}"}
            decision = {"mode": "blocked"}
            _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
            log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": f"STABILITY_{stability_mode}"})
            update_dashboard()
            return

    if zone not in TRUST_ZONES:
        result = {"success": False, "error": "INVALID_ZONE"}
        decision = {"mode": "blocked"}
        log_event(
            "TRUST_ZONE_BLOCK_EXEC",
            {
                "task_id": task_id,
                "command": command,
                "source": task.get("source"),
                "origin": origin,
                "zone": zone,
                "task_type": task_type,
                "reason": "missing_or_invalid_zone",
            },
        )
        _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": "INVALID_ZONE"})
        update_dashboard()
        return

    resolved_zone = resolve_zone(task.get("source", ""), origin)
    if resolved_zone != zone:
        result = {"success": False, "error": "ZONE_MISMATCH"}
        decision = {"mode": "blocked"}
        log_event(
            "TRUST_ZONE_BLOCK_EXEC",
            {
                "task_id": task_id,
                "command": command,
                "source": task.get("source"),
                "origin": origin,
                "zone": zone,
                "resolved_zone": resolved_zone,
                "task_type": task_type,
                "reason": "zone_mismatch",
            },
        )
        _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": "ZONE_MISMATCH"})
        update_dashboard()
        return

    allowed, reason, specials = _trust_zone_allowed(zone, task_type, command)
    if not allowed:
        result = {"success": False, "error": "TRUST_ZONE_BLOCKED"}
        decision = {"mode": "blocked"}
        log_event(
            "TRUST_ZONE_BLOCK_EXEC",
            {
                "task_id": task_id,
                "command": command,
                "source": task.get("source"),
                "origin": origin,
                "zone": zone,
                "task_type": task_type,
                "reason": reason,
                "special": specials,
            },
        )
        _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": "TRUST_ZONE_BLOCKED"})
        update_dashboard()
        return

    # Level 40: Policy gate (task_type permissions)
    if not can_execute(task_type, mode):
        result = {"success": False, "error": "PERMISSION_DENIED"}
        decision = {"mode": "blocked"}
        log_event("TASK_PERMISSION_DENIED", {"task_id": task_id, "task_type": task_type, "mode": mode})
        _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": "PERMISSION_DENIED"})
        update_dashboard()
        return

    # Level 41: Integrity gate (HMAC signature)
    if not verify_task(task):
        result = {"success": False, "error": "INVALID_SIGNATURE"}
        decision = {"mode": "blocked"}
        log_event("TASK_INVALID_SIGNATURE", {"task_id": task_id})
        _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": "INVALID_SIGNATURE"})
        update_dashboard()
        return

    preflight_error = _preflight_execution(command)
    if preflight_error:
        decision = {"mode": "blocked"}
        _store_memory_event(task_id, command, decision, preflight_error, task.get("source", "queue"))
        log_event("TASK_FAILED", {"task_id": task_id, "command": command, "error": preflight_error.get("error")})
        update_dashboard()
        return

    with state_lock:
        AETHER_STATE["status"] = "WORKING"
        AETHER_STATE["energy"] = max(0, int(AETHER_STATE.get("energy", 0)) - 1)
        AETHER_STATE["last_cycle"] = safe_now()
        AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
        save_json_atomic(STATE_FILE, AETHER_STATE)

    log_event("TASK_START", {"task_id": task_id, "command": command, "task_type": task_type, "mode": mode})

    # Level 42: Isolated worker with deepcopy + timeout
    worker = IsolatedWorker(task)
    worker.start()
    timeout = max(1, int(AETHER_TASK_TIMEOUT_SEC))
    worker.join(timeout)

    if worker.is_alive():
        decision = {"mode": "timeout"}
        result = {"success": False, "error": "TIMEOUT"}
        log_event("TASK_TIMEOUT", {"task_id": task_id, "timeout_sec": timeout})
    else:
        decision = worker.result.get("decision") or {"mode": "unknown"}
        result = worker.result.get("result") or {"success": False, "error": "NO_RESULT"}

    success = bool(result.get("success"))
    record_strategy(command, decision.get("mode", "unknown"), success)
    _store_memory_event(task_id, command, decision, result, task.get("source", "queue"))
    log_event("TASK_DONE", {"task_id": task_id, "command": command, "success": success})
    update_dashboard()

def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))

def _recent_error_stats(now_ts: float) -> Tuple[int, int]:
    window_start = now_ts - THROTTLE_ERROR_WINDOW_SEC
    burst_start = now_ts - THROTTLE_BURST_WINDOW_SEC
    recent_errors = 0
    burst_errors = 0
    with log_lock:
        entries = list(AETHER_LOGS)
    for entry in reversed(entries):
        ts = entry.get("timestamp")
        if not isinstance(ts, str):
            continue
        try:
            entry_ts = datetime.fromisoformat(ts).timestamp()
        except Exception:
            continue
        if entry_ts < window_start:
            break
        if entry.get("type") in THROTTLE_ERROR_TYPES:
            recent_errors += 1
            if entry_ts >= burst_start:
                burst_errors += 1
    return recent_errors, burst_errors

def _compute_throttle_health() -> Tuple[float, List[str], bool]:
    reasons: List[str] = []
    now_ts = time.time()
    recent_errors, burst_errors = _recent_error_stats(now_ts)
    if recent_errors:
        reasons.append(f"errors_last_{THROTTLE_ERROR_WINDOW_SEC}s:{recent_errors}")
    if burst_errors:
        reasons.append(f"errors_last_{THROTTLE_BURST_WINDOW_SEC}s:{burst_errors}")

    queue_size = TASK_QUEUE.qsize()
    if queue_size:
        reasons.append(f"queue:{queue_size}")

    with state_lock:
        energy = int(AETHER_STATE.get("energy", 0))
    if energy < 40:
        reasons.append(f"energy:{energy}")

    if safe_mode_enabled():
        reasons.append("safe_mode")
    if is_frozen():
        reasons.append("freeze")

    score = 1.0
    score -= min(0.6, recent_errors * 0.08)
    score -= min(0.25, max(0, queue_size - 2) * 0.03)
    if energy < 60:
        score -= min(0.3, (60 - energy) * 0.01)
    if safe_mode_enabled():
        score -= 0.2
    if is_frozen():
        score -= 0.2
    score = _clamp(score, 0.1, 1.0)
    burst = burst_errors >= THROTTLE_BURST_COUNT
    return score, reasons, burst

def _step_toward(current: float, target: float, step_frac: float = 0.2) -> float:
    return current + (target - current) * step_frac

def update_throttle_state() -> Dict[str, Any]:
    now_ts = time.time()
    score, reasons, burst = _compute_throttle_health()
    scale = _clamp(score, 0.2, 1.0)

    base_budget = max(1, int(AETHER_TASK_BUDGET))
    target_budget = int(_clamp(round(base_budget * scale), 1, max(1, int(AETHER_TASK_BUDGET_MAX))))
    target_tick = _clamp(BASE_WORKER_TICK_SEC / scale, WORKER_TICK_MIN_SEC, WORKER_TICK_MAX_SEC)
    target_sched = _clamp(BASE_SCHED_SLEEP_SEC / scale, SCHED_SLEEP_MIN_SEC, SCHED_SLEEP_MAX_SEC)
    target_heartbeat = int(
        _clamp(int(round(HEARTBEAT_INTERVAL_SEC / scale)), HEARTBEAT_INTERVAL_MIN_SEC, HEARTBEAT_INTERVAL_MAX_SEC)
    )

    with throttle_lock:
        current_budget = int(THROTTLE_STATE.get("effective_budget", base_budget))
        current_tick = float(THROTTLE_STATE.get("effective_tick_sec", BASE_WORKER_TICK_SEC))
        current_sched = float(THROTTLE_STATE.get("effective_sched_sleep_sec", BASE_SCHED_SLEEP_SEC))
        current_heartbeat = int(THROTTLE_STATE.get("effective_heartbeat_interval", HEARTBEAT_INTERVAL_SEC))
        last_change_ts = float(THROTTLE_STATE.get("last_change_ts") or 0.0)
        stable_since_ts = THROTTLE_STATE.get("stable_since_ts")
        cooldown_until = float(THROTTLE_STATE.get("cooldown_until_ts") or 0.0)
        last_state_log_ts = float(THROTTLE_STATE.get("last_state_log_ts") or 0.0)

        if score >= THROTTLE_UP_THRESHOLD:
            if stable_since_ts is None:
                stable_since_ts = now_ts
        else:
            stable_since_ts = None

        allow_up = (
            stable_since_ts is not None
            and (now_ts - stable_since_ts) >= THROTTLE_STABLE_SEC
            and now_ts >= cooldown_until
        )

        mode = "normal"
        changed = False
        if burst:
            mode = "burst"
            cooldown_until = max(cooldown_until, now_ts + THROTTLE_COOLDOWN_SEC)
            if target_budget < current_budget:
                current_budget = target_budget
                changed = True
            if target_tick > current_tick:
                current_tick = target_tick
                changed = True
            if target_sched > current_sched:
                current_sched = target_sched
                changed = True
            if target_heartbeat > current_heartbeat:
                current_heartbeat = target_heartbeat
                changed = True
        else:
            if score < THROTTLE_DOWN_THRESHOLD:
                mode = "throttled"
                cooldown_until = max(cooldown_until, now_ts + THROTTLE_COOLDOWN_SEC)
                if target_budget < current_budget:
                    current_budget = target_budget
                    changed = True
                if target_tick > current_tick:
                    current_tick = target_tick
                    changed = True
                if target_sched > current_sched:
                    current_sched = target_sched
                    changed = True
                if target_heartbeat > current_heartbeat:
                    current_heartbeat = target_heartbeat
                    changed = True
            else:
                if allow_up:
                    if target_budget > current_budget:
                        current_budget = min(target_budget, current_budget + 1)
                        changed = True
                    if target_tick < current_tick:
                        current_tick = max(target_tick, _step_toward(current_tick, target_tick))
                        changed = True
                    if target_sched < current_sched:
                        current_sched = max(target_sched, _step_toward(current_sched, target_sched))
                        changed = True
                    if target_heartbeat < current_heartbeat:
                        current_heartbeat = max(target_heartbeat, int(_step_toward(current_heartbeat, target_heartbeat)))
                        changed = True

        current_budget = int(_clamp(current_budget, 1, max(1, int(AETHER_TASK_BUDGET_MAX))))
        current_tick = float(_clamp(current_tick, WORKER_TICK_MIN_SEC, WORKER_TICK_MAX_SEC))
        current_sched = float(_clamp(current_sched, SCHED_SLEEP_MIN_SEC, SCHED_SLEEP_MAX_SEC))
        current_heartbeat = int(_clamp(current_heartbeat, HEARTBEAT_INTERVAL_MIN_SEC, HEARTBEAT_INTERVAL_MAX_SEC))

        if changed or mode != THROTTLE_STATE.get("mode"):
            THROTTLE_STATE["last_change"] = safe_now()
            THROTTLE_STATE["last_change_ts"] = now_ts
            event_type = "THROTTLE_DOWN" if mode in {"throttled", "burst"} else "THROTTLE_UP"
            log_event(
                event_type,
                {
                    "mode": mode,
                    "score": round(score, 3),
                    "effective_budget": current_budget,
                    "effective_sched_sleep_sec": current_sched,
                    "effective_tick_sec": current_tick,
                    "effective_heartbeat_interval": current_heartbeat,
                    "reasons": reasons,
                },
            )
            changed = True

        if (now_ts - last_state_log_ts) >= THROTTLE_STATE_LOG_SEC:
            THROTTLE_STATE["last_state_log_ts"] = now_ts
            log_event(
                "THROTTLE_STATE",
                {
                    "mode": mode,
                    "score": round(score, 3),
                    "effective_budget": current_budget,
                    "effective_sched_sleep_sec": current_sched,
                    "effective_tick_sec": current_tick,
                    "effective_heartbeat_interval": current_heartbeat,
                    "reasons": reasons,
                },
            )

        THROTTLE_STATE.update(
            {
                "score": round(score, 3),
                "mode": mode,
                "effective_budget": current_budget,
                "effective_tick_sec": current_tick,
                "effective_sched_sleep_sec": current_sched,
                "effective_heartbeat_interval": current_heartbeat,
                "stable_since_ts": stable_since_ts,
                "cooldown_until_ts": cooldown_until,
                "reasons": reasons,
            }
        )
        return dict(THROTTLE_STATE)

def task_worker() -> None:
    while not STOP_EVENT.is_set():
        try:
            if safe_mode_enabled():
                with state_lock:
                    AETHER_STATE["status"] = "SAFE_MODE"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
                update_dashboard()
                time.sleep(1.0)
                continue

            if not AETHER_TASK_RUNNER_ENABLED:
                time.sleep(1.0)
                continue

            if is_frozen():
                with state_lock:
                    AETHER_STATE["status"] = "FROZEN"
                    save_json_atomic(STATE_FILE, AETHER_STATE)
                update_dashboard()
                time.sleep(1.0)
                continue

            throttle = update_throttle_state()
            budget = max(1, int(throttle.get("effective_budget", AETHER_TASK_BUDGET)))
            processed = 0

            while processed < budget and not TASK_QUEUE.empty():
                _, task = TASK_QUEUE.get()
                # GUARD 47.2: anti-freeze del loop, continuar si algo falla
                try:
                    try:
                        process_task(task)
                    except Exception as e:
                        try:
                            log_event("TASK_LOOP_GUARD", {"error": str(e), "task": task.get("command")})
                        except Exception:
                            pass
                finally:
                    with queue_lock:
                        QUEUE_SET.discard((task.get("command") or "").strip())
                    TASK_QUEUE.task_done()
                processed += 1

            if processed == 0:
                with state_lock:
                    AETHER_STATE["status"] = "IDLE"
                    save_json_atomic(STATE_FILE, AETHER_STATE)

            update_dashboard()
            tick_sleep = float(throttle.get("effective_tick_sec", BASE_WORKER_TICK_SEC))
            time.sleep(max(WORKER_TICK_MIN_SEC, tick_sleep))
        except Exception as e:
            log_event("WORKER_ERROR", {"error": str(e)})
            time.sleep(1.0)

def scheduler_loop() -> None:
    while not STOP_EVENT.is_set():
        try:
            if safe_mode_enabled():
                time.sleep(1.0)
                continue

            if is_frozen():
                time.sleep(1.0)
                continue
            throttle = update_throttle_state()
            heartbeat_interval = int(throttle.get("effective_heartbeat_interval", HEARTBEAT_INTERVAL_SEC))

            # heartbeat enqueue
            if AETHER_HEARTBEAT_ENABLED:
                now_ts = datetime.now(timezone.utc).timestamp()
                with state_lock:
                    last_ts = AETHER_STATE.get("last_heartbeat_ts")
                    energy = int(AETHER_STATE.get("energy", 0))
                interval_ok = last_ts is None or (now_ts - float(last_ts)) >= heartbeat_interval
                if interval_ok and energy >= HEARTBEAT_MIN_ENERGY and not tasks_queue_contains(HEARTBEAT_CMD):
                    r = enqueue_task(
                        HEARTBEAT_CMD,
                        priority=10,
                        source="internal",
                        task_type="read_only",
                        origin="scheduler_loop",
                    )
                    if isinstance(r, dict) and r.get("ok"):
                        with state_lock:
                            AETHER_STATE["last_heartbeat_ts"] = now_ts
                            save_json_atomic(STATE_FILE, AETHER_STATE)

            with state_lock:
                AETHER_STATE["last_cycle"] = safe_now()
                AETHER_STATE["focus"] = "RECOVERY" if int(AETHER_STATE.get("energy", 0)) < 20 else "ACTIVE"
                save_json_atomic(STATE_FILE, AETHER_STATE)

            run_internal_tasks(throttle)
            update_dashboard()
            sched_sleep = float(throttle.get("effective_sched_sleep_sec", BASE_SCHED_SLEEP_SEC))
            time.sleep(max(SCHED_SLEEP_MIN_SEC, sched_sleep))
        except Exception as e:
            log_event("SCHEDULER_ERROR", {"error": str(e)})
            time.sleep(2.0)

# -----------------------------
# WATCHDOG (stall detector)
# -----------------------------

def _parse_iso_ts(value: Optional[str]) -> Optional[float]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return None

def watchdog_loop() -> None:
    last_seen_cycle = None
    last_progress_ts = time.time()
    while not STOP_EVENT.is_set():
        try:
            with state_lock:
                current_cycle = AETHER_STATE.get("last_cycle")
            if current_cycle and current_cycle != last_seen_cycle:
                last_seen_cycle = current_cycle
                last_progress_ts = time.time()

            now_ts = time.time()
            last_cycle_ts = _parse_iso_ts(current_cycle)
            elapsed_since_progress = now_ts - last_progress_ts
            elapsed_since_cycle = now_ts - last_cycle_ts if last_cycle_ts else elapsed_since_progress

            limit = max(0, int(AETHER_WATCHDOG_SEC))
            grace = max(0, int(AETHER_WATCHDOG_GRACE_SEC))
            if limit > 0 and (elapsed_since_progress >= limit + grace or elapsed_since_cycle >= limit + grace):
                if not safe_mode_enabled():
                    enable_safe_mode("WATCHDOG_STALL")
                time.sleep(1.0)
                continue

            time.sleep(2.0)
        except Exception:
            time.sleep(2.0)

# -----------------------------
# CRASH RECOVERY BRAIN (v46)
# -----------------------------

_RECOVERY_RAN = False

def _detect_unclean_shutdown() -> Tuple[bool, str]:
    # Conservative signals only: incomplete tasks or WORKING state from last run.
    with tasks_lock:
        running = [t for t in AETHER_TASKS if t.get("status") == "RUNNING"]
    if running:
        return True, "running_tasks"
    with state_lock:
        status = AETHER_STATE.get("status")
    if status == "WORKING":
        return True, "state_working"
    return False, "clean_shutdown"

def _latest_snapshot_payload() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    best_payload = None
    best_key = None
    best_ts = None
    for name in snapshot_list():
        payload = load_json(_snapshot_path(name), None)
        if not isinstance(payload, dict) or not payload.get("ok"):
            continue
        created_ts = _parse_iso_ts(payload.get("created_at"))
        if created_ts is None:
            try:
                created_ts = os.path.getmtime(_snapshot_path(name))
            except Exception:
                created_ts = None
        if created_ts is None:
            continue
        if best_ts is None or created_ts > best_ts:
            best_ts = created_ts
            best_payload = payload
            best_key = name
    return best_payload, best_key

def _apply_recovery_payload(payload: Dict[str, Any]) -> None:
    files = payload.get("files", {}) if isinstance(payload, dict) else {}
    st = files.get("state", dict(DEFAULT_STATE))
    mem = files.get("memory", [])
    strat = files.get("strategic", {"patterns": {}, "failures": {}, "history": [], "last_update": None})
    logs = files.get("logs", [])
    projects = files.get("projects", [])
    tasks = files.get("tasks", [])

    with state_lock:
        prev_energy = AETHER_STATE.get("energy", DEFAULT_STATE.get("energy", 100))
        AETHER_STATE.clear()
        AETHER_STATE.update(st if isinstance(st, dict) else dict(DEFAULT_STATE))
        # Preserve energy to avoid unintended budget shifts during recovery.
        AETHER_STATE["energy"] = prev_energy
        AETHER_STATE["version"] = AETHER_VERSION
        save_json_atomic(STATE_FILE, AETHER_STATE)

    with memory_lock:
        AETHER_MEMORY.clear()
        if isinstance(mem, list):
            AETHER_MEMORY.extend(mem)
        save_json_atomic(MEMORY_FILE, AETHER_MEMORY)

    with strategic_lock:
        STRATEGIC_MEMORY.clear()
        STRATEGIC_MEMORY.update(
            strat if isinstance(strat, dict) else {"patterns": {}, "failures": {}, "history": [], "last_update": None}
        )
        save_json_atomic(STRATEGIC_FILE, STRATEGIC_MEMORY)

    with log_lock:
        AETHER_LOGS.clear()
        if isinstance(logs, list):
            AETHER_LOGS.extend(logs)
        save_json_atomic(LOG_FILE, AETHER_LOGS)

    with projects_lock:
        AETHER_PROJECTS.clear()
        if isinstance(projects, list) and projects:
            AETHER_PROJECTS.extend(projects)
        else:
            AETHER_PROJECTS.extend(list(DEFAULT_PROJECTS))
        save_json_atomic(PROJECTS_FILE, AETHER_PROJECTS)

    with tasks_lock:
        AETHER_TASKS.clear()
        if isinstance(tasks, list):
            AETHER_TASKS.extend(tasks)
        _normalize_tasks_locked()
        save_json_atomic(TASKS_FILE, AETHER_TASKS)

def _mark_recovered_tasks() -> int:
    recovered = 0
    with tasks_lock:
        for task in AETHER_TASKS:
            if task.get("status") == "RUNNING":
                # Preserve retry_count/metadata; only update status for safety.
                task["status"] = "RECOVERED"
                recovered += 1
        if recovered:
            save_json_atomic(TASKS_FILE, AETHER_TASKS)
    return recovered

def crash_recovery_brain() -> Dict[str, Any]:
    global _RECOVERY_RAN
    if _RECOVERY_RAN:
        return {"recovered": False, "reason": "already_ran", "restored_from": "state", "tasks_recovered": 0, "timestamp": safe_now()}
    _RECOVERY_RAN = True

    unclean, reason = _detect_unclean_shutdown()
    restored_from = "state"
    if unclean:
        snapshot_payload, snap_name = _latest_snapshot_payload()
        if snapshot_payload:
            _apply_recovery_payload(snapshot_payload)
            restored_from = "snapshot"
            reason = f"{reason}:{snap_name or 'latest'}"

    tasks_recovered = _mark_recovered_tasks() if unclean else 0
    report = {
        "recovered": bool(unclean),
        "reason": reason,
        "restored_from": restored_from,
        "tasks_recovered": int(tasks_recovered),
        "timestamp": safe_now(),
    }
    log_event("RECOVERY_EVENT", report)
    return report

# -----------------------------
# UI HELPERS
# -----------------------------

def ui_status() -> str:
    with state_lock:
        s = dict(AETHER_STATE)
    with modules_lock:
        mods = list(LOADED_MODULES.keys())
    with strategic_lock:
        patterns = STRATEGIC_MEMORY.get("patterns", {})
        failures = STRATEGIC_MEMORY.get("failures", {})
        hist = STRATEGIC_MEMORY.get("history", [])
        st = {
            "patterns": len(patterns) if isinstance(patterns, dict) else 0,
            "failures": len(failures) if isinstance(failures, dict) else 0,
            "last_update": STRATEGIC_MEMORY.get("last_update"),
            "history_len": len(hist) if isinstance(hist, list) else 0,
        }
    with throttle_lock:
        throttle_snapshot = {
            "score": THROTTLE_STATE.get("score"),
            "mode": THROTTLE_STATE.get("mode"),
            "effective_budget": THROTTLE_STATE.get("effective_budget"),
            "effective_sched_sleep_sec": THROTTLE_STATE.get("effective_sched_sleep_sec"),
            "last_change": THROTTLE_STATE.get("last_change"),
            "reasons": THROTTLE_STATE.get("reasons"),
        }
    trust_zone_summary = {
        "blocks": _summarize_trust_zone_blocks(),
        "policy": _trust_zone_policy_snapshot(),
    }
    diagnosis = get_self_diagnosis()
    diagnosis_summary = _diagnosis_summary(diagnosis)
    stability = evaluate_stability()
    snapshots = snapshot_list()
    return json.dumps(
        {
            "state": s,
            "queue_size": TASK_QUEUE.qsize(),
            "memory_len": len(AETHER_MEMORY),
            "strategic": st,
            "kill_switch": KILL_SWITCH,
            "modules": mods,
            "data_dir": DATA_DIR,
            "version": AETHER_VERSION,
            "freeze": FREEZE_STATE,
            "safe_mode": dict(SAFE_MODE),
            "watchdog": {
                "watchdog_sec": int(AETHER_WATCHDOG_SEC),
                "watchdog_grace_sec": int(AETHER_WATCHDOG_GRACE_SEC),
            },
            "throttle": throttle_snapshot,
            "orchestrator_policy": ORCHESTRATOR_POLICY,
            "projects_count": len(AETHER_PROJECTS),
            "tasks_count": len(AETHER_TASKS),
            "tasks_status": _task_status_counts(),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            "demo1_exists": "demo1" in snapshots,
            "snapshots": snapshots,
            "trust_zone": trust_zone_summary,
            "diagnosis": diagnosis_summary,
            "stability": {
                "mode": stability.get("mode"),
                "reasons": stability.get("reasons"),
                "since": stability.get("since"),
            },
        },
        indent=2,
        ensure_ascii=False,
    )

def ui_enqueue(cmd: str, prio: int) -> Tuple[str, str]:
    r = enqueue_task(cmd, int(prio), source="ui", origin="ui_enqueue")
    status_text = f"ENQUEUE_RESULT={json.dumps(r, ensure_ascii=False)}\n\n{ui_status()}"
    return status_text, ui_tail_logs()

def ui_reload_modules() -> str:
    mods = reload_ai_modules()
    return f"RELOADED={mods}\n\n{ui_status()}"

def ui_tail_logs(n: int = 50) -> str:
    try:
        n = int(n)
    except Exception:
        n = 50
    with log_lock:
        tail = AETHER_LOGS[-n:]
    return "\n".join(json.dumps(x, ensure_ascii=False) for x in tail)

def ui_tick(logs_n: int = 50) -> Tuple[str, str]:
    return ui_status(), ui_tail_logs(logs_n)

def ui_snapshot_list() -> str:
    return json.dumps({"snapshots": snapshot_list()}, indent=2, ensure_ascii=False)

def ui_snapshot_create(name: str) -> str:
    return json.dumps(snapshot_create(name), indent=2, ensure_ascii=False)

def ui_snapshot_restore(name: str) -> str:
    return json.dumps(snapshot_restore(name), indent=2, ensure_ascii=False)

def ui_snapshot_export(name: str) -> str:
    return snapshot_export(name)

def ui_snapshot_import(txt: str) -> str:
    return json.dumps(snapshot_import(txt), indent=2, ensure_ascii=False)

def ui_replica_export(name: str) -> str:
    return replica_export(name or "replica")

def ui_replica_import(txt: str) -> str:
    res = replica_import(txt, apply_now=True)
    return json.dumps(res, indent=2, ensure_ascii=False)

def _project_choices():
    projects = list_projects()
    return [(p.get("name", p.get("id")), p.get("id")) for p in projects if p.get("id")]

def _default_project_value():
    for _, pid in _project_choices():
        if pid == "default":
            return pid
    choices = _project_choices()
    return choices[0][1] if choices else None

def _task_choices(project_id: str):
    tasks = list_tasks(project_id)
    out = []
    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        status = t.get("status", "PENDING")
        rc = t.get("retry_count", 0)
        label = t.get("command", tid)
        out.append((f"[{status}][r{rc}] {label}", tid))
    return out

def ui_refresh_projects():
    return gr.update(choices=_project_choices(), value=_default_project_value())

def ui_refresh_tasks(project_id):
    choices = _task_choices(project_id)
    value = choices[0][1] if choices else None
    return gr.update(choices=choices, value=value)

def ui_add_project(name):
    res = add_project(name)
    return json.dumps(res, indent=2, ensure_ascii=False), gr.update(choices=_project_choices(), value=_default_project_value())

def ui_add_task(project_id, command):
    res = add_task(project_id, command)
    choices = _task_choices(project_id)
    value = choices[0][1] if choices else None
    return json.dumps(res, indent=2, ensure_ascii=False), gr.update(choices=choices, value=value)

def ui_run_task(task_id):
    res = run_project_task(task_id)
    return json.dumps(res, indent=2, ensure_ascii=False)

# -----------------------------
# CHAT HELPERS (messages history)
# -----------------------------

def format_reply(decision: Dict[str, Any], result: Dict[str, Any]) -> str:
    if not result.get("success"):
        if result.get("error") == "SYSTEM_FROZEN":
            return "Sistema congelado (freeze ON). Desactiva AETHER_FREEZE_MODE para ejecutar."
        if result.get("error") == "SAFE_MODE_ON":
            return "SAFE_MODE activo: ejecución externa bloqueada para diagnóstico."
        if result.get("error") == "STABILITY_NEEDS_HUMAN":
            return "⛔ Estabilidad crítica: se requiere intervención humana antes de ejecutar."
        if result.get("error") == "STABILITY_PAUSED":
            return "⏸️ Estabilidad en pausa: ejecución bloqueada (solo mantenimiento interno)."
        if result.get("error") == "STABILITY_DEGRADED":
            return "⚠️ Estabilidad degradada: solo lectura y planificación permitidas."
        return f"⛔ Error: {result.get('error', 'unknown_error')}"
    mode = (decision or {}).get("mode", "general")
    if mode == "planner":
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🧭 Plan propuesto (no ejecutado):\n\n{payload}"
    if mode == "ai_module":
        mod = result.get("module") or "ai_module"
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🧩 Plugin: {mod}\n\n{payload}"
    if mode == "scientific":
        payload = json.dumps(result.get("result"), indent=2, ensure_ascii=False)
        return f"🔬 Resultado científico:\n\n{payload}"
    val = result.get("result")
    if isinstance(val, (dict, list)):
        return json.dumps(val, indent=2, ensure_ascii=False)
    return str(val)

def _normalize_history_messages(history: Any) -> List[Dict[str, str]]:
    if not isinstance(history, list):
        return []
    messages: List[Dict[str, str]] = []
    for item in history:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
            if isinstance(role, str) and isinstance(content, str):
                if role in {"user", "assistant"}:
                    messages.append({"role": role, "content": content})
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            user_text, bot_text = item
            if isinstance(user_text, str):
                messages.append({"role": "user", "content": user_text})
            if isinstance(bot_text, str):
                messages.append({"role": "assistant", "content": bot_text})
    return messages

def _safe_read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default

def load_chat(view: str) -> List[Dict[str, str]]:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_chat.json")
        payload = _safe_read_json(path, [])
        return _normalize_history_messages(payload)
    except Exception:
        return []

def save_chat(view: str, history: Any) -> None:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_chat.json")
        payload = _normalize_history_messages(history)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception:
        return

def load_active(view: str) -> List[Dict[str, str]]:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_active.json")
        payload = _safe_read_json(path, [])
        return _normalize_history_messages(payload)
    except Exception:
        return []

def save_active(view: str, history: Any) -> None:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_active.json")
        payload = _normalize_history_messages(history)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception:
        return

def load_chats(view: str) -> List[Dict[str, Any]]:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_chats.json")
        payload = _safe_read_json(path, [])
        if not isinstance(payload, list):
            return []
        chats: List[Dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            history = _normalize_history_messages(item.get("history"))
            chat_id = item.get("id")
            title = item.get("title")
            ts = item.get("ts")
            if isinstance(chat_id, str) and isinstance(title, str) and isinstance(ts, str):
                chats.append(
                    {
                        "id": chat_id,
                        "title": title,
                        "ts": ts,
                        "history": history,
                        "hash": item.get("hash"),
                    }
                )
        return chats
    except Exception:
        return []

def save_chats(view: str, chats: List[Dict[str, Any]]) -> None:
    try:
        os.makedirs(UI_DATA_DIR, exist_ok=True)
        path = os.path.join(UI_DATA_DIR, f"{view}_chats.json")
        safe_payload: List[Dict[str, Any]] = []
        for item in chats:
            if not isinstance(item, dict):
                continue
            history = _normalize_history_messages(item.get("history"))
            chat_id = item.get("id")
            title = item.get("title")
            ts = item.get("ts")
            if isinstance(chat_id, str) and isinstance(title, str) and isinstance(ts, str):
                safe_payload.append(
                    {
                        "id": chat_id,
                        "title": title,
                        "ts": ts,
                        "history": history,
                        "hash": item.get("hash"),
                    }
                )
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(safe_payload, handle, ensure_ascii=False, indent=2)
    except Exception:
        return

def _snapshot_title() -> str:
    return f"Proyecto {datetime.now().strftime('%Y-%m-%d %H:%M')}"

def snapshot_current_to_list(view: str, history: Any, chats: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    history_messages = _normalize_history_messages(history)
    if not history_messages:
        return list(chats or load_chats(view))
    chat_list = list(chats or load_chats(view))
    history_hash = sha256_text(json.dumps(history_messages, ensure_ascii=False, sort_keys=True))
    if any(item.get("hash") == history_hash for item in chat_list):
        return chat_list
    chat_list.append(
        {
            "id": uuid.uuid4().hex[:8],
            "title": _snapshot_title(),
            "ts": safe_now(),
            "history": history_messages,
            "hash": history_hash,
        }
    )
    save_chats(view, chat_list)
    return chat_list

def _chat_choices(chats: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    choices: List[Tuple[str, str]] = []
    for item in chats:
        chat_id = item.get("id")
        title = item.get("title")
        ts = item.get("ts")
        if isinstance(chat_id, str) and isinstance(title, str):
            label = f"{title} · {ts}" if isinstance(ts, str) else title
            choices.append((label, chat_id))
    return choices

# PATCH 46: flujo unificado de guardas 47/48 (clasificación + mensaje seguro)
def _classify_chat_error(err: Exception) -> str:
    if isinstance(err, (ValueError, TypeError)):
        return "input"
    if isinstance(err, (RuntimeError, TimeoutError)):
        return "runtime"
    return "system"

def _format_chat_error(category: str) -> str:
    if category == "input":
        return "⚠️ Entrada inválida. Reformula tu solicitud."
    if category == "runtime":
        return "⚠️ Fallo durante la ejecución. Intenta de nuevo."
    return "⚠️ Error interno. El CORE sigue activo."

def _run_chat_guard(message: str) -> str:
    try:
        decision, result = run_now(message, source="chat", origin="chat_send")
        return format_reply(decision, result)
    except Exception as e:
        category = _classify_chat_error(e)
        try:
            log_event(
                "CHAT_GUARD_ERROR",
                {
                    "error": str(e),
                    "category": category,
                    "traceback": traceback.format_exc(),
                },
            )
        except Exception:
            pass
        return _format_chat_error(category)

def chat_send(message: str, history: Any):
    message = (message or "").strip()
    history_messages = _normalize_history_messages(history)
    if not message:
        return history_messages, history_messages, ""
    if message.lower() == "diagnose" or "why are you in safe mode" in message.lower():
        diagnosis = get_self_diagnosis()
        try:
            log_event("DIAGNOSE_REQUEST", {"source": "chat"})
        except Exception:
            pass
        payload = json.dumps(diagnosis, indent=2, ensure_ascii=False)
        history_messages.append({"role": "user", "content": message})
        history_messages.append({"role": "assistant", "content": payload})
        return history_messages, history_messages, ""
    # GUARD 47.1: blindaje total del chat para siempre responder
    try:
        decision, result = run_now(message, source="chat", origin="chat_send")
        reply = format_reply(decision, result)
    except Exception as e:
        try:
            log_event("CHAT_GUARD_ERROR", {"error": str(e)})
        except Exception:
            pass
        reply = "⚠️ Error interno. El CORE sigue activo."
    history_messages.append({"role": "user", "content": message})
    history_messages.append({"role": "assistant", "content": reply})
    return history_messages, history_messages, ""

def _format_plugin_reply(payload: Any) -> str:
    if payload is None:
        return "⚠️ Sin respuesta del módulo."
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    except Exception:
        return str(payload)

def ui_new_chat() -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    empty: List[Dict[str, str]] = []
    return empty, empty

def ui_new_builder_chat(
    history: Any, chats: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]], gr.update]:
    updated_chats = snapshot_current_to_list("builder", history, chats)
    empty: List[Dict[str, str]] = []
    save_active("builder", empty)
    return empty, empty, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)

def ui_new_scientific_chat(
    history: Any, chats: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]], gr.update]:
    updated_chats = snapshot_current_to_list("scientific", history, chats)
    empty: List[Dict[str, str]] = []
    save_active("scientific", empty)
    return empty, empty, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)

def ui_select_builder_chat(
    chat_id: Optional[str], history: Any, chats: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]], gr.update]:
    updated_chats = snapshot_current_to_list("builder", history, chats)
    if not chat_id:
        return history, history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)
    selected = next((item for item in updated_chats if item.get("id") == chat_id), None)
    if not selected:
        return history, history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)
    new_history = _normalize_history_messages(selected.get("history"))
    save_active("builder", new_history)
    return new_history, new_history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=chat_id)

def ui_select_scientific_chat(
    chat_id: Optional[str], history: Any, chats: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]], gr.update]:
    updated_chats = snapshot_current_to_list("scientific", history, chats)
    if not chat_id:
        return history, history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)
    selected = next((item for item in updated_chats if item.get("id") == chat_id), None)
    if not selected:
        return history, history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=None)
    new_history = _normalize_history_messages(selected.get("history"))
    save_active("scientific", new_history)
    return new_history, new_history, updated_chats, gr.update(choices=_chat_choices(updated_chats), value=chat_id)

def builder_chat_send(message: str, history: Any):
    message = (message or "").strip()
    history_messages = _normalize_history_messages(history)
    if not message:
        return history_messages, history_messages, ""
    command = f"builder: {message}"
    response = execute_ai_module(command)
    if response.get("success"):
        reply = _format_plugin_reply(response.get("result"))
    else:
        reply = response.get("error") or "⚠️ Error al ejecutar builder."
    history_messages.append({"role": "user", "content": message})
    history_messages.append({"role": "assistant", "content": reply})
    save_active("builder", history_messages)
    return history_messages, history_messages, ""

def scientific_chat_send(message: str, history: Any):
    message = (message or "").strip()
    history_messages = _normalize_history_messages(history)
    if not message:
        return history_messages, history_messages, ""
    command = f"scientific: {message}"
    response = execute_ai_module(command)
    if response.get("success"):
        reply = _format_plugin_reply(response.get("result"))
    else:
        reply = response.get("error") or "⚠️ Error al ejecutar scientific."
    history_messages.append({"role": "user", "content": message})
    history_messages.append({"role": "assistant", "content": reply})
    save_active("scientific", history_messages)
    return history_messages, history_messages, ""

# -----------------------------
# STARTUP (safe once)
# -----------------------------
_STARTED = False
_worker_thread = None
_sched_thread = None
_watchdog_thread = None

# -----------------------------
# STARTUP (safe once)
# -----------------------------

def start_aether() -> str:
    global _STARTED, _worker_thread, _sched_thread, _watchdog_thread
    if _STARTED:
        return "AETHER ya estaba iniciado."
    _STARTED = True

    init_state()
    ensure_demo1()
    # Level 46: Crash Recovery Brain runs once at startup before any workers.
    crash_recovery_brain()
    ensure_projects()
    reload_ai_modules()

    with state_lock:
        AETHER_STATE["version"] = AETHER_VERSION
        AETHER_STATE["focus"] = "ACTIVE"
        if safe_mode_enabled():
            AETHER_STATE["status"] = "SAFE_MODE"
        else:
            AETHER_STATE["status"] = "FROZEN" if is_frozen() else "IDLE"
        if int(AETHER_STATE.get("energy", 0)) <= 0:
            AETHER_STATE["energy"] = 80
        save_json_atomic(STATE_FILE, AETHER_STATE)

    _worker_thread = threading.Thread(target=task_worker, daemon=True)
    _worker_thread.start()

    _sched_thread = threading.Thread(target=scheduler_loop, daemon=True)
    _sched_thread.start()

    _watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    _watchdog_thread.start()

    if safe_mode_enabled():
        enable_safe_mode(SAFE_MODE.get("reason") or "ENV_ENABLED")

    log_event(
        "BOOT",
        {
            "version": AETHER_VERSION,
            "data_dir": DATA_DIR,
            "freeze_mode": bool(is_frozen()),
            "safe_mode": dict(SAFE_MODE),
            "heartbeat_enabled": bool(AETHER_HEARTBEAT_ENABLED),
            "task_runner_enabled": bool(AETHER_TASK_RUNNER_ENABLED),
            "task_budget": max(1, int(AETHER_TASK_BUDGET)),
            "task_max_retries": max(0, int(AETHER_TASK_MAX_RETRIES)),
            "orchestrator_policy": dict(ORCHESTRATOR_POLICY),
        },
    )
    update_dashboard()
    return "✅ AETHER iniciado correctamente."

# -----------------------------
# GRADIO UI (HF SAFE)
# -----------------------------

def _account_status_text(account_state: Dict[str, str], lang: str = "es") -> str:
    status = (account_state or {}).get("status") or ""
    username = (account_state or {}).get("username") or ""
    if isinstance(status, str) and status.lower() == "admin":
        status_text = t(lang, "account_status_admin")
    else:
        status_text = t(lang, "account_status_guest")
    if username and isinstance(status, str) and status.lower() == "admin":
        return f"**{t(lang, 'account_status_label')}:** {status_text} ({username})"
    return f"**{t(lang, 'account_status_label')}:** {status_text}"


def ui_apply_language(lang: str, account_state: Dict[str, str]) -> Tuple[Any, ...]:
    resolved = normalize_lang(lang)
    return (
        resolved,
        gr.update(value=f"<div id='aether-header'><div>{t(resolved, 'header_beta')}</div></div>"),
        gr.update(label=t(resolved, "boot_label")),
        gr.update(value=t(resolved, "new_chat")),
        gr.update(label=t(resolved, "chats")),
        gr.update(label=t(resolved, "chat_label")),
        gr.update(label=t(resolved, "message_label"), placeholder=t(resolved, "message_placeholder")),
        gr.update(value=t(resolved, "send_chat")),
        gr.update(value=t(resolved, "reload_modules")),
        gr.update(value=t(resolved, "export_demo1")),
        gr.update(value=t(resolved, "refresh_status")),
        gr.update(value=t(resolved, "btn_builder")),
        gr.update(value=t(resolved, "btn_scientific")),
        gr.update(label=t(resolved, "admin_ops")),
        gr.update(value=t(resolved, "task_queue_title")),
        gr.update(label=t(resolved, "task_cmd_label"), placeholder=t(resolved, "task_cmd_placeholder")),
        gr.update(label=t(resolved, "priority_label")),
        gr.update(value=t(resolved, "enqueue_task")),
        gr.update(value=t(resolved, "orchestrator_title")),
        gr.update(label=t(resolved, "project_name_label"), placeholder=t(resolved, "project_name_placeholder")),
        gr.update(value=t(resolved, "create_project")),
        gr.update(label=t(resolved, "project_label")),
        gr.update(label=t(resolved, "task_command_label"), placeholder=t(resolved, "task_command_placeholder")),
        gr.update(value=t(resolved, "add_task")),
        gr.update(label=t(resolved, "task_label")),
        gr.update(value=t(resolved, "run_task")),
        gr.update(label=t(resolved, "orchestrator_output")),
        gr.update(label=t(resolved, "status_json")),
        gr.update(label=t(resolved, "logs_last_n")),
        gr.update(label=t(resolved, "tail_logs")),
        gr.update(value=t(resolved, "refresh_logs")),
        gr.update(label=t(resolved, "export_demo1_label")),
        gr.update(value=t(resolved, "snapshots_title")),
        gr.update(label=t(resolved, "snapshot_name_label")),
        gr.update(value=t(resolved, "create_snapshot")),
        gr.update(value=t(resolved, "restore_snapshot")),
        gr.update(value=t(resolved, "list_snapshots")),
        gr.update(value=t(resolved, "export_snapshot")),
        gr.update(label=t(resolved, "snapshot_output")),
        gr.update(label=t(resolved, "import_snapshot_json")),
        gr.update(value=t(resolved, "import_snapshot")),
        gr.update(value=t(resolved, "replica_title")),
        gr.update(label=t(resolved, "replica_name_label")),
        gr.update(value=t(resolved, "export_replica")),
        gr.update(label=t(resolved, "replica_json")),
        gr.update(label=t(resolved, "import_replica_json")),
        gr.update(value=t(resolved, "import_replica_apply")),
        gr.update(label=t(resolved, "replica_import_result")),
        gr.update(value=t(resolved, "home_button")),
        gr.update(value=t(resolved, "builder_title")),
        gr.update(value=t(resolved, "builder_subtitle")),
        gr.update(value=t(resolved, "builder_tags")),
        gr.update(value=t(resolved, "builder_desc")),
        gr.update(label=t(resolved, "project_id_label")),
        gr.update(label=t(resolved, "export_zip_label")),
        gr.update(value=t(resolved, "export_button")),
        gr.update(value=t(resolved, "new_chat")),
        gr.update(label=t(resolved, "chats")),
        gr.update(label=t(resolved, "builder_chat_label")),
        gr.update(label=t(resolved, "message_label"), placeholder=t(resolved, "builder_message_placeholder")),
        gr.update(value=t(resolved, "send_button")),
        gr.update(value=t(resolved, "home_button")),
        gr.update(value=t(resolved, "scientific_title")),
        gr.update(value=t(resolved, "scientific_subtitle")),
        gr.update(value=t(resolved, "scientific_desc")),
        gr.update(value=t(resolved, "new_chat")),
        gr.update(label=t(resolved, "chats")),
        gr.update(label=t(resolved, "scientific_chat_label")),
        gr.update(label=t(resolved, "message_label"), placeholder=t(resolved, "scientific_message_placeholder")),
        gr.update(value=t(resolved, "send_button")),
        gr.update(value=t(resolved, "home_button")),
        gr.update(value=t(resolved, "config_title")),
        gr.update(value=t(resolved, "config_account_title")),
        gr.update(value=_account_status_text(account_state, resolved)),
        gr.update(label=t(resolved, "username_label"), placeholder=t(resolved, "username_placeholder")),
        gr.update(label=t(resolved, "pin_label"), placeholder=t(resolved, "pin_placeholder")),
        gr.update(value=t(resolved, "login")),
        gr.update(value=t(resolved, "logout")),
        gr.update(value=t(resolved, "config_language_title")),
        gr.update(label=t(resolved, "language_selector_label"), choices=LANGUAGE_CHOICES, value=resolved),
        gr.update(value=t(resolved, "config_plans_title")),
        gr.update(label=t(resolved, "plans_accordion_label")),
        gr.update(value=t(resolved, "plan_free_text")),
        gr.update(value=t(resolved, "plan_pro_text")),
        gr.update(value=t(resolved, "plan_lab_text")),
        gr.update(value=t(resolved, "plan_upgrade")),
        gr.update(value=t(resolved, "plan_footer")),
        gr.update(value="<div style='font-size: 0.85em; color: #666;'>inf.aether@outlook.com</div>"),
    )


def ui_init_language(account_state: Dict[str, str], request: gr.Request) -> Tuple[Any, ...]:
    accept_language = ""
    if request:
        try:
            accept_language = dict(request.headers).get("accept-language", "")
        except Exception:
            accept_language = ""
    detected = detect_language_from_header(accept_language)
    return ui_apply_language(detected, account_state)

def _admin_env() -> Tuple[bool, str, str]:
    pin = os.environ.get("AETHER_ADMIN_PIN", "").strip()
    user = os.environ.get("AETHER_ADMIN_USER", "").strip()
    return bool(pin), user, pin

def _admin_visibility_updates(is_admin: bool) -> Tuple[gr.update, gr.update, gr.update, gr.update, gr.update]:
    return (
        gr.update(visible=is_admin),
        gr.update(visible=is_admin),
        gr.update(visible=is_admin),
        gr.update(visible=is_admin),
        gr.update(visible=is_admin),
    )

def ui_set_view(view: str) -> Tuple[gr.update, gr.update, gr.update, gr.update, str]:
    return (
        gr.update(visible=view == "home"),
        gr.update(visible=view == "builder"),
        gr.update(visible=view == "scientific"),
        gr.update(visible=view == "config"),
        view,
    )

def ui_login(
    username: str, pin: str, account_state: Dict[str, str], lang: str
) -> Tuple[bool, Dict[str, str], str, gr.update, gr.update, gr.update, gr.update, gr.update]:
    username = (username or "").strip()
    pin = (pin or "").strip()
    admin_enabled, required_user, admin_pin = _admin_env()
    is_admin = False
    new_state = dict(account_state or {})
    if admin_enabled and pin and hmac.compare_digest(pin, admin_pin):
        if required_user and username != required_user:
            is_admin = False
        else:
            is_admin = True
    if is_admin:
        new_state["status"] = "Admin"
        new_state["username"] = username or (required_user or "admin")
    else:
        new_state["status"] = "Invitado"
        new_state["username"] = ""
    return (is_admin, new_state, _account_status_text(new_state, lang), *_admin_visibility_updates(is_admin))

def ui_logout(
    account_state: Dict[str, str], lang: str
) -> Tuple[bool, Dict[str, str], str, gr.update, gr.update, gr.update, gr.update, gr.update]:
    new_state = dict(account_state or {})
    new_state["status"] = "Invitado"
    new_state["username"] = ""
    return (False, new_state, _account_status_text(new_state, lang), *_admin_visibility_updates(False))

def build_ui() -> gr.Blocks:
    ensure_projects()
    with gr.Blocks(
        title=t("es", "app_title"),
        css="""
        #aether-header .aether-header-line { color: #8a8a8a; font-size: 12px; }
        #aether-gear button {
            width: 32px;
            min-width: 32px;
            padding: 0;
        }
        """,
    ) as demo:
        view_state = gr.State("home")
        language_state = gr.State("es")
        account_state = gr.State({"status": "Invitado", "username": ""})
        is_admin_state = gr.State(False)
        builder_initial_history = load_active("builder")
        scientific_initial_history = load_active("scientific")
        builder_saved_chats = load_chats("builder")
        scientific_saved_chats = load_chats("scientific")

        with gr.Row():
            with gr.Column(scale=1, min_width=160):
                header_html = gr.HTML(
                    f"<div id='aether-header'><div>{t('es', 'header_beta')}</div></div>"
                )
            with gr.Column(scale=1, min_width=120):
                btn_open_config = gr.Button("⚙️", size="sm", elem_id="aether-gear")

        with gr.Column(visible=True) as home_view:
            with gr.Row():
                with gr.Column(scale=5):
                    boot_msg = gr.Textbox(label=t("es", "boot_label"), lines=1, visible=False)

                    with gr.Row():
                        btn_new_chat = gr.Button(t("es", "new_chat"), size="sm")
                        chat_selector = gr.Dropdown(
                            label=t("es", "chats"),
                            choices=["Chat 1"],
                            value="Chat 1",
                        )

                    chat = gr.Chatbot(label=t("es", "chat_label"), height=420, value=[])
                    chat_state = gr.State([])
                    user_msg = gr.Textbox(
                        label=t("es", "message_label"),
                        placeholder=t("es", "message_placeholder"),
                        lines=2,
                    )

                    with gr.Row():
                        btn_send = gr.Button(t("es", "send_chat"))
                        btn_reload = gr.Button(t("es", "reload_modules"), visible=False)
                        btn_export_demo = gr.Button(t("es", "export_demo1"), visible=False)
                        btn_refresh_status = gr.Button(t("es", "refresh_status"), visible=False)

                    with gr.Row():
                        btn_builder = gr.Button(t("es", "btn_builder"), variant="primary")
                        btn_scientific = gr.Button(t("es", "btn_scientific"), variant="primary")

                    with gr.Accordion(t("es", "admin_ops"), open=False, visible=False) as admin_ops:
                        task_queue_md = gr.Markdown(t("es", "task_queue_title"))
                        task_cmd = gr.Textbox(
                            label=t("es", "task_cmd_label"),
                            placeholder=t("es", "task_cmd_placeholder"),
                            lines=1,
                        )
                        prio = gr.Slider(1, 20, value=5, step=1, label=t("es", "priority_label"))
                        btn_enqueue = gr.Button(t("es", "enqueue_task"))

                        gr.Markdown("---")
                        project_orchestrator_md = gr.Markdown(t("es", "orchestrator_title"))
                        project_name = gr.Textbox(
                            label=t("es", "project_name_label"),
                            placeholder=t("es", "project_name_placeholder"),
                            lines=1,
                        )
                        btn_add_project = gr.Button(t("es", "create_project"))
                        project_selector = gr.Dropdown(
                            label=t("es", "project_label"),
                            choices=_project_choices(),
                            value=_default_project_value(),
                        )
                        task_command = gr.Textbox(
                            label=t("es", "task_command_label"),
                            placeholder=t("es", "task_command_placeholder"),
                            lines=1,
                        )
                        btn_add_task = gr.Button(t("es", "add_task"))
                        _initial_pid = _default_project_value() or "default"
                        _initial_tasks = _task_choices(_initial_pid)
                        _initial_task_value = _initial_tasks[0][1] if _initial_tasks else None
                        task_selector = gr.Dropdown(
                            label=t("es", "task_label"),
                            choices=_initial_tasks,
                            value=_initial_task_value,
                        )
                        btn_run_task = gr.Button(t("es", "run_task"))
                        orchestrator_out = gr.Code(label=t("es", "orchestrator_output"), language="json")

                        gr.Markdown("---")
                        status = gr.Code(label=t("es", "status_json"), language="json")

                        logs_n = gr.Slider(10, 200, value=50, step=10, label=t("es", "logs_last_n"))
                        logs = gr.Textbox(label=t("es", "tail_logs"), lines=12)
                        btn_refresh_logs = gr.Button(t("es", "refresh_logs"))

                        export_out = gr.Code(label=t("es", "export_demo1_label"), language="json")

                        gr.Markdown("---")
                        snapshots_md = gr.Markdown(t("es", "snapshots_title"))
                        snap_name = gr.Textbox(label=t("es", "snapshot_name_label"), value="demo1", lines=1)
                        with gr.Row():
                            btn_snap_create = gr.Button(t("es", "create_snapshot"))
                            btn_snap_restore = gr.Button(t("es", "restore_snapshot"))
                            btn_snap_list = gr.Button(t("es", "list_snapshots"))
                            btn_snap_export = gr.Button(t("es", "export_snapshot"))
                        snap_out = gr.Code(label=t("es", "snapshot_output"), language="json")
                        snap_import_txt = gr.Textbox(label=t("es", "import_snapshot_json"), lines=6)
                        btn_snap_import = gr.Button(t("es", "import_snapshot"))

                        gr.Markdown("---")
                        replica_md = gr.Markdown(t("es", "replica_title"))
                        replica_name = gr.Textbox(label=t("es", "replica_name_label"), value="replica", lines=1)
                        btn_replica_export = gr.Button(t("es", "export_replica"))
                        replica_out = gr.Code(label=t("es", "replica_json"), language="json")
                        replica_in = gr.Textbox(label=t("es", "import_replica_json"), lines=8)
                        btn_replica_import = gr.Button(t("es", "import_replica_apply"))
                        replica_result = gr.Code(label=t("es", "replica_import_result"), language="json")

        with gr.Column(visible=False) as builder_view:
            btn_home_from_builder = gr.Button(t("es", "home_button"))
            builder_title_md = gr.Markdown(t("es", "builder_title"))
            builder_subtitle_md = gr.Markdown(t("es", "builder_subtitle"))
            builder_tags_md = gr.Markdown(t("es", "builder_tags"))
            builder_desc_md = gr.Markdown(t("es", "builder_desc"))
            builder_project_id = gr.Textbox(label=t("es", "project_id_label"), value="", interactive=False)
            builder_export_file = gr.File(label=t("es", "export_zip_label"), interactive=False)
            with gr.Row():
                btn_builder_export = gr.Button(t("es", "export_button"))
            with gr.Row():
                with gr.Column(scale=1, min_width=180):
                    btn_builder_new_chat = gr.Button(t("es", "new_chat"), size="sm")
                    builder_chat_selector = gr.Radio(
                        label=t("es", "chats"),
                        choices=_chat_choices(builder_saved_chats),
                        value=None,
                    )
                with gr.Column(scale=4):
                    builder_chat = gr.Chatbot(
                        label=t("es", "builder_chat_label"),
                        height=420,
                        value=builder_initial_history,
                    )
                    builder_msg = gr.Textbox(
                        label=t("es", "message_label"),
                        placeholder=t("es", "builder_message_placeholder"),
                        lines=2,
                    )
                    with gr.Row():
                        btn_builder_send = gr.Button(t("es", "send_button"))
            builder_chat_state = gr.State(builder_initial_history)
            builder_chats_state = gr.State(builder_saved_chats)

        with gr.Column(visible=False) as scientific_view:
            btn_home_from_scientific = gr.Button(t("es", "home_button"))
            scientific_title_md = gr.Markdown(t("es", "scientific_title"))
            scientific_subtitle_md = gr.Markdown(t("es", "scientific_subtitle"))
            scientific_desc_md = gr.Markdown(t("es", "scientific_desc"))
            with gr.Row():
                with gr.Column(scale=1, min_width=180):
                    btn_scientific_new_chat = gr.Button(t("es", "new_chat"), size="sm")
                    scientific_chat_selector = gr.Radio(
                        label=t("es", "chats"),
                        choices=_chat_choices(scientific_saved_chats),
                        value=None,
                    )
                with gr.Column(scale=4):
                    scientific_chat = gr.Chatbot(
                        label=t("es", "scientific_chat_label"),
                        height=420,
                        value=scientific_initial_history,
                    )
                    scientific_msg = gr.Textbox(
                        label=t("es", "message_label"),
                        placeholder=t("es", "scientific_message_placeholder"),
                        lines=2,
                    )
                    with gr.Row():
                        btn_scientific_send = gr.Button(t("es", "send_button"))
            scientific_chat_state = gr.State(scientific_initial_history)
            scientific_chats_state = gr.State(scientific_saved_chats)

        with gr.Column(visible=False) as config_view:
            btn_home_from_config = gr.Button(t("es", "home_button"))
            config_title_md = gr.Markdown(t("es", "config_title"))

            config_account_md = gr.Markdown(t("es", "config_account_title"))
            account_status = gr.Markdown(_account_status_text({"status": "Invitado", "username": ""}, "es"))
            account_username = gr.Textbox(label=t("es", "username_label"), placeholder=t("es", "username_placeholder"), lines=1)
            account_pin = gr.Textbox(label=t("es", "pin_label"), placeholder=t("es", "pin_placeholder"), type="password", lines=1)
            btn_login = gr.Button(t("es", "login"))
            btn_logout = gr.Button(t("es", "logout"))

            gr.Markdown("---")
            config_language_md = gr.Markdown(t("es", "config_language_title"))
            language_selector = gr.Dropdown(
                label=t("es", "language_selector_label"),
                choices=LANGUAGE_CHOICES,
                value="es",
            )

            gr.Markdown("---")
            config_plans_md = gr.Markdown(t("es", "config_plans_title"))
            with gr.Accordion(t("es", "plans_accordion_label"), open=False) as plans_accordion:
                with gr.Row():
                    with gr.Column():
                        plan_free_md = gr.Markdown(t("es", "plan_free_text"))
                    with gr.Column():
                        plan_pro_md = gr.Markdown(t("es", "plan_pro_text"))
                    with gr.Column():
                        plan_lab_md = gr.Markdown(t("es", "plan_lab_text"))
            btn_plan_upgrade = gr.Button(t("es", "plan_upgrade"))
            plan_footer_md = gr.Markdown(t("es", "plan_footer"))

            gr.Markdown("---")
            config_email_html = gr.HTML(
                "<div style='font-size: 0.85em; color: #666;'>inf.aether@outlook.com</div>"
            )

        language_outputs = [
            language_state,
            header_html,
            boot_msg,
            btn_new_chat,
            chat_selector,
            chat,
            user_msg,
            btn_send,
            btn_reload,
            btn_export_demo,
            btn_refresh_status,
            btn_builder,
            btn_scientific,
            admin_ops,
            task_queue_md,
            task_cmd,
            prio,
            btn_enqueue,
            project_orchestrator_md,
            project_name,
            btn_add_project,
            project_selector,
            task_command,
            btn_add_task,
            task_selector,
            btn_run_task,
            orchestrator_out,
            status,
            logs_n,
            logs,
            btn_refresh_logs,
            export_out,
            snapshots_md,
            snap_name,
            btn_snap_create,
            btn_snap_restore,
            btn_snap_list,
            btn_snap_export,
            snap_out,
            snap_import_txt,
            btn_snap_import,
            replica_md,
            replica_name,
            btn_replica_export,
            replica_out,
            replica_in,
            btn_replica_import,
            replica_result,
            btn_home_from_builder,
            builder_title_md,
            builder_subtitle_md,
            builder_tags_md,
            builder_desc_md,
            builder_project_id,
            builder_export_file,
            btn_builder_export,
            btn_builder_new_chat,
            builder_chat_selector,
            builder_chat,
            builder_msg,
            btn_builder_send,
            btn_home_from_scientific,
            scientific_title_md,
            scientific_subtitle_md,
            scientific_desc_md,
            btn_scientific_new_chat,
            scientific_chat_selector,
            scientific_chat,
            scientific_msg,
            btn_scientific_send,
            btn_home_from_config,
            config_title_md,
            config_account_md,
            account_status,
            account_username,
            account_pin,
            btn_login,
            btn_logout,
            config_language_md,
            language_selector,
            config_plans_md,
            plans_accordion,
            plan_free_md,
            plan_pro_md,
            plan_lab_md,
            btn_plan_upgrade,
            plan_footer_md,
            config_email_html,
        ]

        # wiring
        btn_send.click(fn=chat_send, inputs=[user_msg, chat_state], outputs=[chat, chat_state, user_msg])
        btn_new_chat.click(fn=ui_new_chat, inputs=[], outputs=[chat, chat_state])
        btn_enqueue.click(fn=ui_enqueue, inputs=[task_cmd, prio], outputs=[status, logs])
        btn_reload.click(fn=ui_reload_modules, inputs=[], outputs=[status])
        btn_export_demo.click(fn=export_demo1, inputs=[], outputs=[export_out])
        btn_refresh_status.click(fn=ui_status, inputs=[], outputs=[status])

        btn_add_project.click(fn=ui_add_project, inputs=[project_name], outputs=[orchestrator_out, project_selector])
        project_selector.change(fn=ui_refresh_tasks, inputs=[project_selector], outputs=[task_selector])
        btn_add_task.click(fn=ui_add_task, inputs=[project_selector, task_command], outputs=[orchestrator_out, task_selector])
        btn_run_task.click(fn=ui_run_task, inputs=[task_selector], outputs=[orchestrator_out])

        btn_refresh_logs.click(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])
        logs_n.change(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

        btn_snap_create.click(fn=ui_snapshot_create, inputs=[snap_name], outputs=[snap_out])
        btn_snap_restore.click(fn=ui_snapshot_restore, inputs=[snap_name], outputs=[snap_out])
        btn_snap_list.click(fn=ui_snapshot_list, inputs=[], outputs=[snap_out])
        btn_snap_export.click(fn=ui_snapshot_export, inputs=[snap_name], outputs=[snap_out])
        btn_snap_import.click(fn=ui_snapshot_import, inputs=[snap_import_txt], outputs=[snap_out])

        btn_replica_export.click(fn=ui_replica_export, inputs=[replica_name], outputs=[replica_out])
        btn_replica_import.click(fn=ui_replica_import, inputs=[replica_in], outputs=[replica_result])

        btn_builder_send.click(
            fn=builder_chat_send,
            inputs=[builder_msg, builder_chat_state],
            outputs=[builder_chat, builder_chat_state, builder_msg],
        )
        btn_builder_new_chat.click(
            fn=ui_new_builder_chat,
            inputs=[builder_chat_state, builder_chats_state],
            outputs=[builder_chat, builder_chat_state, builder_chats_state, builder_chat_selector],
        )
        builder_chat_selector.change(
            fn=ui_select_builder_chat,
            inputs=[builder_chat_selector, builder_chat_state, builder_chats_state],
            outputs=[builder_chat, builder_chat_state, builder_chats_state, builder_chat_selector],
        )
        btn_builder_export.click(
            fn=export_builder_project,
            inputs=[builder_project_id],
            outputs=[builder_project_id, builder_export_file],
        )
        btn_scientific_send.click(
            fn=scientific_chat_send,
            inputs=[scientific_msg, scientific_chat_state],
            outputs=[scientific_chat, scientific_chat_state, scientific_msg],
        )
        btn_scientific_new_chat.click(
            fn=ui_new_scientific_chat,
            inputs=[scientific_chat_state, scientific_chats_state],
            outputs=[scientific_chat, scientific_chat_state, scientific_chats_state, scientific_chat_selector],
        )
        scientific_chat_selector.change(
            fn=ui_select_scientific_chat,
            inputs=[scientific_chat_selector, scientific_chat_state, scientific_chats_state],
            outputs=[scientific_chat, scientific_chat_state, scientific_chats_state, scientific_chat_selector],
        )

        btn_login.click(
            fn=ui_login,
            inputs=[account_username, account_pin, account_state, language_state],
            outputs=[
                is_admin_state,
                account_state,
                account_status,
                boot_msg,
                btn_reload,
                btn_export_demo,
                btn_refresh_status,
                admin_ops,
            ],
        )
        btn_logout.click(
            fn=ui_logout,
            inputs=[account_state, language_state],
            outputs=[
                is_admin_state,
                account_state,
                account_status,
                boot_msg,
                btn_reload,
                btn_export_demo,
                btn_refresh_status,
                admin_ops,
            ],
        )
        language_selector.change(
            fn=ui_apply_language,
            inputs=[language_selector, account_state],
            outputs=language_outputs,
        )

        btn_open_config.click(
            fn=lambda: ui_set_view("config"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )
        btn_builder.click(
            fn=lambda: ui_set_view("builder"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )
        btn_scientific.click(
            fn=lambda: ui_set_view("scientific"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )
        btn_home_from_builder.click(
            fn=lambda: ui_set_view("home"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )
        btn_home_from_scientific.click(
            fn=lambda: ui_set_view("home"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )
        btn_home_from_config.click(
            fn=lambda: ui_set_view("home"),
            inputs=[],
            outputs=[home_view, builder_view, scientific_view, config_view, view_state],
        )

        # boot (solo una vez)
        demo.load(fn=ui_init_language, inputs=[account_state], outputs=language_outputs)
        demo.load(fn=start_aether, inputs=[], outputs=[boot_msg])
        demo.load(fn=ui_status, inputs=[], outputs=[status])
        demo.load(fn=ui_tail_logs, inputs=[logs_n], outputs=[logs])

        if hasattr(gr, "Timer"):
            ticker = gr.Timer(5)
            ticker.tick(fn=ui_tick, inputs=[logs_n], outputs=[status, logs])
    return demo

_DEMO: Optional[gr.Blocks] = None

def get_demo() -> gr.Blocks:
    global _DEMO
    if _DEMO is None:
        init_state()
        _DEMO = build_ui()
    return _DEMO

def __getattr__(name: str):
    if name == "demo":
        return get_demo()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# -----------------------------
# HF ENTRYPOINT
# -----------------------------

def main() -> None:
    if not ALLOW_NETWORK:
        print("AETHER_ALLOW_NETWORK=0: skipping demo.launch()")
        return
    demo = get_demo()
    port = int(os.environ.get("PORT", "7860"))
    demo.queue()
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
        ssr_mode=False,
        show_error=True,
    )

if __name__ == "__main__":
    main()
