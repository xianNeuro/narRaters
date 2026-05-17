#!/usr/bin/env python3
"""Generate the narRater tutorial PDF with TOC and screenshots."""

import inspect
import os
import re
import sys
from pathlib import Path
from fpdf import FPDF

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
from helpers.anthropic_ids import ANTHROPIC_SUPPORTED_MODELS, anthropic_model_slug

SCREENSHOT_DIR = str(_repo_root / "tutorial_screenshots")
OUTPUT_FILE = str(_repo_root / "narRater_Tutorial.pdf")


def _sanitize(text):
    """Replace Unicode characters unsupported by built-in PDF fonts."""
    return (text
            .replace('\u2014', '--')   # em-dash
            .replace('\u2013', '-')    # en-dash
            .replace('\u2018', "'")    # left single quote
            .replace('\u2019', "'")    # right single quote
            .replace('\u201c', '"')    # left double quote
            .replace('\u201d', '"')    # right double quote
            .replace('\u2026', '...')  # ellipsis
            .replace('\u2022', '-')    # bullet
            .replace('\u2192', '->')   # arrow
            .replace('\u2264', '<=')   # less-than-or-equal
            .replace('\u2265', '>=')   # greater-than-or-equal
            )


def _expected_toc_entry_count():
    """Count chapter_title() calls in build_pdf (keeps TOC reservation in sync)."""
    src = inspect.getsource(build_pdf)
    return len(re.findall(r"\.chapter_title\(", src))


