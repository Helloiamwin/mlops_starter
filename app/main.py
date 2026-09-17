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
        status="healthy v3333" if model_holder.is_loaded else "unhealthy",
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
