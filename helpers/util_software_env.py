"""Load ``software/.env`` (KEY=value) without overriding existing environment variables."""
from __future__ import annotations

import os
from pathlib import Path


def load_software_dotenv(software_root: Path) -> None:
    p = software_root / ".env"
    if not p.is_file():
        return
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
