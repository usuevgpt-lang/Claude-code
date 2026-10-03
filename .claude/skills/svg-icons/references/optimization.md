<!-- Vendored from tryopendata/skills@f97583e plugins/opendesign/skills/svg-design/references/optimization.md (MIT, see ../LICENSE-svg-design.txt). Modified: SVGO section rewritten for SVGO 4.1.0, removeXMLNS dropped, no in-place overwrite. See ../NOTICE.md. -->
# SVG Optimization

## Consolidate Styles to Root Element

```xml
<!-- Before: repeated on every element -->
<path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" d="..." />
<path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" d="..." />

<!-- After: set once on root -->
<svg stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" ...>
  <path d="..." />
  <path d="..." />
</svg>
```

## SVGO (Automated Optimization)

Pinned version: **SVGO 4.1.0** (MIT, Node >= 16, no install scripts). Run it only after the
user has approved the drawing **and** has agreed to running `npx` (it downloads the package
from npm on first use). Never install it globally without asking.

```bash
# single file -> new file (never overwrite the original)
npx svgo@4.1.0 --config path/to/svgo.config.mjs icons/src/valve.svg -o icons/dist/valve.svg
# whole folder -> another folder
npx svgo@4.1.0 --config path/to/svgo.config.mjs -f icons/src -o icons/dist
```

Do **not** use `svgo input.svg` without `-o`: it overwrites the input in place.

### Recommended config for icons (SVGO 4)

This is the file shipped as `../svgo.config.mjs`:

```js
// svgo.config.mjs (SVGO 4.x)
export default {
  multipass: true,
  floatPrecision: 2,
  plugins: [
    { name: 'preset-default', params: { overrides: { cleanupIds: false } } }, // keep ids used by <defs>/<use>/clipPath
    'removeScripts', // strips <script>, on* handlers, javascript: URLs
    'removeXlink',   // xlink:href -> href (SVG 2)
  ],
};
```

Notes on SVGO 4 versus older configs:

- `removeViewBox` and `removeTitle` are **no longer in `preset-default`** in SVGO 4, so the
  viewBox and `<title>` are kept by default. Overriding `removeViewBox: false` inside
  `preset-default` only prints a warning; leave it out.
- Do **not** add `removeXMLNS` for standalone `.svg` files: without `xmlns` the file is not
  rendered as SVG when opened directly or used in `<img>`. Use it only for SVG pasted inline
  into HTML, and then in a separate config.
- `floatPrecision: 2` is enough for icons drawn on a 24-unit or 220-unit canvas. Check the
  result visually (render at real size) because rounding can move small details.
- `removeScripts` is not a full sanitiser. For user uploads use a real sanitiser
  (DOMPurify with the SVG profile) plus a Content-Security-Policy.

### Dangerous SVGO behaviours to watch

| Plugin | Risk | Fix |
|--------|------|-----|
| `removeViewBox` (not default in v4) | Breaks responsive scaling | Never enable it |
| `cleanupIds` | Breaks gradient/mask/clipPath references | Disabled in our config |
| `removeHiddenElems` | Can remove elements that are revealed via CSS/JS | Disable for animated SVGs |
| `collapseGroups` | Removes groups that may carry important transforms | Review output |
| `removeXMLNS` (not default) | Standalone files stop rendering | Only for inline SVG |

## Sprites

**Pros:** Single HTTP request for all icons, browser caches the file, consistent styling.

**Cons:** Downloads all icons even if page uses one. No tree-shaking. External sprite files don't work with `<use>` in Safari for cross-origin requests.

## When to Use `<g>` Groups

Groups are free (no rendering cost) but add DOM complexity. Use them when:

- Applying a shared `transform` to multiple elements
- Applying a shared `opacity`, `clip-path`, `mask`, or `filter`
- Logically grouping elements for readability
- Adding event handlers to a collection of shapes

Don't use them just for organization in distributed icons (Lucide prohibits them entirely).
