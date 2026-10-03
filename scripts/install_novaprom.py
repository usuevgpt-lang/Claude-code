#!/usr/bin/env python3
"""Установка среды НОВАПРОМ для Claude Code на уровне пользователя — Windows, macOS, Linux, облачная среда.

После установки навыки, субагенты, правила маршрутизации и хук безопасности действуют во ВСЕХ проектах
(Claude Code CLI и вкладка Code в приложении Claude), а Claude сам выбирает подходящий навык по задаче.

Копирует в папку настроек Claude Code (~/.claude, на Windows %USERPROFILE%\\.claude, или CLAUDE_CONFIG_DIR):
  skills/                  — все навыки из .claude/skills репозитория;
  agents/                  — субагенты из .claude/agents;
  hooks/novaprom_guard.py  — хук безопасности;
  novaprom/NOVAPROM.md     — правила и таблица маршрутизации; импортируются строкой из CLAUDE.md пользователя;
и вливает docs/settings.proposed.json в settings.json (scripts/merge_settings.py: хук, правила ask/deny,
телеметрия, маркетплейсы и плагины; остальные настройки пользователя сохраняются).

Повторный запуск безопасен: одинаковые файлы не трогаются; изменённые навыки и агенты перед заменой
переносятся в novaprom-backups/<время>/ (не удаляются), CLAUDE.md и settings.json получают копию *.bak-<время>.
В конце — проверка установки: навыки, агенты, хук, настройки, Python-пакеты расчётов, Node.js.

Запуск из корня репозитория:
  python scripts/install_novaprom.py              установить/обновить и проверить
  python scripts/install_novaprom.py --check      только проверить, ничего не менять
  python scripts/install_novaprom.py --dry-run    показать, что изменится
Код возврата: 0 — среда установлена; 1 — обязательная часть отсутствует (см. отчёт); 2 — ошибка запуска.
"""
from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMPORT_MARK = "novaprom/NOVAPROM.md"
RETIRED_SKILLS = ("task-observer",)
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
# Модули Python, нужные расчётным скриптам и проверке конфигурации: (импорт, пакет pip, кому нужен)
PY_MODULES = (
    ("CoolProp", "CoolProp", "Z и свойства газа (novaprom-gas-hydraulics, -gas-reduction)"),
    ("openpyxl", "openpyxl", "Excel со сметами (novaprom-cost-estimation)"),
    ("ezdxf", "ezdxf", "DXF и развёртки (novaprom-cad)"),
    ("matplotlib", "matplotlib", "предпросмотр DXF, графики"),
    ("PIL", "Pillow", "PNG/WebP (web-assets, svg-icons)"),
    ("yaml", "PyYAML", "scripts/validate_config.py"),
)


def default_claude_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def skill_names(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if (p / "SKILL.md").is_file()) if root.is_dir() else []


def agent_names(root: Path) -> list[str]:
    return sorted(p.name for p in root.glob("*.md")) if root.is_dir() else []


def same_tree(a: Path, b: Path) -> bool:
    """Одинаковы ли папки по набору файлов и содержимому (без __pycache__)."""
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__", ".DS_Store"])
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    return all(same_tree(a / d, b / d) for d in cmp.common_dirs)


