$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Önce README.md içindeki sanal ortam kurulumunu tamamlayın.'
}

function Test-Endpoint([string]$url) {
    try {
        return (Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200
    } catch { return $false }
}

if (-not (Test-Endpoint 'http://127.0.0.1:8765/api/health')) {
    Start-Process -FilePath $python -ArgumentList @('prompt_api.py') `
        -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
}
if (-not (Test-Endpoint 'http://127.0.0.1:8501/')) {
    Start-Process -FilePath $python -ArgumentList @('-m','streamlit','run','app.py',
        '--server.address','127.0.0.1','--server.port','8501','--browser.gatherUsageStats','false') `
        -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-Endpoint 'http://127.0.0.1:8765/api/health') -and
        (Test-Endpoint 'http://127.0.0.1:8501/')) {
        Write-Host 'OneTech Studio hazır: http://127.0.0.1:8501/'
        Start-Process -FilePath 'http://127.0.0.1:8501/' | Out-Null
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
throw 'OneTech Studio veya yerel prompt API başlatılamadı.'
