# Installs Claude Code skills and plugins for the current Windows user.
# Skills are copied to %USERPROFILE%\.claude\skills, plugin marketplaces
# are registered in %USERPROFILE%\.claude\settings.json, so they work in
# every folder on this machine, not just this repository.
#
# Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1

$ErrorActionPreference = 'Stop'

$repoRoot  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$claudeDir = Join-Path $env:USERPROFILE '.claude'
$skillsSrc = Join-Path $repoRoot '.claude\skills'
$skillsDst = Join-Path $claudeDir 'skills'

# 1. Skills: copy into the user-level skills folder
New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null
Copy-Item -Recurse -Force -Path (Join-Path $skillsSrc '*') -Destination $skillsDst
Write-Host "[OK] Skills installed to $skillsDst"

# 2. Plugins: register marketplaces and enable plugins in user settings
$settingsPath = Join-Path $claudeDir 'settings.json'
if (Test-Path $settingsPath) {
    Copy-Item -Force $settingsPath "$settingsPath.bak"
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    Write-Host "[OK] Existing settings backed up to $settingsPath.bak"
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

$settings | ConvertTo-Json -Depth 10 | Set-Content -Path $settingsPath -Encoding UTF8
Write-Host "[OK] Plugins registered in $settingsPath"
Write-Host ''
Write-Host 'Done! Restart Claude Code. On first start it will ask to trust the'
Write-Host 'plugin marketplaces (thedotmack, superpowers-marketplace, impeccable)'
Write-Host '- confirm to finish the plugin installation.'
