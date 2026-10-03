#!/usr/bin/env python3
"""
Generate favicons, app icons and site.webmanifest from a logo.

Vendored from alonw0/web-asset-generator (MIT, commit c6d56dc) and modified
for НОВАПРОМ — see NOTICE.md. Python 3.10+, stdlib + Pillow only, no network.
SVG input is rasterised only by a locally installed `resvg` CLI.

Outputs (icon_type "all"):
  favicon.ico (16/32/48), favicon-16x16.png, favicon-32x32.png, favicon-96x96.png,
  apple-touch-icon.png (180, opaque), android-chrome-192x192.png,
  android-chrome-512x512.png, maskable-icon-512x512.png (opaque, safe zone),
  site.webmanifest, icon.svg (copy of the SVG, if one is given).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (Image, contain_on_canvas, die, load_image, parse_color,  # noqa: E402
                        require_opaque, setup_console, to_hex, trim_transparent, url_prefix,
                        warn)
from lib import validators  # noqa: E402

FAVICON_PNG = {"favicon-16x16.png": 16, "favicon-32x32.png": 32, "favicon-96x96.png": 96}
ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
ICO_BASE = 256                      # ICO frames are downscaled from this square
APPLE_ICON, APPLE_SIZE, APPLE_PADDING = "apple-touch-icon.png", 180, 0.10
ANDROID_ICONS = {"android-chrome-192x192.png": 192, "android-chrome-512x512.png": 512}
MASKABLE_ICON, MASKABLE_SIZE = "maskable-icon-512x512.png", 512
MASKABLE_SAFE_DIAMETER = 0.80       # W3C: content must fit a centred circle, radius 40%
SVG_RASTER_WIDTH = 1024
MIN_SOURCE_SIDE = 512


# --- SVG -------------------------------------------------------------------

def check_svg(svg: Path) -> None:
    try:
        text = svg.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        die(f"не удалось прочитать {svg}: {exc}", f"cannot read {svg}: {exc}")
    low = text.lower()
    if "<svg" not in low:
        die(f"{svg} не похож на SVG", f"{svg} does not look like an SVG file")
    if "<script" in low or "javascript:" in low:
        warn(f"{svg.name} содержит скрипты — уберите их перед публикацией",
             f"{svg.name} contains scripts; remove them before publishing")
    if re.search(r"""(href|src)\s*=\s*["']https?://""", low):
        warn(f"{svg.name} ссылается на внешние ресурсы", f"{svg.name} references external resources")


