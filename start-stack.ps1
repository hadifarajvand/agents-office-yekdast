# Agent Office - Complete Stack Startup Script

$ProjectDir = "D:\Projects\agent-office-yekdast"
$BackendDir = $ProjectDir
$FrontendDir = "$ProjectDir\frontend"
$BackendLog = "$env:TEMP\backend.log"
$FrontendLog = "$env:TEMP\frontend.log"

Write-Host "Agent Office - Complete Stack Startup" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Kill existing processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

Write-Host "1. Starting Backend..." -ForegroundColor Blue

# Start Backend
cd $BackendDir
$env:USE_PYTHON_BACKEND = "true"
$env:PYTHON_BACKEND_URL = "http://localhost:8000"
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:20128/v1"
$env:ANTHROPIC_AUTH_TOKEN = "sk-d88b5ef429e08f78-wah1ts-45f9884f"

$BackendProcess = Start-Process python -ArgumentList "-m backend.main" -PassThru -NoNewWindow -RedirectStandardOutput $BackendLog
$BackendPID = $BackendProcess.Id

Write-Host "[OK] Backend started (PID: $BackendPID)" -ForegroundColor Green
Write-Host "     Logs: $BackendLog"
Start-Sleep -Seconds 3

# Check if backend is running
if (Get-Process -Id $BackendPID -ErrorAction SilentlyContinue) {
  Write-Host "[OK] Backend is running" -ForegroundColor Green
} else {
  Write-Host "[FAIL] Backend failed to start" -ForegroundColor Red
  Get-Content $BackendLog
  exit 1
}

# Wait for backend to be ready
Write-Host ""
Write-Host "2. Waiting for backend to be ready..." -ForegroundColor Blue

$maxAttempts = 30
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
  try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
      Write-Host "[OK] Backend is healthy" -ForegroundColor Green
      break
    }
  } catch {
    # Still waiting
  }
  if ($attempt -lt $maxAttempts) {
    Write-Host "   Attempt $attempt/$maxAttempts..."
  }
  Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "3. Starting Frontend..." -ForegroundColor Blue

# Start Frontend
cd $FrontendDir
$env:USE_PYTHON_BACKEND = "true"
$env:PYTHON_BACKEND_URL = "http://localhost:8000"

# Use cmd /c to properly invoke npm (which is a batch/cmd file)
$FrontendProcess = Start-Process cmd -ArgumentList "/c", "npm start" -PassThru -NoNewWindow -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendLog
$FrontendPID = $FrontendProcess.Id

Write-Host "[OK] Frontend started (PID: $FrontendPID)" -ForegroundColor Green
Write-Host "     Logs: $FrontendLog"
Start-Sleep -Seconds 4

# Check if frontend is running
if (Get-Process -Id $FrontendPID -ErrorAction SilentlyContinue) {
  Write-Host "[OK] Frontend is running" -ForegroundColor Green
} else {
  Write-Host "[FAIL] Frontend failed to start" -ForegroundColor Red
  Get-Content $FrontendLog
  exit 1
}

# Wait for frontend to be ready
Write-Host ""
Write-Host "4. Waiting for frontend to be ready..." -ForegroundColor Blue

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
  try {
    $response = Invoke-WebRequest -Uri "http://localhost:4520" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
      Write-Host "[OK] Frontend is ready" -ForegroundColor Green
      break
    }
  } catch {
    # Still waiting
  }
  if ($attempt -lt $maxAttempts) {
    Write-Host "   Attempt $attempt/$maxAttempts..."
  }
  Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Green
Write-Host "Agent Office Stack Ready!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "[OK] ALL SERVICES RUNNING" -ForegroundColor Green
Write-Host ""
Write-Host "ACCESS POINTS:" -ForegroundColor White
Write-Host "  Frontend (UI):     http://localhost:4520" -ForegroundColor Cyan
Write-Host "  Backend (API):     http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:          http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Health:            http://localhost:8000/api/health" -ForegroundColor Cyan
Write-Host "  Real-time Events:  http://localhost:8000/api/events" -ForegroundColor Cyan
Write-Host "  Metrics:           http://localhost:8000/api/metrics" -ForegroundColor Cyan
Write-Host ""
Write-Host "LOGS:" -ForegroundColor White
Write-Host "  Backend:  Get-Content -Wait '$BackendLog'"
Write-Host "  Frontend: Get-Content -Wait '$FrontendLog'"
Write-Host ""
Write-Host "TEST STEPS:" -ForegroundColor White
Write-Host "  1. Open http://localhost:4520 in browser"
Write-Host "  2. Create a task using the UI"
Write-Host "  3. Watch it appear in real-time (no 6-second delay!)"
Write-Host "  4. Check backend health: curl http://localhost:8000/api/metrics"
Write-Host ""
Write-Host "To stop: Press Ctrl+C" -ForegroundColor Yellow
Write-Host ""

# Keep processes running
while ($true) {
  if (-not (Get-Process -Id $BackendPID -ErrorAction SilentlyContinue) -or -not (Get-Process -Id $FrontendPID -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: One or more services crashed." -ForegroundColor Yellow
    break
  }
  Start-Sleep -Seconds 5
}
