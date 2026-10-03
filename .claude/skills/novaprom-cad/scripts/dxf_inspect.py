#!/usr/bin/env python3
"""Анализ DXF-чертежа/развёртки: состав, основная надпись, размеры, контуры, длина реза.

Запуск:
    python dxf_inspect.py drawing.dxf [--json out.json] [--render preview.png] [--texts 50]

Требуется: ezdxf (python -m pip install ezdxf==1.4.4); для --render также matplotlib.
Файл открывается в режиме восстановления (ezdxf.recover) — исходный файл не изменяется.
DWG сначала конвертировать в DXF (ODA File Converter) — см. SKILL.md.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter

try:
    import ezdxf
    from ezdxf import bbox, recover
    from ezdxf.path import make_path
except ImportError:
    raise SystemExit("Установите ezdxf: python -m pip install ezdxf==1.4.4")

UNITS = {0: "не задано", 1: "дюймы", 2: "футы", 4: "мм", 5: "см", 6: "м"}
FLATTEN = 0.05  # мм, точность аппроксимации кривых


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


def inspect(path: str, max_texts: int) -> dict:
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
    # замкнутые контуры и длина реза
    contours, cut = [], 0.0
    for e in ents:
        t = e.dxftype()
        L = length_of(e)
        cut += L
        closed = (t == "CIRCLE") or (t in ("LWPOLYLINE", "POLYLINE") and e.closed) or \
                 (t in ("SPLINE",) and getattr(e, "closed", False)) or \
                 (t == "ELLIPSE" and abs((e.dxf.end_param - e.dxf.start_param) - 2 * math.pi) < 1e-6)
        if closed:
            if t == "CIRCLE":
                area = math.pi * e.dxf.radius ** 2
            else:
                pts = path_points(e)
                area = poly_area(pts) if len(pts) > 2 else 0.0
            contours.append({"type": t, "layer": e.dxf.layer, "area_mm2": round(area, 2), "perimeter_mm": round(L, 2)})
    contours.sort(key=lambda c: -c["area_mm2"])
    res["closed_contours"] = contours
    res["cut_length_total_mm"] = round(cut, 1)
    if contours:
        outer = contours[0]["area_mm2"]
        holes = sum(c["area_mm2"] for c in contours[1:])
        res["blank_estimate"] = {"outer_area_mm2": outer, "holes_area_mm2": round(holes, 2),
                                 "net_area_mm2": round(outer - holes, 2), "pierces": len(contours),
                                 "note": "оценка: наибольший замкнутый контур считается наружным, остальные — отверстиями"}
    return res, doc


def to_md(r: dict) -> str:
    o = [f"# Анализ DXF: {r['file']}", "",
         f"- Версия DXF: {r['dxf_version']}; единицы: {r['units']}; ошибки аудита: {r['audit_errors']} (исправлено {r['audit_fixes']})"]
    if r["extents"]:
        o.append(f"- Габарит: {r['extents']['size'][0]} × {r['extents']['size'][1]}")
    o.append(f"- Сущности: {', '.join(f'{k} {v}' for k, v in r['entities_by_type'].items())}")
    o.append(f"- Слои ({len(r['layers'])}): {', '.join(f'{k} ({v})' for k, v in r['entities_by_layer'].items())}")
    o.append(f"- Блоки: {', '.join(r['blocks']) or '—'}")
    o.append(f"- Суммарная длина контуров (оценка длины реза): {r['cut_length_total_mm']} мм")
    if r.get("blank_estimate"):
        b = r["blank_estimate"]
        o.append(f"- Заготовка (оценка): наружный контур {b['outer_area_mm2']} мм², отверстия {b['holes_area_mm2']} мм², "
                 f"нетто {b['net_area_mm2']} мм², врезок {b['pierces']}")
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
    a = ap.parse_args(argv)
    r, doc = inspect(a.dxf, a.texts)
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
