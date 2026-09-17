import pickle
import os
from datetime import datetime

class ModelHolder:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoder = None
        self.version = os.environ.get("MODEL_VERSION", "0.1.0")
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
