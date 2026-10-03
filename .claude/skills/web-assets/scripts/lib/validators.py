#!/usr/bin/env python3
"""
Validation utilities for web assets.

Vendored from alonw0/web-asset-generator (MIT, commit c6d56dc) and modified
(see NOTICE.md): every check opens the file and reads real pixels/format,
never trusts file names; colours accept #rgb and #rrggbb; ICO, manifest and
SVG checks added; ASCII status markers (safe on Windows consoles).
"""

from __future__ import annotations

import json
import os
import string
from pathlib import Path
from typing import Dict, List, Tuple, Union

from PIL import Image, ImageColor

Color = Union[str, Tuple[int, ...]]

# Platform-specific requirements (upstream values)
PLATFORM_REQUIREMENTS = {
    'facebook': {
        'max_file_size': 8 * 1024 * 1024,  # 8MB
        'recommended_size': (1200, 630),
        'min_size': (600, 315),
        'aspect_ratio': 1.91,
        'formats': ['png', 'jpg', 'jpeg'],
    },
    'twitter': {
        'max_file_size': 5 * 1024 * 1024,  # 5MB
        'recommended_size': (1200, 675),
        'min_size': (300, 157),
        'aspect_ratio': 16 / 9,
        'formats': ['png', 'jpg', 'jpeg', 'webp'],
    },
    'linkedin': {
        'max_file_size': 5 * 1024 * 1024,  # 5MB
        'recommended_size': (1200, 627),
        'min_size': (1200, 628),
        'aspect_ratio': 1.91,
        'formats': ['png', 'jpg', 'jpeg'],
    },
    'whatsapp': {
        'max_file_size': 8 * 1024 * 1024,  # 8MB (same as Facebook)
        'recommended_size': (1200, 630),
        'min_size': (600, 315),
        'aspect_ratio': 1.91,
        'formats': ['png', 'jpg', 'jpeg'],
    },
}

# Expected pixel sizes of the files our generators write
ICON_SIZES = {
    'favicon-16x16.png': (16, 16),
    'favicon-32x32.png': (32, 32),
    'favicon-96x96.png': (96, 96),
    'apple-touch-icon.png': (180, 180),
    'android-chrome-192x192.png': (192, 192),
    'android-chrome-512x512.png': (512, 512),
    'maskable-icon-512x512.png': (512, 512),
}
OPAQUE_ICONS = {'apple-touch-icon.png', 'maskable-icon-512x512.png'}
OG_SIZES = {'og-image': (1200, 630), 'twitter-image': (1200, 675), 'og-square': (1200, 1200)}
OG_PLATFORM = {'og-image': 'facebook', 'twitter-image': 'twitter', 'og-square': 'facebook'}
EXT_FORMAT = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP', '.ico': 'ICO'}
ICO_REQUIRED = {(16, 16), (32, 32), (48, 48)}
MANIFEST_KEYS = ('name', 'short_name', 'icons', 'start_url', 'display',
                 'theme_color', 'background_color')

# WCAG contrast ratio requirements
WCAG_AA_NORMAL = 4.5
WCAG_AA_LARGE = 3.0
WCAG_AAA_NORMAL = 7.0
WCAG_AAA_LARGE = 4.5


class ValidationResult:
    """Represents the result of a validation check."""

    def __init__(self, passed: bool, message: str, level: str = 'info'):
        self.passed = passed
        self.message = message
        self.level = level  # 'success', 'warning', 'error', 'info'

    def __str__(self):
        icon = {'success': '[OK]', 'warning': '[WARN]', 'error': '[ERROR]',
                'info': '[INFO]'}.get(self.level, '[-]')
        return f"{icon} {self.message}"

    def __repr__(self):
        return f"ValidationResult(passed={self.passed}, level='{self.level}', message='{self.message}')"


def ok(msg: str) -> ValidationResult:
    return ValidationResult(True, msg, 'success')


def warning(msg: str) -> ValidationResult:
    return ValidationResult(True, msg, 'warning')


def error(msg: str) -> ValidationResult:
    return ValidationResult(False, msg, 'error')


