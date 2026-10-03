#!/usr/bin/env python3
"""Проверка конфигурации Claude Code в этом репозитории.

- SKILL.md: YAML-фронтматтер разбирается, name совпадает с папкой, description + when_to_use ≤ 1536 символов,
  тело ≤ 500 строк (предупреждение);
- субагенты: фронтматтер, уникальные имена, предзагружаемые навыки существуют;
- одинаковые копии _calcreport.py во всех инженерных навыках;
- JSON-файлы (plugin.json, marketplace.json, docs/settings.proposed.json) корректны;
- .claude/settings.json и docs/settings.proposed.json совпадают по env/permissions/hooks/plugins;
- в репозитории нет похожих на секреты строк (URL вебхуков Bitrix24 с кодом, приватные ключи).

Запуск: python scripts/validate_config.py   (код возврата 1 при ошибках)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
warnings: list[str] = []

# навыки, которые приходят не из репозитория (аккаунт claude.ai, плагины) и могут упоминаться субагентами
EXTERNAL_SKILLS = {"docx", "xlsx", "pptx", "pdf", "frontend-design", "lead-triage", "skill-creator"}


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        errors.append(f"{path}: нет YAML-фронтматтера")
        return {}, text
    if yaml is None:
        warnings.append("PyYAML не установлен — разбор фронтматтера упрощён")
        data = {}
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
        return data, text[m.end():]
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        errors.append(f"{path}: ошибка YAML: {e}")
        return {}, text[m.end():]
    return data, text[m.end():]


def check_skills() -> set[str]:
    names: set[str] = set()
    dirs = list((ROOT / ".claude" / "skills").glob("*/SKILL.md")) + list((ROOT / "plugins").glob("*/skills/*/SKILL.md"))
    for p in sorted(dirs):
        fm, body = frontmatter(p)
        if not fm:
            continue
        name = fm.get("name")
        if not name:
            errors.append(f"{p}: нет поля name")
        elif name != p.parent.name:
            errors.append(f"{p}: name '{name}' не совпадает с папкой '{p.parent.name}'")
        desc = str(fm.get("description", ""))
        if not desc:
            errors.append(f"{p}: нет description")
        total = len(desc) + len(str(fm.get("when_to_use", "") or ""))
        if total > 1536:
            errors.append(f"{p}: description + when_to_use = {total} > 1536")
        lines = body.count("\n")
        if lines > 500:
            warnings.append(f"{p}: тело {lines} строк (> 500 — вынести детали в references/)")
        names.add(p.parent.name)
    return names


def check_agents(skill_names: set[str]) -> None:
    seen: dict[str, Path] = {}
    files = list((ROOT / ".claude" / "agents").glob("*.md")) + list((ROOT / "plugins").glob("*/agents/*.md"))
    for p in sorted(files):
        fm, _ = frontmatter(p)
        if not fm:
            continue
        name = fm.get("name")
        if not name or not fm.get("description"):
            errors.append(f"{p}: нужны name и description")
            continue
        if name in seen:
            errors.append(f"{p}: имя '{name}' уже используется в {seen[name]}")
        seen[name] = p
        for s in fm.get("skills") or []:
            if s not in skill_names and s not in EXTERNAL_SKILLS:
                errors.append(f"{p}: предзагружаемый навык '{s}' не найден")
        if "plugins" in p.parts and any(k in fm for k in ("hooks", "mcpServers", "permissionMode")):
            warnings.append(f"{p}: hooks/mcpServers/permissionMode игнорируются для субагентов плагинов")


def check_calcreport() -> None:
    copies = sorted((ROOT / ".claude" / "skills").glob("*/scripts/_calcreport.py"))
    ref = ROOT / ".claude" / "skills" / "novaprom-pressure-vessels" / "scripts" / "_calcreport.py"
    if not ref.exists():
        errors.append("нет эталонного _calcreport.py")
        return
    h = hashlib.sha256(ref.read_bytes()).hexdigest()
    for c in copies:
        if hashlib.sha256(c.read_bytes()).hexdigest() != h:
            errors.append(f"{c}: отличается от эталона {ref.relative_to(ROOT)}")


def check_json() -> None:
    files = [ROOT / ".claude-plugin" / "marketplace.json", ROOT / "docs" / "settings.proposed.json",
             ROOT / ".claude" / "settings.json"] + list((ROOT / "plugins").glob("*/.claude-plugin/plugin.json"))
    for f in files:
        if f.exists():
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{f}: некорректный JSON: {e}")


def check_settings_sync() -> None:
    """Настройки репозитория и эталон для уровня пользователя не должны расходиться."""
    repo = ROOT / ".claude" / "settings.json"
    prop = ROOT / "docs" / "settings.proposed.json"
    if not (repo.exists() and prop.exists()):
        return
    try:
        a = json.loads(repo.read_text(encoding="utf-8"))
        b = json.loads(prop.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return  # уже отмечено в check_json
    for key in ("env", "permissions", "hooks", "enabledPlugins", "extraKnownMarketplaces"):
        if a.get(key) != b.get(key):
            errors.append(f"{key}: .claude/settings.json и docs/settings.proposed.json расходятся")
    hook_cmds = json.dumps(a.get("hooks", {}), ensure_ascii=False)
    if "novaprom_guard" in hook_cmds and not (ROOT / ".claude" / "hooks" / "novaprom_guard.py").exists():
        errors.append("хук ссылается на novaprom_guard.py, но файла нет")


SECRET_PATTERNS = [
    (re.compile(r"https?://[^\s\"']+/rest/\d+/[a-z0-9]{10,}/", re.I), "URL вебхука Bitrix24 с кодом"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "приватный ключ"),
    (re.compile(r"(api[_-]?key|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]", re.I), "похоже на токен/пароль"),
]


def check_secrets() -> None:
    for p in ROOT.rglob("*"):
        if p.is_dir() or ".git" in p.parts or p.suffix.lower() in (".png", ".jpg", ".webp", ".ico", ".pdf", ".ttf"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rx, what in SECRET_PATTERNS:
            if rx.search(text):
                errors.append(f"{p.relative_to(ROOT)}: {what}")


def main() -> int:
    names = check_skills()
    check_agents(names)
    check_calcreport()
    check_json()
    check_settings_sync()
    check_secrets()
    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    for w in dict.fromkeys(warnings):
        print(f"ПРЕДУПРЕЖДЕНИЕ: {w}")
    for e in errors:
        print(f"ОШИБКА: {e}")
    print(f"Навыков: {len(names)}; ошибок: {len(errors)}; предупреждений: {len(set(warnings))}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
