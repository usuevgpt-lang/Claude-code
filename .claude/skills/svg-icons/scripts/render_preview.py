#!/usr/bin/env python3
"""render_preview.py - render SVG to PNG at real pixel sizes and build comparison contact sheets.

Backends (picked in this order with --backend auto):
  1. resvg CLI   (found with shutil.which; most accurate; Apache-2.0/MIT)
  2. CairoSVG    (Python package, imported in-process with unsafe=False; LGPL-3.0+)
Contact sheets and WebP output need Pillow.

Usage:
  render_preview.py backends
  render_preview.py render FILE... --sizes 106 239 [--out-dir DIR] [--background none|#RRGGBB]
                    [--dpr 1] [--webp] [--backend auto|resvg|cairosvg]
  render_preview.py sheet FILE... --sizes 106 239 --out sheet.png [--background "#FFFFFF"]
                    [--dpr 1] [--columns 8] [--title TEXT] [--backend ...]

--sizes are display widths in CSS px; the height follows the SVG viewBox aspect. --dpr 2 renders
at 2x pixels (HiDPI screens). FILE may be a glob pattern (expanded here, also on Windows) or a
directory (all *.svg in it). Output files are always new files; inputs are never modified.
"""
import argparse
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

INSTALL_HINTS = """No SVG renderer is available. Install ONE of these (ask the user first):

  resvg (recommended, one static binary, no Python needed)
    Linux:    cargo install resvg --locked
              or download a release binary: https://github.com/linebender/resvg/releases
    Windows:  scoop install resvg          (Scoop "main" bucket)
  CairoSVG (Python package, needs the native Cairo library)
    Linux:    sudo apt install libcairo2   then
              python3 -m venv .venv && .venv/bin/pip install "cairosvg>=2.7"
    Windows:  py -3 -m venv .venv; .\\.venv\\Scripts\\pip install "cairosvg>=2.7"
              (also needs Cairo DLLs, e.g. from the GTK3 runtime or MSYS2; resvg is simpler)

Then re-run this script with the same arguments (with the venv's python for CairoSVG)."""

PILLOW_HINT = """Pillow is required for contact sheets and WebP output (ask the user first):
    Linux:    python3 -m venv .venv && .venv/bin/pip install "Pillow>=12,<13"
    Windows:  py -3 -m venv .venv; .\\.venv\\Scripts\\pip install "Pillow>=12,<13"
For WebP without Pillow: cwebp -lossless in.png -o out.webp  (Linux: sudo apt install webp;
Windows: scoop install libwebp)."""


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def expand_paths(items):
    files = []
    for item in items:
        if os.path.isdir(item):
            files.extend(sorted(glob.glob(os.path.join(item, "*.svg"))))
        elif any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item, recursive=True)))
        else:
            files.append(item)
    out = []
    for f in files:
        if f not in out:
            out.append(f)
    return out


