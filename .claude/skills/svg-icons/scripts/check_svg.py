#!/usr/bin/env python3
"""check_svg.py - structural and security checks for SVG icons (Python stdlib only).

Usage:
  python check_svg.py [options] PATH [PATH ...]
  PATH = file, directory (all *.svg inside) or a glob pattern ("icons/*.svg", expanded here,
  so it also works in Windows cmd/PowerShell).

Options:
  --require-title    a missing <title> (first child of <svg>) is an error
  --allow-raster     embedded raster images (<image> with data:image/png|jpeg|gif|webp) are a
                     warning instead of an error
  --max-bytes N      warn above N bytes (default 10000)
  --json             machine-readable output
  -q, --quiet        print only files with errors or warnings

Errors (exit code 1): DOCTYPE/ENTITY, xml-stylesheet PI, not well-formed XML, root not <svg> in
the SVG namespace, missing/invalid viewBox, <script>/<foreignObject>/<iframe>/<embed>/<object>/
<handler>/<listener>, on* event attributes, javascript:/vbscript:/data:text/html URLs, any
external reference (href/src/url() not starting with '#'), nested data:image/svg+xml, embedded
raster unless --allow-raster, animation targeting href or on*, @import/expression()/external url()
in CSS.
Warnings never fail the run. The report also lists size, viewBox, element counts and the
effective (inherited) stroke colours, stroke widths, fills, linecaps and linejoins.
Exit codes: 0 = no errors, 1 = errors found, 2 = usage error / no SVG files found.
"""
import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
EDITOR_NS = (
    "http://www.inkscape.org/namespaces/inkscape",
    "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "http://www.bohemiancoding.com/sketch/ns",
    "http://ns.adobe.com/",
    "http://www.figma.com/",
)
FORBIDDEN = {"script", "foreignObject", "iframe", "embed", "object", "handler", "listener"}
ANIMATION = {"set", "animate", "animateTransform", "animateMotion", "animateColor"}
SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
NON_RENDERED = {"defs", "clipPath", "mask", "symbol", "pattern", "marker",
                "linearGradient", "radialGradient", "filter"}
STYLE_PROPS = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
               "stroke-miterlimit", "opacity", "fill-opacity", "stroke-opacity")
DEFAULTS = {"fill": "#000000", "stroke": "none", "stroke-width": "1", "stroke-linecap": "butt",
            "stroke-linejoin": "miter", "stroke-miterlimit": "4", "opacity": "1",
            "fill-opacity": "1", "stroke-opacity": "1"}
INHERITED = set(STYLE_PROPS) - {"opacity"}
BAD_SCHEMES = ("javascript:", "vbscript:", "data:text/html", "data:application/")
RASTER_DATA = re.compile(r"^data:image/(png|jpe?g|gif|webp|bmp|avif)", re.I)
URL_FUNC = re.compile(r"url\(\s*['\"]?([^'\")]*)", re.I)
NAMED_COLORS = {"white": "#ffffff", "black": "#000000", "red": "#ff0000", "lime": "#00ff00",
                "blue": "#0000ff", "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0",
                "yellow": "#ffff00", "orange": "#ffa500", "transparent": "none"}
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def ns_of(tag):
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


