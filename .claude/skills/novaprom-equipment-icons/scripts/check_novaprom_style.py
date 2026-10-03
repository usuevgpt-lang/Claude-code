#!/usr/bin/env python3
"""check_novaprom_style.py - check a candidate SVG against the NOVAPROM ICON DESIGN SYSTEM.

Usage:
  python check_novaprom_style.py [--family auto|tile|dropdown|simple] [--spec icon-spec.json]
                                 [--json] [--no-render] FILE [FILE ...]

Reference ranges are read from references/icon-spec.json (measured on the 14 tile, 7 dropdown and
6 simple icons of novaprom.ru); nothing is invented here. Statuses:
  PASS  inside the measured range / rule
  WARN  outside the measured range, or a soft rule (joins, caps, budget) - review
  FAIL  breaks a hard rule of the family (canvas, palette, stroke weights, gradients/opacity/
        transforms/text/raster, geometry clipped by the viewBox)
  SKIP  needs an optional package (svgelements for geometry; cairosvg or resvg + Pillow for ink)
  INFO  reported for the designer, not judged
Stdlib-only checks always run: canvas, palette, stroke widths, joins/caps/miterlimit, forbidden
features, element types, path and node counts. Geometry checks (centring, padding, live area,
2-unit line share, ellipse ratio, projection) need `pip install svgelements`; the ink coverage
check needs cairosvg or the resvg CLI, plus Pillow. Exit code 1 if any FAIL, 2 on usage error.
Run svg-icons/scripts/check_svg.py as well: this script checks style, not security.
"""
import argparse
import glob
import io
import json
import math
import os
import re
import shutil
import statistics as st
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SPEC = os.path.join(HERE, "..", "references", "icon-spec.json")
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
NON_RENDERED = {"defs", "clipPath", "mask", "symbol", "pattern", "marker", "linearGradient",
                "radialGradient", "filter", "title", "desc", "metadata", "style"}
STYLE_PROPS = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
               "stroke-miterlimit", "opacity", "fill-opacity", "stroke-opacity")
DEFAULTS = {"fill": "#000000", "stroke": "none", "stroke-width": "1", "stroke-linecap": "butt",
            "stroke-linejoin": "miter", "stroke-miterlimit": "4", "opacity": "1",
            "fill-opacity": "1", "stroke-opacity": "1"}
NAMED = {"white": "#ffffff", "black": "#000000", "none": "none"}
# display widths (CSS px) per family, from icon-spec.json families.*.display_size_css_px
DISPLAY_PX = {"tile": (106, 239), "dropdown": (57,), "simple": (100,)}


# --------------------------------------------------------------------------- helpers
def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def norm_color(c):
    if c is None:
        return None
    c = c.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        return "#" + "".join(ch * 2 for ch in c[1:])
    return NAMED.get(c, "currentColor" if c == "currentcolor" else c)


def fnum(v, nd=2):
    if v is None:
        return "-"
    if isinstance(v, float):
        r = round(v, nd)
        return str(int(r)) if r == int(r) else f"{r:g}"
    return str(v)


def inside(v, lo, hi, eps=0.15):
    """Range test with a small allowance for the 1-2 decimal rounding of the measured min/max."""
    return lo - eps <= v <= hi + eps


def rng(lo, hi, unit=""):
    return f"{fnum(lo)}..{fnum(hi)}{unit}"


def expand_paths(items):
    out = []
    for item in items:
        if os.path.isdir(item):
            out.extend(sorted(glob.glob(os.path.join(item, "*.svg"))))
        elif any(ch in item for ch in "*?["):
            out.extend(sorted(glob.glob(item)))
        else:
            out.append(item)
    return list(dict.fromkeys(out))


