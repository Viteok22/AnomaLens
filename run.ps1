$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    python -m venv backend\.venv
}

& $python -m pip install -r backend\requirements.txt

if (-not (Test-Path "backend\artifacts\fault_model.joblib")) {
    Push-Location backend
    & .\.venv\Scripts\python.exe train_fault_classifier.py
    Pop-Location
}

if (-not (Test-Path "frontend\node_modules")) {
    Push-Location frontend
    npm install
    Pop-Location
}

Push-Location frontend
npm run build
Pop-Location

Write-Host ""
Write-Host "Open http://127.0.0.1:8000"
Set-Location backend
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
