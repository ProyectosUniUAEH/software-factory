param([string]$Token = $env:GITHUB_TOKEN)
if (-not $Token) { throw "Define GITHUB_TOKEN en tu entorno (no lo hardcodees)." }
$headers = @{ Authorization = "Bearer $Token"; Accept = "application/vnd.github+json" }
$owner = "futurefarms-softwarefactory"
$repo  = "homepage-api"

function Update-RepoFile {
    param($Path, $LocalFile, $Msg)
    $content = Get-Content -Raw -Path $LocalFile
    $cur = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$owner/$repo/contents/$Path"
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($content))
    $body = @{ message = $Msg; content = $b64; sha = $cur.sha; branch = "main" } | ConvertTo-Json
    $resp = Invoke-RestMethod -Headers $headers -Method Put -Uri "https://api.github.com/repos/$owner/$repo/contents/$Path" -Body $body -ContentType "application/json"
    Write-Host ("Updated {0} -> {1}" -f $Path, $resp.commit.sha)
}

$labs = Split-Path -Parent $MyInvocation.MyCommand.Path
Update-RepoFile "app/main.py" (Join-Path $labs "new_main.py") "feat: add /db-check endpoint validating MongoDB connectivity"
Update-RepoFile "requirements.txt" (Join-Path $labs "new_requirements.txt") "feat: add motor for async MongoDB driver"
