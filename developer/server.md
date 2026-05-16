# Web Viewer Server

Documentation for the `server/` folder (Flask app). This page lives under **`developer/`**; the runnable files remain in **`server/`**.

## Quick Start

**Double-click `narRater.app`** (shipped at the project root) to launch the web interface. Alternatives: double-click `START_HERE.command`, or `narraters serve` from the terminal. If you want to rebuild the `.app` after editing the launcher or icon, run `bash packaging/macos/build_app_bundle.sh` from the project root — the resulting bundle resolves `PROJECT_ROOT` and the Python interpreter at runtime, so it works on any Mac without further edits.

This will:
- Start the Flask web server
- Open your browser automatically to the web interface

## Files

- **`START_HERE.command`** - Main launcher (double-click to start)
- **`web-interface.py`** - Flask web server application

## Usage

1. **Start the server:**
   - Double-click `START_HERE.command` (recommended)
   - Or run: `python3 server/web-interface.py`

2. **Access the interface:**
   - Browser opens automatically to: http://localhost:5000/pipeline-config
   - If pipeline is configured, goes to: http://localhost:5000

3. **Stop the server:**
   - Press `Ctrl+C` in the Terminal window

## Troubleshooting

**Server won't start:**
- Check Python version: `python3 --version` (should be 3.7+)
- Install dependencies: `pip install -r ../requirements.txt`
- Check Terminal for error messages

**Port 5000 already in use:**
- Close other applications using port 5000
- Or modify the port in `web-interface.py` (last line)

**Browser shows "Not Found":**
- Wait a few seconds for the server to fully start
- Manually navigate to: http://localhost:5000/pipeline-config
