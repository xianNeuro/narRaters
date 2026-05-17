#!/usr/bin/env python3
"""Capture PNG screenshots from a running narRaters web UI for the tutorial PDF.

Prerequisites::
    pip install playwright && playwright install chromium

Run (two terminals)::


    narraters serve --no-browser              # localhost
    python developer/capture_tutorial_screenshots.py

Alternatively use 127.0.0.1 (recommended on macOS)::

    narraters serve --no-browser --host 127.0.0.1
    NARRATERS_URL=http://127.0.0.1:5000 python developer/capture_tutorial_screenshots.py

Outputs ``tutorial_screenshots/*.png`` at the repo root, then regenerate the PDF::

    python developer/generate_tutorial_pdf.py

Palette ``data-step`` values must stay in sync with ``templates/pipeline-config.html``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tutorial_screenshots"
BASE = os.environ.get("NARRATERS_URL", "http://127.0.0.1:5000").rstrip("/")
VIEWPORT = {"width": 1280, "height": 900}

STORY_PRIMARY = os.environ.get("SHOT_STORY", "the_siren").strip()
STORY_AUDIO_SAMPLE = os.environ.get("SHOT_STORY_AUDIO_STORY", "pieman_edited").strip()
SUBJECT_ID = os.environ.get("SHOT_SUBJECT", "the_siren_sub-01").strip()

# Matches ``templates/pipeline-config.html`` palette ``data-step`` strings.
PALETTE_PIPELINE_ORDER = (
    "eventSegment",
    "causalRating",
    "audioTranscribe:recall",
    "sentenceCorrect",
    "textParsing",
    "textMatching",
)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit(
        "Playwright is required:\n"
        "  pip install playwright && playwright install chromium"
    )


def _save(page, name: str, note: str = "") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / name
    page.screenshot(path=str(dest), full_page=False)
    print(f"  saved {name}" + (f"  ({note})" if note else ""))


def _dismiss_overlays(page) -> None:
    # Pipeline-config tutorial balloon
    for sel in (
        "#tutorial-notification .tutorial-close",
        ".tutorial-close",
    ):
        btn = page.locator(sel).first
        if btn.count() and btn.is_visible():
            btn.click(timeout=2000)
            page.wait_for_timeout(200)

    # Subject / story onboarding banners — best-effort
    for sel in (
        ".story-events-notification-close",
        "#story-events-notification .story-events-notification-close",
    ):
        while True:
            close = page.locator(sel).first
            try:
                if close.count() and close.is_visible():
                    close.click(timeout=800)
                    page.wait_for_timeout(150)
                    continue
            except Exception:
                pass
            break


def _add_pipeline_steps_placeholder(page, todos: list[str]) -> None:
    confirm = page.locator("#confirm-btn")
    prev = ""
    added = False
    for step in PALETTE_PIPELINE_ORDER:
        locator = page.locator(f'.palette-step[data-step="{step}"] button.palette-step-add')
        try:
            if locator.count():
                locator.first.click(timeout=5000)
                page.wait_for_timeout(320)
                added = True
            else:
                todos.append(f"Palette entry missing for {step!r} — check pipeline-config HTML.")
                return
        except Exception:
            todos.append(f"Could not click +Add for palette step {step!r}")
            return
    if not added:
        return
    # Wait until Continue enables (requires rater + >=1 step)
    try:
        page.wait_for_timeout(250)
        if confirm.is_visible() and confirm.get_attribute("disabled") is None:
            return
    except Exception:
        pass
    new = ""
    for _ in range(40):  # up to ~4s
        new = confirm.get_attribute("disabled") or ""
        if new != prev:
            prev = new
            if new is None:
                break
        page.wait_for_timeout(100)
    todos.append(
        "Continue stayed disabled after palette adds — manually add one step and rerun."
    )


def _click_named_tab(page, label: str) -> None:
    page.get_by_role("button", name=label, exact=True).click(timeout=8000)
    page.wait_for_timeout(400)


def _capture_subject_tabs(page, todos: list[str]) -> None:
    """Save 07_subject_detail + per-tab screenshots on the recall subject inspection page."""
    url = f"{BASE}/subject/{SUBJECT_ID}"
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(1500)
    if "/pipeline-config" in page.url:
        todos.append(
            "Subject inspection: bounced to pipeline-config — save a pipeline and re-run capture."
        )
        return

    tabs = page.locator("div.tabs button.tab")
    n = tabs.count()
    if n == 0:
        todos.append("No inspection tabs rendered on subject — check pipeline JSON and data.")
        return

    _dismiss_overlays(page)
    page.wait_for_timeout(300)

    # Default landing tab covers the dashboard click-through UX
    try:
        _save(page, "07_subject_detail.png", "subject landing tab")
    except Exception as exc:
        todos.append(f"07_subject_detail.png: {exc}")

    spec = [
        ("Audio Transcription", "08_subject_recall_audio_tab.png"),
        ("Corrected Recall", "09_subject_corrected_recall_tab.png"),
        ("Parsed Recall", "10_subject_parsed_recall_tab.png"),
        ("Recall Matching", "11_subject_recall_matching_tab.png"),
        ("Story Segments", "12_subject_story_segments_reference_tab.png"),
    ]
    for label, fname in spec:
        try:
            if page.get_by_role("button", name=label, exact=True).count():
                _click_named_tab(page, label)
                _dismiss_overlays(page)
                page.wait_for_timeout(400)
                _save(page, fname, label)
        except Exception as exc:
            todos.append(f"{fname} ({label}): {exc}")


def main() -> int:
    todos: list[str] = []
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
        page = ctx.new_page()

        # ---- 01: empty pipeline ------------------------------------------------
        page.goto(f"{BASE}/pipeline-config", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        reset = page.locator("button.btn-secondary", has_text="Reset")
        if reset.count():
            reset.first.click()
            page.wait_for_timeout(500)
        _dismiss_overlays(page)
        try:
            page.fill("#rater-name-input", "")
        except Exception:
            pass
        page.wait_for_timeout(350)
        _save(page, "01_pipeline_rater.png", "rater + dice, Continue disabled")

        # ---- 03: populated pipeline ------------------------------------------
        _dismiss_overlays(page)
        page.fill("#rater-name-input", "TutorialScreenshots")
        page.wait_for_timeout(200)

        prev_disabled = None
        for step in PALETTE_PIPELINE_ORDER:
            loc = page.locator(f'.palette-step[data-step="{step}"] button.palette-step-add')
            try:
                if loc.count():
                    loc.first.click()
                    page.wait_for_timeout(300)
                    prev_disabled = page.locator("#confirm-btn").get_attribute("disabled")
            except Exception as exc:
                todos.append(f"Could not auto-add palette step {step}: {exc}")
                break

        confirm = page.locator("#confirm-btn")
        disabled = confirm.get_attribute("disabled")
        if disabled is None:
            _save(page, "03_pipeline_config.png", "populated Pipeline Flow")
        else:
            todos.append(
                "03_pipeline_config.png: Continue stayed disabled — add steps manually "
                "(drag palette or fix JS), then rerun capture."
            )

        # Navigate to dashboard (Confirm may or may not trigger a full navigation depending on Flask build)
        if confirm.get_attribute("disabled") is None:
            try:
                confirm.click(timeout=8000)
            except Exception:
                todos.append("Could not click Continue -- save pipeline manually.")
            page.wait_for_timeout(2500)

        if "/pipeline-config" in page.url:
            page.goto(f"{BASE}/", wait_until="domcontentloaded")

        page.wait_for_timeout(1500)

        # ---- 04: dashboard ----------------------------------------------------
        if "/pipeline-config" in page.url:
            todos.append("04_dashboard.png: still on pipeline-config — click Continue.")
        else:
            _save(page, "04_dashboard.png", "status grid")

        # ---- Story screenshots -------------------------------------------------
        page.goto(f"{BASE}/story/{STORY_PRIMARY}", wait_until="networkidle")
        page.wait_for_timeout(1200)
        _dismiss_overlays(page)
        _save(page, "05_story_detail.png", f"story {STORY_PRIMARY} default tabs")

        page.goto(f"{BASE}/story/{STORY_PRIMARY}/step0", wait_until="networkidle")
        page.wait_for_timeout(1000)
        _dismiss_overlays(page)
        _save(page, "06_story_events.png", f"deep-link story segmentation / {STORY_PRIMARY}/step0")

        page.goto(f"{BASE}/story/{STORY_PRIMARY}/step0_causal", wait_until="networkidle")
        page.wait_for_timeout(1200)
        _dismiss_overlays(page)
        _save(page, "14_story_causal_rating_tab.png", "causal rating matrix")

        page.goto(f"{BASE}/story/{STORY_AUDIO_SAMPLE}/step0_story_audio", wait_until="networkidle")
        page.wait_for_timeout(1200)
        _dismiss_overlays(page)
        _save(page, "13_story_audio_transcription_tab.png", f"{STORY_AUDIO_SAMPLE} audio tab")

        # ---- Subject tabs -----------------------------------------------------
        _capture_subject_tabs(page, todos)

        browser.close()

    print("\nTutorial screenshot capture finished.")
    if todos:
        print("\nOutstanding notes (some shots may still be usable):")
        for t in todos:
            print(f"  - {t}")

    missing = sorted(
        p.name for p in OUT.glob("*.png") if p.stat().st_size < 2048  # accidental blank
    )
    if missing:
        print("\nTiny PNGs (might be failures):", ", ".join(missing))

    print("\nRebuild the PDF:")
    print("  python developer/generate_tutorial_pdf.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
