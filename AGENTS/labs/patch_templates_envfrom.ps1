#!/usr/bin/env pwsh
<#
Patch base/deployment.yaml in kaanbal-templates so generated apps load
their secretGenerator-produced Secret via envFrom.
Engine-agnostic: works for MongoDB, Postgres, MySQL bindings (env var names
are uniform: {APP}_DB_HOST/PORT/USER/PASSWORD/DATABASE/URI).
#>
param([string]$Token = $env:GITHUB_TOKEN)
if (-not $Token) { throw "Define GITHUB_TOKEN en tu entorno (no lo hardcodees)." }
$headers = @{ Authorization = "Bearer $Token"; Accept = "application/vnd.github+json" }
$owner = "futurefarms-softwarefactory"
$repo  = "kaanbal-templates"

$paths = @(
    "fastapi-api/k8s/base/deployment.yaml",
    "templates/backend/fastapi-api/k8s/base/deployment.yaml",
    "templates/frontend/react-spa/k8s/base/deployment.yaml",
    "vue3-spa/k8s/base/deployment.yaml"
)

function Add-EnvFrom([string]$yaml) {
    if ($yaml -match "(?ms)^\s+envFrom:") { return $yaml }
    # Insert envFrom right after the first 'ports:' block (matches '            - containerPort: N')
    $pattern = "(?ms)(\s+ports:\s*\n\s+- containerPort:\s+\d+(\s*\n\s+name:.*)?)(\s*\n\s+resources:)"
    $envBlock = "`n          envFrom:`n            - secretRef:`n                name: placeholder-app-secrets`n                optional: true"
    return [Regex]::Replace($yaml, $pattern, "`$1$envBlock`$3", 1)
}

foreach ($p in $paths) {
    $cur  = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$owner/$repo/contents/$p"
    $orig = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($cur.content))
    $new  = Add-EnvFrom $orig
    if ($new -eq $orig) { Write-Host "SKIP (already has envFrom or pattern not matched): $p"; continue }
    $b64  = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($new))
    $body = @{ message = "fix: load app secrets via envFrom (DB bindings - Lesson #5)"; content = $b64; sha = $cur.sha; branch = "main" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Headers $headers -Method Put -Uri "https://api.github.com/repos/$owner/$repo/contents/$p" -Body $body -ContentType "application/json"
    Write-Host ("OK {0} -> {1}" -f $p, $resp.commit.sha)
}
