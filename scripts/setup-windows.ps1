# Installs the NOVAPROM Claude Code environment for the current Windows user.
# Skills, subagents and the safety hook are copied to %USERPROFILE%\.claude,
# the routing rules (global/NOVAPROM.md) are imported from %USERPROFILE%\.claude\CLAUDE.md,
# Replaced skills/agents are moved to %USERPROFILE%\.claude\novaprom-backups\<timestamp>;
# CLAUDE.md and settings.json get a *.bak-<timestamp> copy next to them.
#
# Security settings from docs/settings.proposed.json (hook, ask/deny rules, telemetry off,
# plugins) are merged into %USERPROFILE%\.claude\settings.json by scripts/merge_settings.py.
# Retired skills (find-skills, task-observer) are moved aside; claude-mem is disabled.
#
# Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1

$ErrorActionPreference = 'Stop'

$repoRoot  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$claudeDir = Join-Path $env:USERPROFILE '.claude'
$stamp     = Get-Date -Format 'yyyyMMdd-HHmmss'
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
# Backups go OUTSIDE skills\ and agents\: a copied skill folder left in skills\ would be loaded
# by Claude Code as a duplicate skill.
$backupDir = Join-Path $claudeDir "novaprom-backups\$stamp"

function Backup-Item($path, $category) {
    $dst = Join-Path $backupDir $category
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Move-Item -Force $path (Join-Path $dst (Split-Path -Leaf $path))
}

function Copy-Tree($src, $dst) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Get-ChildItem -Path $src -Directory | ForEach-Object {
        $target = Join-Path $dst $_.Name
        if (Test-Path $target) { Backup-Item $target 'skills' }
        Copy-Item -Recurse -Force $_.FullName $target
    }
}

# 0. Python is required by the calculation scripts and by the safety hook
# "python" from WindowsApps is the Microsoft Store stub, not a real interpreter.
$python = Get-Command python -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*\WindowsApps\*' } | Select-Object -First 1
if ($python) {
    $pyVersion = cmd /c "python --version 2>&1"
    Write-Host "[OK] Python: $pyVersion ($($python.Source))"
} else {
    $python = $null
    Write-Warning 'Python not found (or only the Microsoft Store stub). Install Python 3.11+ from python.org and tick "Add python.exe to PATH". The safety hook calls "python": without it the hook does not run and the calculation scripts do not work. Then run this script again.'
}

# 1. Skills -> %USERPROFILE%\.claude\skills (a replaced skill folder is moved to $backupDir)
Copy-Tree (Join-Path $repoRoot '.claude\skills') (Join-Path $claudeDir 'skills')
Write-Host "[OK] Skills installed to $claudeDir\skills"

# 2. Subagents -> %USERPROFILE%\.claude\agents
$agentsDst = Join-Path $claudeDir 'agents'
New-Item -ItemType Directory -Force -Path $agentsDst | Out-Null
Get-ChildItem (Join-Path $repoRoot '.claude\agents\*.md') | ForEach-Object {
    $target = Join-Path $agentsDst $_.Name
    if (Test-Path $target) { Backup-Item $target 'agents' }
    Copy-Item -Force $_.FullName $target
}
Write-Host "[OK] Subagents installed to $agentsDst"

# 3. Safety hook script -> %USERPROFILE%\.claude\hooks (activated by the settings merged in step 6)
$hooksDst = Join-Path $claudeDir 'hooks'
New-Item -ItemType Directory -Force -Path $hooksDst | Out-Null
Copy-Item -Force (Join-Path $repoRoot '.claude\hooks\novaprom_guard.py') $hooksDst
Write-Host "[OK] Hook script copied to $hooksDst"

# 4. Routing rules: copy global/NOVAPROM.md and import it from the user CLAUDE.md
$novaDir = Join-Path $claudeDir 'novaprom'
New-Item -ItemType Directory -Force -Path $novaDir | Out-Null
Copy-Item -Force (Join-Path $repoRoot 'global\NOVAPROM.md') $novaDir
$userClaudeMd = Join-Path $claudeDir 'CLAUDE.md'
$importLine = '@~/.claude/novaprom/NOVAPROM.md'
if (Test-Path $userClaudeMd) {
    $content = [System.IO.File]::ReadAllText($userClaudeMd)   # detects UTF-8/UTF-16 by BOM
    if ($content -notmatch [regex]::Escape($importLine)) {
        Copy-Item -Force $userClaudeMd "$userClaudeMd.bak-$stamp"
        $head = ([System.IO.File]::ReadAllBytes($userClaudeMd) | Select-Object -First 2) -join ','
        if (($head -eq '255,254') -or ($head -eq '254,255')) {
            # UTF-16 file: rewrite as UTF-8 so the appended line does not mix encodings
            [System.IO.File]::WriteAllText($userClaudeMd, $content, $utf8NoBom)
        }
        [System.IO.File]::AppendAllText($userClaudeMd, "`r`n# NOVAPROM`r`n$importLine`r`n", $utf8NoBom)
    }
} else {
    [System.IO.File]::WriteAllText($userClaudeMd, "# NOVAPROM`r`n$importLine`r`n", $utf8NoBom)
}
Write-Host "[OK] Routing rules imported in $userClaudeMd"

# 5. Remove skills retired from the environment (find-skills, task-observer).
#    They are moved to $backupDir, not deleted.
foreach ($old in 'find-skills', 'task-observer') {
    $path = Join-Path $claudeDir "skills\$old"
    if (Test-Path $path) {
        Backup-Item $path 'skills-removed'
        Write-Host "[OK] Retired skill $old moved to $backupDir\skills-removed"
    }
}

# 6. Settings: security hook, ask/deny rules, telemetry off, plugins
#    (frontend-design and novaprom-marketing on; claude-mem off;
#    superpowers and impeccable off globally - enable them per code project).
#    The merge keeps everything else in settings.json and makes a backup first.
$settingsPath = Join-Path $claudeDir 'settings.json'
if ($python) {
    & python (Join-Path $repoRoot 'scripts\merge_settings.py') `
        --proposed (Join-Path $repoRoot 'docs\settings.proposed.json') `
        --target $settingsPath `
        --disable-plugin 'claude-mem@thedotmack' `
        --drop-marketplace 'thedotmack'
    if ($LASTEXITCODE -ne 0) { Write-Warning "Settings were not changed: fix $settingsPath and run the script again." }
} else {
    Write-Warning 'Settings not merged (Python missing). Install Python and run the script again.'
}

Write-Host ''
Write-Host 'Done! Next steps (see docs\ARCHITECTURE.md, section 7):'
Write-Host '  1. Restart Claude Code; confirm trust for the plugin marketplaces (frontend-design and'
Write-Host '     novaprom-marketing install automatically; or: /plugin install frontend-design@claude-plugins-official).'
Write-Host '  2. Remove claude-mem completely:'
Write-Host '       /plugin uninstall claude-mem@thedotmack'
Write-Host '       /plugin marketplace remove thedotmack'
Write-Host '     then close Claude Code and delete %USERPROFILE%\.claude-mem (it may contain copies of customer documents).'
Write-Host '  3. superpowers / impeccable: enable only in a code project (website, scripts) - add to that project''s'
Write-Host '     .claude\settings.local.json:  { "enabledPlugins": { "superpowers@superpowers-marketplace": true } }'
Write-Host '  4. List protected folders (one path per line) in %USERPROFILE%\.claude\novaprom-protected-paths.txt'
Write-Host '  5. Python packages for calculations:  python -m pip install CoolProp openpyxl ezdxf==1.4.4 matplotlib'
Write-Host "Backups of replaced files: $backupDir"
