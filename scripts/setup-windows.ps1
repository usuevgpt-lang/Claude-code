# Installs the NOVAPROM Claude Code environment for the current Windows user.
# The work is done by scripts/install_novaprom.py (one installer for Windows, macOS, Linux and cloud):
# skills, subagents, the safety hook and the routing rules (global/NOVAPROM.md) are copied to
# %USERPROFILE%\.claude and become available in EVERY project (Claude Code CLI and the Code tab of the
# Claude app); docs/settings.proposed.json is merged into %USERPROFILE%\.claude\settings.json.
# Replaced skills/agents are kept in %USERPROFILE%\.claude\novaprom-backups\<timestamp>;
# CLAUDE.md and settings.json get a *.bak-<timestamp> copy. Safe to run again (updates only what changed).
#
# Easiest: double-click scripts\install-windows.cmd (it also runs "git pull" first).
# Or from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1          install / update
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1 -Check   only check

param([switch]$Check)

$ErrorActionPreference = 'Continue'
$repoRoot  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$installer = Join-Path $repoRoot 'scripts\install_novaprom.py'
$req       = Join-Path $repoRoot 'scripts\requirements-novaprom.txt'

# Python is required by the installer, the safety hook and the calculation scripts.
# "python" from WindowsApps is the Microsoft Store stub, not a real interpreter.
$python = Get-Command python -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*\WindowsApps\*' } | Select-Object -First 1
if (-not $python) {
    Write-Warning 'Python not found (or only the Microsoft Store stub). Install Python 3.11+ from python.org and tick "Add python.exe to PATH" (the safety hook calls "python"). Then run this script again.'
    exit 1
}
$py = $python.Source
Write-Host "[OK] Python: $(& $py --version) ($py)"

if ($Check) {
    & $py $installer --check
    exit $LASTEXITCODE
}

& $py $installer
$rc = $LASTEXITCODE

# Python packages for the calculation scripts: ask first, install for the current user only.
& $py -c "import importlib.util as u, sys; sys.exit(0 if all(u.find_spec(m) for m in ('CoolProp','openpyxl','ezdxf','matplotlib','PIL','yaml')) else 1)"
if ($LASTEXITCODE -ne 0) {
    $answer = Read-Host 'Install the Python packages for the calculation scripts now (pip install --user -r scripts\requirements-novaprom.txt)? [y/N]'
    if ($answer -match '^[yY]') {
        & $py -m pip install --user -r $req
        & $py $installer --check
    } else {
        Write-Host "Later:  python -m pip install --user -r `"$req`""
    }
}

Write-Host ''
Write-Host 'Next steps (details: docs\ARCHITECTURE.md, section 7):'
Write-Host '  1. Restart Claude Code (CLI or the Code tab of the Claude app). Plugins from settings install on start;'
Write-Host '     confirm trust for the plugin marketplaces if asked. Check in Claude Code: /skills, /agents, /hooks, /plugin.'
Write-Host '  2. Document skills (docx, xlsx, pptx, pdf, skill-creator) and your own claude.ai skills (lead-triage,'
Write-Host '     humanizer) come from your Claude account: sign in with /login using the Claude account (not an API key);'
Write-Host '     they are listed in /plugin as ...@synced. Enable them in claude.ai Settings > Capabilities.'
Write-Host '  3. claude-mem keeps a local memory of every session in %USERPROFILE%\.claude-mem. Keep customer-document'
Write-Host '     folders out of it with CLAUDE_MEM_EXCLUDED_PROJECTS - see docs\ARCHITECTURE.md, section 7.'
Write-Host '  4. agent-skills (or superpowers - pick one, they overlap) / impeccable: enable only in a code project'
Write-Host '     (website, scripts) - add to that project''s .claude\settings.local.json:'
Write-Host '     { "enabledPlugins": { "agent-skills@novaprom": true } }'
Write-Host '  5. List protected folders (one path per line) in %USERPROFILE%\.claude\novaprom-protected-paths.txt'
Write-Host '  6. To update later: double-click scripts\install-windows.cmd (git pull + this script).'
exit $rc
