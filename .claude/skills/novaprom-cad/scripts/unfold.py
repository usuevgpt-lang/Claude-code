#!/usr/bin/env python3
"""Аналитические развёртки листовых деталей (по нейтральному слою).

Подкоманды:
  cone    усечённый прямой круговой конус (концентрический переход)
  mitre   цилиндр, срезанный плоскостью под углом β к нормальному сечению
  gore    сегмент (полный и половинный) секционного отвода «лобстер»
  saddle  врезка цилиндра в цилиндр (оси перпендикулярны, со смещением e)

Все размеры — мм, углы — градусы. Диаметры — НЕЙТРАЛЬНЫЕ (по середине толщины или по
k-фактору производства). Пересчёт наружного диаметра в нейтральный ключами --outer D --t s --k k
выполняется ТОЛЬКО в mitre (k — доля толщины от внутренней поверхности до нейтрального слоя; значение —
по технологии производства; 0,5 соответствует срединной поверхности). Для cone, gore, saddle эти ключи
отклоняются: нейтральные размеры задаются явно (D_нейтр = D_нар − 2·t + 2·k·t).

Вывод: таблица ключевых размеров и координат; --dxf файл.dxf — контур развёртки (нужен ezdxf).

Примеры:
  python unfold.py cone --D 1000 --d 500 --H 500 --dxf cone.dxf
  python unfold.py gore --r 159.5 --R 480 --angle 90 --n 3 --points 72 --dxf gore.dxf
  python unfold.py saddle --rb 54 --Rh 159 --e 0 --points 72

Эксцентрические переходы и переходы «квадрат–круг» — триангуляцией в CAD (SolidWorks lofted bends).
Результат проверять по эталонной детали в SolidWorks перед запуском в производство.
"""
from __future__ import annotations

import argparse
import math
import sys


NEUTRAL_HELP = {
    "cone": "--D и --d — нейтральные диаметры торцов",
    "gore": "--r — нейтральный радиус трубы",
    "saddle": "--rb — нейтральный радиус ответвления, --Rh — радиус магистрали по поверхности контакта",
}


def neutral(args, key: str) -> float:
    """Нейтральный диаметр из явного значения или из наружного диаметра, толщины и k (только mitre)."""
    val = getattr(args, key, None)
    given = [n for n in ("outer", "t", "k") if getattr(args, n, None) is not None]
    if val is not None and given:
        raise SystemExit(f"Задайте либо --{key} (нейтральный диаметр), либо --outer, --t, --k — не одновременно")
    if val is not None:
        return val
    if len(given) != 3:
        raise SystemExit(f"Задайте --{key} (нейтральный диаметр) или все три ключа --outer, --t, --k")
    if not 0 <= args.k <= 1:
        raise SystemExit("--k — доля толщины, требуется 0 ≤ k ≤ 1")
    if args.t <= 0 or args.outer <= 2 * args.t:
        raise SystemExit("Требуется t > 0 и наружный диаметр > 2·t")
    return args.outer - 2 * args.t + 2 * args.k * args.t


def reject_outer(args) -> None:
    """cone/gore/saddle работают только с нейтральными размерами — --outer/--t/--k не игнорируются молча."""
    given = [f"--{n}" for n in ("outer", "t", "k") if getattr(args, n, None) is not None]
    if given:
        raise SystemExit(
            f"Подкоманда {args.cmd}: {'ключи' if len(given) > 1 else 'ключ'} {', '.join(given)} "
            f"{'не поддерживаются' if len(given) > 1 else 'не поддерживается'} (пересчёт наружного размера "
            f"в нейтральный есть только в mitre). Задайте нейтральные размеры явно: {NEUTRAL_HELP[args.cmd]}. "
            "Пересчёт: D_нейтр = D_нар − 2·t + 2·k·t, k — по технологии производства.")


def save_dxf(path: str, polylines: list[list[tuple[float, float]]], arcs=(), lines=()) -> None:
    try:
        import ezdxf
    except ImportError:
        raise SystemExit("Для вывода DXF установите ezdxf: python -m pip install ezdxf==1.4.4")
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # мм
    msp = doc.modelspace()
    doc.layers.add("UNFOLD", color=1)
    for pl in polylines:
        msp.add_lwpolyline(pl, dxfattribs={"layer": "UNFOLD"})
    for c, r, a0, a1 in arcs:
        msp.add_arc(c, r, a0, a1, dxfattribs={"layer": "UNFOLD"})
    for p0, p1 in lines:
        msp.add_line(p0, p1, dxfattribs={"layer": "UNFOLD"})
    doc.saveas(path)
    print(f"DXF сохранён: {path}")


def table(rows: list[tuple[float, float]], head=("x, мм", "y, мм"), step: int = 1) -> str:
    out = [f"| {head[0]} | {head[1]} |", "|---|---|"]
    for i, (x, y) in enumerate(rows):
        if i % step == 0 or i == len(rows) - 1:
            out.append(f"| {x:.2f} | {y:.2f} |")
    return "\n".join(out)


