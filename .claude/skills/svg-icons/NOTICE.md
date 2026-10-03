# Third-party notice

Parts of `references/` come from the **svg-design** skill of the OpenData `opendesign` plugin.

| Item | Value |
|---|---|
| Source | https://github.com/tryopendata/skills, path `plugins/opendesign/skills/svg-design/references/` |
| Commit | `f97583ecb7eeb8a0c2a193fe9b80e55806d29823` (2026-07-25, plugin `opendesign` v1.3.2) |
| License | MIT, Copyright (c) 2026 OpenData. Full text: `LICENSE-svg-design.txt` (copy of upstream `LICENSE.md`, sha256 `54bf7a20…ee19da4`) |
| Vendored on | 2026-10-03 |

## Files

| File | Status | Upstream sha256 |
|---|---|---|
| `references/icon-design.md` | unmodified | `0459ebf842c0f85664edbf4b954f0c114532c87e2e14acef253f42085658a552` |
| `references/path-patterns.md` | unmodified | `314528f6a4bbea6c1efd45701fd2a5bd4021d76b2b8382965b73e1b678622802` |
| `references/accessibility-and-pitfalls.md` | unmodified | `6bf6fa56b309f4350da1087f836fb79fb4b9ca9dea191437e9c8ba0ed4170706` |
| `references/optimization.md` | **modified** | `4853060b6494cc7a09f176baf26194a2b64534740d8a840343e5820705780010` |
| `references/editing-workflow.md` | **modified** | `41d305491387b7958b498db3c1e0289b6167257738102fdd476514394d3c41b6` |

## Modifications

- `optimization.md`
  - Rewrote the SVGO section for SVGO 4.1.0. `removeViewBox: false` is gone because that plugin is not in SVGO 4's `preset-default`, and overriding it only prints a warning.
  - Dropped the unconditional `removeXMLNS`, which breaks standalone `.svg` files.
  - Added `removeScripts`, `removeXlink`, `multipass` and a global `floatPrecision: 2`. This matches `svgo.config.mjs`.
  - Replaced `npm install -g svgo` and in-place `svgo input.svg` with pinned `npx svgo@4.1.0 … -o <new file>`, run only after the user approves.
  - Added a note that `removeScripts` is not a sanitiser.
- `editing-workflow.md`
  - Replaced the "Multi-Variant Preview Page" section with a static contact-sheet workflow (`scripts/render_preview.py sheet`), because `assets/preview.html` is not vendored.
  - Added commands for opening files on Windows (cmd and PowerShell), Linux and macOS.
  - Adapted workflow tips 1, 3 and 5, and added tip 7 (never overwrite originals).
- Both modified files start with an HTML comment naming the source and the change.

## Not vendored

Upstream files left out:
- `SKILL.md`: replaced by our own.
- `references/logo-techniques.md`, `animation.md` and `advanced-techniques.md`: not needed for icon work. Add them from the same commit if needed.
- `assets/preview.html`

## Own files

These are not covered by the upstream licence:
- `SKILL.md`
- `svgo.config.mjs`
- `scripts/check_svg.py`
- `scripts/render_preview.py`
- `scripts/test_check_svg.py`

`check_svg.py` grew out of the stdlib checker in the 2026-10-03 design-skills review (report 03, Appendix C2).
