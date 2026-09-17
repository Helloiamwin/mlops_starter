import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_schemas_import():
    from app.schemas import PredictRequest, PredictResponse, HealthResponse, ModelInfoResponse
    assert PredictResponse is not None
    assert HealthResponse is not None
    assert ModelInfoResponse is not None
    req = PredictRequest(area=2000, bedrooms=3, bathrooms=2, age=5, floors=1.0, location="98178")
    assert req.area == 2000
    assert req.location == "98178"

def test_predict_request_validation():
    from app.schemas import PredictRequest
    from pydantic import ValidationError
    try:
        PredictRequest(area=-10, bedrooms=3, bathrooms=2, age=5, floors=1.0, location="98178")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

def test_health_response():
    from app.schemas import HealthResponse
    resp = HealthResponse(status="healthy", model_loaded=True, timestamp="2024-01-01T00:00:00")
    assert resp.status == "healthy"
