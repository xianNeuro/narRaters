#!/bin/bash

# Diagnostic script to test server startup

cd "$(dirname "$0")"
SERVER_DIR="$(pwd)"
PROJECT_ROOT="$(cd .. && pwd)"

echo "=========================================="
echo "Server Diagnostic Test"
echo "=========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo "Server dir: $SERVER_DIR"
echo ""

# Check Python
echo "1. Checking Python..."
if command -v python3 &> /dev/null; then
    echo "   ✓ Python found: $(python3 --version)"
else
    echo "   ✗ Python 3 not found!"
    exit 1
fi

# Check Flask
echo ""
echo "2. Checking Flask..."
if python3 -c "import flask" 2>/dev/null; then
    FLASK_VERSION=$(python3 -c "import flask; print(flask.__version__)" 2>/dev/null || echo "unknown")
    echo "   ✓ Flask installed: $FLASK_VERSION"
else
    echo "   ✗ Flask not installed!"
    echo "   Run: pip install -r $PROJECT_ROOT/requirements.txt"
    exit 1
fi

# Check other dependencies
echo ""
echo "3. Checking other dependencies..."
for module in pandas openpyxl; do
    if python3 -c "import $module" 2>/dev/null; then
        echo "   ✓ $module installed"
    else
        echo "   ✗ $module not installed"
    fi
done

# Check port 5000
echo ""
echo "4. Checking port 5000..."
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "   ⚠ Port 5000 is in use"
    echo "   Process: $(lsof -Pi :5000 -sTCP:LISTEN | tail -1)"
else
    echo "   ✓ Port 5000 is available"
fi

# Check if web-interface.py exists
echo ""
echo "5. Checking server file..."
if [ -f "$SERVER_DIR/web-interface.py" ]; then
    echo "   ✓ web-interface.py found"
else
    echo "   ✗ web-interface.py not found!"
    exit 1
fi

# Test if the file can be parsed (syntax check)
echo ""
echo "6. Testing server file syntax..."
cd "$SERVER_DIR"
if python3 -m py_compile web-interface.py 2>&1; then
    echo "   ✓ File syntax is valid"
else
    echo "   ✗ File has syntax errors!"
    exit 1
fi

# Try to start server briefly
echo ""
echo "7. Testing server startup (5 second test)..."
cd "$SERVER_DIR"
python3 web-interface.py &
SERVER_PID=$!
sleep 5

if kill -0 $SERVER_PID 2>/dev/null; then
    echo "   ✓ Server started successfully (PID: $SERVER_PID)"
    
    # Test if it responds
    if curl -s http://localhost:5000 > /dev/null 2>&1; then
        echo "   ✓ Server is responding to requests"
    else
        echo "   ⚠ Server is running but not responding"
    fi
    
    # Kill the test server
    kill $SERVER_PID 2>/dev/null
    wait $SERVER_PID 2>/dev/null
    echo "   ✓ Test server stopped"
else
    echo "   ✗ Server failed to start"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ All checks passed! Server should work."
echo "=========================================="
echo ""
echo "To start the server, run:"
echo "  cd $SERVER_DIR"
echo "  python3 web-interface.py"
echo ""
echo "Or double-click START_HERE.command"
echo ""