def parse_style(el):
    d = {p: el.get(p).strip() for p in STYLE_PROPS if el.get(p) is not None}
    for decl in (el.get("style") or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            if k.strip() in STYLE_PROPS:
                d[k.strip()] = v.strip()
    return d


def collect(root):
    """(element, effective style, list of ancestor transforms) for rendered shapes."""
    out = []

    def walk(el, inherited, transforms):
        name = local(el.tag)
        if name in NON_RENDERED:
            return
        style = dict(inherited)
        style["opacity"] = "1"
        style.update(parse_style(el))
        tr = transforms + ([el.get("transform")] if el.get("transform") else [])
        if name in SHAPES:
            out.append((el, style, tr))
        for ch in el:
            if isinstance(ch.tag, str):
                walk(ch, style, tr)

    walk(root, dict(DEFAULTS), [])
    return out


# --------------------------------------------------------------------------- node count (stdlib)
ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
TOKEN_RE = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")


def count_nodes(d):
    """Drawing segments in path data, counted like the measurement (zero-length L/Z skipped)."""
    toks = [(m.group(1), m.group(2)) for m in TOKEN_RE.finditer(d or "")]
    i, n, cmd = 0, 0, None
    cx = cy = sx = sy = 0.0
    while i < len(toks):
        c, num = toks[i]
        if c:
            cmd = c
            i += 1
            if cmd in "Zz":
                if math.hypot(cx - sx, cy - sy) > 1e-6:
                    n += 1
                cx, cy = sx, sy
                continue
        if cmd is None:
            break
        k = ARGS[cmd.lower()]
        vals = []
        while len(vals) < k and i < len(toks) and toks[i][1] is not None:
            vals.append(float(toks[i][1]))
            i += 1
        if len(vals) < k:
            break
        rel = cmd.islower()
        lc = cmd.lower()
        if lc == "m":
            x, y = vals
            cx, cy = (cx + x, cy + y) if rel else (x, y)
            sx, sy = cx, cy
            cmd = "l" if rel else "L"  # implicit lineto after the first pair
            continue
        if lc == "h":
            nx, ny = (cx + vals[0] if rel else vals[0]), cy
        elif lc == "v":
            nx, ny = cx, (cy + vals[0] if rel else vals[0])
        else:
            nx, ny = vals[-2], vals[-1]
            if rel:
                nx, ny = cx + nx, cy + ny
        if lc in "lhv":
            if math.hypot(nx - cx, ny - cy) > 1e-6:
                n += 1
        else:
            n += 1
        cx, cy = nx, ny
    return n


def shape_nodes(el):
    name = local(el.tag)
    if name == "path":
        return count_nodes(el.get("d"))
    if name in ("rect", "polygon", "polyline", "line"):
        if name == "line":
            return 1
        if name == "rect":
            return 8 if (el.get("rx") or el.get("ry")) else 4
        pts = NUM_RE.findall(el.get("points") or "")
        return max(0, len(pts) // 2 - 1) + (1 if name == "polygon" else 0)
    return 4  # circle / ellipse ~ 4 arcs


# --------------------------------------------------------------------------- spec -> rules
def load_rules(spec, fam):
    raw = spec["family_summary_raw"][fam]
    per = {k: v for k, v in spec["per_icon"].items() if k.startswith(fam + "/")}

    def mm(key):
        a = raw.get(key) or {}
        return (a.get("min"), a.get("max"), a.get("median"))

    canvases = [tuple(float(x) for x in vb.split()[2:]) for vb in raw["viewBoxes"]]
    main_canvas = max(raw["viewBoxes"].items(), key=lambda kv: kv[1])[0]
    sw = {float(k): v for k, v in raw["stroke_width_element_counts"].items()}
    tot = sum(sw.values())
    widths = sorted(w for w, c in sw.items() if c >= 0.05 * tot)
    outliers = sorted(w for w in sw if w not in widths)
    heavy = max(widths) if len(widths) > 1 else None
    heavy_shares = [v["stroke_length_share_by_width_pct"].get(f"{heavy:.1f}") for v in per.values()] if heavy else []
    heavy_shares = [h for h in heavy_shares if h is not None]
    ell = [(v.get("ellipse_minor_major_ratio") or {}).get("median") for v in per.values()]
    ell = [e for e in ell if e is not None]
    joins, caps = raw["linejoin_counts"], raw["linecap_counts"]
    dom_join = max(joins, key=joins.get)
    dom_cap = max(caps, key=caps.get)
    two_weight = any(len(v.get("stroke_widths", {})) >= 2 for v in per.values())
    budget = None
    for rule in spec.get("reproduction_rules_for_new_icons", []):
        m = re.search(r"(\d+)-(\d+) paths, (\d+)-(\d+) nodes for tile icons; (\d+)-(\d+) paths, (\d+)-(\d+) nodes for menu", rule)
        if m:
            g = [int(x) for x in m.groups()]
            budget = {"tile": (g[0], g[1], g[2], g[3]), "dropdown": (g[4], g[5], g[6], g[7])}.get(fam)
    dirs = raw.get("direction_share_pct", {})
    return {
        "family": fam, "n_icons": raw["icons"],
        "canvas": tuple(float(x) for x in main_canvas.split()[2:]),
        "canvas_all": canvases, "viewBox": main_canvas,
        "strokes": set(raw["stroke_colour_element_counts"]),
        "fills": set(raw["fill_colour_element_counts"]),
        "widths": widths, "width_outliers": outliers,
        "heavy": heavy, "heavy_range": (min(heavy_shares), max(heavy_shares), st.median(heavy_shares)) if heavy_shares else None,
        "join": (dom_join, round(100 * joins[dom_join] / max(1, sum(joins.values())), 1)),
        "cap": (dom_cap, round(100 * caps[dom_cap] / max(1, sum(caps.values())), 1)),
        "two_weight": two_weight,
        "flat": fam == "simple",  # flat front/side views: projection rule does not apply
        "miterlimit": set(raw["miterlimit_counts"]),
        "shapes": mm("shape_count"), "nodes": mm("nodes"), "budget": budget,
        "pad": {s: mm(f"padding_pct_{s}") for s in ("left", "top", "right", "bottom")},
        "live_w": mm("live_area_w_pct"), "live_h": mm("live_area_h_pct"),
        "cx": mm("bbox_center_offset_x_pct"), "cy": mm("bbox_center_offset_y_pct"),
        "ink": mm("ink_coverage_pct_of_viewBox"),
        "ellipse": (min(ell), max(ell), st.median(ell)) if ell else None,
        "iso30_max": (dirs.get("iso30") or {}).get("max"), "diag45_max": (dirs.get("diag45") or {}).get("max"),
        "vertical": (dirs.get("vertical") or {}).get("median"),
        "with_clip": raw.get("with_clipPath", []),
    }


def detect_family(vb):
    w, h = vb[2], vb[3]
    if (w, h) in ((220.0, 160.0), (439.0, 160.0)):
        return "tile"
    if (w, h) == (65.0, 50.0):
        return "dropdown"
    if (w, h) == (100.0, 70.0):
        return "simple"
    return "tile"


# --------------------------------------------------------------------------- geometry (svgelements)
def geometry(elements, vb):
    import svgelements as se
    bbox = [math.inf, math.inf, -math.inf, -math.inf]
    len_by_w = Counter()
    ellipses = []
    dir_len = defaultdict(float)

    def bucket(deg):
        a = deg % 180.0
        near = lambda t, tol: min(abs(a - t), 180 - abs(a - t)) <= tol  # noqa: E731
        if near(0, 2.5):
            return "horizontal"
        if near(90, 2.5):
            return "vertical"
        if near(30, 4) or near(150, 4):
            return "iso30"
        if near(45, 3) or near(135, 3):
            return "diag45"
        return "oblique_other"

    def dist(p, a, b):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            return math.hypot(p[0] - a[0], p[1] - a[1])
        return abs((b[1] - a[1]) * p[0] - (b[0] - a[0]) * p[1] + b[0] * a[1] - b[1] * a[0]) / L

    for el, style, trs in elements:
        name = local(el.tag)
        f = lambda k: float(el.get(k, 0) or 0)  # noqa: E731
        if name == "path":
            p = se.Path(el.get("d", ""))
        elif name == "rect":
            p = se.Path(se.Rect(f("x"), f("y"), f("width"), f("height"), f("rx"), f("ry") or f("rx")))
        elif name == "circle":
            p = se.Path(se.Circle(f("cx"), f("cy"), f("r")))
        elif name == "ellipse":
            p = se.Path(se.Ellipse(f("cx"), f("cy"), f("rx"), f("ry")))
            if f("rx") and f("ry"):
                ellipses.append(min(f("rx"), f("ry")) / max(f("rx"), f("ry")))
        elif name == "line":
            p = se.Path(f"M{f('x1')},{f('y1')} L{f('x2')},{f('y2')}")
        else:
            pts = el.get("points", "").strip()
            p = se.Path("M" + pts + (" Z" if name == "polygon" else ""))
        if trs:
            m = se.Matrix()
            for t in trs:  # outermost first; m = T_child * m_parent (child applied first)
                m = se.Matrix(t) * m
            p = p * m
            p.reify()
        stroke = norm_color(style.get("stroke"))
        sw = float(style.get("stroke-width", "1")) if stroke not in (None, "none") else 0.0
        bb = p.bbox()
        if bb:
            h = sw / 2
            bbox = [min(bbox[0], bb[0] - h), min(bbox[1], bb[1] - h), max(bbox[2], bb[2] + h), max(bbox[3], bb[3] + h)]
        if sw:
            try:
                len_by_w[round(sw, 3)] += p.length(error=1e-3)
            except Exception:
                pass
        for sub in p.as_subpaths():
            segs = [g for g in sub if not isinstance(g, se.Move)]
            cub = [g for g in segs if isinstance(g, se.CubicBezier)]
            rest = [g for g in segs if not isinstance(g, se.CubicBezier) and not (isinstance(g, se.Close) and g.length() < 1e-3)]
            if len(cub) == 4 and not rest:
                x0, y0, x1, y1 = se.Path(sub).bbox()
                w_, h_ = x1 - x0, y1 - y0
                if max(w_, h_) > 0 and min(w_, h_) / max(w_, h_) < 0.97:
                    ellipses.append(min(w_, h_) / max(w_, h_))
        for seg in p:
            if isinstance(seg, se.Move) or seg.start is None or seg.end is None:
                continue
            a, b = (seg.start.x, seg.start.y), (seg.end.x, seg.end.y)
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-6:
                continue
            straight = isinstance(seg, (se.Line, se.Close))
            if isinstance(seg, se.CubicBezier):
                tol = max(0.02, 0.002 * max(vb[2], vb[3]))
                straight = dist((seg.control1.x, seg.control1.y), a, b) < tol and dist((seg.control2.x, seg.control2.y), a, b) < tol
            if straight:
                dir_len[bucket(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))] += L
    tl = sum(len_by_w.values())
    sl = sum(dir_len.values())
    return {
        "bbox": bbox if math.isfinite(bbox[0]) else None,
        "len_share": {w: 100 * v / tl for w, v in len_by_w.items()} if tl else {},
        "ellipse_median": st.median(ellipses) if ellipses else None, "ellipse_n": len(ellipses),
        "dir_share": {k: 100 * v / sl for k, v in dir_len.items()} if sl else {},
    }


# --------------------------------------------------------------------------- ink coverage (render)
def ink_coverage(raw, vb):
    """Percent of canvas pixels with alpha >= 0.5 (same definition as the measurement)."""
    try:
        from PIL import Image
    except ImportError:
        return None, "Pillow not installed"
    scale = max(1, min(8, int(800 / max(vb[2], vb[3])) or 1))
    W, H = int(round(vb[2] * scale)), int(round(vb[3] * scale))
    png, how = None, None
    try:
        import cairosvg
        png, how = cairosvg.svg2png(bytestring=raw, output_width=W, output_height=H, unsafe=False), "cairosvg"
    except Exception:
        exe = shutil.which("resvg")
        if exe:
            with tempfile.TemporaryDirectory() as tmp:
                src, out = os.path.join(tmp, "in.svg"), os.path.join(tmp, "o.png")
                with open(src, "wb") as fh:
                    fh.write(raw)
                r = subprocess.run([exe, "--width", str(W), "--height", str(H), src, out], capture_output=True)
                if r.returncode == 0:
                    png, how = open(out, "rb").read(), "resvg"
    if png is None:
        return None, "no renderer (cairosvg or resvg)"
    alpha = Image.open(io.BytesIO(png)).convert("RGBA").getchannel("A")
    hist = alpha.histogram()
    return 100.0 * sum(hist[128:]) / (W * H), how


# --------------------------------------------------------------------------- main check
def check_file(path, spec, family="auto", render=True):
    rows = []

    def row(status, check, value, ref):
        rows.append({"status": status, "check": check, "value": value, "reference": ref})

    raw = open(path, "rb").read()
    if re.search(rb"<!DOCTYPE|<!ENTITY", raw, re.I):
        row("FAIL", "xml", "DOCTYPE/ENTITY present", "run svg-icons check_svg.py")
        return "?", rows
    root = ET.fromstring(raw)
    vbn = [float(x) for x in NUM_RE.findall(root.get("viewBox") or "")]
    if len(vbn) != 4 or vbn[2] <= 0 or vbn[3] <= 0:
        row("FAIL", "canvas", f"viewBox={root.get('viewBox')!r}", "viewBox required")
        return "?", rows
    fam = detect_family(vbn) if family == "auto" else family
    R = load_rules(spec, fam)
    ref_n = f"{R['n_icons']} {fam} icons"

    # 1 canvas
    size = (vbn[2], vbn[3])
    vb_txt = " ".join(fnum(v) for v in vbn)
    if size == R["canvas"] and vbn[0] == 0 and vbn[1] == 0:
        row("PASS", "canvas", f"viewBox {vb_txt}", f"{R['viewBox']}")
    elif size in R["canvas_all"]:
        row("WARN", "canvas", f"viewBox {vb_txt}", f"{R['viewBox']} (this size is a known outlier)")
    else:
        row("FAIL", "canvas", f"viewBox {vb_txt}", f"{R['viewBox']}")
    w, h = root.get("width"), root.get("height")
    if w and h and NUM_RE.findall(w) and NUM_RE.findall(h) and \
            (float(NUM_RE.findall(w)[0]), float(NUM_RE.findall(h)[0])) == size:
        row("PASS", "width/height", f"{w}x{h}", "= viewBox (1:1 export)")
    else:
        row("WARN", "width/height", f"{w}x{h}", "= viewBox (1:1 export)")

    elements, bg_rects = [], []
    for el, s, tr in collect(root):
        if local(el.tag) == "rect" and norm_color(s.get("fill")) == "#ffffff" and \
                abs(float(el.get("width", 0) or 0) - vbn[2]) < 0.01 and abs(float(el.get("height", 0) or 0) - vbn[3]) < 0.01:
            bg_rects.append(el)  # excluded from all measurements, as in the reference analysis
        else:
            elements.append((el, s, tr))
    strokes, fills, widths = Counter(), Counter(), Counter()
    joins, caps, miters, opac = Counter(), Counter(), Counter(), 0
    for el, s, _ in elements:
        sc, fc = norm_color(s.get("stroke")), norm_color(s.get("fill"))
        if fc not in (None, "none"):
            fills[fc] += 1
        if sc not in (None, "none"):
            strokes[sc] += 1
            widths[float(s.get("stroke-width", "1"))] += 1
            joins[s.get("stroke-linejoin", "miter")] += 1
            caps[s.get("stroke-linecap", "butt")] += 1
            miters[s.get("stroke-miterlimit", "4")] += 1
        for p in ("opacity", "fill-opacity", "stroke-opacity"):
            try:
                opac += float(s.get(p, "1")) != 1.0
            except ValueError:
                opac += 1

    # 2 palette
    bad = sorted(set(strokes) - R["strokes"])
    row("FAIL" if bad or not strokes else "PASS", "stroke colours",
        ", ".join(f"{k}x{v}" for k, v in strokes.items()) or "none",
        "{" + ", ".join(sorted(c.upper() for c in R["strokes"])) + "}")
    bad = sorted(set(fills) - R["fills"])
    row("FAIL" if bad else "PASS", "fill colours",
        ", ".join(f"{k}x{v}" for k, v in fills.items()) or "none",
        "{" + ", ".join(sorted(c.upper() for c in R["fills"])) + "} occluder only")

    # 3 stroke widths
    tol = 0.05
    off = [x for x in widths if not any(abs(x - a) <= tol for a in R["widths"])]
    known = [x for x in off if any(abs(x - a) <= tol for a in R["width_outliers"])]
    status = "FAIL" if [x for x in off if x not in known] else ("WARN" if known else "PASS")
    row(status, "stroke widths", ", ".join(f"{fnum(k)}x{v}" for k, v in sorted(widths.items())),
        "{" + ", ".join(fnum(x) for x in R["widths"]) + "} +/-" + fnum(tol) +
        (f"; outlier seen: {', '.join(fnum(x) for x in R['width_outliers'])}" if R["width_outliers"] else ""))

    # 4 joins / caps / miterlimit
    for label, counts, (dom, share) in (("linejoin", joins, R["join"]), ("linecap", caps, R["cap"])):
        mine = 100 * counts.get(dom, 0) / max(1, sum(counts.values()))
        need = min(80.0, share - 10)
        row("PASS" if mine >= need else "WARN", label, f"{dom} {mine:.0f}% ({dict(counts)})",
            f"{dom} ~{fnum(share, 0)}% in family; >= {fnum(need, 0)}% expected")
    mset = {fnum(float(m)) for m in miters}
    row("PASS" if mset <= {fnum(float(x)) for x in R["miterlimit"]} else "WARN", "miterlimit",
        ", ".join(sorted(mset)) or "-", ", ".join(sorted(fnum(float(x)) for x in R["miterlimit"])))

    # 5 forbidden features
    tags = Counter(local(e.tag) for e in root.iter() if isinstance(e.tag, str))
    forb = []
    for t in ("linearGradient", "radialGradient", "pattern", "filter", "mask", "text", "image", "style", "use", "foreignObject", "script"):
        if tags.get(t):
            forb.append(f"<{t}>x{tags[t]}")
    ntr = sum(1 for e in root.iter() if isinstance(e.tag, str) and e.get("transform"))
    if ntr:
        forb.append(f"transform x{ntr}")
    if opac:
        forb.append(f"opacity x{opac}")
    ncls = sum(1 for e in root.iter() if isinstance(e.tag, str) and e.get("class"))
    if ncls:
        forb.append(f"class x{ncls}")
    if "currentColor" in strokes or "currentColor" in fills:
        forb.append("currentColor")
    row("FAIL" if forb else "PASS", "no gradients/opacity/transforms", ", ".join(forb) or "none",
        "none (flat hard-coded colours)")

    # 6 element types
    shapes = Counter(local(e.tag) for e, _, _ in elements)
    soft = []
    if set(shapes) - {"path"}:
        soft.append("non-path shapes " + ", ".join(f"<{k}>x{v}" for k, v in shapes.items() if k != "path"))
    if tags.get("g"):
        soft.append(f"<g>x{tags['g']}")
    if tags.get("clipPath"):
        soft.append(f"<clipPath>x{tags['clipPath']}")
    if bg_rects:
        soft.append("opaque full-canvas white <rect> background (excluded from geometry)")
    row("WARN" if soft else "PASS", "element types", "; ".join(soft) or "path only",
        f"flat list of <path>; clipPath only in {len(R['with_clip'])} of {R['n_icons']}")

    # 7 path / node count
    n_shapes = sum(shapes.values())
    n_nodes = sum(shape_nodes(e) for e, _, _ in elements)
    lo, hi, med = R["shapes"]
    b = R["budget"]
    if b:
        row("PASS" if b[0] <= n_shapes <= b[1] else "WARN", "path count", str(n_shapes),
            f"budget {b[0]}..{b[1]}; measured {rng(lo, hi)}, median {fnum(med)}")
        lo, hi, med = R["nodes"]
        row("PASS" if b[2] <= n_nodes <= b[3] else "WARN", "node count", str(n_nodes),
            f"budget {b[2]}..{b[3]}; measured {rng(lo, hi)}, median {fnum(med)}")
    else:
        row("PASS" if lo <= n_shapes <= hi else "WARN", "path count", str(n_shapes), f"measured {rng(lo, hi)}")
        lo, hi, med = R["nodes"]
        row("PASS" if lo <= n_nodes <= hi else "WARN", "node count", str(n_nodes), f"measured {rng(lo, hi)}")

    # 8 geometry
    geo_names = ["horizontal centring", "vertical centring", "padding L/T/R/B", "live area W x H",
                 "2-unit line share", "cylinder ellipse ratio", "projection (30/45 deg lines)"]
    try:
        import svgelements  # noqa: F401
        geo = geometry(elements, vbn)
    except ImportError:
        geo = None
        for g in geo_names:
            row("SKIP", g, "svgelements not installed", "pip install svgelements (in a venv)")
    if geo and geo["bbox"]:
        x0, y0, x1, y1 = geo["bbox"]
        W, H = vbn[2], vbn[3]
        ox = 100 * ((x0 + x1) / 2 - (vbn[0] + W / 2)) / W
        oy = 100 * ((y0 + y1) / 2 - (vbn[1] + H / 2)) / H
        dx = (vbn[0] + W / 2) - (x0 + x1) / 2
        tol_x = max(0.5, max(abs(R["cx"][0]), abs(R["cx"][1])) + 0.1)
        row("PASS" if abs(ox) <= tol_x else "WARN", "horizontal centring",
            f"{ox:+.2f}% (shift x by {dx:+.1f})" if abs(ox) > tol_x else f"{ox:+.2f}%",
            f"exact: {rng(*R['cx'][:2], '%')} measured; tolerance {fnum(tol_x)}%")
        dy = (vbn[1] + H / 2) - (y0 + y1) / 2
        row("PASS" if abs(oy) <= 1.0 else "WARN", "vertical centring",
            f"{oy:+.2f}% (shift y by {dy:+.1f})" if abs(oy) > 1.0 else f"{oy:+.2f}%",
            f"median {fnum(R['cy'][2])}%, range {rng(*R['cy'][:2], '%')}; tolerance 1%")
        pads = {"left": 100 * (x0 - vbn[0]) / W, "top": 100 * (y0 - vbn[1]) / H,
                "right": 100 * (vbn[0] + W - x1) / W, "bottom": 100 * (vbn[1] + H - y1) / H}
        status = "PASS"
        for side, v in pads.items():
            lo, hi, _ = R["pad"][side]
            if v < min(0.0, lo) - 0.15:
                status = "FAIL"
            elif not inside(v, lo, hi) and status != "FAIL":
                status = "WARN"
        row(status, "padding L/T/R/B", "/".join(f"{pads[s]:.1f}" for s in pads) + " %",
            "/".join(rng(*R["pad"][s][:2]) for s in pads) + " %")
        lw, lh = 100 * (x1 - x0) / W, 100 * (y1 - y0) / H
        ok = inside(lw, *R["live_w"][:2]) and inside(lh, *R["live_h"][:2])
        row("PASS" if ok else "WARN", "live area W x H", f"{lw:.1f} x {lh:.1f} %",
            f"{rng(*R['live_w'][:2])} x {rng(*R['live_h'][:2])} %, median {fnum(R['live_w'][2])} x {fnum(R['live_h'][2])}")
        if R["two_weight"] and R["heavy"] and R["heavy_range"]:
            hs = sum(v for k, v in geo["len_share"].items() if abs(k - R["heavy"]) <= tol)
            lo, hi, med = R["heavy_range"]
            row("PASS" if inside(hs, lo, hi) else "WARN", "2-unit line share", f"{hs:.1f}% of stroke length",
                f"{rng(lo, hi, '%')}, median {fnum(med)}%")
        else:
            row("INFO", "2-unit line share", "n/a: one stroke weight per icon in this family", "-")
        if R["ellipse"]:
            lo, hi, med = R["ellipse"]
            em = geo["ellipse_median"]
            if em is None:
                row("INFO", "cylinder ellipse ratio", "no 4-cubic ellipses found", f"per-icon medians {lo:.3f}..{hi:.3f}")
            else:
                row("PASS" if inside(em, lo, hi, 0.003) else "WARN", "cylinder ellipse ratio",
                    f"median {em:.3f} (n={geo['ellipse_n']})", f"per-icon medians {lo:.3f}..{hi:.3f}, family {med:.3f}")
        ds = geo["dir_share"]
        i30, d45 = ds.get("iso30", 0.0), ds.get("diag45", 0.0)
        ok = (R["iso30_max"] is None or i30 <= R["iso30_max"] + 0.15) and (R["diag45_max"] is None or d45 <= R["diag45_max"] + 0.15)
        row("INFO" if R["flat"] else ("PASS" if ok else "WARN"), "projection (30/45 deg lines)",
            f"30deg {i30:.1f}%, 45deg {d45:.1f}%, vertical {ds.get('vertical', 0):.1f}%",
            f"max 30deg {fnum(R['iso30_max'])}%, 45deg {fnum(R['diag45_max'])}%; vertical median {fnum(R['vertical'])}%")
    elif geo is not None:
        row("FAIL", "geometry", "no drawable geometry", "-")

    # 9 ink coverage
    if render:
        if bg_rects:
            parent = {c: p for p in root.iter() for c in p}
            for el in bg_rects:
                parent[el].remove(el)
            raw = ET.tostring(root)
        ink, how = ink_coverage(raw, vbn)
        lo, hi, med = R["ink"]
        if ink is None:
            row("SKIP", "ink coverage", how, "pip install cairosvg Pillow, or resvg on PATH")
        else:
            row("PASS" if inside(ink, lo, hi) else "WARN", "ink coverage", f"{ink:.1f}% of canvas ({how})",
                f"{rng(lo, hi, '%')}, median {fnum(med)}%")
    # 10 display weights (info)
    if fam in DISPLAY_PX:
        parts = []
        for px in DISPLAY_PX[fam]:
            parts.append(f"{px}px: " + ", ".join(f"{fnum(w_)}u={w_ * px / vbn[2]:.2f}px" for w_ in sorted(widths)))
        row("INFO", "rendered line weight", "; ".join(parts), "< 1 px renders as a faint hairline")
    return fam, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--family", choices=["auto", "tile", "dropdown", "simple"], default="auto")
    ap.add_argument("--spec", default=DEFAULT_SPEC)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-render", action="store_true", help="skip the ink coverage render")
    args = ap.parse_args(argv)
    try:
        with open(args.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
    except OSError as exc:
        print(f"cannot read spec: {exc}", file=sys.stderr)
        return 2
    files = expand_paths(args.files)
    if not files:
        print("no SVG files found", file=sys.stderr)
        return 2
    try:
        import svgelements
        geo_lib = f"svgelements {getattr(svgelements, 'SVGELEMENTS_VERSION', '')}".strip()
    except ImportError:
        geo_lib = "svgelements MISSING - geometry checks skipped"
    results, any_fail = [], False
    for f in files:
        try:
            fam, rows = check_file(f, spec, args.family, not args.no_render)
        except (ET.ParseError, OSError) as exc:
            fam, rows = "?", [{"status": "FAIL", "check": "read/parse", "value": str(exc), "reference": "-"}]
        cnt = Counter(r["status"] for r in rows)
        any_fail |= cnt.get("FAIL", 0) > 0
        results.append({"file": f, "family": fam, "summary": dict(cnt), "rows": rows})
    if args.json:
        print(json.dumps({"geometry": geo_lib, "results": results}, ensure_ascii=False, indent=1))
        return 1 if any_fail else 0
    for r in results:
        print(f"\n== {r['file']}  [family: {r['family']}; geometry: {geo_lib}]")
        wc = max(len(x["check"]) for x in r["rows"])
        wv = min(46, max(len(x["value"]) for x in r["rows"]))
        print(f"{'STATUS':6}  {'CHECK':{wc}}  {'VALUE':{wv}}  REFERENCE")
        for x in r["rows"]:
            print(f"{x['status']:6}  {x['check']:{wc}}  {x['value']:{wv}}  {x['reference']}")
        s = r["summary"]
        print("-- " + ", ".join(f"{s.get(k, 0)} {k}" for k in ("PASS", "WARN", "FAIL", "SKIP", "INFO")))
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
