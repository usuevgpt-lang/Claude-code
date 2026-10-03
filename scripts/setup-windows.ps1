# Installs the NOVAPROM Claude Code environment for the current Windows user.
# Skills, subagents and the safety hook are copied to %USERPROFILE%\.claude,
# the routing rules (global/NOVAPROM.md) are imported from %USERPROFILE%\.claude\CLAUDE.md,
# plugin marketplaces are registered in %USERPROFILE%\.claude\settings.json.
# Existing files are backed up (*.bak-<timestamp>) before they are overwritten.
#
# Security settings (hooks, ask/deny permission rules) are NOT applied automatically:
# review docs/settings.proposed.json and docs/ARCHITECTURE.md (section "Настройки безопасности")
# and apply them yourself.
#
# Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1

$ErrorActionPreference = 'Stop'

$repoRoot  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$claudeDir = Join-Path $env:USERPROFILE '.claude'
$stamp     = Get-Date -Format 'yyyyMMdd-HHmmss'
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Copy-Tree($src, $dst) {
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Get-ChildItem -Path $src -Directory | ForEach-Object {
        $target = Join-Path $dst $_.Name
        if (Test-Path $target) {
            Copy-Item -Recurse -Force $target "$target.bak-$stamp"
            Remove-Item -Recurse -Force $target
        }
        Copy-Item -Recurse -Force $_.FullName $target
    }
}

# 0. Python is required by the calculation scripts and by the safety hook
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Write-Host "[OK] Python: $(& python --version 2>&1)"
} else {
    Write-Warning 'Python not found. Install Python 3.11+ from python.org (tick "Add python.exe to PATH"). Without it the calculation scripts and the safety hook will not run.'
}

# 1. Skills -> %USERPROFILE%\.claude\skills (each skill folder is replaced, the old one is backed up)
Copy-Tree (Join-Path $repoRoot '.claude\skills') (Join-Path $claudeDir 'skills')
Write-Host "[OK] Skills installed to $claudeDir\skills"

# 2. Subagents -> %USERPROFILE%\.claude\agents
$agentsDst = Join-Path $claudeDir 'agents'
New-Item -ItemType Directory -Force -Path $agentsDst | Out-Null
Get-ChildItem (Join-Path $repoRoot '.claude\agents\*.md') | ForEach-Object {
    $target = Join-Path $agentsDst $_.Name
    if (Test-Path $target) { Copy-Item -Force $target "$target.bak-$stamp" }
    Copy-Item -Force $_.FullName $target
}
Write-Host "[OK] Subagents installed to $agentsDst"

# 3. Safety hook script -> %USERPROFILE%\.claude\hooks (activated by the settings, see docs)
$hooksDst = Join-Path $claudeDir 'hooks'
New-Item -ItemType Directory -Force -Path $hooksDst | Out-Null
Copy-Item -Force (Join-Path $repoRoot '.claude\hooks\novaprom_guard.py') $hooksDst
Write-Host "[OK] Hook script copied to $hooksDst (not activated automatically)"

# 4. Routing rules: copy global/NOVAPROM.md and import it from the user CLAUDE.md
$novaDir = Join-Path $claudeDir 'novaprom'
New-Item -ItemType Directory -Force -Path $novaDir | Out-Null
Copy-Item -Force (Join-Path $repoRoot 'global\NOVAPROM.md') $novaDir
$userClaudeMd = Join-Path $claudeDir 'CLAUDE.md'
$importLine = '@~/.claude/novaprom/NOVAPROM.md'
if (Test-Path $userClaudeMd) {
    $content = Get-Content $userClaudeMd -Raw
    if ($content -notmatch [regex]::Escape($importLine)) {
        Copy-Item -Force $userClaudeMd "$userClaudeMd.bak-$stamp"
        [System.IO.File]::AppendAllText($userClaudeMd, "`r`n# НОВАПРОМ`r`n$importLine`r`n", $utf8NoBom)
    }
} else {
    [System.IO.File]::WriteAllText($userClaudeMd, "# НОВАПРОМ`r`n$importLine`r`n", $utf8NoBom)
}
Write-Host "[OK] Routing rules imported in $userClaudeMd"

# 5. Plugins: register marketplaces and enable plugins in user settings (unchanged behaviour)
$settingsPath = Join-Path $claudeDir 'settings.json'
if (Test-Path $settingsPath) {
    Copy-Item -Force $settingsPath "$settingsPath.bak-$stamp"
    $settings = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "[OK] Existing settings backed up to $settingsPath.bak-$stamp"
} else {
    $settings = [pscustomobject]@{}
}

foreach ($key in 'extraKnownMarketplaces', 'enabledPlugins') {
    if (-not $settings.PSObject.Properties[$key]) {
        $settings | Add-Member -MemberType NoteProperty -Name $key -Value ([pscustomobject]@{})
    }
}

$marketplaces = @{
    'thedotmack'              = 'thedotmack/claude-mem'
    'superpowers-marketplace' = 'obra/superpowers-marketplace'
    'impeccable'              = 'pbakaus/impeccable'
}
foreach ($name in $marketplaces.Keys) {
    $entry = [pscustomobject]@{
        source = [pscustomobject]@{ source = 'github'; repo = $marketplaces[$name] }
    }
    if ($settings.extraKnownMarketplaces.PSObject.Properties[$name]) {
        $settings.extraKnownMarketplaces.PSObject.Properties.Remove($name)
    }
    $settings.extraKnownMarketplaces | Add-Member -MemberType NoteProperty -Name $name -Value $entry
}

$plugins = @('claude-mem@thedotmack', 'superpowers@superpowers-marketplace', 'impeccable@impeccable')
foreach ($plugin in $plugins) {
    if ($settings.enabledPlugins.PSObject.Properties[$plugin]) {
        $settings.enabledPlugins.PSObject.Properties.Remove($plugin)
    }
    $settings.enabledPlugins | Add-Member -MemberType NoteProperty -Name $plugin -Value $true
}

# write without BOM (PowerShell 5.1 Set-Content -Encoding UTF8 adds one)
[System.IO.File]::WriteAllText($settingsPath, ($settings | ConvertTo-Json -Depth 10), $utf8NoBom)
Write-Host "[OK] Plugins registered in $settingsPath"

Write-Host ''
Write-Host 'Done! Next steps (see docs\ARCHITECTURE.md):'
Write-Host '  1. Restart Claude Code; confirm trust for the plugin marketplaces.'
Write-Host '  2. Install the official design plugin:  /plugin install frontend-design@claude-plugins-official'
Write-Host '  3. Marketing plugin (website/marketing work):'
Write-Host '       /plugin marketplace add usuevgpt-lang/Claude-code'
Write-Host '       /plugin install novaprom-marketing@novaprom'
Write-Host '  4. Review docs\settings.proposed.json and add the hooks/permissions to your settings.'
Write-Host '  5. List protected folders (one path per line) in %USERPROFILE%\.claude\novaprom-protected-paths.txt'
Write-Host '  6. Python packages for calculations:  python -m pip install CoolProp openpyxl ezdxf==1.4.4 matplotlib'
