# Script demo End-to-End cho du an House Price Prediction (Windows PowerShell 5.1 / 7)
# Chay tu thu muc goc repo:  .\scripts\run_e2e_demo.ps1
# Dung ngay khi mot buoc loi (exit code != 0).

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:MLFLOW_DISABLE_AGENT_HINT = "1"
# Neu MLflow server khong chay, train.py chi in canh bao thay vi cho retry lau
$env:MLFLOW_HTTP_REQUEST_MAX_RETRIES = "0"

function Run-Step {
    param([string]$Title, [string]$Command)
    Write-Host ""
    Write-Host "[$Title] $Command" -ForegroundColor Yellow
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $Title (exit $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " DEMO END-TO-END: House Price Prediction" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Run-Step "Buoc 1 - Kiem tra du lieu tho"  "python -c `"import pandas as pd; df = pd.read_csv('data/raw/kc_house_data.csv'); print(f'  Du lieu: {len(df)} dong, {len(df.columns)} cot')`""
Run-Step "Buoc 2 - Ingest"                 "python src/ingestion/ingest.py"
Run-Step "Buoc 3 - Validate du lieu"       "python src/validation/validate.py"
Run-Step "Buoc 4 - Tien xu ly"             "python src/preprocessing/preprocess.py"
Run-Step "Buoc 5 - Chia train/val/test"    "python src/split/split.py"
Run-Step "Buoc 6 - Huan luyen model"       "python src/training/train.py"
Run-Step "Buoc 7 - Quality gate"           "python scripts/validate_model.py"
Run-Step "Buoc 8 - Dang ky model (local)"  "python scripts/register_best_model.py"
Run-Step "Buoc 9 - Drift report"           "python monitoring/generate_drift_report.py"
Run-Step "Buoc 10 - Validate config"       "python scripts/validate_config.py"
Run-Step "Buoc 11 - Unit tests"            "python -m pytest tests/ -q"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " DEMO HOAN TAT!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Cac buoc tiep theo:" -ForegroundColor Cyan
Write-Host "  1. Serve API local:  uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host "  2. Thu predict:      python scripts/sample_predict.py"
Write-Host "  3. Commit + push de chay CI:  git add -A; git commit -m 'lab: session 08 e2e'; git push origin session/08"
Write-Host "  4. (Optional) Stack Docker:   docker compose -f infra/docker-compose.yml up -d --build"
