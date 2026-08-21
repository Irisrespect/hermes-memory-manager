"""Hermes Memory Manager dashboard plugin — backend API routes.

Mounted at /api/plugins/hermes-memory-manager/ by the dashboard plugin system.

Purpose: list every Hermes profile's memory files (MEMORY.md / USER.md),
read them as §-delimited entries, and write edited entry lists back to disk.

The parse/serialize format matches Hermes' own ``MemoryStore`` exactly
(tools/memory_tool.py):
  - delimiter: ``ENTRY_DELIMITER = "\\n§\\n"`` (a lone § line)
  - parse: split on the delimiter, strip each entry, drop empties
  - write: ``"\\n§\\n".join(entries)`` via atomic temp-file + rename
so edits made here can never corrupt what the agent reads back.

Defensive details:
  - reads normalize CRLF → LF before splitting (a Windows-written file must
    still parse); writes always use LF so Hermes' ``_parse_entries`` works.
  - profile names are validated (no separators / ``..``), and only
    ``memories/MEMORY.md|USER.md`` under a profile home is ever touched.
  - writes are atomic (temp file + ``os.replace``), mirroring
    ``utils.atomic_write_text``.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

ENTRY_DELIMITER = "\n§\n"
MEMORY_FILES = {"memory": "MEMORY.md", "profile": "USER.md"}

# Guardrails against silly-sized payloads, not a content policy.
_MAX_ENTRIES = 10_000
_MAX_ENTRY_CHARS = 200_000


# ── profile discovery ────────────────────────────────────────────────────────


def _hermes_root() -> Path:
    """Resolve the Hermes home root, honoring HERMES_HOME then platform defaults."""
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


def _discover_profiles() -> list[dict]:
    """Return [{name, dir}] with the default profile first, then profiles/<dir>s.

    Handles both views: HERMES_HOME pointing at the hermes root (default
    profile) and pointing into profiles/<name> (a named profile's gateway).
    """
    home = _hermes_root()
    if (home / "profiles").is_dir():
        root, profiles_dir = home, home / "profiles"
    elif home.parent.name == "profiles":
        # Running under a named profile: walk back up to the hermes root.
        root, profiles_dir = home.parent.parent, home.parent
    else:
        root, profiles_dir = home, None
    names = (
        sorted(d.name for d in profiles_dir.iterdir() if d.is_dir())
        if profiles_dir is not None and profiles_dir.is_dir()
        else []
    )
    result = [{"name": "default", "dir": str(root)}]
    for name in names:
        if name == "default":
            continue  # the root home IS the default profile; avoid a duplicate
        result.append({"name": name, "dir": str(root / "profiles" / name)})
    return result


def _profile_dir(name: str) -> Path:
    """Map a profile name to its home dir, refusing path tricks."""
    if not name or name in (".", "..") or "/" in name or "\\" in name or ":" in name:
        raise HTTPException(400, f"bad profile name: {name!r}")
    for p in _discover_profiles():
        if p["name"] == name:
            return Path(p["dir"])
    raise HTTPException(404, f"unknown profile: {name!r}")


def _current_profile_name() -> str:
    """Name of the profile this process is running under.

    HERMES_HOME pointing at a named profile (``<root>/profiles/<name>``)
    means the backend serves that profile; otherwise it's the default.
    """
    home = _hermes_root()
    if home.parent.name == "profiles":
        return home.name
    return "default"


def _memory_path(profile: str, source: str) -> Path:
    """Validate source + profile and return the target memory file path."""
    if source not in MEMORY_FILES:
        raise HTTPException(400, f"source must be one of {sorted(MEMORY_FILES)}")
    return _profile_dir(profile) / "memories" / MEMORY_FILES[source]


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


@router.get("/profiles")
def list_profiles() -> dict:
    profiles = []
    for p in _discover_profiles():
        memories = Path(p["dir"]) / "memories"
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
        profiles.append(
            {"name": p["name"], "memories_dir": str(memories), "files": files}
        )
    return {"profiles": profiles}


@router.get("/profile")
def get_profile() -> dict:
    """GET /api/plugins/hermes-memory-manager/profile — current profile info.

    Single-profile shape the desktop plugin expects: {name, memories_dir,
    files:{memory:{...}, profile:{...}}}.  Profile = the one this process
    runs under (default, or the named profile HERMES_HOME points at).
    """
    name = _current_profile_name()
    p = next(x for x in _discover_profiles() if x["name"] == name)
    memories = Path(p["dir"]) / "memories"
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
def get_content(profile: Optional[str] = None, source: str = "") -> dict:
    if profile is None:
        profile = _current_profile_name()
    path = _memory_path(profile, source)
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
def put_content(profile: Optional[str] = None, source: str = "", body: ContentBody = None) -> dict:
    if profile is None:
        profile = _current_profile_name()
    path = _memory_path(profile, source)
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
