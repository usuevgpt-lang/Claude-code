"""Общий формат инженерного отчёта НОВАПРОМ.

ИСХОДНЫЕ ДАННЫЕ -> НОРМАТИВ -> ФОРМУЛА -> ПОДСТАНОВКА -> РЕЗУЛЬТАТ -> ПРОВЕРКА.

Каждое входное значение передаётся как число или как объект
{"value": ..., "unit": "...", "source": "..."}. Значение без источника
помечается в отчёте как «ИСТОЧНИК НЕ УКАЗАН» — это не ошибка расчёта,
но такой отчёт нельзя выпускать без сверки.

Файл одинаковый во всех инженерных навыках (scripts/_calcreport.py).
Эталон: .claude/skills/novaprom-pressure-vessels/scripts/_calcreport.py
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any

NO_SOURCE = "ИСТОЧНИК НЕ УКАЗАН"
EXIT_CHECKS_FAILED = 3   # 0 — все проверки выполнены; 3 — есть невыполненные; 1/2 — ошибка входа/аргументов

# Пересчёт единиц: множитель к базовой единице группы. Единица во входном объекте
# ({"value": 1.0, "unit": "м"}) пересчитывается в ожидаемую скриптом; несовместимая — ошибка.
_UNIT_GROUPS = [
    {"мм": 1e-3, "mm": 1e-3, "см": 1e-2, "cm": 1e-2, "м": 1.0, "m": 1.0, "мкм": 1e-6, "µm": 1e-6, "um": 1e-6,
     "дюйм": 0.0254, "in": 0.0254},
    {"Па": 1.0, "Pa": 1.0, "кПа": 1e3, "kPa": 1e3, "МПа": 1e6, "MPa": 1e6, "бар": 1e5, "bar": 1e5,
     "кгс/см²": 98066.5, "кгс/см2": 98066.5, "psi": 6894.757},
    {"Н": 1.0, "N": 1.0, "кН": 1e3, "kN": 1e3, "МН": 1e6, "MN": 1e6},
    {"кг": 1.0, "kg": 1.0, "т": 1e3, "t": 1e3},
    {"Вт": 1.0, "W": 1.0, "кВт": 1e3, "kW": 1e3, "МВт": 1e6, "MW": 1e6},
    {"м³/ч": 1.0, "m3/h": 1.0, "м3/ч": 1.0, "м³/с": 3600.0, "m3/s": 3600.0},
]
_TEMPERATURE = {"°C", "C", "К", "K"}


def convert_unit(value: Any, given: str, expected: str) -> Any:
    """Пересчитать value из единицы given в expected; SystemExit, если единицы несовместимы."""
    g, e = (given or "").strip(), (expected or "").strip()
    if not g or not e or g == e or not isinstance(value, (int, float)):
        return value
    if g in _TEMPERATURE and e in _TEMPERATURE:
        to_k = value + 273.15 if g in ("°C", "C") else value
        return to_k - 273.15 if e in ("°C", "C") else to_k
    for grp in _UNIT_GROUPS:
        if g in grp and e in grp:
            return value * grp[g] / grp[e]
    raise SystemExit(f"Единица «{g}» не может быть пересчитана в ожидаемую «{e}». "
                     f"Задайте значение в «{e}».")


def fmt(x: Any, digits: int = 4) -> str:
    """Число в инженерном виде: 4 значащие цифры, без экспоненты где можно."""
    if isinstance(x, bool) or x is None:
        return str(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        if x == 0 or not math.isfinite(x):
            return str(x)
        mag = math.floor(math.log10(abs(x)))
        if -4 <= mag < 7:
            decimals = max(0, digits - 1 - mag)
            s = f"{x:.{decimals}f}"
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            return s
        return f"{x:.{digits - 1}e}"
    return str(x)


@dataclass
class Param:
    key: str
    name: str
    value: Any
    unit: str
    source: str


@dataclass
class Step:
    title: str
    norm: str
    formula: str
    substitution: str
    result: str


@dataclass
class Check:
    text: str
    ok: bool
    note: str = ""


@dataclass
class CalcReport:
    title: str
    params: list[Param] = field(default_factory=list)
    norms: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    # ---- входные данные -------------------------------------------------
    def get(self, data: dict, key: str, name: str, unit: str = "",
            default: Any = None, required: bool = True) -> Any:
        """Взять значение из входного словаря и зарегистрировать его источник."""
        raw = data.get(key, None)
        if raw is None:
            if default is None:
                if required:
                    raise SystemExit(f"Не задан обязательный параметр '{key}' ({name}, {unit})")
                return None
            value, source = default, "значение по умолчанию скрипта — ПРОВЕРИТЬ"
            self.warnings.append(f"Параметр «{name}» ({key}) принят по умолчанию = {fmt(value)} {unit}.")
        elif isinstance(raw, dict):
            value = raw.get("value")
            source = raw.get("source") or NO_SOURCE
            given = raw.get("unit")
            if given and unit and given.strip() != unit:
                converted = convert_unit(value, given, unit)
                self.assumptions.append(f"«{name}»: {fmt(value)} {given} пересчитано в {fmt(converted)} {unit}.")
                value = converted
            elif given and not unit:
                unit = given
        else:
            value, source = raw, NO_SOURCE
        if source == NO_SOURCE:
            self.warnings.append(f"Для параметра «{name}» ({key}) не указан источник.")
        self.params.append(Param(key, name, value, unit, source))
        return value

    # ---- ход расчёта ----------------------------------------------------
    def norm(self, ref: str) -> None:
        if ref not in self.norms:
            self.norms.append(ref)

    def step(self, title: str, norm: str, formula: str, substitution: str,
             value: float, unit: str = "", symbol: str = "") -> float:
        self.norm(norm)
        res = f"{symbol} = {fmt(value)} {unit}".strip() if symbol else f"{fmt(value)} {unit}".strip()
        self.steps.append(Step(title, norm, formula, substitution, res))
        return value

    def check(self, text: str, ok: bool, note: str = "") -> bool:
        self.checks.append(Check(text, bool(ok), note))
        return bool(ok)

    def warn(self, text: str) -> None:
        self.warnings.append(text)

    def assume(self, text: str) -> None:
        self.assumptions.append(text)

    # ---- вывод ----------------------------------------------------------
    def verdict(self) -> str:
        if not self.checks:
            return "НЕТ ПРОВЕРОК"
        return "ВЫПОЛНЕНО" if all(c.ok for c in self.checks) else "НЕ ВЫПОЛНЕНО"

    def to_markdown(self) -> str:
        out: list[str] = [f"# {self.title}", ""]
        out += ["## 1. Исходные данные", "",
                "| Параметр | Обозн. | Значение | Ед. | Источник |",
                "|---|---|---|---|---|"]
        for p in self.params:
            out.append(f"| {p.name} | `{p.key}` | {fmt(p.value)} | {p.unit} | {p.source} |")
        out += ["", "## 2. Нормативная база", ""]
        out += [f"- {n}" for n in self.norms] or ["- (не указана)"]
        out += ["", "## 3. Расчёт", ""]
        for i, s in enumerate(self.steps, 1):
            out += [f"### 3.{i}. {s.title}", "",
                    f"- **Норматив:** {s.norm}",
                    f"- **Формула:** `{s.formula}`",
                    f"- **Подстановка:** `{s.substitution}`",
                    f"- **Результат:** **{s.result}**", ""]
        out += ["## 4. Проверки", "", "| Условие | Результат | Примечание |", "|---|---|---|"]
        for c in self.checks:
            out.append(f"| {c.text} | {'✅ выполнено' if c.ok else '❌ НЕ выполнено'} | {c.note} |")
        out += ["", f"**Итог проверок: {self.verdict()}**", ""]
        if self.assumptions:
            out += ["## 5. Допущения", ""] + [f"- {a}" for a in self.assumptions] + [""]
        if self.warnings:
            out += ["## 6. Предупреждения", ""] + [f"- ⚠️ {w}" for w in self.warnings] + [""]
        out += ["---",
                "_Статус: предварительный инженерный расчёт, выполнен скриптом-помощником. "
                "Перед выпуском: сверить формулы и коэффициенты с действующей редакцией "
                "нормативов, выполнить независимую проверку (engineering-reviewer) и "
                "подписание ответственным инженером._"]
        return "\n".join(out)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "params": [p.__dict__ for p in self.params],
            "norms": self.norms,
            "steps": [s.__dict__ for s in self.steps],
            "checks": [c.__dict__ for c in self.checks],
            "warnings": self.warnings,
            "assumptions": self.assumptions,
            "verdict": self.verdict(),
        }


def load_input(argv: list[str] | None = None) -> tuple[dict, dict]:
    """Разбор CLI: script.py input.json [--out report.md] [--json]."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="JSON-файл исходных данных ('-' = stdin)")
    ap.add_argument("--out", help="сохранить отчёт в файл (.md или .json)")
    ap.add_argument("--json", action="store_true", help="вывести результат в JSON")
    args = ap.parse_args(argv)
    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
    return data, vars(args)


def emit(reports: list[CalcReport], opts: dict) -> int:
    """Вывести отчёты; код возврата 0 — проверки выполнены, EXIT_CHECKS_FAILED — есть невыполненные."""
    out = opts.get("out")
    if opts.get("json") or (out and str(out).lower().endswith(".json")):
        text = json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2)
    else:
        text = "\n\n".join(r.to_markdown() for r in reports)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Отчёт сохранён: {out}")
    else:
        getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
        print(text)
    return 0 if all(r.verdict() != "НЕ ВЫПОЛНЕНО" for r in reports) else EXIT_CHECKS_FAILED
