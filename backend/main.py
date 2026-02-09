import os
import sys
import webbrowser
from threading import Timer

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Inflection API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Determine base directory (works for both dev and PyInstaller)
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add project root to sys.path so backend imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Serve frontend static files
frontend_dir = os.path.join(BASE_DIR, "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# Include API routes
from backend.api.routes import router
app.include_router(router)


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")


def open_browser():
    webbrowser.open("http://127.0.0.1:8765")


if __name__ == "__main__":
    Timer(1.5, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
