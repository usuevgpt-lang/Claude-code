#!/usr/bin/env python3
"""Предварительный прочностной расчёт элементов сосудов по ГОСТ 34233.x-2017.

Запуск:
    python vessel_calc.py input.json [--out report.md] [--json]

Формат входа (все величины: давление — МПа, размеры — мм, напряжения — МПа):
{
  "title": "Корпус фильтра-сепаратора",
  "elements": [
    {"type": "cyl_internal", "name": "Обечайка",
     "p": {"value": 6.3, "source": "ОЛ заказчика, п.2"},
     "D": 1000, "s": 22, "c": 2.8, "sigma": 177, "phi": 1.0},
    ...
  ]
}

Поддерживаемые типы элементов:
  cyl_internal       цилиндрическая обечайка, внутреннее давление
  cyl_external       цилиндрическая обечайка, наружное давление (без колец жёсткости)
  cone_internal      гладкая коническая обечайка, внутреннее давление
  ellipsoidal_head   эллиптическое/полусферическое днище, внутреннее давление
  flat_head          плоское круглое днище/крышка
  opening            одиночное отверстие с радиальным штуцером (условие укрепления)
  test_pressure      пробное давление гидроиспытаний и проверка прочности при испытании
  allowable_stress   допускаемое напряжение по механическим характеристикам
  mass               масса обечаек, днищ, плоских деталей

Скрипт не содержит встроенных коэффициентов из таблиц стандартов:
[σ], φ, E, K, n_y и т.п. задаются во входных данных с указанием источника.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import NO_SOURCE, CalcReport, Param, emit, fmt, load_input  # noqa: E402

G34233_1 = "ГОСТ 34233.1-2017 (общие требования, допускаемые напряжения, прибавки)"
G34233_2 = "ГОСТ 34233.2-2017 (обечайки, днища, крышки)"
G34233_3 = "ГОСТ 34233.3-2017 (укрепление отверстий)"


def get_c(rep: CalcReport, d: dict) -> float:
    """Суммарная прибавка c = c1 + c2 + c3 (или готовое c)."""
    if "c" in d:
        return rep.get(d, "c", "Суммарная прибавка к толщине c = c1+c2+c3", "мм")
    c1 = rep.get(d, "c1", "Прибавка для компенсации коррозии/эрозии c1", "мм")
    c2 = rep.get(d, "c2", "Прибавка на минусовой допуск c2", "мм")
    c3 = rep.get(d, "c3", "Технологическая прибавка c3", "мм", default=0.0)
    c = c1 + c2 + c3
    rep.step("Суммарная прибавка к расчётной толщине", G34233_1,
             "c = c1 + c2 + c3", f"c = {fmt(c1)} + {fmt(c2)} + {fmt(c3)}", c, "мм", "c")
    return c


# --------------------------------------------------------------------------
def cyl_internal(d: dict) -> CalcReport:
    rep = CalcReport(f"Цилиндрическая обечайка под внутренним давлением — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    D = rep.get(d, "D", "Внутренний диаметр D", "мм")
    sig = rep.get(d, "sigma", "Допускаемое напряжение при расчётной температуре [σ]", "МПа")
    phi = rep.get(d, "phi", "Коэффициент прочности продольного сварного шва φp", "—")
    c = get_c(rep, d)
    s = rep.get(d, "s", "Исполнительная толщина стенки s", "мм", required=False)

    sp = rep.step("Расчётная толщина стенки", G34233_2 + ", расчёт гладкой обечайки",
                  "s_p = p·D / (2·[σ]·φp − p)",
                  f"s_p = {fmt(p)}·{fmt(D)} / (2·{fmt(sig)}·{fmt(phi)} − {fmt(p)})",
                  p * D / (2 * sig * phi - p), "мм", "s_p")
    sreq = rep.step("Требуемая толщина с прибавками", G34233_2,
                    "s ≥ s_p + c", f"{fmt(sp)} + {fmt(c)}", sp + c, "мм", "s_треб")
    if s is None:
        rep.warn("Исполнительная толщина не задана: принять ближайшую стандартную толщину листа "
                 "≥ s_треб и повторить расчёт с проверкой [p].")
        return rep
    pa = rep.step("Допускаемое внутреннее избыточное давление", G34233_2,
                  "[p] = 2·[σ]·φp·(s − c) / (D + (s − c))",
                  f"[p] = 2·{fmt(sig)}·{fmt(phi)}·({fmt(s)} − {fmt(c)}) / ({fmt(D)} + ({fmt(s)} − {fmt(c)}))",
                  2 * sig * phi * (s - c) / (D + (s - c)), "МПа", "[p]")
    rep.check(f"s = {fmt(s)} ≥ s_p + c = {fmt(sreq)} мм", s >= sreq)
    rep.check(f"[p] = {fmt(pa)} ≥ p = {fmt(p)} МПа", pa >= p)
    ratio = (s - c) / D
    lim = 0.1 if D >= 200 else 0.3
    rep.check(f"Применимость формул: (s − c)/D = {fmt(ratio)} ≤ {lim}", ratio <= lim,
              "условие применимости расчётных формул ГОСТ 34233.2 для D ≥ 200 мм / D < 200 мм")
    return rep


def cyl_external(d: dict) -> CalcReport:
    rep = CalcReport(f"Цилиндрическая обечайка под наружным давлением — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное наружное давление p", "МПа")
    D = rep.get(d, "D", "Внутренний диаметр D", "мм")
    s = rep.get(d, "s", "Исполнительная толщина стенки s", "мм")
    sig = rep.get(d, "sigma", "Допускаемое напряжение [σ]", "МПа")
    E = rep.get(d, "E", "Модуль продольной упругости при расчётной температуре E", "МПа")
    l = rep.get(d, "l", "Расчётная длина обечайки l", "мм")
    ny = rep.get(d, "ny", "Коэффициент запаса устойчивости n_y", "—")
    c = get_c(rep, d)
    se = s - c
    pP = rep.step("Допускаемое давление из условия прочности", G34233_2 + ", наружное давление",
                  "[p]_П = 2·[σ]·(s − c) / (D + (s − c))",
                  f"2·{fmt(sig)}·{fmt(se)} / ({fmt(D)} + {fmt(se)})",
                  2 * sig * se / (D + se), "МПа", "[p]_П")
    B1 = rep.step("Коэффициент B1", G34233_2,
                  "B1 = min{1; 9,45·(D/l)·√(D/(100·(s − c)))}",
                  f"min{{1; 9,45·({fmt(D)}/{fmt(l)})·√({fmt(D)}/(100·{fmt(se)}))}}",
                  min(1.0, 9.45 * (D / l) * math.sqrt(D / (100 * se))), "", "B1")
    pE = rep.step("Допускаемое давление из условия устойчивости в пределах упругости", G34233_2,
                  "[p]_E = 2,08·10⁻⁵·E/(n_y·B1) · (D/l) · [100·(s − c)/D]^2,5",
                  f"2,08e-5·{fmt(E)}/({fmt(ny)}·{fmt(B1)})·({fmt(D)}/{fmt(l)})·(100·{fmt(se)}/{fmt(D)})^2,5",
                  2.08e-5 * E / (ny * B1) * (D / l) * (100 * se / D) ** 2.5, "МПа", "[p]_E")
    pa = rep.step("Допускаемое наружное давление", G34233_2,
                  "[p] = [p]_П / √(1 + ([p]_П/[p]_E)²)",
                  f"{fmt(pP)} / √(1 + ({fmt(pP)}/{fmt(pE)})²)",
                  pP / math.sqrt(1 + (pP / pE) ** 2), "МПа", "[p]")
    rep.check(f"[p] = {fmt(pa)} ≥ p = {fmt(p)} МПа", pa >= p)
    rep.assume("Обечайка без колец жёсткости; расчётная длина l определена по ГОСТ 34233.2 "
               "(с учётом примыкающих днищ).")
    rep.warn("Формулы устойчивости требуют сверки обозначений и условий применимости с текстом "
             "ГОСТ 34233.2-2017 (раздел расчёта на наружное давление).")
    return rep


def cone_internal(d: dict) -> CalcReport:
    rep = CalcReport(f"Гладкая коническая обечайка под внутренним давлением — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    Dk = rep.get(d, "Dk", "Расчётный диаметр гладкой конической обечайки D_k", "мм")
    a = rep.get(d, "alpha_deg", "Половина угла раствора при вершине α1", "град")
    sig = rep.get(d, "sigma", "Допускаемое напряжение [σ]", "МПа")
    phi = rep.get(d, "phi", "Коэффициент прочности сварного шва φp", "—")
    c = get_c(rep, d)
    s = rep.get(d, "s", "Исполнительная толщина s_k", "мм", required=False)
    ca = math.cos(math.radians(a))
    sp = rep.step("Расчётная толщина стенки", G34233_2 + ", конические обечайки",
                  "s_k.p = p·D_k / (2·φp·[σ] − p) · 1/cos α1",
                  f"{fmt(p)}·{fmt(Dk)} / (2·{fmt(phi)}·{fmt(sig)} − {fmt(p)}) / cos {fmt(a)}°",
                  p * Dk / (2 * phi * sig - p) / ca, "мм", "s_k.p")
    sreq = sp + c
    rep.check(f"α1 = {fmt(a)}° ≤ 70°", a <= 70, "область применения формул для конических обечаек")
    if s is None:
        rep.step("Требуемая толщина", G34233_2, "s_k ≥ s_k.p + c", f"{fmt(sp)} + {fmt(c)}", sreq, "мм", "s_треб")
        return rep
    pa = rep.step("Допускаемое давление", G34233_2,
                  "[p] = 2·[σ]·φp·(s_k − c) / (D_k/cos α1 + (s_k − c))",
                  f"2·{fmt(sig)}·{fmt(phi)}·({fmt(s)} − {fmt(c)}) / ({fmt(Dk)}/{fmt(ca)} + {fmt(s - c)})",
                  2 * sig * phi * (s - c) / (Dk / ca + (s - c)), "МПа", "[p]")
    rep.check(f"s_k = {fmt(s)} ≥ {fmt(sreq)} мм", s >= sreq)
    rep.check(f"[p] = {fmt(pa)} ≥ p = {fmt(p)} МПа", pa >= p)
    rep.warn("Зоны сопряжения конуса с цилиндром (с тороидальным переходом или без) рассчитываются "
             "отдельно по ГОСТ 34233.2 — скрипт их не проверяет.")
    return rep


def ellipsoidal_head(d: dict) -> CalcReport:
    rep = CalcReport(f"Выпуклое (эллиптическое/полусферическое) днище — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    D = rep.get(d, "D", "Внутренний диаметр D", "мм")
    H = rep.get(d, "H", "Высота выпуклой части днища H (0,25D — эллиптическое 2:1; 0,5D — полусфера)", "мм")
    sig = rep.get(d, "sigma", "Допускаемое напряжение [σ]", "МПа")
    phi = rep.get(d, "phi", "Коэффициент прочности сварных швов днища φ (цельноштампованное — 1)", "—")
    c = get_c(rep, d)
    s = rep.get(d, "s", "Исполнительная толщина s1", "мм", required=False)
    R = rep.step("Радиус кривизны в вершине днища", G34233_2 + ", выпуклые днища",
                 "R = D² / (4·H)", f"{fmt(D)}² / (4·{fmt(H)})", D * D / (4 * H), "мм", "R")
    sp = rep.step("Расчётная толщина стенки", G34233_2,
                  "s_1p = p·R / (2·φ·[σ] − 0,5·p)",
                  f"{fmt(p)}·{fmt(R)} / (2·{fmt(phi)}·{fmt(sig)} − 0,5·{fmt(p)})",
                  p * R / (2 * phi * sig - 0.5 * p), "мм", "s_1p")
    sreq = sp + c
    rep.check(f"0,2 ≤ H/D = {fmt(H / D)} ≤ 0,5", 0.2 <= H / D <= 0.5, "область применения")
    if s is None:
        rep.step("Требуемая толщина", G34233_2, "s1 ≥ s_1p + c", f"{fmt(sp)} + {fmt(c)}", sreq, "мм", "s_треб")
        rep.warn("При штамповке днище утоняется: технологическую прибавку c3 согласовать с изготовителем "
                 "днищ (ГОСТ 6533-78 / ТУ поставщика).")
        return rep
    pa = rep.step("Допускаемое давление", G34233_2,
                  "[p] = 2·(s1 − c)·φ·[σ] / (R + 0,5·(s1 − c))",
                  f"2·({fmt(s)} − {fmt(c)})·{fmt(phi)}·{fmt(sig)} / ({fmt(R)} + 0,5·{fmt(s - c)})",
                  2 * (s - c) * phi * sig / (R + 0.5 * (s - c)), "МПа", "[p]")
    rep.check(f"s1 = {fmt(s)} ≥ {fmt(sreq)} мм", s >= sreq)
    rep.check(f"[p] = {fmt(pa)} ≥ p = {fmt(p)} МПа", pa >= p)
    r = (s - c) / D
    rep.check(f"0,002 ≤ (s1 − c)/D = {fmt(r)} ≤ 0,1", 0.002 <= r <= 0.1, "область применения")
    return rep


def flat_head(d: dict) -> CalcReport:
    rep = CalcReport(f"Плоское круглое днище/крышка — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    Dp = rep.get(d, "Dp", "Расчётный диаметр D_p (по типу закрепления)", "мм")
    K = rep.get(d, "K", "Коэффициент конструкции K (по типу закрепления, ГОСТ 34233.2)", "—")
    sig = rep.get(d, "sigma", "Допускаемое напряжение [σ]", "МПа")
    phi = rep.get(d, "phi", "Коэффициент прочности сварных швов φ", "—")
    c = get_c(rep, d)
    holes = rep.get(d, "openings_d", "Диаметры отверстий в днище (список)", "мм", required=False)
    if "K0" in d:
        K0 = rep.get(d, "K0", "Коэффициент ослабления отверстиями K0", "—")
    elif holes:
        x = sum(holes) / Dp
        K0 = rep.step("Коэффициент ослабления отверстиями (сумма диаметров на диаметре)", G34233_2,
                      "K0 = √((1 − (Σd/Dp)³) / (1 − Σd/Dp))",
                      f"Σd/Dp = {fmt(sum(holes))}/{fmt(Dp)} = {fmt(x)}",
                      math.sqrt((1 - x ** 3) / (1 - x)), "", "K0")
        rep.warn("Формулу K0 для отверстий в плоском днище сверить с ГОСТ 34233.2 (разные случаи "
                 "расположения отверстий).")
    else:
        K0 = 1.0
        rep.assume("Отверстий в днище нет: K0 = 1.")
    s = rep.get(d, "s", "Исполнительная толщина s1", "мм", required=False)
    sp = rep.step("Расчётная толщина", G34233_2 + ", плоские круглые днища",
                  "s_1p = K·K0·D_p·√(p / (φ·[σ]))",
                  f"{fmt(K)}·{fmt(K0)}·{fmt(Dp)}·√({fmt(p)}/({fmt(phi)}·{fmt(sig)}))",
                  K * K0 * Dp * math.sqrt(p / (phi * sig)), "мм", "s_1p")
    sreq = sp + c
    if s is None:
        rep.step("Требуемая толщина", G34233_2, "s1 ≥ s_1p + c", f"{fmt(sp)} + {fmt(c)}", sreq, "мм", "s_треб")
        return rep
    pa = rep.step("Допускаемое давление", G34233_2,
                  "[p] = ((s1 − c) / (K·K0·D_p))²·φ·[σ]",
                  f"(({fmt(s)} − {fmt(c)}) / ({fmt(K)}·{fmt(K0)}·{fmt(Dp)}))²·{fmt(phi)}·{fmt(sig)}",
                  ((s - c) / (K * K0 * Dp)) ** 2 * phi * sig, "МПа", "[p]")
    rep.check(f"s1 = {fmt(s)} ≥ {fmt(sreq)} мм", s >= sreq)
    rep.check(f"[p] = {fmt(pa)} ≥ p = {fmt(p)} МПа", pa >= p)
    r = (s - c) / Dp
    rep.check(f"(s1 − c)/D_p = {fmt(r)} ≤ 0,11", r <= 0.11,
              "при превышении ГОСТ 34233.2 уменьшает [p] поправочным коэффициентом, который скрипт не применяет: "
              "[p] выше завышено — выполнить расчёт по тексту стандарта")
    return rep


def opening(d: dict) -> CalcReport:
    rep = CalcReport(f"Укрепление одиночного отверстия — {d.get('name', '')}")
    shell = d.get("shell", "cyl")
    rep.assume(f"Тип укрепляемого элемента: {shell}; штуцер радиальный; отверстие одиночное "
               "(влияние соседних отверстий не учитывается).")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    sig = rep.get(d, "sigma", "Допускаемое напряжение материала обечайки/днища [σ]", "МПа")
    phi = rep.get(d, "phi", "Коэффициент φ для расчётной толщины в зоне отверстия", "—", default=1.0)
    s = rep.get(d, "s", "Исполнительная толщина обечайки/днища s", "мм")
    c = get_c(rep, d)
    if shell == "cyl":
        D = rep.get(d, "D", "Внутренний диаметр D", "мм")
        Dp = rep.step("Расчётный диаметр", G34233_3, "D_p = D", f"D_p = {fmt(D)}", D, "мм", "D_p")
        sp = rep.step("Расчётная толщина обечайки без отверстия", G34233_3,
                      "s_p = p·D_p / (2·φ·[σ] − p)",
                      f"{fmt(p)}·{fmt(Dp)} / (2·{fmt(phi)}·{fmt(sig)} − {fmt(p)})",
                      p * Dp / (2 * phi * sig - p), "мм", "s_p")
    elif shell in ("ellipsoidal", "hemispherical"):
        D = rep.get(d, "D", "Внутренний диаметр D", "мм")
        H = rep.get(d, "H", "Высота выпуклой части H", "мм")
        x = rep.get(d, "x", "Расстояние от центра отверстия до оси днища x", "мм")
        Dp = rep.step("Расчётный диаметр в месте отверстия", G34233_3,
                      "D_p = 2·D²/(4H)·√(1 − 4·(D² − 4H²)·x²/D⁴)",
                      f"2·{fmt(D)}²/(4·{fmt(H)})·√(1 − 4·({fmt(D)}² − 4·{fmt(H)}²)·{fmt(x)}²/{fmt(D)}⁴)",
                      2 * D * D / (4 * H) * math.sqrt(1 - 4 * (D * D - 4 * H * H) * x * x / D ** 4), "мм", "D_p")
        sp = rep.step("Расчётная толщина днища без отверстия", G34233_3,
                      "s_p = p·D_p / (4·φ·[σ] − p)",
                      f"{fmt(p)}·{fmt(Dp)} / (4·{fmt(phi)}·{fmt(sig)} − {fmt(p)})",
                      p * Dp / (4 * phi * sig - p), "мм", "s_p")
    elif shell == "cone":
        Dk = rep.get(d, "Dk", "Расчётный диаметр конуса в месте отверстия D_k", "мм")
        a = rep.get(d, "alpha_deg", "Половина угла раствора α1", "град")
        Dp = rep.step("Расчётный диаметр", G34233_3, "D_p = D_k / cos α1",
                      f"{fmt(Dk)} / cos {fmt(a)}°", Dk / math.cos(math.radians(a)), "мм", "D_p")
        sp = rep.step("Расчётная толщина конуса без отверстия", G34233_3,
                      "s_p = p·D_p / (2·φ·[σ] − p)",
                      f"{fmt(p)}·{fmt(Dp)} / (2·{fmt(phi)}·{fmt(sig)} − {fmt(p)})",
                      p * Dp / (2 * phi * sig - p), "мм", "s_p")
    else:
        raise SystemExit(f"Неизвестный тип элемента shell='{shell}' (cyl|ellipsoidal|hemispherical|cone)")

    dn = rep.get(d, "d", "Внутренний диаметр штуцера d", "мм")
    cs = rep.get(d, "cs", "Сумма прибавок к толщине стенки штуцера c_s", "мм")
    dp = rep.step("Расчётный диаметр отверстия (радиальный штуцер)", G34233_3,
                  "d_p = d + 2·c_s", f"{fmt(dn)} + 2·{fmt(cs)}", dn + 2 * cs, "мм", "d_p")
    L0 = math.sqrt(Dp * (s - c))
    d0 = rep.step("Диаметр отверстия, не требующего укрепления (с учётом избыточной толщины)", G34233_3,
                  "d_0 = 2·((s − c)/s_p − 0,8)·√(D_p·(s − c))",
                  f"2·(({fmt(s)} − {fmt(c)})/{fmt(sp)} − 0,8)·√({fmt(Dp)}·{fmt(s - c)})",
                  2 * ((s - c) / sp - 0.8) * L0, "мм", "d_0")
    need_reinf = dp > d0

    # стенка штуцера проверяется всегда, когда задана (и обязательна, если нужна проверка укрепления)
    s1 = rep.get(d, "s1", "Исполнительная толщина стенки штуцера s1", "мм", required=need_reinf)
    s1p = None
    if s1 is not None:
        sig1 = rep.get(d, "sigma1", "Допускаемое напряжение материала штуцера [σ]1", "МПа")
        phi1 = rep.get(d, "phi1", "Коэффициент прочности продольного шва штуцера φ1", "—", default=1.0)
        s1p = rep.step("Расчётная толщина стенки штуцера", G34233_3,
                       "s_1p = p·(d + 2c_s) / (2·φ1·[σ]1 − p)",
                       f"{fmt(p)}·{fmt(dp)} / (2·{fmt(phi1)}·{fmt(sig1)} − {fmt(p)})",
                       p * dp / (2 * phi1 * sig1 - p), "мм", "s_1p")
        rep.check(f"Стенка штуцера: s1 = {fmt(s1)} ≥ s_1p + c_s = {fmt(s1p + cs)} мм", s1 >= s1p + cs)
    else:
        rep.warn("Толщина стенки штуцера s1 не задана — прочность стенки штуцера не проверена.")

    base = Dk if shell == "cone" else D
    lim = 0.6 if shell in ("ellipsoidal", "hemispherical") else 1.0
    ratio = (dp - 2 * cs) / base
    rep.check(f"Применимость: (d_p − 2c_s)/D = {fmt(ratio)} ≤ {lim}", ratio <= lim,
              "условие применимости метода укрепления ГОСТ 34233.3 — сверить с пунктом стандарта")

    if not need_reinf:
        rep.check(f"d_p = {fmt(dp)} ≤ d_0 = {fmt(d0)} мм — дополнительное укрепление не требуется", True)
        return rep
    rep.step("Сравнение с d_0: требуется проверка условия укрепления", G34233_3,
             "d_p > d_0", f"{fmt(dp)} > {fmt(d0)}", dp - d0, "мм", "d_p − d_0")

    l1 = rep.get(d, "l1", "Исполнительная длина наружной части штуцера l1", "мм")
    lp_avail = rep.get(d, "l", "Расстояние до ближайшего отверстия/несущего элемента l", "мм", required=False)
    lp = min(L0, lp_avail) if lp_avail else L0
    rep.step("Ширина зоны укрепления в обечайке", G34233_3,
             "l_p = min{l; √(D_p·(s − c))}", f"√({fmt(Dp)}·{fmt(s - c)}) = {fmt(L0)}"
             + (f"; l = {fmt(lp_avail)}" if lp_avail else ""), lp, "мм", "l_p")
    if not lp_avail:
        rep.assume("Расстояние до ближайшего отверстия/несущего элемента не задано: l_p = √(D_p(s−c)).")
    l1p = rep.step("Расчётная длина наружной части штуцера", G34233_3,
                   "l_1p = min{l1; 1,25·√((d + 2c_s)·(s1 − c_s))}",
                   f"min{{{fmt(l1)}; 1,25·√({fmt(dp)}·({fmt(s1)} − {fmt(cs)}))}}",
                   min(l1, 1.25 * math.sqrt(dp * (s1 - cs))), "мм", "l_1p")
    chi1 = min(1.0, sig1 / sig)
    A1 = l1p * (s1 - s1p - cs) * chi1
    A2 = 0.0
    if d.get("s2"):
        s2 = rep.get(d, "s2", "Толщина накладного кольца s2", "мм")
        l2 = rep.get(d, "l2", "Ширина накладного кольца l2", "мм")
        sig2 = rep.get(d, "sigma2", "Допускаемое напряжение материала кольца [σ]2", "МПа")
        l2p = rep.step("Расчётная ширина накладного кольца", G34233_3,
                       "l_2p = min{l2; √(D_p·(s2 + s − c))}",
                       f"min{{{fmt(l2)}; √({fmt(Dp)}·({fmt(s2)} + {fmt(s - c)}))}}",
                       min(l2, math.sqrt(Dp * (s2 + s - c))), "мм", "l_2p")
        A2 = l2p * s2 * min(1.0, sig2 / sig)
    A3 = 0.0
    if d.get("l3"):
        l3 = rep.get(d, "l3", "Длина внутренней части штуцера l3", "мм")
        s3 = rep.get(d, "s3", "Толщина внутренней части штуцера s3", "мм")
        cs1 = rep.get(d, "cs1", "Прибавка для внутренней части штуцера c_s1", "мм")
        sig3 = rep.get(d, "sigma3", "Допускаемое напряжение внутренней части [σ]3", "МПа", default=sig1)
        l3p = rep.step("Расчётная длина внутренней части штуцера", G34233_3,
                       "l_3p = min{l3; 0,5·√((d + 2c_s)·(s3 − c_s − c_s1))}",
                       f"min{{{fmt(l3)}; 0,5·√({fmt(dp)}·({fmt(s3)} − {fmt(cs)} − {fmt(cs1)}))}}",
                       min(l3, 0.5 * math.sqrt(dp * (s3 - cs - cs1))), "мм", "l_3p")
        A3 = l3p * (s3 - cs - cs1) * min(1.0, sig3 / sig)
    A_shell = lp * (s - sp - c)
    d0p = rep.step("Расчётный диаметр отверстия, не требующего укрепления при отсутствии избыточной толщины",
                   G34233_3, "d_0p = 0,4·√(D_p·(s − c))", f"0,4·{fmt(L0)}", 0.4 * L0, "мм", "d_0p")
    lhs = rep.step("Площадь укрепляющих элементов (левая часть условия)", G34233_3,
                   "A = l_1p·(s1 − s_1p − c_s)·χ1 + l_2p·s2·χ2 + l_3p·(s3 − c_s − c_s1)·χ3 + l_p·(s − s_p − c)",
                   f"{fmt(A1)} + {fmt(A2)} + {fmt(A3)} + {fmt(A_shell)}  (χ1 = {fmt(chi1)})",
                   A1 + A2 + A3 + A_shell, "мм²", "A")
    rhs = rep.step("Требуемая площадь укрепления (правая часть условия)", G34233_3,
                   "A_треб = 0,5·(d_p − d_0p)·s_p",
                   f"0,5·({fmt(dp)} − {fmt(d0p)})·{fmt(sp)}",
                   0.5 * (dp - d0p) * sp, "мм²", "A_треб")
    rep.check(f"Условие укрепления: A = {fmt(lhs)} ≥ A_треб = {fmt(rhs)} мм²", lhs >= rhs)
    rep.warn("Проверено только условие укрепления (баланс площадей). Допускаемое давление ослабленного "
             "элемента (коэффициент V), наклонные/смещённые штуцеры, взаимное влияние отверстий и "
             "внешние нагрузки на штуцер — по полному методу ГОСТ 34233.3-2017 / ПО (ПАССАТ и т.п.).")
    return rep


def test_pressure(d: dict) -> CalcReport:
    rep = CalcReport(f"Пробное давление гидравлического испытания — {d.get('name', '')}")
    p = rep.get(d, "p", "Расчётное давление p", "МПа")
    k = rep.get(d, "k", "Коэффициент пробного давления k (по ФНП ОРПД / ТР ТС 032/2013 / ГОСТ 34347 / ОТТ заказчика)", "—")
    s20 = rep.get(d, "sigma20", "Допускаемое напряжение при 20 °C [σ]20", "МПа")
    st = rep.get(d, "sigmat", "Допускаемое напряжение при расчётной температуре [σ]t", "МПа")
    ppr = rep.step("Пробное давление", "ФНП ОРПД (приказ Ростехнадзора № 536 от 15.12.2020); ТР ТС 032/2013; ГОСТ 34347-2017",
                   "P_пр = k·p·[σ]20/[σ]t", f"{fmt(k)}·{fmt(p)}·{fmt(s20)}/{fmt(st)}",
                   k * p * s20 / st, "МПа", "P_пр")
    rep.warn("Минимальные значения пробного давления, особые случаи (литые сосуды, низкое давление, "
             "многокамерные аппараты) и требования заказчика проверить по действующему тексту ФНП ОРПД, "
             "ГОСТ 34347-2017 и ОТТ/ТЗ заказчика.")
    if "Re20" in d:
        Re = rep.get(d, "Re20", "Предел текучести при 20 °C R_e/20 (R_p0,2/20)", "МПа")
        nt = rep.get(d, "nt_test", "Коэффициент запаса по текучести для условий испытаний n_т", "—")
        eta = rep.get(d, "eta", "Поправочный коэффициент η (прокат — 1, отливки — по ГОСТ)", "—", default=1.0)
        si = rep.step("Допускаемое напряжение для условий испытаний", G34233_1,
                      "[σ]_и = η·R_e/20 / n_т", f"{fmt(eta)}·{fmt(Re)}/{fmt(nt)}", eta * Re / nt, "МПа", "[σ]_и")
        ph = 0.0
        if "h_water" in d:
            h = rep.get(d, "h_water", "Высота столба воды над рассчитываемым элементом", "м")
            ph = rep.step("Гидростатическое давление при испытании", "—", "p_г = ρ·g·h·10⁻⁶",
                          f"1000·9,81·{fmt(h)}·1e-6", 1000 * 9.81 * h * 1e-6, "МПа", "p_г")
        if "D" in d:
            D = rep.get(d, "D", "Внутренний диаметр обечайки D", "мм")
            s = rep.get(d, "s", "Исполнительная толщина обечайки s", "мм")
            c = get_c(rep, d)
            phi = rep.get(d, "phi", "Коэффициент прочности шва φp", "—")
            pa = rep.step("Допускаемое давление обечайки в условиях испытаний", G34233_2,
                          "[p]_и = 2·[σ]_и·φp·(s − c) / (D + (s − c))",
                          f"2·{fmt(si)}·{fmt(phi)}·{fmt(s - c)} / ({fmt(D)} + {fmt(s - c)})",
                          2 * si * phi * (s - c) / (D + (s - c)), "МПа", "[p]_и")
            rep.check(f"P_пр + p_г = {fmt(ppr + ph)} ≤ [p]_и = {fmt(pa)} МПа", ppr + ph <= pa)
            rep.assume("Прибавка c в условиях испытаний принята как в рабочих условиях (консервативно).")
    return rep


def allowable_stress(d: dict) -> CalcReport:
    rep = CalcReport(f"Допускаемое напряжение по механическим характеристикам — {d.get('name', '')}")
    rep.warn("Предпочтительно брать [σ] непосредственно из таблиц ГОСТ 34233.1-2017 (прил. А) для марки, "
             "толщины и температуры. Расчёт по характеристикам — для материалов, отсутствующих в таблицах, "
             "при наличии гарантированных значений (сертификат/ТУ/ГОСТ на прокат).")
    eta = rep.get(d, "eta", "Поправочный коэффициент η", "—")
    Re = rep.get(d, "Re_t", "Минимальный предел текучести при расчётной температуре R_e/t (R_p0,2/t)", "МПа")
    Rm = rep.get(d, "Rm20", "Минимальный предел прочности при 20 °C R_m/20", "МПа")
    nt = rep.get(d, "nt", "Коэффициент запаса по пределу текучести n_т", "—")
    nb = rep.get(d, "nb", "Коэффициент запаса по пределу прочности n_в", "—")
    cands = {"R_e/t / n_т": Re / nt, "R_m/20 / n_в": Rm / nb}
    if "RD" in d:
        RD = rep.get(d, "RD", "Предел длительной прочности за 10⁵ ч при t", "МПа")
        nd = rep.get(d, "nd", "Коэффициент запаса по длительной прочности n_д", "—")
        cands["R_д / n_д"] = RD / nd
    if "R1" in d:
        R1 = rep.get(d, "R1", "Условный предел ползучести 1%/10⁵ ч при t", "МПа")
        npz = rep.get(d, "np", "Коэффициент запаса по пределу ползучести n_п", "—")
        cands["R_1% / n_п"] = R1 / npz
    sub = "; ".join(f"{k} = {fmt(v)}" for k, v in cands.items())
    rep.step("Допускаемое напряжение", G34233_1, "[σ] = η·min{R_e/t/n_т; R_m/20/n_в; R_д/n_д; R_1%/n_п}",
             f"{fmt(eta)}·min{{{sub}}}", eta * min(cands.values()), "МПа", "[σ]")
    return rep


def mass(d: dict) -> CalcReport:
    rep = CalcReport(f"Масса деталей — {d.get('name', '')}")
    rho = rep.get(d, "rho", "Плотность материала ρ", "кг/м³")
    total = 0.0
    parts = d.get("parts", [])
    parts = parts.get("value", []) if isinstance(parts, dict) else parts
    for i, raw_part in enumerate(parts, 1):
        part = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in raw_part.items()}
        if any(isinstance(v, dict) for v in raw_part.values()):
            rep.params.append(Param(f"parts[{i}]", f"Деталь {i}: {part.get('kind')}", "см. ход расчёта", "",
                                    "; ".join(f"{k}: {v.get('source')}" for k, v in raw_part.items()
                                              if isinstance(v, dict) and v.get("source")) or NO_SOURCE))
        kind = part["kind"]
        n = part.get("qty", 1)
        if kind == "cylinder":
            D, s, L = part["D"], part["s"], part["L"]
            m = rho * math.pi * (D + s) * s * L * 1e-9
            rep.step(f"{i}. Обечайка Ø{fmt(D)}×{fmt(s)}, L={fmt(L)} (×{n})", "геометрия",
                     "m = ρ·π·(D + s)·s·L", f"{fmt(rho)}·π·({fmt(D)} + {fmt(s)})·{fmt(s)}·{fmt(L)}·10⁻⁹",
                     m * n, "кг", "m")
        elif kind == "ellipsoidal_head":
            D, s, H, h1 = part["D"], part["s"], part.get("H", part["D"] / 4), part.get("h1", 0)
            a = (D + s) / 2
            cc = H + s / 2
            if abs(a - cc) < 1e-9:
                area = 2 * math.pi * a * a
            elif cc < a:   # сплюснутый полуэллипсоид (обычные днища, H < D/2)
                e = math.sqrt(1 - (cc / a) ** 2)
                area = math.pi * a * a * (1 + (1 - e * e) / e * math.atanh(e))
            else:          # вытянутый полуэллипсоид (H > D/2)
                e = math.sqrt(1 - (a / cc) ** 2)
                area = math.pi * a * a * (1 + cc / (a * e) * math.asin(e))
            area += math.pi * (D + s) * h1
            m = rho * area * s * 1e-9
            rep.step(f"{i}. Днище эллиптическое Ø{fmt(D)}×{fmt(s)}, H={fmt(H)}, h1={fmt(h1)} (×{n})",
                     "геометрия (срединная поверхность полуэллипсоида + отбортовка)",
                     "m = ρ·s·[π·a²·(1 + (1−e²)/e·artanh e) + π·(D+s)·h1]",
                     f"a = {fmt(a)}, c = {fmt(cc)}, S = {fmt(area * 1e-6)} м²", m * n, "кг", "m")
            rep.warn("Массу штампованных днищ сверить с ГОСТ 6533-78 / каталогом поставщика (учёт утонения).")
        elif kind == "plate_round":
            D, s = part["D"], part["s"]
            m = rho * math.pi * D * D / 4 * s * 1e-9
            rep.step(f"{i}. Диск Ø{fmt(D)}×{fmt(s)} (×{n})", "геометрия", "m = ρ·π·D²/4·s",
                     f"{fmt(rho)}·π·{fmt(D)}²/4·{fmt(s)}·10⁻⁹", m * n, "кг", "m")
        elif kind == "plate_rect":
            a, b, s = part["a"], part["b"], part["s"]
            m = rho * a * b * s * 1e-9
            rep.step(f"{i}. Пластина {fmt(a)}×{fmt(b)}×{fmt(s)} (×{n})", "геометрия", "m = ρ·a·b·s",
                     f"{fmt(rho)}·{fmt(a)}·{fmt(b)}·{fmt(s)}·10⁻⁹", m * n, "кг", "m")
        else:
            raise SystemExit(f"Неизвестный вид детали: {kind}")
        total += m * n
    rep.step("Итого масса", "—", "Σm", "сумма позиций", total, "кг", "M")
    rep.assume("Масса без сварных швов, крепежа и покрытий; отверстия не вычитаются.")
    return rep


HANDLERS = {
    "cyl_internal": cyl_internal,
    "cyl_external": cyl_external,
    "cone_internal": cone_internal,
    "ellipsoidal_head": ellipsoidal_head,
    "flat_head": flat_head,
    "opening": opening,
    "test_pressure": test_pressure,
    "allowable_stress": allowable_stress,
    "mass": mass,
}


def run(data: dict) -> list[CalcReport]:
    reports = []
    for el in data.get("elements", []):
        t = el.get("type")
        if t not in HANDLERS:
            raise SystemExit(f"Неизвестный тип элемента '{t}'. Допустимо: {', '.join(HANDLERS)}")
        reports.append(HANDLERS[t](el))
    return reports


if __name__ == "__main__":
    data, opts = load_input()
    sys.exit(emit(run(data), opts))