def _toc_page_count(num_entries):
    """Blank pages to reserve after the cover for the table of contents."""
    lines_per_page = 32
    header_lines = 5
    return max(2, (num_entries + header_lines + lines_per_page - 1) // lines_per_page)


class TutorialPDF(FPDF):
    """Custom PDF with header/footer, TOC support, and internal links."""

    def __init__(self):
        super().__init__()
        self.toc_entries = []
        self._section_links = {}

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "narRater -- User Tutorial", align="C")
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def add_toc_entry(self, title, level=0):
        self.toc_entries.append((title, self.page_no(), level))

    def chapter_title(self, num, title, level=0):
        display = _sanitize(f"{num}  {title}" if num else title)
        self.add_toc_entry(display, level)
        link = self.add_link()
        self.set_link(link, y=self.get_y(), page=self.page_no())
        self._section_links[display] = link
        if level == 0:
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(30, 60, 120)
        else:
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(50, 80, 140)
        self.cell(0, 12, display, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        return link

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, _sanitize(text))
        self.ln(2)

    def bullet(self, text, indent=10):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        x = self.get_x()
        self.set_x(x + indent)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, _sanitize(text))
        self.ln(1)

    def bold_text(self, label, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 30, 30)
        self.cell(self.get_string_width(_sanitize(label)) + 2, 5.5, _sanitize(label))
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, _sanitize(text))
        self.ln(1)

    def code_block(self, lines):
        """Render a monospaced code block."""
        self.set_font("Courier", "", 9)
        self.set_text_color(40, 40, 40)
        self.set_fill_color(245, 245, 245)
        for line in lines:
            self.cell(0, 4.5, "  " + _sanitize(line), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)

    def methods_table(self, rows, col_widths=(35, 95, 50)):
        """Render a compact 3-column reference table: Method | Description | Args / Keys.

        rows: list of (method_label, description, args_or_keys) tuples.
        Wraps multi-line descriptions so the right column never overflows the page.
        """
        headers = ("Method", "What it does", "Args / Keys")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(255, 255, 255)
        self.set_fill_color(60, 90, 150)
        for h, w in zip(headers, col_widths):
            self.cell(w, 6, _sanitize(h), border=0, fill=True, align="L")
        self.ln(6)
        self.set_text_color(30, 30, 30)
        fill_toggle = False
        for method, desc, args in rows:
            self.set_font("Helvetica", "B", 9)
            x_start = self.get_x()
            y_start = self.get_y()
            fill = (240, 245, 252) if fill_toggle else (255, 255, 255)
            self.set_fill_color(*fill)
            # Method cell
            self.multi_cell(col_widths[0], 4.5, _sanitize(method), border=0, fill=True)
            y_after_m = self.get_y()
            # Description cell
            self.set_xy(x_start + col_widths[0], y_start)
            self.set_font("Helvetica", "", 9)
            self.multi_cell(col_widths[1], 4.5, _sanitize(desc), border=0, fill=True)
            y_after_d = self.get_y()
            # Args cell
            self.set_xy(x_start + col_widths[0] + col_widths[1], y_start)
            self.set_font("Courier", "", 8)
            self.multi_cell(col_widths[2], 4.5, _sanitize(args), border=0, fill=True)
            y_after_a = self.get_y()
            # Pad shorter cells to the longest row height with empty fill
            row_bottom = max(y_after_m, y_after_d, y_after_a)
            self.set_y(row_bottom)
            self.set_x(x_start)
            fill_toggle = not fill_toggle
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.ln(2)

    def example_box(self, title, content_lines):
        """Render a highlighted example data box."""
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(30, 90, 30)
        self.set_fill_color(240, 248, 240)
        self.cell(0, 5.5, _sanitize(f"  Example: {title}"), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.set_font("Courier", "", 8)
        self.set_text_color(30, 30, 30)
        for line in content_lines:
            self.cell(0, 4, "  " + _sanitize(line), new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(3)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)

    def add_screenshot(self, filename, caption="", width=170):
        path = os.path.join(SCREENSHOT_DIR, filename)
        if not os.path.exists(path):
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(180, 0, 0)
            self.cell(0, 6, f"[Screenshot not found: {filename}]", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
            return
        if self.get_y() + 80 > self.h - 30:
            self.add_page()
        x = (self.w - width) / 2
        self.image(path, x=x, w=width)
        if caption:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, caption, new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def render_toc(self, toc_page_number, num_pages):
        """Render TOC with clickable hyperlinks to each section."""
        last_toc_page = toc_page_number + num_pages - 1
        self.page = toc_page_number
        self.set_y(40)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(30, 60, 120)
        self.cell(0, 12, "Table of Contents", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(6)
        for title, page_num, level in self.toc_entries:
            if self.get_y() + 7 > self.h - 22 and self.page_no() < last_toc_page:
                self.add_page()
                self.set_y(28)
            indent = level * 8
            self.set_x(20 + indent)
            if level == 0:
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(30, 60, 120)
            else:
                self.set_font("Helvetica", "", 10)
                self.set_text_color(60, 60, 60)
            title_w = self.get_string_width(title)
            page_str = str(page_num)
            page_w = self.get_string_width(page_str)
            avail = self.w - self.get_x() - 20

            link = self._section_links.get(title)
            self.cell(title_w + 2, 6, title, link=link if link else "")

            dots_w = avail - title_w - page_w - 4
            self.set_font("Helvetica", "", 8)
            self.set_text_color(160, 160, 160)
            self.cell(max(dots_w, 2), 6, "", align="R")

            if level == 0:
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(30, 60, 120)
            else:
                self.set_font("Helvetica", "", 10)
                self.set_text_color(60, 60, 60)
            self.cell(page_w + 2, 6, page_str, new_x="LMARGIN", new_y="NEXT", align="R",
                      link=link if link else "")
            self.ln(0.5)


def build_pdf():
    pdf = TutorialPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(30, 60, 120)
    pdf.cell(0, 14, "narRater", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "User Tutorial", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, "A step-by-step guide to the narrative recall processing pipeline",
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 7, "Covering setup, operation, input/output formats, and all processing methods",
             new_x="LMARGIN", new_y="NEXT", align="C")

    # =========================================================================
    # TOC PLACEHOLDER (will be rendered at end)
    # =========================================================================
    toc_page = pdf.page_no() + 1
    toc_pages = _toc_page_count(_expected_toc_entry_count())
    for _ in range(toc_pages):
        pdf.add_page()

    # =========================================================================
    # 1. OVERVIEW
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("1", "Overview")
    pdf.ln(4)
    pdf.body_text(
        "narRater is a multi-step pipeline for processing narrative recall data. "
        "It transforms raw recall text (or audio) into corrected, segmented, and scored formats "
        "suitable for research analysis. The pipeline preserves the original narrative structure, "
        "meaning, and style while fixing errors, organising content, and matching recall segments "
        "to story events."
    )
    pdf.body_text(
        "The software provides both a web-based graphical interface (recommended) and command-line "
        "scripts. Every automated step also has a Manual mode for human editing."
    )
    pdf.body_text("The pipeline consists of six main steps:")
    pdf.bullet("Step 1 -- Audio Transcription: convert audio recordings to text "
               "(narraters transcribe)")
    pdf.bullet("Step 2 -- Story Event Segmentation: split the story transcript into "
               "numbered events (narraters segment)")
    pdf.bullet("Step 3 -- Spell & Grammar Correction: fix errors in subject recall "
               "text, no rewriting (narraters correct)")
    pdf.bullet("Step 4 -- Recall Parsing: split corrected recall into clause-level "
               "segments (narraters parse)")
    pdf.bullet("Step 5 -- Recall Rating: match each recall segment to story events "
               "(narraters match)")
    pdf.bullet("Step 6 -- Causal Rating: rate the causal strength of every "
               "story-event pair (narraters rate)")

    pdf.ln(2)
    pdf.body_text(
        "Each step can be run in Automatic mode (using rule-based algorithms or LLM API calls) "
        "or Manual mode (human editing through the web interface). The web interface shows input "
        "on the left and editable output on the right, side by side."
    )
    pdf.body_text(
        "Every step is also available from the terminal via the 'narraters' command "
        "installed with the package -- e.g. 'narraters segment', 'narraters match'. "
        "Each step chapter below ends with a 'Terminal Command' section showing the "
        "exact invocation and options; 'narraters <step> --help' lists them at any time. "
        "Steps 1-2 work on the story, steps 3-5 on each subject's recall, and step 6 on "
        "the story-event list; a text-only project can skip Step 1."
    )

    # =========================================================================
    # 2. GETTING STARTED
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("2", "Getting Started")

    pdf.chapter_title("2.1", "Prerequisites", level=1)
    pdf.body_text("Before running the software, ensure you have:")
    pdf.bullet("Python 3.10 or later installed")
    pdf.bullet("Install the package: pip install -e .  (or pip install -r requirements.txt)")
    pdf.body_text(
        "The default install is deliberately minimal: it is enough to run the lightweight "
        "default method of every step plus the web UI, and pulls no multi-GB ML frameworks, "
        "so it installs fast and will not fill up your disk. Heavier methods are opt-in extras:"
    )
    pdf.bullet("[api] -- Anthropic / OpenAI clients for LLM-based methods (Steps 5, 6)")
    pdf.bullet("[audio] -- Whisper / WhisperX for Step 1 audio transcription (pulls torch)")
    pdf.bullet("[nlp] -- spaCy + benepar for higher-accuracy Step 2 fine/coarse segmentation")
    pdf.bullet("[match] -- the rmatch embedding backend for Step 5 (pulls torch)")
    pdf.bullet("[local-llm] -- transformers + torch for local Gemma via HuggingFace")
    pdf.body_text("Example: pip install -e \".[api]\"   |   no account or password is ever required.")

    pdf.chapter_title("2.2", "Setting Up API Keys", level=1)
    pdf.body_text(
        "Several steps can use LLM models via API for higher-quality results. "
        "The software supports both Anthropic and OpenAI (GPT) models. "
        "To set up an API key:"
    )
    pdf.bullet("Anthropic: export ANTHROPIC_API_KEY='your-key-here'")
    pdf.bullet("OpenAI: export OPENAI_API_KEY='your-key-here'")
    pdf.bullet("Or run the setup script: bash scripts/setup_api_key.sh")
    pdf.body_text(
        "API keys are read from environment variables and are never stored in code files. "
        "You can also enter the API key through the web interface's Pipeline Configuration page."
    )

    pdf.chapter_title("2.3", "Starting the Web Interface", level=1)
    pdf.body_text(
        "The recommended way to use the software is through its web interface. "
        "To start the server, use any one of:"
    )
    pdf.bullet("Terminal: narraters serve   (auto-opens the browser)")
    pdf.bullet("macOS: double-click narRater.app")
    pdf.bullet("macOS: double-click server/START_HERE.command")
    pdf.body_text(
        "The browser opens automatically to http://localhost:5000. If a pipeline is not yet "
        "configured you land on the Pipeline Configuration page; otherwise on the Dashboard."
    )

    pdf.chapter_title("2.4", "Rater Name (no login)", level=1)
    pdf.body_text(
        "There is no login, account, or password. Instead, on the Pipeline Configuration page "
        "you enter a Rater name in the box at the top of the Pipeline Flow panel (the middle "
        "panel). This name is used only to label any output files you save by hand, e.g. "
        "the_siren_sub-01_BraveOtter-edit.xlsx -- a made-up / dummy name is perfectly fine. "
        "Click the dice button to fill in a random adjective+noun name."
    )
    pdf.add_screenshot(
        "01_pipeline_rater.png",
        "Figure 1: Pipeline Configuration -- the Rater name box (with the dice button) sits at "
        "the top of the Pipeline Flow panel in the middle. The Continue button stays greyed "
        "out until a rater name is entered AND at least one step has been added.")

    # =========================================================================
    # 3. PIPELINE CONFIGURATION
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("3", "Pipeline Configuration")
    pdf.body_text(
        "When the app starts, you are taken to the Pipeline Configuration page. "
        "Here you define which processing steps to run and in what order."
    )
    pdf.add_screenshot("03_pipeline_config.png",
                       "Figure 2: Pipeline configuration builder -- drag steps from the 'Available Steps' "
                       "palette on the left into the 'Pipeline Flow' canvas in the middle. The Rater name "
                       "box and dice sit at the top of that middle panel.")
    pdf.body_text(
        "The left panel ('Available Steps') is the palette. Drag steps into the 'Pipeline Flow' "
        "canvas in the middle to build your workflow. Each step has configurable input and "
        "output paths that determine where it reads data from and writes results to."
    )
    pdf.body_text("Configurable options for each step:")
    pdf.bullet("Input Path: the directory from which the step reads input files")
    pdf.bullet("Output Path: the directory where the step writes output files")
    pdf.bullet("Method: the processing method (automatic algorithm, API call, or Manual)")
    pdf.body_text(
        "At the top of the Pipeline Flow panel, enter a Rater name (or click the dice for a "
        "random one). The 'Continue' button is greyed out and not clickable until BOTH a rater "
        "name is entered AND at least one step has been added. Clicking 'Continue' saves the "
        "configuration to pipeline_config.json and opens the main dashboard; you can return to "
        "this page anytime via the 'Change Rater' button on the dashboard."
    )

    # =========================================================================
    # 4. MAIN DASHBOARD
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("4", "Main Dashboard")
    pdf.body_text(
        "The dashboard shows all subjects and stories detected from your data directories, "
        "grouped into one panel per pipeline chain. Each row is a subject/story and each "
        "column is a pipeline step; every cell shows that step's status for that item. "
        "Click an item to open its detail view."
    )
    pdf.add_screenshot("04_dashboard.png",
                       "Figure 3: Main dashboard -- one panel per pipeline chain; rows are subjects/stories, "
                       "columns are steps. Click a step cell to auto-process it for that item.")
    pdf.body_text(
        "Status colours: green = completed, yellow = in progress, grey = not started. "
        "To AUTO-PROCESS a step for one item, click its cell. For steps that have more than "
        "one method, a dialog opens where you choose the Method, Model, Prompt version, and "
        "Input variant before it runs. Batch buttons run a step across all items at once."
    )
    pdf.body_text(
        "The File Version dropdown switches between the automated output and any "
        "{ratername}-edit versions when both exist. The 'Change Rater' button (top right) "
        "returns to the Pipeline Configuration page so you can change the rater name or the "
        "pipeline."
    )

    pdf.chapter_title("4.1", "Heavy-Method Warning", level=1)
    pdf.body_text(
        "Some methods load multi-GB local models -- Gemma-4 via Ollama, the rMatch embedding "
        "matcher, local Transformers, or Whisper. Before launching one, the app runs a "
        "resource preflight that checks available RAM, free disk space, and whether the model "
        "/ runtime is even installed. It never downloads or starts a model to make this "
        "decision, so the check itself cannot crash the machine."
    )
    pdf.body_text(
        "If the chosen method is likely too heavy for your device, a popup appears before "
        "anything is spawned. It explains why (e.g. not enough free RAM, not enough disk for "
        "the model) and offers three choices:"
    )
    pdf.bullet("Use lighter method -- one click switches to a free, no-model method "
               "(e.g. rules, keyword 'test', clause) and runs that instead")
    pdf.bullet("Run anyway -- proceed with the heavy method despite the warning")
    pdf.bullet("Cancel -- do nothing")
    pdf.body_text(
        "On a capable machine with the model already installed, the checks pass silently and "
        "no popup interrupts the run."
    )

    # =========================================================================
    # 5. INPUT FILES AND FORMATS
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("5", "Input Files and Formats")

    pdf.chapter_title("5.1", "Story Transcripts", level=1)
    pdf.bold_text("Location: ", "data/2_story_transcript/")
    pdf.bold_text("Format: ", "Plain text files (.txt), one file per story")
    pdf.bold_text("Naming: ", "{story_name}.txt")
    pdf.body_text("The story transcript is the full text of the narrative to be segmented into events.")
    pdf.example_box("Story transcript file (my_story.txt)", [
        "Once upon a time there was a young girl named Clara.",
        "She lived in a small town near the mountains.",
        "One day, she decided to go on an adventure...",
    ])

    pdf.chapter_title("5.2", "Recall Text Files", level=1)
    pdf.bold_text("Location: ", "data/5_recall_texts/")
    pdf.bold_text("Format: ", "Plain text files (.txt), one file per subject")
    pdf.bold_text("Naming: ", "{story_name}_sub-{subject_id}.txt")
    pdf.body_text("Each file contains one subject's recall of the story, transcribed verbatim.")
    pdf.example_box("Recall text file (my_story_sub-001.txt)", [
        "there was a girl named clara who lived in a mountain town",
        "she went on an adventure one day and met a wise old man",
    ])

    pdf.chapter_title("5.3", "Audio Files (Optional)", level=1)
    pdf.bold_text("Story audio: ", "data/1_story_audio/  (.wav, .mp3, .mp4, .m4a, .flac, .ogg)")
    pdf.bold_text("Recall audio: ", "data/4_recall_audio/  (same formats)")
    pdf.body_text(
        "Audio files are used for automatic transcription (Step 1). If you already have text "
        "transcripts, audio files are not required."
    )

    pdf.chapter_title("5.4", "Summary Excel Files (Alternative)", level=1)
    pdf.bold_text("Location: ", "data/summary_*.xlsx (one file per condition)")
    pdf.bold_text("Required columns: ", "'sub' (subject number), 'ID' (subject ID), 'recall' (recall text)")
    pdf.body_text(
        "These Excel files can be used as an alternative source for recall text. "
        "The software will extract individual subject recalls from the 'all' sheet."
    )
    pdf.example_box("Summary Excel structure", [
        "Sheet: 'all'",
        "| sub | ID   | recall                              |",
        "|-----|------|-------------------------------------|",
        "| 1   | 1001 | there was a girl named clara who... |",
        "| 2   | 1002 | clara lived near mountains and...   |",
    ])

    # =========================================================================
    # 6. STEP 1: AUDIO TRANSCRIPTION
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("6", "Step 1: Audio Transcription")

    pdf.chapter_title("6.1", "What This Step Does", level=1)
    pdf.body_text(
        "Converts audio recordings (story narrations or subject recall recordings) into text "
        "transcripts. This is the entry point if your data starts as audio files rather than "
        "text files."
    )

    pdf.chapter_title("6.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "data/1_story_audio/ or data/4_recall_audio/")
    pdf.bold_text("Output: ", "output/story_audio-transcribed/ or output/recall_audio-transcribed/")
    pdf.body_text("Available methods:")
    pdf.bullet(
        "Automatic (WhisperX / Whisper): The preferred engine is WhisperX (batched inference with "
        "word-level alignment); falls back to standard Whisper if WhisperX is not installed. "
        "Default model size: 'large-v2' (WhisperX) or 'medium' (Whisper). "
        "Performs verbatim transcription in English."
    )
    pdf.bullet(
        "Manual: Creates an empty transcript file. Open the Audio Transcription tab in the "
        "detail view to listen to the audio and type or paste the transcription."
    )

    pdf.chapter_title("6.3", "Technical Details", level=1)
    pdf.body_text("Whisper/WhisperX model sizes and their trade-offs:")
    pdf.bullet("'tiny' / 'base': Fastest, lowest accuracy")
    pdf.bullet("'small' / 'medium': Good balance of speed and accuracy")
    pdf.bullet("'large-v2' (default for WhisperX): Best accuracy, requires more memory")
    pdf.body_text(
        "No API key is needed for local transcription. The model runs on your machine. "
        "Install with: pip install whisperx (or pip install openai-whisper for standard Whisper)."
    )

    pdf.chapter_title("6.4", "Interface Walkthrough", level=1)
    pdf.body_text(
        "In the detail view, the Audio Transcription tab shows an audio player on the left "
        "and an editable text area on the right. You can play the audio, pause, and type the "
        "transcription. Click 'Export Edited File' to save."
    )
    pdf.add_screenshot(
        "13_story_audio_transcription_tab.png",
        "Captured from story inspection using bundled story-level audio inputs (same tab layout appears "
        "for recall audio with step 3 subject files). If this image is missing, run developer/capture_tutorial_screenshots.py.",
    )
    pdf.example_box("Transcription output (my_story_sub-001.txt)", [
        "there was a girl named clara who lived in a mountain",
        "town she went on an adventure one day",
    ])

    pdf.chapter_title("6.5", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("Whisper local (only)",
         "Loads OpenAI Whisper locally (no cloud). Pick a model size from the launcher.",
         "--model tiny | base | small | medium | large-v2  (default: base)"),
    ])

    # =========================================================================
    # 7. STEP 2: STORY EVENT SEGMENTATION
    # =========================================================================
    pdf.chapter_title("6.6", "Terminal Command", level=1)
    pdf.body_text("Step 1 also runs headless via the 'narraters' command (no GUI):")
    pdf.code_block([
        "narraters transcribe                       # recall audio (default)",
        "narraters transcribe --kind story --model small",
        "narraters transcribe -i path/in -o path/out --timestamps",
        "narraters transcribe --filter sub-01       # one item only",
    ])
    pdf.body_text(
        "Options: --model (tiny|base|small|medium|large-v2|large-v3); --timestamps "
        "(also write a word-level timing Excel); --kind recall|story (chooses the "
        "conventional input/output directories); -i/--input and -o/--output (override "
        "those directories); --filter (process one item id). Requires the [audio] extra."
    )

    pdf.add_page()
    pdf.chapter_title("7", "Step 2: Story Event Segmentation")

    pdf.chapter_title("7.1", "What This Step Does", level=1)
    pdf.body_text(
        "Splits a story transcript into numbered events. Each event represents a discrete "
        "unit of the narrative (an action, state change, or dialogue turn). The segmentation "
        "level determines how finely the story is divided."
    )

    pdf.chapter_title("7.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "data/2_story_transcript/{story_name}.txt")
    pdf.bold_text("Output: ", "data/3_story_events/{story_name}_events-{method}.xlsx")
    pdf.bold_text("Output columns: ", "'event' (number), 'story_texts' (segment text)")
    pdf.ln(2)
    pdf.body_text("The granularity hierarchy from finest to broadest is:")
    pdf.bullet("Clause Level -- one independent clause per segment (finest, the atomic unit)")
    pdf.bullet("Fine-Grained -- one discrete event per segment (default); each event is 1 or more consecutive clause segments")
    pdf.bullet("Coarse-Grained -- one scene per segment (broadest); each scene is 1 or more consecutive fine-grained events")
    pdf.ln(2)
    pdf.body_text(
        "Each level is built compositionally on the one below it. The clause-level method "
        "produces the atomic segments. Fine-grained segmentation runs clause-level first, "
        "then merges consecutive clause segments into events. Coarse-grained segmentation "
        "runs fine-grained first, then merges consecutive fine-grained events into scene "
        "blocks. This guarantees that every boundary at a coarser level always coincides "
        "with a boundary at the finer level."
    )

    pdf.chapter_title("7.3", "Fundamental Rule", level=1)
    pdf.body_text(
        "Every segment at every level must contain at least one independent clause "
        "(a clause with a subject and a finite verb that can stand alone as a sentence). "
        "Fragments, interjections, and bare noun phrases are automatically merged with "
        "neighbouring segments. Dialogue speech acts (quoted text) are exempt from this rule."
    )

    pdf.chapter_title("7.4", "Method: Clause Level (Atomic Unit)", level=1)
    pdf.body_text(
        "The finest granularity. This is the atomic unit of segmentation -- all other "
        "non-API methods build on these segments. Splits at every independent clause boundary:"
    )
    pdf.bullet("Sentence boundaries (. ! ? followed by uppercase)")
    pdf.bullet("Semicolons (always separate independent clauses)")
    pdf.bullet("Non-restrictive relative clauses: ', who/which/whom'")
    pdf.bullet("Speech attribution + direct speech boundaries")
    pdf.bullet("Commas between independent clauses (subject + verb on both sides)")
    pdf.bullet("Coordinating conjunctions (and/but/so/yet) between independent clauses")
    pdf.body_text("Never splits: subordinate + main clause, time/place + action, participial continuations.")
    pdf.body_text(
        "Post-processing: a proof-check pass merges unjustified fragments (bare time phrases, "
        "dangling subordinates, trailing conjunctions). An independent-clause validation pass "
        "then merges any remaining non-IC segments."
    )

    pdf.chapter_title("7.5", "Method: Fine-Grained (Default)", level=1)
    pdf.body_text(
        "Each discrete action, state change, or dialogue turn is its own event. "
        "Built on clause-level output: runs clause-level segmentation first, then merges "
        "consecutive clause segments into events using the following rules:"
    )
    pdf.bullet("Sentence boundaries always start a new event (clauses from different sentences are never merged)")
    pdf.bullet("Within a sentence, all clauses are merged into one event by default")
    pdf.bullet(
        "Temporal transitions (and then / eventually / later / suddenly / next / finally) "
        "keep the clause split when the current group has 5 or more words"
    )
    pdf.bullet("Contrast transitions (but) keep the clause split when the current group has 8 or more words")
    pdf.bullet("Very short adjacent events (both 3 words or fewer) are merged together")

    pdf.chapter_title("7.6", "Method: Coarse-Grained", level=1)
    pdf.body_text(
        "Scene-level segmentation. Built on fine-grained output: runs fine-grained "
        "segmentation first, then merges consecutive fine-grained events into scene "
        "blocks using the following rules:"
    )
    pdf.bullet(
        "Strong narrative transitions (Later, Eventually, Meanwhile, Suddenly, "
        "The next day, Back at, etc.) start a new scene when the current block has 15 or more words"
    )
    pdf.bullet("Forced split when a block exceeds ~100 words")
    pdf.bullet("All other fine-grained events accumulate into the current scene block")

    pdf.chapter_title("7.7", "Method: API (LLM Call)", level=1)
    pdf.body_text(
        "Uses a language model with a prompt template to segment the story. "
        "This method sends the full story transcript to an LLM and receives back "
        "a segmented version."
    )
    pdf.body_text("Available API models:")
    pdf.bullet("Sonnet 4.5 tier (Anthropic) -- requires ANTHROPIC_API_KEY")
    pdf.bullet("Haiku 3.5 tier (Anthropic) -- faster, lower cost")
    pdf.bullet("GPT-4o (OpenAI) -- requires OPENAI_API_KEY")
    pdf.bullet("GPT-4o Mini (OpenAI) -- faster, lower cost")
    pdf.bullet("Gemma 4 E4B (Ollama, local) -- no cloud key; requires Ollama with e.g. gemma4:e4b pulled")
    pdf.bullet("Optional Llama tags via the same Ollama API path (see UI presets)")
    pdf.body_text(
        "Select the model from the Method dropdown in the web interface. "
        "The model choice determines both quality and cost."
    )
    pdf.body_text("Prompt used (from scripts/prompt/event_segment.txt):")
    pdf.code_block([
        "An event is an ongoing coherent situation. The following",
        "story needs to be copied and segmented into events.",
        "Copy the following story word-for-word and start a new",
        "line whenever one event ends and another begins.",
        "This is the story:",
    ])
    pdf.body_text(
        "To modify the prompt: edit scripts/prompt/event_segment.txt directly. "
        "You can also create alternate versions (e.g., event_segment_v2.txt) and "
        "select them from the command line with --prompt-version."
    )

    pdf.chapter_title("7.8", "Method: Manual", level=1)
    pdf.body_text(
        "Places the full transcript as a single event. Open the Story Segments tab "
        "in the detail view to manually split/merge events using the Split and Merge buttons."
    )

    pdf.chapter_title("7.9", "Interface Walkthrough", level=1)
    pdf.body_text(
        "In the detail view, the Story Segments tab shows the full story transcript on the "
        "left and the segmented events on the right. Each event is shown in an editable text "
        "box with its event number."
    )
    pdf.add_screenshot("06_story_events.png",
                       "Figure 4: Story events segmentation view -- left: full transcript; right: segmented events")

    pdf.chapter_title("7.10", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("clause",
         "Rule-based atomic-clause segmentation. Uses spaCy if installed, else regex.",
         "no key needed"),
        ("fine (default)",
         "Rule-based mid-grained segmentation. Merges adjacent clauses into events.",
         "no key needed"),
        ("coarse",
         "Rule-based coarse segmentation. Larger event units (paragraph-like).",
         "no key needed"),
        ("api",
         "LLM-based segmentation using a remote API or local Ollama.",
         "--model <id>  --prompt-version <name>\nANTHROPIC_API_KEY or OPENAI_API_KEY (none for Ollama)"),
        ("manual",
         "Places the full transcript as a single event for hand-segmentation in the UI.",
         "no key needed"),
    ])
    pdf.body_text("Models offered when method=api (see Section 15.1 for the full list):")
    _anthropic_rows = [
        (
            mid,
            f"{meta['label']}; see Anthropic console for pricing.",
            "ANTHROPIC_API_KEY",
        )
        for mid, meta in sorted(ANTHROPIC_SUPPORTED_MODELS.items(), key=lambda kv: kv[0])
    ]
    pdf.methods_table(
        _anthropic_rows
        + [
        ("gpt-4o / gpt-4o-mini",
         "OpenAI alternatives.",
         "OPENAI_API_KEY"),
        ("gemma4-e4b-ollama",
         "Local Gemma 4 E4B via Ollama; no cloud key.",
         "EVENT_SEGMENT_OLLAMA_MODEL override optional"),
        ("llama3.3-ollama / llama5.3-ollama",
         "Local Llama tags via Ollama.",
         "same; override tag via env"),
    ], col_widths=(40, 90, 50))
    pdf.body_text("Editing controls:")
    pdf.bullet("Split: click between two events to insert a boundary")
    pdf.bullet("Merge: combine adjacent events into one")
    pdf.bullet("Export Edited File: save your edits as {story}_events_{ratername}-edit.xlsx")

    pdf.example_box("Story events output ({story_name}_events-fine.xlsx)", [
        "| event | story_texts                                     |",
        "|-------|-------------------------------------------------|",
        "| 1     | Once upon a time there was a young girl Clara.  |",
        "| 2     | She lived in a small town near the mountains.   |",
        "| 3     | One day, she decided to go on an adventure.     |",
    ])

    # =========================================================================
    # 8. STEP 3: SPELL & GRAMMAR CORRECTION
    # =========================================================================
    pdf.chapter_title("7.11", "Terminal Command", level=1)
    pdf.body_text("Run Step 2 from the terminal:")
    _seg_m = anthropic_model_slug("sonnet-4-6")
    pdf.code_block([
        "narraters segment --method clause",
        "narraters segment --method fine -i data/2_story_transcript/my_story.txt",
        f"narraters segment --method api --model {_seg_m} \\",
        "                  --prompt-version event_segment",
        "narraters segment --list-prompts     # show available prompt versions",
    ])
    pdf.body_text(
        "--method: clause | fine | coarse | api. --model is used only with --method "
        "api. -i/--input may be a single transcript file or a directory; -o/--output "
        "defaults to data/3_story_events/."
    )

    pdf.add_page()
    pdf.chapter_title("8", "Step 3: Spell & Grammar Correction")

    pdf.chapter_title("8.1", "What This Step Does", level=1)
    pdf.body_text(
        "Corrects spelling and grammar errors in recall text while strictly preserving "
        "the original meaning, structure, and wording. Only clear errors are fixed -- "
        "the step never rewrites, paraphrases, or restructures sentences."
    )

    pdf.chapter_title("8.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "data/5_recall_texts/{subject_id}.txt (or summary Excel)")
    pdf.bold_text("Output: ", "output/recall_corrected/{subject_id}.txt (rules), or Gemma outputs *_spell-gemma-hf_* / *_spell-ollama_*")
    pdf.body_text("Available methods:")
    pdf.bullet(
        "Automatic (Rule-Based, default): A multi-pass pipeline that applies conservative "
        "corrections in sequence."
    )
    pdf.bullet(
        "Manual: Copies the raw input text to the output folder. Open the Corrected Recall "
        "tab in the detail view to manually correct the text side-by-side with the original."
    )
    pdf.bullet(
        "Gemma 4 (Hugging Face, local): Uses google/gemma-4-E4B-it by default with scripts/prompt/spell_gram.txt. "
        "Requires PyTorch + transformers."
    )
    pdf.bullet(
        "Gemma 4 (Ollama, local): Same prompt via Ollama (default model tag gemma4:e4b); optional override in the UI."
    )

    pdf.chapter_title("8.3", "Automatic Processing Pipeline", level=1)
    pdf.body_text("The automatic mode applies corrections in this order:")
    pdf.bullet("1. Abbreviation protection: protects known abbreviations (p.m., a.m., e.g., i.e., etc.) from incorrect splitting")
    pdf.bullet("2. Contraction repair: fixes broken contractions (could't -> couldn't, did'nt -> didn't)")
    pdf.bullet("3. Grammar fixes: corrects common grammar issues ('i' -> 'I', 'i a,' -> 'I am,')")
    pdf.bullet("4. Capitalisation: adds capitals after sentence-ending punctuation (not after abbreviation periods)")
    pdf.bullet("5. Common misspellings: fixes frequent misspellings (seperate -> separate, recieve -> receive)")
    pdf.bullet("6. Punctuation cleanup: fixes spacing, duplicates, misplaced periods")
    pdf.bullet("7. Spell-check: uses pyspellchecker with a whitelist for proper nouns, acronyms, Roman numerals. Blocks plural-to-singular and adjective-to-verb changes.")
    pdf.bullet("8. LanguageTool (optional): additional grammar fixes, skipping style/typography rules")

    pdf.chapter_title("8.4", "Interface Walkthrough", level=1)
    pdf.body_text(
        "In the detail view, the Corrected Recall tab shows the raw recall text on the left "
        "and the corrected text on the right. You can directly edit the corrected text and "
        "save it."
    )
    pdf.add_screenshot(
        "09_subject_corrected_recall_tab.png",
        "Subject inspection -- Corrected Recall tab (Step 3).",
    )
    pdf.example_box("Before correction", [
        "there was a girl named clara who lived in a mountian",
        "tow she went on an adventure one day",
    ])
    pdf.example_box("After correction", [
        "There was a girl named Clara who lived in a mountain",
        "town. She went on an adventure one day.",
    ])

    pdf.chapter_title("8.5", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("rule-based (default)",
         "Local spell-checker + targeted grammar fixes. Conservative; no rewrites.",
         "no key needed"),
        ("gemma-ollama",
         "Local Gemma 4 via Ollama; same minimal-correction prompt as the cloud path.",
         "Ollama running locally"),
        ("manual",
         "Copies raw text into the corrected output for hand-editing in the UI.",
         "no key needed"),
    ])

    # =========================================================================
    # 9. STEP 4: RECALL PARSING
    # =========================================================================
    pdf.chapter_title("8.6", "Terminal Command", level=1)
    pdf.body_text("Run Step 3 from the terminal:")
    pdf.code_block([
        "narraters correct --method rules",
        "narraters correct --method gemma-ollama --ollama-model gemma4:e4b",
    ])
    pdf.body_text(
        "--method: rules (entirely local, no model) | gemma-ollama (needs a local "
        "Ollama server). --ollama-model sets the model tag; --prompt-file overrides "
        "the instructions file; -i/--input is a single recall text file and "
        "-o/--output its directory."
    )

    pdf.add_page()
    pdf.chapter_title("9", "Step 4: Recall Parsing")

    pdf.chapter_title("9.1", "What This Step Does", level=1)
    pdf.body_text(
        "Splits the corrected recall text into clause-level segments. Each segment "
        "represents one idea unit that can be matched to a story event. This step uses "
        "the same fundamental rule as story segmentation: every segment must contain at "
        "least one independent clause."
    )

    pdf.chapter_title("9.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "output/recall_corrected/{subject_id}.txt or method-specific spell outputs")
    pdf.bold_text("Output: ", "output/recall_parsed/{subject_id}_parsed.xlsx (rules) or {subject_id}_parsed-ollama_*.xlsx (Ollama)")
    pdf.bold_text("Output columns: ", "'recalled_events' (empty, filled in Step 5), 'recall_in_temporal_order' (segment text)")
    pdf.body_text("Available methods:")
    pdf.bullet(
        "Automatic (Clause-Based, default): Uses the same clause-level splitting rules "
        "as story segmentation (sentence boundaries, semicolons, non-restrictive relative "
        "clauses, comma-separated independent clauses, coordinating conjunctions). Includes "
        "a proof-check pass and independent-clause validation."
    )
    pdf.bullet(
        "Manual: Places the full corrected text as a single segment. Use Split/Merge buttons "
        "in the detail view to segment manually."
    )
    pdf.bullet(
        "Gemma 4 (Ollama, local): Uses scripts/prompt/recall_parse_clause.txt with your local Ollama server; "
        "output filename includes the method tag."
    )

    pdf.chapter_title("9.3", "Splitting Rules (Automatic Mode)", level=1)
    pdf.bullet("Sentence boundaries (. ! ? followed by capital letter, ignoring abbreviation periods)")
    pdf.bullet("Closing-quote sentence boundaries (. ! ? + \" correctly keeps quote with its sentence)")
    pdf.bullet("Semicolons (always split)")
    pdf.bullet("Non-restrictive relative clauses (, who/which/whom with own verb)")
    pdf.bullet("Commas between independent clauses (>= 6 words before, new subject+verb after)")
    pdf.bullet("Coordinating conjunctions (and/but/so/yet) between independent clauses with different subjects")
    pdf.body_text(
        "Optional NLP enhancement: If spaCy is installed (pip install spacy && python -m spacy download en_core_web_sm), "
        "dependency parsing is used for more accurate clause boundary detection. Otherwise regex heuristics are applied."
    )

    pdf.chapter_title("9.4", "Interface Walkthrough", level=1)
    pdf.body_text(
        "In the detail view, the Parsed Recall tab shows the story events on the left "
        "(for reference) and the parsed recall segments on the right. Each segment is an "
        "editable text box."
    )
    pdf.add_screenshot(
        "10_subject_parsed_recall_tab.png",
        "Subject inspection -- Parsed Recall tab (Step 4).",
    )

    pdf.example_box("Parsed recall output ({subject_id}_parsed.xlsx)", [
        "| recalled_events | recall_in_temporal_order                    |",
        "|----------------|--------------------------------------------|",
        "|                | There was a girl named Clara.               |",
        "|                | She lived in a mountain town.               |",
        "|                | She went on an adventure one day.           |",
    ])

    pdf.chapter_title("9.5", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("rule-based (default)",
         "Sentence-level splitter with regex clause boundaries. Fast and deterministic.",
         "no key needed"),
        ("gemma-ollama",
         "Local Gemma 4 via Ollama for clause parsing.",
         "Ollama running locally\nRECALL_PARSE_METHOD=ollama"),
        ("manual",
         "Loads the corrected text as a single segment for hand-splitting in the UI.",
         "no key needed"),
    ])

    # =========================================================================
    # 10. STEP 5: RECALL RATING
    # =========================================================================
    pdf.chapter_title("9.6", "Terminal Command", level=1)
    pdf.body_text("Run Step 4 from the terminal:")
    pdf.code_block([
        "narraters parse --method rules",
        "narraters parse --method ollama --model gemma4:e4b",
        "narraters parse --filter-pattern sub-02     # one subject only",
    ])
    pdf.body_text(
        "--method: rules (default, regex, no model) | ollama (local Gemma via "
        "Ollama). -i/--input defaults to output/recall_corrected/ and -o/--output "
        "to output/recall_parsed/; --filter-pattern limits to one subject."
    )

    pdf.add_page()
    pdf.chapter_title("10", "Step 5: Recall Rating")

    pdf.chapter_title("10.1", "What This Step Does", level=1)
    pdf.body_text(
        "Matches each recall segment to one or more story events. This is the final "
        "processing step that produces the scored recall data suitable for analysis."
    )

    pdf.chapter_title("10.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "output/recall_parsed/{subject_id}_parsed.xlsx + data/3_story_events/{story}_events.xlsx")
    pdf.bold_text("Output: ", "output/recall_rated/{subject_id}_rate-recall*.xlsx (filename suffix shows API vs Ollama vs test mode)")
    pdf.body_text("Available methods:")
    pdf.bullet(
        "Test Mode (default): Keyword/phrase matching without API. Uses phrase overlap, "
        "concept matching, and word overlap with score thresholds. Returns up to 3 matched "
        "events per segment. Fast, no cost, no API key needed."
    )
    pdf.bullet(
        "API (LLM Call): Sends all recall segments and story events to an Anthropic "
        "Messages API model in a single batch request. The launcher exposes a Model dropdown "
        "(Opus 4.7, Sonnet 4.6, Haiku 4.5, Sonnet 4.5, Haiku 3.5 -- see Section 14.1). "
        "More accurate for semantic matching. Requires ANTHROPIC_API_KEY."
    )
    pdf.bullet(
        "Manual: Copies parsed segments with empty event-match fields. Assign story event "
        "numbers manually in the detail view."
    )
    pdf.bullet(
        "Gemma 4 (Ollama, local): Same batch JSON prompt as the cloud API path (scripts/prompt/recall_rating.txt) via Ollama; "
        "default tag gemma4:e4b. Output is JSON-schema-constrained so the model returns one "
        "match object per recall row even without an Anthropic key."
    )
    pdf.bullet(
        "rMatch (Hugging Face, local): Uses the PyPI rmatch package "
        "(github.com/gabrielkp/rmatch) with a local Hugging Face causal-LM. Best when a "
        "GPU/MPS is available. See Section 10.5."
    )

    pdf.chapter_title("10.3", "API Method Details", level=1)
    pdf.body_text(
        "When using the API method, the software sends all recall segments and story events "
        "to the Anthropic Messages API in a single batch request. The model returns a JSON mapping each "
        "recall row to its matched event number(s)."
    )
    pdf.body_text("Prompt used (from scripts/prompt/recall_rating.txt):")
    pdf.code_block([
        "You are given two Excel files:",
        "story_events.xlsx (each row is a story event; columns:",
        "  'event', 'story_texts') and",
        "story_recall.xlsx (each row is one recall segment).",
        "Go through the recall file row by row.",
        "For each recall segment, identify which story event(s)",
        "  it refers to.",
        "* Write the matching event number(s) into column 1.",
        "* If multiple events are referenced, separate with commas.",
        "* If no event matches, use NONE.",
        "",
        "Output format (STRICT): Output ONLY valid JSON array.",
        "Each element: {\"row_index\": N, \"matched_events\": ...}",
    ])
    pdf.body_text(
        "To modify the prompt: edit scripts/prompt/recall_rating.txt directly. Alternative prompt "
        "versions (recall_rating_v2.txt, recall_rating_v3.txt, etc.) can be created in the "
        "scripts/prompt/ folder and selected via the RECALL_RATING_PROMPT environment variable:"
    )
    pdf.code_block([
        "export RECALL_RATING_PROMPT=\"recall_rating_v2\"",
        "python scripts/5_recall-rater.py",
    ])
    pdf.body_text(
        "See scripts/prompt/README.md for documentation on all available prompt versions and their "
        "differences."
    )

    pdf.chapter_title("10.5", "rMatch Method (Hugging Face, local)", level=1)
    pdf.body_text(
        "The rMatch method uses the PyPI rmatch package (github.com/gabrielkp/rmatch) to "
        "score recall-to-event matches with a locally hosted Hugging Face causal-LM. Unlike "
        "the Ollama path, rmatch runs the model directly via transformers/bitsandbytes, so it "
        "can leverage GPU/MPS when available and run any HF chat-tuned model."
    )
    pdf.bold_text("Requirements: ", "")
    pdf.bullet("pip install rmatch (already listed in requirements.txt)")
    pdf.bullet(
        "Hugging Face token (HF_TOKEN) in software/.env, in environment, or via "
        "huggingface-cli login"
    )
    pdf.bullet("Enough disk + RAM for the chosen model; see warning below")
    pdf.bold_text("Configuration via environment variables (or step options in the UI):", "")
    pdf.bullet("RMATCH_MODEL_NAME -- HF model id (default google/gemma-4-31B-it)")
    pdf.bullet("RMATCH_QUANTIZATION -- 4bit | 8bit | (empty for none)")
    pdf.bullet("RMATCH_WINDOW_SIZE -- sliding-window size, integer (default 5)")
    pdf.bullet("RMATCH_PROMPT -- one of primary, primary_no_story, primary_no_cot, "
               "primary_no_story_no_cot (default), secondary")
    pdf.bullet("RMATCH_BATCH_SIZE -- inference batch size; defaults to 1 on macOS to avoid "
               "Metal NDArray limits")
    pdf.bullet("RMATCH_FORCE_CPU -- 1/true to bypass Apple MPS (more RAM, slower)")
    pdf.bullet("RMATCH_MAX_NEW_TOKENS -- per-call generation budget")
    pdf.body_text(
        "WARNING: the default model google/gemma-4-31B-it is roughly 18 GB on disk and needs "
        "around 16 GB RAM even with 4-bit quantization. On a CPU-only machine, matching 30+ "
        "recall segments can take hours. Pick a smaller HF model (e.g. google/gemma-2-2b-it "
        "or Qwen/Qwen2.5-1.5B-Instruct) for tractable runtimes on a laptop, trading off "
        "accuracy. The launcher description repeats this warning."
    )
    pdf.body_text(
        "Output filename suffix: -rmatch-pypi-{model-slug}-{quant}.xlsx so multiple rMatch "
        "runs with different models coexist without overwriting each other."
    )

    pdf.chapter_title("10.6", "Interface Walkthrough", level=1)
    pdf.body_text(
        "In the detail view, the Recall Matching tab shows the story events on the left "
        "and the recall segments on the right. Each segment has an editable field for the "
        "matched event number(s). Enter event numbers separated by commas for multiple matches."
    )
    pdf.add_screenshot(
        "11_subject_recall_matching_tab.png",
        "Subject inspection -- Recall Matching tab (Step 5).",
    )

    pdf.example_box("Recall rating output ({subject_id}_rate-recall.xlsx)", [
        "| recalled_events | recall_in_temporal_order                    |",
        "|----------------|--------------------------------------------|",
        "| 1              | There was a girl named Clara.               |",
        "| 2              | She lived in a mountain town.               |",
        "| 3              | She went on an adventure one day.           |",
    ])

    pdf.chapter_title("10.7", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("test-mode (default)",
         "Keyword/phrase overlap matcher. Fast, deterministic, no LLM.",
         "no key needed"),
        ("api",
         "Anthropic batch matcher. Picks Anthropic model from dropdown.",
         "ANTHROPIC_API_KEY\nRECALL_RATING_MODEL=<id>"),
        ("gemma-ollama",
         "Local Gemma 4 E4B via Ollama; JSON-schema constrained output.",
         "Ollama running locally\nRECALL_RATING_BACKEND=ollama\nOLLAMA_GEMMA_TAG override optional"),
        ("rmatch",
         "PyPI rmatch + Hugging Face causal-LM. See Section 10.5 for size warnings.",
         "HF_TOKEN\nRECALL_RATING_BACKEND=rmatch\nRMATCH_MODEL_NAME, RMATCH_QUANTIZATION,\nRMATCH_WINDOW_SIZE, RMATCH_PROMPT"),
        ("manual",
         "Copies parsed segments with empty event-match fields for hand-rating in UI.",
         "no key needed"),
    ])

    # =========================================================================
    # 11. STEP 6: CAUSAL RATING
    # =========================================================================
    pdf.chapter_title("10.8", "Terminal Command", level=1)
    pdf.body_text("Run Step 5 from the terminal:")
    pdf.code_block([
        "narraters match --test-mode                 # keyword, no model/API",
        "narraters match --method api --story-events data/3_story_events",
        "narraters match --method gemma-ollama",
        "narraters match --method rmatch             # needs the [match] extra",
    ])
    pdf.body_text(
        "--method: test | api | gemma-ollama | rmatch (--test-mode == --method test). "
        "--story-events points at the {story}_events.xlsx directory; -i/--input is "
        "the recall-parsed directory and -o/--output the rated-output directory."
    )

    pdf.add_page()
    pdf.chapter_title("11", "Step 6: Causal Rating")

    pdf.chapter_title("11.1", "What This Step Does", level=1)
    pdf.body_text(
        "Rates the strength of the causal relation between every pair of story events. "
        "Operates on the segmented story events from Step 2 (not on the recall) and produces "
        "a square cause-by-effect matrix of ratings 0-3. Optional per-pair fields capture "
        "reasoning text, causal type (physical / motivational / psychological / enabling), "
        "and a semantic-similarity score."
    )

    pdf.chapter_title("11.2", "How It Works", level=1)
    pdf.bold_text("Input: ", "data/3_story_events/{story}_events.xlsx (or a per-variant version)")
    pdf.bold_text(
        "Output: ",
        "output/causal_rated/{story}_causal-{method}.xlsx (one row per (event_A, event_B) "
        "pair with rating > 0; optional reasoning / causal_type / semantic columns)"
    )
    pdf.body_text("Available methods:")
    pdf.bullet(
        "Linguistic (default): Rule-based causal scoring using causal connectives, entity "
        "continuity, and action-consequence verb patterns. No API key required. Uses spaCy "
        "if installed; falls back to a regex-based scorer otherwise."
    )
    pdf.bullet(
        "API (LLM Call): Sends each pair (or batch of pairs) to an Anthropic or OpenAI model "
        "and parses a structured rating + reasoning. Model dropdown lists the same Anthropic "
        "options as Steps 2 and 5 (Opus 4.7, Sonnet 4.6, Haiku 4.5, Sonnet 4.5, Haiku 3.5; "
        "see Section 15.1). Requires an API key."
    )
    pdf.bullet(
        "Manual: Creates an empty causal-rating workbook so you can fill in ratings cell-by-"
        "cell in the matrix UI."
    )

    pdf.chapter_title("11.3", "Cell-Picker UI", level=1)
    pdf.body_text(
        "The detail view shows the cause-by-effect matrix. Hover any cell to preview both "
        "event texts; click a cell to open the multi-step picker. The picker asks for the "
        "rating (0-3), then -- depending on which flags are checked in the toolbar -- for "
        "reasoning text, causal type, and a semantic-similarity score. The currently saved "
        "value is highlighted in yellow so you can see it before overwriting. The mode "
        "dropdown above the matrix lets you visualize the matrix as Causal (default) or "
        "Semantic-similarity connection lines."
    )
    pdf.body_text(
        "Click x in a cell (or pick 0) to clear a rating."
    )
    pdf.add_screenshot(
        "14_story_causal_rating_tab.png",
        "Causal Rating inspection tab on a story row: matrix + event sidebar. Regenerate screenshots with developer/capture_tutorial_screenshots.py.",
    )

    pdf.chapter_title("11.4", "Export With Custom Filename", level=1)
    pdf.body_text(
        "The Export Causal Ratings button opens a popup pre-filled with a default path "
        "(output/causal_rated/{story}_causal-manual_{ratername}-edit.xlsx for manual edits, "
        "or the source file's name preserved for re-export). You can edit the filename in "
        "the popup before clicking Save; the file is written exactly to the path you enter, "
        "as long as it resolves to somewhere inside the project root. This is how you save "
        "named variants such as ..._trial2.xlsx or ..._post-review.xlsx."
    )
    pdf.body_text(
        "Cancel closes the popup without saving. Enter confirms; Escape cancels."
    )

    pdf.chapter_title("11.5", "Saved Columns", level=1)
    pdf.body_text(
        "Each row in the output workbook is one rated (event_A, event_B) pair. Columns "
        "are gated by the flag checkboxes in the toolbar:"
    )
    pdf.bullet("event_A, event_B -- the cause and effect event numbers")
    pdf.bullet("rating -- integer 1, 2, or 3 (rows with 0 are not saved)")
    pdf.bullet("reasoning -- free text (only when the Reasoning flag is on)")
    pdf.bullet("causal_type -- physical / motivational / psychological / enabling / other "
               "(only when the Causal Type flag is on)")
    pdf.bullet("semantic -- 0-3 score (only when the Semantic flag is on)")

    pdf.chapter_title("11.6", "Methods & Options Reference", level=1)
    pdf.methods_table([
        ("linguistic (default)",
         "Rule-based causal scorer using connectives, entity continuity, action-consequence verbs.",
         "no key needed\nspaCy used if installed"),
        ("api",
         "LLM-based causal rating. Pick Anthropic model from dropdown.",
         "ANTHROPIC_API_KEY or OPENAI_API_KEY\nCAUSAL_RATING_MODEL=<id>\nCAUSAL_RATING_PROMPT=<name>"),
        ("manual",
         "Creates an empty rating workbook for hand-filling in the matrix UI.",
         "no key needed"),
    ])

    # =========================================================================
    # 12. DETAIL VIEW AND MANUAL EDITING
    # =========================================================================
    pdf.chapter_title("11.7", "Terminal Command", level=1)
    pdf.body_text("Run Step 6 from the terminal:")
    _rate_m = anthropic_model_slug("sonnet-4-6")
    pdf.code_block([
        "narraters rate --method linguistic",
        f"narraters rate --method api --model {_rate_m} \\",
        "               --prompt-version causal_rating",
        "narraters rate --method manual     # empty NxN matrix to fill by hand",
    ])
    pdf.body_text(
        "--method: linguistic (rule-based, no model) | api (LLM) | manual (writes an "
        "empty matrix for hand rating). --model and --prompt-version apply to "
        "--method api; -i/--input and -o/--output set the event-list input and "
        "causal-rated output."
    )

    pdf.add_page()
    pdf.chapter_title("12", "Detail View and Manual Editing")
    pdf.body_text(
        "Click any row in the dashboard to open detail / inspection views. Stories and subjects "
        "each get a tab strip for whichever pipeline steps apply. Most recall tabs mirror the pipeline "
        "order shown on the Dashboard; story rows add Story Segments, optional story audio transcription, "
        "and -- when causalRating is configured -- Causal Rating."
    )
    pdf.body_text(
        "Figures below are regenerated together from developer/capture_tutorial_screenshots.py "
        "using bundled the_siren/pieman examples; missing thumbnails mean screenshots were "
        "not rebuilt after a UI update."
    )
    pdf.bold_text("Story inspection snapshots", "")
    pdf.add_screenshot(
        "05_story_detail.png",
        "Story inspection (default routing) showing the story-row tab strip (example: bundled the_siren materials).",
    )
    pdf.add_screenshot(
        "06_story_events.png",
        "Story inspection deep-linked to segmented events / Story Segments layout (routing .../story/<name>/step0).",
    )
    pdf.add_screenshot(
        "14_story_causal_rating_tab.png",
        "Causal Rating matrix mounted on story inspection (.../story/<name>/step0_causal when causalRating runs).",
    )
    pdf.add_screenshot(
        "13_story_audio_transcription_tab.png",
        "Story-level Audio Transcription tab (example capture with pieman_edited story audio bundled in data/).",
    )
    pdf.bold_text("Subject recall inspection snapshots", "")
    pdf.add_screenshot(
        "07_subject_detail.png",
        "Subject inspection landing tab immediately after navigating from the dashboard (defaults depend on configured steps/data).",
    )
    pdf.add_screenshot(
        "08_subject_recall_audio_tab.png",
        "Recall inspection -- Audio Transcription tab for subjects with recall recordings (bundled mp4/audio for the_siren).",
    )
    pdf.add_screenshot(
        "12_subject_story_segments_reference_tab.png",
        "Subject inspection -- Story Segments reference tab injected whenever recall parsing steps need contextual story segmentation.",
    )
    pdf.add_screenshot(
        "09_subject_corrected_recall_tab.png",
        "Subject inspection -- Corrected Recall.",
    )
    pdf.add_screenshot(
        "10_subject_parsed_recall_tab.png",
        "Subject inspection -- Parsed Recall.",
    )
    pdf.add_screenshot(
        "11_subject_recall_matching_tab.png",
        "Subject inspection -- Recall Matching.",
    )

    pdf.body_text("Editing controls per tab:")
    pdf.bullet("Audio Transcription: audio player (left) + editable transcript (right). Export to save.")
    pdf.bullet("Story Segments: full story transcript (left) + event segments (right). Split, Merge, Export.")
    pdf.bullet("Corrected Recall: raw recall text (left) + corrected text editor (right). Export to save.")
    pdf.bullet("Parsed Recall: story events reference (left) + parsed segments (right). Split, Merge, Export.")
    pdf.bullet("Recall Matching: story events reference (left) + recall with event editors (right). Export to save.")
    pdf.ln(2)
    pdf.body_text(
        "When you export an edited file, it is saved with your rater name in the filename "
        "(e.g., {subject_id}_{ratername}-edit.txt). This keeps automated and manual versions "
        "separate. Use the File Version dropdown to switch between versions."
    )
    pdf.body_text(
        "Keyboard shortcut: Ctrl+S (Windows/Linux) or Cmd+S (macOS) to save the current tab."
    )

    # =========================================================================
    # 12. OUTPUT FILES AND FORMATS
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("13", "Output Files and Formats")

    pdf.chapter_title("13.1", "Corrected Recall", level=1)
    pdf.bold_text("Location: ", "output/recall_corrected/")
    pdf.bold_text("Format: ", "Plain text (.txt)")
    pdf.bold_text("Naming: ", "{subject_id}.txt (auto) or {subject_id}_{ratername}-edit.txt (manual)")
    pdf.example_box("Corrected recall file", [
        "There was a girl named Clara who lived in a mountain town.",
        "She went on an adventure one day and met a wise old man.",
    ])

    pdf.chapter_title("13.2", "Parsed Recall", level=1)
    pdf.bold_text("Location: ", "output/recall_parsed/")
    pdf.bold_text("Format: ", "Excel (.xlsx)")
    pdf.bold_text("Columns: ", "'recalled_events' (initially empty), 'recall_in_temporal_order' (segment text)")

    pdf.chapter_title("13.3", "Rated Recall", level=1)
    pdf.bold_text("Location: ", "output/recall_rated/")
    pdf.bold_text("Format: ", "Excel (.xlsx)")
    pdf.bold_text("Columns: ", "'recalled_events' (matched event numbers), 'recall_in_temporal_order' (segment text)")

    pdf.chapter_title("13.4", "Story Events", level=1)
    pdf.bold_text("Location: ", "data/3_story_events/")
    pdf.bold_text("Format: ", "Excel (.xlsx)")
    pdf.bold_text("Columns: ", "'event' (number), 'story_texts' (segment text)")

    # =========================================================================
    # 13. COMMAND-LINE USAGE
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("14", "Command-Line Usage")
    pdf.body_text("You can also run each step directly from the terminal:")
    pdf.ln(2)
    pdf.code_block([
        "# Audio transcription",
        "python scripts/1_audio-transcribe.py",
        "",
        "# Story event segmentation (fine-grained)",
        "python scripts/2_story-event-segment.py --method fine",
        "",
        "# Story event segmentation (API with specific model)",
        "python scripts/2_story-event-segment.py --method api --model gpt-4o",
        "",
        "# List available models and prompts",
        "python scripts/2_story-event-segment.py --list-models",
        "python scripts/2_story-event-segment.py --list-prompts",
        "",
        "# Spell & grammar correction",
        "python scripts/3_spell-grammar-correct.py",
        "",
        "# Recall parsing",
        "python scripts/4_parse-texts.py",
        "",
        "# Recall rating",
        "python scripts/5_recall-rater.py",
    ])
    pdf.body_text("All outputs are saved to the output/ directory.")

    pdf.body_text("Common command-line options for Step 2 (Story Event Segmentation):")
    pdf.bullet("--method {clause|fine|coarse|api}: choose segmentation method")
    pdf.bullet("--model {model_name}: specify LLM model for API method")
    pdf.bullet("--prompt-version {filename}: specify prompt file for API method")
    pdf.bullet("--input {path}: specify input file instead of scanning the default directory")
    pdf.bullet("--reconstruct {events.xlsx}: reconstruct story text from event segmentation file")

    # =========================================================================
    # 14. API CONFIGURATION REFERENCE
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("15", "API Configuration Reference")

    pdf.chapter_title("15.1", "Supported Models", level=1)
    pdf.body_text(
        "The following LLM models are exposed in the web-interface dropdown for steps that "
        "offer an API method (Step 2 Story Event Segmentation, Step 5 Recall Rating, and "
        "Step 6 Causal Rating)."
    )
    pdf.ln(1)
    pdf.bold_text("Anthropic Messages API:", "")
    for mid, meta in sorted(ANTHROPIC_SUPPORTED_MODELS.items(), key=lambda kv: kv[0]):
        pdf.bullet(f"{mid} -- {meta['label']}")
    pdf.ln(1)
    pdf.bold_text("OpenAI:", "")
    pdf.bullet("gpt-4o -- high quality, alternative to Anthropic balanced tiers")
    pdf.bullet("gpt-4o-mini -- faster and cheaper")
    pdf.ln(1)
    pdf.bold_text("Local (no cloud key):", "")
    pdf.bullet("Ollama (Gemma 4 E4B) -- shared backend for Steps 3, 4, and 5; uses local Ollama server")
    pdf.bullet("rMatch (Hugging Face) -- Step 5 only; PyPI rmatch package, requires HF_TOKEN")
    pdf.body_text(
        "Model selection: pick from the API method dropdown in the launcher, or pass --model "
        "on the command line. The Step 5 launcher also exposes rMatch as a fourth method "
        "(Test Mode / API / Ollama / rMatch). Different steps may benefit from different models."
    )

    pdf.chapter_title("15.2", "Prompt Files", level=1)
    pdf.body_text("All prompts are stored as plain text files in the scripts/prompt/ folder:")
    pdf.bullet("scripts/prompt/event_segment.txt -- used by Step 2 (Story Event Segmentation) API method")
    pdf.bullet("scripts/prompt/recall_rating.txt -- used by Step 5 (Recall Rating) API method")
    pdf.body_text(
        "You can create alternative prompt versions by adding new files to the scripts/prompt/ folder "
        "(e.g., recall_rating_v2.txt). Select them via environment variable or command-line flag."
    )

    pdf.chapter_title("15.3", "Setting Up API Keys", level=1)
    pdf.body_text("Three ways to provide API keys:")
    pdf.bullet("Environment variable: export ANTHROPIC_API_KEY='sk-ant-...' (or OPENAI_API_KEY)")
    pdf.bullet("Setup script: bash scripts/setup_api_key.sh (interactive prompts)")
    pdf.bullet("Web interface: enter the key on the Pipeline Configuration page")
    pdf.body_text(
        "API keys are never stored in code files. They are read from the environment at runtime."
    )

    # =========================================================================
    # 15. TIPS AND BEST PRACTICES
    # =========================================================================
    pdf.add_page()
    pdf.chapter_title("16", "Tips and Best Practices")
    pdf.bullet("Always verify automated output before proceeding to the next step.")
    pdf.bullet(
        "Use Fine-Grained segmentation for most research purposes; switch to Clause Level "
        "only when you need the finest possible granularity."
    )
    pdf.bullet(
        "The web interface supports keyboard shortcuts: Ctrl+S / Cmd+S to save the current tab."
    )
    pdf.bullet(
        "Install spaCy for more accurate clause boundary detection: "
        "pip install spacy && python -m spacy download en_core_web_sm"
    )
    pdf.bullet(
        "If you have an Anthropic API key, the API segmentation method and Anthropic-based "
        "recall rating tend to produce higher-quality results."
    )
    pdf.bullet(
        "Multiple users can work on the same dataset -- each rater's edits are saved with "
        "their rater name, so nothing is overwritten."
    )
    pdf.bullet(
        "For large datasets, use the Batch Process button on the dashboard to process "
        "all items at once."
    )
    pdf.bullet(
        "Check scripts/prompt/README.md for documentation on different recall rating prompt versions "
        "and their characteristics."
    )

    # =========================================================================
    # RENDER TOC (with hyperlinks)
    # =========================================================================
    pdf.render_toc(toc_page, toc_pages)

    pdf.output(OUTPUT_FILE)
    print(f"Tutorial PDF generated: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")


if __name__ == "__main__":
    build_pdf()
