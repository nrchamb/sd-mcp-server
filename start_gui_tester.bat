@echo off
REM Windows batch file to launch GUI tester in UV environment

echo 🔧 SD MCP Server - GUI Tester Launcher (Windows)
echo ================================================

REM Check if UV is installed
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ UV not found. Install from: https://docs.astral.sh/uv/getting-started/installation/
    pause
    exit /b 1
)

REM Check if in UV project
if not exist "pyproject.toml" (
    echo ❌ pyproject.toml not found - not a UV project
    pause
    exit /b 1
)

if not exist "uv.lock" (
    echo ⚠️  uv.lock not found - run 'uv sync' first
    pause
    exit /b 1
)

echo ✅ UV environment detected

REM Install GUI dependencies if needed
echo 📦 Ensuring GUI dependencies are available...
uv add --dev pillow >nul 2>&1

REM Launch GUI
echo 🚀 Launching GUI Tester...
uv run python gui_tester.py

if %errorlevel% neq 0 (
    echo ❌ Failed to launch GUI tester
    pause
    exit /b 1
)

echo ✅ GUI Tester closed successfully
pause