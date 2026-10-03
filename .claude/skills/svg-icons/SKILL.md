---
name: svg-icons
description: >-
  Create, edit, check, optimise and export SVG icons, pictograms and line illustrations of equipment.
  Covers structure and security checks, rendering to PNG at the real display size, contact sheets
  that compare variants and reference icons, SVGO 4 optimisation and PNG/WebP export.
  Use when the user asks to draw or fix an SVG icon, clean up an SVG exported from Figma or Inkscape,
  check a third-party SVG before it goes on a site, compare icon variants, or export SVG to PNG, WebP or ICO.
when_to_use: >-
  "нарисуй иконку", "проверь SVG", "почисти svg после Figma", "оптимизируй svg", "сделай PNG/WebP из SVG",
  "сравни варианты иконок", "как иконка выглядит в реальном размере", "почему иконка размыта",
  "безопасен ли этот svg", "draw an SVG icon", "export svg to png".
argument-hint: >-
  [file.svg | folder | description of the icon]
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/check_svg.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/check_svg.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/render_preview.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/render_preview.py *)
---

# SVG icons and pictograms

An SVG is code. Write it by hand and keep it minimal and readable. Answer in the user's language.

For НОВАПРОМ equipment illustrations (catalogue tiles, mega-menu icons of novaprom.ru), start
with the `novaprom-equipment-icons` skill. It holds the company design system and uses the tools of this skill.

## Hard rules
1. **Never overwrite originals and never edit the live site.**
   - Work in a new folder, e.g. `./icons-work/<name>/` with `src/` (drafts), `preview/` (renders), `dist/` (optimised) and `export/` (PNG/WebP).
   - Files the user gave you are read-only.
2. **Valid structure.**
   - Every file has `xmlns="http://www.w3.org/2000/svg"` and a valid `viewBox` (4 numbers, width and height > 0).
   - Add `width`/`height` when the file is used via `<img>` without a CSS size.
3. **No active or external content.** Not allowed:
   - `<script>`, `on*` handlers, `<foreignObject>`, DOCTYPE/ENTITY;
   - `javascript:` URLs, external `href`/`src`/`url()`;
   - editor metadata;
   - embedded raster images, unless the user explicitly wants one.
4. **Accessibility.**
   - Inline informative SVG: `role="img"`, a `<title>` as the first child, `aria-labelledby`.
   - Inline decorative SVG: `aria-hidden="true"`.
   - For `<img src="….svg">`, the text goes in `alt`, not in the SVG.
   - Details: `references/accessibility-and-pitfalls.md`.
5. **No live text.** Convert `<text>` to paths before delivery (`usvg`, or Inkscape "Object to Path").
6. **Optimise only after the user approves the drawing.**
   - Run SVGO via `npx` only after the user agrees, because `npx` downloads the package from npm.
   - Never install anything system-wide or without asking. Python packages go into a venv.