def norm_color(c):
    if c is None:
        return None
    c = c.strip()
    lc = c.lower()
    if re.fullmatch(r"#[0-9a-f]{3}", lc):
        return "#" + "".join(ch * 2 for ch in lc[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", lc):
        return lc
    if lc == "currentcolor":
        return "currentColor"
    return NAMED_COLORS.get(lc, lc)


def fmt_num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


def parse_style_attr(value):
    out = {}
    for decl in (value or "").split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def check_url_value(value, where, errors, warnings, allow_raster):
    """Check an href/src value."""
    v = value.strip()
    lv = v.lower().replace("\t", "").replace("\n", "").replace(" ", "")
    if not v or v.startswith("#"):
        return
    if lv.startswith(BAD_SCHEMES):
        errors.append(f"executable/active URL in {where}: {v[:40]!r}")
    elif lv.startswith("data:image/svg+xml"):
        errors.append(f"nested SVG data URI in {where} (cannot be checked; inline it instead)")
    elif RASTER_DATA.match(lv):
        if not allow_raster:
            errors.append(f"embedded raster data URI in {where} (use --allow-raster if intended)")
    else:
        errors.append(f"external reference in {where}: {v[:60]!r}")


def check_css(text, where, errors):
    low = text.lower()
    if "@import" in low:
        errors.append(f"@import in {where}")
    if "expression(" in low or "javascript:" in low or "behavior:" in low:
        errors.append(f"script-like CSS in {where}")
    for target in URL_FUNC.findall(text):
        if target.strip() and not target.strip().startswith("#"):
            errors.append(f"external url() in {where}: {target.strip()[:60]!r}")


def expand_paths(items):
    files = []
    for item in items:
        if os.path.isdir(item):
            files.extend(sorted(glob.glob(os.path.join(item, "*.svg"))))
        elif any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item, recursive=True)))
        else:
            files.append(item)
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def collect_style(root):
    """Effective presentation values of rendered shapes (CSS classes are not resolved)."""
    stats = {k: Counter() for k in ("stroke", "stroke-width", "fill", "stroke-linecap",
                                    "stroke-linejoin", "stroke-miterlimit")}
    flags = Counter()

    def walk(el, inherited):
        name = local(el.tag)
        if name in NON_RENDERED:
            return
        style = {k: v for k, v in inherited.items() if k in INHERITED}
        style["opacity"] = "1"
        for p in STYLE_PROPS:
            if el.get(p) is not None:
                style[p] = el.get(p).strip()
        style.update({k: v for k, v in parse_style_attr(el.get("style")).items() if k in STYLE_PROPS})
        if el.get("class"):
            flags["class"] += 1
        for p in ("opacity", "fill-opacity", "stroke-opacity"):
            try:
                if float(style.get(p, "1")) != 1.0:
                    flags[p] += 1
            except ValueError:
                pass
        if name in SHAPES:
            stroke = norm_color(style.get("stroke"))
            fill = norm_color(style.get("fill"))
            if fill not in (None, "none"):
                stats["fill"][fill] += 1
            if stroke not in (None, "none"):
                stats["stroke"][stroke] += 1
                stats["stroke-width"][fmt_num(style.get("stroke-width", "1"))] += 1
                stats["stroke-linecap"][style.get("stroke-linecap", "butt")] += 1
                stats["stroke-linejoin"][style.get("stroke-linejoin", "miter")] += 1
                stats["stroke-miterlimit"][fmt_num(style.get("stroke-miterlimit", "4"))] += 1
        for ch in el:
            if isinstance(ch.tag, str):
                walk(ch, style)

    walk(root, dict(DEFAULTS))
    return {k: dict(v.most_common()) for k, v in stats.items()}, dict(flags)


def check(path, max_bytes=10_000, require_title=False, allow_raster=False):
    errors, warnings = [], []
    info = {"file": path}
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return [f"cannot read: {exc}"], warnings, info
    info["bytes"] = len(raw)
    if len(raw) > max_bytes:
        warnings.append(f"size {len(raw)} B > {max_bytes} B (optimise after approval)")
    if re.search(rb"<!DOCTYPE|<!ENTITY", raw, re.I):
        errors.append("DOCTYPE/ENTITY declarations are not allowed (XXE / entity expansion risk)")
        return errors, warnings, info
    if re.search(rb"<\?xml-stylesheet", raw, re.I):
        errors.append("<?xml-stylesheet?> processing instruction loads external CSS")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        errors.append(f"not well-formed XML: {exc}")
        return errors, warnings, info

    if root.tag != f"{{{SVG_NS}}}svg":
        errors.append("root element is not <svg> in the SVG namespace (missing xmlns?)")
    vb = root.get("viewBox")
    info["viewBox"] = vb
    info["width"], info["height"] = root.get("width"), root.get("height")
    nums = re.findall(NUM, vb or "")
    if not vb or len(nums) != 4 or len(re.split(r"[\s,]+", vb.strip())) != 4:
        errors.append(f"missing or invalid viewBox: {vb!r}")
    elif float(nums[2]) <= 0 or float(nums[3]) <= 0:
        errors.append(f"viewBox width/height must be > 0: {vb!r}")
    else:
        vw, vh = float(nums[2]), float(nums[3])
        try:
            w = float(re.match(NUM, info["width"] or "").group(0)) if info["width"] else None
            h = float(re.match(NUM, info["height"] or "").group(0)) if info["height"] else None
        except AttributeError:
            w = h = None
        if w and h and abs(w / h - vw / vh) > 0.01 * (vw / vh):
            warnings.append(f"width/height {info['width']}x{info['height']} do not match viewBox aspect {fmt_num(vw)}x{fmt_num(vh)}")
        if not (info["width"] and info["height"]):
            info["note"] = "no width/height: fine inline with CSS size; for <img> without CSS add them"

    first = next((ch for ch in root if isinstance(ch.tag, str)), None)
    has_title = first is not None and local(first.tag) == "title"
    info["title"] = (first.text or "").strip() if has_title else None
    if require_title and not has_title:
        errors.append("no <title> as first child of <svg> (required with --require-title)")

    elements = Counter()
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        name, ns = local(el.tag), ns_of(el.tag)
        elements[name] += 1
        if name in FORBIDDEN:
            errors.append(f"forbidden element <{name}>")
        elif ns and ns != SVG_NS:
            if ns.startswith(EDITOR_NS):
                warnings.append(f"editor element <{name}> ({ns}): remove or run SVGO")
            else:
                warnings.append(f"non-SVG element <{name}> in namespace {ns}")
        if name == "image":
            if allow_raster:
                warnings.append("<image> raster content does not scale with the vector drawing")
            else:
                errors.append("<image> element: raster content in an icon (use --allow-raster if intended)")
        if name == "text":
            warnings.append("<text> found: font-dependent; convert to paths before delivery")
        if name == "metadata":
            warnings.append("editor metadata <metadata>: run SVGO")
        if name == "a":
            warnings.append("<a> link inside the SVG: unusual for an icon")
        if name == "style":
            check_css(el.text or "", "<style>", errors)
            warnings.append("<style> element: rules leak into the page when inlined; prefer attributes")
        if name in ANIMATION:
            target = (el.get("attributeName") or "").lower()
            if target in ("href", "xlink:href") or target.startswith("on"):
                errors.append(f"<{name}> animates {target!r}")
            for a in ("to", "from", "values", "by"):
                if el.get(a) and el.get(a).strip().lower().replace(" ", "").startswith(BAD_SCHEMES):
                    errors.append(f"<{name}> {a}= sets an executable URL")
            warnings.append(f"animation element <{name}>")
        for attr, value in el.attrib.items():
            a = local(attr).lower()
            ans = ns_of(attr)
            if a.startswith("on"):
                errors.append(f"event handler attribute {a} on <{name}>")
            elif a in ("href", "src") or attr == f"{{{XLINK_NS}}}href":
                check_url_value(value, f"{a} on <{name}>", errors, warnings, allow_raster)
            elif a == "style":
                check_css(value, f"style on <{name}>", errors)
            elif a == "base" and ans == "http://www.w3.org/XML/1998/namespace":
                warnings.append("xml:base changes how URLs resolve")
            elif "url(" in value.lower():
                check_css(value, f"{a} on <{name}>", errors)
            if ans.startswith(EDITOR_NS):
                warnings.append(f"editor attribute {a} on <{name}>: run SVGO")

    info["elements"] = dict(elements.most_common())
    style, flags = collect_style(root)
    info["style"] = style
    info["features"] = {
        "transform": sum(1 for el in root.iter() if isinstance(el.tag, str) and el.get("transform")),
        "gradient": elements.get("linearGradient", 0) + elements.get("radialGradient", 0),
        "clipPath": elements.get("clipPath", 0), "mask": elements.get("mask", 0),
        "filter": elements.get("filter", 0), "use": elements.get("use", 0),
        **flags,
    }
    if flags.get("class") or elements.get("style"):
        info["note"] = (info.get("note", "") + "; " if info.get("note") else "") + \
            "CSS classes/<style> are not resolved in the colour/width report"
    # de-duplicate repeated warnings while keeping order
    warnings = list(dict.fromkeys(warnings))
    errors = list(dict.fromkeys(errors))
    return errors, warnings, info


