# NOTICE — anydoc

- Upstream skill: https://github.com/firecrawl/anydoc — `skills/convert-documents-to-markdown/SKILL.md`
- Commit: `261fc25` (2026-08-27). Licence: MIT, © 2026 Sideguide Technologies Inc. (Firecrawl) — `LICENSE`.
- CLI: npm `@firecrawl/anydoc` 0.2.4 (published 2026-08-27). Reviewed 2026-10-03: no install scripts, no
  dependencies, prebuilt native binaries as optional platform packages, no telemetry. The only network call is
  Firecrawl Parse (`https://api.firecrawl.dev/v2/parse`, overridable by `FIRECRAWL_API_URL`), made only with
  `--ocr hosted`; it uploads the whole PDF.

## Local changes
1. Skill renamed `anydoc` (as the user calls it); description and triggers extended with НОВАПРОМ document types,
   Russian phrases, and a pointer to docx/xlsx/pptx/pdf for creating and editing files.
2. Added «Правила НОВАПРОМ»: local conversion only, `--ocr hosted` forbidden for confidential documents and allowed
   only with the user's explicit consent; pinned CLI version; work on copies.
3. All commands pinned to `@firecrawl/anydoc@0.2.4`; option to install the CLI once instead of `npx` each time.
4. Exit code 3 (scanned pages) routed to local OCR with the `pdf` skill instead of the hosted OCR instruction.
5. Library usage note: do not set the `ocr` option.
