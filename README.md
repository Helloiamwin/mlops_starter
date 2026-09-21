# Buổi 08 — Chạy End-to-End: Data → Train → Gate → Serve → CI (Docker Compose optional)

> **Dataset:** [House Sales in King County, USA](https://www.kaggle.com/datasets/harlfoxem/housesalesprediction) — file raw duy nhất `data/raw/kc_house_data.csv` (~21613 rows).
> Mapping cột trong `src/ingestion/ingest.py` (`sqft_living→area`, `yr_built→age`, `zipcode→location`, `floors`).
> Lệnh trong buổi này viết cho **Windows PowerShell**, chạy từ **thư mục gốc repo**.

## Mục tiêu buổi học

- Fork repo về tài khoản GitHub của mình, checkout `session/08`, ôn nhanh các branch buổi trước
- Chạy **toàn bộ flow bằng lệnh**: ingest → validate → preprocess → split → train → quality gate → register → drift → serve API
- Giả lập dữ liệu năm mới có trend khác → phát hiện **data drift** (PSI) và **performance degradation** → **retrain** → gate → register
- Commit + push để **GitHub Actions** chạy CI (lint → test → validate config → train + quality gate)
- (Optional, cuối buổi) Khởi động toàn bộ stack bằng Docker Compose: Postgres + MinIO + MLflow + API + Prometheus + Loki + Grafana
- (Optional) Làm quen Ansible cho Infrastructure as Code

---

## Kiến thức lý thuyết

### Docker Compose

- Công cụ **orchestrate** ứng dụng đa container
- Định nghĩa tất cả services trong một file `docke-compose.yml`
- Quản lý networks, volumes, dependencies giữa các services
- Khởi động/dừng toàn bộ stack bằng một lệnh duy nhất

### Các service trong stack

| Service | Vai trò |
|---------|---------|
| **PostgreSQL** | Backend store cho MLflow (lưu metadata experiments, runs, metrics) |
| **MinIO** | S3-compatible object storage (lưu artifacts: model files, plots) |
| **MLflow Server** | Tracking server kết nối PostgreSQL + MinIO |
| **Model API** | FastAPI serving predictions, expose `/health`, `/predict`, `/metrics` |
| **Prometheus** | Thu thập và lưu trữ metrics từ Model API |
| **Loki** | Thu thập và lưu trữ logs tập trung |
| **Promtail** | Agent đọc log files và đẩy vào Loki |
| **Grafana** | Dashboard hiển thị metrics và logs |

### Service Dependencies và Health Checks

```
PostgreSQL ──┐
             ├── MLflow Server ── Model API ── Prometheus
MinIO ───────┘                                     │
                                    Loki ── Promtail
                                     │
                                   Grafana
```

- MLflow phụ thuộc PostgreSQL + MinIO (phải healthy trước)
- Model API phụ thuộc MLflow (để load model)
- Grafana kết nối Prometheus + Loki làm data sources

### Infrastructure as Code (IaC) — Ansible (optional)

- **Ansible**: công cụ tự động hóa cấu hình server
- Dùng YAML playbooks để mô tả trạng thái mong muốn
- Không cần agent trên máy đích (agentless, dùng SSH)
- Ứng dụng: cài Docker, deploy stack lên server remote

---

## Hướng dẫn thực hành (Windows PowerShell, chạy từ thư mục gốc repo)

### 1. Clone repo

```powershell
git clone https://github.com/nhavanntd31/mlops_starter.git
cd mlops_starter
git checkout session/08
```

Để push và chạy CI trên tài khoản của mình: mở [https://github.com/nhavanntd31/mlops_starter](https://github.com/nhavanntd31/mlops_starter) → **Fork** (bỏ tick "Copy the master branch only"). Fork có cùng tên repo, chỉ đổi phần tài khoản. Ví dụ tài khoản `chi-anhle-ai`:

```powershell
git remote rename origin upstream
git remote add origin https://github.com/chi-anhle-ai/mlops_starter.git
git remote -v
```

Thay `chi-anhle-ai` bằng tên GitHub của bạn. Sau đó `origin` = fork (push lên đây), `upstream` = repo lớp `nhavanntd31/mlops_starter`.

### 2. Môi trường

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt pytest ruff
```

Nếu báo `running scripts is disabled`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 3. Bật MLflow (terminal riêng, giữ chạy)

```powershell
mlflow ui --port 5000
```

### 4. Chạy toàn bộ pipeline

```powershell
dvc init
dvc repro
python src/training/train.py
python scripts/validate_model.py
python scripts/register_best_model.py
python monitoring/generate_drift_report.py
```

Hoặc một lệnh chạy hết (kèm pytest):

```powershell
.\scripts\run_e2e_demo.ps1
```

Kết quả: `test_r2 ≈ 0.78`, `Result: ALL CHECKS PASSED`, `models/model.pkl`, `reports/evaluation.json`, run mới trên http://localhost:5000.

### 4b. Kịch bản data drift → retrain

Giả lập dữ liệu **năm 2016**: giá tăng ~30%, nhà rộng hơn ~20%, xây mới hơn.

```powershell
python scripts/simulate_new_data.py
python monitoring/generate_drift_report.py --current data/interim/kc_house_data_2016.csv
python scripts/evaluate_model.py
```

Mong đợi: `price PSI≈0.26 (significant_drift) -> RETRAIN RECOMMENDED` (exit 2) và model cũ `[FAIL] |bias| <= 50000 -> bias≈-66,000` (exit 1): model dự đoán thấp hơn giá thật vì học trên thị trường cũ.

Retrain trên dữ liệu gộp 2014–2016 rồi đánh giá lại:

```powershell
$env:KC_RAW_PATH = "data/interim/kc_house_data_2014_2016.csv"
python src/preprocessing/preprocess.py
python src/split/split.py
python src/training/train.py
python scripts/validate_model.py
python scripts/evaluate_model.py
python scripts/register_best_model.py
Remove-Item Env:KC_RAW_PATH
```

Mong đợi: gate PASS, trên dữ liệu 2016 `R2≈0.82`, `bias≈-26,000` → PASS. Đây là vòng **monitor → trigger → retrain → validate → register** của `docs/retraining-trigger.md`.

### 5. Serve API (terminal riêng) và gọi thử

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```powershell
python scripts/sample_predict.py
curl.exe http://localhost:8000/metrics
```

> Trong PowerShell phải gõ `curl.exe`, vì `curl` là alias của `Invoke-WebRequest`.
> Cổng 8000 bị chiếm: `netstat -ano | findstr :8000` → `taskkill /PID <pid> /F`.

### 6. Commit → CI

```powershell
git add -A
git commit -m "lab: session 08 e2e"
git push -u origin session/08
```

Fork → tab **Actions** → enable workflows → workflow **ci** chạy 4 job: lint → test → validate config → train + quality gate.

Thử gate chặn: sửa `configs/thresholds.yaml` thành `min_r2: 0.99`, commit, push → job 04 đỏ. Trả về `0.60`, push lại.

### 7. (Optional) Docker Compose

Tắt `mlflow ui` và `uvicorn` trước để nhả cổng 5000/8000. Cần Docker Desktop đang chạy.

```powershell
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
python scripts/sample_predict.py
```

| Dịch vụ | URL |
|---|---|
| MLflow | http://localhost:5000 |
| API docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 (Status → Targets: `model-api` UP) |
| Grafana | http://localhost:3000 (`admin` / `admin123`) |
| MinIO | http://localhost:9001 (`minioadmin` / `minioadmin123`) |

Chạy lại `python src/training/train.py` → run vào Postgres, artifact vào MinIO.

Dừng: `docker compose -f infra/docker-compose.yml down -v`.

### 8. (Optional) Ansible

```bash
pip install ansible
ansible-playbook infra/ansible/ping.yml
```

(Ansible chạy trong WSL/Ubuntu, không hỗ trợ control node Windows.)

---

## Lệnh tương đương trên Ubuntu / WSL

```bash
git clone https://github.com/nhavanntd31/mlops_starter.git && cd mlops_starter
git checkout session/08

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt pytest ruff

mlflow ui --port 5000 &          # hoặc mở terminal riêng

dvc init
dvc repro
python src/training/train.py
python scripts/validate_model.py
python scripts/register_best_model.py
python monitoring/generate_drift_report.py
pytest tests/ -q

# Drift -> retrain
python scripts/simulate_new_data.py
python monitoring/generate_drift_report.py --current data/interim/kc_house_data_2016.csv
python scripts/evaluate_model.py
KC_RAW_PATH=data/interim/kc_house_data_2014_2016.csv bash -c '
  python src/preprocessing/preprocess.py && python src/split/split.py &&
  python src/training/train.py && python scripts/validate_model.py'
python scripts/evaluate_model.py

uvicorn app.main:app --host 0.0.0.0 --port 8000 &
python scripts/sample_predict.py
curl http://localhost:8000/metrics

git add -A && git commit -m "lab: session 08 e2e" && git push -u origin session/08

# Optional Docker
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml down -v
```

Cổng bị chiếm trên Ubuntu: `sudo lsof -i :8000` → `kill <pid>` hoặc `docker stop <container>`.

---

## Xử lý lỗi thường gặp

| Lỗi | Cách sửa |
|---|---|
| `curl: -X` không hiểu (Windows) | Dùng `curl.exe` |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `dvc: command not found` | Activate venv, hoặc `python -m dvc repro` |
| `MLflow logging failed` | Chưa bật `mlflow ui`; model vẫn lưu, pipeline vẫn chạy |
| `model_loaded: false` | Chưa có `models/*.pkl`; chạy bước 4 rồi restart uvicorn / build lại image |
| `Can't get attribute ... sklearn` trong container | Bản scikit-learn khác bản đã train; `pip install -r requirements.txt` (đã pin) rồi train + build lại |
| Cổng 5000/8000 bận | `netstat -ano \| findstr :8000` → `taskkill /PID <pid> /F` |
| `LF will be replaced by CRLF` | Cảnh báo vô hại, `.gitattributes` đã ép LF |

---

## Bảng service và port

| Service | Image | Port(s) | Mô tả | URL kiểm tra |
|---------|-------|---------|--------|--------------|
| PostgreSQL | `postgres:15` | `5432` | MLflow backend store | — |
| MinIO | `quay.io/minio/minio` | `9000` (API), `9001` (Console) | S3-compatible storage | `http://localhost:9001` |
| MLflow | build từ `infra/Dockerfile.mlflow` | `5000` | Experiment tracking | `http://localhost:5000` |
| Model API | build local | `8000` | Prediction serving | `http://localhost:8000/docs` |
| Prometheus | `prom/prometheus` | `9090` | Metrics DB | `http://localhost:9090` |
| Loki | `grafana/loki` | `3100` | Log aggregation | — |
| Promtail | `grafana/promtail` | — | Log shipping agent | — |
| Grafana | `grafana/grafana` | `3000` | Visualization | `http://localhost:3000` |

---

## Chi tiết `docker-compose.yml`

### PostgreSQL

```yaml
postgres:
  image: postgres:15
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
    interval: 10s
    timeout: 5s
    retries: 5
```

Lưu trữ metadata của MLflow: experiments, runs, params, metrics.

### MinIO

```yaml
minio:
  image: quay.io/minio/minio
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  ports:
    - "9000:9000"
    - "9001:9001"
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 10s
    timeout: 5s
    retries: 5
```

S3-compatible storage cho MLflow artifacts (model files, plots, ...).

### MLflow Server

```yaml
mlflow:
  build:
    context: .
    dockerfile: Dockerfile.mlflow     # ghcr.io/mlflow/mlflow + psycopg2-binary + boto3
  command: >
    mlflow server
    --backend-store-uri postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    --artifacts-destination s3://mlflow-artifacts/
    --serve-artifacts
    --host 0.0.0.0 --port 5000
  environment:
    MLFLOW_S3_ENDPOINT_URL: http://minio:9000
    AWS_ACCESS_KEY_ID: ${MINIO_ROOT_USER}
    AWS_SECRET_ACCESS_KEY: ${MINIO_ROOT_PASSWORD}
  ports:
    - "5000:5000"
  depends_on:
    postgres:
      condition: service_healthy
    minio-init:
      condition: service_completed_successfully
```

Image MLflow chính thức **không kèm** driver Postgres/S3 nên phải build thêm 1 layer. `--serve-artifacts` cho server **proxy** artifact lên MinIO, nên máy học viên không cần cài `boto3` hay khai báo AWS key. Service `minio-init` (image `quay.io/minio/mc`) tạo bucket `mlflow-artifacts` rồi thoát.

Kết nối PostgreSQL (backend) + MinIO (artifacts). Chỉ khởi động sau khi cả hai healthy.

### Model API

```yaml
model-api:
  build:
    context: ..
    dockerfile: Dockerfile
  environment:
    MODEL_URI: ${MODEL_URI:-}
    MLFLOW_TRACKING_URI: ${MLFLOW_TRACKING_URI}
  ports:
    - "8000:8000"
  volumes:
    - api_logs:/app/logs
  depends_on:
    mlflow:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 10s
    timeout: 5s
    retries: 5
```

FastAPI app serving predictions. Mount volume `api_logs` để Promtail đọc logs.

### Prometheus

```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - ../monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml
    - prometheus_data:/prometheus
  ports:
    - "9090:9090"
  depends_on:
    model-api:
      condition: service_healthy
```

Scrape metrics từ Model API mỗi 15 giây, lưu time-series data.

### Loki

```yaml
loki:
  image: grafana/loki:2.9.0
  ports:
    - "3100:3100"
  volumes:
    - loki_data:/loki
```

Nhận và lưu trữ logs từ Promtail.

### Promtail

```yaml
promtail:
  image: grafana/promtail:2.9.0
  volumes:
    - ./promtail.yml:/etc/promtail/config.yml
    - api_logs:/var/log/app:ro
  depends_on:
    - loki
```

Đọc log files từ volume `api_logs` và đẩy vào Loki.

### Grafana

```yaml
grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  environment:
    GF_SECURITY_ADMIN_USER: admin
    GF_SECURITY_ADMIN_PASSWORD: admin
  volumes:
    - grafana_data:/var/lib/grafana
  depends_on:
    - prometheus
    - loki
```

Dashboard hiển thị metrics (Prometheus) và logs (Loki).

### Networks và Volumes

```yaml
networks:
  default:
    name: mlops-network

volumes:
  postgres_data:
  minio_data:
  prometheus_data:
  loki_data:
  grafana_data:
  api_logs:
```

Tất cả services cùng network `mlops-network`, giao tiếp qua tên service. Volumes persist dữ liệu giữa các lần restart.

---

## Bài tập sau buổi học

1. **Thêm service Alertmanager** — thêm `alertmanager` vào `docker-compose.yml`, cấu hình nhận alerts từ Prometheus và gửi thông báo (email hoặc Slack webhook). Test bằng cách tạo tình huống HighErrorRate.

2. **Tạo Grafana dashboard tự động** — viết file JSON provisioning cho Grafana dashboard, mount vào container. Dashboard hiển thị: request rate, latency p95, error rate, prediction count. Khi Grafana khởi động sẽ tự động có dashboard.

3. **Viết script health check toàn bộ stack** — tạo `scripts/check_stack_health.py` kiểm tra tất cả services (curl health endpoint), in bảng trạng thái, exit code = 1 nếu có service nào fail.

4. **Thêm auto-scaling cho Model API** — nghiên cứu và cấu hình `deploy.replicas` trong Docker Compose hoặc dùng `docker compose up --scale model-api=3`. Test load balancing bằng cách gửi nhiều request đồng thời.

---

## Buổi tiếp theo

**Buổi 09 — Phân tích Bài toán AI Doanh nghiệp**: Chuyển từ kỹ thuật sang tư duy sản phẩm — phân tích bài toán kinh doanh, xác định bài toán ML phù hợp, thiết kế hệ thống AI cho doanh nghiệp, và trình bày kế hoạch triển khai.
