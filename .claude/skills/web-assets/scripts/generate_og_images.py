#!/usr/bin/env python3
"""
Generate Open Graph / Twitter (X) share images: PNG + WebP, optional JPEG.

Vendored from alonw0/web-asset-generator (MIT, commit c6d56dc) and modified
for НОВАПРОМ — see NOTICE.md. Python 3.10+, stdlib + Pillow only, no network.

Modes:
  --text  "Фильтры-сепараторы газа"   text on a brand background (Cyrillic font required)
  --image logo.png                   logo/photo "contained" on a brand background

Outputs: og-image (1200x630), twitter-image (1200x675), og-square (1200x1200)
as .png and .webp, plus .jpg with --jpeg. Always flattened to RGB.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (LANCZOS, Image, ImageDraw, ImageFont, ImageOps,  # noqa: E402
                        contain_on_canvas, die, find_font, is_absolute_url, load_image,
                        parse_color, require_opaque, require_webp, setup_console, trim_transparent,
                        url_prefix, warn)
from lib import validators  # noqa: E402

OG_SIZES = {
    "og-image": (1200, 630),       # Facebook, VK, Telegram, WhatsApp, LinkedIn
    "twitter-image": (1200, 675),  # X/Twitter summary_large_image (16:9)
    "og-square": (1200, 1200),     # square previews
}
PLATFORMS = {
    "all": list(OG_SIZES),
    "facebook": ["og-image"],
    "twitter": ["twitter-image"],
    "square": ["og-square"],
}
MIN_FONT = 36
LINE_SPACING = 1.15


def calculate_font_size(text: str, base_size: int = 120) -> int:
    """Starting font size by text length (upstream logic); shrunk later to fit."""
    n = len(text)
    if n <= 20:
        return int(base_size * 1.2)
    if n <= 40:
        return base_size
    if n <= 60:
        return int(base_size * 0.85)
    return int(base_size * 0.7)


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            trial = f"{current} {word}".strip()
            if current and draw.textlength(trial, font=font) > max_width:
                lines.append(current)
                current = word
            else:
                current = trial
        lines.append(current)
    return lines


def fit_text(draw, text: str, font_path: str, max_w: int, max_h: int, start: int):
    """Largest font size (<= start) at which the wrapped text fits the box."""
    size = start
    while True:
        font = ImageFont.truetype(font_path, size)
        lines = wrap_lines(draw, text, font, max_w)
        ascent, descent = font.getmetrics()
        line_h = int((ascent + descent) * LINE_SPACING)
        block_h = (len(lines) - 1) * line_h + ascent + descent
        widest = max(draw.textlength(line, font=font) for line in lines)
        if widest <= max_w and block_h <= max_h:
            return font, lines, line_h, block_h
        if size <= MIN_FONT:
            warn("текст слишком длинный и не помещается — сократите его",
                 "text is too long to fit; shorten it")
            return font, lines, line_h, block_h
        size = max(MIN_FONT, int(size * 0.9))


def text_image(text: str, size: tuple[int, int], font_path: str, bg, fg, accent,
               logo: Image.Image | None) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, bg[:3])
    draw = ImageDraw.Draw(img)
    margin_x, top, bottom = int(w * 0.08), int(h * 0.12), h - int(h * 0.12)
    if accent:
        bar = max(8, int(h * 0.025))
        draw.rectangle([0, h - bar, w, h], fill=accent[:3])
    if logo is not None:
        fitted = ImageOps.contain(logo, (int(w * 0.5), int(h * 0.18)), LANCZOS)
        img.paste(fitted, ((w - fitted.width) // 2, top), fitted)
        top += fitted.height + int(h * 0.06)
    start = calculate_font_size(text, 120 if w >= 1200 else 90)
    font, lines, line_h, block_h = fit_text(draw, text, font_path, w - 2 * margin_x,
                                            bottom - top, start)
    y = top + (bottom - top - block_h) // 2
    for line in lines:
        draw.text((w // 2, y), line, font=font, fill=fg[:3], anchor="ma")
        y += line_h
    return img


def picture_image(src: Image.Image, size: tuple[int, int], bg, fit: str,
                  padding: float) -> Image.Image:
    if fit == "cover":  # fills the frame, crops edges: photos only, never logos
        canvas = Image.new("RGBA", size, bg)
        canvas.alpha_composite(ImageOps.fit(src, size, LANCZOS))
        return canvas.convert("RGB")
    box = (size[0] * (1 - 2 * padding), size[1] * (1 - 2 * padding))
    return contain_on_canvas(src, size, box, bg).convert("RGB")


def meta_tags(prefix: str, names: list[str], ext: str, args, title: str | None,
              alt: str) -> str:
    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    mime = {"png": "image/png", "jpg": "image/jpeg"}[ext]
    main = "og-image" if "og-image" in names else names[0]
    tw = "twitter-image" if "twitter-image" in names else main
    w, h = OG_SIZES[main]
    tags = ['<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{esc(args.site_name)}">',
            '<meta property="og:locale" content="ru_RU">']
    if title:
        tags.append(f'<meta property="og:title" content="{esc(title)}">')
    if args.description:
        tags.append(f'<meta property="og:description" content="{esc(args.description)}">')
    if args.page_url:
        tags.append(f'<meta property="og:url" content="{esc(args.page_url)}">')
    tags += [f'<meta property="og:image" content="{prefix}{main}.{ext}">',
             f'<meta property="og:image:type" content="{mime}">',
             f'<meta property="og:image:width" content="{w}">',
             f'<meta property="og:image:height" content="{h}">',
             f'<meta property="og:image:alt" content="{esc(alt)}">',
             '<meta name="twitter:card" content="'
             + ("summary" if main == "og-square" else "summary_large_image") + '">',
             f'<meta name="twitter:image" content="{prefix}{tw}.{ext}">',
             f'<meta name="twitter:image:alt" content="{esc(alt)}">']
    return "\n".join(tags)


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(
        description="Open Graph / Twitter share images (PNG + WebP, optional JPEG).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n'
               '  python generate_og_images.py out/og --text "Фильтры-сепараторы газа" '
               '--logo logo-white.png --accent "#FDB913"\n'
               '  python generate_og_images.py out/og --image logo.png --bg "#FFFFFF" --jpeg\n')
    p.add_argument("output_dir", help="output directory (created if missing)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="headline drawn on the image (Russian is fine)")
    src.add_argument("--image", help="logo or photo placed on the background")
    p.add_argument("--logo", help="logo above the text (text mode); use a light logo on a dark --bg")
    p.add_argument("--bg", default="#1C1C1C", help="background colour (default: #1C1C1C; or #FFFFFF)")
    p.add_argument("--text-color", default="#FFFFFF", help="text colour (default: #FFFFFF)")
    p.add_argument("--accent", help="optional bottom stripe colour, e.g. #FDB913")
    p.add_argument("--font", help="TrueType font with Cyrillic, e.g. Raleway-Bold.ttf "
                                  "(default: Arial/Segoe UI on Windows, DejaVu/Liberation on Linux)")
    p.add_argument("--fit", choices=["contain", "cover"], default="contain",
                   help="image mode: contain = whole logo visible (default); cover = crop, photos only")
    p.add_argument("--padding", type=float, default=0.10,
                   help="image mode margin per side, fraction 0..0.3 (default: 0.10)")
    p.add_argument("--platforms", choices=list(PLATFORMS), default="all")
    p.add_argument("--jpeg", action="store_true",
                   help="also write .jpg (smaller; the printed tags then point to .jpg)")
    p.add_argument("--base-url", default="/",
                   help="absolute URL folder of the images, e.g. https://novaprom.ru/assets/og/")
    p.add_argument("--title", help="og:title (default: --text)")
    p.add_argument("--description", help="og:description")
    p.add_argument("--page-url", help="og:url of the page")
    p.add_argument("--alt", help="og:image:alt (default: title)")
    p.add_argument("--site-name", default="НОВАПРОМ", help="og:site_name (default: НОВАПРОМ)")
    p.add_argument("--validate", action="store_true", help="check the written files afterwards")
    args = p.parse_args()

    require_webp()
    bg = parse_color(args.bg, "--bg")
    require_opaque(bg, "--bg")
    fg = parse_color(args.text_color, "--text-color")
    accent = parse_color(args.accent, "--accent") if args.accent else None
    if not 0 <= args.padding <= 0.3:
        die("--padding должен быть от 0 до 0.3", "--padding must be between 0 and 0.3")
    prefix = url_prefix(args.base_url)

    font_path = None
    logo = trim_transparent(load_image(args.logo)) if args.logo else None
    picture = trim_transparent(load_image(args.image)) if args.image else None
    if args.text is not None:
        if not args.text.strip():
            die("--text пустой", "--text is empty")
        font_path = find_font(args.font, args.text)
        print(f"Font: {font_path}")

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = PLATFORMS[args.platforms]
    for name in names:
        size = OG_SIZES[name]
        if args.text is not None:
            img = text_image(args.text, size, font_path, bg, fg, accent, logo)
        else:
            img = picture_image(picture, size, bg, args.fit, args.padding)
        img.save(out / f"{name}.png", "PNG", optimize=True)
        img.save(out / f"{name}.webp", "WEBP", quality=85, method=6)
        formats = "png, webp"
        if args.jpeg:
            img.save(out / f"{name}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
            formats += ", jpg"
        print(f"[OK] {name} {size[0]}x{size[1]} ({formats})")

    ok = True
    if args.validate:
        print("\nValidation / Проверка:")
        ok = validators.print_directory_report(validators.check_directory(out))
        if args.text is not None:
            result = validators.validate_contrast(fg[:3], bg[:3], font_size=MIN_FONT, is_bold=True)
            print(f"  text contrast: {result}")
            ok = ok and result.passed

    print(f"\nWritten to {out}. Nothing was uploaded or published.")
    print("Файлы не загружены на сайт. Размещать только после подтверждения пользователя.")
    if not is_absolute_url(prefix):
        warn("og:image должен быть абсолютным URL — задайте --base-url https://novaprom.ru/…/",
             "og:image must be an absolute URL; pass --base-url https://novaprom.ru/.../")
    title = args.title or args.text
    alt = args.alt or title or args.site_name
    print("\nHTML meta tags for <head>:\n")
    print(meta_tags(prefix, names, "jpg" if args.jpeg else "png", args, title, alt))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
