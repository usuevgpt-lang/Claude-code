#!/usr/bin/env python3
"""PreToolUse-хук безопасности НОВАПРОМ.

Получает JSON вызова инструмента на stdin и решает:
  deny  — запрещено всегда (установка «из интернета в shell»: curl|bash, irm|iex);
  ask   — принудительный запрос подтверждения пользователя (даже в auto mode);
  (нет вывода) — обычная обработка правилами разрешений Claude Code.

Профили (аргумент --profile):
  default           — общий профиль (подключается в settings.json);
  bitrix-readonly   — для субагента bitrix-auditor: сетевые клиенты, SSH, БД, PHP и обращения
                      к /rest/ в обход b24_readonly.py блокируются (deny), а не «спрашиваются».

Защищённые пути (запись/правка требует подтверждения): переменная окружения
NOVAPROM_PROTECTED_PATHS (через «;» или «:») и/или файлы со списком путей (по одному на строку):
  <проект>/.claude/protected-paths.txt и ~/.claude/novaprom-protected-paths.txt
Сбой хука не блокирует работу (Claude Code считает ненулевой код, кроме 2, неблокирующей ошибкой),
поэтому в settings.json дублирующие правила "ask" заданы и без хука.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DENY_RULES = [
    (r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", "Скачивание и выполнение скрипта из интернета (curl|sh) запрещено политикой. "
     "Скачайте файл, проверьте его (навык novaprom-tool-vetting) и запустите отдельно с разрешения пользователя."),
    (r"\b(irm|iwr|invoke-restmethod|invoke-webrequest)\b[^|]*\|\s*(iex|invoke-expression)\b", "Выполнение скрипта из интернета (irm|iex) запрещено политикой."),
    (r"\biex\s*\(\s*(new-object|irm|iwr|invoke-)", "Выполнение загруженного кода (iex) запрещено политикой."),
]

ASK_RULES = [
    # удаление и необратимые операции
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|--recursive)", "Рекурсивное удаление файлов"),
    (r"\bremove-item\b.*-recurse", "Рекурсивное удаление файлов (PowerShell)"),
    (r"\b(rmdir|rd)\s+/s\b", "Рекурсивное удаление каталога"),
    (r"\bdel\s+/[sq]", "Массовое удаление файлов"),
    (r"\bgit\s+push\b.*(--force|-f\b|--force-with-lease)", "Принудительная перезапись истории в удалённом репозитории"),
    (r"\bgit\s+(reset\s+--hard|clean\s+-[a-z]*f|checkout\s+--\s|restore\s+--source)", "Необратимое отбрасывание изменений git"),
    (r"\bgit\s+branch\s+-D\b", "Удаление ветки git"),
    # удалённые системы и базы данных
    (r"\b(ssh|scp|sftp|rsync|plink|pscp|winscp)\b", "Подключение к удалённому серверу (сайт, Bitrix24, хостинг)"),
    (r"\b(mysql|mariadb|psql|sqlcmd)\b.*\b(update|delete|drop|alter|truncate|insert|create|grant|revoke|rename)\b",
     "Изменяющий запрос к базе данных"),
    (r"\b(mysqladmin|mysqlimport)\b", "Администрирование базы данных"),
    # Bitrix24 REST и запись во внешние веб-системы
    (r"/rest/\d+/", "Обращение к REST API Bitrix24 в обход read-only клиента b24_readonly.py"),
    (r"\b(curl|wget)\b.*(-X\s*(POST|PUT|PATCH|DELETE)|--data|-d\s|--form|-F\s|--upload-file|-T\s)", "HTTP-запрос с изменением данных (POST/PUT/DELETE)"),
    (r"\b(invoke-webrequest|invoke-restmethod|iwr|irm)\b.*-method\s+(post|put|patch|delete)", "HTTP-запрос с изменением данных (PowerShell)"),
    # установка и запуск стороннего кода
    (r"\b(pip3?|python3?\s+-m\s+pip|py\s+(-\d(\.\d+)?\s+)?-m\s+pip|uv\s+pip)\s+install\b", "Установка Python-пакета — сначала проверка (novaprom-tool-vetting)"),
    (r"\b(npm|pnpm|yarn)\s+(install|i|add)\b|\bnpm\s+i\b", "Установка npm-пакета — сначала проверка (novaprom-tool-vetting)"),
    (r"\b(npx|uvx|pnpx|bunx)\b", "Запуск пакета из реестра (npx/uvx) — сторонний код"),
    (r"\b(winget|choco|scoop|apt|apt-get|dnf|yum|brew|cargo)\s+install\b", "Установка программы"),
    (r"\bclaude\s+(mcp\s+add|plugin\s+(install|marketplace\s+add))", "Подключение MCP/плагина — сначала проверка (novaprom-tool-vetting)"),
    # управление CAD и конвертеры
    (r"SldWorks|win32com|comtypes|swconst|\.swp\b", "Автоматизация SolidWorks (управление CAD) — требуется явное разрешение"),
    (r"ODAFileConverter|dwg2dxf|dxf2dwg|freecadcmd", "Запуск конвертера/CAD-программы на файлах"),
    # секреты
    (r"(config\.inc\.php|dbconn\.php|\.settings\.php|\.env\b|id_rsa|\.pem\b|\.pfx\b)", "Доступ к файлу с секретами"),
]

BITRIX_DENY = [
    (r"\b(curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|httpie|http)\b", "сетевые клиенты запрещены — только b24_readonly.py"),
    (r"\b(ssh|scp|sftp|rsync|plink)\b", "подключение к серверу запрещено в режиме аудита"),
    (r"\b(mysql|mariadb|psql|mysqldump)\b", "прямой доступ к БД запрещён в режиме аудита"),
    (r"\bphp\b", "запуск PHP запрещён в режиме аудита"),
]

MCP_ASK = re.compile(r"(send|forward|reply|trash|delete|share|publish|merge|archive|status_change|remove|"
                     r"apply_sensitive|mark_.*spam|respond_to_event|create_event|update_event|recipients_)", re.I)
SECRET_FILE = re.compile(r"(config\.inc\.php|dbconn\.php|\.settings\.php|(^|[\\/])\.env$|id_rsa|\.pem$|\.pfx$)", re.I)


def protected_paths(cwd: str) -> list[str]:
    paths: list[str] = []
    env = os.environ.get("NOVAPROM_PROTECTED_PATHS", "")
    paths += [p for p in re.split(r"[;\n]", env) if p.strip()]
    candidates = [Path(os.environ.get("CLAUDE_PROJECT_DIR", cwd or ".")) / ".claude" / "protected-paths.txt",
                  Path.home() / ".claude" / "novaprom-protected-paths.txt"]
    for f in candidates:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    paths.append(line)
        except OSError:
            pass
    return [os.path.normcase(os.path.abspath(os.path.expanduser(p.strip()))) for p in paths]


def under(path: str, roots: list[str]) -> str | None:
    p = os.path.normcase(os.path.abspath(os.path.expanduser(path)))
    for r in roots:
        if p == r or p.startswith(r.rstrip("\\/") + os.sep):
            return r
    return None


def decide(data: dict, profile: str) -> tuple[str, str] | None:
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    cwd = data.get("cwd", "")
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "")
        low = cmd.lower()
        for pat, why in DENY_RULES:
            if re.search(pat, low, re.I):
                return "deny", why
        if profile == "bitrix-readonly":
            uses_wrapper = "b24_readonly.py" in low
            if "/rest/" in low and not uses_wrapper:
                return "deny", "Режим аудита Bitrix24: обращения к /rest/ только через b24_readonly.py."
            for pat, why in BITRIX_DENY:
                if re.search(pat, low, re.I) and not uses_wrapper:
                    return "deny", f"Режим аудита Bitrix24 (только чтение): {why}."
        reasons = [why for pat, why in ASK_RULES if re.search(pat, cmd, re.I)]
        if "b24_readonly.py" in low:
            reasons = [r for r in reasons if "Bitrix24" not in r]
        roots = protected_paths(cwd)
        for r in roots:
            if r and r in os.path.normcase(cmd):
                reasons.append(f"Команда затрагивает защищённый путь {r}")
        if reasons:
            return "ask", "НОВАПРОМ: требуется подтверждение — " + "; ".join(dict.fromkeys(reasons))
        return None
    if tool in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not path:
            return None
        if SECRET_FILE.search(path):
            return "ask", f"НОВАПРОМ: изменение файла с секретами/конфигурацией ({path})"
        r = under(path, protected_paths(cwd))
        if r:
            return "ask", f"НОВАПРОМ: изменение в защищённой папке {r} (производственные данные/действующие системы)"
        return None
    if tool.startswith("mcp__") and MCP_ASK.search(tool):
        return "ask", f"НОВАПРОМ: действие во внешней системе ({tool}) — отправка/удаление/публикация требует подтверждения"
    return None


def main() -> int:
    profile = "default"
    if "--profile" in sys.argv:
        i = sys.argv.index("--profile")
        if i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    res = decide(data, profile)
    if not res:
        return 0
    decision, reason = res
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                  "permissionDecisionReason": reason}}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
