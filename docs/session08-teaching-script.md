# Kịch bản giảng dạy — Buổi 08: Chạy End-to-End

> Dành cho giảng viên. Học viên dùng `README.md` (branch `session/08`). Mọi lệnh viết cho **Windows PowerShell**, chạy từ thư mục gốc repo.
> Thời lượng đề xuất: **155 phút** + 30 phút optional Docker/Ansible.

## Mục tiêu đầu ra

Kết thúc buổi, mỗi học viên có:

1. Fork riêng trên GitHub, branch `session/08` đã push.
2. Chạy được toàn bộ flow bằng lệnh: data → train → gate → register → drift → API.
3. Một lần CI xanh trên GitHub Actions (4 job) và một lần CI đỏ do quality gate.
4. (Optional) Stack Docker Compose 9 service lên và scrape được metrics.

## Chuẩn bị trước buổi (giảng viên)

- [ ] Push branch `session/08` đã có `.github/workflows/ci.yml`, `.gitattributes`, `tests/test_api.py` đã sửa.
- [ ] Tự fork sang tài khoản demo, chạy CI một lần để chắc job xanh (runner `ubuntu-latest`, ~4 phút).
- [ ] Docker Desktop đang chạy, đã `docker compose -f infra/docker-compose.yml pull` trước để không chờ tải image (~1.5 GB).
- [ ] Đóng mọi thứ chiếm cổng 5000, 8000, 9090, 3000 (`netstat -ano | findstr :8000`).
- [ ] Máy chiếu mở sẵn 3 terminal: **T1 mlflow ui**, **T2 lệnh chính**, **T3 uvicorn**.

## Timeline

| Thời gian | Block | Nội dung |
|---|---|---|
| 0:00–0:10 | 1 | Mở đầu: bức tranh E2E, map từng buổi vào flow |
| 0:10–0:30 | 2 | Fork, clone, remote, ôn branch, line ending |
| 0:30–0:40 | 3 | Môi trường Python + MLflow UI |
| 0:40–1:05 | 4 | DVC repro → train → gate → register → drift |
| 1:05–1:10 | 5 | `run_e2e_demo.ps1` chạy lại một lệnh |
| 1:10–1:35 | 5b | **Drift → retrain**: dữ liệu 2016, PSI, bias, retrain, gate |
| 1:35–1:45 | — | Nghỉ |
| 1:45–2:00 | 6 | Serve API + gọi request + xem metrics |
| 2:00–2:25 | 7 | Lint/test local → commit → push → CI xanh → CI đỏ |
| 2:25–2:35 | 8 | Tổng kết, Q&A, giao bài tập |
| 2:35–3:05 | 9 | **Optional**: Docker Compose stack, Ansible ping |

---

## Block 1 — Mở đầu (10')

**Nói:** 7 buổi trước mỗi buổi làm một mảnh. Hôm nay nối lại thành một dây chuyền và chạy từ đầu tới cuối **chỉ bằng lệnh**, rồi để máy (CI) chạy lại y hệt.

Vẽ lên bảng và chỉ từng buổi:

```
raw CSV ──ingest──validate──preprocess──split──▶ train ──▶ quality gate ──▶ register ──▶ serve API ──▶ metrics/drift
  (01)     (02)      (02)       (02)      (02)    (03)        (04/06)         (04)          (05)          (07)
                                                     └──────────── CI GitHub Actions (06) ────────────┘
```

**Nhấn:** hôm nay Docker Compose là *cách đóng gói* dây chuyền, không phải bản thân dây chuyền. Dây chuyền phải chạy được bằng Python thuần trước.

## Block 2 — Fork, clone, remote, ôn branch (20')

Repo lớp: **https://github.com/nhavanntd31/mlops_starter** (chiếu link này lên). Theo README mục 1.

**Điểm dừng kiểm tra:**

```powershell
git remote -v        # origin = fork cá nhân, upstream = nhavanntd31
git branch -r        # thấy đủ origin/session/01..08
git ls-files --eol | Select-String -NotMatch "i/lf|i/none"   # không in gì
```

