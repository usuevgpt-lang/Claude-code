# NOTICE — find-skills

- Upstream: https://github.com/vercel-labs/skills — `skills/find-skills/SKILL.md`
- Commit: `18f96ea` (2026-10-02). Licence: MIT, © 2026 Vercel, Inc. (`LICENSE`).
- CLI used by the skill: npm package `skills`, pinned to 1.7.0 (MIT, published 2026-09-17), the version reviewed
  in the 2026-10-03 audit.
- Restored at the owner's request on 2026-10-03 after being removed; local changes follow the audit's
  "if kept" recommendations.

## Local changes
1. Description narrowed to explicit requests to find/install a skill (upstream also triggered on any
   "how do I do X" question).
2. Added the «Rules (НОВАПРОМ)» section: check installed skills first, generic queries only (the CLI sends search
   queries to skills.sh and, unless disabled, telemetry to add-skill.vercel.sh), pinned CLI version, telemetry off via
   `DO_NOT_TRACK=1`, mandatory `novaprom-tool-vetting` review and user approval before install.
3. Install command changed from `npx skills add <pkg> -g -y` (global, no confirmation) to
   `npx skills@1.7.0 add <owner/repo> --skill <name> -a claude-code --copy` (current project, with confirmation).
4. All `npx skills …` examples pinned to `@1.7.0`; `--list` added for looking inside a repository without installing.
5. Popularity checks extended (licence, activity, faked stars); example response and categories adapted to НОВАПРОМ.
6. "No skills found" suggests an in-house skill instead of `npx skills init`.
