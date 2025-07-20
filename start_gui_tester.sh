#!/bin/bash
# Shell script to launch GUI tester in UV environment (Linux/macOS)

echo "🔧 SD MCP Server - GUI Tester Launcher"
echo "======================================"

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo "✅ UV found: $(uv --version)"

# Check if in UV project
if [ ! -f "pyproject.toml" ]; then
    echo "❌ pyproject.toml not found - not a UV project"
    exit 1
fi

if [ ! -f "uv.lock" ]; then
    echo "⚠️  uv.lock not found - run 'uv sync' first"
    exit 1
fi

echo "✅ UV environment detected"

# Function to check GUI dependencies
check_gui_deps() {
    uv run python -c "import tkinter; from PIL import Image" 2>/dev/null
    return $?
}

# Install GUI dependencies if needed
if ! check_gui_deps; then
    echo "📦 Installing GUI dependencies..."
    uv add --dev pillow
    
    if ! check_gui_deps; then
        echo "❌ Failed to install GUI dependencies"
        exit 1
    fi
fi

echo "✅ GUI dependencies available"

# Launch GUI
echo "🚀 Launching GUI Tester..."
uv run python gui_tester.py

if [ $? -eq 0 ]; then
    echo "✅ GUI Tester closed successfully"
else
    echo "❌ GUI Tester exited with error"
    exit 1
fi