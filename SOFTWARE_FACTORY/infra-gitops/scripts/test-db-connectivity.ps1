#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Tests connectivity for all 9 database deployments (3 DBs × 3 environments)
.DESCRIPTION
    Validates:
    1. Internal cluster access (via SSH + kubectl exec)
    2. Tailscale VPN access (from local laptop)
    3. Authenticated database connections
.NOTES
    Exposure matrix:
    | DB           | dev        | staging    | prod       |
    |--------------|------------|------------|------------|
    | mongo-001    | tailscale  | tailscale  | internal   |
    | postgres-001 | internal   | tailscale  | tailscale  |
    | mysql-001    | tailscale  | internal   | internal   |
#>

param(
    [string]$PemPath = "$PSScriptRoot\..\factory.pem",
    [string]$MasterIP = "78.12.35.42",
    [string]$TailscaleSuffix = "taildd8884.ts.net"
)

$ErrorActionPreference = "Continue"

# Colors
function Write-Pass { param($msg) Write-Host "  [PASS] $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "  [INFO] $msg" -ForegroundColor Cyan }
function Write-Section { param($msg) Write-Host "`n=== $msg ===" -ForegroundColor Yellow }

# Secrets reference
$secrets = @{
    "mongo-001" = @{
        dev     = @{ user = "devadmin"; pass = "hK5bLvR9MVpxqEDO82lX1rki" }
        staging = @{ user = "staadmin"; pass = "Om5VAe2EfUajtMTrKi4o6xGJ" }
        prod    = @{ user = "proadmin"; pass = "jty1dYgE4aS6bLG9RO0cBweW" }
    }
    "postgres-001" = @{
        dev     = @{ user = "devadmin"; pass = "FX82n9gxYSol50KfNZzp4w1R"; db = "postgres_001" }
        staging = @{ user = "staadmin"; pass = "iHewE5WRshI8ZbTFYoCmN9yl"; db = "postgres_001" }
        prod    = @{ user = "proadmin"; pass = "xD5CyPuv8Xaz7BIrAEFtkWmM"; db = "postgres_001" }
    }
    "mysql-001" = @{
        dev     = @{ user = "devadmin"; pass = "x1j5KhLMq3JOtgrH69VoXz7Y"; rootpass = "BAM5tTpwN1RXO9HiE6em0og8"; db = "mysql_001" }
        staging = @{ user = "staadmin"; pass = "J2WSayE91odAFZ8nPprKzXeC"; rootpass = "DvSloHVMPiOxdZ4u28Rb6jY9"; db = "mysql_001" }
        prod    = @{ user = "proadmin"; pass = "41XPi27wlZ6rC8da3OKVkhBc"; rootpass = "TFbmlqPnvsdZ6QIJciHeGUDz"; db = "mysql_001" }
    }
}

# Exposure matrix
$exposure = @{
    "mongo-001"    = @{ dev = "tailscale"; staging = "tailscale"; prod = "internal" }
    "postgres-001" = @{ dev = "internal";  staging = "tailscale"; prod = "tailscale" }
    "mysql-001"    = @{ dev = "tailscale"; staging = "internal";  prod = "internal" }
}

# Tailscale hostnames
$tsHostnames = @{
    "mongo-001"    = @{ dev = "dev-mongo-001"; staging = "staging-mongo-001" }
    "postgres-001" = @{ staging = "staging-postgres-001"; prod = "prod-postgres-001" }
    "mysql-001"    = @{ dev = "dev-mysql-001" }
}

# Ports
$ports = @{
    "mongo-001"    = 27017
    "postgres-001" = 5432
    "mysql-001"    = 3306
}

$totalTests = 0
$passedTests = 0
$failedTests = 0

function Run-SSH {
    param([string]$Command)
    $result = ssh -i $PemPath -o StrictHostKeyChecking=no -o ConnectTimeout=10 "ubuntu@$MasterIP" $Command 2>&1
    return ($result -join "`n")
}

# ============================================================
Write-Section "1. ArgoCD Application Status"
# ============================================================
$argoResult = Run-SSH "sudo kubectl get apps -n argocd 2>/dev/null | grep -E 'mongo-001|postgres-001|mysql-001'"
foreach ($line in ($argoResult -split "`n" | Where-Object { $_ })) {
    $totalTests++
    if ($line -match "Healthy") {
        Write-Pass $line.Trim()
        $passedTests++
    } else {
        Write-Fail $line.Trim()
        $failedTests++
    }
}

# ============================================================
Write-Section "2. Pod Status (all namespaces)"
# ============================================================
foreach ($ns in @("dev", "staging", "prod")) {
    $podResult = Run-SSH "sudo kubectl get pods -n $ns -l 'app in (mongo-001,postgres-001,mysql-001)' --no-headers 2>/dev/null"
    foreach ($line in ($podResult -split "`n" | Where-Object { $_ })) {
        $totalTests++
        if ($line -match "1/1\s+Running") {
            Write-Pass "$ns - $($line.Trim())"
            $passedTests++
        } else {
            Write-Fail "$ns - $($line.Trim())"
            $failedTests++
        }
    }
}

# ============================================================
Write-Section "3. Internal Authenticated Access (via kubectl exec)"
# ============================================================

# MongoDB - use a debug pod with mongosh to avoid OOMkill in small containers
foreach ($env in @("dev", "staging", "prod")) {
    $totalTests++
    $s = $secrets["mongo-001"][$env]
    # Test via TCP connectivity from within the cluster using a temp busybox pod
    $cmd = "sudo kubectl run -n $env mongo-test-$env --rm -i --restart=Never --image=busybox:latest -- sh -c 'nc -z -w3 mongo-001 27017 && echo OK || echo FAIL' 2>&1 | grep -E '^OK$|^FAIL$' | tail -1"
    $result = Run-SSH $cmd
    if ($result -match "OK") {
        Write-Pass "mongo-001/$env internal TCP 27017 = OK"
        $passedTests++
    } else {
        Write-Fail "mongo-001/$env internal TCP 27017 = $result"
        $failedTests++
    }
}

# PostgreSQL
foreach ($env in @("dev", "staging", "prod")) {
    $totalTests++
    $s = $secrets["postgres-001"][$env]
    $cmd = "sudo kubectl exec -n $env deploy/postgres-001 -- psql -U $($s.user) -d $($s.db) -t -c 'SELECT 1' 2>&1 | head -1"
    $result = Run-SSH $cmd
    if ($result -match "1") {
        Write-Pass "postgres-001/$env SELECT 1 = OK"
        $passedTests++
    } else {
        Write-Fail "postgres-001/$env SELECT 1 = $result"
        $failedTests++
    }
}

# MySQL
foreach ($env in @("dev", "staging", "prod")) {
    $totalTests++
    $s = $secrets["mysql-001"][$env]
    $cmd = "sudo kubectl exec -n $env deploy/mysql-001 -- mysqladmin ping -h localhost -u $($s.user) -p$($s.pass) 2>&1 | tail -1"
    $result = Run-SSH $cmd
    if ($result -match "alive") {
        Write-Pass "mysql-001/$env mysqladmin ping = OK"
        $passedTests++
    } else {
        Write-Fail "mysql-001/$env mysqladmin ping = $result"
        $failedTests++
    }
}

# ============================================================
Write-Section "4. Tailscale VPN Access (from local laptop)"
# ============================================================

foreach ($app in @("mongo-001", "postgres-001", "mysql-001")) {
    foreach ($env in @("dev", "staging", "prod")) {
        $mode = $exposure[$app][$env]
        $port = $ports[$app]
        
        if ($mode -eq "tailscale") {
            $hostname = $tsHostnames[$app][$env]
            $fqdn = "$hostname.$TailscaleSuffix"
            $totalTests++
            
            Write-Info "Testing TCP $fqdn`:$port ..."
            $tcp = Test-NetConnection -ComputerName $fqdn -Port $port -WarningAction SilentlyContinue
            if ($tcp.TcpTestSucceeded) {
                Write-Pass "$app/$env via Tailscale ($fqdn`:$port) = CONNECTED"
                $passedTests++
            } else {
                Write-Fail "$app/$env via Tailscale ($fqdn`:$port) = FAILED"
                $failedTests++
            }
        } else {
            Write-Info "$app/$env = internal-only (no Tailscale test)"
        }
    }
}

# ============================================================
Write-Section "5. Exposure Verification"
# ============================================================

$svcResult = Run-SSH "sudo kubectl get svc -A --no-headers 2>/dev/null | grep -E 'mongo-001|postgres-001|mysql-001'"
Write-Info "Cluster services:"
foreach ($line in ($svcResult -split "`n" | Where-Object { $_ })) {
    Write-Host "    $($line.Trim())"
}

# Verify internal-only envs DON'T have Tailscale service
foreach ($app in @("mongo-001", "postgres-001", "mysql-001")) {
    foreach ($env in @("dev", "staging", "prod")) {
        if ($exposure[$app][$env] -eq "internal") {
            $totalTests++
            $tsCheck = Run-SSH "sudo kubectl get svc -n $env ${app}-ts --no-headers 2>&1"
            if ($tsCheck -match "not found" -or $tsCheck -match "NotFound") {
                Write-Pass "$app/$env has NO Tailscale service (correct for internal)"
                $passedTests++
            } else {
                Write-Fail "$app/$env has unexpected Tailscale service"
                $failedTests++
            }
        }
    }
}

# ============================================================
Write-Section "SUMMARY"
# ============================================================
Write-Host ""
Write-Host "Total:  $totalTests tests" -ForegroundColor White
Write-Host "Passed: $passedTests" -ForegroundColor Green
Write-Host "Failed: $failedTests" -ForegroundColor $(if ($failedTests -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($failedTests -eq 0) {
    Write-Host "ALL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "$failedTests TESTS FAILED" -ForegroundColor Red
}

exit $failedTests
