#!/usr/bin/env python3
"""Анализ DXF-чертежа/развёртки: состав, основная надпись, размеры, контуры, длина реза.

Запуск:
    python dxf_inspect.py drawing.dxf [--json out.json] [--render preview.png] [--texts 50]
                          [--tol 0.01] [--layers CUT,0]

Контуры: замкнутые сущности (CIRCLE, замкнутые LWPOLYLINE/POLYLINE/SPLINE, полный ELLIPSE) плюс цепочки,
собранные из незамкнутых LINE/ARC/LWPOLYLINE/POLYLINE/SPLINE/дуг ELLIPSE по совпадению концов в пределах
--tol мм (типичная развёртка SolidWorks — отрезки и дуги). Длина реза — сумма длин всей линейной геометрии
пространства модели (рамка, линии гиба, осевые тоже попадают); --layers ограничивает слои для длины реза
и контуров.

Требуется: ezdxf (python -m pip install ezdxf==1.4.4); для --render также matplotlib.
Файл открывается в режиме восстановления (ezdxf.recover) — исходный файл не изменяется.
DWG сначала конвертировать в DXF (ODA File Converter) — см. SKILL.md.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict

try:
    import ezdxf
    from ezdxf import bbox, recover
    from ezdxf.path import make_path
except ImportError:
    raise SystemExit("Установите ezdxf: python -m pip install ezdxf==1.4.4")

UNITS = {0: "не задано", 1: "дюймы", 2: "футы", 4: "мм", 5: "см", 6: "м"}
FLATTEN = 0.05  # мм, точность аппроксимации кривых
CHAIN_TOL = 0.01  # мм, допуск совпадения концов при сборке контуров из отрезков/дуг
CURVES = ("LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE")


def poly_area(pts) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def path_points(e):
    try:
        p = make_path(e)
        return [(v.x, v.y) for v in p.flattening(FLATTEN)]
    except Exception:  # неподдерживаемые сущности
        return []


def length_of(e) -> float:
    t = e.dxftype()
    if t == "LINE":
        return e.dxf.start.distance(e.dxf.end)
    if t == "CIRCLE":
        return 2 * math.pi * e.dxf.radius
    if t == "ARC":
        span = (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360
        return math.radians(span) * e.dxf.radius
    if t in ("LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"):
        pts = path_points(e)
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    return 0.0


def is_curve(e) -> bool:
    """Линейная геометрия, которая режется (POLYLINE — только 2D/3D-полилиния, не сеть/полигранник)."""
    t = e.dxftype()
    if t == "POLYLINE":
        return bool(getattr(e, "is_2d_polyline", False) or getattr(e, "is_3d_polyline", False))
    return t in CURVES


def is_closed(e) -> bool:
    """Замкнутость по флагу сущности. У старой POLYLINE флаг — is_closed, у LWPOLYLINE/SPLINE — closed."""
    t = e.dxftype()
    if t == "CIRCLE":
        return True
    if t == "POLYLINE":
        return bool(getattr(e, "is_closed", False))
    if t in ("LWPOLYLINE", "SPLINE"):
        return bool(getattr(e, "closed", False))
    if t == "ELLIPSE":
        span = (e.dxf.get("end_param", 2 * math.pi) - e.dxf.get("start_param", 0.0)) % (2 * math.pi)
        return span < 1e-6 or abs(span - 2 * math.pi) < 1e-6
    return False


def bbox_of(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_inside(inner, outer, tol: float) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and
            inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def chain_segments(segs: list[dict], tol: float) -> tuple[list[dict], int]:
    """Жадная сборка незамкнутых кривых в цепочки по совпадению концов (в пределах tol).

    segs: [{"pts": [(x, y), ...], "len": L, "layer": ...}]. Сегменты при необходимости разворачиваются.
    Возвращает (цепочки, число узлов, где сходится больше двух концов — сборка там неоднозначна).
    """
    cell = max(tol, 1e-9)
    grid: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)

    def key(p):
        return math.floor(p[0] / cell), math.floor(p[1] / cell)

    def end_pt(i, end):
        return segs[i]["pts"][0] if end == 0 else segs[i]["pts"][-1]

    for i, s in enumerate(segs):
        grid[key(s["pts"][0])].append((i, 0))
        grid[key(s["pts"][-1])].append((i, 1))

    def near(p, used=None):
        cx, cy = key(p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i, end in grid.get((cx + dx, cy + dy), ()):
                    if used is not None and used[i]:
                        continue
                    d = math.dist(p, end_pt(i, end))
                    if d <= tol:
                        yield d, i, end

    # узлы ветвления (≥ 3 концов в одной точке)
    seen, branches = set(), 0
    for i in range(len(segs)):
        for end in (0, 1):
            if (i, end) in seen:
                continue
            cluster = [(j, e2) for _, j, e2 in near(end_pt(i, end))]
            seen.update(cluster)
            if len(cluster) >= 3:
                branches += 1

    used = [False] * len(segs)

    def take(p):
        best = min(near(p, used), default=None)
        if best is None:
            return None
        used[best[1]] = True
        return best[1], best[2]

    chains = []
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        pts, members, length = list(segs[i]["pts"]), [i], segs[i]["len"]

        def closed_now():
            return len(pts) > 2 and math.dist(pts[0], pts[-1]) <= tol

        while not closed_now():  # наращивание вперёд
            nxt = take(pts[-1])
            if nxt is None:
                break
            j, end = nxt
            p = segs[j]["pts"] if end == 0 else segs[j]["pts"][::-1]
            pts += p[1:]
            members.append(j)
            length += segs[j]["len"]
        while not closed_now():  # наращивание назад
            prv = take(pts[0])
            if prv is None:
                break
            j, end = prv
            p = segs[j]["pts"] if end == 1 else segs[j]["pts"][::-1]
            pts = p[:-1] + pts
            members.insert(0, j)
            length += segs[j]["len"]
        chains.append({"pts": pts, "len": length, "members": members, "closed": closed_now(),
                       "layers": sorted({segs[m]["layer"] for m in members})})
    return chains, branches


def inspect(path: str, max_texts: int, tol: float = CHAIN_TOL, layers: list[str] | None = None) -> tuple[dict, object]:
    doc, auditor = recover.readfile(path)
    msp = doc.modelspace()
    ents = list(msp)
    by_type = Counter(e.dxftype() for e in ents)
    by_layer = Counter(e.dxf.layer for e in ents)
    ext = bbox.extents(msp)
    res: dict = {
        "file": path,
        "dxf_version": doc.dxfversion,
        "units": UNITS.get(doc.header.get("$INSUNITS", 0), str(doc.header.get("$INSUNITS"))),
        "audit_errors": len(auditor.errors),
        "audit_fixes": len(auditor.fixes),
        "entities_by_type": dict(by_type.most_common()),
        "entities_by_layer": dict(by_layer.most_common()),
        "layers": [l.dxf.name for l in doc.layers],
        "blocks": [b.name for b in doc.blocks if not b.name.startswith("*")],
        "extents": None,
    }
    if ext.has_data:
        res["extents"] = {"min": [round(ext.extmin.x, 3), round(ext.extmin.y, 3)],
                          "max": [round(ext.extmax.x, 3), round(ext.extmax.y, 3)],
                          "size": [round(ext.size.x, 3), round(ext.size.y, 3)]}
    # атрибуты блоков (основная надпись, штампы)
    attrs = []
    for ins in msp.query("INSERT"):
        tags = {a.dxf.tag: a.dxf.text for a in ins.attribs}
        if tags:
            attrs.append({"block": ins.dxf.name, "attribs": tags})
    res["block_attributes"] = attrs
    texts = []
    for e in msp.query("TEXT MTEXT"):
        txt = e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text
        if txt and txt.strip():
            p = e.dxf.insert
            texts.append({"text": txt.strip()[:200], "x": round(p.x, 2), "y": round(p.y, 2), "layer": e.dxf.layer})
    res["texts_total"] = len(texts)
    res["texts"] = texts[:max_texts]
    dims = []
    for d in msp.query("DIMENSION"):
        try:
            m = d.get_measurement()
            m = round(m, 3) if isinstance(m, float) else str(m)
        except Exception:
            m = None
        dims.append({"measurement": m, "text_override": d.dxf.get("text", ""), "layer": d.dxf.layer})
    res["dimensions"] = dims

    # ---- замкнутые контуры и длина реза --------------------------------------------------
    warnings: list[str] = []
    wanted = {x.strip().lower() for x in layers if x.strip()} if layers else None
    geo = [e for e in ents if is_curve(e) and (wanted is None or e.dxf.layer.lower() in wanted)]
    res["layers_filter"] = sorted(wanted) if wanted else None
    res["chain_tol_mm"] = tol
    if wanted is not None and not geo:
        warnings.append(f"На слоях {', '.join(layers)} нет линейной геометрии. Слои файла: {', '.join(res['layers'])}.")
    contours, cut, segs = [], 0.0, []
    for e in geo:
        t = e.dxftype()
        L = length_of(e)
        cut += L
        if is_closed(e):
            if t == "CIRCLE":
                c, r = e.dxf.center, e.dxf.radius
                area, box = math.pi * r ** 2, (c.x - r, c.y - r, c.x + r, c.y + r)
            else:
                pts = path_points(e)
                area = poly_area(pts) if len(pts) > 2 else 0.0
                box = bbox_of(pts) if pts else (0.0, 0.0, 0.0, 0.0)
                if t == "ELLIPSE":  # точная площадь полного эллипса π·a·b
                    a_ = e.dxf.major_axis.magnitude
                    area = math.pi * a_ * a_ * e.dxf.ratio
            contours.append({"type": t, "layer": e.dxf.layer, "area_mm2": round(area, 2),
                             "perimeter_mm": round(L, 2), "_bbox": box})
        else:
            pts = path_points(e)
            if len(pts) >= 2 and L > tol:
                segs.append({"pts": pts, "len": L, "layer": e.dxf.layer})
    chains, branches = chain_segments(segs, tol)
    open_chains, degenerate = [], 0
    for ch in chains:
        if not ch["closed"]:
            open_chains.append(ch)
            continue
        area = poly_area(ch["pts"])
        if area <= tol * ch["len"]:  # «туда-обратно» по дублирующимся линиям
            degenerate += 1
            continue
        contours.append({"type": f"CHAIN({len(ch['members'])})", "layer": ",".join(ch["layers"]),
                         "area_mm2": round(area, 2), "perimeter_mm": round(ch["len"], 2),
                         "_bbox": bbox_of(ch["pts"])})
    contours.sort(key=lambda c: -c["area_mm2"])
    res["cut_length_total_mm"] = round(cut, 1)
    if wanted:
        res["cut_length_note"] = (f"сумма длин линейной геометрии слоёв: {', '.join(sorted(wanted))} "
                                  "(геометрия внутри блоков INSERT не учитывается)")
    else:
        res["cut_length_note"] = ("сумма длин ВСЕЙ геометрии пространства модели, включая рамку, штамп, линии гиба "
                                  "и осевые; для длины реза детали ограничьте слои ключом --layers "
                                  "(геометрия внутри блоков INSERT не учитывается)")
    open_len = sum(ch["len"] for ch in open_chains)
    res["open_chains"] = {"count": len(open_chains), "length_mm": round(open_len, 1)}
    if open_chains:
        warnings.append(f"Незамкнутые контуры: {len(open_chains)} шт., суммарная длина {open_len:.1f} мм "
                        f"(концы не сходятся в пределах --tol {tol:g} мм) — линии гиба/осевые/рамка или разрывы контура.")
    if degenerate:
        warnings.append(f"Вырожденные замкнутые цепочки нулевой площади: {degenerate} (вероятно, дублирующиеся линии).")
    if branches:
        warnings.append(f"Узлов, где сходится больше двух концов: {branches} — сборка контуров неоднозначна, "
                        "проверьте предпросмотр (--render).")
    if contours:
        outer = contours[0]
        holes = [c for c in contours[1:] if bbox_inside(c["_bbox"], outer["_bbox"], tol)]
        outside = len(contours) - 1 - len(holes)
        hole_area = sum(c["area_mm2"] for c in holes)
        note = ("оценка: наибольший замкнутый контур считается наружным, замкнутые контуры внутри его габарита — "
                "отверстиями")
        reliable = True
        if open_chains:
            ob = bbox_of([p for ch in open_chains for p in ch["pts"]])
            ob_area = (ob[2] - ob[0]) * (ob[3] - ob[1])
            if outer["area_mm2"] < ob_area or not bbox_inside(ob, outer["_bbox"], tol):
                reliable = False
                warnings.append(f"Незамкнутая геометрия (габарит {ob[2] - ob[0]:.1f} × {ob[3] - ob[1]:.1f} мм) выходит "
                                "за наибольший замкнутый контур — наружный контур, вероятно, разорван или в файле "
                                "есть рамка. Проверьте --tol и фильтр слоёв --layers.")
                note = ("ОЦЕНКА НЕДОСТОВЕРНА: незамкнутая геометрия выходит за наибольший замкнутый контур; " + note)
        if outside:
            warnings.append(f"Замкнутых контуров вне габарита наружного: {outside} — не учтены как отверстия "
                            "(несколько деталей в файле?).")
        res["blank_estimate"] = {"outer_area_mm2": outer["area_mm2"], "holes_area_mm2": round(hole_area, 2),
                                 "net_area_mm2": round(outer["area_mm2"] - hole_area, 2), "pierces": 1 + len(holes),
                                 "reliable": reliable, "note": note}
    elif open_chains:
        warnings.append("Замкнутых контуров не найдено — площадь заготовки не оценивается.")
    for c in contours:
        c.pop("_bbox", None)
    res["closed_contours"] = contours
    res["warnings"] = warnings
    return res, doc


def to_md(r: dict) -> str:
    o = [f"# Анализ DXF: {r['file']}", "",
         f"- Версия DXF: {r['dxf_version']}; единицы: {r['units']}; ошибки аудита: {r['audit_errors']} (исправлено {r['audit_fixes']})"]
    if r["extents"]:
        o.append(f"- Габарит: {r['extents']['size'][0]} × {r['extents']['size'][1]}")
    o.append(f"- Сущности: {', '.join(f'{k} {v}' for k, v in r['entities_by_type'].items())}")
    o.append(f"- Слои ({len(r['layers'])}): {', '.join(f'{k} ({v})' for k, v in r['entities_by_layer'].items())}")
    o.append(f"- Блоки: {', '.join(r['blocks']) or '—'}")
    o.append(f"- Суммарная длина контуров (оценка длины реза): {r['cut_length_total_mm']} мм — {r['cut_length_note']}")
    oc = r["open_chains"]
    o.append(f"- Контуры: замкнутых {len(r['closed_contours'])}, незамкнутых цепочек {oc['count']} "
             f"({oc['length_mm']} мм); допуск стыковки концов {r['chain_tol_mm']:g} мм")
    if r.get("blank_estimate"):
        b = r["blank_estimate"]
        o.append(f"- Заготовка (оценка): наружный контур {b['outer_area_mm2']} мм², отверстия {b['holes_area_mm2']} мм², "
                 f"нетто {b['net_area_mm2']} мм², врезок {b['pierces']} — {b['note']}")
    if r["warnings"]:
        o += ["", "## Предупреждения"] + [f"- ⚠️ {w}" for w in r["warnings"]]
    if r["block_attributes"]:
        o += ["", "## Атрибуты блоков (штамп/основная надпись)"]
        for a in r["block_attributes"]:
            o.append(f"- {a['block']}: " + "; ".join(f"{k} = {v}" for k, v in a["attribs"].items()))
    if r["dimensions"]:
        o += ["", f"## Размеры ({len(r['dimensions'])})"] + \
             [f"- {d['measurement']}{(' / текст: ' + d['text_override']) if d['text_override'] else ''} [{d['layer']}]"
              for d in r["dimensions"][:100]]
    if r["texts"]:
        o += ["", f"## Тексты ({r['texts_total']}, показано {len(r['texts'])})"] + \
             [f"- ({t['x']}, {t['y']}) [{t['layer']}]: {t['text']}" for t in r["texts"]]
    if r["closed_contours"]:
        o += ["", "## Замкнутые контуры (по убыванию площади)", "| Тип | Слой | Площадь, мм² | Периметр, мм |", "|---|---|---|---|"]
        o += [f"| {c['type']} | {c['layer']} | {c['area_mm2']} | {c['perimeter_mm']} |" for c in r["closed_contours"][:50]]
    o += ["", "_Проверьте предпросмотр (--render), что разобрано именно то, что изображено. "
          "Тексты в «взорванных» штампах ищутся по координатам основной надписи (ГОСТ 2.104)._"]
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dxf")
    ap.add_argument("--json", help="сохранить полный результат в JSON")
    ap.add_argument("--render", help="сохранить предпросмотр PNG/PDF/SVG (нужен matplotlib)")
    ap.add_argument("--texts", type=int, default=50, help="сколько текстов вывести")
    ap.add_argument("--tol", type=float, default=CHAIN_TOL,
                    help=f"допуск совпадения концов при сборке контуров, мм (по умолчанию {CHAIN_TOL})")
    ap.add_argument("--layers", help="слои через запятую для длины реза и контуров, напр. CUT,0 (по умолчанию все)")
    a = ap.parse_args(argv)
    if a.tol <= 0:
        ap.error("--tol должен быть > 0")
    layers = [x for x in a.layers.split(",") if x.strip()] if a.layers else None
    r, doc = inspect(a.dxf, a.texts, tol=a.tol, layers=layers)
    getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")
    print(to_md(r))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"\nJSON: {a.json}")
    if a.render:
        try:
            import matplotlib
            matplotlib.use("Agg")
            from ezdxf.addons.drawing import matplotlib as dmpl
            dmpl.qsave(doc.modelspace(), a.render, bg="#FFFFFF")
            print(f"Предпросмотр: {a.render}")
        except ImportError:
            print("Для --render установите matplotlib")
    return 0


if __name__ == "__main__":
    sys.exit(main())
