"""Canonical GitHub download links for narRaters releases."""
from __future__ import annotations

import re
from pathlib import Path

GITHUB_REPO = "xianNeuro/narRaters"
_ZIP_URL_RE = re.compile(
    rf"https://github\.com/{re.escape(GITHUB_REPO)}/archive/refs/(?:heads/main|tags/v[\d.]+)\.zip"
)


def package_version() -> str:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not read version from pyproject.toml")
    return match.group(1)


def github_tag_zip_url(version: str | None = None) -> str:
    ver = version or package_version()
    return f"https://github.com/{GITHUB_REPO}/archive/refs/tags/v{ver}.zip"
