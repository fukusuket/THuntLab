"""Block ending a turn that edited files without running `make check`.

`mark-checked` fires on both success and failure of `make check`: the gate is
"you ran it", not "it passed". CLAUDE.md already requires quoting the real
output, and touching only on success would trap a red run in a loop.

`verify` blocks at most once per dirty state. A Stop hook that can never be
satisfied is worse than the mistake it prevents, so after warning once it lets
the turn end - by then Claude has been told, and the user can see it.

`reset` clears the state files. The state lives on disk, so a session that ended
dirty used to block the first turn of the *next* session, which had edited
nothing. session-start.sh calls this on a fresh start (never on a compact, which
would drop a gate the current session still owes).
"""
import json
import os
import pathlib
import re
import sys

PROJECT = pathlib.Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()
STATE = PROJECT / ".claude" / ".state"
DIRTY, CHECKED, WARNED = STATE / "dirty", STATE / "checked", STATE / "warned"


def touch(path):
    STATE.mkdir(parents=True, exist_ok=True)
    path.touch()


def mtime(path):
    return path.stat().st_mtime if path.exists() else 0.0


def edits_the_project():
    """True when the edited file lives inside the repository.

    An edit to a scratchpad file or anything else outside the project cannot
    change what `make check` verifies, and demanding the gate for it turned an
    honest guard into noise.
    """
    if "CLAUDE_PROJECT_DIR" not in os.environ:
        return True  # cannot tell where the project is: assume it mattered
    try:
        path = str((json.load(sys.stdin).get("tool_input") or {}).get("file_path", ""))
    except (json.JSONDecodeError, ValueError, AttributeError):
        return True  # unreadable payload: assume it mattered
    if not path:
        return True
    try:
        return PROJECT in pathlib.Path(path).resolve().parents
    except OSError:
        return True


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "verify"

    if action == "reset":
        for path in (DIRTY, CHECKED, WARNED):
            path.unlink(missing_ok=True)
    elif action == "mark-dirty":
        if edits_the_project():
            touch(DIRTY)
    elif action == "mark-checked":
        # Match the command here rather than relying on a hook `if:` filter, so
        # a filter that does not apply cannot silently mark every Bash call as
        # a passing gate and neuter the Stop check.
        try:
            command = str((json.load(sys.stdin).get("tool_input") or {}).get("command", ""))
        except (json.JSONDecodeError, ValueError, AttributeError):
            return
        # The separator class must include newlines: a multi-line command such as
        # `cd <repo>\nmake check | tail` is the normal shape, and missing it made
        # the gate silently un-recordable - a false negative that blocks a turn
        # whose check actually passed.
        # `check`, not `check-tier0` or `check-submodule`: the gate is Tier 0 +
        # Tier 1 together, and \b happily matched the hyphenated targets, so
        # running Tier 0 alone used to satisfy it.
        if re.search(r"(?:^|[;&|`(\n\r]|\$\()\s*make\s+check(?![\w-])", command, re.MULTILINE):
            touch(CHECKED)
    elif action == "verify":
        dirty = mtime(DIRTY)
        if not dirty:
            return  # read-only turn: nothing to verify, never misfire
        if mtime(CHECKED) > dirty or mtime(WARNED) > dirty:
            return  # gate ran after the last edit, or we already said this once
        touch(WARNED)
        print(
            "You edited files this session but have not run `make check` since "
            "the last edit. That is the gate (AGENTS.md §3): Tier 0 + Tier 1, "
            "offline, one exit code. Run it and quote the real output before "
            "reporting - a change is not done because it was written.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
