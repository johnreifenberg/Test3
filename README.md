# Inflection

A DCF (Discounted Cash Flow) financial modeling application with Monte Carlo simulation, sensitivity analysis, and interactive visualization. Built as a local single-user web application with a FastAPI backend and vanilla HTML/CSS/JS frontend.

## Features

- **Deterministic DCF Analysis** - Calculate NPV and IRR using expected values for all parameters
- **Monte Carlo Simulation** - Run thousands of scenarios with stochastic distributions to quantify risk
- **Sensitivity Analysis** - Tornado charts showing which inputs drive the most value
- **NPV and IRR Modes** - Choose between Net Present Value or Internal Rate of Return as the primary calculation
- **Distribution Support** - Fixed, Normal, Lognormal, Uniform, Triangular, Logistic (S-curve adoption), and Linear distributions
- **Parent-Child Stream Relationships** - Model derived revenue/costs with conversion rates, trigger delays, and periodic renewals
- **Unit Value x Market Units Mode** - Specify base amounts as price per unit times quantity, each with their own distribution
- **Adoption Curves** - Logistic (S-curve) or Linear adoption models for gradual market penetration
- **Escalation Rates** - Global annual escalation applied to all streams, compounded monthly
- **Terminal Value** - Gordon Growth Model perpetuity for streams extending beyond the forecast horizon
- **Excel Export** - Download results with summary, cashflows, stream details, sensitivity data, and distribution histograms
- **Model Persistence** - Save/load models as JSON files
- **Bundled Templates** - SaaS, perpetual software, and professional services starter models
- **Single Executable** - Package as a standalone `.exe` with PyInstaller

## How It Works

### Streams

Each financial model consists of **streams** representing individual revenue or cost items. Streams are the fundamental building blocks:

- **Root streams** have a base amount (or unit value x market units) and an optional adoption curve
- **Child streams** derive their value from a parent stream, with a conversion rate, optional trigger delay, and optional renewal period
- Costs are automatically negated in cashflow calculations

### Calculation Flow

1. Streams are topologically sorted by parent-child dependencies
2. Root stream cashflows are computed per month: `amount * adoption_factor * escalation`
3. Child stream cashflows are derived from parent values: `parent_value * ratio * conversion_rate`
4. All stream cashflows are summed into total monthly cashflows
5. NPV mode: discount total cashflows and add terminal value for perpetual streams
6. IRR mode: find the discount rate that makes NPV = 0 using `scipy.optimize.brentq`

### Monte Carlo

Each simulation independently samples all stochastic parameters (amounts, discount rate, escalation rate) and runs the full calculation. Results include mean, median, standard deviation, and P10/P25/P75/P90 percentiles, plus a histogram of the outcome distribution.

## Project Structure

```
dcf-modeler/
  backend/
    main.py                  # FastAPI app entry point, static file serving, uvicorn
    api/
      routes.py              # REST endpoints for model CRUD, streams, calculations, export
    engine/
      calculator.py          # DCF calculator: NPV, IRR, deterministic & Monte Carlo
      distributions.py       # Distribution sampling, deterministic values, percentiles, previews
      sensitivity.py         # Tornado analysis: identify uncertain params, sweep P10/P90
      terminal_value.py      # Gordon Growth Model terminal value calculation
    models/
      model.py               # FinancialModel, ModelSettings dataclasses
      stream.py              # Stream, Distribution, DistributionType, StreamType dataclasses
    services/
      persistence.py         # JSON save/load, template discovery
      excel_export.py        # Multi-sheet Excel export with openpyxl
  frontend/
    index.html               # Single-page app with modals for streams and templates
    css/
      styles.css             # Complete UI styling with CSS variables
    js/
      api-client.js          # Fetch wrapper: GET, POST, PUT, DELETE, file upload/download
      app.js                 # App initialization, model operations, result display
      charts.js              # Chart.js wrappers: line, bar, histogram, tornado charts
      model-builder.js       # Stream modal logic, distribution param rendering, form handling
  templates/
    saas_model.json           # SaaS subscription template with adoption curve
    perpetual_software.json   # One-time license with maintenance/support child streams
    professional_services.json # Consulting model with project-based revenue
  tests/
    test_calculator.py        # Calculator tests: NPV, IRR, streams, unit value, Monte Carlo
    test_distributions.py     # Distribution engine tests: all types, previews, linear
    test_model.py             # Model tests: CRUD, validation, serialization, topological sort
  inflection.spec             # PyInstaller spec for single-file Windows executable
  requirements.txt            # Python dependencies
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/model` | Get current model state |
| POST | `/api/model/new` | Create a new model |
| PUT | `/api/model/settings` | Update model settings (preserves streams) |
| POST | `/api/model/load` | Upload and load a model JSON file |
| GET | `/api/model/save` | Download current model as JSON |
| GET | `/api/model/templates` | List available templates |
| POST | `/api/model/template/{name}` | Load a template |
| POST | `/api/streams` | Add a new stream |
| PUT | `/api/streams/{id}` | Update an existing stream |
| DELETE | `/api/streams/{id}` | Delete a stream |
| POST | `/api/calculate/deterministic` | Run deterministic analysis |
| POST | `/api/calculate/monte-carlo` | Run Monte Carlo simulation |
| POST | `/api/calculate/sensitivity` | Run sensitivity/tornado analysis |
| POST | `/api/preview-distribution` | Preview a distribution as a time series |
| GET | `/api/export/excel` | Export results to Excel |

## Running Locally

```bash
pip install -r requirements.txt
python backend/main.py
```

The app starts on `http://127.0.0.1:8765` and opens your browser automatically.

## Running Tests

```bash
python -m pytest tests/ -v
```

## Building the Executable

```bash
pip install pyinstaller
pyinstaller inflection.spec --noconfirm
```

The output is `dist/Inflection.exe` (~57 MB). Double-click to launch.

## Dependencies

- **FastAPI** + **uvicorn** - Web framework and ASGI server
- **numpy** - Numerical computation and random sampling
- **scipy** - IRR root-finding via `brentq`
- **openpyxl** - Excel file generation
- **pydantic** - Request validation
- **python-multipart** - File upload support
- **Chart.js** (CDN) - Frontend charting
