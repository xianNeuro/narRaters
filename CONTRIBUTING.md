# Research background

Citations below motivate or validate **automated** approaches similar to the optional narRaters methods (numbered to match the [pipeline overview](README.md#pipeline-overview)). Your study still needs design-appropriate evaluation.

**Step 1 — `audioTranscribe`** &nbsp;No paper cited; validation is Whisper/WhisperX accuracy on your audio plus manual spot checks.

**Step 2 — `eventSegment`** &nbsp;Michelmann, Kumar, **Norman**, & Toneva, *Large language models can segment narrative events similarly to humans*: GPT-3 zero-shot boundaries correlate with human segmentations and approximate crowd consensus — useful precedent for LLM-based story segmentation. [arXiv:2301.10297](https://arxiv.org/abs/2301.10297), [Behavior Research Methods (2025)](https://doi.org/10.3758/s13428-024-02569-z), [code](https://github.com/s-michelmann/GPT_event_segmentation).

**Step 3 — `sentenceCorrect`** &nbsp;No external benchmark; the package enforces minimal, non-paraphrasing edits.

**Step 4 — `textParsing`** &nbsp;Clause-level structure is checked against the same independent-clause logic as `eventSegment`.

**Step 5 — `textMatching`**
- Toneva et al., *Memory for long narratives* (Princeton Computational Memory Lab, 2021; with **K. A. Norman**): long-form novel recall scored by aligning recalled events to chapter events with GPT-2 representations. [PDF](https://compmem.princeton.edu/wp/wp-content/uploads/2022/05/memory-for-long-narratives.pdf).
- **rMatch** — Kressin Palacios & Arekar: embedding-based recall-to-event matching with human-data validation. [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch).

**Step 6 — `causalRating`** &nbsp;Li et al., *Agency personalizes episodic memories* (PsyArXiv, 2024): behavioral work with choose-your-own-adventure narratives examining how agency shapes memory for branching event sequences — aligned with event-wise materials for which pairwise causal ratings are meaningful. [DOI:10.31234/osf.io/7evwj](https://doi.org/10.31234/osf.io/7evwj).

## Prompt templates

LLM-backed methods load text from **`scripts/prompt/`** (you can add versions or override paths; see [`scripts/prompt/README.md`](scripts/prompt/README.md)). Bundled templates:

| File | Step | Used by |
|---|---|---|
| `event_segment.txt` | 2 — segment | `--method api` |
| `spell_gram.txt` | 3 — correct | `--method gemma-ollama` |
| `recall_parse_clause.txt` | 4 — parse | `--method ollama` |
| `recall_rating.txt` | 5 — match | `--method api`, `--method gemma-ollama` |
| `causal_rating.txt` | 6 — rate | `--method api` |

You can:

- **Browse available versions** with `narraters <step> --list-prompts`
- **Select a version** with `--prompt-version <name>`
- **Override the file directly** for Step 3 with `--prompt-file path/to/prompt.txt`
- **Add your own** by dropping a new `.txt` into `scripts/prompt/` — it's picked up automatically

---

## Acknowledgements

- **Janice Chen** for brainstorming the causal-rating step interface and for help testing and improving package functionality.
- **Gabi Kressin Palacios** and **Dhruva Arekar** for an additional method for the recall-matching step (matching human recall text to story events). See [GabrielKP/rMatch](https://github.com/GabrielKP/rMatch) for human-data–validated AI-assisted recall rating.
- **Xiyu Li (Rita)** for contributions to the `recall_rating` prompt development and for validating model performance on human recall data (commercial LLM APIs were close to human raters).
- **Sebastian Michelmann** for feedback on the event-segmentation step (see [Michelmann et al., 2023](https://arxiv.org/abs/2301.10297)).
- **Colette Youstra** and **Quinton Covington** for testing the app's manual-rating functions.
- **Samira Tavassoli** and **Yuye Huang** for help testing the app's segmentation and causal-reasoning functions.

## Author

**Xian Li** — [xianl.cogneuro@gmail.com](mailto:xianl.cogneuro@gmail.com)