def cmd_cone(a) -> None:
    D, d, H = a.D, a.d, a.H
    if D <= d:
        raise SystemExit("Требуется D > d")
    l = math.hypot(H, (D - d) / 2)
    R1 = D * l / (D - d)
    R2 = R1 - l
    theta = 180.0 * (D - d) / l
    chord = 2 * R1 * math.sin(math.radians(theta) / 2)
    alpha = math.degrees(math.atan((D - d) / 2 / H))
    print("# Развёртка усечённого конуса\n")
    print(f"- Нейтральные диаметры: D = {D:.2f}, d = {d:.2f} мм; высота H = {H:.2f} мм")
    print(f"- Половина угла при вершине α = {alpha:.3f}°")
    print(f"- Длина образующей l = √(H² + ((D − d)/2)²) = {l:.2f} мм")
    print(f"- Наружный радиус развёртки R1 = D·l/(D − d) = {R1:.2f} мм")
    print(f"- Внутренний радиус развёртки R2 = R1 − l = {R2:.2f} мм")
    print(f"- Угол сектора θ = 180°·(D − d)/l = {theta:.3f}°")
    print(f"- Хорда сектора по R1: c = 2·R1·sin(θ/2) = {chord:.2f} мм")
    print(f"- Контроль: длина дуги R1·θ = {R1 * math.radians(theta):.2f} мм = π·D = {math.pi * D:.2f} мм")
    if a.segments and a.segments > 1:
        print(f"- Деление на {a.segments} равных секторов по {theta / a.segments:.3f}° (если не хватает ширины листа)")
    if theta > 360:
        print("⚠️ θ > 360° — проверьте исходные данные")
    if a.dxf:
        start = 90 - theta / 2
        end = 90 + theta / 2
        p = lambda r, ang: (r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)))
        save_dxf(a.dxf, [], arcs=[((0, 0), R1, start, end), ((0, 0), R2, start, end)],
                 lines=[(p(R2, start), p(R1, start)), (p(R2, end), p(R1, end))])


