# Model Card — House Price Prediction

## Thông tin chung

| Mục | Chi tiết |
|-----|----------|
| Tên model (Registry) | house-price-model |
| Thuật toán | GradientBoostingRegressor |
| Framework | scikit-learn |
| Experiment | house-price-prediction |
| Owner | MLOps lab / ml-lead |

## Mục đích sử dụng

Dự đoán giá nhà (USD) tại King County từ đặc trưng tabular: area, bedrooms, bathrooms, age, floors, location.

**Ngoài phạm vi:** thị trường ngoài King County, dữ liệu sau 2015 chưa retrain, định giá pháp lý/tín dụng chính thức.

## Dữ liệu huấn luyện

- Nguồn: Kaggle House Sales in King County (`kc_house_data.csv`)
- Mapping: `sqft_living→area`, `yr_built→age`, `zipcode→location`
- Split: theo `configs/params.yaml` / phiên bản DVC buổi 2
- Preprocess: LabelEncoder (`location`), StandardScaler (numeric)

## Đặc trưng

| Feature | Mô tả |
|---------|--------|
| area | Diện tích sống (sqft) |
| bedrooms / bathrooms | Số phòng |
| age | 2015 - yr_built |
| floors | Số tầng |
| location | Zipcode đã encode |

(Tuỳ run Buổi 3 có thể thêm feature engineered: total_rooms, bath_bed_ratio, ...)

## Metrics chấp nhận (lab)

Xem `configs/thresholds.yaml`:

- `test_r2 >= 0.75`
- `test_rmse <= 200000`
- `test_mae <= 120000`

Điền số liệu run Production thật sau khi promote:

| Tập | RMSE | MAE | R² |
|-----|------|-----|-----|
| Validation | | | |
| Test | | | |

## Governance

| Bước | Cách làm trong lab |
|------|---------------------|
| Register | `scripts/register_model.py` |
| Auto validate | `scripts/validate_and_promote.py` → Staging / Rejected |
| Approve | `scripts/promote_model.py` → Production + tag `approved_by` |
| Rollback | `scripts/rollback_model.py` + `reports/governance_audit.jsonl` |

## Rủi ro và hạn chế

- Dữ liệu 2014–2015; drift giá thị trường hiện tại
- Zipcode lạ / outlier diện tích làm sai số lớn
- Feature engineered không đảm bảo luôn tốt hơn baseline

## Liên hệ cập nhật

1. Detect drift (Buổi 7) → thu thập data → DVC version mới  
2. Retrain + log MLflow (Buổi 3)  
3. Register → validate → approve (Buổi 4)  
4. Redeploy serving (Buổi 5)
