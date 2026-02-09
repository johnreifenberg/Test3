# Building Inflection on Ubuntu

Complete instructions for building the Inflection DCF Financial Modeler on Ubuntu Linux, including how to produce both a Linux and Windows executable.

## Prerequisites

Ubuntu 22.04 LTS or later (also works on 24.04). You need Python 3.10+ and git.

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

Verify Python is available:

```bash
python3 --version   # Should be 3.10 or later
```

## Clone the Repository

```bash
git clone https://github.com/johnreifenberg/Inflection.git
cd Inflection
```

## Set Up Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
python -m pytest tests/ -v
```

All tests should pass before proceeding.

## Run the Application (Development)

```bash
python backend/main.py
```

The app starts on `http://127.0.0.1:8765` and attempts to open a browser automatically. If running on a headless server, open the URL manually from a machine with browser access.

Press `Ctrl+C` to stop the server.

---

## Building the Linux Executable

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build

```bash
pyinstaller inflection.spec --noconfirm
```

This creates `dist/Inflection` (a single Linux executable, ~50-60 MB).

### Test the Linux Executable

```bash
./dist/Inflection
```

Navigate to `http://127.0.0.1:8765` in your browser. Verify:
- The app loads and displays the "Inflection" title
- Templates load when you click the Templates button
- Creating a model and running deterministic analysis works
- Excel export downloads a valid `.xlsx` file

Press `Ctrl+C` to stop.

### Make Portable

You can copy the single `dist/Inflection` file to any Linux machine with a compatible architecture (x86_64). No Python installation is required on the target machine.

---

## Building the Windows Executable (Cross-Compilation)

Cross-compiling a PyInstaller executable from Linux to Windows is **not directly supported** by PyInstaller. There are two reliable approaches:

### Option A: Use a Windows VM or Machine

The simplest and most reliable approach.

1. Install Python 3.10+ on Windows from [python.org](https://www.python.org/downloads/).
2. Open Command Prompt or PowerShell:

```powershell
git clone https://github.com/johnreifenberg/Inflection.git
cd Inflection
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
pyinstaller inflection.spec --noconfirm
```

3. The output is `dist\Inflection.exe` (~57 MB). Double-click to launch.

### Option B: Use Wine on Ubuntu

Wine can run the Windows Python installer and PyInstaller. This is more complex but avoids needing a Windows machine.

#### 1. Install Wine

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y wine64 wine32
```

#### 2. Download and Install Windows Python Under Wine

```bash
# Download the Python 3.11 Windows installer (64-bit)
wget https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

# Run the installer under Wine
wine python-3.11.9-amd64.exe /quiet InstallAllUsers=0 PrependPath=1
```

Wait for the installer to complete. Python is installed to `~/.wine/drive_c/users/$USER/AppData/Local/Programs/Python/Python311/`.

#### 3. Verify Python Under Wine

```bash
wine python --version
```

#### 4. Install Dependencies Under Wine

```bash
wine python -m pip install --upgrade pip
wine python -m pip install -r requirements.txt
wine python -m pip install pyinstaller
```

#### 5. Build the Windows Executable

```bash
wine python -m PyInstaller inflection.spec --noconfirm
```

The output is `dist/Inflection.exe`. This is a native Windows executable.

#### 6. Test Under Wine (Optional)

```bash
wine dist/Inflection.exe
```

> **Note:** Wine-based builds may have occasional compatibility issues with certain native libraries. If you encounter problems, prefer Option A (native Windows build).

### Option C: GitHub Actions CI/CD

Automate both builds using a GitHub Actions workflow. Create `.github/workflows/build.yml`:

```yaml
name: Build Executables

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: python -m pytest tests/ -v
      - run: pyinstaller inflection.spec --noconfirm
      - uses: actions/upload-artifact@v4
        with:
          name: Inflection-Linux
          path: dist/Inflection

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: python -m pytest tests/ -v
      - run: pyinstaller inflection.spec --noconfirm
      - uses: actions/upload-artifact@v4
        with:
          name: Inflection-Windows
          path: dist/Inflection.exe
```

Push the workflow, then trigger a build by pushing a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Download the artifacts from the Actions tab on GitHub. This approach gives you both Linux and Windows executables from a single CI pipeline.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`

Ensure you run from the project root directory (where `backend/` is a subdirectory). The app adds the project root to `sys.path` at startup.

### PyInstaller hidden import errors

If PyInstaller fails with missing module errors, the `inflection.spec` file already includes hidden imports for uvicorn submodules and all backend modules. If you add new modules, add them to the `hiddenimports` list in the spec file.

### scipy build fails on Ubuntu

Install the system-level build dependencies:

```bash
sudo apt install -y python3-dev gfortran libopenblas-dev liblapack-dev
pip install scipy
```

### Port 8765 already in use

Kill any existing process on the port:

```bash
lsof -ti:8765 | xargs kill -9
```

### No browser opens on headless server

The app calls `webbrowser.open()` on startup. On headless servers, this is harmless — just navigate to `http://127.0.0.1:8765` manually or via SSH tunnel:

```bash
ssh -L 8765:localhost:8765 user@server
```

Then open `http://localhost:8765` in your local browser.
