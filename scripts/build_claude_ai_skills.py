#!/usr/bin/env python3
"""Сборка навыков НОВАПРОМ в ZIP-архивы для загрузки в аккаунт claude.ai (Настройки → Skills → Upload).

Навык, загруженный в аккаунт, работает в чате Claude (веб, приложение на ПК и телефоне) и синхронизируется
в Claude Code. Для каждого навыка из .claude/skills собирается <имя>.zip:
  - внутри папка <имя>/ с SKILL.md и всеми файлами навыка (скрипты, справочники), без __pycache__;
  - во frontmatter остаются только name и description (description = description + when_to_use, ≤ 1024 символа);
    поля Claude Code (when_to_use, allowed-tools, argument-hint, disallowed-tools) в claude.ai не используются;
  - в начало текста добавляется примечание: откуда навык и что значит ${CLAUDE_SKILL_DIR} вне Claude Code.
Навыки, которые работают только в Claude Code на ПК (find-skills, anydoc, novaprom-bitrix-audit), не собираются.

Запуск из корня репозитория:
  python scripts/build_claude_ai_skills.py            → dist/claude-ai-skills/*.zip
  python scripts/build_claude_ai_skills.py --open     то же и открыть папку (Windows)
  python scripts/build_claude_ai_skills.py --only novaprom-piping,novaprom-materials
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / ".claude" / "skills"
DEFAULT_OUT = REPO / "dist" / "claude-ai-skills"
MAX_DESCRIPTION = 1024
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Только для Claude Code на ПК: в чате claude.ai у них нет нужной среды.
EXCLUDE = {
    "find-skills": "ставит навыки в Claude Code через npx skills",
    "anydoc": "CLI через npx; в чате claude.ai документы читаются встроенными навыками docx/xlsx/pdf",
    "novaprom-bitrix-audit": "нужен вебхук портала и локальная среда с хуком только-чтение",
}
SKIP_PARTS = {"__pycache__", ".DS_Store"}


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        raise ValueError("нет frontmatter")
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


def claude_ai_description(fm: dict) -> str:
    parts = [str(fm.get("description") or "").strip(), str(fm.get("when_to_use") or "").strip()]
    desc = re.sub(r"\s+", " ", " - ".join(p for p in parts if p))
    if not desc:
        raise ValueError("пустое description")
    # XML-теги в description запрещены: «<head>» → «head» (в кавычках-ёлочках)
    desc = re.sub(r"<([^<>]*)>", r"«\1»", desc).replace("<", "").replace(">", "")
    if len(desc) > MAX_DESCRIPTION:
        raise ValueError(f"description {len(desc)} > {MAX_DESCRIPTION} символов")
    return desc


def convert_skill_md(text: str) -> str:
    fm, body = split_frontmatter(text)
    name = str(fm.get("name") or "")
    if not NAME_RE.match(name) or len(name) > 64:
        raise ValueError(f"имя навыка {name!r} не подходит для claude.ai")
    desc = claude_ai_description(fm)
    note = ("> Навык рабочей среды НОВАПРОМ (github.com/usuevgpt-lang/Claude-code). Правила: никаких выдуманных "
            "коэффициентов и норм — нет источника, пометить «ТРЕБУЕТ УТОЧНЕНИЯ»; расчёт в формате ИСХОДНЫЕ ДАННЫЕ → "
            "НОРМАТИВ → ФОРМУЛА → ПОДСТАНОВКА → РЕЗУЛЬТАТ → ПРОВЕРКА; давление с пометкой «изб.»/«абс.».")
    if "${CLAUDE_SKILL_DIR}" in body:
        note += ("\n> `${CLAUDE_SKILL_DIR}` в командах — папка этого навыка (где лежит этот SKILL.md); если переменная "
                 "не подставлена, используйте фактический путь к ней. Недостающие Python-пакеты (CoolProp, ezdxf, openpyxl, "
                 "matplotlib, Pillow) ставить `pip install`; в чате claude.ai — `pip install --break-system-packages`.")
    front = yaml.safe_dump({"name": name, "description": desc}, allow_unicode=True, sort_keys=False, width=100000)
    return f"---\n{front}---\n\n{note}\n\n{body.lstrip()}"


def build_one(skill_dir: Path, out_dir: Path) -> Path:
    name = skill_dir.name
    skill_md = convert_skill_md((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    target = out_dir / f"{name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{name}/SKILL.md", skill_md)
        for f in sorted(skill_dir.rglob("*")):
            rel = f.relative_to(skill_dir)
            if f.is_dir() or rel.as_posix() == "SKILL.md" or SKIP_PARTS & set(rel.parts) or f.suffix == ".pyc":
                continue
            z.write(f, f"{name}/{rel.as_posix()}")
    return target


def main(argv: list[str] | None = None) -> int:
    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="", help="через запятую: собрать только эти навыки")
    ap.add_argument("--open", action="store_true", help="открыть папку с архивами (Windows)")
    a = ap.parse_args(argv)

    only = {s.strip() for s in a.only.split(",") if s.strip()}
    skills = sorted(p.parent for p in SRC.glob("*/SKILL.md"))
    unknown = only - {p.name for p in skills}
    if unknown:
        print(f"ОШИБКА: нет таких навыков: {', '.join(sorted(unknown))}")
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    for old in a.out.glob("*.zip"):
        old.unlink()   # только наши архивы в нашей папке dist/ — пересобираются целиком

    built, errors = [], []
    for d in skills:
        if (only and d.name not in only) or (not only and d.name in EXCLUDE):
            continue
        try:
            built.append(build_one(d, a.out))
        except (ValueError, yaml.YAMLError) as e:
            errors.append(f"{d.name}: {e}")

    print(f"Архивы для claude.ai: {len(built)} в {a.out}")
    for z in built:
        print(f"  {z.name:42s} {z.stat().st_size // 1024:>5d} КБ")
    if not only:
        for name, why in EXCLUDE.items():
            print(f"  не собран {name}: {why}")
    for e in errors:
        print(f"  [X] {e}")
    print("Загрузка: claude.ai → Настройки → Capabilities → Skills → Upload skill → выбрать .zip (по одному).")
    if a.open and os.name == "nt":
        os.startfile(a.out)   # noqa: S606 — открыть папку в Проводнике
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