def svg_aspect(path):
    """Return width/height of the SVG canvas from viewBox (or width/height attributes)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if re.search(rb"<!DOCTYPE|<!ENTITY", raw, re.I):
        die(f"{path}: DOCTYPE/ENTITY found - refusing to render (run check_svg.py)")
    root = ET.fromstring(raw)
    vb = re.findall(NUM, root.get("viewBox") or "")
    if len(vb) == 4 and float(vb[2]) > 0 and float(vb[3]) > 0:
        return float(vb[2]) / float(vb[3]), raw
    w = re.findall(NUM, root.get("width") or "")
    h = re.findall(NUM, root.get("height") or "")
    if w and h and float(h[0]) > 0:
        return float(w[0]) / float(h[0]), raw
    die(f"{path}: no usable viewBox or width/height")


def pick_backend(name):
    resvg = shutil.which("resvg")
    try:
        import cairosvg  # noqa: F401
        have_cairo = True
    except Exception:  # ImportError or OSError when the native Cairo library is missing
        have_cairo = False
    if name in ("auto", "resvg") and resvg:
        return ("resvg", resvg)
    if name in ("auto", "cairosvg") and have_cairo:
        return ("cairosvg", None)
    if name != "auto":
        die(f"backend {name!r} is not available.\n\n" + INSTALL_HINTS)
    die(INSTALL_HINTS)


def render_png(backend, path, raw, width, height, background=None):
    """Render to PNG bytes at exactly width x height pixels."""
    kind, exe = backend
    if kind == "resvg":
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.png")
            cmd = [exe, "--width", str(width), "--height", str(height)]
            if background:
                cmd += ["--background", background]
            cmd += [path, out]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                die(f"resvg failed on {path}: {proc.stderr.strip()}", 1)
            with open(out, "rb") as fh:
                return fh.read()
    import cairosvg
    return cairosvg.svg2png(bytestring=raw, output_width=width, output_height=height,
                            background_color=background, unsafe=False)


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def cmd_backends(_args):
    resvg = shutil.which("resvg")
    print(f"resvg:    {resvg or 'not found'}")
    try:
        import cairosvg
        print(f"cairosvg: {getattr(cairosvg, '__version__', 'installed')}")
    except Exception as exc:
        print(f"cairosvg: not available ({exc.__class__.__name__})")
    try:
        import PIL
        print(f"Pillow:   {PIL.__version__}")
    except ImportError:
        print("Pillow:   not installed (needed for 'sheet' and --webp)")
    print(f"cwebp:    {shutil.which('cwebp') or 'not found'}")
    if not resvg:
        try:
            import cairosvg  # noqa: F401,F811
        except Exception:
            print("\n" + INSTALL_HINTS)
    return 0


def cmd_render(args):
    files = expand_paths(args.files)
    if not files:
        die("no SVG files found")
    backend = pick_backend(args.backend)
    if args.webp:
        try:
            from PIL import Image
        except ImportError:
            die(PILLOW_HINT)
    bg = None if args.background in (None, "none", "transparent") else args.background
    for f in files:
        aspect, raw = svg_aspect(f)
        out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(f)), "preview")
        os.makedirs(out_dir, exist_ok=True)
        for size in args.sizes:
            w = int(round(size * args.dpr))
            h = max(1, int(round(w / aspect)))
            suffix = f"-{size}" + (f"@{args.dpr:g}x" if args.dpr != 1 else "")
            out = os.path.join(out_dir, stem(f) + suffix + ".png")
            if os.path.abspath(out) == os.path.abspath(f):
                die("refusing to overwrite the input")
            data = render_png(backend, f, raw, w, h, bg)
            with open(out, "wb") as fh:
                fh.write(data)
            msg = f"{out}  {w}x{h}px  {len(data)} B  ({backend[0]})"
            if args.webp:
                from PIL import Image
                webp = out[:-4] + ".webp"
                Image.open(io.BytesIO(data)).save(webp, "WEBP", lossless=True, method=6)
                msg += f"  + {webp} {os.path.getsize(webp)} B"
            print(msg)
    return 0


def load_font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def cmd_sheet(args):
    files = expand_paths(args.files)
    if not files:
        die("no SVG files found")
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        die(PILLOW_HINT)
    backend = pick_backend(args.backend)
    bg = args.background
    font, font_small = load_font(14), load_font(11)
    pad, label_h, header_h = 12, 30, 24
    max_chars = args.label_chars
    cols = max(1, min(args.columns, len(files)))

    loaded = [(f, *svg_aspect(f)) for f in files]
    bands = []
    for size in args.sizes:
        w = int(round(size * args.dpr))
        tiles = []
        for f, aspect, raw in loaded:
            h = max(1, int(round(w / aspect)))
            png = render_png(backend, f, raw, w, h, None if bg in ("none", "transparent") else bg)
            tiles.append((f, Image.open(io.BytesIO(png)).convert("RGBA")))
        cell_w = max(w, 120)
        cell_h = max(t.size[1] for _, t in tiles)
        rows = (len(tiles) + cols - 1) // cols
        band_w = pad + cols * (cell_w + pad)
        band_h = header_h + rows * (cell_h + label_h + pad)
        bands.append((size, w, tiles, cell_w, cell_h, band_w, band_h))

    title_h = 30 if args.title else 0
    sheet_w = max(b[5] for b in bands) + pad
    sheet_h = title_h + sum(b[6] for b in bands) + pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), "#E4E4E4")
    draw = ImageDraw.Draw(sheet)
    y = pad
    if args.title:
        draw.text((pad, y), args.title, fill="#1C1C1C", font=font)
        y += title_h
    for size, w, tiles, cell_w, cell_h, _bw, band_h in bands:
        dpr = f" @ {args.dpr:g}x = {w} device px" if args.dpr != 1 else ""
        draw.text((pad, y), f"{size} px wide{dpr}", fill="#1C1C1C", font=font)
        y0 = y + header_h
        for i, (f, im) in enumerate(tiles):
            r, c = divmod(i, cols)
            x = pad + c * (cell_w + pad)
            yy = y0 + r * (cell_h + label_h + pad)
            cell = Image.new("RGBA", (cell_w, cell_h), bg if bg not in ("none", "transparent") else "#FFFFFF")
            cell.alpha_composite(im, ((cell_w - im.size[0]) // 2, (cell_h - im.size[1]) // 2))
            sheet.alpha_composite(cell, (x, yy))
            name = stem(f)
            if len(name) > max_chars:
                name = name[: max_chars - 2] + ".."
            while len(name) > 3 and draw.textlength(name, font=font_small) > cell_w:
                name = name[:-3] + ".."
            draw.text((x, yy + cell_h + 3), name, fill="#333333", font=font_small)
            draw.text((x, yy + cell_h + 16), f"{im.size[0]}x{im.size[1]}px", fill="#777777", font=font_small)
        y += band_h
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    if os.path.abspath(args.out) in {os.path.abspath(f) for f in files}:
        die("refusing to overwrite an input")
    sheet.convert("RGB").save(args.out)
    print(f"{args.out}  {sheet_w}x{sheet_h}px  {len(files)} SVG x {len(args.sizes)} size(s)  ({backend[0]})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backends", help="show available renderers and install hints")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("files", nargs="+")
    common.add_argument("--sizes", nargs="+", type=int, required=True, help="display widths in CSS px")
    common.add_argument("--dpr", type=float, default=1.0, help="device pixel ratio (2 = HiDPI)")
    common.add_argument("--backend", choices=["auto", "resvg", "cairosvg"], default="auto")
    r = sub.add_parser("render", parents=[common], help="SVG -> PNG (and optional WebP) per size")
    r.add_argument("--out-dir", help="default: <svg folder>/preview")
    r.add_argument("--background", default="none", help="none (transparent) or a colour such as #FFFFFF")
    r.add_argument("--webp", action="store_true", help="also write lossless WebP (Pillow)")
    s = sub.add_parser("sheet", parents=[common], help="contact sheet: all SVGs side by side per size")
    s.add_argument("--out", required=True)
    s.add_argument("--background", default="#FFFFFF", help="cell background, e.g. #1C1C1C for dark UI")
    s.add_argument("--columns", type=int, default=8)
    s.add_argument("--title")
    s.add_argument("--label-chars", type=int, default=30)
    args = ap.parse_args(argv)
    if args.cmd == "backends":
        return cmd_backends(args)
    if any(sz <= 0 for sz in args.sizes) or args.dpr <= 0:
        die("sizes and --dpr must be positive")
    return cmd_render(args) if args.cmd == "render" else cmd_sheet(args)


if __name__ == "__main__":
    sys.exit(main())
