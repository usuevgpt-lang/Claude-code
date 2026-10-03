#!/usr/bin/env python3
"""Быстросъёмные затворы (байонетные, с запорным кольцом) — предварительная оценка нагрузок.

Запуск:
    python closure_calc.py input.json [--out report.md] [--json]

Единицы: давление — МПа, размеры — мм, силы — Н (выводятся также в кН), напряжения — МПа.

Типы расчётов (cases[].type):
  axial_load     осевое усилие на крышку от давления
  bayonet        байонет: срез, смятие и изгиб зубьев (лепестков)
  locking_ring   разрезное запорное кольцо: срез кольца, смятие, срез бурта корпуса

Это оценка простыми формулами сопротивления материалов. Неравномерность распределения
нагрузки между зубьями, контактные эффекты и концентрация напряжений учитываются только
через коэффициент неравномерности k_н (вход). Окончательное обоснование — МКЭ и/или
методики ГОСТ 34233.x / ASME VIII Div.2 Part 5 с подтверждением испытаниями (ПМИ).
Допускаемые напряжения [τ], [σ_и], [σ_см] задаются во входных данных с источником.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import CalcReport, emit, fmt, load_input  # noqa: E402

N_SOPR = "Сопротивление материалов (срез, смятие, изгиб консоли) — оценочный расчёт"


def _axial(rep: CalcReport, d: dict) -> float:
    if "F" in d:
        return rep.get(d, "F", "Осевое усилие на крышку F", "Н")
    p = rep.get(d, "p", "Расчётное давление p (или пробное — для режима испытаний)", "МПа")
    Dg = rep.get(d, "D_seal", "Диаметр, по которому действует давление (средний диаметр уплотнения)", "мм")
    F = rep.step("Осевое усилие от давления", N_SOPR, "F = p·π·D_упл²/4", f"{fmt(p)}·π·{fmt(Dg)}²/4",
                 p * math.pi * Dg * Dg / 4, "Н", "F")
    rep.step("Осевое усилие, кН", "—", "F/1000", f"{fmt(F)}/1000", F / 1000, "кН", "F")
    return F


def axial_load(d: dict) -> CalcReport:
    rep = CalcReport(f"Осевое усилие на крышку затвора — {d.get('name', '')}")
    _axial(rep, d)
    return rep


def bayonet(d: dict) -> CalcReport:
    rep = CalcReport(f"Байонетный затвор: зубья (лепестки) — {d.get('name', '')}")
    F = _axial(rep, d)
    n = rep.get(d, "n", "Число зубьев в зацеплении n", "шт")
    kn = rep.get(d, "k_n", "Коэффициент неравномерности нагрузки между зубьями k_н", "—")
    b = rep.get(d, "b", "Ширина зуба по дуге (по окружности) b", "мм")
    h = rep.get(d, "h", "Толщина зуба в осевом направлении у основания h", "мм")
    e = rep.get(d, "e", "Радиальная длина контакта (перекрытие зубьев) e", "мм")
    arm = rep.get(d, "arm", "Плечо силы от основания зуба до центра контакта a", "мм")
    Fi = rep.step("Нагрузка на наиболее нагруженный зуб", N_SOPR, "F_з = k_н·F/n",
                  f"{fmt(kn)}·{fmt(F)}/{fmt(n)}", kn * F / n, "Н", "F_з")
    tau = rep.step("Касательное напряжение среза у основания зуба", N_SOPR, "τ = F_з/(b·h)",
                   f"{fmt(Fi)}/({fmt(b)}·{fmt(h)})", Fi / (b * h), "МПа", "τ")
    sig_b = rep.step("Напряжение изгиба у основания зуба", N_SOPR, "σ_и = 6·F_з·a/(b·h²)",
                     f"6·{fmt(Fi)}·{fmt(arm)}/({fmt(b)}·{fmt(h)}²)", 6 * Fi * arm / (b * h * h), "МПа", "σ_и")
    sig_c = rep.step("Напряжение смятия на контактной площадке", N_SOPR, "σ_см = F_з/(b·e)",
                     f"{fmt(Fi)}/({fmt(b)}·{fmt(e)})", Fi / (b * e), "МПа", "σ_см")
    t_all = rep.get(d, "tau_allow", "Допускаемое напряжение среза [τ]", "МПа")
    b_all = rep.get(d, "bend_allow", "Допускаемое напряжение изгиба [σ_и]", "МПа")
    c_all = rep.get(d, "crush_allow", "Допускаемое напряжение смятия [σ_см]", "МПа")
    rep.check(f"τ = {fmt(tau)} ≤ [τ] = {fmt(t_all)} МПа", tau <= t_all)
    rep.check(f"σ_и = {fmt(sig_b)} ≤ [σ_и] = {fmt(b_all)} МПа", sig_b <= b_all)
    rep.check(f"σ_см = {fmt(sig_c)} ≤ [σ_см] = {fmt(c_all)} МПа", sig_c <= c_all)
    rep.warn("Проверить ответные зубья корпуса (горловины) теми же формулами со своими размерами и материалом.")
    rep.warn("Обязательны устройства, исключающие открытие крышки под давлением и подачу давления при "
             "неполном закрытии (требование ФНП ОРПД / ТР ТС 032/2013 к быстросъёмным затворам — сверить пункт).")
    return rep


def locking_ring(d: dict) -> CalcReport:
    rep = CalcReport(f"Затвор с разрезным запорным кольцом — {d.get('name', '')}")
    F = _axial(rep, d)
    kn = rep.get(d, "k_n", "Коэффициент неравномерности (разрез кольца, зазоры)", "—")
    Dr = rep.get(d, "D_shear", "Диаметр поверхности среза кольца D_ср", "мм")
    hr = rep.get(d, "h_ring", "Осевая высота кольца в плоскости среза h_к", "мм")
    Dc = rep.get(d, "D_contact", "Средний диаметр площадки смятия D_см", "мм")
    ec = rep.get(d, "e_contact", "Радиальная ширина площадки смятия e", "мм")
    cut = rep.get(d, "cut_frac", "Доля окружности, занятая разрезом/вырезами кольца", "—", default=0.0)
    L = math.pi * (1 - cut)
    tau = rep.step("Срез кольца", N_SOPR, "τ = k_н·F/(π·D_ср·h_к·(1 − δ_разр))",
                   f"{fmt(kn)}·{fmt(F)}/(π·{fmt(Dr)}·{fmt(hr)}·{fmt(1 - cut)})", kn * F / (L * Dr * hr), "МПа", "τ")
    sc = rep.step("Смятие по опорной поверхности кольца", N_SOPR, "σ_см = k_н·F/(π·D_см·e·(1 − δ_разр))",
                  f"{fmt(kn)}·{fmt(F)}/(π·{fmt(Dc)}·{fmt(ec)}·{fmt(1 - cut)})", kn * F / (L * Dc * ec), "МПа", "σ_см")
    t_all = rep.get(d, "tau_allow", "Допускаемое напряжение среза кольца [τ]", "МПа")
    c_all = rep.get(d, "crush_allow", "Допускаемое напряжение смятия [σ_см]", "МПа")
    rep.check(f"τ_кольца = {fmt(tau)} ≤ [τ] = {fmt(t_all)} МПа", tau <= t_all)
    rep.check(f"σ_см = {fmt(sc)} ≤ [σ_см] = {fmt(c_all)} МПа", sc <= c_all)
    if "D_groove" in d:
        Dgv = rep.get(d, "D_groove", "Диаметр среза бурта (паза) корпуса", "мм")
        hg = rep.get(d, "h_groove", "Осевая высота бурта корпуса над пазом", "мм")
        tg_all = rep.get(d, "tau_allow_body", "Допускаемое напряжение среза материала корпуса", "МПа")
        tg = rep.step("Срез бурта корпуса", N_SOPR, "τ_б = k_н·F/(π·D_п·h_б)",
                      f"{fmt(kn)}·{fmt(F)}/(π·{fmt(Dgv)}·{fmt(hg)})", kn * F / (math.pi * Dgv * hg), "МПа", "τ_б")
        rep.check(f"τ_бурта = {fmt(tg)} ≤ {fmt(tg_all)} МПа", tg <= tg_all)
    rep.warn("Проверить усилие разжатия/сжатия кольца приводом, фиксацию кольца в рабочем положении и "
             "блокировку открытия под давлением.")
    return rep


HANDLERS = {"axial_load": axial_load, "bayonet": bayonet, "locking_ring": locking_ring}


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
