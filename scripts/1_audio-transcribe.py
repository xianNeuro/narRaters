#!/usr/bin/env python3
"""
Script to transcribe audio files into verbatim text with optional word-level timestamps.

Uses WhisperX (preferred, better accuracy + alignment) when available, falling back
to OpenAI Whisper. Supports wav, mp3, mp4, m4a, flac, ogg, webm, aac via ffmpeg.

Usage (from project root):
    python scripts/1_audio-transcribe.py                          # Transcribe all audio files
    python scripts/1_audio-transcribe.py --timestamps             # Also output timestamp Excel files
    python scripts/1_audio-transcribe.py --model large-v2         # Use a specific model size

Environment variables (for batch/web processing):
    BATCH_INPUT_DIR   - Input directory (overrides default)
    BATCH_OUTPUT_DIR  - Output directory (overrides default)
    BATCH_ITEM_ID     - Process only files matching this ID
    TIMESTAMPS        - Set to '1' to enable timestamp output
"""

import os
import argparse
from pathlib import Path

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# Heavy audio dependencies are optional — install with `pip install 'narraters[audio]'`.
# Defer the import so the module loads (and --help works) even when whisper/torch are absent.
try:
    import whisperx
    HAS_WHISPERX = True
except ImportError:
    HAS_WHISPERX = False

try:
    import whisper
except ImportError:
    whisper = None

try:
    import torch
except ImportError:
    torch = None

import pandas as pd


def _require_audio_deps():
    """Raise a friendly error if the optional audio dependencies are missing."""
    missing = [name for name, mod in (("whisper", whisper), ("torch", torch)) if mod is None]
    if missing:
        raise ImportError(
            "Audio transcription requires the optional [audio] extras: "
            + ", ".join(missing)
            + ". Install with: pip install 'narraters[audio]'"
        )

SUPPORTED_AUDIO_EXTENSIONS = ('.wav', '.mp3', '.mp4', '.m4a', '.flac', '.ogg', '.webm', '.aac')

DEFAULT_MODEL = 'medium' if not HAS_WHISPERX else 'large-v2'


def _get_device():
    """Select best available compute device."""
    _require_audio_deps()
    if torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def _transcribe_whisperx(audio_path, model_name, timestamps, device):
    """Transcribe using WhisperX (batched inference + wav2vec2 alignment)."""
    compute_type = 'float16' if device == 'cuda' else 'float32'

    print(f"  Loading WhisperX model: {model_name} (device={device}, compute_type={compute_type})")
    model = whisperx.load_model(model_name, device, compute_type=compute_type, language='en')

    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=16, language='en')

    full_text = ' '.join(seg['text'].strip() for seg in result['segments']).strip()

    word_timestamps = None
    if timestamps:
        print("  Running forced alignment for word-level timestamps...")
        model_a, metadata = whisperx.load_align_model(language_code='en', device=device)
        result = whisperx.align(
            result['segments'], model_a, metadata, audio, device,
            return_char_alignments=False
        )
        word_timestamps = _extract_word_timestamps(result['segments'])

    return full_text, word_timestamps


def _transcribe_whisper(audio_path, model_name, timestamps, device):
    """Transcribe using OpenAI Whisper (fallback)."""
    print(f"  Loading Whisper model: {model_name} (device={device})")
    model = whisper.load_model(model_name, device=device)

    result = model.transcribe(
        str(audio_path),
        task='transcribe',
        language='en',
        verbose=False,
        fp16=(device == 'cuda'),
        word_timestamps=timestamps
    )

    full_text = result['text'].strip()

    word_timestamps = None
    if timestamps:
        word_timestamps = _extract_word_timestamps(result.get('segments', []))

    return full_text, word_timestamps


def _extract_word_timestamps(segments):
    """Build list of {count, text, onset, offset} from segment/word data."""
    words = []
    count = 0
    for segment in segments:
        for w in segment.get('words', []):
            word_text = w.get('word', '').strip()
            if not word_text:
                continue
            count += 1
            words.append({
                'count': count,
                'text': word_text,
                'onset': round(w.get('start', 0.0), 3),
                'offset': round(w.get('end', 0.0), 3),
            })
    return words


def transcribe_audio(audio_path, model_name=None, timestamps=False):
    """
    Transcribe an audio file, optionally producing word-level timestamps.

    Args:
        audio_path: Path to the audio file
        model_name: Model size (default: 'large-v2' for WhisperX, 'medium' for Whisper)
        timestamps: If True, also return word-level timestamps

    Returns:
        (transcribed_text, word_timestamps)
        word_timestamps is None when timestamps=False, otherwise a list of dicts.
    """
    if model_name is None:
        model_name = DEFAULT_MODEL

    device = _get_device()
    engine = 'WhisperX' if HAS_WHISPERX else 'Whisper'
    print(f"Transcribing: {audio_path}  [engine={engine}, model={model_name}, timestamps={timestamps}]")

    if HAS_WHISPERX:
        return _transcribe_whisperx(audio_path, model_name, timestamps, device)
    else:
        return _transcribe_whisper(audio_path, model_name, timestamps, device)


