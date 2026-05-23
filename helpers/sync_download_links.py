#!/usr/bin/env python3
"""Rewrite GitHub ZIP download URLs to match pyproject.toml version."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers.release_links import _ZIP_URL_RE, github_tag_zip_url, package_version  # noqa: E402

TARGETS = [
    ROOT / "README.md",
    ROOT / "docs/index.html",
    ROOT / "deploy/xian-li-site/narRaters/index.html",
    ROOT / "deploy/xian-li-site/tools/narRaters-full-embed.html",
    ROOT / "deploy/xian-li-site/tools/narRaters-embed.html",
    ROOT / "deploy/xian-li-site/tools/PASTE-INTO-GOOGLE-SITES.txt",
]

PYPROJECT = ROOT / "pyproject.toml"
DOWNLOAD_LINE_RE = re.compile(
    r'^Download = "https://github\.com/xianNeuro/narRaters/archive/refs/tags/v[\d.]+\.zip"$',
    re.MULTILINE,
)


def main() -> int:
    url = github_tag_zip_url()
    version = package_version()
    changed = 0

    for path in TARGETS:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new_text, n = _ZIP_URL_RE.subn(url, text)
        if n:
            path.write_text(new_text, encoding="utf-8")
            print(f"updated {n} link(s) in {path.relative_to(ROOT)}")
            changed += n

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    if 'Download = "' in pyproject:
        new_pyproject, n = DOWNLOAD_LINE_RE.subn(f'Download = "{url}"', pyproject, count=1)
    else:
        needle = '"Feedback" = "https://github.com/xianNeuro/narRaters/issues/new?template=feedback"\n'
        insert = f'{needle}Download = "{url}"\n'
        new_pyproject = pyproject.replace(needle, insert, 1)
        n = 1 if new_pyproject != pyproject else 0
    if n:
        PYPROJECT.write_text(new_pyproject, encoding="utf-8")
        print(f"updated pyproject.toml Download URL")
        changed += n

    if not changed:
        print(f"all download links already point to v{version}")
    else:
        print(f"download ZIP URL is now {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
