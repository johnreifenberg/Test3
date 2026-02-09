# Build Prompt: Inflection DCF Financial Modeler

Use this prompt with Claude Code to reproduce the Inflection app from scratch.

---

## Overview

Build a local single-user DCF (Discounted Cash Flow) financial modeling web application called **Inflection**. It uses a **FastAPI** backend (Python) with a **vanilla HTML/CSS/JavaScript** frontend. The app runs on `http://127.0.0.1:8765` and opens the browser automatically on startup. All state is held in memory (no database). Chart.js is loaded from CDN for visualization.

## Dependencies

```
fastapi==0.109.0
uvicorn==0.27.0
numpy==1.26.3
scipy
openpyxl==3.1.2
pydantic==2.5.3
python-multipart==0.0.6
```

## Project Structure

```
dcf-modeler/
  backend/
    __init__.py                  (empty)
    main.py                      FastAPI app entry point, static file serving, uvicorn
    api/
      __init__.py                (empty)
      routes.py                  REST endpoints for model CRUD, streams, calculations, export
    engine/
      __init__.py                (empty)
      calculator.py              DCF calculator: NPV, IRR, deterministic & Monte Carlo
      distributions.py           Distribution sampling, deterministic values, percentiles, previews
      sensitivity.py             Sensitivity/tornado analysis: identify uncertain params, sweep P10/P90
      terminal_value.py          Gordon Growth Model terminal value calculation
    models/
      __init__.py                (empty)
      model.py                   FinancialModel, ModelSettings dataclasses
      stream.py                  Stream, Distribution, DistributionType, StreamType dataclasses
    services/
      __init__.py                (empty)
      persistence.py             JSON save/load, template discovery
      excel_export.py            Multi-sheet Excel export with openpyxl
  frontend/
    index.html                   Single-page app with modals for streams and templates
    css/
      styles.css                 Complete UI styling with CSS variables
    js/
      api-client.js              Fetch wrapper: GET, POST, PUT, DELETE, file upload/download
      app.js                     App initialization, model operations, result display
      charts.js                  Chart.js wrappers: line, bar, histogram, tornado charts
      model-builder.js           Stream modal logic, distribution param rendering, form handling
  templates/
    saas_model.json              SaaS subscription template with logistic adoption curve
    perpetual_software.json      One-time license with maintenance/support child streams
    professional_services.json   Consulting model with project-based revenue
  tests/
    __init__.py                  (empty)
    test_calculator.py           Calculator tests: NPV, IRR, streams, unit value, Monte Carlo
    test_distributions.py        Distribution engine tests: all types, previews, linear
    test_model.py                Model tests: CRUD, validation, serialization, topological sort
  inflection.spec                PyInstaller spec for single-file executable
  requirements.txt               Python dependencies
```

---

## Data Model

### Distribution

A probability distribution used for any uncertain parameter. Stored as `{type, params}`.

**DistributionType enum** (string values): `FIXED`, `NORMAL`, `LOGNORMAL`, `UNIFORM`, `TRIANGULAR`, `LOGISTIC`, `LINEAR`

**Parameters by type:**

| Type | Params | Deterministic Value | Notes |
|------|--------|-------------------|-------|
| FIXED | `{value}` | `value` | Constant value |
| NORMAL | `{mean, std}` | `mean` | Gaussian |
| LOGNORMAL | `{mean, std}` | `exp(mean + std^2/2)` | Log-normal (params are in log-space) |
| UNIFORM | `{min, max}` | `(min+max)/2` | Uniform between min and max |
| TRIANGULAR | `{min, likely, max}` | `(min+likely+max)/3` | Triangular |
| LOGISTIC | `{midpoint, steepness, amplitude}` | See below | S-curve adoption; returns **incremental** (derivative) |
| LINEAR | `{rate, amplitude}` | `amplitude * rate` | Constant monthly adoption rate |

**LOGISTIC details (critical):** This returns the *incremental* adoption per month (the derivative of the logistic S-curve), NOT the cumulative S-curve value. Formula: `amplitude * steepness * S(t) * (1 - S(t))` where `S(t) = 1 / (1 + exp(-steepness * (month - midpoint)))`. The `amplitude` parameter defaults to 1.0. This is used as a multiplier on the base amount each month (e.g., month 0 near zero, ramp up, peak around midpoint, then taper).

