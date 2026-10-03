"""Shared helpers for the web-assets scripts.

Local addition (not in upstream). Python 3.10+, stdlib + Pillow only.
No network access anywhere in this package.
"""

from __future__ import annotations

import os
import sys

if sys.version_info < (3, 10):
    sys.exit("Ошибка: нужен Python 3.10+ / Error: Python 3.10+ is required")

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps, features
except ImportError:
    sys.exit(
        "Ошибка: не установлен Pillow. Создайте venv и установите его:\n"
        "  Linux:   python3 -m venv .venv && .venv/bin/python -m pip install \"Pillow>=12,<13\"\n"
        "  Windows: py -3 -m venv .venv; .venv\\Scripts\\python -m pip install \"Pillow>=12,<13\"\n"
        "Error: Pillow is not installed. Create a venv and install it (commands above).\n"
        "Never use --break-system-packages."
    )

RGBA = tuple[int, int, int, int]
TRANSPARENT: RGBA = (0, 0, 0, 0)
LANCZOS = Image.Resampling.LANCZOS


def setup_console() -> None:
    """Print UTF-8 and never crash on characters the console cannot show."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def die(ru: str, en: str, code: int = 1) -> None:
    """Exit with a bilingual error message."""
    print(f"Ошибка: {ru}\nError: {en}", file=sys.stderr)
    sys.exit(code)


def warn(ru: str, en: str) -> None:
    print(f"[WARN] {ru} / {en}", file=sys.stderr)


def parse_color(value: str, name: str = "colour") -> RGBA:
    """Parse '#rgb', '#rrggbb', 'rrggbb', CSS names or 'transparent' into RGBA."""
    v = value.strip()
    if v.lower() in ("transparent", "none"):
        return TRANSPARENT
    if len(v) in (3, 6) and all(c in "0123456789abcdefABCDEF" for c in v):
        v = "#" + v
    try:
        return ImageColor.getcolor(v, "RGBA")
    except ValueError:
        die(f"неверный цвет {name}: {value!r} (используйте #rgb или #rrggbb)",
            f"invalid {name}: {value!r} (use #rgb or #rrggbb)")
    raise AssertionError  # unreachable


def to_hex(color: RGBA) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color[:3])


def require_opaque(color: RGBA, option: str) -> None:
    if color[3] != 255:
        die(f"{option} должен быть непрозрачным цветом (например #FFFFFF)",
            f"{option} must be an opaque colour (e.g. #FFFFFF)")


def load_image(path: str) -> Image.Image:
    """Open a raster image and return an RGBA copy (file handle closed)."""
    if not os.path.isfile(path):
        die(f"файл не найден: {path}", f"file not found: {path}")
    try:
        with Image.open(path) as im:
            im.load()
            return im.convert("RGBA")
    except (OSError, Image.DecompressionBombError) as exc:
        die(f"не удалось открыть изображение {path}: {exc}",
            f"cannot open image {path}: {exc}")
    raise AssertionError  # unreachable


def trim_transparent(img: Image.Image) -> Image.Image:
    """Crop fully transparent borders (margins are re-added via --padding)."""
    bbox = img.convert("RGBA").getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


def contain_on_canvas(img: Image.Image, canvas: tuple[int, int],
                      box: tuple[int, int], bg: RGBA) -> Image.Image:
    """Scale img to fit inside box WITHOUT stretching and centre it on a canvas.

    Returns RGBA. A transparent bg keeps transparency; an opaque bg gives a
    fully opaque image (convert to RGB before saving if needed).
    """
    box = (max(1, int(box[0])), max(1, int(box[1])))
    fitted = ImageOps.contain(img.convert("RGBA"), box, LANCZOS)
    out = Image.new("RGBA", canvas, bg)
    out.alpha_composite(fitted, ((canvas[0] - fitted.width) // 2,
                                 (canvas[1] - fitted.height) // 2))
    return out


# --- fonts -----------------------------------------------------------------

def default_font_candidates() -> list[str]:
    """Cyrillic-capable TrueType fonts that usually exist on each OS."""
    if sys.platform.startswith("win"):
        fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        return [os.path.join(fonts, n) for n in
                ("arialbd.ttf", "segoeuib.ttf", "arial.ttf", "segoeui.ttf")]
    if sys.platform == "darwin":
        return ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"]
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",       # Debian/Ubuntu
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",     # Fedora/RHEL
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",                   # Arch
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]


def missing_glyphs(font_path: str, text: str) -> list[str]:
    """Characters of text that the font draws as its 'missing glyph' box."""
    probe = ImageFont.truetype(font_path, 48)

    def bitmap(ch: str) -> bytes:
        im = Image.new("L", (112, 112), 0)
        ImageDraw.Draw(im).text((16, 16), ch, font=probe, fill=255)
        return im.tobytes()

    notdef = bitmap("\U0010FFFD")  # private-use code point: never in a real font
    return sorted({ch for ch in text if not ch.isspace() and bitmap(ch) == notdef})


def find_font(user_font: str | None, text: str) -> str:
    """Return a TrueType font path that can draw every character of text.

    Never falls back to Pillow's tiny built-in bitmap font.
    """
    if user_font:
        try:
            ImageFont.truetype(user_font, 20)
        except OSError:
            die(f"не удалось открыть шрифт --font {user_font}",
                f"cannot open font --font {user_font}")
        miss = missing_glyphs(user_font, text)
        if miss:
            die(f"в шрифте {user_font} нет символов: {''.join(miss)}",
                f"font {user_font} lacks glyphs for: {''.join(miss)}")
        return user_font
    checked, missing = [], set()
    for cand in default_font_candidates():
        if not os.path.isfile(cand):
            continue
        miss = missing_glyphs(cand, text)
        if not miss:
            return cand
        checked.append(cand)
        missing.update(miss)
    chars = f" (нет символов / missing glyphs: {''.join(sorted(missing))})" if missing else ""
    die("не найден TrueType-шрифт, способный отрисовать текст" + chars + ". Укажите --font "
        "путь/к/Raleway-Bold.ttf (Windows: C:\\Windows\\Fonts\\arial.ttf; Linux: установите "
        "fonts-dejavu-core или fonts-liberation).",
        "no TrueType font that can draw this text" + chars + ". Pass --font path/to/font.ttf. "
        f"Checked: {checked or 'none of the default paths exist'}")
    raise AssertionError  # unreachable


# --- URLs ------------------------------------------------------------------

def url_prefix(base_url: str) -> str:
    """Validate --base-url and return it with a trailing slash.

    Accepts '/path/', 'https://host/path/' or a MODX placeholder such as
    '[[++site_url]]assets/og/' (site_url already ends with '/').
    """
    b = base_url.strip()
    if '"' in b or "<" in b or ">" in b:
        die("недопустимые символы в --base-url", "invalid characters in --base-url")
    if not b.startswith(("/", "https://", "http://", "[[")):
        die("--base-url должен начинаться с /, https:// или [[++site_url]]",
            "--base-url must start with /, https:// or [[++site_url]]")
    if b.startswith("http://"):
        warn("лучше https://", "https:// is recommended")
    if not b.endswith(("/", "]]")):
        b += "/"
    return b


def is_absolute_url(prefix: str) -> bool:
    return prefix.startswith(("https://", "http://", "[[++site_url]]", "[[!++site_url]]"))


def require_webp() -> None:
    if not features.check("webp"):
        die("эта сборка Pillow без поддержки WebP; переустановите Pillow из PyPI в venv",
            "this Pillow build has no WebP support; reinstall Pillow from PyPI in a venv")