def fmt_counter(d):
    return ", ".join(f"{k}×{v}" for k, v in d.items()) if d else "-"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--max-bytes", type=int, default=10_000)
    ap.add_argument("--require-title", action="store_true")
    ap.add_argument("--allow-raster", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)
    files = expand_paths(args.paths)
    if not files:
        print("no SVG files found", file=sys.stderr)
        return 2
    failed = False
    results = []
    for f in files:
        errors, warnings, info = check(f, args.max_bytes, args.require_title, args.allow_raster)
        failed |= bool(errors)
        results.append({"file": f, "status": "FAIL" if errors else "ok", "errors": errors,
                        "warnings": warnings, "info": info})
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 1 if failed else 0
    for r in results:
        if args.quiet and not (r["errors"] or r["warnings"]):
            continue
        info = r["info"]
        size = f"{info.get('bytes', 0) / 1024:.1f} KB" if "bytes" in info else ""
        wh = f" width={info.get('width')} height={info.get('height')}" if info.get("width") or info.get("height") else ""
        print(f"{r['status']:4} {r['file']}  {size}  viewBox={info.get('viewBox')}{wh}")
        if "style" in info:
            st = info["style"]
            print(f"     elements: {fmt_counter(info['elements'])}")
            print(f"     stroke: {fmt_counter(st['stroke'])} | width: {fmt_counter(st['stroke-width'])}"
                  f" | cap: {fmt_counter(st['stroke-linecap'])} | join: {fmt_counter(st['stroke-linejoin'])}"
                  f" | miterlimit: {fmt_counter(st['stroke-miterlimit'])}")
            print(f"     fill: {fmt_counter(st['fill'])}")
            feats = {k: v for k, v in info["features"].items() if v}
            if feats:
                print(f"     features: {fmt_counter(feats)}")
            if info.get("title"):
                print(f"     title: {info['title']}")
            if info.get("note"):
                print(f"     note: {info['note']}")
        for e in r["errors"]:
            print(f"     error: {e}")
        for w in r["warnings"]:
            print(f"     warn:  {w}")
    n_fail = sum(1 for r in results if r["errors"])
    n_warn = sum(1 for r in results if r["warnings"] and not r["errors"])
    print(f"{len(results)} file(s): {n_fail} with errors, {n_warn} with warnings only")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
