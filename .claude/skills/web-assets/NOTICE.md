# NOTICE — web-assets

Vendored with changes from **Web Asset Generator**:

- Upstream: https://github.com/alonw0/web-asset-generator (path `skills/web-asset-generator/`)
- Commit: `c6d56dc54ab86eae4eeb1393d9c8cdc71ae8d1a8` (2026-01-28)
- Licence: MIT. Copyright (c) 2025 Web Asset Generator Contributors. Full text in `LICENSE`.
  Local modifications are distributed under the same MIT licence.
- Vendored: 2026-10-03, after a static security review (no network code in the vendored part;
  the only network path was the optional pilmoji emoji renderer, which was removed).

## Files

| File | Status | Upstream sha256 |
|---|---|---|
| `scripts/generate_favicons.py` | modified (largely rewritten) | `d4a3b5d01d43a57458afc1c2afce8e8635266c3f10fbd0fb78c4eeecb23c33ac` |
| `scripts/generate_og_images.py` | modified (largely rewritten) | `601bd948bc7ec328f1b9d83a4185c565d4d7bea4afcee7775cda4e603e0df778` |
| `scripts/lib/__init__.py` | unchanged | `a00414aab421b63759f4870572c9fe16b6eb9b7549bd8efd1080bb21af78af31` |
| `scripts/lib/validators.py` | modified | `88c2fb0884e5bc0c20a4f69d78fecf5576f06fca2d1f457259623354eee1b89d` |
| `references/specifications.md` | modified | `ec59441f349f08c40c01313d09c54b044e3ada45793a2d2002f62feba46d5d32` |
| `LICENSE` | unchanged | `ee4c9993913bffb47e17d05cf42a550ab8feefc11414ffaf5ad6c281a485fbe1` |
| `scripts/lib/common.py` | new (local) | — |
| `scripts/check_assets.py` | new (local) | — |
| `SKILL.md`, `NOTICE.md` | new (local); upstream SKILL.md not used | — |

Not vendored: `scripts/emoji_utils.py`, `scripts/check_dependencies.py`, `CLAUDE.md`, the original
`SKILL.md`, `demo.mp4`, docs and plugin manifests.

## Local modifications

1. **Emoji removed.** All emoji/pilmoji code paths and options (`--emoji`, `--emoji-bg`, `--suggest`)
   are gone, so nothing can reach the network. Status markers are ASCII (`[OK]`, `[WARN]`, `[ERROR]`)
   so output does not crash Windows consoles; stdout/stderr are switched to UTF-8 with `errors=replace`.
2. **ICO fixed.** `favicon.ico` is saved from a 256 px square image with sizes 16/32/48. Upstream saved
   from a 16 px image, so Pillow dropped the larger sizes.
3. **No stretching.** Non-square logos are fitted with `ImageOps.contain` and centred on a square canvas
   (transparent for favicons, `--bg` configurable). Fully transparent borders are trimmed first;
   `--padding` adds a margin back.
4. **Open Graph.** The default is "contain" on a brand background (`--bg`, default `#1C1C1C`, or `#FFFFFF`),
   always flattened to RGB. "cover" is kept as `--fit cover` for photos only. Text mode has `--font`
   with Cyrillic-capable defaults per OS (Windows Arial/Segoe UI; Linux DejaVu/Liberation; macOS Arial).
   It checks that the font has every glyph of the text, and it exits with a clear error instead of
   falling back to Pillow's built-in font. The text is shrunk to fit and supports an optional brand
   accent stripe (`--accent`).
5. **New outputs.**
   - `site.webmanifest`: name, short_name, lang, start_url, display, theme_color, background_color,
     and the 192/512 icons.
   - `maskable-icon-512x512.png`: the logo diagonal fits the 80% safe circle.
   - Opaque `apple-touch-icon.png`.
   - WebP copies of all OG images, and optional JPEG (`--jpeg`).
   - `icon.svg` copied as-is when the source (or `--svg`) is SVG. SVG input is rasterised only with
     a local `resvg` CLI found by `shutil.which`; otherwise the script asks for a PNG source.
     `subprocess` is used only for this call: no shell, with a timeout.
6. **Validators.**
   - Every check opens the file and reads the real pixel size, format and alpha; file names are
     never trusted.
   - New checks: ICO frames, manifest (JSON, keys, icon files and their declared sizes, maskable),
     SVG (no scripts), and opaque/RGB rules.
   - Colours accept `#rgb` and `#rrggbb` (and CSS names).
   - `check_directory()` plus a new CLI `scripts/check_assets.py`.
7. **Tags.** Both generators print the `<link>`/`<meta>` tags at the end: manifest, theme-color,
   SVG icon, `og:image:type`, `og:locale` and `og:site_name`. `--base-url` accepts `/path/`,
   `https://…/` or a MODX `[[++site_url]]` prefix, and the OG generator warns when the URL is not absolute.
8. **Specifications.** Updated for ICO 16/32/48, SVG favicon, manifest and maskable icons, WebP/JPEG,
   Cyrillic fonts, VK and Telegram, brand contrast pairs. The removed X/Twitter Card Validator
   preview is noted.
9. **Clean skill folder.** Scripts set `sys.dont_write_bytecode` so they don't create `__pycache__`
   inside the skill. Python 3.10+, stdlib + Pillow (`>=12,<13`) only.