# --- colours and contrast ---------------------------------------------------

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """'#rgb', '#rrggbb' (with or without '#') -> (r, g, b)."""
    s = hex_color.strip().lstrip('#')
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    if len(s) != 6 or any(c not in string.hexdigits for c in s):
        raise ValueError(f"Invalid hex colour {hex_color!r}: use #rgb or #rrggbb")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_rgb(color: Color) -> Tuple[int, int, int]:
    """Accept an RGB(A) tuple, '#rgb', '#rrggbb' or a CSS colour name."""
    if isinstance(color, tuple):
        return tuple(color[:3])
    if color.strip().startswith('#'):
        return hex_to_rgb(color)
    try:
        return hex_to_rgb(color)
    except ValueError:
        return ImageColor.getrgb(color)[:3]  # names like 'white'; raises ValueError


def calculate_contrast_ratio(color1: Color, color2: Color) -> float:
    """WCAG 2.x contrast ratio (1.0 to 21.0) between two colours."""
    def relative_luminance(rgb):
        channels = []
        for c in rgb:
            c = c / 255.0
            channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lum1 = relative_luminance(to_rgb(color1))
    lum2 = relative_luminance(to_rgb(color2))
    lighter, darker = max(lum1, lum2), min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def validate_contrast(text_color: Color, bg_color: Color, font_size: int = 16,
                      is_bold: bool = False) -> ValidationResult:
    """Check WCAG AA/AAA contrast. font_size in px (16px = 12pt)."""
    ratio = calculate_contrast_ratio(text_color, bg_color)
    pt_size = font_size * 0.75
    is_large = pt_size >= 18 or (pt_size >= 14 and is_bold)
    min_aa = WCAG_AA_LARGE if is_large else WCAG_AA_NORMAL
    min_aaa = WCAG_AAA_LARGE if is_large else WCAG_AAA_NORMAL
    if ratio >= min_aaa:
        return ok(f"Contrast ratio {ratio:.1f}:1 meets WCAG AAA ({min_aaa:.1f}:1 required)")
    if ratio >= min_aa:
        return ok(f"Contrast ratio {ratio:.1f}:1 meets WCAG AA ({min_aa:.1f}:1 required)")
    return error(f"Contrast ratio {ratio:.1f}:1 fails WCAG AA ({min_aa:.1f}:1 required)")


# --- platform checks (upstream API; they open the file) ---------------------

def _unknown_or_missing(file_path, platform):
    if platform not in PLATFORM_REQUIREMENTS:
        return error(f"Unknown platform: {platform}")
    if not Path(file_path).is_file():
        return error(f"File not found: {file_path}")
    return None


def validate_file_size(file_path: str, platform: str = 'facebook') -> ValidationResult:
    bad = _unknown_or_missing(file_path, platform)
    if bad:
        return bad
    size = os.path.getsize(file_path)
    limit = PLATFORM_REQUIREMENTS[platform]['max_file_size']
    mb, limit_mb = size / 1048576, limit / 1048576
    if size > limit:
        return error(f"File size {mb:.2f}MB exceeds {platform.title()} limit of {limit_mb:.0f}MB")
    if size > limit * 0.8:
        return warning(f"File size {mb:.2f}MB is close to {platform.title()} limit ({limit_mb:.0f}MB)")
    return ok(f"File size {mb:.2f}MB is within {platform.title()} limits")


def validate_dimensions(file_path: str, platform: str = 'facebook') -> ValidationResult:
    bad = _unknown_or_missing(file_path, platform)
    if bad:
        return bad
    try:
        with Image.open(file_path) as img:
            width, height = img.size
    except Exception as e:  # noqa: BLE001 - report any decoder error
        return error(f"Could not read image dimensions: {e}")
    req = PLATFORM_REQUIREMENTS[platform]
    if (width, height) == req['recommended_size']:
        return ok(f"Dimensions {width}x{height} match {platform.title()} recommended size")
    min_w, min_h = req['min_size']
    if width < min_w or height < min_h:
        return error(f"Dimensions {width}x{height} below {platform.title()} minimum ({min_w}x{min_h})")
    ratio = width / height
    if abs(ratio - req['aspect_ratio']) > 0.1:
        return warning(f"Dimensions {width}x{height}: non-standard aspect ratio "
                       f"(expected {req['aspect_ratio']:.2f}:1, got {ratio:.2f}:1)")
    return ok(f"Dimensions {width}x{height} meet {platform.title()} requirements")