def cmd_mitre(a) -> None:
    r = a.D / 2
    beta = math.radians(a.beta)
    n = a.points
    rows = []
    for i in range(n + 1):
        phi = 2 * math.pi * i / n
        rows.append((r * phi, a.L0 + r * math.tan(beta) * math.cos(phi)))
    print("# Развёртка цилиндра с косым срезом\n")
    if a.outer is not None:
        print(f"- Нейтральный диаметр из наружного: D = D_нар − 2·t + 2·k·t = {a.outer:g} − 2·{a.t:g} + 2·{a.k:g}·{a.t:g}"
              f" = {a.D:.2f} мм (k — по технологии производства)")
    print(f"- Нейтральный диаметр D = {a.D:.2f} мм, длина по оси L0 = {a.L0:.2f} мм, угол среза β = {a.beta:.3f}°")
    print(f"- Формула: L(φ) = L0 + r·tg β·cos φ, x = r·φ; ширина развёртки π·D = {math.pi * a.D:.2f} мм")
    print(f"- L max = {a.L0 + r * math.tan(beta):.2f} мм, L min = {a.L0 - r * math.tan(beta):.2f} мм\n")
    print(table(rows, ("x = r·φ, мм", "L(φ), мм"), max(1, n // 24)))
    if a.dxf:
        pts = [(0, 0)] + rows + [(math.pi * a.D, 0), (0, 0)]
        save_dxf(a.dxf, [pts])


def cmd_gore(a) -> None:
    r, R, PHI, n = a.r, a.R, a.angle, a.n
    m = n + 1
    beta = math.radians(PHI / (2 * m))
    N = a.points
    full, half = [], []
    for i in range(N + 1):
        phi = 2 * math.pi * i / N  # от интрадоса
        x = r * phi
        full.append((x, 2 * (R - r * math.cos(phi)) * math.tan(beta)))
        half.append((x, (R - r * math.cos(phi)) * math.tan(beta) + a.tangent))
    print("# Секционный отвод: развёртка сегментов\n")
    print(f"- Нейтральный радиус трубы r = {r:.2f} мм, радиус гиба по оси R = {R:.2f} мм, угол отвода Φ = {PHI:.2f}°")
    print(f"- Средних (полных) сегментов n = {n}, половинных — 2, стыков m = n + 1 = {m}")
    print(f"- Угол поворота на стык Φ/m = {PHI / m:.3f}°, полуугол реза β = Φ/(2m) = {math.degrees(beta):.3f}°")
    print(f"- Полный сегмент: L(φ) = 2·(R − r·cos φ)·tg β (φ от интрадоса), x = r·φ")
    print(f"  · по интрадосу 2(R − r)tg β = {2 * (R - r) * math.tan(beta):.2f} мм; по экстрадосу 2(R + r)tg β = {2 * (R + r) * math.tan(beta):.2f} мм")
    print(f"- Половинный сегмент: L(φ) = (R − r·cos φ)·tg β + прямой участок {a.tangent:.2f} мм")
    print(f"- Ширина развёртки 2π·r = {2 * math.pi * r:.2f} мм\n")
    print("## Полный сегмент\n" + table(full, ("x, мм", "L(φ), мм"), max(1, N // 24)))
    print("\n## Половинный сегмент\n" + table(half, ("x, мм", "L(φ), мм"), max(1, N // 24)))
    print("\nПрочность секционного отвода — отдельный расчёт (ASME B31.3 п. 304.2.3 / ГОСТ 32388 / ОТТ) — навык novaprom-piping.")
    if a.dxf:
        W = 2 * math.pi * r
        # полный сегмент: симметричный контур, кривые сверху и снизу от оси
        top = [(x, y / 2) for x, y in full]
        bot = [(x, -y / 2) for x, y in reversed(full)]
        save_dxf(a.dxf, [top + bot + [top[0]]])
        print(f"(контур полного сегмента; ширина {W:.2f} мм)")


def cmd_saddle(a) -> None:
    rb, Rh, e = a.rb, a.Rh, a.e
    if rb + abs(e) > Rh:
        raise SystemExit("Врезка выходит за образующую магистрали: требуется rb + |e| ≤ Rh")
    N = a.points
    rows, hole = [], []
    for i in range(N + 1):
        phi = 2 * math.pi * i / N
        s = e + rb * math.sin(phi)
        h = math.sqrt(Rh * Rh - s * s)
        rows.append((rb * phi, h))
        hole.append((Rh * math.asin(s / Rh), rb * math.cos(phi)))
    print("# Врезка цилиндра в цилиндр (оси перпендикулярны)\n")
    print(f"- Нейтральный радиус ответвления rb = {rb:.2f} мм, магистрали Rh = {Rh:.2f} мм, смещение осей e = {e:.2f} мм")
    print("- Высота линии реза над осью магистрали: h(φ) = √(Rh² − (e + rb·sin φ)²), x = rb·φ")
    print(f"- Перепад высот линии реза: {max(r[1] for r in rows) - min(r[1] for r in rows):.2f} мм\n")
    print("## Линия реза патрубка (откладывать от базовой линии)\n" + table(rows, ("x, мм", "h(φ), мм"), max(1, N // 24)))
    print("\n## Отверстие в магистрали (развёртка по поверхности магистрали)\n"
          + table(hole, ("x = Rh·asin(...), мм", "y = rb·cos φ, мм"), max(1, N // 24)))
    if a.dxf:
        save_dxf(a.dxf, [rows, hole])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--outer", type=float, help="наружный диаметр для расчёта нейтрального (только mitre)")
        p.add_argument("--t", type=float, help="толщина листа (только mitre, вместе с --outer и --k)")
        p.add_argument("--k", type=float,
                       help="положение нейтрального слоя, доля толщины от внутренней поверхности (только mitre)")
        p.add_argument("--dxf", help="сохранить контур в DXF")
        p.add_argument("--points", type=int, default=72, help="число точек по окружности")

    p = sub.add_parser("cone"); common(p)
    p.add_argument("--D", type=float, required=True, help="нейтральный диаметр большего торца")
    p.add_argument("--d", type=float, required=True, help="нейтральный диаметр меньшего торца")
    p.add_argument("--H", type=float, required=True, help="высота конуса по оси")
    p.add_argument("--segments", type=int, default=1)
    p = sub.add_parser("mitre"); common(p)
    p.add_argument("--D", type=float, help="нейтральный диаметр трубы")
    p.add_argument("--L0", type=float, required=True, help="длина по оси до плоскости среза")
    p.add_argument("--beta", type=float, required=True, help="угол среза к нормальному сечению, °")
    p = sub.add_parser("gore"); common(p)
    p.add_argument("--r", type=float, required=True, help="нейтральный радиус трубы")
    p.add_argument("--R", type=float, required=True, help="радиус гиба по оси")
    p.add_argument("--angle", type=float, required=True, help="угол отвода Φ, °")
    p.add_argument("--n", type=int, required=True, help="число полных (средних) сегментов")
    p.add_argument("--tangent", type=float, default=0.0, help="прямой участок у половинного сегмента, мм")
    p = sub.add_parser("saddle"); common(p)
    p.add_argument("--rb", type=float, required=True, help="нейтральный радиус ответвления")
    p.add_argument("--Rh", type=float, required=True, help="радиус магистрали (по поверхности контакта)")
    p.add_argument("--e", type=float, default=0.0, help="смещение осей")
    a = ap.parse_args(argv)
    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    if a.cmd == "mitre":
        a.D = neutral(a, "D")
    else:
        reject_outer(a)
    {"cone": cmd_cone, "mitre": cmd_mitre, "gore": cmd_gore, "saddle": cmd_saddle}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
