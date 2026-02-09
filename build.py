"""PyInstaller build script for DCF Financial Modeler."""
import os
import shutil
import sys

try:
    import PyInstaller.__main__
except ImportError:
    print("PyInstaller not installed. Install with: pip install pyinstaller")
    sys.exit(1)

# Clean previous builds
for d in ("dist", "build"):
    if os.path.exists(d):
        shutil.rmtree(d)

# Platform-specific separator for --add-data
sep = ";" if sys.platform == "win32" else ":"

PyInstaller.__main__.run([
    "backend/main.py",
    "--name=DCF_Modeler",
    "--onefile",
    "--windowed",
    f"--add-data=frontend{sep}frontend",
    f"--add-data=templates{sep}templates",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols",
    "--hidden-import=uvicorn.protocols.http",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--hidden-import=uvicorn.protocols.websockets",
    "--hidden-import=uvicorn.protocols.websockets.auto",
    "--hidden-import=uvicorn.lifespan",
    "--hidden-import=uvicorn.lifespan.on",
    "--hidden-import=backend.engine.distributions",
    "--hidden-import=backend.engine.calculator",
    "--hidden-import=backend.engine.sensitivity",
    "--hidden-import=backend.engine.terminal_value",
    "--hidden-import=backend.models.stream",
    "--hidden-import=backend.models.model",
    "--hidden-import=backend.services.persistence",
    "--hidden-import=backend.services.excel_export",
    "--hidden-import=backend.api.routes",
    "--clean",
])

print("\nBuild complete! Executable is in dist/DCF_Modeler")
