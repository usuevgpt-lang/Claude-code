---
name: find-skills
description: >-
  Find and install agent skills from the open skills ecosystem (skills.sh, `npx skills`) when the user explicitly asks
  to find, search for or install a skill — "find a skill for X", "is there a skill for X", "найди скилл для …",
  "есть ли готовый навык …", "установи скилл …". Every install goes through the novaprom-tool-vetting review and the
  user's approval. Not for ordinary "how do I do X" questions — answer those directly or with existing skills.
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.
Local version for НОВАПРОМ: based on vercel-labs/skills `find-skills` (MIT), with safety changes listed in `NOTICE.md`.

## Rules (НОВАПРОМ)

1. **Check what is already installed first** (`/skills`, the registry in `docs/ARCHITECTURE.md` of the config repo,
   official sources: `/plugin` → Discover on `claude-plugins-official`, `anthropics/skills`). Do not install a skill
   that duplicates an existing one.
2. **Generic search queries only.** Never put customer names, object names, tender numbers, prices or document titles
   into `npx skills find` or skills.sh — the query leaves the company.
3. **Pinned CLI:** always `npx skills@1.7.0 …`, never the bare `npx skills` (that runs whatever version was published last).
   Telemetry of the CLI is off through `DO_NOT_TRACK=1` in the Claude Code settings `env`; if running the CLI by hand,
   set it in the shell first (PowerShell: `$env:DO_NOT_TRACK = "1"`).
4. **Never `-y`. No `-g` by default.** Install into the current project (`.claude/skills`), with `-a claude-code --copy`
   (copies files instead of symlinks — works on Windows without admin rights). Global install only on the user's
   explicit request.
5. **Review before install:** run the `novaprom-tool-vetting` skill on the chosen skill (read the whole `SKILL.md` and
   every bundled script on GitHub). Reject skills that download/execute remote code, add hooks, phone home, ask for
   credentials or have "use for ANY task / before every response" triggers.
6. **Install only after the user says yes** to the specific skill and the vetting result. The safety hook will also ask
   for confirmation of every `npx` call.

## When to Use This Skill

Use this skill when the user:

- Says "find a skill for X", "is there a skill for X", "найди скилл/навык для …"
- Asks to install a specific skill from skills.sh or GitHub
- Explicitly wants to extend Claude's capabilities with a ready-made skill

## What is the Skills CLI?

The Skills CLI (`npx skills`) is the package manager for the open agent skills ecosystem. Skills are modular packages that extend agent capabilities with specialized knowledge, workflows, and tools.

**Key commands (pinned version):**

- `npx skills@1.7.0 find [query] [--owner <owner>]` - Search for skills by keyword, optionally scoped to a GitHub owner
- `npx skills@1.7.0 add <owner/repo> --list` - List the skills in a repository without installing
- `npx skills@1.7.0 add <owner/repo> --skill <name> -a claude-code --copy` - Install one skill into the current project
- `npx skills@1.7.0 update` - Update installed skills (re-run the vetting on what changed)

**Browse skills at:** https://skills.sh/

## How to Help Users Find Skills

### Step 1: Understand What They Need

When a user asks for a skill, identify:

1. The domain (e.g., documents, design, testing, data)
2. The specific task
3. Whether an installed skill already covers it (rule 1) — if yes, say so and stop

### Step 2: Check the Leaderboard and Official Sources First

Before running a CLI search, check the [skills.sh leaderboard](https://skills.sh/) and the official Anthropic sources.
The leaderboard ranks skills by total installs, surfacing the most popular and battle-tested options.

For example:
- `anthropics/skills` — document processing, frontend design (official)
- `vercel-labs/agent-skills` — React, Next.js, web design

### Step 3: Search for Skills

If those don't cover the need, run the find command with a **generic** query (rule 2):

```bash
npx skills@1.7.0 find [query] [--owner <owner>]
```

For example:

- "найди скилл для работы с DXF" → `npx skills@1.7.0 find dxf`
- "is there a skill for PR reviews?" → `npx skills@1.7.0 find pr review`
- "нужен навык для changelog" → `npx skills@1.7.0 find changelog`

### Step 4: Verify Quality Before Recommending

**Do not recommend a skill based solely on search results.** Always verify:

1. **Install count** — Prefer skills with 1K+ installs. Be cautious with anything under 100.
2. **Source reputation** — Official sources (`anthropics`, `vercel-labs`, `microsoft`) are more trustworthy than unknown authors.
3. **GitHub stars and activity** — A repo with <100 stars, no LICENSE file or no recent commits deserves skepticism.
   Popularity can be faked (stars with 0 forks, bot commits) — popularity alone is not a reason to install.

### Step 5: Present Options to the User

When you find relevant skills, present them with:

1. The skill name and what it does
2. The install count, source repository, licence
3. What overlaps with already installed skills
4. A link to learn more at skills.sh

Example response:

```
Нашёл подходящий навык: "react-best-practices" (vercel-labs/agent-skills, MIT, 185K установок) —
рекомендации по производительности React/Next.js. Пересечений с установленными навыками нет.

Перед установкой проверю его код (novaprom-tool-vetting). Проверить и установить в текущий проект?
Подробнее: https://skills.sh/vercel-labs/agent-skills/react-best-practices
```

### Step 6: Vet, Then Install With the User's Approval

1. Run `novaprom-tool-vetting` on the chosen skill and show the verdict.
2. If the user approves, install it into the current project:

```bash
npx skills@1.7.0 add <owner/repo> --skill <skill-name> -a claude-code --copy
```

3. Show which files were added (`git status` / list of `.claude/skills/<name>/`).
4. For a skill the user wants everywhere: offer to vendor it into the config repo `usuevgpt-lang/Claude-code`
   (`.claude/skills/<name>/` + `NOTICE.md` with source, commit, licence) instead of a global `-g` install.

## Common Skill Categories

| Category        | Example Queries                          |
| --------------- | ---------------------------------------- |
| Documents       | pdf, docx, xlsx, pptx, ocr               |
| Engineering     | cad, dxf, step, engineering, calculation |
| Web Development | php, javascript, css, seo, accessibility |
| Testing         | testing, playwright, e2e                 |
| Design          | ui, ux, svg, icons, design-system        |
| Productivity    | workflow, automation, git                |

## Tips for Effective Searches

1. **Use specific but generic keywords**: "pdf ocr" is better than just "pdf"; never include confidential details
2. **Try alternative terms**: if "deploy" doesn't work, try "deployment" or "ci-cd"
3. **Search in English and Russian terms**: most skills are described in English

## When No Skills Are Found

If no relevant skills exist:

1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using the installed skills and general capabilities
3. Suggest creating an in-house skill (Anthropic `skill-creator`, or following the `novaprom-*` skills as a template)
