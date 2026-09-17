# Buổi 06 — CI/CD, Quality Gate và Continuous Training

> **Dataset:** [House Sales in King County, USA](https://www.kaggle.com/datasets/harlfoxem/housesalesprediction)
> File raw: `data/raw/kc_house_data.csv`. Mapping cột trong `src/ingestion/ingest.py`.
> Buổi này tiếp nối **Buổi 05** (FastAPI + Docker). Cần đã train xong `models/*.pkl`.

## Mục tiêu buổi học

- Cấu hình Git lần đầu, tạo **repo GitLab của riêng bạn** (không dùng chung cả lớp)
- Build image Docker và chạy API trong container (ôn buổi 05)
- Dùng **GitLab CI + GitLab Runner trên máy bạn** — công cụ CI/CD đơn giản nhất để thấy kết quả ngay trên laptop
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
| **remote** | Bản copy trên internet. Lab có 2 remote: `origin` (GitHub lớp) và `gitlab` (repo của bạn) |
| **push** | Đẩy commit từ máy lên remote → GitLab nhận và chạy CI |

Lệnh hay dùng: `git status` (đang sửa gì) → `git add` → `git commit` → `git push`.

### Mỗi người một repo Git — đừng dùng chung

Lab chạy trên **nhiều máy**. Không dùng chung 1 GitLab project cho cả lớp.

| Cách | Kết quả |
|---|---|
| **Mỗi học viên 1 repo GitLab + 1 runner trên laptop mình** | Push của bạn chỉ build/serve Docker trên máy bạn. Đúng bài lab. |
| Cả lớp push 1 repo | Runner máy A có thể nhận job của B → container chạy nhầm máy, pipeline lẫn commit, khó chấm bài. |

Repo GitHub buổi học (`origin`) chỉ để **lấy đề**. Repo GitLab của bạn (`gitlab`) để **nộp bài và chạy CI**.

### CI / CD / CT trong MLOps

| Khái niệm | Giải thích | Trong lab này |
|---|---|---|
| **CI** Continuous Integration | Mỗi lần push, tự chạy lint + test + validate | Jobs `lint`, `test`, `validate-config` |
| **CD** Continuous Delivery | Build image mới và thay container đang serve | Jobs `docker-build`, `deploy-local` |
| **CT** Continuous Training | Retrain khi data/code/params đổi, chỉ nhận model đạt ngưỡng | Job `train` + `scripts/continuous_train.py` |

```
git push gitlab session/06
   │
   ▼
┌─────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐
│  lint   │──►│  test   │──►│ validate │──►│  train  │──►│  build  │──►│  deploy  │
│  ruff   │   │ pytest  │   │  config  │   │ CT+gate │   │ docker  │   │ compose  │
└─────────┘   └─────────┘   └──────────┘   └─────────┘   └─────────┘   └──────────┘
                                 │              │                          │
                                 FAIL dừng      FAIL không deploy          ▼
                                                                  localhost:8000
```

Job `train` **không chạy mọi push**. Chỉ chạy khi đổi `src/`, `configs/params.yaml`, `configs/thresholds.yaml`, `data/`, hoặc `dvc.yaml`. Push sửa docs thì bỏ qua CT, vẫn build + deploy image hiện có.

### Vì sao Runner chạy trên máy bạn?

GitLab.com shared runner build được image nhưng **không đẩy container lên laptop**. Lab dùng **GitLab Runner (shell executor)** trên Windows:

- Pipeline vẫn do GitLab điều phối (nhìn được trên web)
- Lệnh thật chạy trên máy bạn: dùng Docker Desktop sẵn có
- `docker compose up` thay API đang chạy ở `http://127.0.0.1:8000`

Đây là self-hosted runner — cùng ý tưởng team dùng runner trong công ty, chỉ thu nhỏ về 1 máy.

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
├── Dockerfile                 # Image API — đã có từ buổi 05
├── docker-compose.yml         # Serve 1 service: house-price-api :8000
├── .dockerignore
├── .gitlab-ci.yml             # Pipeline CI / CD / CT
├── configs/
│   ├── params.yaml            # Tham số train — đổi cái này sẽ trigger CT
│   └── thresholds.yaml        # Ngưỡng quality gate của model
├── scripts/
│   ├── validate_config.py     # Gate cấu hình
│   ├── validate_model.py      # Gate metrics sau train
│   └── continuous_train.py    # CT: dvc repro → train → validate_model
└── app/model_loader.py        # Đọc MODEL_VERSION từ biến môi trường
```

---

## Hướng dẫn thực hành

Lệnh theo **PowerShell**. Cần Docker Desktop đang chạy.

### Bước 0: Git lần đầu + repo của bạn + môi trường

Chưa dùng Git: làm **0a → 0b → 0c → 0d**. Đã clone repo rồi thì làm 0a (nếu chưa config), 0c, rồi 0d.

**0a — Cài Git và khai báo danh tính (1 lần / máy)**

1. Cài [Git for Windows](https://git-scm.com/download/win), để mặc định, xong mở **PowerShell mới**.
2. Kiểm tra:

```powershell
git --version
```

Phải in ra kiểu `git version 2.xx.x`.

3. Ghi tên và email — GitLab dùng email này nhận diện commit. Thay bằng **tên thật** và email bạn dùng trên GitLab:

```powershell
git config --global user.name "Nguyen Van A"
git config --global user.email "a.nguyen@gmail.com"
git config --global --list
```

Phải thấy `user.name` và `user.email`. Chỉ làm 1 lần trên máy; các repo sau dùng lại.

**0b — Lấy code buổi học**

Nếu **chưa có** thư mục project:

```powershell
cd D:\Workspace\mlops
git clone https://github.com/nhavanntd31/mlops_starter.git
cd mlops_starter
```

Nếu **đã có** (buổi 05):

```powershell
cd D:\Workspace\mlops\mlops_starter
```

Lấy nhánh buổi 06:

```powershell
git fetch origin
git checkout session/06
git pull origin session/06
```

- `clone` = copy repo về máy
- `checkout` = chuyển nhánh
- `pull` = lấy commit mới từ remote lớp

**0c — Tạo repo GitLab của riêng bạn (bắt buộc, không dùng chung)**

1. Đăng ký / đăng nhập [gitlab.com](https://gitlab.com)
2. **New project** → **Create blank project**
3. Project name: `mlops_starter` (hoặc `mlops-lab-tenban`)
4. Visibility: **Private**
5. **Bỏ tick** *Initialize repository with a README* — để trống, nếu không `git push` sẽ xung đột
6. Create project → copy URL HTTPS, ví dụ `https://gitlab.com/tenban/mlops_starter.git`

Gắn remote tên `gitlab`. Không ghi đè `origin` (GitHub lớp):

```powershell
git remote add gitlab https://gitlab.com/tenban/mlops_starter.git
git remote -v
```

Phải thấy 2 remote: `origin` (đề bài) và `gitlab` (repo bạn).

Đẩy nhánh buổi 06 lên repo của bạn:

```powershell
git push -u gitlab session/06
```

Lần đầu GitLab hỏi đăng nhập: username GitLab + **Personal Access Token** (không phải mật khẩu web). Tạo token: GitLab → avatar → **Access Tokens** → scope `write_repository` → copy token, dán vào chỗ password.

Mở GitLab trên web: thấy nhánh `session/06` và file `.gitlab-ci.yml`.

Nếu báo `remote gitlab already exists`:

```powershell
git remote set-url gitlab https://gitlab.com/tenban/mlops_starter.git
```

**0d — Môi trường Python**

```powershell
venv\Scripts\activate
$env:PYTHONUTF8 = "1"
pip install -r requirements.txt
pip install fastapi uvicorn pytest ruff
```

Kiểm tra model buổi 05 còn đó:

```powershell
Get-ChildItem models\*.pkl
```

Phải thấy `model.pkl`, `scaler.pkl`, `label_encoder.pkl`. Nếu thiếu:

```powershell
dvc repro
python src/training/train.py
```

### Bước 1: Ôn Docker buổi 05 — build image và chạy container

```powershell
docker build -t house-price-api:lab .
docker run --rm -p 8000:8000 --name house-price-api house-price-api:lab
```

Tab PowerShell khác:

```powershell
curl.exe http://127.0.0.1:8000/health
python scripts/sample_predict.py
```

Kết quả mong đợi: `"model_loaded": true` và một `predicted_price`.

Dừng container: Ctrl+C ở tab `docker run`, hoặc:

```powershell
docker stop house-price-api
```

### Bước 2: Serve bằng docker compose (cách CD sẽ dùng)

```powershell
$env:MODEL_VERSION = "local"
docker compose up -d --build
docker compose ps
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/model-info
```

Mở [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). `/model-info` có `"model_version": "local"`.

Compose map cổng `8000:8000`, rebuild khi Dockerfile/context đổi, thay container cũ (`--force-recreate` lúc deploy).

### Bước 3: Chạy quality gate trên máy (CI local)

Làm bước này **trước khi** gắn GitLab — cùng lệnh pipeline sẽ chạy.

```powershell
ruff check app src tests scripts --select E,F --ignore E501,E402
python scripts/validate_config.py
pytest tests/ -v --tb=short
python scripts/continuous_train.py
```

Kết quả mong đợi:

```
All configs valid
... 10 passed ...
[CT] dvc repro
[Training] Metrics:
  test_r2: 0.7...
[CT] training pipeline passed quality gate
```

Nếu `validate_model` FAIL: sửa `configs/params.yaml` hoặc nới `configs/thresholds.yaml` — **đừng tắt gate**.

Thử gate config: đổi `learning_rate: 0` rồi chạy lại `validate_config.py` — phải FAIL. Trả file về `0.1`.

### Bước 4: Gắn GitLab Runner trên máy bạn

Pipeline đọc `.gitlab-ci.yml` trên **repo GitLab của bạn**. Runner cài trên **đúng laptop đó**. Không đăng ký runner vào repo của bạn khác.

**4a — Tắt runner dùng chung của GitLab.com**

Trong project GitLab **của bạn**: Settings → CI/CD → Runners → tắt **Enable instance runners for this project**.

Nếu để bật, job có thể chạy trên máy GitLab — không build được Docker trên laptop bạn.

**4b — Cài GitLab Runner (Windows)**

```powershell
New-Item -ItemType Directory -Force -Path C:\GitLab-Runner | Out-Null
Invoke-WebRequest -Uri "https://gitlab-runner-downloads.s3.amazonaws.com/latest/binaries/gitlab-runner-windows-amd64.exe" -OutFile C:\GitLab-Runner\gitlab-runner.exe
```

**4c — Đăng ký runner với repo của bạn**

GitLab (project của bạn) → Settings → CI/CD → Runners → **New project runner**:

- Tags: `local` (đúng chữ này — khớp `tags: [local]` trong `.gitlab-ci.yml`)
- Bỏ chọn "Run untagged jobs"
- Create runner → copy token

```powershell
cd C:\GitLab-Runner
.\gitlab-runner.exe register --non-interactive --url "https://gitlab.com" --token "<TOKEN>" --executor "shell" --shell "powershell" --name "laptop-mlops"
.\gitlab-runner.exe install
.\gitlab-runner.exe start
.\gitlab-runner.exe status
```

Kết quả: `Service is running`. Trên GitLab, runner hiện Online với tag `local`.

Runner dùng Python/Docker của máy bạn. Cần `venv\` ở root repo và Docker Desktop đang chạy.

### Bước 5: Push — CI tự build và serve image mới

Giữ compose đang chạy từ Bước 2. Tập commit như người mới: sửa file nhỏ (không đụng train), xem Git thấy gì, đẩy lên **repo gitlab của bạn**.

Ví dụ sửa `docs/architecture.md` thêm một dòng, rồi:

```powershell
git status
git add docs/architecture.md
git commit -m "lab: trigger ci pipeline"
git push gitlab session/06
```

Lần sau: `git add` file đã sửa → `git commit -m "..."` → `git push gitlab session/06`.

GitLab → **Build → Pipelines**. Job `train` **skipped** (không đụng code train/data). `docker-build` + `deploy-local` chạy trên laptop.

Kết quả job `deploy-local`: JSON `/health` và `/model-info`. `model_version` = short SHA commit (7 ký tự).

```powershell
curl.exe http://127.0.0.1:8000/model-info
docker ps --filter name=house-price-api
```

Container `house-price-api` image tag = SHA commit vừa push.

### Bước 6: Continuous Training — đổi params, push, model mới được serve

Baseline `training.params` trong `configs/params.yaml`:

```yaml
    n_estimators: 200
    max_depth: 5
    learning_rate: 0.1
```

Đổi nhẹ để trigger CT:

```yaml
    n_estimators: 150
```

```powershell
git add configs/params.yaml
git commit -m "train: n_estimators 150"
git push gitlab session/06
```

Pipeline lần này **chạy job `train`**:

```
dvc repro
python src/training/train.py
python scripts/validate_model.py
```

PASS gate → build image (COPY `models/` mới) → `docker compose up -d --build --force-recreate` → API load model mới (`loaded_at` đổi).

Kiểm tra:

```powershell
curl.exe http://127.0.0.1:8000/model-info
python scripts/sample_predict.py
```

`model_version` khác SHA lần push trước.

### Bước 7: Thấy quality gate chặn deploy

Tạm đặt trong `configs/thresholds.yaml`: `min_r2: 0.99` (model lab ~0.75–0.80 sẽ FAIL).

```powershell
git add configs/thresholds.yaml
git commit -m "test: raise r2 gate to fail CT"
git push gitlab session/06
```

Job `train` FAIL (`R2 >= 0.99`). Stage `build` / `deploy` bị skip. Container cũ vẫn serve — đúng hành vi production: **model kém không lên**.

Trả `min_r2: 0.60`, commit + `git push gitlab session/06`.

Chạy CT tay không cần push:

```powershell
python scripts/continuous_train.py
```

---

## Chi tiết `.gitlab-ci.yml`

6 stage, mọi job gắn tag `local` → chỉ runner laptop của **repo đó** nhận.

| Job | Stage | Khi nào chạy | Việc làm |
|---|---|---|---|
| `lint` | lint | mọi push | `ruff check` |
| `test` | test | mọi push | `pytest` + JUnit artifact |
| `validate-config` | validate | mọi push | schema + range siêu tham số |
| `train` | train | đổi code/data/params, hoặc Run pipeline trên web | `continuous_train.py` |
| `docker-build` | build | mọi push | `docker build` + smoke `import app.main` |
| `deploy-local` | deploy | sau build; skip nếu train FAIL | `docker compose up -d --build` + curl health |

Job `train` skipped thì GitLab vẫn chạy `build` + `deploy`. Job `train` FAIL thì hai stage sau bị bỏ — không serve model kém.

`MODEL_VERSION` = `$CI_COMMIT_SHORT_SHA` đưa vào compose → `/model-info` chứng minh image mới đang chạy.

---

## Chi tiết Continuous Training

`scripts/continuous_train.py` gọi tuần tự:

1. Kiểm tra `data/raw/kc_house_data.csv`
2. `dvc repro` — pipeline ingest → validate → preprocess → split
3. `python src/training/train.py` — ghi `models/model.pkl`, `reports/evaluation.json`
4. `python scripts/validate_model.py` — so metrics với `configs/thresholds.yaml`

Gate mặc định:

| Metric | Ngưỡng |
|---|---|
| test R² | ≥ 0.60 |
| test RMSE | ≤ 250000 |
| test MAE | ≤ 150000 |

---

## Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `git: command not found` | Chưa cài Git hoặc chưa mở lại PowerShell | Cài Git for Windows, đóng/mở terminal |
| `Authentication failed` khi push GitLab | Dùng mật khẩu web | Dùng Personal Access Token, scope `write_repository` |
| `remote origin already exists` / nhầm repo | Đẩy vào repo lớp hoặc repo bạn khác | `git remote -v` — `origin` = GitHub lớp, `gitlab` = repo bạn; `git push gitlab session/06` |
| Job pending forever | Không có runner tag `local`, hoặc instance runners đang bật | Bật runner laptop **trên project của bạn**, tắt instance runners |
| `docker: command not found` | Docker Desktop tắt / không có trong PATH của Windows Service | Mở Docker Desktop; đăng nhập lại Windows sau khi cài Docker; `gitlab-runner restart` |
| `model_loaded: false` | Build image khi chưa có `models/*.pkl` | Chạy Bước 0d train, rồi `dvc repro` + `train.py` |
| `validate_config` FAIL data path | Chưa có CSV raw | Lấy data buổi 02 vào `data/raw/kc_house_data.csv` |
| `train` FAIL R2 | Ngưỡng quá cao hoặc data lệch | Xem `reports/evaluation.json`, nới `thresholds.yaml` có chủ đích |
| Cổng 8000 already allocated | Còn container/uvicorn buổi 05 | `docker compose down`; `docker rm -f house-price-api` |
| PowerShell `ruff` không chạy | Chưa activate venv | `venv\Scripts\activate` rồi chạy lại |
| `gitlab-runner status` stopped | Service chưa start | `.\gitlab-runner.exe start` trong `C:\GitLab-Runner` |

---

## Bài tập sau buổi học

1. **CT từ GitLab UI** — Build → Pipelines → Run pipeline. Source `web` luôn chạy job `train`. So sánh với push chỉ sửa README (train skipped).
2. **Fail-then-fix** — đặt `n_estimators: 0`, push lên **gitlab của bạn**, chỉ ra job nào FAIL. Sửa lại, push, xác nhận deploy chạy.
3. **Gắn SHA vào health** — thêm field `git_sha` vào `HealthResponse` đọc từ `MODEL_VERSION`.
4. **Chặn deploy khi test FAIL** — cố tình phá 1 unit test, push, chứng minh container cũ không bị thay (so `loaded_at` trước/sau).

---

## Buổi tiếp theo

**Buổi 07 — Monitoring, Metrics và Drift Detection**: Prometheus trên FastAPI, log, phát hiện data drift, alert. Pipeline buổi 06 là chỗ cắm job drift sau này.