## Before drawing
- **Match the existing set.** Look for icons already in the project or on the site (`**/*.svg`, the template's `img/` folder). Match their canvas, stroke widths, caps and joins, colours, perspective and level of detail. `check_svg.py` prints the effective stroke colours, widths, caps and joins of any file.
- **UI icon defaults:**
  - `viewBox="0 0 24 24"`;
  - on the root: `fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"`;
  - 2 units of padding and integer coordinates (`references/icon-design.md`).
- **Technical pictograms for diagrams and documentation** (P&ID, schemes, passports) follow the symbol standard named by the user or customer. Never invent a symbol for a standardised item.
  - Candidates: ГОСТ 2.785-70 (pipeline fittings), ГОСТ 21.208-2013 (automation and instrumentation), ISO 14617 (graphical symbols for diagrams), ISO 10628-2 (P&ID).
  - **Проверить применимость**: check the current edition, the replacement status and the customer's requirements before using any of them. Ask if unsure.
- **Product illustrations** (marketing tiles) are not bound by these standards, but must show the real construction of the equipment.
- **Load other references only when needed:**

| Need | Reference |
|---|---|
| Grids, pixel alignment, stroke conventions, optical balance | `references/icon-design.md` |
| Arc flags, hand-written path templates | `references/path-patterns.md` |
| a11y, browser pitfalls, stroke clipping at the edges | `references/accessibility-and-pitfalls.md` |
| SVGO 4 details, sprites, groups | `references/optimization.md` |
| Mirroring, combining, boolean ops, comparing variants, opening files per OS | `references/editing-workflow.md` |

## Pipeline
Run commands from the project root. `${CLAUDE_SKILL_DIR}` is this skill's folder. On Windows use `py -3` instead of `python3`. The scripts expand quoted wildcards themselves.

1. **Draw.** Write `icons-work/<name>/src/<name>.svg`.
2. **Check:**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/check_svg.py icons-work/<name>/src/      # add --require-title for inline informative icons
   ```
   Fix every error and explain any warning you leave. Exit code 1 means errors.
3. **Render at the real size and look at it:**
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/render_preview.py sheet "icons-work/<name>/src/*.svg" "path/to/reference/*.svg" \
       --sizes 24 48 --out icons-work/<name>/preview/sheet.png          # use the real CSS widths of the page
   ```
   - Open the PNG with the Read tool **before** showing it to the user.
   - Check readability at the smallest real size, and with `--dpr 2` for HiDPI screens.
   - Lines thinner than about 1 device pixel turn into faint hairlines.
   - Renderer: `resvg` if it is on PATH, otherwise CairoSVG. If neither exists, the script prints install hints. `render_preview.py backends` shows what is available.
4. **Show the user** the best variants and the sheet, then iterate. Put new rounds in new files or folders.
5. **After approval, optimise.** Ask first: "run `npx svgo@4.1.0` (downloads SVGO from npm)?"
   ```bash
   npx svgo@4.1.0 --config ${CLAUDE_SKILL_DIR}/svgo.config.mjs -f icons-work/<name>/src -o icons-work/<name>/dist
   python3 ${CLAUDE_SKILL_DIR}/scripts/check_svg.py icons-work/<name>/dist/
   ```
   - The config is SVGO 4 `preset-default` with `cleanupIds` off, plus `removeScripts`, `removeXlink`, multipass and `floatPrecision` 2.
   - `mergePaths` merges paths with identical attributes, so the path count drops while the picture stays the same. Re-render the sheet and compare with `src/`.
6. **Export to web formats** when asked:
   - PNG and lossless WebP, written to new files:
     ```bash
     python3 ${CLAUDE_SKILL_DIR}/scripts/render_preview.py render icons-work/<name>/dist/<name>.svg \
         --sizes 106 239 --dpr 2 --webp --out-dir icons-work/<name>/export
     ```
   - The same with the CLI tools: `resvg -w 478 in.svg out.png`, then `cwebp -lossless out.png -o out.webp`.
   - ICO: `python3 -c "from PIL import Image; Image.open('x-256.png').save('favicon.ico', sizes=[(16,16),(32,32),(48,48)])"`. For a full favicon/OG set, use the `web-assets` skill.
7. **Report:**
   - the files written;
   - bytes before and after SVGO;
   - warnings left and checks skipped;
   - where the sheet is.

## Tools (install only with the user's consent)
| Tool | Role | Linux (Debian/Ubuntu) | Windows (PowerShell) |
|---|---|---|---|
| Python 3.10+ | scripts | `sudo apt install python3 python3-venv` | `winget install Python.Python.3.12` |
| resvg 0.4x | SVG → PNG (preferred) | `cargo install resvg --locked` or release binary | `scoop install resvg` |
| CairoSVG ≥ 2.7 | SVG → PNG (fallback; needs Cairo) | `python3 -m venv .venv && .venv/bin/pip install cairosvg` | `py -3 -m venv .venv; .\.venv\Scripts\pip install cairosvg` (+ Cairo DLLs) |
| Pillow 12 | sheets, WebP, ICO | `.venv/bin/pip install "Pillow>=12,<13"` | `.\.venv\Scripts\pip install "Pillow>=12,<13"` |
| Node.js + SVGO 4.1.0 | optimisation | `npx svgo@4.1.0 …` (Node ≥ 16) | `winget install OpenJS.NodeJS.LTS`, then `npx svgo@4.1.0 …` |
| cwebp | PNG → WebP (optional) | `sudo apt install webp` | `scoop install libwebp` |

- Confirm winget IDs with `winget search` first.
- ImageMagick: use it only for PNG → ICO, never to rasterise SVG (history of SVG/MVG CVEs).
- svglint configs are executable JavaScript, so run svglint only in trusted repositories.
- Self-test of the checker: `python3 ${CLAUDE_SKILL_DIR}/scripts/test_check_svg.py`.
