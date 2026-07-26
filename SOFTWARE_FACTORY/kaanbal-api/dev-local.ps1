# Kaanbal Development Environment - Quick Start
# Ejecutar este script para iniciar el entorno de desarrollo local

Write-Host "🚀 Iniciando entorno de desarrollo Kaanbal..." -ForegroundColor Cyan

# Configuración
$SSH_KEY = "c:\Users\andre\OneDrive\Documents\DEV\SOFTWARE FACTORY\_private\keys\contabo.pem"
$CLUSTER_IP = "161.97.112.80"

# Verificar si el túnel SSH ya está corriendo
$tunnelCheck = netstat -ano | findstr ":27017.*LISTENING"

if (-not $tunnelCheck) {
    Write-Host "📡 Iniciando túnel SSH a MongoDB del cluster..." -ForegroundColor Yellow
    Start-Process -FilePath "ssh" -ArgumentList "-i `"$SSH_KEY`" -N -L 27017:datastore.prod.svc.cluster.local:27017 ubuntu@$CLUSTER_IP -o StrictHostKeyChecking=accept-new" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Write-Host "✅ Túnel SSH iniciado en background" -ForegroundColor Green
} else {
    Write-Host "✅ Túnel SSH ya está activo" -ForegroundColor Green
}

# Verificar conexión MongoDB
Write-Host "🔍 Verificando conexión a MongoDB..." -ForegroundColor Yellow
$mongoCheck = Test-NetConnection -ComputerName localhost -Port 27017 -WarningAction SilentlyContinue
if ($mongoCheck.TcpTestSucceeded) {
    Write-Host "✅ MongoDB accesible en localhost:27017" -ForegroundColor Green
} else {
    Write-Host "❌ No se puede conectar a MongoDB. Verifica el túnel SSH." -ForegroundColor Red
    exit 1
}

# Variables de entorno
$env:MONGODB_URI = "mongodb://localhost:27017/forge"
$env:SECRET_KEY = "dev-secret-key-change-in-prod"
$env:DOMAIN = "localhost"

Write-Host ""
Write-Host "📋 Variables de entorno configuradas:" -ForegroundColor Cyan
Write-Host "   MONGODB_URI = $env:MONGODB_URI"
Write-Host "   SECRET_KEY = [configurado]"
Write-Host "   DOMAIN = $env:DOMAIN"
Write-Host ""

Write-Host ""
Write-Host "🌐 Iniciando Kaanbal API en http://localhost:8000" -ForegroundColor Cyan
Write-Host "📖 Documentación en http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para detener: Ctrl+C" -ForegroundColor Gray
Write-Host ""

# Iniciar uvicorn con Python 3.11
py -3.11 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
