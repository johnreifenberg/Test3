import json
import os
import sys
from datetime import datetime
from typing import Dict

from backend.models.model import FinancialModel


def save_model(model: FinancialModel, filepath: str) -> None:
    data = model.to_dict()
    data["_metadata"] = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "last_modified": datetime.now().isoformat(),
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_model(filepath: str) -> FinancialModel:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Strip metadata before parsing
    data.pop("_metadata", None)
    data.pop("_comment", None)
    model = FinancialModel.from_dict(data)
    return model


def get_template_dir() -> str:
    """Get the templates directory path."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "templates")


def get_model_templates() -> Dict[str, FinancialModel]:
    templates = {}
    template_dir = get_template_dir()
    if not os.path.isdir(template_dir):
        return templates
    for fname in os.listdir(template_dir):
        if fname.endswith(".json"):
            name = fname.replace(".json", "")
            try:
                model = load_model(os.path.join(template_dir, fname))
                templates[name] = model
            except Exception:
                continue
    return templates
