"""Backend self-test for hermes-memory-manager dashboard plugin (v2: current-profile scope).

Builds a fake Hermes home in a temp dir, exercises the API functions directly
(no HTTP layer), and cross-checks round-trip compatibility against Hermes'
own MemoryStore parser.

v2 scope: every route touches ONLY the profile the process is running under
(derived from HERMES_HOME) — there is no profile parameter at all.
"""

import importlib
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERMES_AGENT = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "hermes-agent"
DASHBOARD = Path(__file__).parent / "dashboard"
sys.path.insert(0, str(HERMES_AGENT))
sys.path.insert(0, str(DASHBOARD))

from fastapi import HTTPException  # noqa: E402

plugin_api = importlib.import_module("plugin_api")
memory_tool = importlib.import_module("tools.memory_tool")
MemoryStore = memory_tool.MemoryStore

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


def expect_http(name: str, code: int, fn, *args):
    try:
        fn(*args)
    except HTTPException as e:
        check(name, e.status_code == code, f"got {e.status_code}, want {code}")
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"raised {type(e).__name__}: {e}")
        return
    check(name, False, "no HTTPException raised")


def build_fake_home(root: Path):
    """Default-profile memory file + a named profile with its own files."""
    (root / "memories").mkdir()
    (root / "profiles" / "p1" / "memories").mkdir(parents=True)
    (root / "memories" / "MEMORY.md").write_text(
        "默认条目一\n§\n默认条目二\n", encoding="utf-8"
    )
    (root / "memories" / "USER.md").write_text("默认用户 A", encoding="utf-8")
    (root / "profiles" / "p1" / "memories" / "MEMORY.md").write_text(
        "P1 条目一\n§\nP1 条目二\n§\nP1 条目三", encoding="utf-8"
    )
    # CRLF file: parser must still split correctly.
    (root / "profiles" / "p1" / "memories" / "USER.md").write_bytes(
        "CRLF 用户一条\r\n§\r\nCRLF 用户两条".encode()
    )


def main():
    root = Path(tempfile.mkdtemp(prefix="memmgr_test_"))
    try:
        build_fake_home(root)

        print("== current-profile resolution ==")
        os.environ["HERMES_HOME"] = str(root)
        check("default view → 'default'", plugin_api._current_profile() == "default")

        os.environ["HERMES_HOME"] = str(root / "profiles" / "p1")
        check("named view → 'p1'", plugin_api._current_profile() == "p1")

        print("== GET /profile (current profile only) ==")
        os.environ["HERMES_HOME"] = str(root)
        data = plugin_api.get_profile()
        check("name", data["name"] == "default")
        check(
            "memory exists, 2 entries",
            data["files"]["memory"]["entry_count"] == 2,
            str(data["files"]["memory"]),
        )
        check("user exists, 1 entry", data["files"]["profile"]["entry_count"] == 1)

        os.environ["HERMES_HOME"] = str(root / "profiles" / "p1")
        data1 = plugin_api.get_profile()
        check("p1 name", data1["name"] == "p1")
        check(
            "p1 memory 3 entries",
            data1["files"]["memory"]["entry_count"] == 3,
            str(data1["files"]["memory"]),
        )
        check(
            "p1 memories_dir",
            data1["memories_dir"] == str(root / "profiles" / "p1" / "memories"),
        )

        print("== GET /content (no profile param; current profile only) ==")
        got = plugin_api.get_content("memory")
        check(
            "p1 memory entries",
            got["entries"] == ["P1 条目一", "P1 条目二", "P1 条目三"],
            str(got["entries"]),
        )
        got_crlf = plugin_api.get_content("profile")
        check(
            "CRLF user parses",
            got_crlf["entries"] == ["CRLF 用户一条", "CRLF 用户两条"],
            str(got_crlf["entries"]),
        )
        # Under p1, the DEFAULT profile's files must NOT be reachable.
        root_user = root / "memories" / "USER.md"
        check(
            "default user untouched",
            root_user.read_text(encoding="utf-8") == "默认用户 A",
        )

        print("== PUT /content ==")
        res = plugin_api.put_content(
            "profile", plugin_api.ContentBody(entries=[" 新用户一 ", "", "新用户二"])
        )
        check("put ok", res["ok"] and res["entry_count"] == 2)
        raw = (root / "profiles" / "p1" / "memories" / "USER.md").read_text(
            encoding="utf-8"
        )
        check("file is LF §-joined", raw == "新用户一\n§\n新用户二", repr(raw))
        got2 = plugin_api.get_content("profile")
        check("read-back", got2["entries"] == ["新用户一", "新用户二"])

        print("== MemoryStore round-trip (agent compat) ==")
        ms_entries = MemoryStore._read_file(
            root / "profiles" / "p1" / "memories" / "USER.md"
        )
        check(
            "MemoryStore parses our file",
            ms_entries == ["新用户一", "新用户二"],
            str(ms_entries),
        )

        print("== missing file → create on save ==")
        (root / "profiles" / "p2").mkdir(parents=True)
        os.environ["HERMES_HOME"] = str(root / "profiles" / "p2")
        missing = plugin_api.get_content("memory")
        check(
            "missing → exists=false", not missing["exists"] and missing["entries"] == []
        )
        res2 = plugin_api.put_content(
            "memory", plugin_api.ContentBody(entries=["全新条目"])
        )
        check("create ok", res2["ok"] and res2["entry_count"] == 1)
        check(
            "created under p2",
            (root / "profiles" / "p2" / "memories" / "MEMORY.md").read_text(
                encoding="utf-8"
            )
            == "全新条目",
        )

        print("== validation ==")
        expect_http("bad source", 400, plugin_api.get_content, "bad")
        expect_http(
            "non-string entry",
            400,
            plugin_api.put_content,
            "memory",
            plugin_api.ContentBody(entries=[123]),
        )
        expect_http(
            "too many entries",
            400,
            plugin_api.put_content,
            "memory",
            plugin_api.ContentBody(entries=["x"] * 10_001),
        )

        print(f"\n{PASS} passed, {FAIL} failed")
        sys.exit(1 if FAIL else 0)
    finally:
        os.environ.pop("HERMES_HOME", None)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
