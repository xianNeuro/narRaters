"""User accounts: storage, password hashing, and verification.

Centralizes the account logic so both the web app (``server/web-interface.py``)
and the CLI (``narraters users ...``) share one implementation without the CLI
having to import the large Flask server module.

Storage: a single JSON file at ``~/.narraters/users.json`` (override the parent
with ``NARRATERS_DATA_DIR``), owner-only ``0600`` permissions. Each record is::

    {"<username>": {"password_hash": "<hash>", "created": "<iso8601>"}}

Hashing uses Werkzeug's ``generate_password_hash`` / ``check_password_hash``
(scrypt by default in Werkzeug 3.1+). Pre-existing records that stored a bare
hash string, the older custom ``pbkdf2_sha256$...`` format, or a legacy bare
SHA-256 digest are still accepted by :func:`verify_password`; the next
successful login upgrades them in place to the current Werkzeug format.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


def sanitize_username(raw: str) -> str:
    """Collapse a name to a filesystem/regex-safe token (``\\w`` only, max 32).

    A username doubles as a directory name and filename prefix under
    ``benchmark/rated/<user>/``, so it must contain no path separators or other
    special characters. Returns '' if nothing usable remains.
    """
    token = re.sub(r"\W+", "_", (raw or "").strip()).strip("_")
    return token[:32]


def is_safe_username(raw: str) -> bool:
    """True iff ``raw`` is already safe (equals its sanitized form, non-empty)."""
    clean = sanitize_username(raw)
    return bool(clean) and clean == (raw or "").strip()


def account_data_dir() -> Path:
    """Directory holding ``users.json`` (``NARRATERS_DATA_DIR`` or ``~/.narraters``)."""
    override = (os.environ.get("NARRATERS_DATA_DIR") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".narraters"


def users_file() -> Path:
    return account_data_dir() / "users.json"


def load_users() -> dict:
    """Load the users dict; returns {} if the file is missing or unreadable."""
    path = users_file()
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error loading users file: {e}")
            return {}
    return {}


def save_users(users: dict) -> bool:
    """Write the users dict with owner-only permissions."""
    try:
        d = account_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = users_file()
        with open(path, "w") as f:
            json.dump(users, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except Exception as e:
        print(f"Error saving users file: {e}")
        import traceback
        traceback.print_exc()
        return False


# --- Password hashing -------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password for storage (Werkzeug default: scrypt)."""
    return generate_password_hash(password)


def _is_legacy_sha256_hash(stored) -> bool:
    return (
        isinstance(stored, str)
        and len(stored) == 64
        and all(c in "0123456789abcdef" for c in stored.lower())
    )


def verify_password(password: str, stored) -> bool:
    """Verify ``password`` against a stored hash of any supported format.

    Accepts current Werkzeug hashes (``scrypt:``/``pbkdf2:``), the older custom
    ``pbkdf2_sha256$<iters>$<salt>$<hash>`` format, and legacy bare SHA-256
    digests. Returns False for anything unrecognized or empty.
    """
    if not stored or not isinstance(stored, str):
        return False
    # Older custom format from before the Werkzeug switch.
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _algo, iters_str, salt_hex, hash_hex = stored.split("$", 3)
            derived = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters_str)
            )
            return secrets.compare_digest(derived.hex(), hash_hex)
        except Exception:
            return False
    if _is_legacy_sha256_hash(stored):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, stored)
    # Current Werkzeug formats.
    try:
        return check_password_hash(stored, password)
    except Exception:
        return False


def _is_current_hash(stored) -> bool:
    """True if ``stored`` is already in the current Werkzeug format."""
    return isinstance(stored, str) and (
        stored.startswith("scrypt:") or stored.startswith("pbkdf2:")
    )


# --- Record helpers ---------------------------------------------------------

def _stored_hash(record) -> str | None:
    """Extract the password hash from a record (dict or bare string)."""
    if isinstance(record, dict):
        return record.get("password_hash") or record.get("password")
    if isinstance(record, str):
        return record
    return None


def user_exists(username: str) -> bool:
    return username in load_users()