**LINEAR details:** Returns a constant value `amplitude * rate` every month. Used for constant-rate adoption curves. After `1/rate` months, cumulative adoption reaches `amplitude`.

**Percentiles:** For FIXED, LOGISTIC, and LINEAR, `get_percentile()` returns the deterministic value (no uncertainty). For stochastic types, it samples 10,000 values and computes the requested percentile.

**Preview timeseries:** Returns a list of `{month, value}` (or `{month, mean, p10, p90}` for stochastic types) for chart previewing. Respects `start_month` and `end_month` (inclusive), returning 0 for inactive months.

### Stream

A financial stream (revenue or cost item). Fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| id | str | required | Unique identifier |
| name | str | required | Display name |
| stream_type | StreamType | required | `REVENUE` or `COST` |
| start_month | int | required | First active month (0-indexed) |
| end_month | int? | None | Last active month (inclusive). None = perpetual |
| amount | Distribution | required | Base amount distribution |
| adoption_curve | Distribution? | None | Adoption multiplier (LOGISTIC or LINEAR). Root streams only |
| parent_stream_id | str? | None | Parent stream ID (makes this a child stream) |
| conversion_rate | float | 1.0 | Fraction of parent events that trigger child (0.0-1.0) |
| trigger_delay_months | int | 0 | Months after parent event before child event |
| periodicity_months | int? | None | Child event recurrence period. None = single concurrent event |
| amount_is_ratio | bool | True | If true, child amount is a ratio of parent value; if false, absolute |
| unit_value | Distribution? | None | Per-unit price distribution (alternative to amount) |
| market_units | Distribution? | None | Number of units distribution (alternative to amount) |

**Unit value mode:** When both `unit_value` and `market_units` are set on a root stream, the calculator computes `sample(unit_value) * sample(market_units)` instead of using `amount`. The `amount` field should still be set to a dummy `FIXED 0` for serialization.

### ModelSettings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| forecast_months | int | 60 | Number of months to simulate |
| discount_rate | Distribution | FIXED 0.10 | Annual discount rate |
| terminal_growth_rate | float | 0.025 | Gordon Growth Model terminal growth rate |
| escalation_rate | Distribution? | None | Annual escalation rate applied to all streams |
| calculation_mode | str | "NPV" | `"NPV"` or `"IRR"` |

**Validation:** In NPV mode, `discount_rate > terminal_growth_rate` is enforced. In IRR mode, this check is skipped (discount rate is not used).

### FinancialModel

Top-level container:
- `name: str`
- `settings: ModelSettings`
- `streams: Dict[str, Stream]` (keyed by stream ID)

