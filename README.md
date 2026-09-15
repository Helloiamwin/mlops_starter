# Buổi 05 — Docker và FastAPI Model Serving

> **Dataset:** [House Sales in King County, USA](https://www.kaggle.com/datasets/harlfoxem/housesalesprediction) (`data/raw/kc_house_data.csv`), raw `data/raw/kc_house_data.csv` (~21510 rows; `sqft_living→area`, `yr_built→age`, `zipcode→location`, `floors`).
> Chuẩn bị lại: `# column mapping in src/ingestion/ingest.py`

## Mục tiêu buổi học

- Xây dựng pipeline data + training (ingest → validate → preprocess → split → train)
- Xây dựng API serving với FastAPI: `/health`, `/predict`, `/model-info`
- Hiểu 3 loại inference: batch, online, streaming
- Đóng gói ứng dụng với Docker
- Viết integration test cho API

---

## Kiến thức lý thuyết

### 3 loại Inference

| Loại | Mô tả | Ví dụ | Đặc điểm |
|------|--------|-------|-----------|
| **Batch** | Xử lý hàng loạt dữ liệu theo lịch | Cron job chạy dự đoán mỗi đêm | Throughput cao, latency không quan trọng |
| **Online** | Real-time REST API, trả kết quả ngay | Người dùng gửi request, nhận prediction | Low latency (< 200ms), đồng bộ |
| **Streaming** | Event-driven, xử lý liên tục | Kafka consumer nhận event và dự đoán | Bất đồng bộ, throughput cao, near real-time |

### FastAPI

- Framework Python hiện đại, hỗ trợ **async/await**
- Tự động sinh tài liệu API (Swagger UI tại `/docs`, ReDoc tại `/redoc`)
- Validation dữ liệu đầu vào với **Pydantic**
- Hiệu năng cao nhờ Starlette và Uvicorn (ASGI)
- Type hints giúp code rõ ràng, dễ bảo trì

### Docker

| Khái niệm | Giải thích |
|------------|------------|
| **Image** | Bản thiết kế bất biến chứa code, dependencies, runtime |
| **Container** | Thực thể đang chạy từ image, cô lập với hệ thống host |
| **Dockerfile** | File kịch bản định nghĩa cách build image |
| **Layer caching** | Mỗi lệnh trong Dockerfile tạo một layer; Docker cache layer không đổi để build nhanh hơn |

### API Contract

**Input** — `POST /predict`:
```json
{
  "area": 2000,
  "bedrooms": 3,
  "bathrooms": 2,
  "age": 10,
  "floors": 1.0,
  "location": "98178"
}
```

**Output**:
```json
{
  "predicted_price": 512345.67,
  "model_version": "0.1.0",
  "timestamp": "2026-09-16T00:41:00.000000"
}
```

---

## Cấu trúc file liên quan

```
mlops_starter/
├── src/
│   ├── ingestion/ingest.py       # Đọc raw CSV, map cột (sqft_living→area, ...)
│   ├── validation/validate.py    # Kiểm tra schema, null, range, duplicate
│   ├── preprocessing/preprocess.py  # Scale numeric, encode location -> models/scaler.pkl, models/label_encoder.pkl
│   ├── split/split.py            # Train/val/test split -> data/processed/{train,val,test}.csv
│   └── training/train.py         # Train GradientBoostingRegressor -> models/model.pkl, reports/evaluation.json
├── app/
│   ├── main.py                   # FastAPI app, endpoints (/health, /predict, /model-info)
│   ├── schemas.py                # Pydantic models cho request/response
│   ├── model_loader.py           # ModelHolder: load model.pkl/scaler.pkl/label_encoder.pkl từ models/
│   └── predictors/
│       └── tabular.py            # Logic dự đoán: scale numeric, encode location, gọi model.predict
├── configs/params.yaml           # Config data path, feature list, training params
├── dvc.yaml                      # Pipeline stages: ingest, validate, preprocess, split
├── Dockerfile                    # Đóng gói ứng dụng (copy app/, models/, configs/)
├── tests/
│   └── test_api.py               # Integration tests cho API
└── scripts/
    └── sample_predict.py         # Script gửi request mẫu tới http://localhost:8000
```

---

## Hướng dẫn thực hành

### Bước 1: Checkout branch

```bash
git checkout session-05-docker-fastapi
```

### Bước 2: Cài dependencies

```bash
pip install -r requirements.txt
pip install fastapi uvicorn httpx python-multipart
```

### Bước 3: Chạy pipeline data + training (bắt buộc trước khi serve API)

`models/` cần chứa `model.pkl`, `scaler.pkl`, `label_encoder.pkl` thì API mới load được model. Các file này **không** có sẵn trong repo (`models/` chỉ có `.gitkeep`) — phải tự chạy pipeline để tạo ra:

```bash
python src/ingestion/ingest.py        # đọc data/raw/kc_house_data.csv, map cột
python src/validation/validate.py     # kiểm tra schema/null/range/duplicate
python src/preprocessing/preprocess.py  # tạo data/processed/processed.csv, models/scaler.pkl, models/label_encoder.pkl
python src/split/split.py             # tạo data/processed/{train,val,test}.csv
python src/training/train.py          # train model, tạo models/model.pkl, reports/evaluation.json
```

Hoặc chạy toàn bộ 4 stage đầu bằng DVC (lưu ý: `train` hiện **chưa** có trong `dvc.yaml`, nên vẫn cần chạy `train.py` thủ công như trên):

```bash
dvc repro
python src/training/train.py
```

Kết quả mong đợi sau khi train xong:
```
[Training] Metrics:
  val_rmse: ...
  val_mae: ...
  val_r2: 0.75~0.78
  test_rmse: ...
  test_mae: ...
  test_r2: 0.78~0.80
[Training] Model saved to models/model.pkl
[Training] Evaluation saved to reports/evaluation.json
```

Kiểm tra lại:
```bash
ls models/
# label_encoder.pkl  model.pkl  scaler.pkl  .gitkeep
```

### Bước 4: Chạy API local

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Lưu ý:** Model được load một lần khi API khởi động (`@app.on_event("startup")` trong `app/main.py`). Nếu bạn train model **sau khi** API đã chạy, endpoint `/health` vẫn sẽ báo `model_loaded: false` — phải **restart lại process** (Ctrl+C rồi chạy lại lệnh uvicorn) để nó load model mới.

### Bước 5: Test thủ công bằng trình duyệt hoặc curl

Mở trình duyệt và truy cập **Swagger UI**:

```
http://localhost:8000/docs
```

Hoặc dùng curl:

```bash
curl http://localhost:8000/health
```

### Bước 6: Test endpoint `/health`

```bash
curl -X GET http://localhost:8000/health
```

Kết quả mong đợi (sau khi model đã load thành công):
```json
{
  "status": "healthy",
  "model_loaded": true,
  "timestamp": "2026-09-16T00:45:00.000000"
}
```

### Bước 7: Build Docker image

```bash
docker build -t house-price-api .
```

> Dockerfile copy cả `app/`, `models/` và `configs/` vào image — nghĩa là **phải chạy xong Bước 3 (train xong `models/*.pkl`) trước khi build**, nếu không container sẽ khởi động với `model_loaded: false` giống hệt vấn đề ở Bước 4.

### Bước 8: Chạy Docker container

```bash
docker run -p 8000:8000 house-price-api
```

Kiểm tra container đang chạy:
```bash
docker ps
```

### Bước 9: Chạy tests

```bash
pytest -v
```

Toàn bộ test (`tests/test_api.py`, `tests/test_data.py`, `tests/test_training.py`) không phụ thuộc vào việc API đang chạy hay không — chúng import trực tiếp module Python.

### Bước 10: Dùng script gửi request mẫu

```bash
python scripts/sample_predict.py
```

Script gọi `/health`, `/model-info`, `/predict` tới `http://localhost:8000` và in kết quả ra terminal. Yêu cầu API đang chạy (Bước 4) **và** đã load được model (Bước 3).

Kết quả mong đợi:
```
Health: {'status': 'healthy', 'model_loaded': True, 'timestamp': '...'}
Model Info: {
  "model_type": "GradientBoostingRegressor",
  "model_version": "0.1.0",
  "features": ["area", "bedrooms", "bathrooms", "age", "floors", "location"],
  "loaded_at": "..."
}
Prediction: {
  "predicted_price": ...,
  "model_version": "0.1.0",
  "timestamp": "..."
}
```

### Bước 11: Phân biệt 3 loại inference (thực hành nhẹ)

Buổi này API đang phục vụ **online inference** (`POST /predict`).

**Online (đang làm):**

```bash
python scripts/sample_predict.py
```

**Batch (mô phỏng):** gọi API nhiều lần như nightly batch job:

```powershell
1..5 | ForEach-Object { python scripts/sample_predict.py }
```

**Streaming (khái niệm):** không bắt buộc code Kafka trong lab. Hãy viết 5–7 dòng vào `docs/inference-notes.md` giải thích khác biệt latency/throughput giữa batch / online / streaming áp dụng cho bài house price.

---

## Chi tiết code

### `app/schemas.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class PredictRequest(BaseModel):
    area: float = Field(..., gt=0, description="Living area in sqft")
    bedrooms: int = Field(..., ge=0)
    bathrooms: float = Field(..., ge=0)
    age: int = Field(..., ge=0)
    floors: float = Field(..., gt=0)
    location: str = Field(..., description="Zipcode")

class PredictResponse(BaseModel):
    predicted_price: float
    model_version: str
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    timestamp: str

class ModelInfoResponse(BaseModel):
    model_type: str
    model_version: str
    features: list
    loaded_at: str
```

### `app/model_loader.py`

```python
import pickle
import os
from datetime import datetime

class ModelHolder:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.version = "0.1.0"
        self.loaded_at = None

    def load(self, model_dir="models"):
        model_path = os.path.join(model_dir, "model.pkl")
        scaler_path = os.path.join(model_dir, "scaler.pkl")
        encoder_path = os.path.join(model_dir, "label_encoder.pkl")

        with open(model_path, "rb") as f:
            self.model = pickle.load(f)
        with open(scaler_path, "rb") as f:
            self.scaler = pickle.load(f)
        with open(encoder_path, "rb") as f:
            self.label_encoder = pickle.load(f)

        self.loaded_at = datetime.now().isoformat()
        print(f"[ModelHolder] Model loaded from {model_dir}")

    @property
    def is_loaded(self):
        return self.model is not None

model_holder = ModelHolder()
```

### `app/predictors/tabular.py`

```python
import numpy as np
from app.model_loader import model_holder

def predict_price(area, bedrooms, bathrooms, age, floors, location):
    holder = model_holder

    loc_encoded = holder.label_encoder.transform([location])[0]

    numeric_features = np.array([[area, bedrooms, bathrooms, age, floors]])
    numeric_scaled = holder.scaler.transform(numeric_features)

    features = np.append(numeric_scaled[0], loc_encoded).reshape(1, -1)

    prediction = holder.model.predict(features)[0]
    return float(prediction)
```

### `app/main.py`

```python
from fastapi import FastAPI, HTTPException
from datetime import datetime
from app.schemas import PredictRequest, PredictResponse, HealthResponse, ModelInfoResponse
from app.model_loader import model_holder
from app.predictors.tabular import predict_price

app = FastAPI(title="House Price Prediction API", version="0.1.0")

@app.on_event("startup")
def startup_event():
    try:
        model_holder.load()
    except Exception as e:
        print(f"[API] Failed to load model: {e}")

@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy" if model_holder.is_loaded else "unhealthy",
        model_loaded=model_holder.is_loaded,
        timestamp=datetime.now().isoformat(),
    )

