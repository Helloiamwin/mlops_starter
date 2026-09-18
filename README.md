# Buổi 06 — CI/CD, Quality Gate và Continuous Training (test edit file)

> **Dataset:** [House Sales in King County, USA](https://www.kaggle.com/datasets/harlfoxem/housesalesprediction)
> File raw: `data/raw/kc_house_data.csv`. Mapping cột trong `src/ingestion/ingest.py`.
> Buổi này tiếp nối **Buổi 05** (FastAPI + Docker). Cần đã train xong `models/*.pkl`.

## Mục tiêu buổi học

- Cấu hình Git lần đầu, **fork repo GitHub** của riêng bạn (cùng tài khoản GitHub, không cần GitLab)
- Build image Docker và chạy API trong container (ôn buổi 05)
- Dùng **GitHub Actions + self-hosted runner trên máy bạn** — CI/CD đơn giản, cùng auth GitHub
- Mỗi lần `git push` tự lint → test → validate → (retrain nếu cần) → build image → serve container mới
- Thiết lập **Continuous Training (CT)** có quality gate: model kém thì không deploy

---

## Kiến thức lý thuyết

### Git — vài khái niệm cho người mới

| Khái niệm | Ý nghĩa |
|---|---|
| **repo** | Thư mục project có lịch sử thay đổi (`.git`) |
| **commit** | Một bản ghi "đã lưu" kèm message |
| **branch** | Nhánh làm việc, buổi này dùng `session/06` |
| **remote** | Bản copy trên GitHub. `origin` = **fork của bạn**, `upstream` = repo lớp |
| **push** | Đẩy commit lên GitHub → Actions chạy CI |
| **fork** | Copy repo lớp sang tài khoản GitHub của bạn (1 nút, cùng login) |

Lệnh hay dùng: `git status` → `git add` → `git commit` → `git push`.

### Mỗi người một fork GitHub — đừng push chung 1 repo lớp

Lab chạy trên **nhiều máy**. Không đẩy hết vào `nhavanntd31/mlops_starter`.

| Cách | Kết quả |
|---|---|
| **Mỗi học viên 1 fork + 1 runner trên laptop mình** | Push của bạn chỉ build/serve Docker trên máy bạn. Cùng tài khoản GitHub, không đổi auth. |
| Cả lớp push 1 repo | Runner máy A có thể nhận job của B → container chạy nhầm máy. |

Repo lớp (`upstream`) để **lấy đề**. Fork của bạn (`origin`) để **nộp bài và chạy CI**.

### CI / CD / CT trong MLOps

| Khái niệm | Giải thích | Trong lab này |
|---|---|---|
| **CI** Continuous Integration | Mỗi lần push, tự chạy lint + test + validate | Steps `03–05` trong GitHub Actions |
| **CD** Continuous Delivery | Build image mới và thay container đang serve | Steps `09–12` Docker build → deploy → health |
| **CT** Continuous Training | Retrain + quality gate trước khi bake image | Steps `06–08` |

GitHub Actions giống Jenkins: **một pipeline**, nhiều **step** nối tiếp. Step FAIL → các step sau không chạy.

`dvc.yaml` chỉ chứa data pipeline (ingest → validate → preprocess → split). Lint/test/train/deploy **không** nhét vào DVC.

### Tóm tắt 12 step

| # | Step | Nhóm | Làm gì |
|---|---|---|---|
| 01 | Checkout | chuẩn bị | Lấy code commit vừa push |
| 02 | Setup | chuẩn bị | `pip install`, copy CSV raw nếu thiếu |
| 03 | Lint | CI | `ruff` — code có lỗi cú pháp/import thừa không |
| 04 | Test | CI | `pytest` — unit test |
| 05 | Validate config | CI | `params.yaml` / `thresholds.yaml` hợp lệ |
| 06 | Data pipeline | CT | `dvc repro` — ingest → validate → preprocess → split |
| 07 | Train | CT | `train.py` — ghi `models/model.pkl` |
| 08 | Model quality gate | CT | R² / RMSE / MAE đạt ngưỡng? FAIL thì dừng, không deploy |
| 09 | Docker build | CD | Build image `house-price-api:<sha>` |
| 10 | Smoke test | CD | Container import được `app.main` |
| 11 | Deploy | CD | `docker compose up` thay API đang chạy |
| 12 | Health check | CD | `curl` `/health` và `/model-info` |

### Xem process chạy ở đâu

**Chỗ chính — GitHub Actions (giống màn hình job Jenkins):**

1. Mở **fork của bạn** trên github.com (không phải repo lớp)
2. Tab **Actions** (menu ngang, cạnh Code / Pull requests)
3. Trái: workflow **ci-cd-ct**. Giữa: danh sách lần chạy (mỗi `git push` một dòng)
4. Bấm một lần chạy → job **CI / CD / CT**
5. Bấm job đó → **12 step** xếp dọc. Vàng = đang chạy, xanh = xong, đỏ = fail. Bấm từng step để xem log

URL dạng: `https://github.com/<tenban>/mlops_starter/actions`

Chạy tay không cần push: Actions → **ci-cd-ct** → **Run workflow**.

**Chỗ phụ — trên máy bạn (vì runner local):**

| Chỗ | Xem gì |
|---|---|
| Cửa sổ runner / Windows Service `actions.runner.*` | Log khi GitHub gọi máy bạn |
| `docker ps` | Container `house-price-api` đã recreate chưa |
| [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) | API sau step 12 |
| [http://127.0.0.1:8000/model-info](http://127.0.0.1:8000/model-info) | `model_version` = 7 ký tự SHA commit |

Local chạy thử step 03–08 trước khi push: `ruff`, `pytest`, `validate_config.py`, `dvc repro`, `train.py`, `validate_model.py`.


### Vì sao Runner chạy trên máy bạn?

GitHub-hosted runner (máy ảo Ubuntu) build được image nhưng **không đẩy container lên laptop**. Lab dùng **self-hosted runner** trên Windows:

- Pipeline do GitHub Actions điều phối (tab Actions trên web)
- Lệnh thật chạy trên máy bạn: Docker Desktop sẵn có
- `docker compose up` thay API ở `http://127.0.0.1:8000`

`runs-on: [self-hosted, local]` → job không lên máy GitHub, chỉ runner laptop bạn nhận.

### Quality Gate

Gate = điều kiện bắt buộc. Một job FAIL → pipeline dừng, **không serve model mới**.

| Gate | Điều kiện |
|---|---|
| Lint | `ruff check` không báo lỗi |
| Tests | `pytest tests/` pass |
| Config | `params.yaml` / `thresholds.yaml` đủ key, siêu tham số hợp lệ, file raw tồn tại |
| Model (CT) | `test_r2`, `test_rmse`, `test_mae` đạt `configs/thresholds.yaml` |
| Docker | `docker build` xong và `import app.main` được |

---

## Cấu trúc file buổi này

```
mlops_starter/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .github/workflows/ci.yml   # 12 step kiểu Jenkins (CI + CT + CD)
├── dvc.yaml                   # ingest → validate → preprocess → split
├── configs/
│   ├── params.yaml
│   └── thresholds.yaml
├── scripts/
│   ├── validate_config.py
│   ├── validate_model.py
│   └── continuous_train.py
└── app/model_loader.py
```

---

## Hướng dẫn thực hành

Lệnh theo **PowerShell**. Cần Docker Desktop đang chạy.

### Bước 0: Git lần đầu + fork GitHub + môi trường

Chưa dùng Git: làm **0a → 0b → 0c → 0d**. Đã clone rồi thì 0a (nếu chưa config), 0c, rồi 0d.

**0a — Cài Git và khai báo danh tính (1 lần / máy)**

1. Cài [Git for Windows](https://git-scm.com/download/win), để mặc định, mở **PowerShell mới**.
2. Kiểm tra:

```powershell
git --version
```

3. Thay bằng tên thật và email dùng trên GitHub:

```powershell
git config --global user.name "Nguyen Van A"
git config --global user.email "a.nguyen@gmail.com"
git config --global --list
```

**0b — Lấy code**

Nếu **chưa có** thư mục:

```powershell
cd D:\Workspace\mlops
git clone https://github.com/nhavanntd31/mlops_starter.git
cd mlops_starter
```

Nếu **đã có**:

```powershell
cd D:\Workspace\mlops\mlops_starter
```

```powershell
git fetch origin
git checkout session/06
git pull origin session/06
```

**0c — Fork repo của bạn (cùng GitHub, không tạo GitLab)**

1. Mở [https://github.com/nhavanntd31/mlops_starter](https://github.com/nhavanntd31/mlops_starter) khi đã login
2. Bấm **Fork** → Create fork (để mặc định)
3. Fork xong URL là `https://github.com/<tenban>/mlops_starter`

Trỏ `origin` về fork, giữ repo lớp là `upstream`:

```powershell
git remote rename origin upstream
git remote add origin https://github.com/<tenban>/mlops_starter.git
git remote -v
git push -u origin session/06
```

Phải thấy `origin` = fork bạn, `upstream` = repo lớp. Push dùng **cùng GitHub** đang login (Git Credential Manager), không đổi sang GitLab.

Mở fork trên web: thấy nhánh `session/06` và `.github/workflows/ci.yml`.

Lần đầu Actions trên fork: tab **Actions** → bấm **I understand my workflows, go ahead and enable them**.

**0d — Môi trường Python**

```powershell
venv\Scripts\activate
$env:PYTHONUTF8 = "1"
pip install -r requirements.txt
pip install fastapi uvicorn pytest ruff
```

```powershell
Get-ChildItem models\*.pkl
```

Phải có `model.pkl`, `scaler.pkl`, `label_encoder.pkl`. Nếu thiếu:

```powershell
dvc repro
python src/training/train.py
```

Copy CSV sang chỗ runner luôn tìm được (file raw không nằm trong Git):

```powershell
New-Item -ItemType Directory -Force "$HOME\mlops-raw" | Out-Null
Copy-Item data\raw\kc_house_data.csv "$HOME\mlops-raw\kc_house_data.csv"
```

### Bước 1: Ôn Docker buổi 05 — build image và chạy container

```powershell
docker build -t house-price-api:lab .
docker run --rm -p 8000:8000 --name house-price-api house-price-api:lab
```

Tab khác:

```powershell
curl.exe http://127.0.0.1:8000/health
python scripts/sample_predict.py
```

Dừng: Ctrl+C, hoặc `docker stop house-price-api`.

### Bước 2: Serve bằng docker compose (cách CD sẽ dùng)

```powershell
$env:MODEL_VERSION = "local"
docker compose up -d --build
docker compose ps
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/model-info
```

Mở [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Bước 3: Chạy quality gate trên máy (CI local)

```powershell
ruff check app src tests scripts --select E,F --ignore E501,E402
python scripts/validate_config.py
pytest tests/ -v --tb=short
python scripts/continuous_train.py
```

Kết quả mong đợi: `All configs valid`, `10 passed`, `[CT] training pipeline passed quality gate`.

Thử gate: `learning_rate: 0` rồi `validate_config.py` phải FAIL. Trả về `0.1`.

### Bước 4: Cài GitHub self-hosted runner trên máy bạn

Runner gắn **fork của bạn**, không gắn repo lớp.

1. Fork trên GitHub → **Settings → Actions → Runners → New self-hosted runner**
2. Chọn **Windows** x64
3. Copy 3 lệnh GitHub hiện ra (download zip, `config.cmd`, `run.cmd`) vào PowerShell

Khi `config.cmd` hỏi:

- Runner group: Enter
- Runner name: `laptop-mlops`
- Labels: gõ `local` rồi Enter (thêm vào label mặc định `self-hosted`)
- Work folder: Enter

Cài service để không phải để cửa sổ mở:

```powershell
cd $HOME\actions-runner
.\svc.cmd install
.\svc.cmd start
.\svc.cmd status
```

Fork → Settings → Actions → Runners: runner **Idle**, labels có `self-hosted` và `local`.

Settings → Actions → General: **Allow all actions and reusable workflows**.

Docker Desktop phải đang chạy. Cần `venv\` ở root repo.

### Bước 5: Push — CI tự build và serve image mới

Giữ compose từ Bước 2. Sửa nhẹ `docs/architecture.md`, rồi:

```powershell
git status
git add docs/architecture.md
git commit -m "lab: trigger ci pipeline"
git push origin session/06
```

GitHub fork → tab **Actions** → bấm lần chạy mới nhất → job **CI / CD / CT** → 12 step (vàng / xanh / đỏ). Chi tiết: mục **Xem process chạy ở đâu** phía trên.

```powershell
curl.exe http://127.0.0.1:8000/model-info
docker ps --filter name=house-price-api
```

`model_version` = 7 ký tự SHA commit.

### Bước 6: Continuous Training

Trong `configs/params.yaml` đổi `n_estimators: 150` rồi:

```powershell
git add configs/params.yaml
git commit -m "train: n_estimators 150"
git push origin session/06
```

Step `07 Train` + `08 Model quality gate` chạy lại. PASS → image mới → compose recreate.

```powershell
curl.exe http://127.0.0.1:8000/model-info
python scripts/sample_predict.py
```

Hoặc GitHub → Actions → **Run workflow** (luôn CT).

### Bước 7: Quality gate chặn deploy

Đặt `min_r2: 0.99` trong `configs/thresholds.yaml`, commit, `git push origin session/06`.

Job `08 Model quality gate` FAIL (`R2 >= 0.99`). Step 09–12 không chạy. Container cũ vẫn serve — đúng hành vi production: **model kém không lên**.

Trả `min_r2: 0.60`, push lại.

```powershell
python scripts/continuous_train.py
```

---

## Chi tiết `.github/workflows/ci.yml`

Một job `pipeline`, 12 step tuần tự — giống Jenkins stage/step. `runs-on: [self-hosted, local]`.

| # | Step | Lệnh |
|---|---|---|
| 01 | Checkout | `actions/checkout` |
| 02 | Setup | `pip install` + `ensure_raw.py` |
| 03 | Lint | `ruff check` |
| 04 | Test | `pytest` |
| 05 | Validate config | `python scripts/validate_config.py` |
| 06 | Data pipeline | `dvc repro` (chỉ ingest → split) |
| 07 | Train | `python src/training/train.py` |
| 08 | Model quality gate | `python scripts/validate_model.py` |
| 09 | Docker build | `docker build -t house-price-api:$SHA` |
| 10 | Smoke test | `import app.main` trong container |
| 11 | Deploy | `docker compose up -d --build` |
| 12 | Health check | `curl /health` và `/model-info` |

Jenkins `stage { steps { } }` ≈ GitHub `jobs.*.steps`. Step đỏ → pipeline dừng.

`MODEL_VERSION` = 7 ký tự `GITHUB_SHA`.

---

## Chi tiết Continuous Training

1. Có `data/raw/kc_house_data.csv`
2. `dvc repro` — ingest → validate → preprocess → split
3. `python src/training/train.py`
4. `python scripts/validate_model.py` vs `configs/thresholds.yaml`

| Metric | Ngưỡng |
|---|---|
| test R² | ≥ 0.60 |
| test RMSE | ≤ 250000 |
| test MAE | ≤ 150000 |

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `git: command not found` | Chưa cài Git | Cài Git for Windows, mở lại PowerShell |
| `pwsh: command not found` | Runner Windows không có PowerShell 7 | Workflow dùng `shell: powershell` (Windows PowerShell). Commit/push file `ci.yml` mới |
| Push nhầm repo lớp | `origin` vẫn là `nhavanntd31/...` | `git remote -v` — `origin` phải là fork; Bước 0c |
| `docker: command not found` trong Actions | Docker Desktop tắt / service runner không thấy Docker | Mở Docker Desktop; `svc.cmd stop` rồi `start`; đăng nhập lại Windows |
| `model_loaded: false` | Chưa có `models/*.pkl` lúc build | Bước 0d: `dvc repro` + `train.py` |
| `validate` FAIL data path | Thiếu CSV raw | Data buổi 02 vào `data/raw/` |
| Cổng 8000 bận | Còn container buổi 05 | `docker compose down`; `docker rm -f house-price-api` |
| `ruff` không chạy | Chưa activate venv | `venv\Scripts\activate` |

---

## Bài tập sau buổi học

1. **CT từ GitHub UI** — Actions → Run workflow. So với `git push` thường: cùng một pipeline.
2. **Fail-then-fix** — `n_estimators: 0`, push fork, xem job FAIL. Sửa, push, deploy chạy.
3. **Gắn SHA vào health** — field `git_sha` đọc `MODEL_VERSION`.
4. **Chặn deploy khi test FAIL** — phá 1 unit test, push, `loaded_at` không đổi.

---

## Buổi tiếp theo

**Buổi 07 — Monitoring, Metrics và Drift Detection**: Prometheus trên FastAPI, log, phát hiện data drift, alert. Pipeline buổi 06 là chỗ cắm job drift sau này.
