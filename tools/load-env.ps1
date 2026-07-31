# Carga variables Kaanbal: global ~/.kaanbal/env + .env.local del repo
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$globalEnv = Join-Path $env:USERPROFILE ".kaanbal\env"
$localEnv = Join-Path $RepoRoot ".env.local"

function Import-DotEnv($path) {
    if (-not (Test-Path $path)) { return }
    Get-Content $path | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) {
            $name = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

Import-DotEnv $globalEnv
Import-DotEnv $localEnv

Write-Host "Env cargado desde:"
if (Test-Path $globalEnv) { Write-Host "  $globalEnv" }
if (Test-Path $localEnv) { Write-Host "  $localEnv" }
if (-not (Test-Path $globalEnv) -and -not (Test-Path $localEnv)) {
    Write-Host "  (ninguno — copia tools/env.example a ~/.kaanbal/env)"
}
