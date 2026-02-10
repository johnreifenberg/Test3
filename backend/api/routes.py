import io
import json
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from backend.models.stream import Distribution, DistributionType, Stream, StreamType
from backend.models.model import (
    FinancialModel,
    ModelSettings,
    ModelValidationError,
    CircularDependencyError,
)
from backend.engine.distributions import DistributionEngine
from backend.engine.calculator import DCFCalculator
from backend.engine.sensitivity import SensitivityAnalyzer
from backend.services.persistence import save_model, load_model, get_model_templates
from backend.services.excel_export import ExcelExporter

router = APIRouter(prefix="/api")


# ── Session state ──────────────────────────────────────────────────────
class AppSession:
    def __init__(self):
        self.model: Optional[FinancialModel] = FinancialModel()
        self.last_results: Optional[dict] = None
        self.last_sensitivity: Optional[dict] = None


session = AppSession()


def _require_model() -> FinancialModel:
    if session.model is None:
        raise HTTPException(status_code=400, detail="No model loaded. Create or load a model first.")
    return session.model


# ── Pydantic request schemas ──────────────────────────────────────────
class NewModelRequest(BaseModel):
    name: str = "Untitled Model"
    forecast_months: int = 60
    terminal_growth_rate: float = 0.025
    discount_rate: dict = {"type": "NORMAL", "params": {"mean": 0.12, "std": 0.02}}
    escalation_rate: Optional[dict] = None
    calculation_mode: str = "NPV"


class StreamRequest(BaseModel):
    id: str
    name: str
    stream_type: str
    start_month: int
    end_month: Optional[int] = None
    amount: dict
    adoption_curve: Optional[dict] = None
    parent_stream_id: Optional[str] = None
    conversion_rate: float = 1.0
    trigger_delay_months: int = 0
    periodicity_months: Optional[int] = None
    amount_is_ratio: bool = True
    unit_value: Optional[dict] = None
    market_units: Optional[dict] = None


class ReorderRequest(BaseModel):
    order: List[str]


class MonteCarloRequest(BaseModel):
    n_simulations: int = 10000


class PreviewDistributionRequest(BaseModel):
    distribution: dict
    months: int = 60
    start_month: int = 0
    end_month: Optional[int] = None


# ── Model Operations ─────────────────────────────────────────────────
@router.get("/model")
async def get_model():
    if session.model is None:
        return {"model": None}
    return session.model.to_dict()


@router.post("/model/new")
async def create_new_model(req: NewModelRequest):
    settings = ModelSettings(
        forecast_months=req.forecast_months,
        discount_rate=Distribution.from_dict(req.discount_rate),
        terminal_growth_rate=req.terminal_growth_rate,
        escalation_rate=Distribution.from_dict(req.escalation_rate) if req.escalation_rate else None,
        calculation_mode=req.calculation_mode,
    )
    session.model = FinancialModel(name=req.name, settings=settings)
    session.last_results = None
    session.last_sensitivity = None
    return session.model.to_dict()


@router.put("/model/settings")
async def update_model_settings(req: NewModelRequest):
    model = _require_model()
    model.name = req.name
    model.settings.forecast_months = req.forecast_months
    model.settings.discount_rate = Distribution.from_dict(req.discount_rate)
    model.settings.terminal_growth_rate = req.terminal_growth_rate
    model.settings.escalation_rate = Distribution.from_dict(req.escalation_rate) if req.escalation_rate else None
    model.settings.calculation_mode = req.calculation_mode
    session.last_results = None
    session.last_sensitivity = None
    return model.to_dict()


@router.post("/model/load")
async def load_model_file(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content)
        data.pop("_metadata", None)
        session.model = FinancialModel.from_dict(data)
        session.last_results = None
        session.last_sensitivity = None
        return session.model.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load model: {str(e)}")


@router.get("/model/save")
async def save_model_file():
    model = _require_model()
    data = model.to_dict()
    data["_metadata"] = {"version": "1.0"}
    content = json.dumps(data, indent=2)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={model.name.replace(' ', '_')}.json"},
    )


@router.get("/model/templates")
async def list_templates():
    templates = get_model_templates()
    return {name: tpl.to_dict() for name, tpl in templates.items()}