def process_audio_files(input_dir=None, output_dir=None, model_name=None, timestamps=False):
    """
    Process all audio files in the input directory and save transcriptions.

    Args:
        input_dir:   Directory containing audio files (or from BATCH_INPUT_DIR env)
        output_dir:  Directory for output text files (or from BATCH_OUTPUT_DIR env)
        model_name:  Whisper model size (default chosen per engine)
        timestamps:  If True, additionally output Excel files with word-level timing
    """
    if input_dir is None:
        input_dir = os.environ.get('BATCH_INPUT_DIR', 'data/4_recall_audio')
    if output_dir is None:
        output_dir = os.environ.get('BATCH_OUTPUT_DIR', 'output/recall_audio-transcribed')
    if os.environ.get('TIMESTAMPS', '') == '1':
        timestamps = True

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return

    # Discover audio files
    audio_files = []
    for ext in SUPPORTED_AUDIO_EXTENSIONS:
        audio_files.extend(input_path.glob(f'*{ext}'))
    audio_files = sorted(set(audio_files))

    # Filter by BATCH_ITEM_ID if set
    batch_item_id = os.environ.get('BATCH_ITEM_ID')
    if batch_item_id:
        audio_files = [f for f in audio_files
                       if batch_item_id in f.stem or f.stem.startswith(batch_item_id)]
        if audio_files:
            print(f"Filtering by BATCH_ITEM_ID: {batch_item_id}")
        else:
            print(f"No audio files found matching BATCH_ITEM_ID: {batch_item_id}")

    # Filter by BATCH_INPUT_VARIANT if set: require stem == f"{item_id}{variant}".
    explicit_variant = os.environ.get('BATCH_INPUT_VARIANT')
    if explicit_variant is not None and batch_item_id:
        before = len(audio_files)
        target_stem = f"{batch_item_id}{explicit_variant}"
        audio_files = [f for f in audio_files if f.stem == target_stem]
        print(
            f"Filtering by BATCH_INPUT_VARIANT={explicit_variant!r}: "
            f"{before} -> {len(audio_files)} file(s)"
        )

    if not audio_files:
        ext_list = ', '.join(SUPPORTED_AUDIO_EXTENSIONS)
        suffix = f" matching {batch_item_id}" if batch_item_id else ""
        print(f"No audio files ({ext_list}) found in {input_dir}{suffix}")
        return

    engine = 'WhisperX' if HAS_WHISPERX else 'Whisper'
    effective_model = model_name or DEFAULT_MODEL
    print(f"Found {len(audio_files)} audio file(s) to transcribe")
    print(f"Engine: {engine}  |  Model: {effective_model}  |  Timestamps: {timestamps}")
    print(f"Output directory: {output_path.absolute()}\n")

    processed_count = 0

    for audio_file in audio_files:
        print(f"Processing {audio_file.name}...")

        try:
            text, word_ts = transcribe_audio(audio_file, model_name=model_name, timestamps=timestamps)

            if not text:
                print(f"  Warning: No transcription generated for {audio_file.name}")
                continue

            # Always save plain-text transcript
            txt_file = output_path / (audio_file.stem + '.txt')
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(text)

            word_count = len(text.split())
            print(f"  Transcribed: {word_count} words")
            print(f"  Saved to {txt_file}")

            # Optionally save timestamp Excel
            if timestamps and word_ts:
                ts_file = output_path / (audio_file.stem + '_timestamps.xlsx')
                df = pd.DataFrame(word_ts, columns=['count', 'text', 'onset', 'offset'])
                df.to_excel(str(ts_file), index=False)
                print(f"  Timestamps ({len(word_ts)} words) saved to {ts_file}")

            print()
            processed_count += 1

        except Exception as e:
            print(f"  Error processing {audio_file.name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"Processing complete!  {processed_count} file(s) processed.")
    print(f"Output directory: {output_path.absolute()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Transcribe audio files using WhisperX / Whisper')
    parser.add_argument('--model', default=None,
                        help=f'Model size (default: {DEFAULT_MODEL}). Options: tiny, base, small, medium, large-v2, large-v3')
    parser.add_argument('--timestamps', action='store_true',
                        help='Additionally output Excel files with word-level onset/offset timing')
    args = parser.parse_args()

    try:
        process_audio_files(model_name=args.model, timestamps=args.timestamps)
    except Exception as e:
        print(f"Error processing audio files: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
