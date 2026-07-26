$ErrorActionPreference = "Stop"

# Configuration
$PemPath = "..\_private\keys\contabo.pem"
$RemoteUser = "ubuntu"
$RemoteIP = "161.97.112.80"
$RemoteDB = "datastore.prod.svc.cluster.local"
$RemotePort = 27017
$LocalPort = 27017

Write-Host "🚀 Starting Kaanbal API in Hybrid Mode (Local Code + Remote Data)" -ForegroundColor Cyan

# 1. Check Key
if (-not (Test-Path $PemPath)) {
    Write-Error "SSH Key not found at $PemPath. Please verify path."
}

# 2. Check for existing process on port 27017
$existing = Get-NetTCPConnection -LocalPort $LocalPort -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warning "Port $LocalPort in use. Attempting to kill existing mongo tunnel/process..."
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
}

# 3. Start SSH Tunnel
Write-Host "🔌 Establishing SSH Tunnel to MongoDB ($RemoteDB)..." -ForegroundColor Yellow
$TunnelJob = Start-Job -ScriptBlock {
    param($pem, $user, $ip, $rdb, $rport, $lport)
    # Using -N for no command (tunnel only), -o StrictHostKeyChecking=no to avoid prompt
    ssh -i $pem -N -L "${lport}:${rdb}:${rport}" "${user}@${ip}" -o StrictHostKeyChecking=no
} -ArgumentList $PemPath, $RemoteUser, $RemoteIP, $RemoteDB, $RemotePort, $LocalPort

# Wait for tunnel
Start-Sleep -Seconds 5
$jobState = Get-Job -Id $TunnelJob.Id
if ($jobState.State -eq "Failed") {
    Receive-Job -Id $TunnelJob.Id
    Write-Error "Failed to start SSH Tunnel."
}
Write-Host "✅ Tunnel established!" -ForegroundColor Green

# 4. Set Environment for Local
$env:MONGODB_URI = "mongodb://localhost:${LocalPort}/forge"
$env:SECRET_KEY = "supersecretkey_dev_only" # Or fetch from vault if needed
$env:DOMAIN = "localhost"

# 5. Run Uvicorn
Write-Host "🔥 Starting Uvicorn Server..." -ForegroundColor Cyan
Write-Host "   API: http://localhost:8000"
Write-Host "   Docs: http://localhost:8000/docs"
Write-Host "   DB: $env:MONGODB_URI (Tunneled)"

try {
    # Check if dependencies are installed
    python -c "import fastapi, uvicorn, pymongo, jose, passlib" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Dependencies missing. Installing..."
        pip install -r requirements.txt
    }

    # Run Server
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
}
finally {
    Write-Host "`n🛑 Stopping Tunnel..." -ForegroundColor Yellow
    Stop-Job -Id $TunnelJob.Id -ErrorAction SilentlyContinue
    Remove-Job -Id $TunnelJob.Id -ErrorAction SilentlyContinue
    
    # Kill any ssh.exe spawned by the job if it lingers
    # Stop-Process -Name ssh -ErrorAction SilentlyContinue 
}