@router.post("/model/template/{name}")
async def load_template(name: str):
    templates = get_model_templates()
    if name not in templates:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    session.model = templates[name]
    session.last_results = None
    session.last_sensitivity = None
    return session.model.to_dict()


# ── Stream Operations ────────────────────────────────────────────────
@router.post("/streams")
async def add_stream(req: StreamRequest):
    model = _require_model()
    try:
        stream = Stream(
            id=req.id,
            name=req.name,
            stream_type=StreamType(req.stream_type),
            start_month=req.start_month,
            end_month=req.end_month,
            amount=Distribution.from_dict(req.amount),
            adoption_curve=Distribution.from_dict(req.adoption_curve) if req.adoption_curve else None,
            parent_stream_id=req.parent_stream_id,
            conversion_rate=req.conversion_rate,
            trigger_delay_months=req.trigger_delay_months,
            periodicity_months=req.periodicity_months,
            amount_is_ratio=req.amount_is_ratio,
            unit_value=Distribution.from_dict(req.unit_value) if req.unit_value else None,
            market_units=Distribution.from_dict(req.market_units) if req.market_units else None,
        )
        model.add_stream(stream)
        return model.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/streams/{stream_id}")
async def update_stream(stream_id: str, req: StreamRequest):
    model = _require_model()
    if stream_id not in model.streams:
        raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
    try:
        stream = Stream(
            id=req.id,
            name=req.name,
            stream_type=StreamType(req.stream_type),
            start_month=req.start_month,
            end_month=req.end_month,
            amount=Distribution.from_dict(req.amount),
            adoption_curve=Distribution.from_dict(req.adoption_curve) if req.adoption_curve else None,
            parent_stream_id=req.parent_stream_id,
            conversion_rate=req.conversion_rate,
            trigger_delay_months=req.trigger_delay_months,
            periodicity_months=req.periodicity_months,
            amount_is_ratio=req.amount_is_ratio,
            unit_value=Distribution.from_dict(req.unit_value) if req.unit_value else None,
            market_units=Distribution.from_dict(req.market_units) if req.market_units else None,
        )
        # Remove old, add new
        if stream_id != req.id:
            model.remove_stream(stream_id)
        model.streams[req.id] = stream
        return model.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str):
    model = _require_model()
    try:
        model.remove_stream(stream_id)
        return model.to_dict()
    except ModelValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/streams/reorder")
async def reorder_streams(req: ReorderRequest):
    model = _require_model()
    try:
        model.reorder_streams(req.order)
        return model.to_dict()
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Calculation Endpoints ────────────────────────────────────────────
@router.post("/calculate/deterministic")
async def run_deterministic():
    model = _require_model()
    try:
        model.validate()
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    calc = DCFCalculator(model)
    results = calc.run_deterministic()
    session.last_results = results
    return results


@router.post("/calculate/monte-carlo")
async def run_monte_carlo(req: MonteCarloRequest):
    model = _require_model()
    try:
        model.validate()
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    calc = DCFCalculator(model)
    results = calc.run_monte_carlo(n_simulations=req.n_simulations)
    session.last_results = results
    return results


@router.post("/calculate/sensitivity")
async def run_sensitivity():
    model = _require_model()
    try:
        model.validate()
    except ModelValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    analyzer = SensitivityAnalyzer(model)
    results = analyzer.run_tornado_analysis()
    session.last_sensitivity = results
    return results


# ── Utility Endpoints ────────────────────────────────────────────────
@router.post("/preview-distribution")
async def preview_distribution(req: PreviewDistributionRequest):
    try:
        dist = Distribution.from_dict(req.distribution)
        preview = DistributionEngine.preview_timeseries(
            dist, months=req.months, start_month=req.start_month, end_month=req.end_month,
        )
        return {"preview": preview}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/export/excel")
async def export_excel():
    model = _require_model()
    if session.last_results is None:
        raise HTTPException(status_code=400, detail="Run a calculation before exporting")
    exporter = ExcelExporter(model, session.last_results, session.last_sensitivity)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    exporter.export(tmp.name)
    return FileResponse(
        tmp.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="dcf_results.xlsx",
    )
