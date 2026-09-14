# Buổi 04 — Model Registry và Model Governance

> **Dataset:** [House Sales in King County, USA](https://www.kaggle.com/datasets/harlfoxem/housesalesprediction)  
> Tiếp nối Buổi 03: dùng run đã log trên MLflow Tracking để đăng ký, validate, promote và rollback trên **Model Registry**.

## Mục tiêu buổi học

- Hiểu vì sao cần Model Registry sau experiment tracking
- Mô tả lifecycle: Candidate → Validation → Staging → Production → Rollback/Retire
- Phân biệt Registry (kỹ thuật/version) và Governance (ai duyệt, audit, traceability)
- Đăng ký ≥2 version vào MLflow Registry từ run Buổi 3
- Chạy automated validation theo `configs/thresholds.yaml` (pass → Staging, fail → Rejected)
- Human approve Staging → Production, rồi demo rollback
- Điền Model Card + bảng traceability + audit log

```text
Buổi 3: Train + Experiment Tracking
              ↓
Buổi 4: Select best → Register → Validate → Approve → Production → Rollback
```

---

## Kiến thức lý thuyết

### 1. Vì sao cần Registry và Governance?

Sau nhiều lần train, doanh nghiệp cần trả lời:

- Model nào được phép dùng? Version nào đang Production?
- Ai phê duyệt? Train bằng dataset / git commit nào?
- Model mới có vượt validation không? Rollback về đâu khi lỗi?

Registry + Governance biến các file `model.pkl` rời rạc thành quy trình có version, trạng thái, người chịu trách nhiệm và lịch sử.

### 2. Model Registry

Kho quản lý model đủ điều kiện xem xét triển khai. Mỗi version thường gắn:

| Trường | Ví dụ |
| --- | --- |
| name / version | `house-price-model` / `1` |
| source run | `runs:/abc123/model` |
| metrics | `test_r2`, `test_rmse` |
| tags | `git_commit`, `dataset_version`, `validation_status` |
| stage / alias | `Staging`, `Production` / `staging`, `champion` |

### 3. Lifecycle

```text
Development → Experiment → Candidate → Validation
                                      ├── Rejected
                                      └── Staging → Human Approve → Production
                                                                  ├── Continue
                                                                  └── Rollback / Retire
```

| Trạng thái | Ý nghĩa trong lab |
| --- | --- |
| Candidate | Vừa register, chưa validate |
| Staging | Automated validation PASSED |
| Production | Human approve (alias `champion`) |
| Rejected | Metric dưới ngưỡng |
| Archived | Bị thay khi promote version mới |

### 4. Validation vs Approval

- **Automated validation:** so metrics run nguồn với `thresholds.yaml` (R²/RMSE/MAE). Pass → Staging.
- **Human approval:** checklist + promote Production (lab mô phỏng bằng script + tag `approved_by`).

Không đưa thẳng Production chỉ vì test metric đẹp.

### 5. Governance, Audit, Traceability

```text
Prediction → Model version → Run → Git commit → Dataset version → Metrics → Approval history
```

Mỗi thay đổi stage nên ghi audit: ai, khi nào, version trước/sau, lý do.

### 6. Rollback

Giữ artifact version cũ. Khi Production mới lỗi: chuyển alias/stage về version ổn định trước — **không** đồng nghĩa retrain ngay.

### 7. MLflow: Tracking vs Registry

```text
Training Runs (Buổi 3)
    ↓ Select best
Register Model
    ↓ Candidate
Validate / Approve
    ↓
Production version + aliases
```

---

## Cấu trúc file buổi 4

```text
configs/thresholds.yaml              # Ngưỡng tabular / offline validation
scripts/register_model.py            # Register top-N runs vào Registry
scripts/validate_and_promote.py      # Auto validate → Staging hoặc Rejected
scripts/promote_model.py             # Human approve → Production
scripts/rollback_model.py            # Rollback Production + audit
scripts/show_registry.py             # In trạng thái Registry
scripts/validate_model.py            # Offline check reports/evaluation.json
docs/model-card.md                   # Model Card
reports/governance_audit.jsonl       # Audit trail (tạo khi chạy script)
```

---

## Hướng dẫn thực hành

### Bước 0: Chuẩn bị

```powershell
git checkout session/04
```

Cần MLflow UI + ít nhất 1 run FINISHED có artifact `model` (từ Buổi 3):

```powershell
mlflow ui --port 5000
```

Nếu chưa có run / data:

```powershell
python src/ingestion/ingest.py
python src/validation/validate.py
python src/preprocessing/preprocess.py
python src/split/split.py
$env:PYTHONUTF8="1"
python src/training/train.py
```

Đổi hyperparams trong `configs/params.yaml` (ví dụ `n_estimators: 50`) rồi train thêm 1 lần để có **≥2 runs** (phục vụ reject + rollback).

### Bước 1: Offline validation (evaluation.json)

```powershell
python scripts/validate_model.py
```

Đọc `reports/evaluation.json` so với `configs/thresholds.yaml`. Exit 0 = pass, 1 = fail (dùng được trong CI).

### Bước 2: Xem ngưỡng Registry

```yaml
tabular:
  r2_min: 0.75
  rmse_max: 200000
  mae_max: 120000
```

| Key | Metric run | Ý nghĩa |
| --- | --- | --- |
| `r2_min` | `test_r2` | R² test tối thiểu |
| `rmse_max` | `test_rmse` | RMSE test tối đa (USD) |
| `mae_max` | `test_mae` | MAE test tối đa |

### Bước 3: Register ≥2 version

```powershell
$env:PYTHONUTF8="1"
$env:MLFLOW_TRACKING_URI="http://localhost:5000"
python scripts/register_model.py --model-name house-price-model --n 2
python scripts/show_registry.py
```

Script chọn top run theo `test_r2` (có artifact `model`), gắn tag `git_commit`, `dataset_version`, `lifecycle=Candidate`.

Mở http://localhost:5000/#/models → `house-price-model`.

### Bước 4: Automated validation → Staging / Rejected

```powershell
python scripts/validate_and_promote.py --model-name house-price-model --version 1 --track tabular
python scripts/validate_and_promote.py --model-name house-price-model --version 2 --track tabular
python scripts/show_registry.py
```

- Pass → stage/alias **Staging**, tag `validation_status=passed`
- Fail → **không** promote, tag `validation_status=rejected`, exit code 1

Muốn chắc có 1 version reject: tạm tăng `r2_min: 0.99` trong `thresholds.yaml`, validate version kém hơn, rồi trả lại ngưỡng.

### Bước 5: Human approve → Production

Checklist:

```text
[ ] validation_status=passed
[ ] evaluation / metrics ổn
[ ] đủ metadata (run_id, git_commit)
[ ] có người approve (lab: --approved-by)
```

```powershell
python scripts/promote_model.py --model-name house-price-model --version 1 --approved-by ml-lead --reason "pass offline gate"
python scripts/show_registry.py
```

### Bước 6: Rollback

Giả sử Production mới có vấn đề (lab: promote version khác rồi rollback):

```powershell
python scripts/rollback_model.py --model-name house-price-model --to-version 1 --reason "canary error_rate spike (lab demo)"
python scripts/show_registry.py
```

Audit ghi vào `reports/governance_audit.jsonl`.

### Bước 7: Traceability + Model Card

Điền bảng (mẫu):

| Thông tin | Giá trị |
| --- | --- |
| Model name/version | house-price-model / 1 |
| Experiment run | `<run_id>` |
| Dataset version | kc_house_data_session02 |
| Git commit | `git rev-parse --short HEAD` |
| Metrics | test_r2 / test_rmse / test_mae |
| Validated by | automated_pipeline |
| Approved by | ml-lead |
| Rollback target | version ổn định trước đó |

Chỉnh `docs/model-card.md` cho khớp metrics thật.

Chuỗi audit mẫu:

```text
POST /predict → house-price-model v1 (champion)
    → run <run_id> → git commit → dataset version → metrics → approved_by
```

### Bước 8 (tuỳ chọn): So sánh run Buổi 3

```powershell
python scripts/compare_runs.py --n 5
```

---

## Sản phẩm cuối buổi

- [ ] ≥2 version trong Registry
- [ ] 1 version Staging (pass) và demo 1 version Rejected (fail)
- [ ] 1 version Production / alias `champion`
- [ ] Rollback có lý do + dòng trong `governance_audit.jsonl`
- [ ] Model Card đã điền
- [ ] Bảng traceability của nhóm

---

## Bài tập sau buổi

1. Siết ngưỡng (`r2_min: 0.80`) và quan sát version nào bị reject.
2. Gộp train → register → validate thành một script CI.
3. Bổ sung fairness theo `location` vào Model Card.
4. (Nâng cao) Đọc phần canary/shadow trong giáo trình Buổi 4 — chuẩn bị cho serving Buổi 5.

---

## Buổi tiếp theo

**Buổi 05 — Docker + FastAPI Serving**: đóng gói model Production, API predict, health check.