def validate_format(file_path: str, platform: str = 'facebook') -> ValidationResult:
    bad = _unknown_or_missing(file_path, platform)
    if bad:
        return bad
    try:
        with Image.open(file_path) as img:
            fmt = (img.format or '').lower()
    except Exception as e:  # noqa: BLE001
        return error(f"Could not read image format: {e}")
    allowed = PLATFORM_REQUIREMENTS[platform]['formats']
    if fmt in allowed:
        return ok(f"Format {fmt.upper()} is supported by {platform.title()}")
    return error(f"Format {fmt.upper() or '?'} not supported by {platform.title()} "
                 f"(use {', '.join(allowed).upper()})")


def validate_all(file_path: str, platforms: List[str] = None) -> Dict[str, List[ValidationResult]]:
    results = {}
    for platform in platforms or ['facebook', 'twitter']:
        results[platform] = [validate_file_size(file_path, platform),
                             validate_dimensions(file_path, platform),
                             validate_format(file_path, platform)]
    return results


def print_validation_results(results: Dict[str, List[ValidationResult]], verbose: bool = True):
    for platform, checks in results.items():
        print(f"\n{platform.title()} Validation:")
        for result in checks:
            if verbose or result.level in ('warning', 'error'):
                print(f"  {result}")
    total = sum(len(c) for c in results.values())
    passed = sum(1 for c in results.values() for r in c if r.passed)
    print(f"\nSummary: {passed}/{total} checks passed")


# --- file checks for generated assets ---------------------------------------

def validate_image(path: Path, expected: Tuple[int, int], opaque: bool = False,
                   rgb_only: bool = False) -> List[ValidationResult]:
    """Open the file and check real format, pixel size and transparency."""
    try:
        with Image.open(path) as img:
            img.load()
            fmt, size, mode = img.format, img.size, img.mode
            alpha_min = img.getchannel('A').getextrema()[0] if 'A' in img.getbands() else 255
    except Exception as e:  # noqa: BLE001
        return [error(f"cannot open image: {e}")]
    res = []
    want_fmt = EXT_FORMAT.get(path.suffix.lower())
    res.append(ok(f"format {fmt}") if fmt == want_fmt
               else error(f"real format {fmt} does not match extension {path.suffix}"))
    res.append(ok(f"{size[0]}x{size[1]} px") if size == expected
               else error(f"{size[0]}x{size[1]} px, expected {expected[0]}x{expected[1]}"))
    if opaque and alpha_min < 255:
        res.append(error("has transparent pixels; must be opaque"))
    if rgb_only and mode not in ('RGB', 'L'):
        res.append(error(f"mode {mode}; social images must be flattened to RGB"))
    return res


def validate_ico(path: Path) -> List[ValidationResult]:
    try:
        with Image.open(path) as img:
            fmt = img.format
            sizes = set(img.info.get('sizes', set()))
    except Exception as e:  # noqa: BLE001
        return [error(f"cannot open ICO: {e}")]
    if fmt != 'ICO':
        return [error(f"real format {fmt}, expected ICO")]
    listed = ', '.join(f"{w}x{h}" for w, h in sorted(sizes))
    missing = ICO_REQUIRED - sizes
    if missing:
        return [error(f"ICO sizes {listed}; missing "
                      + ', '.join(f"{w}x{h}" for w, h in sorted(missing)))]
    return [ok(f"ICO contains {listed}")]


def _hex_ok(value) -> bool:
    try:
        hex_to_rgb(value)
        return isinstance(value, str) and value.startswith('#')
    except (ValueError, AttributeError):
        return False