def list_users() -> list[str]:
    return sorted(load_users().keys())


def add_user(username: str, password: str, *, overwrite: bool = False) -> bool:
    """Create (or, with ``overwrite``, replace) an account. Returns False if it
    already exists and ``overwrite`` is False."""
    users = load_users()
    if username in users and not overwrite:
        return False
    users[username] = {
        "password_hash": hash_password(password),
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    return save_users(users)


def set_password(username: str, password: str) -> bool:
    """Change an existing user's password. Returns False if the user is unknown."""
    users = load_users()
    if username not in users:
        return False
    record = users[username]
    if not isinstance(record, dict):
        record = {}
    record["password_hash"] = hash_password(password)
    users[username] = record
    return save_users(users)


def remove_user(username: str) -> bool:
    """Delete an account. Returns False if the user is unknown."""
    users = load_users()
    if username not in users:
        return False
    del users[username]
    return save_users(users)


# --- Benchmark pass state ----------------------------------------------------
#
# In `narraters serve --benchmark` each rater is locked to one pass at a time:
# pass 1 (matching) by default, pass 2 (rating) once an admin enables it with
# `narraters users second-pass <name>` (`narraters users first-pass <name>`
# switches back). Kept in its own JSON file (not users.json) so it also covers
# local no-login raters, whose name is the OS username and has no account.

def passes_file() -> Path:
    return account_data_dir() / "benchmark_passes.json"


def _load_passes() -> dict:
    path = passes_file()
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error loading benchmark passes file: {e}")
            return {}
    return {}


def get_benchmark_pass(username: str) -> int:
    """Which benchmark pass ``username`` is locked to: 1 (default) or 2."""
    try:
        return 2 if int(_load_passes().get(username, 1)) == 2 else 1
    except (TypeError, ValueError):
        return 1


def set_benchmark_pass(username: str, pass_no: int) -> bool:
    """Lock ``username`` to benchmark pass 1 or 2."""
    if pass_no not in (1, 2):
        raise ValueError(f"pass_no must be 1 or 2, got {pass_no!r}")
    passes = _load_passes()
    passes[username] = pass_no
    try:
        d = account_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(passes_file(), "w") as f:
            json.dump(passes, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving benchmark passes file: {e}")
        return False


# --- Benchmark batch visibility ------------------------------------------------
#
# In `narraters serve --benchmark` the items are grouped into hardcoded batches
# (see BENCHMARK_BATCHES in server/web-interface.py). The admin shows/hides
# batches per rater from the admin page. Stored as {username: {batch: bool}};
# batches with no stored entry fall back to the server's default (only the
# first batch visible). Same rationale as benchmark_passes.json for living in
# its own file: it also covers local no-login raters without an account.

def batches_file() -> Path:
    return account_data_dir() / "benchmark_batches.json"


def _load_batch_visibility() -> dict:
    path = batches_file()
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error loading benchmark batches file: {e}")
            return {}
    return {}


def get_batch_visibility(username: str) -> dict:
    """Explicit per-batch visibility overrides for ``username``: {batch: bool}.
    Batches absent from the dict have no override (server default applies)."""
    record = _load_batch_visibility().get(username, {})
    if not isinstance(record, dict):
        return {}
    return {str(k): bool(v) for k, v in record.items()}


def set_batch_visible(username: str, batch: str, visible: bool) -> bool:
    """Show or hide one benchmark batch for ``username``."""
    data = _load_batch_visibility()
    record = data.get(username)
    if not isinstance(record, dict):
        record = {}
    record[batch] = bool(visible)
    data[username] = record
    try:
        d = account_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        with open(batches_file(), "w") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving benchmark batches file: {e}")
        return False


def verify_user(username: str, password: str) -> bool:
    """Verify credentials, upgrading a legacy hash in place on success."""
    users = load_users()
    record = users.get(username)
    stored = _stored_hash(record)
    if not stored or not verify_password(password, stored):
        return False
    # Upgrade older hash formats to the current one after a successful login.
    if not _is_current_hash(stored):
        try:
            set_password(username, password)
        except Exception:
            pass
    return True
