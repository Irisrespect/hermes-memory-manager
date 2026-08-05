"""Hermes Memory Manager dashboard plugin — backend API routes.

Mounted at /api/plugins/hermes-memory-manager/ by the dashboard plugin system.

Purpose: let the user view and edit the memory files of the profile the
gateway is CURRENTLY running under — MEMORY.md (agent memory) and USER.md
(profile memory), edited one §-delimited entry at a time.

Design notes:
  - The plugin is profile-scoped by construction: the gateway process's
    ``HERMES_HOME`` determines the current profile, and every route touches
    only that profile's ``memories/`` dir. There is no profile parameter to
    pass, so there is nothing to escalate.
  - The parse/serialize format matches Hermes' own ``MemoryStore`` exactly
    (tools/memory_tool.py): delimiter ``"\\n§\\n"``, parse = split + strip +
    drop empties, write = ``"\\n§\\n".join(entries)`` via atomic temp-file +
    rename. Reads normalize CRLF → LF first; writes always use LF.
  - No local-machine assumptions: profile names come from the filesystem,
    the hermes root from HERMES_HOME (falling back to the platform default),
    and only ``memories/MEMORY.md|USER.md`` is ever touched.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

ENTRY_DELIMITER = "\n§\n"
MEMORY_FILES = {"memory": "MEMORY.md", "profile": "USER.md"}

# Guardrails against silly-sized payloads, not a content policy.
_MAX_ENTRIES = 10_000
_MAX_ENTRY_CHARS = 200_000


# ── profile / path resolution ────────────────────────────────────────────────


def _hermes_root() -> Path:
    """Resolve the current profile's home, honoring HERMES_HOME then platform defaults."""
    home = os.environ.get("HERMES_HOME")
    if home:
        p = Path(home).expanduser()
        if p.is_dir():
            return p
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            p = Path(local) / "hermes"
            if p.is_dir():
                return p
    return Path.home() / ".hermes"


def _current_profile() -> str:
    """Name of the profile this gateway runs under ('default' or the profiles/<dir> name)."""
    home = _hermes_root()
    if home.parent.name == "profiles":
        return home.name
    return "default"


def _memory_path(source: str) -> Path:
    """Validate source and return the target memory file path (current profile only)."""
    if source == "memory":
        fname = "MEMORY.md"
    elif source == "profile":
        fname = "USER.md"
    else:
        raise HTTPException(400, f"source must be one of {sorted(MEMORY_FILES)}")
    return _hermes_root() / "memories" / fname


# ── entry parsing (lockstep with MemoryStore) ────────────────────────────────


def _parse_entries(raw: str) -> list[str]:
    """Split raw memory-file text into stripped, non-empty entries."""
    raw = raw.replace("\r\n", "\n")  # tolerate Windows line endings
    if not raw.strip():
        return []
    return [e.strip() for e in raw.split(ENTRY_DELIMITER) if e]


def _entry_count(path: Path) -> int:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    return len(_parse_entries(raw))


# ── routes ───────────────────────────────────────────────────────────────────


@router.get("/profile")
def get_profile() -> dict:
    """Current profile + the status of its two memory files."""
    name = _current_profile()
    memories = _hermes_root() / "memories"
    files = {}
    for source, fname in MEMORY_FILES.items():
        f = memories / fname
        if f.is_file():
            try:
                st = f.stat()
                files[source] = {
                    "exists": True,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "entry_count": _entry_count(f),
                }
            except OSError:
                files[source] = {"exists": False}
        else:
            files[source] = {"exists": False}
    return {"name": name, "memories_dir": str(memories), "files": files}


@router.get("/content")
def get_content(source: str) -> dict:
    path = _memory_path(source)
    if not path.is_file():
        return {"exists": False, "entries": [], "mtime": None}
    try:
        st = path.stat()
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            500, f"{path.name} is not valid UTF-8 — refusing to edit"
        ) from None
    except OSError as e:
        raise HTTPException(500, f"failed to read {path}: {e}") from e
    return {
        "exists": True,
        "entries": _parse_entries(raw),
        "mtime": st.st_mtime,
    }


class ContentBody(BaseModel):
    entries: list


@router.put("/content")
def put_content(source: str, body: ContentBody) -> dict:
    path = _memory_path(source)
    if len(body.entries) > _MAX_ENTRIES:
        raise HTTPException(
            400, f"too many entries ({len(body.entries)} > {_MAX_ENTRIES})"
        )
    cleaned: list[str] = []
    for e in body.entries:
        if not isinstance(e, str):
            raise HTTPException(400, "entries must be strings")
        s = e.strip()
        if len(s) > _MAX_ENTRY_CHARS:
            raise HTTPException(
                400, f"entry too long ({len(s)} > {_MAX_ENTRY_CHARS} chars)"
            )
        if s:
            cleaned.append(s)
    content = ENTRY_DELIMITER.join(cleaned)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".mem_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
    except OSError as e:
        raise HTTPException(500, f"failed to write {path}: {e}") from e
    try:
        st = path.stat()
    except OSError as e:
        raise HTTPException(500, f"failed to stat {path}: {e}") from e
    return {"ok": True, "entry_count": len(cleaned), "mtime": st.st_mtime}
