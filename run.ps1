# สคริปต์สำหรับเริ่มรัน Mission Control Streamlit App บนเครื่อง Windows 11
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$VenvStreamlit = Join-Path $ScriptDir ".venv\Scripts\streamlit.exe"

if (-not (Test-Path $VenvStreamlit)) {
    Write-Host "ไม่พบ .venv กำลังสร้างสภาพแวดล้อมใหม่..." -ForegroundColor Yellow
    python -m venv .venv
    & $VenvPython -m pip install -r requirements.txt --quiet
}

Write-Host "กำลังเริ่มรัน Mission Control ใน Isolated Environment (.venv)..." -ForegroundColor Green
& $VenvStreamlit run app.py
