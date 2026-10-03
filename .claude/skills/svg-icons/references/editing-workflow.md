<!-- Vendored from tryopendata/skills@f97583e plugins/opendesign/skills/svg-design/references/editing-workflow.md (MIT, see ../LICENSE-svg-design.txt). Modified: "Multi-Variant Preview Page" replaced by a contact-sheet workflow (assets/preview.html is not vendored), Windows/Linux/macOS open commands added, workflow tips adapted. See ../NOTICE.md. -->
# SVG Editing Workflow

## Flipping/Mirroring

The `translate` compensates for the flip moving content off-canvas. Values should match the viewBox dimensions.

```xml
<!-- Horizontal flip -->
<g transform="scale(-1, 1) translate(-24, 0)">...</g>

<!-- Vertical flip -->
<g transform="scale(1, -1) translate(0, -24)">...</g>
```

## Combining Multiple SVGs

Merge SVGs by placing their content into a single `<svg>` element. Adjust positions using `transform="translate(x, y)"` or by wrapping in `<g>` groups.

```xml
<!-- Icon + text logo composition -->
<svg viewBox="0 0 200 40" xmlns="http://www.w3.org/2000/svg">
  <!-- Icon (scaled down from 24x24 to 32x32 area, positioned at left) -->
  <g transform="translate(4, 4) scale(1.33)">
    <!-- paste icon paths here -->
  </g>
  <!-- Wordmark text -->
  <text x="44" y="28" font-family="Inter" font-size="20" font-weight="700" fill="currentColor">
    BrandName
  </text>
</svg>
```

## Boolean Operations as Compound Paths

Design tools have union, subtract, intersect, and exclude. In raw SVG, achieve these with compound paths and fill rules.

### Union (combine two shapes)

Merge both shapes' path data into a single `<path>`. With the default `fill-rule="nonzero"`, overlapping same-direction subpaths just fill.

For a true outline-only union (merged contour), you'd need to calculate the actual merged path. In practice, either accept overlapping paths (they render the same when filled) or manually trace the combined outline.

### Subtract (cut one shape out of another)

Use `fill-rule="evenodd"` with overlapping subpaths. The intersection becomes transparent:

```xml
<!-- Circle with rectangular cutout -->
<path fill-rule="evenodd" d="
  M 12 2 A 10 10 0 1 1 12 22 A 10 10 0 1 1 12 2 Z
  M 8 8 h 8 v 8 h -8 Z
" />
```

Alternatively, use `<mask>` for non-path shapes.

### Intersect (keep only the overlap)

Use `<clipPath>` with one shape clipping the other:

```xml
<defs>
  <clipPath id="clip-circle">
    <circle cx="14" cy="12" r="8" />
  </clipPath>
</defs>
<circle cx="10" cy="12" r="8" clip-path="url(#clip-circle)" />
```

### Exclude (XOR: only non-overlapping areas)

Use `fill-rule="evenodd"` with both shapes in a single path. Where they overlap, the fill cancels out. The key difference from union: with `evenodd`, the overlapping region is transparent. With `nonzero` (default), it's filled.


## Comparing Variants (contact sheet)

The upstream live preview page (`assets/preview.html` + `variants.js`) is **not vendored** in this
skill. Compare variants with a static contact sheet instead: every SVG is rendered at the
real display sizes, side by side, with its file name under it. `${CLAUDE_SKILL_DIR}` below
means the folder of the `svg-icons` skill.

```bash
# Linux / macOS
python3 "${CLAUDE_SKILL_DIR}/scripts/render_preview.py" sheet work/concepts/*.svg ref/*.svg \
    --sizes 24 48 --out work/preview/sheet.png
```

```powershell
# Windows (PowerShell). The scripts expand wildcards themselves, so quote the patterns.
# Use the skill folder you installed: project .claude\skills\svg-icons or %USERPROFILE%\.claude\skills\svg-icons
py -3 "$env:USERPROFILE\.claude\skills\svg-icons\scripts\render_preview.py" sheet "work\concepts\*.svg" "ref\*.svg" --sizes 24 48 --out work\preview\sheet.png
```

Then look at the PNG yourself (the Read tool shows images) before showing it to the user.
Group candidates and references in the same sheet so the comparison is at identical sizes
and background.

### Opening a file for the user

| OS | Command |
|----|---------|
| Windows (cmd) | `start "" work\preview\sheet.png` |
| Windows (PowerShell) | `Start-Process work\preview\sheet.png` |
| Linux | `xdg-open work/preview/sheet.png` |
| macOS | `open work/preview/sheet.png` |

In a remote/cloud session there is no desktop: give the user the file path instead.

### Iteration workflow

| Change type | What to do |
|-------------|-----------|
| Edit an SVG (colours, shapes, paths) | Re-run `check_svg.py`, then re-render the sheet |
| Add/remove a variant | Change the file list passed to `render_preview.py sheet` |
| New round of concepts | Write them to a new numbered folder (`round-2/`), keep the previous round |

## Workflow Tips

1. **Start with shape primitives**, convert to paths only when needed for optimization or compound operations (or when the target icon family is path-only)
2. **Use relative coordinates** (`m`, `l`, `c`) when hand-writing paths. Easier to reason about incrementally
3. **Test at the real display sizes**: render at the sizes the icon is actually shown (for UI icons 16, 24, 48 px; for product illustrations the CSS width on the page)
4. **Keep a monochrome version**: if using color, ensure it also works with a single `currentColor`
5. **Validate the output**: run `scripts/check_svg.py`, then look at the rendered PNG, not just the code. Check for rendering artifacts
6. **Round coordinates to the grid**: snap to integers on 24x24 canvas for pixel-perfect rendering at 1x
7. **Never overwrite the original**: write edits and optimised output to a new folder