@app.get("/model-info", response_model=ModelInfoResponse)
def model_info():
    if not model_holder.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return ModelInfoResponse(
        model_type="GradientBoostingRegressor",
        model_version=model_holder.version,
        features=["area", "bedrooms", "bathrooms", "age", "floors", "location"],
        loaded_at=model_holder.loaded_at,
    )

@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    if not model_holder.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        price = predict_price(
            area=request.area,
            bedrooms=request.bedrooms,
            bathrooms=request.bathrooms,
            age=request.age,
            floors=request.floors,
            location=request.location,
        )
        return PredictResponse(
            predicted_price=round(price, 2),
            model_version=model_holder.version,
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn

COPY app/ ./app/
COPY models/ ./models/
COPY configs/ ./configs/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- Dùng `python:3.11-slim` để giảm kích thước image
- Copy `requirements.txt` trước để tận dụng **layer caching** (chỉ cài lại khi file thay đổi)
- Copy `models/` và `configs/` vào image — image chỉ hoạt động đúng nếu `models/` đã có `model.pkl`, `scaler.pkl`, `label_encoder.pkl` **trước khi build** (xem Bước 3 và Bước 7)
- `EXPOSE 8000` khai báo cổng cho container
- `CMD` chạy Uvicorn khi container khởi động

---

## Xử lý sự cố (Troubleshooting)

### `model_loaded: false` dù đã train xong model

Nguyên nhân phổ biến nhất: **API server được khởi động trước khi `models/*.pkl` tồn tại**. `ModelHolder.load()` chỉ chạy một lần lúc startup (`@app.on_event("startup")`), nên tạo file model sau đó không có tác dụng cho tới khi restart.

Cách khắc phục:
1. Đảm bảo đã chạy xong Bước 3 (pipeline + train) và `models/` có đủ 3 file `.pkl`.
2. Dừng process uvicorn đang chạy (`Ctrl+C`, hoặc `kill <pid>` nếu chạy nền) và khởi động lại.
3. Nếu server chạy trong Docker, cần `docker build` lại sau khi có model (vì `models/` được COPY vào image tại thời điểm build), rồi `docker run` lại container.
4. Chạy lại `python scripts/sample_predict.py` để xác nhận `model_loaded: true`.

### `tests/test_api.py::test_schemas_import` fail

Test hiện tại tạo `PredictRequest(area=2000, ..., location="98178")` nhưng lại assert `req.area == 120` và `req.location == "District_1"` — đây là lỗi trong chính file test (giá trị assert không khớp giá trị vừa truyền vào), không phải lỗi của `app/schemas.py`. Cần sửa lại assertion cho khớp input trước khi coi test này là hợp lệ.

---

## Bài tập sau buổi học

1. **Thêm stage `train` vào `dvc.yaml`** để `dvc repro` chạy được toàn bộ pipeline ingest → validate → preprocess → split → train trong một lệnh, thay vì phải chạy `train.py` thủ công.

2. **Thêm endpoint `/predict/batch`** — nhận danh sách nhiều mẫu dữ liệu, trả về danh sách prediction. Sử dụng `list[PredictRequest]` làm input.

3. **Thêm input validation** — trong `schemas.py`, thêm validator kiểm tra các giá trị số phải hợp lệ (vd. `age` không vượt quá năm hiện tại). Dùng `@field_validator` của Pydantic v2.

4. **Viết thêm test cases** — trong `tests/test_api.py`, thêm test cho trường hợp: request thiếu field, request có giá trị âm, request body rỗng. Kiểm tra API trả về đúng mã lỗi (422).

5. **Tối ưu Dockerfile** — thêm `.dockerignore` để loại trừ `__pycache__`, `.git`, `*.pyc`, `data/`. So sánh kích thước image trước và sau khi tối ưu.

---

## Buổi tiếp theo

**Buổi 06 — CI/CD và Quality Gate**: Xây dựng pipeline CI/CD tự động với GitLab CI, thiết lập quality gates (lint, test, validate config, build Docker), và viết script kiểm tra cấu hình dự án.