class Installer:
    def __init__(self, claude_dir: Path, dry_run: bool = False):
        self.dir = claude_dir
        self.dry = dry_run
        self.stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Резервные копии — ВНЕ skills/ и agents/: папка навыка, оставленная в skills/, загрузилась бы как дубль.
        self.backup_dir = claude_dir / "novaprom-backups" / self.stamp
        self.counts = {"new": 0, "updated": 0, "same": 0}

    def say(self, msg: str) -> None:
        print(("[DRY] " if self.dry else "") + msg)

    def _backup(self, path: Path, category: str) -> None:
        dst = self.backup_dir / category
        dst.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(dst / path.name))

    def put_dir(self, src: Path, dst: Path, category: str) -> str:
        if dst.is_dir() and same_tree(src, dst):
            status = "same"
        else:
            status = "updated" if dst.exists() else "new"
            if not self.dry:
                if dst.exists():
                    self._backup(dst, category)
                shutil.copytree(src, dst, ignore=IGNORE)
        self.counts[status] += 1
        return status

    def put_file(self, src: Path, dst: Path, category: str | None) -> str:
        if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            status = "same"
        else:
            status = "updated" if dst.exists() else "new"
            if not self.dry:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists() and category:
                    self._backup(dst, category)
                shutil.copy2(src, dst)
        self.counts[status] += 1
        return status

    def install_skills(self) -> None:
        src_root = REPO / ".claude" / "skills"
        names = skill_names(src_root)
        changed = [n for n in names if self.put_dir(src_root / n, self.dir / "skills" / n, "skills") != "same"]
        self.say(f"[OK] Навыки: {len(names)} в {self.dir / 'skills'}"
                 + (f"; новые/обновлённые: {', '.join(changed)}" if changed else "; изменений нет"))

    def install_agents(self) -> None:
        src_root = REPO / ".claude" / "agents"
        names = agent_names(src_root)
        changed = [n for n in names if self.put_file(src_root / n, self.dir / "agents" / n, "agents") != "same"]
        self.say(f"[OK] Субагенты: {len(names)} в {self.dir / 'agents'}"
                 + (f"; новые/обновлённые: {', '.join(changed)}" if changed else "; изменений нет"))

    def install_hook_and_rules(self) -> None:
        self.put_file(REPO / ".claude" / "hooks" / "novaprom_guard.py", self.dir / "hooks" / "novaprom_guard.py", None)
        self.put_file(REPO / "global" / "NOVAPROM.md", self.dir / "novaprom" / "NOVAPROM.md", None)
        self.say(f"[OK] Хук безопасности и правила НОВАПРОМ скопированы в {self.dir}")

    def import_line(self) -> str:
        if self.dir.resolve() == (Path.home() / ".claude").resolve():
            return "@~/.claude/" + IMPORT_MARK
        return "@" + (self.dir / IMPORT_MARK).as_posix()

    def ensure_import(self) -> None:
        """Добавляет в CLAUDE.md пользователя импорт правил НОВАПРОМ (UTF-8/UTF-16/BOM/cp1251 — читаются)."""
        path = self.dir / "CLAUDE.md"
        text = read_text_any(path) if path.exists() else ""
        if IMPORT_MARK in text:
            self.say(f"[OK] Импорт правил уже есть в {path}")
            return
        if not self.dry:
            if path.exists():
                shutil.copy2(path, path.with_name(f"{path.name}.bak-{self.stamp}"))
            sep = "" if not text or text.endswith("\n") else "\n"
            body = text + sep + ("\n" if text else "") + f"# NOVAPROM\n{self.import_line()}\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode("utf-8"))   # UTF-8 без BOM; исходник — в *.bak
        self.say(f"[OK] Импорт правил добавлен в {path}")

    def retire(self) -> None:
        for name in RETIRED_SKILLS:
            path = self.dir / "skills" / name
            if path.exists():
                if not self.dry:
                    self._backup(path, "skills-removed")
                self.say(f"[OK] Выведенный навык {name} перенесён в {self.backup_dir / 'skills-removed'}")

    def merge_settings(self, extra: list[str]) -> int:
        spec = importlib.util.spec_from_file_location("merge_settings", REPO / "scripts" / "merge_settings.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        argv = ["--proposed", str(REPO / "docs" / "settings.proposed.json"),
                "--target", str(self.dir / "settings.json")] + extra + (["--dry-run"] if self.dry else [])
        return mod.main(argv)

    def run(self, settings_args: list[str], skip_settings: bool) -> int:
        if not self.dry:
            self.dir.mkdir(parents=True, exist_ok=True)
        self.install_skills()
        self.install_agents()
        self.install_hook_and_rules()
        self.ensure_import()
        self.retire()
        rc = 0 if skip_settings else self.merge_settings(settings_args)
        if self.backup_dir.exists():
            self.say(f"[OK] Заменённые файлы сохранены в {self.backup_dir}")
        return rc


