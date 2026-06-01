<p align="center">
  <a href="../README.md">README</a> &nbsp;·&nbsp;
  <a href="install.md">Install</a> &nbsp;·&nbsp;
  <a href="input-data.md">Input data</a> &nbsp;·&nbsp;
  <strong>Web interface</strong> &nbsp;·&nbsp;
  <a href="troubleshooting.md">Troubleshooting</a> &nbsp;·&nbsp;
  <a href="command-line.md">Command-line</a> &nbsp;·&nbsp;
  <a href="../LICENSE">License</a>
</p>

---

## Using the web interface

The app is a **local Flask site** at **`http://127.0.0.1:5000`**. After the initial install, restart it any time by:

| How | Where |
|-----|-------|
| Double-click **`narRater.app`** | macOS, repo root |
| Double-click **`narRaters_installer.bat`** | Windows, repo root |
| `narraters serve` in Terminal | any OS — opens your browser automatically |

On first visit you see **pipeline configuration**; if a pipeline was already saved, you land on the **dashboard**.

### `narraters serve` options

| Flag | Default | Purpose |
|---|---|---|
| `--port` | `5000` | Another port if `5000` is busy |
| `--host` | `127.0.0.1` | Bind address; use `0.0.0.0` only on a **trusted** network (the UI runs subprocesses on your machine) |
| `--no-browser` | off | Do not open a browser tab (SSH, headless) |
| `--debug` | off | Flask debug / auto-reload while hacking on the server |

```bash
narraters serve --port 8080 --no-browser
```

### Navigating the three main screens

Use this table as a mental map; URLs are for bookmarking or support.

| Screen | Route | What you do there |
|--------|--------|-------------------|
| **Pipeline setup** | `/pipeline-config` | Drag steps from **Available Steps** into **Pipeline Flow**, set per-step **folders**, enter a **rater name** (or 🎲). **Continue** unlocks only when there is a **name** and **at least one step**; it saves config and opens the dashboard. |
| **Dashboard** | `/` | Grid: **rows** = subjects or stories, **columns** = steps. **Click a cell** to run that step for that row (pick **method / model / prompt / variant** if the step offers them). **Batch** actions run one step across all rows. **Change rater** returns to setup. |
| **Detail view** | `/subject/…` or `/story/…` | **Tabs** per pipeline step for **one** row. Read outputs, use the **version** dropdown to compare the latest automated file vs your **`{id}_{ratername}-edit`** saves, **edit**, **save**. Use **`-edit`** files for downstream analysis. |

**Flow:** setup → dashboard (bulk status + runs) → open a row when you need to **inspect, hand-correct, or compare versions**. You can return to setup anytime to add steps or change paths.

### Heavy local models

Before a step that would load **Whisper**, **Gemma via Ollama**, **rMatch** embeddings, or **local Transformers**, the app runs a **RAM / disk / model** preflight. If the run is likely unsafe for your machine, a **popup** explains why and can **switch you to a lighter method** (for example `rules`, `test`, `clause`). The check does **not** download or start a model just to decide, so it should not wedge the system. Capable machines with models already installed often see no popup.
