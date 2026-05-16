#!/usr/bin/env python3
"""Capture the tutorial screenshots from a running narRaters web UI.

The tutorial PDF (`generate_tutorial_pdf.py`) embeds the PNGs in this folder.
Whenever the UI changes, recapture them with one command:

    pip install playwright && playwright install chromium
    narraters serve --no-browser            # in another terminal
    python tutorial_screenshots/capture_screenshots.py

Environment:
    NARRATERS_URL   base URL (default http://localhost:5000)
    SHOT_SUBJECT    subject id for the detail shots (default: first discovered)

Shot list (filenames must match exactly — the generator references them):

    01_pipeline_rater.png  /pipeline-config, empty pipeline. The Rater-name box
                           + dice at the TOP of the middle "Pipeline Flow"
                           panel; greyed-out Continue button.
    03_pipeline_config.png /pipeline-config with 3-4 steps added; palette
                           (left), populated canvas (middle), a step's
                           Input/Output/Method fields visible.
    04_dashboard.png       /  dashboard: one panel, rows = subjects/stories,
                           columns = steps, mixed status cells; Change Rater
                           (top-right) and File Version dropdown visible.
    05_story_detail.png    /story/<name>: tabbed view, Story Events tab.
    06_story_events.png    /story/<name>: events editor + Export Edited File.
    07_subject_detail.png  /subject/<id>: a step tab with input (left) and
                           editable output (right).

Steps that need drag-and-drop or hand-editing are best-effort; the script
prints a clear TODO for any shot it could not fully stage so you can finish
it by hand, then rebuild the PDF with `python generate_tutorial_pdf.py`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = os.environ.get("NARRATERS_URL", "http://localhost:5000").rstrip("/")
OUT = Path(__file__).resolve().parent
VIEWPORT = {"width": 1280, "height": 900}

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "Playwright is required:\n"
        "  pip install playwright && playwright install chromium"
    )


def _save(page, name: str, note: str = "") -> None:
    page.screenshot(path=str(OUT / name), full_page=False)
    print(f"  saved {name}" + (f"  ({note})" if note else ""))


def main() -> int:
    todos: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        # 01 — pipeline config, rater box (empty pipeline)
        page.goto(f"{BASE}/pipeline-config", wait_until="networkidle")
        page.wait_for_timeout(800)
        try:
            page.fill("#rater-name-input", "")
        except Exception:
            pass
        _save(page, "01_pipeline_rater.png", "rater box + dice, Continue greyed")

        # 03 — pipeline config with steps (drag-drop is not reliably scriptable
        # across builds; capture if steps are already present, else TODO).
        if page.locator(".pipeline-step:not(.empty)").count():
            page.fill("#rater-name-input", "DemoRater")
            page.wait_for_timeout(300)
            _save(page, "03_pipeline_config.png", "populated pipeline")
        else:
            todos.append(
                "03_pipeline_config.png: drag 3-4 steps from the palette, set a "
                "rater name, then re-run (or screenshot this page by hand)."
            )

        # 04 — dashboard
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(1500)
        if "/pipeline-config" in page.url:
            todos.append(
                "04_dashboard.png: confirm a pipeline first (no "
                "pipeline_config.json yet), then re-run."
            )
        else:
            _save(page, "04_dashboard.png", "status grid")

        # 07 — subject detail
        subj = os.environ.get("SHOT_SUBJECT", "")
        if not subj:
            try:
                link = page.locator("a[href^='/subject/']").first
                if link.count():
                    subj = link.get_attribute("href").split("/subject/")[-1]
            except Exception:
                subj = ""
        if subj:
            page.goto(f"{BASE}/subject/{subj}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            _save(page, "07_subject_detail.png", f"subject {subj}")
        else:
            todos.append("07_subject_detail.png: no subject discoverable; add recall data and re-run.")

        todos.append(
            "05_story_detail.png + 06_story_events.png: open a /story/<name> "
            "view and its events editor; capture per the shot list above."
        )

        browser.close()

    print("\nDone. Remaining manual shots / TODOs:")
    for t in todos:
        print("  - " + t)
    print("\nThen rebuild the PDF:  python generate_tutorial_pdf.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
