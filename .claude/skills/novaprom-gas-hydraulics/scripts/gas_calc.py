#!/usr/bin/env python3
"""Газодинамические расчёты для природного газа (инженерная оценка).

Запуск:
    python gas_calc.py input.json [--out report.md] [--json]

Давления: МПа (абсолютное — ключ p_abs, избыточное — ключ p_g); температуры: °C;
диаметры: мм; длины: м; расходы: м³/ч при стандартных условиях ГОСТ 2939-63
(20 °C; 101,325 кПа) — ключ Q_st.

{
  "gas": {"rho_st": {"value": 0.68, "source": "паспорт качества газа"},
          "composition": {"Methane": 0.95, "Ethane": 0.03, ...}},   # опционально
  "z_method": "gazprom",            # gazprom | papay | coolprop | value
  "cases": [ {"type": "properties", "p_abs": 5.5, "t": 10}, ... ]
}

Типы расчётов (cases[].type):
  properties     Z, плотность, рабочий расход при (p, t)
  velocity       скорость в трубе внутренним диаметром d
  select_dn      выбор диаметра по допустимой скорости из списка труб
  pressure_drop  потери давления на участке (Дарси–Вейсбах; изотермическое течение)
  jt_cooling     охлаждение газа при дросселировании (эффект Джоуля–Томсона)
  preheat        тепловая мощность подогрева перед редуцированием
  regulator_kv   требуемый Kv регулятора (упрощённо, VDI/VDE 2173)

Z рассчитывается основным методом (z_method) и, для перекрёстной проверки, остальными
доступными методами; при расхождении > 2 % выдаётся предупреждение.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _calcreport import CalcReport, emit, fmt, load_input  # noqa: E402

P_ST = 0.101325  # МПа, ГОСТ 2939-63
T_ST = 293.15    # К, ГОСТ 2939-63 (20 °C)
T_N = 273.15     # К, нормальные условия (0 °C)
RHO_AIR_ST = 1.2041  # кг/м³ сухого воздуха при 20 °C и 101,325 кПа

N_GOST2939 = "ГОСТ 2939-63 (стандартные условия: 20 °C, 101,325 кПа)"
N_GAZPROM = ("СТО Газпром 2-3.5-051-2006 / ОНТП 51-1-85 — упрощённая формула Z "
             "(инженерная оценка; для коммерческого учёта — ГОСТ 30319.2/30319.3-2015)")
N_PAPAY = "Корреляция Papay + псевдокритические параметры по Sutton (инженерная оценка)"
N_COOLPROP = "CoolProp (HEOS, GERG-2008 для смесей) — расчёт по полному составу"
N_DARCY = "Уравнение Дарси–Вейсбаха, λ по Колбруку–Уайту"


# --------------------------------------------------------------------------- Z
def z_gazprom(p: float, T: float, rho_st: float) -> float:
    ppk = 0.1773 * (26.831 - rho_st)
    tpk = 155.24 * (0.564 + rho_st)
    pr, tr = p / ppk, T / tpk
    tau = 1 - 1.68 * tr + 0.78 * tr ** 2 + 0.0107 * tr ** 3
    return 1 - 0.0241 * pr / tau


def z_papay(p: float, T: float, rho_st: float) -> float:
    g = rho_st / RHO_AIR_ST
    tpc = (169.2 + 349.5 * g - 74.0 * g * g) / 1.8           # °R -> K
    ppc = (756.8 - 131.0 * g - 3.6 * g * g) * 0.00689476     # psia -> МПа
    pr, tr = p / ppc, T / tpc
    return 1 - 3.52 * pr / 10 ** (0.9813 * tr) + 0.274 * pr ** 2 / 10 ** (0.8157 * tr)


def _coolprop_state(comp: dict):
    import CoolProp.CoolProp as CP  # noqa: F401
    from CoolProp.CoolProp import AbstractState
    names = list(comp)
    st = AbstractState("HEOS", "&".join(names))
    tot = sum(comp.values())
    st.set_mole_fractions([comp[n] / tot for n in names])
    return st


def z_coolprop(p: float, T: float, comp: dict) -> float:
    import CoolProp.CoolProp as CP
    st = _coolprop_state(comp)
    st.update(CP.PT_INPUTS, p * 1e6, T)
    return st.compressibility_factor()


def coolprop_available() -> bool:
    try:
        import CoolProp  # noqa: F401
        return True
    except ImportError:
        return False


class Gas:
    """Свойства газа с регистрацией источников в отчёте."""

    def __init__(self, rep: CalcReport, data: dict):
        self.rep = rep
        g = data.get("gas", {})
        self.comp = g.get("composition")
        self.method = data.get("z_method", "gazprom")
        if "rho_st" in g:
            self.rho_st = rep.get(g, "rho_st", "Плотность газа при стандартных условиях ρ_с", "кг/м³")
        elif self.comp and coolprop_available():
            import CoolProp.CoolProp as CP
            st = _coolprop_state(self.comp)
            st.update(CP.PT_INPUTS, P_ST * 1e6, T_ST)
            self.rho_st = rep.step("Плотность газа при стандартных условиях (по составу)", N_COOLPROP,
                                   "ρ_с = ρ(p_с, T_с, состав)", "CoolProp HEOS", st.rhomass(), "кг/м³", "ρ_с")
        else:
            raise SystemExit("Задайте gas.rho_st или gas.composition (при установленном CoolProp).")
        self.z_value = g.get("Z")
        rep.norm(N_GOST2939)

    def z(self, p: float, T: float, label: str = "", record: bool = True) -> float:
        methods = {"gazprom": lambda: z_gazprom(p, T, self.rho_st),
                   "papay": lambda: z_papay(p, T, self.rho_st)}
        if self.comp and coolprop_available():
            methods["coolprop"] = lambda: z_coolprop(p, T, self.comp)
        if self.method == "value":
            if self.z_value is None:
                raise SystemExit("z_method=value, но gas.Z не задан")
            zval = self.z_value["value"] if isinstance(self.z_value, dict) else self.z_value
            return zval
        if self.method not in methods:
            raise SystemExit(f"Метод Z '{self.method}' недоступен (coolprop требует gas.composition и пакет CoolProp)")
        if not record:
            return methods[self.method]()
        res = {k: f() for k, f in methods.items()}
        z = res[self.method]
        if record:
            norm = {"gazprom": N_GAZPROM, "papay": N_PAPAY, "coolprop": N_COOLPROP}[self.method]
            others = ", ".join(f"{k}: {fmt(v)}" for k, v in res.items())
            self.rep.step(f"Коэффициент сжимаемости {label}".strip(), norm,
                          "Z = 1 − 0,0241·p_пр/τ; τ = 1 − 1,68·T_пр + 0,78·T_пр² + 0,0107·T_пр³; "
                          "p_пк = 0,1773·(26,831 − ρ_с); T_пк = 155,24·(0,564 + ρ_с)"
                          if self.method == "gazprom" else f"метод {self.method}",
                          f"p = {fmt(p)} МПа, T = {fmt(T)} К, ρ_с = {fmt(self.rho_st)}; сравнение методов → {others}",
                          z, "", "Z")
            spread = (max(res.values()) - min(res.values())) / z
            if spread > 0.02:
                self.rep.warn(f"Расхождение методов расчёта Z {label} = {fmt(spread * 100)} % (> 2 %): "
                              "уточнить по ГОСТ 30319.2/30319.3-2015 или по полному составу газа.")
        return z

    @property
    def R_s(self) -> float:
        """Удельная газовая постоянная, Дж/(кг·К), из ρ_с с учётом Z_с."""
        zc = self.z(P_ST, T_ST, record=False)
        return P_ST * 1e6 / (self.rho_st * zc * T_ST)


def pressure_abs(rep: CalcReport, d: dict, key: str = "p", name: str = "Давление") -> float:
    if f"{key}_abs" in d:
        return rep.get(d, f"{key}_abs", f"{name} абсолютное", "МПа")
    if f"{key}_g" in d:
        pg = rep.get(d, f"{key}_g", f"{name} избыточное", "МПа")
        patm = rep.get(d, "p_atm", "Атмосферное давление", "МПа", default=P_ST)
        return pg + patm
    raise SystemExit(f"Задайте {key}_abs (абсолютное) или {key}_g (избыточное) давление, МПа")


def state(rep: CalcReport, gas: Gas, d: dict, pkey: str = "p", label: str = "") -> tuple[float, float, float, float]:
    """Возвращает (p_abs, T, Z, rho) и записывает шаги."""
    p = pressure_abs(rep, d, pkey, f"Давление {label}".strip())
    t = rep.get(d, "t" if pkey == "p" else f"t{pkey[-1]}", f"Температура газа {label}".strip(), "°C")
    T = t + 273.15
    z = gas.z(p, T, label)
    zc = gas.z(P_ST, T_ST, record=False)
    rho = rep.step(f"Плотность газа в рабочих условиях {label}".strip(), N_GOST2939,
                   "ρ = ρ_с·(p/p_с)·(T_с/T)·(Z_с/Z)",
                   f"{fmt(gas.rho_st)}·({fmt(p)}/{P_ST})·({T_ST}/{fmt(T)})·({fmt(zc)}/{fmt(z)})",
                   gas.rho_st * (p / P_ST) * (T_ST / T) * (zc / z), "кг/м³", "ρ")
    return p, T, z, rho


def q_work(rep: CalcReport, gas: Gas, Qst: float, p: float, T: float, z: float) -> float:
    zc = gas.z(P_ST, T_ST, record=False)
    return rep.step("Рабочий (фактический) объёмный расход", N_GOST2939,
                    "Q_р = Q_с·(p_с/p)·(T/T_с)·(Z/Z_с)",
                    f"{fmt(Qst)}·({P_ST}/{fmt(p)})·({fmt(T)}/{T_ST})·({fmt(z)}/{fmt(zc)})",
                    Qst * (P_ST / p) * (T / T_ST) * (z / zc), "м³/ч", "Q_р")


# --------------------------------------------------------------------------- cases
def c_properties(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Свойства газа в рабочих условиях — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    p, T, z, rho = state(rep, gas, d)
    if "Q_st" in d:
        Qst = rep.get(d, "Q_st", "Расход при стандартных условиях Q_с", "м³/ч")
        q_work(rep, gas, Qst, p, T, z)
        rep.step("Массовый расход", N_GOST2939, "G = Q_с·ρ_с/3600", f"{fmt(Qst)}·{fmt(gas.rho_st)}/3600",
                 Qst * gas.rho_st / 3600, "кг/с", "G")
    return rep


def _velocity(rep, gas, d, Qst, p, T, z, d_in, w_max=None):
    Qw = q_work(rep, gas, Qst, p, T, z)
    A = math.pi * (d_in / 1000) ** 2 / 4
    w = rep.step("Скорость газа", "уравнение неразрывности", "w = Q_р / (3600·π·d²/4)",
                 f"{fmt(Qw)} / (3600·π·{fmt(d_in / 1000)}²/4)", Qw / 3600 / A, "м/с", "w")
    if w_max is not None:
        rep.check(f"w = {fmt(w)} ≤ w_доп = {fmt(w_max)} м/с", w <= w_max)
    return w


def c_velocity(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Скорость газа в трубопроводе — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    Qst = rep.get(d, "Q_st", "Расход при стандартных условиях Q_с", "м³/ч")
    p, T, z, _ = state(rep, gas, d)
    d_in = rep.get(d, "d_in", "Внутренний диаметр трубы d", "мм")
    w_max = rep.get(d, "w_max", "Допустимая скорость газа w_доп (норматив/ОТТ заказчика)", "м/с", required=False)
    _velocity(rep, gas, d, Qst, p, T, z, d_in, w_max)
    return rep


def c_select_dn(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Выбор диаметра трубопровода по скорости — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    Qst = rep.get(d, "Q_st", "Расход при стандартных условиях Q_с", "м³/ч")
    p, T, z, _ = state(rep, gas, d)
    w_max = rep.get(d, "w_max", "Допустимая скорость газа w_доп (норматив/ОТТ заказчика)", "м/с")
    Qw = q_work(rep, gas, Qst, p, T, z)
    dmin = rep.step("Минимальный внутренний диаметр", "уравнение неразрывности",
                    "d_min = √(4·Q_р / (3600·π·w_доп))", f"√(4·{fmt(Qw)}/(3600·π·{fmt(w_max)}))",
                    math.sqrt(4 * Qw / (3600 * math.pi * w_max)) * 1000, "мм", "d_min")
    chosen = None
    for pipe in sorted(d.get("pipes", []), key=lambda x: x["D"] - 2 * x["s"]):
        di = pipe["D"] - 2 * pipe["s"]
        w = Qw / 3600 / (math.pi * (di / 1000) ** 2 / 4)
        ok = w <= w_max
        rep.step(f"Вариант {pipe.get('name', '')} {fmt(pipe['D'])}×{fmt(pipe['s'])} — "
                 f"{'подходит' if ok else 'скорость выше допустимой'}", "уравнение неразрывности",
                 "w = Q_р / (3600·π·d²/4), d = D − 2s", f"d = {fmt(di)} мм", w, "м/с", "w")
        if ok and chosen is None:
            chosen = pipe
    if d.get("pipes"):
        rep.check("Найден подходящий типоразмер из списка", chosen is not None,
                  f"принят {chosen.get('name', '')} {fmt(chosen['D'])}×{fmt(chosen['s'])}" if chosen else "увеличить DN")
    rep.assume(f"d_min = {fmt(dmin)} мм; толщину стенки выбранной трубы проверить на прочность (novaprom-piping).")
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


def c_pressure_drop(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Потери давления газа на участке — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    Qst = rep.get(d, "Q_st", "Расход при стандартных условиях Q_с", "м³/ч")
    p1, T, z, rho = state(rep, gas, d, label="на входе")
    d_in = rep.get(d, "d_in", "Внутренний диаметр d", "мм") / 1000
    L = rep.get(d, "L", "Длина участка L", "м")
    k = rep.get(d, "roughness", "Эквивалентная шероховатость Δ", "мм") / 1000
    mu = rep.get(d, "mu", "Динамическая вязкость газа μ", "Па·с")
    zeta = rep.get(d, "sum_zeta", "Сумма коэффициентов местных сопротивлений Σζ", "—", default=0.0)
    G = Qst * gas.rho_st / 3600
    A = math.pi * d_in ** 2 / 4
    w = G / (rho * A)
    Re = rep.step("Число Рейнольдса", N_DARCY, "Re = 4·G/(π·d·μ)", f"4·{fmt(G)}/(π·{fmt(d_in)}·{fmt(mu)})",
                  4 * G / (math.pi * d_in * mu), "", "Re")
    lam = rep.step("Коэффициент гидравлического трения", N_DARCY,
                   "1/√λ = −2·lg(Δ/(3,7·d) + 2,51/(Re·√λ))", f"Δ/d = {fmt(k / d_in)}, Re = {fmt(Re)}",
                   colebrook(Re, k / d_in), "", "λ")
    dp = rep.step("Потери давления (несжимаемое приближение, ρ на входе)", N_DARCY,
                  "Δp = (λ·L/d + Σζ)·ρ·w²/2", f"({fmt(lam)}·{fmt(L)}/{fmt(d_in)} + {fmt(zeta)})·{fmt(rho)}·{fmt(w)}²/2·10⁻⁶",
                  (lam * L / d_in + zeta) * rho * w * w / 2 / 1e6, "МПа", "Δp")
    if dp / p1 > 0.1 or d.get("isothermal"):
        Rs = gas.R_s
        flux = G / A
        p2 = max(p1 - dp, 0.3 * p1)
        feasible = True
        for _ in range(100):
            zm = gas.z((p1 + p2) / 2, T, record=False)
            rhs = flux ** 2 * zm * Rs * T * ((lam * L / d_in + zeta) + 2 * math.log(p1 / p2))
            if (p1 * 1e6) ** 2 - rhs <= (0.05 * p1 * 1e6) ** 2:
                feasible = False
                break
            p2_new = math.sqrt((p1 * 1e6) ** 2 - rhs) / 1e6
            if abs(p2_new - p2) < 1e-9:
                break
            p2 = 0.5 * (p2 + p2_new)
        if not feasible:
            rep.check("Пропуск заданного расхода при данных p1, d, L физически возможен", False,
                      "давление в конце участка стремится к нулю/критическому режиму — увеличить DN или p1")
            return rep
        rep.step("Давление в конце участка (изотермическое течение)", N_DARCY + "; изотермическое течение газа",
                 "p1² − p2² = (G/A)²·Z_ср·R·T·[λ·L/d + Σζ + 2·ln(p1/p2)]",
                 f"G/A = {fmt(flux)} кг/(м²·с), R = {fmt(Rs)} Дж/(кг·К)", p2, "МПа", "p2")
        dp = rep.step("Потери давления (изотермическое течение)", N_DARCY, "Δp = p1 − p2",
                      f"{fmt(p1)} − {fmt(p2)}", p1 - p2, "МПа", "Δp")
    if "dp_max" in d:
        dpm = rep.get(d, "dp_max", "Допустимые потери давления Δp_доп", "МПа")
        rep.check(f"Δp = {fmt(dp)} ≤ Δp_доп = {fmt(dpm)} МПа", dp <= dpm)
    rep.assume("Изменение высотных отметок и теплообмен с окружающей средой не учитываются.")
    return rep


def c_jt_cooling(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Охлаждение газа при редуцировании (эффект Джоуля–Томсона) — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    p1 = pressure_abs(rep, d, "p1", "Давление до редуцирования")
    p2 = pressure_abs(rep, d, "p2", "Давление после редуцирования")
    t1 = rep.get(d, "t1", "Температура газа до редуцирования", "°C")
    if "mu_jt" in d:
        mu = rep.get(d, "mu_jt", "Средний коэффициент Джоуля–Томсона μ_JT", "К/МПа")
        dt = rep.step("Снижение температуры", "ΔT = μ_JT·(p1 − p2) (средний коэффициент)",
                      "ΔT = μ_JT·(p1 − p2)", f"{fmt(mu)}·({fmt(p1)} − {fmt(p2)})", mu * (p1 - p2), "К", "ΔT")
    elif gas.comp and coolprop_available():
        import CoolProp.CoolProp as CP
        st = _coolprop_state(gas.comp)
        st.update(CP.PT_INPUTS, p1 * 1e6, t1 + 273.15)
        h = st.hmass()
        st.update(CP.HmassP_INPUTS, h, p2 * 1e6)
        dt = rep.step("Снижение температуры (изоэнтальпийное дросселирование)", N_COOLPROP,
                      "h(p1, T1) = h(p2, T2)", f"h = {fmt(h / 1000)} кДж/кг", t1 + 273.15 - st.T(), "К", "ΔT")
    else:
        raise SystemExit("Задайте mu_jt (К/МПа, с источником) или gas.composition при установленном CoolProp.")
    t2 = rep.step("Температура после редуцирования", "—", "t2 = t1 − ΔT", f"{fmt(t1)} − {fmt(dt)}", t1 - dt, "°C", "t2")
    if "t2_min" in d:
        tmin = rep.get(d, "t2_min", "Минимально допустимая температура после редуцирования", "°C")
        rep.check(f"t2 = {fmt(t2)} ≥ t2_мин = {fmt(tmin)} °C", t2 >= tmin, "иначе требуется подогрев (case: preheat)")
    rep.warn("Проверить условия гидратообразования и точку росы по воде/углеводородам для фактического "
             "состава газа; при необходимости — подогрев или ингибитор.")
    return rep


def c_preheat(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Мощность подогрева газа — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    Qst = rep.get(d, "Q_st", "Расход при стандартных условиях Q_с", "м³/ч")
    cp = rep.get(d, "cp", "Средняя изобарная теплоёмкость газа c_p", "кДж/(кг·К)")
    t_in = rep.get(d, "t_in", "Температура газа на входе в подогреватель", "°C")
    t_out = rep.get(d, "t_out", "Требуемая температура газа на выходе подогревателя", "°C")
    eta = rep.get(d, "eta", "КПД подогревателя η (для расчёта мощности источника тепла)", "—", default=1.0)
    G = Qst * gas.rho_st / 3600
    Qh = rep.step("Тепловая мощность, передаваемая газу", "тепловой баланс",
                  "Φ = G·c_p·(t_вых − t_вх)", f"{fmt(G)}·{fmt(cp)}·({fmt(t_out)} − {fmt(t_in)})",
                  G * cp * (t_out - t_in), "кВт", "Φ")
    rep.step("Мощность источника тепла с учётом КПД", "тепловой баланс", "Φ_ист = Φ/η",
             f"{fmt(Qh)}/{fmt(eta)}", Qh / eta, "кВт", "Φ_ист")
    rep.assume("c_p принята средней в интервале температур при рабочем давлении (уточнить по составу/CoolProp).")
    return rep


def c_regulator_kv(gas_data: dict, d: dict) -> CalcReport:
    rep = CalcReport(f"Требуемая пропускная способность регулятора Kv — {d.get('name', '')}")
    gas = Gas(rep, gas_data)
    Qst = rep.get(d, "Q_st", "Максимальный расход при стандартных условиях Q_с", "м³/ч")
    p1 = pressure_abs(rep, d, "p1", "Давление на входе (минимальное расчётное)")
    p2 = pressure_abs(rep, d, "p2", "Давление на выходе")
    t1 = rep.get(d, "t1", "Температура газа на входе", "°C")
    T1 = t1 + 273.15
    norm = ("VDI/VDE 2173 (упрощённые формулы Kv для газов); окончательный подбор — по методике и "
            "коэффициентам производителя регулятора (Kv/Cg/KG) или IEC 60534-2-1")
    QN = rep.step("Расход при нормальных условиях (0 °C)", N_GOST2939, "Q_N = Q_с·T_N/T_с",
                  f"{fmt(Qst)}·{T_N}/{T_ST}", Qst * T_N / T_ST, "м³/ч", "Q_N")
    rhoN = rep.step("Плотность при нормальных условиях", N_GOST2939, "ρ_N = ρ_с·T_с/T_N",
                    f"{fmt(gas.rho_st)}·{T_ST}/{T_N}", gas.rho_st * T_ST / T_N, "кг/м³", "ρ_N")
    P1, P2 = p1 * 10, p2 * 10
    dP = P1 - P2
    if P2 > P1 / 2:
        kv = rep.step("Kv (докритический перепад, p2 > p1/2)", norm,
                      "Kv = Q_N/514·√(ρ_N·T1/(Δp·p2))  [бар абс., К]",
                      f"{fmt(QN)}/514·√({fmt(rhoN)}·{fmt(T1)}/({fmt(dP)}·{fmt(P2)}))",
                      QN / 514 * math.sqrt(rhoN * T1 / (dP * P2)), "м³/ч", "Kv")
    else:
        kv = rep.step("Kv (сверхкритический перепад, p2 ≤ p1/2)", norm,
                      "Kv = Q_N/(257·p1)·√(ρ_N·T1)  [бар абс., К]",
                      f"{fmt(QN)}/(257·{fmt(P1)})·√({fmt(rhoN)}·{fmt(T1)})",
                      QN / (257 * P1) * math.sqrt(rhoN * T1), "м³/ч", "Kv")
    if "kvs" in d:
        kvs = rep.get(d, "kvs", "Kvs выбранного регулятора (паспорт производителя)", "м³/ч")
        margin = rep.get(d, "kv_margin", "Требуемый запас Kvs/Kv (по ОТТ/практике)", "—")
        rep.check(f"Kvs/Kv = {fmt(kvs / kv)} ≥ {fmt(margin)}", kvs / kv >= margin)
    rep.warn("Проверить скорость газа на выходе регулятора, уровень шума и необходимость подогрева.")
    return rep


HANDLERS = {
    "properties": c_properties,
    "velocity": c_velocity,
    "select_dn": c_select_dn,
    "pressure_drop": c_pressure_drop,
    "jt_cooling": c_jt_cooling,
    "preheat": c_preheat,
    "regulator_kv": c_regulator_kv,
}


def run(data: dict) -> list[CalcReport]:
    base = {"gas": data.get("gas", {}), "z_method": data.get("z_method", "gazprom")}
    out = []
    for case in data.get("cases", []):
        t = case.get("type")
        if t not in HANDLERS:
            raise SystemExit(f"Неизвестный тип расчёта '{t}'. Допустимо: {', '.join(HANDLERS)}")
        out.append(HANDLERS[t](base, case))
    return out


if __name__ == "__main__":
    data, opts = load_input()
    sys.exit(emit(run(data), opts))