def read_text_any(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1251")


def real_python_on_path() -> str | None:
    """Хук вызывается командой `python`; заглушка Microsoft Store (WindowsApps) не годится."""
    for name in ("python", "python3") if os.name != "nt" else ("python",):
        exe = shutil.which(name)
        if exe and "WindowsApps" not in exe:
            return exe
    return None


def check(claude_dir: Path) -> int:
    """Проверка установленной среды. Возвращает 0, если обязательные части на месте."""
    errors: list[str] = []
    warns: list[str] = []
    ok: list[str] = []

    want = skill_names(REPO / ".claude" / "skills")
    have = set(skill_names(claude_dir / "skills"))
    miss = [n for n in want if n not in have]
    (errors if miss else ok).append(f"навыки НОВАПРОМ: {len(want) - len(miss)} из {len(want)}"
                                    + (f" — нет: {', '.join(miss)}" if miss else ""))
    stale = [n for n in want if n in have and not same_tree(REPO / ".claude" / "skills" / n, claude_dir / "skills" / n)]
    if stale:
        warns.append(f"навыки отличаются от репозитория (запустите установку ещё раз): {', '.join(stale)}")

    want_a = agent_names(REPO / ".claude" / "agents")
    have_a = set(agent_names(claude_dir / "agents"))
    miss_a = [n[:-3] for n in want_a if n not in have_a]
    (errors if miss_a else ok).append(f"субагенты: {len(want_a) - len(miss_a)} из {len(want_a)}"
                                      + (f" — нет: {', '.join(miss_a)}" if miss_a else ""))

    hook = claude_dir / "hooks" / "novaprom_guard.py"
    (ok if hook.is_file() else errors).append(f"хук безопасности: {'есть' if hook.is_file() else 'нет'} ({hook})")

    claude_md = claude_dir / "CLAUDE.md"
    has_import = claude_md.is_file() and IMPORT_MARK in read_text_any(claude_md) \
        and (claude_dir / IMPORT_MARK).is_file()
    (ok if has_import else errors).append("правила и маршрутизация (CLAUDE.md → NOVAPROM.md): "
                                          + ("подключены" if has_import else "не подключены"))

    settings_path = claude_dir / "settings.json"
    try:
        settings = json.loads(read_text_any(settings_path)) if settings_path.is_file() else {}
    except json.JSONDecodeError as e:
        settings = {}
        errors.append(f"settings.json — некорректный JSON: {e}")
    hooked = "novaprom_guard" in json.dumps(settings.get("hooks", {}))
    (ok if hooked else errors).append("хук включён в settings.json" if hooked else "хук не включён в settings.json")
    proposed = json.loads((REPO / "docs" / "settings.proposed.json").read_text(encoding="utf-8"))
    enabled = settings.get("enabledPlugins") or {}
    on = [p for p, v in (proposed.get("enabledPlugins") or {}).items() if v and enabled.get(p) is True]
    off = [p for p, v in (proposed.get("enabledPlugins") or {}).items() if v and enabled.get(p) is not True]
    (warns if off else ok).append(f"плагины включены в настройках: {', '.join(on) or '—'}"
                                  + (f"; не включены: {', '.join(off)}" if off else ""))

    py = real_python_on_path()
    (ok if py else errors).append(f"команда python для хука: {py or 'не найдена (или заглушка Microsoft Store)'}")
    if sys.version_info < (3, 10):
        warns.append(f"Python {sys.version.split()[0]} — нужен 3.10+")
    missing = [(pkg, why) for mod, pkg, why in PY_MODULES if importlib.util.find_spec(mod) is None]
    if missing:
        warns.append("Python-пакеты расчётов не установлены: " + "; ".join(f"{p} ({w})" for p, w in missing)
                     + f". Установить: python -m pip install -r {REPO / 'scripts' / 'requirements-novaprom.txt'}")
    else:
        ok.append("Python-пакеты расчётов: все установлены")
    (ok if shutil.which("npx") else warns).append(
        "Node.js (npx): " + ("есть" if shutil.which("npx") else "нет — нужен для anydoc, svgo, find-skills; "
                                                                "установить Node.js LTS с nodejs.org"))

    print(f"\nПроверка среды НОВАПРОМ в {claude_dir}:")
    for line in ok:
        print(f"  [OK] {line}")
    for line in warns:
        print(f"  [!]  {line}")
    for line in errors:
        print(f"  [X]  {line}")
    if errors:
        print("Итог: установка НЕ завершена — исправьте пункты [X] и запустите установку ещё раз.")
        return 1
    print("Итог: среда установлена. Перезапустите Claude Code; проверка в нём: /skills, /agents, /hooks, /plugin.")
    return 0


def main(argv: list[str] | None = None) -> int:
    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claude-dir", type=Path, default=None,
                    help="папка настроек Claude Code (по умолчанию CLAUDE_CONFIG_DIR или ~/.claude)")
    ap.add_argument("--check", action="store_true", help="только проверить установку")
    ap.add_argument("--dry-run", action="store_true", help="показать изменения, ничего не записывать")
    ap.add_argument("--no-settings", action="store_true", help="не трогать settings.json")
    ap.add_argument("--disable-plugin", action="append", default=[], help="передаётся в merge_settings.py")
    ap.add_argument("--drop-marketplace", action="append", default=[], help="передаётся в merge_settings.py")
    a = ap.parse_args(argv)

    claude_dir = (a.claude_dir.expanduser() if a.claude_dir else default_claude_dir())
    if not (REPO / ".claude" / "skills").is_dir():
        print(f"ОШИБКА: не найден {REPO / '.claude' / 'skills'} — запускайте скрипт из клона репозитория.")
        return 2
    if a.check:
        return check(claude_dir)

    print(f"Установка среды НОВАПРОМ: {REPO} → {claude_dir}")
    extra = [x for p in a.disable_plugin for x in ("--disable-plugin", p)] + \
            [x for m in a.drop_marketplace for x in ("--drop-marketplace", m)]
    rc = Installer(claude_dir, a.dry_run).run(extra, a.no_settings)
    if rc:
        return 1
    return 0 if a.dry_run else check(claude_dir)


if __name__ == "__main__":
    sys.exit(main())
