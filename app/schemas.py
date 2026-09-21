from pydantic import BaseModel, Field

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
