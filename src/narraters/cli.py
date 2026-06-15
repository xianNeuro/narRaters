"""Command-line interface for narRaters.

Exposes a single `narraters` command with subcommands for each pipeline step
plus `serve` for the web UI:

    narraters transcribe ...
    narraters segment ...
    narraters correct ...
    narraters parse ...
    narraters match ...
    narraters rate ...
    narraters serve

Phase 1 implementation: each step subcommand delegates to the legacy
scripts/N_*.py via subprocess, translating CLI flags and env vars as needed.
`serve` imports and runs the legacy Flask app in-process. Phases 2 and 3 will
migrate the actual logic into proper Python modules.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from narraters import __version__
from narraters.paths import (
    ensure_repo_on_path,
    prepare_serve_workspace,
    repo_root,
    scripts_dir,
)
from narraters.runtime_install import (
    prepare_cli_correct,
    prepare_cli_match,
    prepare_cli_parse,
    prepare_cli_rate,
    prepare_cli_segment,
    prepare_cli_transcribe,
)

# Map subcommand name → legacy script filename
_LEGACY_SCRIPTS = {
    "transcribe": "1_audio-transcribe.py",
    "segment": "2_story-event-segment.py",
    "correct": "3_spell-grammar-correct.py",
    "parse": "4_parse-texts.py",
    "match": "5_recall-rater.py",
    "rate": "6_causal-rater.py",
}


def _run_legacy_script(subcommand: str, forwarded_args: list[str], env_overrides: dict[str, str] | None = None) -> int:
    """Invoke a legacy scripts/N_*.py via subprocess and return its exit code."""
    script_name = _LEGACY_SCRIPTS[subcommand]
    script_path = scripts_dir() / script_name
    if not script_path.exists():
        print(f"narraters: legacy script not found: {script_path}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    cmd = [sys.executable, str(script_path), *forwarded_args]
    return subprocess.call(cmd, cwd=str(repo_root()), env=env)


def _add_common_io_args(p: argparse.ArgumentParser, *, include_method: bool = True, include_model: bool = True) -> None:
    """Shared --method / --model / --input / --output options."""
    if include_method:
        p.add_argument("--method", help="Processing method / backend (see step-specific choices).")
    if include_model:
        p.add_argument("--model", help="LLM model identifier for API-based methods.")
    p.add_argument("-i", "--input", help="Input file or directory path.")
    p.add_argument("-o", "--output", help="Output file or directory path.")
    p.add_argument("--prompt-version", help="Prompt template version (for LLM-based steps).")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_transcribe(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_transcribe(args, extra)
    forwarded: list[str] = []
    env: dict[str, str] = {}
    if args.model:
        forwarded += ["--model", args.model]
    if args.timestamps:
        forwarded += ["--timestamps"]
    # --kind sets the conventional default directories; explicit -i/-o override.
    if args.kind == "story":
        env["BATCH_INPUT_DIR"] = "data/1_story_audio"
        env["BATCH_OUTPUT_DIR"] = "output/story_audio-transcribed"
    elif args.kind == "recall":
        env["BATCH_INPUT_DIR"] = "data/4_recall_audio"
        env["BATCH_OUTPUT_DIR"] = "output/recall_audio-transcribed"
    if args.input:
        env["BATCH_INPUT_DIR"] = args.input
    if args.output:
        env["BATCH_OUTPUT_DIR"] = args.output
    if args.filter:
        env["BATCH_ITEM_ID"] = args.filter
    forwarded += extra
    return _run_legacy_script("transcribe", forwarded, env_overrides=env or None)


def cmd_segment(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_segment(args, extra)
    forwarded: list[str] = []
    env: dict[str, str] = {}
    if args.method:
        forwarded += ["--method", args.method]
    if args.model:
        forwarded += ["--model", args.model]
    if args.prompt_version:
        forwarded += ["--prompt-version", args.prompt_version]
    if args.input:
        # Script 2 --input expects a single file. For directories, use the
        # batch-mode env var instead so users can point at a folder of stories.
        if Path(args.input).is_dir():
            env["BATCH_INPUT_DIR"] = args.input
        else:
            forwarded += ["--input", args.input]
    if args.output:
        forwarded += ["--output", args.output]
    if args.list_prompts:
        forwarded += ["--list-prompts"]
    if args.list_models:
        forwarded += ["--list-models"]
    forwarded += extra
    return _run_legacy_script("segment", forwarded, env_overrides=env or None)


def cmd_correct(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_correct(args, extra)
    forwarded: list[str] = []
    if args.method:
        forwarded += ["--method", args.method]
    if args.input:
        forwarded += ["--input-file", args.input]
    if args.output:
        forwarded += ["--output-dir", args.output]
    if args.ollama_model:
        forwarded += ["--ollama-model", args.ollama_model]
    if args.prompt_file:
        forwarded += ["--prompt-file", args.prompt_file]
    forwarded += extra
    return _run_legacy_script("correct", forwarded)


def cmd_parse(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_parse(args, extra)
    # Script 4 reads config primarily from env vars; translate accordingly.
    env: dict[str, str] = {}
    if args.method:
        env["RECALL_PARSE_METHOD"] = args.method  # "rules" | "ollama"
    if args.model:
        env["RECALL_PARSE_OLLAMA_MODEL"] = args.model
    if args.prompt_version:
        env["RECALL_PARSE_PROMPT"] = args.prompt_version
    if args.input:
        env["BATCH_INPUT_DIR"] = args.input
    if args.output:
        env["BATCH_OUTPUT_DIR"] = args.output

    forwarded = list(extra)
    if args.filter_pattern:
        forwarded.append(args.filter_pattern)
    return _run_legacy_script("parse", forwarded, env_overrides=env)


def cmd_match(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_match(args, extra)
    # Script 5 is env-driven.
    env: dict[str, str] = {}
    test_mode = bool(args.test_mode)
    if args.method:
        m = args.method.lower()
        if m == "test":
            test_mode = True
        elif m in ("ollama", "gemma-ollama", "gemma"):
            env["RECALL_RATING_BACKEND"] = "ollama"
        elif m == "rmatch":
            env["RECALL_RATING_BACKEND"] = "rmatch"
        elif m in ("api", "anthropic", "openai"):
            env["RECALL_RATING_BACKEND"] = "api"
    if args.input:
        env["BATCH_INPUT_DIR"] = args.input
    if args.output:
        env["BATCH_OUTPUT_DIR"] = args.output
    if args.story_events:
        env["BATCH_STORY_EVENTS_DIR"] = args.story_events
    if test_mode:
        env["TEST_MODE"] = "1"
    return _run_legacy_script("match", list(extra), env_overrides=env)


def cmd_rate(args: argparse.Namespace, extra: list[str]) -> int:
    prepare_cli_rate(args, extra)
    forwarded: list[str] = []
    env: dict[str, str] = {}
    if args.method:
        forwarded += ["--method", args.method]
    if args.model:
        forwarded += ["--model", args.model]
    if args.prompt_version:
        forwarded += ["--prompt-version", args.prompt_version]
    if args.input:
        # Script 6 --input expects a single events file. Use BATCH_INPUT_DIR
        # for directory mode so a folder of stories can be processed.
        if Path(args.input).is_dir():
            env["BATCH_INPUT_DIR"] = args.input
        else:
            forwarded += ["--input", args.input]
    if args.output:
        forwarded += ["--output", args.output]
    forwarded += extra
    return _run_legacy_script("rate", forwarded, env_overrides=env or None)


def cmd_serve(args: argparse.Namespace, extra: list[str]) -> int:
    """Launch the Flask web UI in-process."""
    import importlib.util

    ensure_repo_on_path()
    seeded = prepare_serve_workspace()
    if seeded is not None:
        print(f"Copied bundled example data/ and output/ into {seeded}")
    server_script = repo_root() / "server" / "web-interface.py"
    if not server_script.exists():
        print(f"narraters: server script not found: {server_script}", file=sys.stderr)
        return 2

    # Load server/web-interface.py as a module (its filename has a hyphen so
    # we can't use a regular import statement).
    spec = importlib.util.spec_from_file_location("narraters._legacy_server", server_script)
    if spec is None or spec.loader is None:
        print("narraters: failed to load server module", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "app"):
        print("narraters: server module did not expose a Flask `app`", file=sys.stderr)
        return 2

    # Default to loopback. The UI runs subprocesses on the user's behalf and
    # has open file-write endpoints — binding to 0.0.0.0 by default would
    # expose those to anyone on the local network. Users who genuinely need
    # LAN access can pass --host 0.0.0.0 (warning is printed below).
    host = args.host or "127.0.0.1"
    port = args.port or 5000
    debug = args.debug or (os.environ.get("FLASK_DEBUG", "0") == "1")

    if host not in ("127.0.0.1", "localhost"):
        print(
            f"⚠️  Binding to {host} — the web UI will be reachable from other "
            "machines on this network. Only do this on a trusted network.",
            file=sys.stderr,
        )

    production = getattr(args, "production", False)

    if not args.no_browser and not production:
        _open_browser_when_ready(host, port)

    browse_host = _loopback_browser_host(host)
    if not production:
        print(f"narRaters web UI starting on http://{browse_host}:{port}/pipeline-config")
    print(f"Project root for data/ and output/ paths: {module.WORKSPACE_ROOT}")
    if not (module.WORKSPACE_ROOT / "data").is_dir() and not (module.WORKSPACE_ROOT / "output").is_dir():
        print(
            "Note: no data/ or output/ folder here. cd into your project directory before "
            "'narraters serve', or set NARRATERS_PROJECT_ROOT to that folder.",
            file=sys.stderr,
        )

    if production:
        # Production hosting: serve via Waitress (a real WSGI server) instead of
        # Flask's single-threaded dev server. Intended to sit behind a Caddy
        # reverse proxy that terminates TLS. See HOSTING.md and `init-service`.
        try:
            from waitress import serve as waitress_serve
        except ImportError:
            print(
                "narraters: --production needs waitress. Install it with "
                "'pip install \"narraters[deploy]\"'.",
                file=sys.stderr,
            )
            return 2
        print(f"narRaters (waitress) serving on http://{host}:{port} — proxy TLS in front of this.")
        waitress_serve(module.app, host=host, port=port, threads=8)
        return 0

    module.app.run(host=host, port=port, debug=debug, use_reloader=False)
    return 0


def _loopback_browser_host(host: str) -> str:
    """Use IPv4 loopback in URLs when the server binds to loopback (avoids localhost → ::1 on macOS)."""
    if host in ("127.0.0.1", "localhost", "::1"):
        return "127.0.0.1"
    return host


def _open_browser_when_ready(host: str, port: int) -> None:
    """Open the default browser to the local server, in a background thread."""
    import threading
    import time
    import webbrowser

    def opener() -> None:
        time.sleep(1.0)
        url = f"http://{_loopback_browser_host(host)}:{port}/pipeline-config"
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=opener, daemon=True).start()


def _detect_narraters_bin() -> str:
    """Best guess for the installed `narraters` console script (for ExecStart)."""
    candidate = Path(sys.executable).with_name("narraters")
    if candidate.exists():
        return str(candidate)
    import shutil

    return shutil.which("narraters") or "narraters"


def cmd_init_service(args: argparse.Namespace, extra: list[str]) -> int:
    """Generate a systemd unit + Caddyfile for hosting narRaters on a VPS."""
    import getpass

    from narraters.deploy import DeployConfig, write_configs

    workdir = Path(args.workdir).expanduser().resolve() if args.workdir else Path.cwd().resolve()
    # Default the output directory to the workspace, not the current directory:
    # init-service is typically run as a dedicated service user (e.g. via
    # `sudo -u narraters`) whose cwd may be a directory it cannot write to.
    # The workspace is owned by that user, so it is always writable.
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workdir
    user = args.user or getpass.getuser()
    narraters_bin = args.narraters_bin or _detect_narraters_bin()

    config = DeployConfig(
        domain=args.domain,
        workdir=str(workdir),
        user=user,
        host=args.host,
        port=args.port,
        narraters_bin=narraters_bin,
    )
    service_path, caddyfile_path = write_configs(config, output_dir)

    print(f"Wrote {service_path}")
    print(f"Wrote {caddyfile_path}")
    print()
    print("Next steps (run on the VPS):")
    print("  1. Install the systemd service:")
    print(f"       sudo cp {service_path} /etc/systemd/system/narraters.service")
    print("       sudo systemctl daemon-reload")
    print("       sudo systemctl enable --now narraters")
    print("       systemctl status narraters")
    print("  2. Install the Caddy & the config (path varies by distro):")
    print(f"       sudo cp {caddyfile_path} /etc/caddy/Caddyfile   # or import it from your main Caddyfile")
    print("       sudo systemctl reload caddy")
    print(f"  3. Point a DNS A record for {args.domain} at this server, then browse")
    print(f"       https://{args.domain}/pipeline-config")
    print()
    print("⚠  narRaters has no built-in auth yet and can execute code. Do not leave it")
    print("   publicly reachable unprotected — uncomment the basic_auth block in the")
    print("   Caddyfile, or restrict access by IP/VPN, until app-level auth is added.")
    print("   See HOSTING.md for the full walkthrough.")
    return 0


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ensure_repo_on_path()
    try:
        from helpers.feedback_links import FEEDBACK_ISSUE_URL
    except ImportError:
        FEEDBACK_ISSUE_URL = "https://github.com/xianNeuro/narRaters/issues/new?template=feedback"

    parser = argparse.ArgumentParser(
        prog="narraters",
        description=(
            "narRaters — AI-assisted narrative processing with human-screening. "
            "Run `narraters serve` for the web UI, or use the "
            "per-step subcommands for scripted pipelines.\n\n"
            f"Feedback and suggestions: {FEEDBACK_ISSUE_URL}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"narRaters {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    # transcribe
    p_t = sub.add_parser("transcribe", help="Step 1: Transcribe story or recall audio to text (WhisperX/Whisper).")
    p_t.add_argument("--model", help="Whisper model name (e.g. tiny, base, small, medium, large-v2, large-v3).")
    p_t.add_argument("--timestamps", action="store_true", help="Also write Excel files with word-level timestamps.")
    p_t.add_argument(
        "--kind",
        choices=["recall", "story"],
        default="recall",
        help="Which audio set to transcribe. recall=data/4_recall_audio (default), "
        "story=data/1_story_audio. Sets the conventional input/output directories.",
    )
    p_t.add_argument("-i", "--input", help="Input audio directory (overrides the --kind default).")
    p_t.add_argument("-o", "--output", help="Output directory (overrides the --kind default).")
    p_t.add_argument("--filter", help="Only transcribe files whose name matches this item id.")
    p_t.set_defaults(func=cmd_transcribe)

    # segment — matches scripts/2_story-event-segment.py VALID_METHODS
    p_s = sub.add_parser("segment", help="Step 2: Segment story transcripts into events.")
    p_s.add_argument(
        "--method",
        choices=["clause", "fine", "coarse", "api"],
        help="Segmentation method (clause=heuristic, fine/coarse=spaCy, api=LLM).",
    )
    _add_common_io_args(p_s, include_method=False)
    p_s.add_argument("--list-prompts", action="store_true", help="List available prompt versions and exit.")
    p_s.add_argument("--list-models", action="store_true", help="List supported models and exit.")
    p_s.set_defaults(func=cmd_segment)

    # correct — matches scripts/3_spell-grammar-correct.py choices
    p_c = sub.add_parser("correct", help="Step 3: Spell/grammar correction of raw recall text.")
    p_c.add_argument("--method", choices=["rules", "gemma-ollama"], help="Correction method.")
    p_c.add_argument("--ollama-model", help="Ollama model tag for --method gemma-ollama (default: gemma4:e4b).")
    p_c.add_argument("--prompt-file", help="Instructions file for --method gemma-ollama.")
    p_c.add_argument("-i", "--input", help="Single recall .txt file to process.")
    p_c.add_argument("-o", "--output", help="Output directory.")
    p_c.set_defaults(func=cmd_correct)

    # parse — script 4 reads RECALL_PARSE_METHOD env var; valid values: rules | ollama
    p_p = sub.add_parser("parse", help="Step 4: Parse corrected recall text into segments.")
    p_p.add_argument(
        "--method",
        choices=["rules", "ollama"],
        help="Parsing method (rules=regex heuristics, ollama=local Gemma via Ollama).",
    )
    _add_common_io_args(p_p, include_method=False)
    p_p.add_argument("--filter-pattern", nargs="?", help="Optional substring to filter recall files by.")
    p_p.set_defaults(func=cmd_parse)

    # match — script 5 reads RECALL_RATING_BACKEND env var; valid backends: api | gemma-ollama | rmatch
    p_m = sub.add_parser("match", help="Step 5: Match recall segments to story events.")
    p_m.add_argument(
        "--method",
        choices=["api", "gemma-ollama", "rmatch", "test"],
        help="Matching backend (api=Anthropic Messages API, gemma-ollama=local Gemma, rmatch=embedding match, test=simulated/no API).",
    )
    _add_common_io_args(p_m, include_method=False, include_model=False)
    p_m.add_argument("--story-events", help="Directory containing story event Excel files (default: data/3_story_events).")
    p_m.add_argument("--test-mode", action="store_true", help="Run in simulated/test mode (no API calls). Equivalent to --method test.")
    p_m.set_defaults(func=cmd_match)

    # rate — matches scripts/6_causal-rater.py VALID_METHODS
    p_r = sub.add_parser("rate", help="Step 6: Rate causal relationships between event pairs.")
    p_r.add_argument(
        "--method",
        choices=["linguistic", "api", "manual"],
        help="Rating method (linguistic=regex/spaCy heuristics, api=LLM, manual=write empty scaffold for hand rating).",
    )
    _add_common_io_args(p_r, include_method=False)
    p_r.set_defaults(func=cmd_rate)

    # serve
    p_serve = sub.add_parser("serve", help="Launch the web UI (Flask) for interactive review and editing.")
    p_serve.add_argument("--host", default=None, help="Bind address (default: 127.0.0.1, loopback only). Pass 0.0.0.0 to allow LAN access — only on a trusted network.")
    p_serve.add_argument("--port", type=int, default=None, help="Bind port (default: 5000).")
    p_serve.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    p_serve.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser on startup.")
    p_serve.add_argument(
        "--production",
        action="store_true",
        help="Serve via Waitress (production WSGI) instead of the Flask dev server. "
        "Install with 'narraters[deploy]'. Intended to run behind a TLS-terminating "
        "reverse proxy (see HOSTING.md).",
    )
    p_serve.set_defaults(func=cmd_serve)

    # init-service — generate systemd + Caddy config for VPS hosting
    p_init = sub.add_parser(
        "init-service",
        help="Generate a systemd unit + Caddyfile for hosting narRaters on a VPS (see HOSTING.md).",
    )
    p_init.add_argument("--domain", required=True, help="Public domain name to serve (e.g. narraters.example.com).")
    p_init.add_argument("--workdir", default=None, help="Workspace dir containing data/ and output/ (default: current directory).")
    p_init.add_argument("--user", default=None, help="System user the service runs as (default: current login user).")
    p_init.add_argument("--host", default="127.0.0.1", help="Loopback bind address for the app (default: 127.0.0.1).")
    p_init.add_argument("--port", type=int, default=5000, help="Port the app binds to behind the proxy (default: 5000).")
    p_init.add_argument("--narraters-bin", default=None, help="Path to the 'narraters' executable used in ExecStart (default: auto-detected next to the running interpreter).")
    p_init.add_argument("--output-dir", default=None, help="Where to write narraters.service and Caddyfile (default: the --workdir).")
    p_init.set_defaults(func=cmd_init_service)

    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_repo_on_path()
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    try:
        return args.func(args, extra)
    except (subprocess.CalledProcessError, RuntimeError) as e:
        print(f"narraters: dependency setup failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
