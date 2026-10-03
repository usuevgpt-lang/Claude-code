#!/usr/bin/env python3
"""Слияние настроек безопасности НОВАПРОМ с пользовательским settings.json Claude Code.

Берёт docs/settings.proposed.json и добавляет в целевой файл (по умолчанию ~/.claude/settings.json):
  - env — ключи из предложения (существующие значения пользователя с тем же именем заменяются);
  - skillListingBudgetFraction — только если не задан;
  - permissions.ask / permissions.deny — объединение без дублей (allow не трогается);
  - hooks.PreToolUse — хуки НОВАПРОМ добавляются, если их ещё нет (распознаются по novaprom_guard);
  - extraKnownMarketplaces — добавляются или обновляются (источник, закреплённая версия);
    маркетплейсы из --drop-marketplace удаляются;
  - enabledPlugins — значения из предложения; плагины из --disable-plugin выключаются (false).
Всё остальное в файле сохраняется. Перед записью создаётся копия <файл>.bak-<время>.
Файл пишется в UTF-8 без BOM.

Запуск:
  python scripts/merge_settings.py --proposed docs/settings.proposed.json [--target PATH]
         [--disable-plugin claude-mem@thedotmack] [--drop-marketplace thedotmack] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

MARK = "novaprom_guard"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig").strip()
    return json.loads(text) if text else {}


def has_novaprom_hook(group: dict) -> bool:
    return MARK in json.dumps(group, ensure_ascii=False)


def merge(cur: dict, prop: dict, disable: list[str], drop: list[str]) -> tuple[dict, list[str]]:
    log: list[str] = []
    out = dict(cur)

    env = dict(out.get("env") or {})
    for k, v in (prop.get("env") or {}).items():
        if env.get(k) != v:
            env[k] = v
            log.append(f"env.{k} = {v}")
    if env:
        out["env"] = env

    if "skillListingBudgetFraction" in prop and "skillListingBudgetFraction" not in out:
        out["skillListingBudgetFraction"] = prop["skillListingBudgetFraction"]
        log.append(f"skillListingBudgetFraction = {prop['skillListingBudgetFraction']}")

    perms = dict(out.get("permissions") or {})
    for kind in ("ask", "deny"):
        existing = list(perms.get(kind) or [])
        added = [r for r in (prop.get("permissions") or {}).get(kind, []) if r not in existing]
        if added:
            perms[kind] = existing + added
            log.append(f"permissions.{kind}: +{len(added)} правил")
    if perms:
        out["permissions"] = perms

    hooks = dict(out.get("hooks") or {})
    for event, groups in (prop.get("hooks") or {}).items():
        current = list(hooks.get(event) or [])
        ours_old = [g for g in current if has_novaprom_hook(g)]
        ours_new = [g for g in groups if has_novaprom_hook(g)]
        if ours_old != ours_new:   # добавить или обновить группы НОВАПРОМ, чужие хуки не трогать
            current = [g for g in current if not has_novaprom_hook(g)] + ours_new
            log.append(f"hooks.{event}: {'обновлены' if ours_old else 'добавлены'} хуки НОВАПРОМ ({len(ours_new)} групп)")
        hooks[event] = current
    if hooks:
        out["hooks"] = hooks

    mk = dict(out.get("extraKnownMarketplaces") or {})
    for name, val in (prop.get("extraKnownMarketplaces") or {}).items():
        if mk.get(name) != val:   # наши маркетплейсы: добавить или обновить источник (например, закреплённую версию)
            log.append(f"extraKnownMarketplaces: {'обновлён' if name in mk else 'добавлен'} {name}")
            mk[name] = val
    for name in drop:   # явные ключи командной строки важнее предложения
        if mk.pop(name, None) is not None:
            log.append(f"extraKnownMarketplaces: удалён {name}")
    if mk:
        out["extraKnownMarketplaces"] = mk

    plugins = dict(out.get("enabledPlugins") or {})
    for name, val in (prop.get("enabledPlugins") or {}).items():
        if plugins.get(name) != val:
            plugins[name] = val
            log.append(f"enabledPlugins.{name} = {str(val).lower()}")
    for name in disable:
        if plugins.get(name) is not False:
            plugins[name] = False
            log.append(f"enabledPlugins.{name} = false")
    if plugins:
        out["enabledPlugins"] = plugins
    return out, log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposed", required=True)
    ap.add_argument("--target", default=str(Path.home() / ".claude" / "settings.json"))
    ap.add_argument("--disable-plugin", action="append", default=[])
    ap.add_argument("--drop-marketplace", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    target = Path(a.target).expanduser()
    try:
        cur = load(target)
    except json.JSONDecodeError as e:
        print(f"ОШИБКА: {target} — некорректный JSON ({e}). Исправьте файл вручную; ничего не изменено.")
        return 1
    prop = json.loads(Path(a.proposed).read_text(encoding="utf-8"))
    prop.pop("$schema", None)
    new, log = merge(cur, prop, a.disable_plugin, a.drop_marketplace)
    if not log:
        print(f"[OK] {target}: изменений не требуется")
        return 0
    for line in log:
        print(f"  {line}")
    if a.dry_run:
        print("DRY RUN: файл не изменён")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name(f"{target.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(target, backup)
        print(f"[OK] Резервная копия: {backup}")
    target.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Настройки обновлены: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