def validate_manifest(path: Path) -> List[ValidationResult]:
    """Valid JSON, required keys, icons exist next to it with the declared pixel sizes."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return [error(f"not valid UTF-8 JSON: {e}")]
    res = [ok("valid JSON")]
    missing = [k for k in MANIFEST_KEYS if k not in data]
    res.append(error(f"missing keys: {', '.join(missing)}") if missing else ok("required keys present"))
    for key in ('theme_color', 'background_color'):
        if key in data and not _hex_ok(data[key]):
            res.append(error(f"{key} {data[key]!r} is not a #hex colour"))
    if len(str(data.get('short_name', ''))) > 12:
        res.append(warning("short_name is longer than 12 characters"))
    sizes_seen, maskable = set(), False
    for icon in data.get('icons', []):
        src = str(icon.get('src', ''))
        name = src.split('?')[0].rsplit('/', 1)[-1]
        declared = str(icon.get('sizes', '')).split()[0] if icon.get('sizes') else ''
        file = path.parent / name
        if not file.is_file():
            res.append(error(f"icon {src} not found next to the manifest"))
            continue
        try:
            w, h = (int(x) for x in declared.lower().split('x'))
        except ValueError:
            res.append(error(f"icon {src}: bad sizes {declared!r}"))
            continue
        try:
            with Image.open(file) as img:
                real = img.size
        except Exception as e:  # noqa: BLE001
            res.append(error(f"icon {src}: cannot open ({e})"))
            continue
        if real != (w, h):
            res.append(error(f"icon {src}: declared {declared}, real {real[0]}x{real[1]}"))
        sizes_seen.add(w)
        maskable = maskable or 'maskable' in str(icon.get('purpose', ''))
    for need in (192, 512):
        if need not in sizes_seen:
            res.append(error(f"no {need}x{need} icon"))
    res.append(ok("maskable icon declared") if maskable else warning("no maskable icon"))
    return res


def validate_svg(path: Path) -> List[ValidationResult]:
    try:
        low = path.read_text(encoding='utf-8', errors='replace').lower()
    except OSError as e:
        return [error(f"cannot read: {e}")]
    if '<svg' not in low:
        return [error("not an SVG document")]
    if '<script' in low or 'javascript:' in low:
        return [error("contains scripts")]
    return [ok("SVG without scripts")]


def check_directory(directory) -> Dict[str, List[ValidationResult]]:
    """Check every known web asset found in a directory (by opening the files)."""
    d = Path(directory)
    report: Dict[str, List[ValidationResult]] = {}
    for name, size in ICON_SIZES.items():
        if (d / name).is_file():
            report[name] = validate_image(d / name, size, opaque=name in OPAQUE_ICONS)
    for base, size in OG_SIZES.items():
        for ext in ('.png', '.jpg', '.jpeg', '.webp'):
            f = d / f"{base}{ext}"
            if not f.is_file():
                continue
            checks = validate_image(f, size, rgb_only=True)
            if ext != '.webp':
                checks.append(validate_file_size(str(f), OG_PLATFORM[base]))
                if f.stat().st_size > 1024 * 1024:
                    checks.append(warning("larger than 1 MB; use --jpeg for faster previews"))
            report[f.name] = checks
    if (d / 'favicon.ico').is_file():
        report['favicon.ico'] = validate_ico(d / 'favicon.ico')
    if (d / 'site.webmanifest').is_file():
        report['site.webmanifest'] = validate_manifest(d / 'site.webmanifest')
    if (d / 'icon.svg').is_file():
        report['icon.svg'] = validate_svg(d / 'icon.svg')
    if not report:
        report[str(d)] = [error("no known web-asset files found")]
    return report


def print_directory_report(report: Dict[str, List[ValidationResult]]) -> bool:
    """Print the report; return True when there are no errors."""
    errors = warnings = 0
    for name, checks in report.items():
        print(f"  {name}")
        for r in checks:
            print(f"    {r}")
            errors += r.level == 'error'
            warnings += r.level == 'warning'
    print(f"  Summary: {len(report)} files, {errors} errors, {warnings} warnings")
    return errors == 0


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validators.py <directory | image_file>")
        sys.exit(1)
    target = Path(sys.argv[1])
    if target.is_dir():
        sys.exit(0 if print_directory_report(check_directory(target)) else 1)
    print(f"Validating: {target}")
    print_validation_results(validate_all(str(target), ['facebook', 'twitter', 'linkedin']))
