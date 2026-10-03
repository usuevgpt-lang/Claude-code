#!/usr/bin/env python3
"""Теплообменные аппараты: тепловой баланс, LMTD, площадь, оценка трубного пучка.

Запуск:
    python hx_calc.py input.json [--out report.md] [--json]

Единицы: расход — кг/с, теплоёмкость — кДж/(кг·К), температура — °C, мощность — кВт,
коэффициенты теплоотдачи/теплопередачи — Вт/(м²·К), термические сопротивления — м²·К/Вт,
размеры труб — мм, длина труб — м.

Типы расчётов (cases[].type):
  heat_balance   тепловой баланс, неизвестная температура или мощность
  lmtd           среднелогарифмический температурный напор, поправка F (1 ход в кожухе / 2,4.. в трубах)
  overall_u      коэффициент теплопередачи по термическим сопротивлениям
  area           требуемая площадь теплообмена с запасом
  tubes          число труб, скорость в трубном пространстве
  bundle         диаметр трубного пучка (эмпирическая зависимость D_b = d_o·(N_t/K1)^(1/n1))

Прочностной расчёт (трубные решётки, кожух) — ГОСТ 34233.7-2017 / novaprom-pressure-vessels.
Окончательный тепловой расчёт — специализированное ПО (HTRI, Aspen EDR) или методика изготовителя.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import CalcReport, emit, fmt, load_input  # noqa: E402

N_BAL = "Уравнение теплового баланса Φ = G·c_p·Δt"
N_LMTD = "Среднелогарифмический температурный напор; F для кожухотрубного аппарата 1–2N (Bowman–Mueller–Nagle)"
N_U = "Термические сопротивления стенки, загрязнений и теплоотдачи (отнесено к наружной поверхности труб)"


def heat_balance(d: dict) -> CalcReport:
    rep = CalcReport(f"Тепловой баланс — {d.get('name', '')}")
    sides = {}
    for side, label in (("hot", "горячий"), ("cold", "холодный")):
        s = d[side]
        sides[side] = {
            "G": rep.get(s, "G", f"Расход ({label} теплоноситель)", "кг/с", required=False),
            "cp": rep.get(s, "cp", f"Теплоёмкость c_p ({label})", "кДж/(кг·К)", required=False),
            "t_in": rep.get(s, "t_in", f"Температура на входе ({label})", "°C", required=False),
            "t_out": rep.get(s, "t_out", f"Температура на выходе ({label})", "°C", required=False),
        }
    h, c = sides["hot"], sides["cold"]
    Q = None
    if None not in (h["G"], h["cp"], h["t_in"], h["t_out"]):
        Q = rep.step("Тепловая мощность по горячему теплоносителю", N_BAL, "Φ = G_г·c_г·(t_г.вх − t_г.вых)",
                     f"{fmt(h['G'])}·{fmt(h['cp'])}·({fmt(h['t_in'])} − {fmt(h['t_out'])})",
                     h["G"] * h["cp"] * (h["t_in"] - h["t_out"]), "кВт", "Φ")
    if None not in (c["G"], c["cp"], c["t_in"], c["t_out"]):
        Qc = rep.step("Тепловая мощность по холодному теплоносителю", N_BAL, "Φ = G_х·c_х·(t_х.вых − t_х.вх)",
                      f"{fmt(c['G'])}·{fmt(c['cp'])}·({fmt(c['t_out'])} − {fmt(c['t_in'])})",
                      c["G"] * c["cp"] * (c["t_out"] - c["t_in"]), "кВт", "Φ_х")
        if Q is None:
            Q = Qc
        else:
            loss = rep.get(d, "loss_frac", "Допустимый небаланс (теплопотери), доля", "—", default=0.05)
            rep.check(f"Небаланс |Φ_г − Φ_х|/Φ_г = {fmt(abs(Q - Qc) / Q)} ≤ {fmt(loss)}", abs(Q - Qc) / Q <= loss)
    if Q is None:
        raise SystemExit("Недостаточно данных: полностью задайте хотя бы одну сторону (G, cp, t_in, t_out).")
    for side, s, sign in (("горячего", h, -1), ("холодного", c, 1)):
        if s["G"] is None and None not in (s["cp"], s["t_in"], s["t_out"]):
            rep.step(f"Расход {side} теплоносителя", N_BAL, "G = Φ/(c_p·|Δt|)",
                     f"{fmt(Q)}/({fmt(s['cp'])}·{fmt(abs(s['t_out'] - s['t_in']))})",
                     Q / (s["cp"] * abs(s["t_out"] - s["t_in"])), "кг/с", "G")
        elif s["t_out"] is None and None not in (s["G"], s["cp"], s["t_in"]):
            rep.step(f"Температура {side} теплоносителя на выходе", N_BAL, "t_вых = t_вх ± Φ/(G·c_p)",
                     f"{fmt(s['t_in'])} {'+' if sign > 0 else '−'} {fmt(Q)}/({fmt(s['G'])}·{fmt(s['cp'])})",
                     s["t_in"] + sign * Q / (s["G"] * s["cp"]), "°C", "t_вых")
    return rep


def f_1_2n(R: float, P: float) -> float:
    if abs(R - 1) < 1e-6:
        s2 = math.sqrt(2)
        num = P * s2 / (1 - P)
        den = math.log((2 - P * (2 - s2)) / (2 - P * (2 + s2)))
        return num / den
    S = math.sqrt(R * R + 1)
    num = S / (R - 1) * math.log((1 - P) / (1 - P * R))
    den = math.log((2 - P * (R + 1 - S)) / (2 - P * (R + 1 + S)))
    return num / den


def lmtd(d: dict) -> CalcReport:
    rep = CalcReport(f"Температурный напор — {d.get('name', '')}")
    T1 = rep.get(d, "T1", "Горячий теплоноситель: вход", "°C")
    T2 = rep.get(d, "T2", "Горячий теплоноситель: выход", "°C")
    t1 = rep.get(d, "t1", "Холодный теплоноситель: вход", "°C")
    t2 = rep.get(d, "t2", "Холодный теплоноситель: выход", "°C")
    flow = d.get("flow", "counter")
    if flow == "parallel":
        dA, dB = T1 - t1, T2 - t2
    else:
        dA, dB = T1 - t2, T2 - t1
    rep.check(f"Положительные концевые напоры: ΔT_A = {fmt(dA)}, ΔT_B = {fmt(dB)} К", dA > 0 and dB > 0,
              "иначе — пересечение температур, схема невозможна")
    if dA <= 0 or dB <= 0:
        return rep
    lm = rep.step("Среднелогарифмический температурный напор (противоток)" if flow != "parallel" else
                  "Среднелогарифмический температурный напор (прямоток)", N_LMTD,
                  "ΔT_лог = (ΔT_A − ΔT_B)/ln(ΔT_A/ΔT_B)", f"({fmt(dA)} − {fmt(dB)})/ln({fmt(dA)}/{fmt(dB)})",
                  (dA - dB) / math.log(dA / dB) if abs(dA - dB) > 1e-9 else dA, "К", "ΔT_лог")
    if flow == "1-2n":
        R = (T1 - T2) / (t2 - t1)
        P = (t2 - t1) / (T1 - t1)
        rep.step("Параметры R и P", N_LMTD, "R = (T1 − T2)/(t2 − t1); P = (t2 − t1)/(T1 − t1)",
                 f"R = {fmt(R)}, P = {fmt(P)}", P, "", "P")
        try:
            F = rep.step("Поправочный коэффициент F (1 ход в межтрубном, чётное число ходов в трубах)", N_LMTD,
                         "F = [√(R²+1)/(R−1)]·ln[(1−P)/(1−PR)] / ln{[2−P(R+1−√(R²+1))]/[2−P(R+1+√(R²+1))]}",
                         f"R = {fmt(R)}, P = {fmt(P)}", f_1_2n(R, P), "", "F")
        except (ValueError, ZeroDivisionError):
            rep.check("Схема 1–2N осуществима при заданных температурах", False,
                      "требуется несколько ходов в межтрубном пространстве или противоток")
            return rep
        Fmin = rep.get(d, "F_min", "Минимально приемлемый F (практика проектирования)", "—", default=0.75)
        rep.check(f"F = {fmt(F)} ≥ {fmt(Fmin)}", F >= Fmin, "при меньших F — 2 хода в кожухе или иная схема")
        rep.step("Эффективный температурный напор", N_LMTD, "ΔT = F·ΔT_лог", f"{fmt(F)}·{fmt(lm)}", F * lm, "К", "ΔT")
    return rep


def overall_u(d: dict) -> CalcReport:
    rep = CalcReport(f"Коэффициент теплопередачи — {d.get('name', '')}")
    ho = rep.get(d, "h_o", "Теплоотдача снаружи труб α_н", "Вт/(м²·К)")
    hi = rep.get(d, "h_i", "Теплоотдача внутри труб α_в", "Вт/(м²·К)")
    Rfo = rep.get(d, "R_fo", "Термическое сопротивление загрязнений снаружи", "м²·К/Вт")
    Rfi = rep.get(d, "R_fi", "Термическое сопротивление загрязнений внутри", "м²·К/Вт")
    do = rep.get(d, "d_o", "Наружный диаметр трубы", "мм") / 1000
    di = rep.get(d, "d_i", "Внутренний диаметр трубы", "мм") / 1000
    k = rep.get(d, "k_wall", "Теплопроводность материала труб λ", "Вт/(м·К)")
    rw = do * math.log(do / di) / (2 * k)
    inv = 1 / ho + Rfo + rw + (do / di) * (Rfi + 1 / hi)
    rep.step("Коэффициент теплопередачи (на наружную поверхность)", N_U,
             "1/U = 1/α_н + R_н + d_н·ln(d_н/d_в)/(2λ) + (d_н/d_в)·(R_в + 1/α_в)",
             f"1/{fmt(ho)} + {fmt(Rfo)} + {fmt(rw)} + {fmt(do / di)}·({fmt(Rfi)} + 1/{fmt(hi)})",
             1 / inv, "Вт/(м²·К)", "U")
    return rep


def area(d: dict) -> CalcReport:
    rep = CalcReport(f"Требуемая площадь теплообмена — {d.get('name', '')}")
    Q = rep.get(d, "Q", "Тепловая мощность Φ", "кВт")
    U = rep.get(d, "U", "Коэффициент теплопередачи U", "Вт/(м²·К)")
    dT = rep.get(d, "dT", "Эффективный температурный напор F·ΔT_лог", "К")
    m = rep.get(d, "margin", "Запас поверхности", "доля", default=0.0)
    A = rep.step("Расчётная площадь", "Φ = U·A·ΔT", "A = Φ·1000/(U·ΔT)", f"{fmt(Q)}·1000/({fmt(U)}·{fmt(dT)})",
                 Q * 1000 / (U * dT), "м²", "A")
    Ar = rep.step("Площадь с запасом", "—", "A_тр = A·(1 + запас)", f"{fmt(A)}·(1 + {fmt(m)})", A * (1 + m), "м²", "A_тр")
    if "A_actual" in d:
        Aa = rep.get(d, "A_actual", "Площадь принятого аппарата", "м²")
        rep.check(f"A_факт = {fmt(Aa)} ≥ A_тр = {fmt(Ar)} м²", Aa >= Ar)
    return rep


def tubes(d: dict) -> CalcReport:
    rep = CalcReport(f"Трубный пучок: количество труб и скорость — {d.get('name', '')}")
    A = rep.get(d, "A", "Требуемая площадь (по наружной поверхности)", "м²")
    do = rep.get(d, "d_o", "Наружный диаметр трубы", "мм") / 1000
    di = rep.get(d, "d_i", "Внутренний диаметр трубы", "мм") / 1000
    L = rep.get(d, "L", "Рабочая длина труб", "м")
    npass = rep.get(d, "passes", "Число ходов по трубам", "—")
    N = rep.step("Число труб", "геометрия", "N_t = A/(π·d_н·L)", f"{fmt(A)}/(π·{fmt(do)}·{fmt(L)})",
                 A / (math.pi * do * L), "шт", "N_t")
    Nt = math.ceil(N / npass) * npass
    rep.step("Число труб, кратное числу ходов", "—", "N_t' = ⌈N_t/z⌉·z", f"⌈{fmt(N)}/{fmt(npass)}⌉·{fmt(npass)}",
             Nt, "шт", "N_t'")
    if "G_t" in d:
        G = rep.get(d, "G_t", "Расход среды в трубах", "кг/с")
        rho = rep.get(d, "rho_t", "Плотность среды в трубах", "кг/м³")
        w = rep.step("Скорость в трубах", "уравнение неразрывности", "w = G/(ρ·(N_t'/z)·π·d_в²/4)",
                     f"{fmt(G)}/({fmt(rho)}·{fmt(Nt / npass)}·π·{fmt(di)}²/4)",
                     G / (rho * (Nt / npass) * math.pi * di * di / 4), "м/с", "w")
        if "w_min" in d:
            wmin = rep.get(d, "w_min", "Рекомендуемая минимальная скорость (загрязнение)", "м/с")
            rep.check(f"w = {fmt(w)} ≥ {fmt(wmin)} м/с", w >= wmin)
        if "w_max" in d:
            wmax = rep.get(d, "w_max", "Допустимая максимальная скорость (эрозия, ΔP)", "м/с")
            rep.check(f"w = {fmt(w)} ≤ {fmt(wmax)} м/с", w <= wmax)
    return rep


def bundle(d: dict) -> CalcReport:
    rep = CalcReport(f"Диаметр трубного пучка и кожуха (оценка) — {d.get('name', '')}")
    Nt = rep.get(d, "N_t", "Число труб", "шт")
    do = rep.get(d, "d_o", "Наружный диаметр трубы", "мм")
    K1 = rep.get(d, "K1", "Константа K1 (шаг, разбивка, число ходов)", "—")
    n1 = rep.get(d, "n1", "Показатель n1", "—")
    Db = rep.step("Диаметр трубного пучка", "Sinnott R.K., Coulson & Richardson's Chemical Engineering, Vol. 6 "
                  "(эмпирическая зависимость; константы — по таблице источника)",
                  "D_b = d_н·(N_t/K1)^(1/n1)", f"{fmt(do)}·({fmt(Nt)}/{fmt(K1)})^(1/{fmt(n1)})",
                  do * (Nt / K1) ** (1 / n1), "мм", "D_b")
    if "clearance" in d:
        cl = rep.get(d, "clearance", "Зазор пучок–кожух (тип пучка)", "мм")
        rep.step("Внутренний диаметр кожуха (оценка)", "—", "D_к = D_b + зазор", f"{fmt(Db)} + {fmt(cl)}",
                 Db + cl, "мм", "D_к")
    rep.warn("Оценка для предварительной компоновки. Размещение труб уточнить по трубной решётке "
             "(шаг, перегородки, анкерные связи, отбойник) и ряду диаметров по ГОСТ 9617-76 (проверить актуальность).")
    return rep


HANDLERS = {
    "heat_balance": heat_balance,
    "lmtd": lmtd,
    "overall_u": overall_u,
    "area": area,
    "tubes": tubes,
    "bundle": bundle,
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