def rasterise_svg(svg: Path) -> Image.Image:
    resvg = shutil.which("resvg")
    if not resvg:
        die("Pillow не читает SVG, а утилита resvg не найдена в PATH. Передайте PNG-исходник "
            f"(не меньше {MIN_SOURCE_SIDE} px), а SVG — через --svg (будет скопирован как icon.svg).",
            "Pillow cannot read SVG and the resvg CLI is not in PATH. Pass a PNG source "
            f"(>= {MIN_SOURCE_SIDE} px) and give the SVG with --svg (copied as icon.svg).")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "source.png"
        try:
            subprocess.run([resvg, "-w", str(SVG_RASTER_WIDTH), str(svg), str(out)],
                           check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            detail = getattr(exc, "stderr", b"") or b""
            die(f"resvg не смог растеризовать {svg}: {exc} {detail.decode(errors='replace')}",
                f"resvg failed to rasterise {svg}: {exc}")
        return load_image(str(out))


# --- icons -----------------------------------------------------------------

def square_icon(src: Image.Image, size: int, bg, padding: float) -> Image.Image:
    """Logo contained (not stretched) and centred on a size x size canvas."""
    inner = round(size * (1 - 2 * padding))
    icon = contain_on_canvas(src, (size, size), (inner, inner), bg)
    return icon.convert("RGB") if bg[3] == 255 else icon


def maskable_icon(src: Image.Image, size: int, bg) -> Image.Image:
    """Scale so the logo's diagonal fits the 80% safe circle; opaque background."""
    scale = MASKABLE_SAFE_DIAMETER * size / math.hypot(*src.size)
    box = (src.width * scale, src.height * scale)
    return contain_on_canvas(src, (size, size), box, bg).convert("RGB")


def generate_icons(src: Image.Image, out: Path, icon_type: str, bg, app_bg,
                   padding: float) -> list[str]:
    written: list[str] = []

    def save(img: Image.Image, name: str) -> None:
        img.save(out / name, "PNG", optimize=True)
        written.append(name)
        print(f"[OK] {name} ({img.width}x{img.height})")

    if icon_type in ("favicon", "all"):
        for name, size in FAVICON_PNG.items():
            save(square_icon(src, size, bg, padding), name)
        base = square_icon(src, ICO_BASE, bg, padding)
        base.save(out / "favicon.ico", format="ICO", sizes=ICO_SIZES)
        written.append("favicon.ico")
        print("[OK] favicon.ico (16x16, 32x32, 48x48)")

    if icon_type in ("app", "all"):
        save(square_icon(src, APPLE_SIZE, app_bg, max(padding, APPLE_PADDING)), APPLE_ICON)
        for name, size in ANDROID_ICONS.items():
            save(square_icon(src, size, bg, padding), name)
        save(maskable_icon(src, MASKABLE_SIZE, app_bg), MASKABLE_ICON)
    return written


def write_manifest(out: Path, args, theme: str, background: str) -> None:
    icons = [{"src": name, "sizes": f"{size}x{size}", "type": "image/png"}
             for name, size in ANDROID_ICONS.items()]
    icons.append({"src": MASKABLE_ICON, "sizes": f"{MASKABLE_SIZE}x{MASKABLE_SIZE}",
                  "type": "image/png", "purpose": "maskable"})
    manifest = {
        "name": args.name,
        "short_name": args.short_name or args.name,
        "lang": args.lang,
        "start_url": args.start_url,
        "display": args.display,
        "theme_color": theme,
        "background_color": background,
        "icons": icons,
    }
    if len(manifest["short_name"]) > 12:
        warn("short_name длиннее 12 символов — может обрезаться", "short_name > 12 chars may be truncated")
    (out / "site.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[OK] site.webmanifest")


def html_tags(prefix: str, written: list[str], theme: str) -> str:
    def u(name: str) -> str:
        return prefix + name

    tags = []
    if "favicon.ico" in written:
        tags.append(f'<link rel="icon" href="{u("favicon.ico")}" sizes="32x32">')
        if "icon.svg" in written:
            tags.append(f'<link rel="icon" href="{u("icon.svg")}" type="image/svg+xml">')
        else:
            for name, size in FAVICON_PNG.items():
                tags.append(f'<link rel="icon" type="image/png" sizes="{size}x{size}" href="{u(name)}">')
    if APPLE_ICON in written:
        tags.append(f'<link rel="apple-touch-icon" sizes="180x180" href="{u(APPLE_ICON)}">')
    if "site.webmanifest" in written:
        tags.append(f'<link rel="manifest" href="{u("site.webmanifest")}">')
        tags.append(f'<meta name="theme-color" content="{theme}">')
    return "\n".join(tags)


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(
        description="Favicons, app icons and site.webmanifest from a logo (PNG/JPEG/WebP or SVG).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python generate_favicons.py logo-mark.png out/icons all "
               "--svg logo-mark.svg --base-url /assets/favicon/ --validate")
    p.add_argument("source", help=f"logo image, >= {MIN_SOURCE_SIDE} px; SVG needs the resvg CLI")
    p.add_argument("output_dir", help="output directory (created if missing)")
    p.add_argument("icon_type", nargs="?", default="all", choices=["favicon", "app", "all"])
    p.add_argument("--bg", default="transparent",
                   help="background of favicons and android-chrome icons (default: transparent)")
    p.add_argument("--app-bg", default="#FFFFFF",
                   help="opaque background of apple-touch-icon and maskable icon (default: #FFFFFF)")
    p.add_argument("--padding", type=float, default=0.0,
                   help="empty margin on each side as a fraction of the icon, 0..0.3 (default: 0); "
                        "transparent borders of the source are trimmed first")
    p.add_argument("--svg", help="SVG version of the logo to copy as icon.svg (as-is)")
    p.add_argument("--name", default="НОВАПРОМ", help="manifest name (default: НОВАПРОМ)")
    p.add_argument("--short-name", help="manifest short_name (default: --name)")
    p.add_argument("--theme-color", default="#1C1C1C", help="theme_color (default: #1C1C1C)")
    p.add_argument("--background-color", help="manifest background_color (default: --app-bg)")
    p.add_argument("--lang", default="ru", help="manifest lang (default: ru)")
    p.add_argument("--start-url", default="/", help="manifest start_url (default: /)")
    p.add_argument("--display", default="browser",
                   choices=["browser", "minimal-ui", "standalone", "fullscreen"])
    p.add_argument("--no-manifest", action="store_true", help="do not write site.webmanifest")
    p.add_argument("--base-url", default="/",
                   help="URL folder where the files will live: /assets/favicon/, "
                        "https://novaprom.ru/assets/favicon/ or [[++site_url]]assets/favicon/")
    p.add_argument("--validate", action="store_true", help="check the written files afterwards")
    args = p.parse_args()

    if not 0 <= args.padding <= 0.3:
        die("--padding должен быть от 0 до 0.3", "--padding must be between 0 and 0.3")
    bg = parse_color(args.bg, "--bg")
    app_bg = parse_color(args.app_bg, "--app-bg")
    require_opaque(app_bg, "--app-bg")
    theme = parse_color(args.theme_color, "--theme-color")
    background = parse_color(args.background_color, "--background-color") if args.background_color else app_bg
    require_opaque(theme, "--theme-color")
    require_opaque(background, "--background-color")
    prefix = url_prefix(args.base_url)

    source = Path(args.source)
    if not source.is_file():
        die(f"файл не найден: {source}", f"file not found: {source}")
    svg = Path(args.svg) if args.svg else None
    if source.suffix.lower() == ".svg":
        check_svg(source)
        src_img = rasterise_svg(source)
        svg = svg or source
    else:
        src_img = load_image(str(source))
    src_img = trim_transparent(src_img)
    if svg:
        if not svg.is_file():
            die(f"файл не найден: {svg}", f"file not found: {svg}")
        check_svg(svg)
    if max(src_img.size) < MIN_SOURCE_SIDE:
        warn(f"исходник {src_img.width}x{src_img.height} меньше {MIN_SOURCE_SIDE} px — крупные иконки будут размытыми",
             f"source is smaller than {MIN_SOURCE_SIDE} px; large icons will be blurry")
    ratio = src_img.width / src_img.height
    if not 0.8 <= ratio <= 1.25:
        warn(f"логотип не квадратный ({ratio:.2f}:1) — он вписан без растяжения, но в 16x16 будет мелким; "
             "для favicon лучше квадратный знак без надписи",
             "non-square logo is contained (not stretched) but will be tiny at 16x16; "
             "a square mark works better for favicons")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Source: {source} ({src_img.width}x{src_img.height}) -> {out}")
    written = generate_icons(src_img, out, args.icon_type, bg, app_bg, args.padding)
    if svg and args.icon_type in ("favicon", "all"):
        shutil.copyfile(svg, out / "icon.svg")
        written.append("icon.svg")
        print("[OK] icon.svg (copied as-is)")
    if args.icon_type in ("app", "all") and not args.no_manifest:
        write_manifest(out, args, to_hex(theme), to_hex(background))
        written.append("site.webmanifest")

    ok = True
    if args.validate:
        print("\nValidation / Проверка:")
        ok = validators.print_directory_report(validators.check_directory(out))

    print(f"\nWritten {len(written)} files to {out}. Nothing was uploaded or published.")
    print("Файлы не загружены на сайт. Размещать только после подтверждения пользователя.")
    if "site.webmanifest" in written:
        print("site.webmanifest must sit in the same folder as the android-chrome/maskable icons.")
    print("\nHTML tags for <head>:\n")
    print(html_tags(prefix, written, to_hex(theme)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
