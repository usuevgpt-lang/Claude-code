#!/usr/bin/env python3
"""
Check a folder of web assets (local addition, see NOTICE.md).

Opens every known file and checks real pixel size, format, transparency,
ICO frame sizes (16/32/48), site.webmanifest JSON and icon paths, icon.svg.
Optionally checks a text/background colour pair for WCAG contrast.

Usage:
  python check_assets.py out/icons out/og
  python check_assets.py out/og --contrast "#FFFFFF" "#1C1C1C"
Exit code 0 = no errors, 1 = errors found.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import die, setup_console  # noqa: E402  (friendly error if Pillow is missing)
from lib import validators  # noqa: E402


def main() -> int:
    setup_console()
    p = argparse.ArgumentParser(description="Check generated favicons, icons, manifest and OG images.")
    p.add_argument("dirs", nargs="+", help="folders with generated assets")
    p.add_argument("--contrast", nargs=2, metavar=("TEXT", "BG"),
                   help="check WCAG contrast of two colours (#rgb or #rrggbb)")
    args = p.parse_args()

    all_ok = True
    for d in args.dirs:
        if not Path(d).is_dir():
            die(f"папка не найдена: {d}", f"folder not found: {d}")
        print(f"\n{d}")
        all_ok &= validators.print_directory_report(validators.check_directory(d))
    if args.contrast:
        try:
            result = validators.validate_contrast(*args.contrast, font_size=36, is_bold=True)
        except ValueError as exc:
            die(f"неверный цвет: {exc}", f"invalid colour: {exc}")
        print(f"\nContrast {args.contrast[0]} on {args.contrast[1]} (large bold text): {result}")
        all_ok &= result.passed
    print("\nRESULT: OK" if all_ok else "\nRESULT: ERRORS FOUND / есть ошибки")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