Provides:
- `add_stream()`, `remove_stream()` (also clears parent references on children)
- `get_children(parent_id)` - list child streams
- `validate()` - checks parent references exist, conversion_rate in [0,1], detects circular dependencies via DFS, validates discount_rate > terminal_growth_rate (NPV mode only)
- `get_execution_order()` - topological sort (BFS/Kahn's algorithm) of stream IDs by parent-child dependencies
- `to_dict()` / `from_dict()` serialization

---

## Calculation Engine

### Root Stream Cashflows

For each month `m` in `[start_month, end_month]`:

1. **Base amount:** If `unit_value` and `market_units` are set, compute `sample(unit_value, month=m) * sample(market_units, month=m)`. Otherwise, sample `amount` distribution (with `month=m` for time-dependent types like LOGISTIC).
2. **Escalation:** If global escalation rate is set, apply compound monthly escalation: `amount *= (1 + annual_esc/12) ^ months_elapsed` where `months_elapsed = m - start_month`.
3. **Adoption curve:** If set, multiply by adoption factor: `amount *= sample(adoption_curve, month=m)`.
4. **Sign:** If `stream_type == COST`, negate: `cashflows = -abs(cashflows)`.

### Child Stream Cashflows

For each parent month `pm` with non-zero cashflow:

1. Sample child `amount` once per simulation run.
2. Compute event value: if `amount_is_ratio`, then `event_val = |parent_val| * child_amount * conversion_rate`; if absolute, then `event_val = child_amount * conversion_rate`.
3. Place event at `first_event = pm + trigger_delay_months`.
4. If `periodicity_months` is set, repeat event at every `periodicity_months` interval from `first_event`.
5. Apply escalation if set, based on months from `stream.start_month`.
6. Costs are negated.

### NPV Calculation

```
monthly_rate = discount_rate / 12
NPV = sum(cashflow[t] / (1 + monthly_rate)^t for t in 0..n_months)
```

### Terminal Value (Gordon Growth Model)

Identify perpetual streams (no `end_month` or `end_month >= forecast_months`). For each:

```
TV = final_month_cashflow * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
PV(TV) = TV / (1 + monthly_rate)^forecast_months
```

Add PV(TV) to NPV. If `discount_rate <= terminal_growth_rate`, terminal value = 0.

### IRR Calculation

Uses `scipy.optimize.brentq` to find the monthly rate where NPV = 0, then annualizes by multiplying by 12.

1. Verify sign change exists (both positive and negative cashflows).
2. Call `brentq(npv_at_rate, -0.5, 10.0, xtol=1e-10, maxiter=1000)`.
3. Return `(monthly_irr * 12, None)` on success, `(None, error_message)` on failure.

### Deterministic Mode

- **NPV mode:** Compute all streams deterministically, calculate NPV + terminal value + informational IRR. Returns `{npv, irr, irr_error, terminal_value, discount_rate, cashflows, stream_details}`.
- **IRR mode:** Compute all streams deterministically, calculate IRR only. Returns `{npv: 0.0, irr, irr_error, terminal_value: null, discount_rate: null, cashflows, stream_details}`.

### Monte Carlo Mode

Run `n_simulations` (default 10,000) independent passes, sampling all stochastic distributions each time.

- **NPV mode:** Each pass samples discount rate, escalation, all stream amounts. Collect NPV array. Return mean, median, std, P10/P25/P75/P90, full distribution array, cashflow_distributions (per-month mean/median/P10/P90).
- **IRR mode:** Each pass computes IRR. Track failed count. Return IRR stats (mean, median, std, percentiles), full distribution array, failed_count.

If sampled discount rate <= terminal growth rate during Monte Carlo NPV, clamp to `terminal_growth_rate + 0.001`.

### Sensitivity / Tornado Analysis

1. Identify all non-FIXED distributions in the model (discount_rate, escalation_rate, stream amounts, unit_value, market_units).
2. Run baseline deterministic calculation.
3. For each uncertain parameter, override to P10 and P90 (as FIXED), run deterministic, record NPV.
4. Compute swing = |NPV_high - NPV_low|.
5. Sort by swing descending, return top 15.

The override/restore pattern temporarily replaces the distribution with a FIXED value, runs the calculation, then restores the original.

---

## API Endpoints

All endpoints are prefixed with `/api`.

| Method | Endpoint | Request Body | Description |
|--------|----------|-------------|-------------|
| GET | `/model` | - | Get current model state |
| POST | `/model/new` | `NewModelRequest` | Create a new model (wipes streams) |
| PUT | `/model/settings` | `NewModelRequest` | Update settings on existing model (preserves streams) |
| POST | `/model/load` | multipart file upload | Upload and load a model JSON file |
| GET | `/model/save` | - | Download current model as JSON |
| GET | `/model/templates` | - | List available templates |
| POST | `/model/template/{name}` | - | Load a named template |
| POST | `/streams` | `StreamRequest` | Add a new stream |
| PUT | `/streams/{id}` | `StreamRequest` | Update an existing stream |
| DELETE | `/streams/{id}` | - | Delete a stream |
| POST | `/calculate/deterministic` | - | Run deterministic analysis |
| POST | `/calculate/monte-carlo` | `{n_simulations: int}` | Run Monte Carlo simulation |
| POST | `/calculate/sensitivity` | - | Run sensitivity/tornado analysis |
| POST | `/preview-distribution` | `{distribution, months, start_month, end_month?}` | Preview a distribution as a time series |
| GET | `/export/excel` | - | Export results to Excel |

### Pydantic Request Schemas

**NewModelRequest:**
```python
name: str = "Untitled Model"
forecast_months: int = 60
terminal_growth_rate: float = 0.025
discount_rate: dict = {"type": "NORMAL", "params": {"mean": 0.12, "std": 0.02}}
escalation_rate: Optional[dict] = None
calculation_mode: str = "NPV"
```

**StreamRequest:**
```python
id: str
name: str
stream_type: str  # "REVENUE" or "COST"
start_month: int
end_month: Optional[int] = None
amount: dict  # Distribution dict
adoption_curve: Optional[dict] = None
parent_stream_id: Optional[str] = None
conversion_rate: float = 1.0
trigger_delay_months: int = 0
periodicity_months: Optional[int] = None
amount_is_ratio: bool = True
unit_value: Optional[dict] = None
market_units: Optional[dict] = None
```

### Session State

In-memory `AppSession` class with:
- `model: Optional[FinancialModel]` (initialized to empty FinancialModel)
- `last_results: Optional[dict]` (cleared on model/settings changes)
- `last_sensitivity: Optional[dict]` (cleared on model/settings changes)

---

## Frontend

### index.html

Single-page app layout:

1. **Header:** App title "Inflection" with toolbar buttons: New, Load, Save, Templates.
2. **Settings panel** (left sidebar):
   - Model name input
   - Forecast months input
   - Calculation mode selector (NPV / IRR) with help text
   - Discount rate section (hidden in IRR mode): distribution type dropdown + dynamic params
   - Terminal growth rate input (hidden in IRR mode)
   - Escalation rate toggle + section: distribution type dropdown + dynamic params
   - Update Settings button
3. **Streams panel** (left sidebar): stream list with Add Stream button.
4. **Main content area** with tabs:
   - **Cashflows tab:** combined preview chart + per-stream amount/adoption previews
   - **Results tab:** deterministic/MC/sensitivity results
5. **Calculation controls:** Deterministic, Monte Carlo (with simulation count input), Sensitivity buttons. Export Excel button (initially hidden).
6. **Stream modal:** Full form for adding/editing streams:
   - ID, name, type (Revenue/Cost), start/end month
   - Parent stream dropdown (None = root stream)
   - Formula bar showing the cashflow formula
   - **Root stream fields:** Amount entry mode toggle (Total Dollars / Unit Value x Quantity), amount distribution inputs, unit value/market units distribution inputs with estimated total display, adoption curve toggle + inputs
   - **Child stream fields:** Amount is ratio checkbox, child amount distribution inputs, conversion rate, trigger delay, periodicity
7. **Template modal:** Grid of available templates.

**Script loading order:** api-client.js, model-builder.js, charts.js, app.js. Chart.js loaded from CDN.

### api-client.js

`ApiClient` class wrapping `fetch()`:
- `get(endpoint)`, `post(endpoint, data)`, `put(endpoint, data)`, `delete(endpoint)` - all return parsed JSON, throw on non-OK response.
- `uploadFile(endpoint, file)` - FormData multipart upload.
- `downloadFile(endpoint, filename)` - blob download with temporary anchor element.
- Global instance: `const api = new ApiClient('/api')`.

### model-builder.js

**Distribution parameter templates:** Five sets of parameter configs:
- `DIST_PARAMS` - general amount parameters (all 7 distribution types)
- `CHILD_RATIO_PARAMS` - child stream ratio parameters (FIXED, NORMAL, UNIFORM, TRIANGULAR)
- `CHILD_ABSOLUTE_PARAMS` - child stream absolute value parameters
- `UNIT_VALUE_PARAMS` - per-unit price parameters (FIXED, NORMAL, LOGNORMAL, UNIFORM, TRIANGULAR)
- `MARKET_UNITS_PARAMS` - market units quantity parameters

Each entry maps distribution type to `[{key, label, default}]`.

**Key functions:**
- `renderDistParams(containerId, distType, prefix, existingParams, labelOverrides)` - generates form inputs for a distribution type
- `renderChildDistParams(containerId, distType, prefix, existingParams, isRatio)` - renders child-specific params
- `renderSpecificDistParams(containerId, distType, prefix, existingParams, paramSet)` - renders from a specific param set
- `getDistFromInputs(distTypeSelectId, paramsContainerId)` - collects distribution from form inputs
- `getSpecificDistFromInputs(distTypeSelectId, prefix, paramSet)` - collects from specific param set
- `getDeterministicEstimate(dist)` - client-side deterministic value for estimated total display
- `updateEstimatedTotal()` - updates the "Estimated Total" display for unit value mode
- `toggleAmountEntryMode()` - shows/hides total vs unit value input sections
- `toggleCalculationMode()` - shows/hides discount rate and terminal growth sections based on NPV/IRR
- `showStreamModal(streamId?)` - opens modal, populates form for edit or blank for add
- `saveStream(e)` - collects form data, sends POST or PUT to API
- `renderStreamList(model)` - renders stream cards with edit/delete buttons
- `renderCashflowsTab(model)` - renders combined preview + per-stream distribution previews
- `previewDistribution(streamId, paramName, dist, startMonth, endMonth)` - calls preview API, renders chart
- `updateFormulaBar()` - updates formula display based on stream type and entry mode

### app.js

**Key functions:**
- `init()` - setup event listeners, load model
- `createNewModel()` - prompts for name, POSTs to `/model/new`
- `loadModelFromFile()` - file input, uploads to `/model/load`
- `saveModelToFile()` - downloads JSON via `/model/save`
- `showTemplateSelector()` - fetches templates, shows modal
- Update Settings handler: PUTs to `/model/settings` (preserves streams)
- `renderModel()` - updates all UI from `currentModel`
- `runDeterministic()`, `runMonteCarlo()`, `runSensitivity()` - call calculation APIs
- `displayDeterministicResults(results)` - branches on NPV/IRR mode, shows result cards + cashflow bar chart
- `displayMonteCarloResults(results)` - branches on NPV/IRR mode, shows stats cards + histogram
- `displaySensitivityResults(results)` - shows tornado chart + data table
- `exportExcel()` - downloads Excel file

**NPV result cards:** NPV, IRR, Terminal Value (PV), Discount Rate.
**IRR result cards:** IRR value (or error message).
**MC NPV cards:** Mean, Median, Std Dev, P10, P25, P75, P90.
**MC IRR cards:** Mean, Median, Std Dev, P10, P90, Failed Simulations (if any).

### charts.js

`ChartManager` class managing Chart.js instances:
- `renderDistributionPreview(canvasId, previewData)` - line chart for distribution timeseries (with P10/P90 bands for stochastic types)
- `renderCombinedCashflowChart(canvasId, streamDetails, streamMeta)` - multi-line chart, green palette for revenue, red for cost
- `renderCashflowChart(canvasId, cashflows)` - bar chart, green for positive, red for negative
- `renderNPVDistribution(canvasId, npvData, xLabel?)` - histogram with 50 bins. Optional `xLabel` for IRR mode: "IRR (%)"
- `renderTornadoChart(canvasId, sensitivityData)` - horizontal bar chart sorted by swing
- `createHistogramBins(data, numBins, isPercent)` - bin data for histograms, format as "$Xk" or "X%" labels

All charts use `destroyChart()` cleanup before re-rendering.

### styles.css

CSS variables for theming (dark-blue header, light background, card-based layout). Key classes:
- `.app-layout` - CSS grid layout (sidebar + main)
- `.result-card` - metric display cards in grid
- `.stream-item` - stream list items with badges and actions
- `.modal-overlay` / `.modal` - modal dialogs
- `.tab` / `.tab-content` - tab switching
- `.badge-revenue` (green), `.badge-cost` (red)
- `.estimated-total` - highlighted unit value total display

---

## Excel Export

Multi-sheet workbook with openpyxl:

1. **Summary:** Model name, forecast months, calculation mode, key results (NPV/IRR stats), key assumptions.
2. **Monthly Cashflows:** Transposed layout - streams as rows, months as columns. Includes Total, Discounted CF, and Cumulative NPV rows. Frozen pane at B2.
3. **Stream Details:** All stream configuration (ID, name, type, timing, distributions, parent info, unit value/market units).
4. **Sensitivity Analysis:** Parameter table with swing, NPV low/high, P10/P90 values.
5. **NPV/IRR Distribution:** Percentile table (P1-P99) + histogram data (50 bins). Sheet title and formatting adapts to NPV vs IRR mode.

Uses styled headers (bold, light blue fill), currency format `"$"#,##0.00`, percent format `0.00%`.

---

## JSON Persistence

**Save:** `model.to_dict()` + `_metadata: {version: "1.0", created, last_modified}`, written as indented JSON.

**Load:** Read JSON, strip `_metadata` and `_comment`, call `FinancialModel.from_dict()`.

**Templates:** Discovered from `templates/` directory. In PyInstaller frozen mode, looks in `sys._MEIPASS/templates/`; otherwise, in the project root `templates/` directory.

---

## Model Templates

Create three starter template JSON files:

1. **saas_model.json** - "SaaS Subscription Model": Monthly subscription revenue with logistic adoption curve, customer support cost as child stream (ratio of revenue), infrastructure cost.

2. **perpetual_software.json** - "Perpetual Software Model": One-time license fee with adoption curve, annual maintenance child stream (recurring every 12 months), professional services child stream (one-time with delay).

3. **professional_services.json** - "Professional Services Model": Project-based consulting revenue, direct labor cost as ratio of revenue, overhead cost as fixed monthly amount.

---

## PyInstaller Packaging

Create `inflection.spec` for single-file executable:
- Entry point: `backend/main.py`
- Bundle `frontend/` and `templates/` as data
- Hidden imports: all uvicorn submodules (logging, loops, protocols, lifespan), all backend modules, `multipart`
- Single-file mode (`onefile`), console=True, name='Inflection'

The app must detect frozen mode (`sys.frozen`) and use `sys._MEIPASS` as base directory for:
- Static file serving in `main.py`
- Template directory in `persistence.py`

---

## Entry Point (main.py)

```python
app = FastAPI(title="Inflection API")
# CORS middleware (allow all)
# Determine base directory (sys._MEIPASS for frozen, dirname for dev)
# Add project root to sys.path
# Mount frontend as /static
# Include API router
# Root "/" redirects to /static/index.html
# On __main__: Timer(1.5, open_browser), uvicorn.run on 127.0.0.1:8765
```

---

## Tests

Write comprehensive tests using pytest. Target ~40-50 tests covering:

### test_distributions.py
- All 7 distribution types: sample, get_deterministic_value
- LOGISTIC: verify incremental behavior, month dependency, zero when no month
- LINEAR: verify constant output, amplitude scaling
- get_percentile: FIXED returns exact value, stochastic returns reasonable values
- preview_timeseries: deterministic vs stochastic output format, start/end month bounds

### test_calculator.py
- NPV calculation: verify discounting, zero rate
- IRR calculation: valid cashflows with sign change, no sign change error
- Root stream cashflows: basic, with adoption curve, cost negation, escalation
- Child stream cashflows: ratio mode, absolute mode, trigger delay, periodicity
- Unit value x market units: product calculation, fallback to amount when not set
- Deterministic NPV mode: complete result structure
- Deterministic IRR mode: result structure, no discount rate
- Monte Carlo NPV: result statistics structure
- Monte Carlo IRR: result statistics, failed count tracking

### test_model.py
- FinancialModel: create, add/remove streams, parent reference cleanup
- Validation: missing parent, circular dependency detection, discount rate vs terminal growth
- Topological sort: correct execution order
- Serialization: to_dict/from_dict roundtrip
- ModelSettings: calculation_mode field, defaults
- Distribution: to_dict/from_dict for all types

---

## Key Design Decisions

1. **Monthly time periods** - all calculations use months, not years.
2. **In-memory state** - single AppSession, no persistence between restarts.
3. **LOGISTIC returns incremental adoption** - the derivative of the S-curve, not the cumulative value. This is critical for correct cashflow calculations.
4. **Costs are negated** - `cashflows = -abs(cashflows)` ensures costs are always negative regardless of input sign.
5. **IRR uses scipy.optimize.brentq** - robust root-finding in range [-0.5, 10.0], annualized by multiplying monthly rate by 12.
6. **Sensitivity uses override/restore** - temporarily replaces distributions with FIXED values, runs deterministic, restores originals.
7. **Update Settings preserves streams** - PUT `/model/settings` updates settings on existing model; POST `/model/new` creates fresh model.
8. **Child amount sampled once per simulation** - not per-month, for consistency within a single MC run.
9. **Terminal value only in NPV mode** - IRR mode skips terminal value calculation entirely.
10. **Escalation compounded monthly** - `(1 + annual_rate/12)^months_elapsed` from stream start, not model start.
