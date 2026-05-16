#!/bin/bash

# Narrative Processor Web Viewer - START HERE
# Double-click this file to launch the web interface

# Get the directory where this script is located (server/)
cd "$(dirname "$0")"
SERVER_DIR="$(pwd)"
PROJECT_ROOT="$(cd .. && pwd)"

echo "=========================================="
echo "Narrative Processor Web Viewer"
echo "=========================================="
echo ""
echo "Starting server..."
echo "Project root: $PROJECT_ROOT"
echo "Server dir: $SERVER_DIR"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    osascript -e 'display dialog "Python 3 is not installed. Please install Python 3 first." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

PY="$(bash "$PROJECT_ROOT/scripts/project_python.sh" "$PROJECT_ROOT" 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "ERROR: Python 3 is not installed!"
    osascript -e 'display dialog "Python 3 is not installed. Please install Python 3 first." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi
echo "Python: $PY ($("$PY" --version 2>&1))"

# Check Flask; install into project .venv if missing
if ! "$PY" -c "import flask" 2>/dev/null; then
    echo "Flask not found — running setup (creates .venv if needed)..."
    if ! bash "$PROJECT_ROOT/scripts/setup_project_venv.sh" "$PROJECT_ROOT"; then
        osascript -e 'display dialog "Failed to install dependencies. Double-click narRaters_installer.command in the project folder, or run: bash scripts/setup_project_venv.sh ." buttons {"OK"} default button "OK" with icon stop'
        exit 1
    fi
    PY="$(bash "$PROJECT_ROOT/scripts/project_python.sh" "$PROJECT_ROOT")"
fi

# Check if port 5000 is already in use
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "WARNING: Port 5000 is already in use!"
    osascript -e 'display dialog "Port 5000 is already in use. Another server may be running. Please stop it first or check the Terminal window." buttons {"OK"} default button "OK" with icon caution'
    # Try to open browser anyway
    open "http://localhost:5000/pipeline-config" 2>/dev/null || open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null
    exit 0
fi

# Test if the file syntax is valid
echo "Testing server file..."
cd "$SERVER_DIR"
if ! "$PY" -m py_compile web-interface.py 2>/dev/null; then
    echo "ERROR: Server file has syntax errors!"
    "$PY" -m py_compile web-interface.py 2>&1 | head -20
    osascript -e 'display dialog "Server file has syntax errors. Check the Terminal for details." buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi
echo "✓ Server file syntax is valid"

# Start the server in a new Terminal window with better error handling
echo "Starting server in new Terminal window..."
osascript <<EOF
tell application "Terminal"
    activate
    set newTab to do script "cd '$SERVER_DIR' && clear && echo '==========================================' && echo 'Narrative Processor Web Viewer' && echo '==========================================' && echo '' && echo 'Project root: $PROJECT_ROOT' && echo 'Server directory: $SERVER_DIR' && echo '' && echo 'Starting server...' && echo '' && '$PY' web-interface.py 2>&1 || (echo '' && echo 'ERROR: Server failed to start!' && echo 'Check the error messages above.' && echo '' && read -p 'Press Enter to close this window...')"
end tell
EOF

# Brief pause then poll (server import is usually ~1–3s; avoid a long fixed wait)
echo "Waiting for server to start..."
sleep 1

# Check if server is ready (try up to 15 times with longer waits)
SERVER_READY=false
for i in {1..15}; do
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        echo "✓ Server is ready!"
        SERVER_READY=true
        break
    fi
    echo "Waiting for server... ($i/15)"
    sleep 1
done

if [ "$SERVER_READY" = false ]; then
    echo ""
    echo "⚠ WARNING: Server may not have started successfully."
    echo "Check the Terminal window for error messages."
    osascript -e 'display dialog "Server may not have started. Please check the Terminal window for error messages. The browser will open anyway - if the page does not load, check the Terminal for errors." buttons {"OK"} default button "OK" with icon caution'
fi

# Try to open browser to pipeline-config page directly
echo "Opening browser..."
open "http://localhost:5000/pipeline-config" 2>/dev/null || open "http://127.0.0.1:5000/pipeline-config" 2>/dev/null

echo ""
echo "=========================================="
if [ "$SERVER_READY" = true ]; then
    echo "✓ Server is running!"
else
    echo "⚠ Server status unknown - check Terminal window"
fi
echo "=========================================="
echo ""
echo "Browser should open automatically."
echo "If the page doesn't load, check the Terminal window for errors."
echo ""
echo "To stop the server, press Ctrl+C in the Terminal window."
echo ""
read -p "Press Enter to close this window..."

