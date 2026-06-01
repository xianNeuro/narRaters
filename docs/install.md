<p align="center">
  <a href="../README.md">README</a> &nbsp;·&nbsp;
  <strong>Install</strong> &nbsp;·&nbsp;
  <a href="input-data.md">Input data</a> &nbsp;·&nbsp;
  <a href="web-interface.md">Web interface</a> &nbsp;·&nbsp;
  <a href="troubleshooting.md">Troubleshooting</a> &nbsp;·&nbsp;
  <a href="command-line.md">Command-line</a> &nbsp;·&nbsp;
  <a href="../LICENSE">License</a>
</p>

---

## Quick start

### Double-click launcher (ZIP download)

1. **[Download the ZIP (v0.3.8)](https://github.com/xianNeuro/narRaters/archive/refs/tags/v0.3.8.zip)** — latest release snapshot — and unzip it. (Or use green **Code ▾** → **Download ZIP** on GitHub for the current `main` branch.)
2. **Open the launcher:** **macOS** — double-click **`narRater.app`**. **Windows** — double-click **`narRaters_installer.bat`**. **Linux** — in Terminal, `cd` into the folder and run `bash install.sh`.
   - **macOS** if Gatekeeper blocks you:
     - Try **Finder** → **control-click** **`narRater.app`** → **Open** → **Open** in the warning dialog (when those choices exist).
     - If there is **no Open** entry or launching still fails: **System Settings** → **Privacy & Security** → scroll to **Security**. After macOS rejects the app once, look for **`narRater` was blocked…** (wording varies) and click **Allow Anyway** or **Open Anyway**, authenticate, then open **`narRater.app`** again (that control may disappear after ~an hour — try launching once more to refresh it).
     - More (including stripping quarantine from a downloaded ZIP): [Installation](#installation) and [Troubleshooting](troubleshooting.md).
3. **A browser tab opens at `http://127.0.0.1:5000`** with bundled examples already loaded — start clicking.

### Via terminal (PyPI)

1. **Check Python** — you need **3.10 or newer**:

```bash
python --version
```

If that fails or shows an older version, try `python3 --version` or install [Python 3.10+](https://www.python.org/downloads/).

2. **Install or upgrade** from PyPI and confirm it finishes without errors:

```bash
python3 -m pip install narraters --upgrade
```

You can verify with `narraters --version`.

3. **Start the web UI** — your browser should open to the pipeline builder:

```bash
narraters serve
```

> Needs **[Python 3.10+](https://www.python.org/downloads/)**. If anything fails, see [Troubleshooting](troubleshooting.md) or the full [Installation](#installation) walkthrough below.

---

## Installation

**Step 1 — Install [Python 3.10 or newer](https://www.python.org/downloads/).**  Windows: check **“Add python.exe to PATH”** in the Python installer.

**Step 2 — Download the project.** Use the **[release ZIP (v0.3.8)](https://github.com/xianNeuro/narRaters/archive/refs/tags/v0.3.8.zip)** link in [Quick start](#quick-start), or on the [GitHub repo page](https://github.com/xianNeuro/narRaters) click the green **Code ▾** button → **Download ZIP**, then unzip wherever you like (e.g. `~/Downloads/`, your desktop, `~/Documents/`). You'll get a folder called **`narRaters-0.3.8`** (release ZIP), **`narRaters-main`** (default GitHub ZIP), or **`narRaters`** if you used `git clone`. Everything below assumes you're inside that folder.

**Step 3 — Launch the app by double-clicking the right file for your OS.**

| Your OS | Double-click… | What happens |
|---------|---------------|--------------|
| **macOS** | **`narRater.app`** | Sets up a Python virtual environment, installs dependencies, opens your browser |
| **Windows** | **`narRaters_installer.bat`** | Same flow, in a Command Prompt window |
| **Linux** | open Terminal in the folder, run `bash install.sh` | Same flow (Linux has no double-click convention here) |

**Step 4 — Done.** Your browser opens **`http://127.0.0.1:5000/pipeline-config`**. Put your data in **`data/`** inside the project folder (bundled examples are already there). Restart later by double-clicking the same file.

Install problems? See **[Troubleshooting](troubleshooting.md)**.

### Alternate install (command line)

For users who prefer the terminal, or who want to install the app without keeping the project folder around. Two flavors — pick whichever you prefer.

<details>
<summary><b>(a) <code>git clone</code> + <code>install.sh</code> (gets you the project folder, with bundled examples)</b></summary>

```bash
# macOS / Linux
cd ~ && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && bash install.sh
```

```bat
:: Windows
cd %USERPROFILE% && git clone https://github.com/xianNeuro/narRaters.git && cd narRaters && narRaters_installer.bat
```

This is what `narRater.app` does under the hood, just without the click. `git: command not found`? On macOS: `xcode-select --install`. On Windows: install [Git for Windows](https://git-scm.com/download/win).
</details>

<details>
<summary><b>(b) PyPI (bundled examples — copied into your current folder on first <code>narraters serve</code>)</b></summary>

Use this if you already have a working Python venv and just want the **`narraters`** command. On first launch, example **`data/`** and **`output/`** folders are copied into whatever directory you run from (unless you already have a project folder, or set **`NARRATERS_PROJECT_ROOT`**).

Always use **`python3 -m pip`**, not bare `pip` — on macOS, `pip` often points at an old Python and will say *“no matching distribution”*.

```bash
python3 --version        # must be 3.10 or newer
mkdir -p ~/narRaters-demo && cd ~/narRaters-demo
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
python3 -m pip install --upgrade pip
python3 -m pip install narraters --upgrade
narraters serve
```

Package: [`narraters`](https://pypi.org/project/narraters/) (all lowercase). For the full project folder (launchers, tutorial PDF, etc.), use the ZIP or git clone install above.
</details>

<details>
<summary><b>Optional extras (Whisper, cloud APIs, local Gemma, etc.)</b></summary>

Inside the project folder, with the venv activated:

```bash
python3 -m pip install -e ".[audio]"     # Whisper transcription
python3 -m pip install -e ".[api]"       # Anthropic / OpenAI
python3 -m pip install -e ".[nlp]"       # spaCy segmentation
python3 -m pip install -e ".[grammar]"   # grammar checker
python3 -m pip install -e ".[local-llm]" # local Gemma
python3 -m pip install -e ".[match]"     # rmatch
python3 -m pip install -e ".[all]"       # api + match
```

PyPI users: `python3 -m pip install "narraters[audio]"`, etc.

Heavy methods (`audio`, `local-llm`, `match`) pull multi-GB packages — the app shows a RAM/disk preflight before downloading. **Ollama (local Gemma):** install [Ollama](https://ollama.com), then `ollama pull gemma4:e4b`. **API keys:** copy `.env.example` to `.env` and edit (see [`SETUP_API.md`](../SETUP_API.md)).
</details>

<details>
<summary><b>Developers</b></summary>

`install.sh` already does an editable install. To work on the codebase:

```bash
git clone https://github.com/xianNeuro/narRaters.git
cd narRaters
python3 -m venv .venv && source .venv/bin/activate && python3 -m pip install -e .
```

Build the standalone macOS app for icon testing: `bash packaging/macos/build_app_bundle.sh`.  Build the slim repo-root launcher: `bash packaging/macos/build_repo_app.sh`.
</details>
