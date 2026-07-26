#!/usr/bin/env pwsh
<#
.SYNOPSIS
End-to-end validation for homepage-api in prod.
Checks: health (200), /db-check (Mongo ping ok), /ws (101 Switching Protocols).
Run from any host with internet access (DNS for homepage-api.futurefarms.mx).
#>
param(
    [string]$Host_ = "homepage-api.futurefarms.mx",
    [int]$TimeoutSec = 10
)

$ErrorActionPreference = "Continue"
$pass = 0; $fail = 0

function Test-Step {
    param($Name, [scriptblock]$Block)
    Write-Host -NoNewline ("[{0}] " -f $Name.PadRight(14))
    try {
        $r = & $Block
        if ($r.ok) {
            Write-Host -ForegroundColor Green ("PASS " + $(if ($r.detail) { $r.detail } else { "" }))
            $script:pass++
        } else {
            Write-Host -ForegroundColor Red ("FAIL " + $(if ($r.detail) { $r.detail } else { "" }))
            $script:fail++
        }
    } catch {
        Write-Host -ForegroundColor Red ("ERROR " + $_.Exception.Message)
        $script:fail++
    }
}

Test-Step "health" {
    $r = Invoke-WebRequest -Uri "https://$Host_/health" -TimeoutSec $TimeoutSec -UseBasicParsing
    @{ ok = ($r.StatusCode -eq 200); detail = "HTTP $($r.StatusCode) body=$($r.Content)" }
}

Test-Step "root" {
    $r = Invoke-WebRequest -Uri "https://$Host_/" -TimeoutSec $TimeoutSec -UseBasicParsing
    @{ ok = ($r.StatusCode -eq 200); detail = "HTTP $($r.StatusCode)" }
}

Test-Step "db-check" {
    $r = Invoke-WebRequest -Uri "https://$Host_/db-check" -TimeoutSec $TimeoutSec -UseBasicParsing
    $j = $r.Content | ConvertFrom-Json
    $detail = "uri_present=$($j.uri_present) ok=$($j.ok) ping=$(($j.ping | ConvertTo-Json -Compress))"
    if ($j.ok -ne $true) { $detail += " error=$($j.error)" }
    @{ ok = ($r.StatusCode -eq 200 -and $j.ok -eq $true); detail = $detail }
}

Test-Step "websocket" {
    # Raw HTTP/1.1 upgrade handshake via TcpClient + SslStream
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect($Host_, 443)
    $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, { $true })
    $ssl.AuthenticateAsClient($Host_)
    $key = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((Get-Random -Maximum 99999999).ToString().PadRight(16,'x')))
    $req = "GET /ws HTTP/1.1`r`nHost: $Host_`r`nUpgrade: websocket`r`nConnection: Upgrade`r`nSec-WebSocket-Key: $key`r`nSec-WebSocket-Version: 13`r`n`r`n"
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($req)
    $ssl.Write($bytes, 0, $bytes.Length); $ssl.Flush()
    $buf = New-Object byte[] 1024
    $n = $ssl.Read($buf, 0, $buf.Length)
    $resp = [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
    $ssl.Close(); $tcp.Close()
    $firstLine = ($resp -split "`r`n")[0]
    @{ ok = $firstLine -match "101"; detail = $firstLine }
}

Write-Host ""
Write-Host ("Result: {0} passed, {1} failed" -f $pass, $fail)
if ($fail -gt 0) { exit 1 } else { exit 0 }
