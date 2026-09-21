import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_schemas_import():
    from app.schemas import PredictRequest

    req = PredictRequest(area=2000, bedrooms=3, bathrooms=2, age=5, floors=1.0, location="98178")
    assert req.area == 2000
    assert req.location == "98178"


def test_predict_request_validation():
    from pydantic import ValidationError

    from app.schemas import PredictRequest

    try:
        PredictRequest(area=-10, bedrooms=3, bathrooms=2, age=5, floors=1.0, location="98178")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_health_response():
    from app.schemas import HealthResponse

    resp = HealthResponse(status="healthy", model_loaded=True, timestamp="2024-01-01T00:00:00")
    assert resp.status == "healthy"
