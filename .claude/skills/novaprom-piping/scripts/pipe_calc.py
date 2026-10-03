#!/usr/bin/env python3
"""Трубопроводы: толщина стенки, допускаемое давление, гидравлика жидкости.

Запуск:
    python pipe_calc.py input.json [--out report.md] [--json]

Единицы: давление — МПа (избыточное), размеры — мм, длины — м, расход жидкости — м³/ч.

Типы расчётов (cases[].type):
  wall_gost32388   технологические трубопроводы, ГОСТ 32388-2013 (наружный диаметр)
  wall_sp36        магистральные трубопроводы, СП 36.13330.2012
  wall_b31_3       ASME B31.3 (для зарубежных ТЗ / сравнения)
  bend_b31_3       толщина отвода (коэффициенты I по ASME B31.3)
  liquid_dp        скорость и потери давления жидкости (Дарси–Вейсбах)

Газовые потоки (Z, рабочий расход, ΔP газа) — скрипт навыка novaprom-gas-hydraulics.
Все коэффициенты (φ, [σ], m, k1, kн, n, E, W, Y) задаются во входных данных с источником.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import CalcReport, emit, fmt, load_input  # noqa: E402

N_32388 = "ГОСТ 32388-2013 «Трубопроводы технологические. Нормы и методы расчёта на прочность...»"
N_SP36 = "СП 36.13330.2012 «Магистральные трубопроводы» (актуализированная редакция СНиП 2.05.06-85*) с изменениями"
N_B313 = "ASME B31.3 Process Piping, п. 304.1.2 (прямые трубы), 304.2.1 (отводы)"
N_DARCY = "Уравнение Дарси–Вейсбаха, λ по Колбруку–Уайту"


def get_c(rep: CalcReport, d: dict) -> float:
    if "c" in d:
        return rep.get(d, "c", "Суммарная прибавка c", "мм")
    c1 = rep.get(d, "c1", "Прибавка на коррозию/эрозию c1", "мм")
    c2 = rep.get(d, "c2", "Прибавка на минусовой допуск c2", "мм")
    c = c1 + c2
    rep.step("Суммарная прибавка", N_32388, "c = c1 + c2", f"{fmt(c1)} + {fmt(c2)}", c, "мм", "c")
    return c


def wall_gost32388(d: dict) -> CalcReport:
    rep = CalcReport(f"Толщина стенки трубы, ГОСТ 32388-2013 — {d.get('name', '')}")
    P = rep.get(d, "P", "Расчётное давление P", "МПа")
    D = rep.get(d, "D", "Наружный диаметр трубы D", "мм")
    sig = rep.get(d, "sigma", "Допускаемое напряжение [σ] при расчётной температуре", "МПа")
    phi = rep.get(d, "phi_w", "Коэффициент прочности сварного шва φ_w", "—")
    c = get_c(rep, d)
    t = rep.get(d, "t", "Номинальная толщина стенки t", "мм", required=False)
    tR = rep.step("Расчётная толщина стенки", N_32388 + " — расчёт на внутреннее давление",
                  "t_R = P·D / (2·φ_w·[σ] + P)", f"{fmt(P)}·{fmt(D)} / (2·{fmt(phi)}·{fmt(sig)} + {fmt(P)})",
                  P * D / (2 * phi * sig + P), "мм", "t_R")
    treq = rep.step("Требуемая толщина с прибавками", N_32388, "t ≥ t_R + c", f"{fmt(tR)} + {fmt(c)}",
                    tR + c, "мм", "t_треб")
    if t is not None:
        pa = rep.step("Допускаемое давление", N_32388, "[P] = 2·φ_w·[σ]·(t − c) / (D − (t − c))",
                      f"2·{fmt(phi)}·{fmt(sig)}·({fmt(t)} − {fmt(c)}) / ({fmt(D)} − ({fmt(t)} − {fmt(c)}))",
                      2 * phi * sig * (t - c) / (D - (t - c)), "МПа", "[P]")
        rep.check(f"t = {fmt(t)} ≥ t_треб = {fmt(treq)} мм", t >= treq)
        rep.check(f"[P] = {fmt(pa)} ≥ P = {fmt(P)} МПа", pa >= P)
    rep.warn("Сверить формулу и условия применимости (t/D) с п. ГОСТ 32388-2013 для внутреннего давления; "
             "прочие нагрузки (изгиб, температурные, вибрация) — поверочным расчётом (СТАРТ-ПРОФ и т.п.).")
    return rep


def wall_sp36(d: dict) -> CalcReport:
    rep = CalcReport(f"Толщина стенки магистрального трубопровода, СП 36.13330.2012 — {d.get('name', '')}")
    p = rep.get(d, "p", "Рабочее (нормативное) давление p", "МПа")
    Dn = rep.get(d, "Dn", "Наружный диаметр трубы D_н", "мм")
    R1n = rep.get(d, "R1n", "Нормативное сопротивление растяжению R1н (= σ_в мин.)", "МПа")
    m = rep.get(d, "m", "Коэффициент условий работы m (по категории участка)", "—")
    k1 = rep.get(d, "k1", "Коэффициент надёжности по материалу k1", "—")
    kn = rep.get(d, "kn", "Коэффициент надёжности по ответственности k_н", "—")
    n = rep.get(d, "n", "Коэффициент надёжности по нагрузке (внутреннее давление) n", "—")
    R1 = rep.step("Расчётное сопротивление растяжению", N_SP36, "R1 = R1н·m / (k1·k_н)",
                  f"{fmt(R1n)}·{fmt(m)} / ({fmt(k1)}·{fmt(kn)})", R1n * m / (k1 * kn), "МПа", "R1")
    delta = rep.step("Расчётная толщина стенки", N_SP36, "δ = n·p·D_н / (2·(R1 + n·p))",
                     f"{fmt(n)}·{fmt(p)}·{fmt(Dn)} / (2·({fmt(R1)} + {fmt(n)}·{fmt(p)}))",
                     n * p * Dn / (2 * (R1 + n * p)), "мм", "δ")
    if "delta_nom" in d:
        dn = rep.get(d, "delta_nom", "Принятая номинальная толщина стенки", "мм")
        rep.check(f"δ_ном = {fmt(dn)} ≥ δ = {fmt(delta)} мм", dn >= delta,
                  "округление до стандартной толщины по сортаменту; учесть минусовой допуск")
    rep.warn("При наличии продольных осевых сжимающих напряжений толщина уточняется с коэффициентом ψ1 "
             "по СП 36.13330.2012 — скрипт этот случай не учитывает. Для КПП СОД и узлов на объектах "
             "Транснефти/Газпрома применимый норматив определить по ОТТ/ТЗ заказчика.")
    return rep


def wall_b31_3(d: dict) -> CalcReport:
    rep = CalcReport(f"Толщина стенки трубы, ASME B31.3 — {d.get('name', '')}")
    P = rep.get(d, "P", "Design pressure P", "МПа")
    D = rep.get(d, "D", "Outside diameter D", "мм")
    S = rep.get(d, "S", "Allowable stress S (Table A-1)", "МПа")
    E = rep.get(d, "E", "Quality factor E (Table A-1A/A-1B)", "—")
    W = rep.get(d, "W", "Weld joint strength reduction factor W", "—")
    Y = rep.get(d, "Y", "Coefficient Y (Table 304.1.1)", "—")
    c = rep.get(d, "c", "Sum of allowances c (corrosion, thread/groove)", "мм")
    t = rep.step("Pressure design thickness", N_B313, "t = P·D / (2·(S·E·W + P·Y))",
                 f"{fmt(P)}·{fmt(D)} / (2·({fmt(S)}·{fmt(E)}·{fmt(W)} + {fmt(P)}·{fmt(Y)}))",
                 P * D / (2 * (S * E * W + P * Y)), "мм", "t")
    tm = rep.step("Minimum required thickness", N_B313, "t_m = t + c", f"{fmt(t)} + {fmt(c)}", t + c, "мм", "t_m")
    if "mill_tol" in d:
        mt = rep.get(d, "mill_tol", "Mill tolerance (доля, напр. 0.125)", "—")
        rep.step("Nominal thickness with mill tolerance", N_B313, "t_nom ≥ t_m / (1 − mill_tol)",
                 f"{fmt(tm)} / (1 − {fmt(mt)})", tm / (1 - mt), "мм", "t_nom")
    rep.check(f"t = {fmt(t)} < D/6 = {fmt(D / 6)} мм (условие применимости формулы)", t < D / 6)
    return rep


def bend_b31_3(d: dict) -> CalcReport:
    rep = CalcReport(f"Толщина стенки отвода, ASME B31.3 — {d.get('name', '')}")
    t = rep.get(d, "t_straight", "Расчётная толщина прямой трубы t (без прибавок)", "мм")
    R = rep.get(d, "R", "Радиус гиба по оси R1", "мм")
    D = rep.get(d, "D", "Наружный диаметр D", "мм")
    x = R / D
    Ii = rep.step("Коэффициент I для внутренней стороны (интрадос)", N_B313, "I = (4·R/D − 1) / (4·R/D − 2)",
                  f"(4·{fmt(x)} − 1) / (4·{fmt(x)} − 2)", (4 * x - 1) / (4 * x - 2), "", "I_инт")
    Ie = rep.step("Коэффициент I для наружной стороны (экстрадос)", N_B313, "I = (4·R/D + 1) / (4·R/D + 2)",
                  f"(4·{fmt(x)} + 1) / (4·{fmt(x)} + 2)", (4 * x + 1) / (4 * x + 2), "", "I_экстр")
    rep.step("Требуемая толщина на интрадосе (без прибавок)", N_B313, "t_инт = t·I_инт",
             f"{fmt(t)}·{fmt(Ii)}", t * Ii, "мм", "t_инт")
    rep.step("Требуемая толщина на экстрадосе (без прибавок)", N_B313, "t_экстр = t·I_экстр",
             f"{fmt(t)}·{fmt(Ie)}", t * Ie, "мм", "t_экстр")
    rep.warn("Для отводов по ГОСТ 17375/ГОСТ 30753 и отводов для КПП СОД (крутоизогнутые/гнутые) "
             "использовать требования стандарта на изделие и ОТТ заказчика; учесть утонение при гибке.")
    return rep


def colebrook(Re: float, rel: float) -> float:
    if Re < 2300:
        return 64 / Re
    lam = 0.02
    for _ in range(100):
        new = (-2 * math.log10(rel / 3.7 + 2.51 / (Re * math.sqrt(lam)))) ** -2
        if abs(new - lam) < 1e-12:
            break
        lam = new
    return lam


def liquid_dp(d: dict) -> CalcReport:
    rep = CalcReport(f"Гидравлика жидкости — {d.get('name', '')}")
    Q = rep.get(d, "Q", "Объёмный расход Q", "м³/ч")
    di = rep.get(d, "d_in", "Внутренний диаметр d", "мм") / 1000
    L = rep.get(d, "L", "Длина L", "м")
    k = rep.get(d, "roughness", "Эквивалентная шероховатость Δ", "мм") / 1000
    rho = rep.get(d, "rho", "Плотность жидкости ρ", "кг/м³")
    mu = rep.get(d, "mu", "Динамическая вязкость μ", "Па·с")
    zeta = rep.get(d, "sum_zeta", "Сумма КМС Σζ", "—", default=0.0)
    w = rep.step("Скорость", "уравнение неразрывности", "w = Q/(3600·π·d²/4)",
                 f"{fmt(Q)}/(3600·π·{fmt(di)}²/4)", Q / 3600 / (math.pi * di * di / 4), "м/с", "w")
    Re = rep.step("Число Рейнольдса", N_DARCY, "Re = w·d·ρ/μ", f"{fmt(w)}·{fmt(di)}·{fmt(rho)}/{fmt(mu)}",
                  w * di * rho / mu, "", "Re")
    lam = rep.step("Коэффициент трения", N_DARCY, "Колбрук–Уайт / 64/Re", f"Δ/d = {fmt(k / di)}",
                   colebrook(Re, k / di), "", "λ")
    dp = rep.step("Потери давления", N_DARCY, "Δp = (λ·L/d + Σζ)·ρ·w²/2",
                  f"({fmt(lam)}·{fmt(L)}/{fmt(di)} + {fmt(zeta)})·{fmt(rho)}·{fmt(w)}²/2·10⁻⁶",
                  (lam * L / di + zeta) * rho * w * w / 2 / 1e6, "МПа", "Δp")
    if "w_max" in d:
        wm = rep.get(d, "w_max", "Допустимая скорость", "м/с")
        rep.check(f"w = {fmt(w)} ≤ {fmt(wm)} м/с", w <= wm)
    if "dp_max" in d:
        dm = rep.get(d, "dp_max", "Допустимые потери давления", "МПа")
        rep.check(f"Δp = {fmt(dp)} ≤ {fmt(dm)} МПа", dp <= dm)
    return rep


HANDLERS = {
    "wall_gost32388": wall_gost32388,
    "wall_sp36": wall_sp36,
    "wall_b31_3": wall_b31_3,
    "bend_b31_3": bend_b31_3,
    "liquid_dp": liquid_dp,
}


def run(data: dict) -> list[CalcReport]:
    out = []
    for case in data.get("cases", []):
        t = case.get("type")
        if t not in HANDLERS:
            raise SystemExit(f"Неизвестный тип расчёта '{t}'. Допустимо: {', '.join(HANDLERS)}")
        out.append(HANDLERS[t](case))
    return out


if __name__ == "__main__":
    data, opts = load_input()
    sys.exit(emit(run(data), opts))
