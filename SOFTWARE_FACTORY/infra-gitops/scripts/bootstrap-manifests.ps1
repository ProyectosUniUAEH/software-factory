#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Bootstrap manifests from terraform.tfvars values.
    
.DESCRIPTION
    Reads configuration from terraform.tfvars and updates all K8s manifests,
    system-config, and core app configurations so NO hardcoded values remain.
    
    This ensures full reproducibility: anyone can clone this repo, put their
    own credentials in terraform.tfvars, run this script, then terraform apply.

.EXAMPLE
    .\bootstrap-manifests.ps1
    .\bootstrap-manifests.ps1 -TfVarsPath "../terraform/terraform.tfvars" -DryRun
#>
param(
    [string]$TfVarsPath = "$PSScriptRoot/../terraform/terraform.tfvars",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$InfraRoot = (Resolve-Path "$PSScriptRoot/..").Path

# ==============================================================================
# 1. Parse terraform.tfvars
# ==============================================================================
Write-Host "[1/6] Reading terraform.tfvars..." -ForegroundColor Cyan
$tfvars = @{}
foreach ($line in Get-Content $TfVarsPath) {
    if ($line -match '^\s*(\w+)\s*=\s*"(.+)"') {
        $tfvars[$Matches[1]] = $Matches[2]
    }
}

$domain         = $tfvars["domain_name"]
$elasticIp      = $tfvars["elastic_ip"]
$workspace      = $tfvars["bitbucket_workspace"]
$gitUsername     = $tfvars["git_username"]
$dockerUser     = $tfvars["docker_username"]
$email          = $tfvars["bitbucket_email"]

if (-not $domain)    { throw "domain_name not found in terraform.tfvars" }
if (-not $elasticIp) { throw "elastic_ip not found in terraform.tfvars" }
if (-not $workspace) { throw "bitbucket_workspace not found in terraform.tfvars" }

Write-Host "  Domain:    $domain" -ForegroundColor Green
Write-Host "  IP:        $elasticIp" -ForegroundColor Green
Write-Host "  Workspace: $workspace" -ForegroundColor Green
Write-Host "  Docker:    $dockerUser" -ForegroundColor Green
Write-Host ""

# ==============================================================================
# Helper: Simple find-replace in file
# ==============================================================================
$script:changedFiles = [System.Collections.ArrayList]::new()

function ReplaceInFile {
    param([string]$Path, [string]$Find, [string]$Replace)
    if (-not (Test-Path $Path)) {
        Write-Host "  SKIP (not found): $Path" -ForegroundColor Yellow
        return
    }
    $content = [System.IO.File]::ReadAllText($Path)
    if ($content.Contains($Find)) {
        if (-not $DryRun) {
            $newContent = $content.Replace($Find, $Replace)
            [System.IO.File]::WriteAllText($Path, $newContent)
        }
        $rel = $Path.Replace($InfraRoot, "").TrimStart("\", "/")
        Write-Host "  OK: $rel" -ForegroundColor Green
        [void]$script:changedFiles.Add($rel)
    }
}

# ==============================================================================
# 2. Detect current hardcoded domain (auto-detect from existing manifests)
# ==============================================================================
Write-Host "[2/6] Auto-detecting current domain in manifests..." -ForegroundColor Cyan
$apiIngressPath = "$InfraRoot\apps\kaanbal-api\base\ingress.yaml"
$currentDomain = ""
if (Test-Path $apiIngressPath) {
    $ingressContent = Get-Content $apiIngressPath -Raw
    if ($ingressContent -match 'kaanbal-api\.([a-zA-Z0-9\-]+\.[a-zA-Z]{2,})') {
        $currentDomain = $Matches[1]
    }
}
if ($currentDomain -and ($currentDomain -ne $domain)) {
    Write-Host "  Old domain: $currentDomain -> New domain: $domain" -ForegroundColor Yellow
} elseif ($currentDomain -eq $domain) {
    Write-Host "  Domain already correct: $domain" -ForegroundColor Green
} else {
    Write-Host "  Could not detect current domain, skipping domain replacement" -ForegroundColor Yellow
}

# ==============================================================================
# 3. Update Core App Manifests
# ==============================================================================
Write-Host "[3/6] Updating core app manifests..." -ForegroundColor Cyan

if ($currentDomain -and ($currentDomain -ne $domain)) {
    # kaanbal-api ingress
    ReplaceInFile -Path ("$InfraRoot\apps\kaanbal-api\base\ingress.yaml") -Find "kaanbal-api.$currentDomain" -Replace "kaanbal-api.$domain"
    
    # kaanbal-console ingress
    ReplaceInFile -Path ("$InfraRoot\apps\kaanbal-console\base\ingress.yaml") -Find "kaanbal-console.$currentDomain" -Replace "kaanbal-console.$domain"
    
    # kaanbal-api deployment: DOMAIN env var value
    $apiDeployPath2 = "$InfraRoot\apps\kaanbal-api\base\deployment.yaml"
    ReplaceInFile -Path $apiDeployPath2 -Find "value: `"$currentDomain`"" -Replace "value: `"$domain`""
    
    # User-deployed app ingresses
    $coreApps = @("kaanbal-api", "kaanbal-console", "datastore", "vault", "tailscale-operator")
    Get-ChildItem ("$InfraRoot\apps") -Directory | Where-Object { $coreApps -notcontains $_.Name } | ForEach-Object {
        $appIngress = "$($_.FullName)\base\ingress.yaml"
        if (Test-Path $appIngress) {
            ReplaceInFile -Path $appIngress -Find "$($_.Name).$currentDomain" -Replace "$($_.Name).$domain"
        }
    }
}

# kaanbal-api deployment: BITBUCKET_WORKSPACE
$apiDeployPath = "$InfraRoot\apps\kaanbal-api\base\deployment.yaml"
if (Test-Path $apiDeployPath) {
    $deployContent = [System.IO.File]::ReadAllText($apiDeployPath)
    # Find current workspace in file
    if ($deployContent -match 'BITBUCKET_WORKSPACE[\s\S]*?value:\s*"([^"]+)"') {
        $oldWs = $Matches[1]
        if ($oldWs -ne $workspace) {
            ReplaceInFile -Path $apiDeployPath -Find "value: `"$oldWs`"" -Replace "value: `"$workspace`""
            ReplaceInFile -Path $apiDeployPath -Find "bitbucket.org/$oldWs/" -Replace "bitbucket.org/$workspace/"
        }
    }
}

# ==============================================================================
# 4. Update system-config.yaml
# ==============================================================================
Write-Host "[4/6] Updating system-config.yaml..." -ForegroundColor Cyan
$sysConfigPath = "$InfraRoot\core\config\system-config.yaml"

if ($currentDomain -and ($currentDomain -ne $domain)) {
    ReplaceInFile -Path $sysConfigPath -Find "domain: `"$currentDomain`"" -Replace "domain: `"$domain`""
}

# Detect old git workspace in system-config
if (Test-Path $sysConfigPath) {
    $sysContent = [System.IO.File]::ReadAllText($sysConfigPath)
    if ($sysContent -match 'git\.workspace:\s*"([^"]+)"') {
        $oldGitWs = $Matches[1]
        if ($oldGitWs -ne $workspace) {
            ReplaceInFile -Path $sysConfigPath -Find "git.workspace: `"$oldGitWs`"" -Replace "git.workspace: `"$workspace`""
        }
    }
}

# ==============================================================================
# 5. Update helper scripts (test scripts with old IPs)
# ==============================================================================
Write-Host "[5/6] Updating helper scripts..." -ForegroundColor Cyan
$testDbScript = "$InfraRoot\scripts\test-db-connectivity.ps1"
if (Test-Path $testDbScript) {
    $content = [System.IO.File]::ReadAllText($testDbScript)
    if ($content -match 'MasterIP\s*=\s*"([^"]+)"') {
        $oldIp = $Matches[1]
        if ($oldIp -ne $elasticIp) {
            ReplaceInFile -Path $testDbScript -Find $oldIp -Replace $elasticIp
        }
    }
}

# ==============================================================================
# 6. Summary
# ==============================================================================
Write-Host ""
Write-Host "[6/6] Summary" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "  DRY RUN - No files were modified" -ForegroundColor Yellow
} elseif ($script:changedFiles.Count -eq 0) {
    Write-Host "  No changes needed - manifests already up to date" -ForegroundColor Green
} else {
    Write-Host "  $($script:changedFiles.Count) file(s) updated:" -ForegroundColor Green
    foreach ($f in $script:changedFiles) {
        Write-Host "    - $f" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Review changes: git diff" -ForegroundColor White
Write-Host "  2. Commit: git add -A ; git commit -m 'chore: bootstrap manifests for $domain'" -ForegroundColor White
Write-Host "  3. Push: git push origin main" -ForegroundColor White
Write-Host "  4. cd terraform ; terraform init ; terraform apply" -ForegroundColor White
Write-Host "  5. Wait ~10 min for cluster bootstrap" -ForegroundColor White
Write-Host "  6. Vault auto-init Job runs automatically" -ForegroundColor White
Write-Host "  7. Configure Settings in Kaanbal Console UI" -ForegroundColor White
Write-Host ""
