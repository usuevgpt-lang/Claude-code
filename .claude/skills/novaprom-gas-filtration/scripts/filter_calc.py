#!/usr/bin/env python3
"""Фильтры, фильтры-сепараторы, сепарационные элементы — предварительный подбор.

Запуск:
    python filter_calc.py input.json [--out report.md] [--json]

Рабочие параметры газа (Q_р, ρ_г, μ) берутся из расчёта novaprom-gas-hydraulics
(gas_calc.py, case "properties") и передаются сюда с указанием источника.

Типы расчётов (cases[].type):
  souders_brown     допустимая скорость и диаметр сепарационной секции (каплеуловитель)
  elements_count    количество фильтрующих/коалесцирующих элементов
  element_dp        пересчёт перепада давления элемента на рабочие условия
  nozzle_check      скорость и импульс ρw² в патрубках
  cyclone_lapple    оценка d50 и фракционной эффективности циклона (метод Lapple)

Коэффициенты (K Саудерса–Брауна, допустимые скорости, ρw², пропускная способность элемента)
принимаются по данным производителя внутренних устройств/элементов, ОТТ заказчика или
признанным методикам (GPSA, API 12J) — с указанием источника во входных данных.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import CalcReport, emit, fmt, load_input  # noqa: E402

N_SB = "Уравнение Саудерса–Брауна (GPSA Engineering Data Book, разд. 7; API 12J) — K по данным производителя"
N_LAPPLE = "Метод Lapple (1951) для циклонов стандартных пропорций — оценочный"


def souders_brown(d: dict) -> CalcReport:
    rep = CalcReport(f"Сепарационная секция: допустимая скорость газа — {d.get('name', '')}")
    Qw = rep.get(d, "Q_w", "Рабочий расход газа Q_р", "м³/ч")
    rg = rep.get(d, "rho_g", "Плотность газа в рабочих условиях ρ_г", "кг/м³")
    rl = rep.get(d, "rho_l", "Плотность жидкой фазы ρ_ж", "кг/м³")
    K = rep.get(d, "K", "Коэффициент Саудерса–Брауна K (тип каплеуловителя, производитель)", "м/с")
    kd = rep.get(d, "k_derate", "Понижающий коэффициент к K (давление, пенообразование, запас)", "—", default=1.0)
    vmax = rep.step("Максимально допустимая скорость газа в сечении каплеуловителя", N_SB,
                    "V_max = k·K·√((ρ_ж − ρ_г)/ρ_г)", f"{fmt(kd)}·{fmt(K)}·√(({fmt(rl)} − {fmt(rg)})/{fmt(rg)})",
                    kd * K * math.sqrt((rl - rg) / rg), "м/с", "V_max")
    A = rep.step("Требуемая площадь проходного сечения", "уравнение неразрывности", "A = Q_р/(3600·V_max)",
                 f"{fmt(Qw)}/(3600·{fmt(vmax)})", Qw / 3600 / vmax, "м²", "A")
    Dmin = rep.step("Минимальный диаметр (вертикальный аппарат, круглое сечение)", "геометрия",
                    "D_min = √(4·A/π)", f"√(4·{fmt(A)}/π)", math.sqrt(4 * A / math.pi) * 1000, "мм", "D_min")
    if "D" in d:
        D = rep.get(d, "D", "Принятый внутренний диаметр аппарата / сечения каплеуловителя", "мм")
        v = Qw / 3600 / (math.pi * (D / 1000) ** 2 / 4)
        rep.step("Фактическая скорость в принятом сечении", "уравнение неразрывности",
                 "V = Q_р/(3600·π·D²/4)", f"{fmt(Qw)}/(3600·π·{fmt(D / 1000)}²/4)", v, "м/с", "V")
        rep.check(f"D = {fmt(D)} ≥ D_min = {fmt(Dmin)} мм (V = {fmt(v)} ≤ V_max = {fmt(vmax)} м/с)", D >= Dmin)
        if "turndown_min" in d:
            vmin_frac = rep.get(d, "turndown_min", "Минимальная доля V/V_max для эффективной работы", "—")
            rep.check(f"V/V_max = {fmt(v / vmax)} ≥ {fmt(vmin_frac)} (эффективность при малых расходах)",
                      v / vmax >= vmin_frac, "для сетчатых/лопастных каплеуловителей — по данным производителя")
    rep.assume("Для горизонтальных аппаратов и комбинированных внутренних устройств методика иная "
               "(площадь над уровнем жидкости, время осаждения капель) — использовать отдельный расчёт.")
    return rep


def elements_count(d: dict) -> CalcReport:
    rep = CalcReport(f"Количество фильтрующих элементов — {d.get('name', '')}")
    Qw = rep.get(d, "Q_w", "Рабочий расход газа Q_р (максимальный)", "м³/ч")
    method = d.get("method", "flow_per_element")
    if method == "flow_per_element":
        q = rep.get(d, "q_el", "Допустимый рабочий расход через один элемент q_эл (данные производителя)", "м³/ч")
        N = rep.step("Расчётное количество элементов", "данные производителя элемента",
                     "N = Q_р / q_эл", f"{fmt(Qw)}/{fmt(q)}", Qw / q, "шт", "N")
    elif method == "face_velocity":
        del_ = rep.get(d, "d_el", "Наружный диаметр элемента d_эл", "мм") / 1000
        Lel = rep.get(d, "L_el", "Рабочая длина элемента L_эл", "мм") / 1000
        vf = rep.get(d, "v_face", "Допустимая скорость фильтрации на поверхности элемента", "м/с")
        Ael = rep.step("Площадь наружной поверхности элемента", "геометрия", "A_эл = π·d_эл·L_эл",
                       f"π·{fmt(del_)}·{fmt(Lel)}", math.pi * del_ * Lel, "м²", "A_эл")
        N = rep.step("Расчётное количество элементов", "по допустимой скорости фильтрации",
                     "N = Q_р/(3600·v_ф·A_эл)", f"{fmt(Qw)}/(3600·{fmt(vf)}·{fmt(Ael)})",
                     Qw / 3600 / (vf * Ael), "шт", "N")
    else:
        raise SystemExit("method: flow_per_element | face_velocity")
    kz = rep.get(d, "reserve", "Коэффициент запаса по количеству элементов", "—", default=1.0)
    Nreq = math.ceil(N * kz - 1e-9)
    rep.step("Принимаемое количество (с запасом, округление вверх)", "—", "N_прин = ⌈N·k_зап⌉",
             f"⌈{fmt(N)}·{fmt(kz)}⌉", Nreq, "шт", "N_прин")
    if "N_actual" in d:
        Na = rep.get(d, "N_actual", "Количество элементов в конструкции", "шт")
        rep.check(f"N = {Na} ≥ {Nreq} шт", Na >= Nreq)
    return rep


def element_dp(d: dict) -> CalcReport:
    rep = CalcReport(f"Перепад давления на элементах в рабочих условиях — {d.get('name', '')}")
    dp_ref = rep.get(d, "dp_ref", "Перепад давления чистого элемента при опорных условиях (каталог)", "кПа")
    q_ref = rep.get(d, "q_ref", "Расход через элемент при опорных условиях (рабочий)", "м³/ч")
    q = rep.get(d, "q", "Расход через элемент в рабочих условиях (рабочий)", "м³/ч")
    regime = d.get("regime", "turbulent")
    if regime == "turbulent":
        rr = rep.get(d, "rho_ref", "Плотность газа при опорных условиях", "кг/м³")
        r = rep.get(d, "rho", "Плотность газа в рабочих условиях", "кг/м³")
        dp = rep.step("Перепад чистого элемента (квадратичный закон)", "ΔP ∝ ρ·w² (инерционный режим)",
                      "ΔP = ΔP_оп·(ρ/ρ_оп)·(q/q_оп)²", f"{fmt(dp_ref)}·({fmt(r)}/{fmt(rr)})·({fmt(q)}/{fmt(q_ref)})²",
                      dp_ref * (r / rr) * (q / q_ref) ** 2, "кПа", "ΔP")
    else:
        mr = rep.get(d, "mu_ref", "Вязкость газа при опорных условиях", "Па·с")
        m = rep.get(d, "mu", "Вязкость газа в рабочих условиях", "Па·с")
        dp = rep.step("Перепад чистого элемента (линейный закон, фильтрация через среду)", "закон Дарси для пористой среды",
                      "ΔP = ΔP_оп·(μ/μ_оп)·(q/q_оп)", f"{fmt(dp_ref)}·({fmt(m)}/{fmt(mr)})·({fmt(q)}/{fmt(q_ref)})",
                      dp_ref * (m / mr) * (q / q_ref), "кПа", "ΔP")
    if "dp_housing" in d:
        dh = rep.get(d, "dp_housing", "Потери давления в корпусе и патрубках", "кПа")
        dp = rep.step("Суммарный перепад чистого фильтра", "—", "ΔP_Σ = ΔP_эл + ΔP_корп",
                      f"{fmt(dp)} + {fmt(dh)}", dp + dh, "кПа", "ΔP_Σ")
    if "dp_max_clean" in d:
        dm = rep.get(d, "dp_max_clean", "Допустимый перепад чистого фильтра (ОЛ/ОТТ)", "кПа")
        rep.check(f"ΔP = {fmt(dp)} ≤ {fmt(dm)} кПа", dp <= dm)
    if "dp_change" in d:
        dc = rep.get(d, "dp_change", "Перепад замены элементов (загрязнённый фильтр)", "кПа")
        rep.assume(f"Замена элементов при ΔP = {fmt(dc)} кПа; корпус и опорные решётки элементов "
                   "проверить на перепад разрушения (collapse ΔP) элемента по каталогу.")
    return rep


def nozzle_check(d: dict) -> CalcReport:
    rep = CalcReport(f"Патрубки аппарата: скорость и импульс потока — {d.get('name', '')}")
    Qw = rep.get(d, "Q_w", "Рабочий расход газа Q_р", "м³/ч")
    rho = rep.get(d, "rho", "Плотность потока ρ (смесь)", "кг/м³")
    di = rep.get(d, "d_in", "Внутренний диаметр патрубка", "мм") / 1000
    w = rep.step("Скорость в патрубке", "уравнение неразрывности", "w = Q_р/(3600·π·d²/4)",
                 f"{fmt(Qw)}/(3600·π·{fmt(di)}²/4)", Qw / 3600 / (math.pi * di * di / 4), "м/с", "w")
    mom = rep.step("Импульс потока", "критерий для входных устройств сепараторов", "ρw²",
                   f"{fmt(rho)}·{fmt(w)}²", rho * w * w, "Па", "ρw²")
    if "w_max" in d:
        wm = rep.get(d, "w_max", "Допустимая скорость в патрубке", "м/с")
        rep.check(f"w = {fmt(w)} ≤ {fmt(wm)} м/с", w <= wm)
    if "mom_max" in d:
        mm = rep.get(d, "mom_max", "Допустимый ρw² для принятого входного устройства", "Па")
        rep.check(f"ρw² = {fmt(mom)} ≤ {fmt(mm)} Па", mom <= mm)
    return rep


def cyclone_lapple(d: dict) -> CalcReport:
    rep = CalcReport(f"Циклон: оценка эффективности по Lapple — {d.get('name', '')}")
    mu = rep.get(d, "mu", "Динамическая вязкость газа μ", "Па·с")
    W = rep.get(d, "W", "Ширина входного патрубка W", "мм") / 1000
    Ne = rep.get(d, "Ne", "Эффективное число оборотов газа N_e", "—")
    Vi = rep.get(d, "Vi", "Скорость во входном патрубке V_i", "м/с")
    rp = rep.get(d, "rho_p", "Плотность частиц/капель ρ_ч", "кг/м³")
    rg = rep.get(d, "rho_g", "Плотность газа ρ_г", "кг/м³")
    d50 = rep.step("Диаметр частиц, улавливаемых на 50 %", N_LAPPLE,
                   "d50 = √(9·μ·W / (2π·N_e·V_i·(ρ_ч − ρ_г)))",
                   f"√(9·{fmt(mu)}·{fmt(W)}/(2π·{fmt(Ne)}·{fmt(Vi)}·({fmt(rp)} − {fmt(rg)})))",
                   math.sqrt(9 * mu * W / (2 * math.pi * Ne * Vi * (rp - rg))) * 1e6, "мкм", "d50")
    for dp in d.get("sizes_um", []):
        eta = 1 / (1 + (d50 / dp) ** 2)
        rep.step(f"Фракционная эффективность для d = {fmt(dp)} мкм", N_LAPPLE, "η = 1/(1 + (d50/d)²)",
                 f"1/(1 + ({fmt(d50)}/{fmt(dp)})²)", eta * 100, "%", "η")
    rep.warn("Метод Lapple — грубая оценка для циклонов стандартных пропорций при атмосферных условиях. "
             "Для газовых мультициклонов высокого давления использовать данные производителя элементов "
             "или испытаний; эффективность подтверждается ПМИ.")
    return rep


HANDLERS = {
    "souders_brown": souders_brown,
    "elements_count": elements_count,
    "element_dp": element_dp,
    "nozzle_check": nozzle_check,
    "cyclone_lapple": cyclone_lapple,
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