**Nói về line ending (3'):** Git for Windows mặc định `autocrlf=true` → file checkout ra CRLF. Python, YAML, PowerShell đều chịu được CRLF, nhưng shell script và file `.env` trong container Linux thì **không** (`\r` dính vào giá trị). Repo đã thêm `.gitattributes` ép LF nên học viên không phải cấu hình gì; cảnh báo `LF will be replaced by CRLF` khi `git add` là vô hại.

**Ôn branch (5'):** chạy `git diff --stat origin/session/07 origin/session/08` và chỉ: buổi 08 thêm `infra/docker-compose.yml`, `.env.example`, `register_best_model.py`, `run_e2e_demo.ps1`, `.github/workflows/ci.yml`.

## Block 3 — Môi trường (10')

README Bước 2–3. Chạy `mlflow ui --port 5000` ở **T1** và để yên.

**Lỗi hay gặp:** `running scripts is disabled` khi activate venv → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Block 4 — Pipeline bằng lệnh (25')

README Bước 4–5. Chạy từng lệnh ở **T2**, sau mỗi lệnh dừng 30 giây hỏi "file nào vừa sinh ra?".

| Lệnh | Sinh ra | Hỏi học viên |
|---|---|---|
| `dvc init` + `dvc repro` | `data/processed/*.csv`, `models/scaler.pkl`, `label_encoder.pkl`, `dvc.lock` | Chạy `dvc repro` lần 2 thì sao? (skip vì hash không đổi) |
| `python src/training/train.py` | `models/model.pkl`, `reports/evaluation.json`, run trên MLflow | test_r2 ≈ 0.785. Vì sao có cả val và test? |
| `python scripts/validate_model.py` | exit 0 / 1 | Ngưỡng lấy ở đâu? (`configs/thresholds.yaml`) |
| `python scripts/register_best_model.py` | `models/registry/v_<ts>/`, `latest.json` | Khác gì MLflow Registry buổi 04? (local, không cần server) |
| `python monitoring/generate_drift_report.py` | `reports/drift_report.json` | PSI train vs test ≈ 0.00x → không drift, vì sao? (cùng phân phối, random split) |

**Số liệu mong đợi** (đã chạy thử trên branch này):

| Metric | Giá trị |
|---|---|
| raw rows → mapped rows | 21613 → 21510 |
| train / val / test | 15057 / 2151 / 4302 |
| test_r2 | 0.7854 |
| test_rmse | 156341 |
| test_mae | 87580 |

**Nếu MLflow báo `MLflow logging failed`:** T1 chưa chạy, hoặc protobuf lệch bản. Model vẫn lưu, pipeline vẫn đi tiếp — chỉ ra đây là *fail-open* có chủ đích trong `train.py`.

## Block 5 — Một lệnh chạy hết (10')

```powershell
.\scripts\run_e2e_demo.ps1
```

**Nhấn:** script chỉ là 11 lệnh vừa gõ tay, thêm kiểm tra `$LASTEXITCODE` để **dừng ngay khi lỗi**. Đây chính là cấu trúc một pipeline CI. Demo: đổi `min_r2: 0.99` rồi chạy lại → dừng ở Bước 7 màu đỏ. Trả lại `0.60`.

## Block 5b — Data drift → retrain (25')

README mục 4b. Câu chuyện: model train trên giao dịch 2014–2015. Sang 2016 thị trường lên 30%, nhà bán ra rộng hơn, mới hơn. Model có còn dùng được không, và **làm sao biết**?

**Bước 1 — sinh dữ liệu 2016** `python scripts/simulate_new_data.py`. Chỉ vào 2 dòng mean: price 540k → 702k, sqft 2080 → 2496. Nhấn: đây là mô phỏng, đời thật là dữ liệu mới đổ về hàng ngày.

**Bước 2 — drift report** `python monitoring/generate_drift_report.py --current data/interim/kc_house_data_2016.csv`

| Feature | PSI | Trạng thái |
|---|---|---|
| price | 0.258 | significant_drift |
| area | 0.165 | moderate_drift |
| age | 0.141 | moderate_drift |
| bedrooms, bathrooms, floors | < 0.1 | no_drift |

Hỏi: vì sao `bedrooms` không drift? (kịch bản không đổi). Giải thích PSI: chia reference thành 10 bin theo quantile, so tỷ lệ rơi vào từng bin; < 0.1 ổn, 0.1–0.2 theo dõi, > 0.2 hành động. Exit code 2 = tín hiệu cho CI/cron kích hoạt retrain.

**Bước 3 — model cũ trên dữ liệu mới** `python scripts/evaluate_model.py`. R2 0.72, RMSE, MAE vẫn qua ngưỡng nhưng **bias −66k**: model dự đoán thấp hơn thật một cách có hệ thống. Nhấn: metric tổng hợp (R2) che mất lệch hệ thống; ngưỡng `max_bias` mới thêm vào `thresholds.yaml` bắt được. Đây là trigger thứ hai trong `docs/retraining-trigger.md` (performance degradation), độc lập với trigger PSI.

**Bước 4 — retrain trên dữ liệu gộp** đặt `$env:KC_RAW_PATH` rồi chạy preprocess → split → train → validate_model → evaluate_model. Hỏi trước khi chạy: "retrain trên 2016 thôi hay gộp 2014–2016?" (gộp: giữ được phân khúc cũ, model học được cả trend). Kết quả: gate PASS, trên 2016 R2 0.82, bias −26k → PASS. `register_best_model.py` tạo version mới trong `models/registry/`, `latest.json` trỏ sang.

**Bước 5 — dọn** `Remove-Item Env:KC_RAW_PATH`. Nhấn: biến môi trường là cách "cắm" nguồn dữ liệu mới mà không sửa code, y như CI/CT buổi 06 làm.

**Số liệu đã chạy thử:**

| | Model cũ (2014–15) trên 2016 | Model mới (2014–16) trên 2016 |
|---|---|---|
| R2 | 0.7206 | 0.8163 |
| RMSE | 207,512 | 168,276 |
| MAE | 133,432 | 109,802 |
| bias | −65,828 (FAIL) | −25,937 (PASS) |

Nếu thiếu giờ: bỏ Bước 4, chỉ chạy đến Bước 3 để thấy trigger, giao retrain làm bài tập.

## Block 6 — Serve API (15')

README Bước 7. **T3:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`. **T2:** `python scripts/sample_predict.py`.

**Bẫy Windows phải nói:** `curl` trong PowerShell là alias `Invoke-WebRequest`, gõ `curl.exe`. Gửi JSON thì dùng `Invoke-RestMethod` với `ConvertTo-Json` (mẫu trong README) — tránh vật lộn escape dấu nháy.

Gửi 2 request lỗi (`location="downtown"` → 400, `area="abc"` → 422) rồi `curl.exe http://localhost:8000/metrics`: chỉ ra counter `http_requests_total{status="400"}` tăng — đây là dữ liệu Prometheus sẽ scrape ở Block 9.

**Cổng bị chiếm:** `netstat -ano | findstr :8000` → `taskkill /PID <pid> /F`. Nếu là container Docker → `docker stop <name>`.

## Block 7 — Commit → CI (30')

README Bước 8–9.

1. Chạy local đúng 3 lệnh CI sẽ chạy: `ruff check ...`, `pytest`, `validate_config.py`. Nhấn: **CI không làm gì mới, nó chỉ chạy lại cái bạn vừa chạy trên máy sạch.**
2. `git status` — chỉ `.dvc/`, `.dvcignore`, `dvc.lock` là file mới. Hỏi: vì sao `models/model.pkl` không hiện? (`.gitignore`). Vì sao `dvc.lock` nên commit? (khóa hash dữ liệu → tái tạo được).
3. `git add -A; git commit -m "lab: session 08 e2e run"; git push -u origin session/08`.
4. Mở fork → Actions → enable workflows → xem 4 job chạy song song 01/02/03 rồi 04. Trong lúc chờ (~4') giải thích `needs:` và `upload-artifact`.
5. **Gate đỏ:** `min_r2: 0.99` → commit → push → job 04 fail ở *Model quality gate*, artifact không upload. Trả `0.60`, push lại → xanh.
6. Chỉ job `05 docker build (optional)` chỉ chạy khi bấm **Run workflow** — Docker là optional đúng như thiết kế buổi.

**Nếu mạng lớp yếu:** cho học viên push, giảng viên chiếu Actions trên fork demo đã xanh sẵn.

## Block 8 — Tổng kết (15')

Quay lại sơ đồ Block 1, tô xanh từng khối đã chạy. Ba câu hỏi chốt:

- Bước nào thất bại thì **không được** deploy? (quality gate)
- Hai tín hiệu nào kích hoạt retrain? (PSI > 0.2 và bias/metric vượt ngưỡng trên dữ liệu mới)
- Cái gì nằm trong Git, cái gì không? (code, config, `dvc.lock` — không phải data/model)
- CI chạy trên máy ai? (`ubuntu-latest` của GitHub; buổi 06 là self-hosted trên laptop)

Giao bài tập trong README (Alertmanager, Grafana provisioning, `check_stack_health.py`, scale API).

## Block 9 — Optional: Docker Compose + Ansible (30')

README Bước 10–11. **Tắt T1 (mlflow) và T3 (uvicorn) trước** để nhả cổng 5000/8000.

```powershell
Copy-Item .env.example infra\.env
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
```

Thứ tự lên: postgres, minio → minio-init tạo bucket → mlflow → model-api → prometheus → grafana. Đã kiểm chứng toàn bộ 9 container healthy và 5 endpoint trả 200. Chỉ vào cột STATUS `healthy`.

Việc làm nhanh: `python scripts/sample_predict.py` (API trong container), Prometheus Targets `model-api` UP, `python src/training/train.py` để run rơi vào MLflow-Postgres và artifact rơi vào MinIO (console http://localhost:9001).

**Lưu ý đã kiểm chứng:**

- `minio/minio` trên Docker Hub đã bị gỡ → compose dùng `quay.io/minio/minio`.
- Image MLflow chính thức không kèm driver Postgres/S3 → build thêm 1 layer bằng `infra/Dockerfile.mlflow` (lần đầu tải ~1 phút).
- Container API báo `model_loaded: false` kèm `Can't get attribute ... sklearn._loss` khi bản scikit-learn trong image khác bản đã train. Vì vậy `requirements.txt` pin `scikit-learn==1.6.1`; học viên phải train bằng venv cài từ file này. Đây là bài học reproducibility: **môi trường train = môi trường serve**.
- Client và server MLflow phải cùng major version (3.x client gọi `/logged-models` mà server 2.x không có → 404). `requirements.txt` và `Dockerfile.mlflow` pin cùng `3.16.1`.
- Server chạy `--serve-artifacts`: client chỉ nói chuyện với MLflow, MLflow tự ghi lên MinIO. Không cần `boto3`/AWS key ở máy học viên.
- `train.py` gọi `log_model(..., serialization_format="cloudpickle")` vì MLflow 3.x mặc định dùng skops và chặn `sklearn.tree._tree.Tree`.
- `.env` phải nằm cạnh compose file (`infra/.env`) hoặc truyền `--env-file`. Compose đã có giá trị mặc định nên thiếu `.env` vẫn chạy.

Ansible: chỉ demo `ansible-playbook infra/ansible/ping.yml` trong WSL, mục đích là thấy playbook = mô tả trạng thái. Không bắt học viên cài.

Dọn: `docker compose -f infra/docker-compose.yml down -v`.

---

## Checklist lỗi Windows đã rà

| Hạng mục | Kết quả kiểm tra |
|---|---|
| CRLF trong repo | Không có; mọi file LF. Đã thêm `.gitattributes` để giữ nguyên trên Windows. |
| Ký tự ngoài ASCII trong `.ps1` | Không có (PowerShell 5.1 đọc file không BOM theo ANSI, tiếng Việt sẽ vỡ). |
| BOM | Chỉ `.gitignore` có BOM UTF-8, Git xử lý được. |
| Đường dẫn `/` trong lệnh Python | Windows chấp nhận, không cần đổi thành `\`. |
| `curl` | Phải dùng `curl.exe` hoặc `Invoke-RestMethod`. |
| `dvc` không có trong PATH | Dùng `python -m dvc ...`. |
| Execution policy `.ps1` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
