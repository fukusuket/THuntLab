#!/bin/bash
# SessionStart - report the working-tree state of both repositories.
#
# CLAUDE.md used to ask the agent to run this by hand. When the submodule has
# tracked modifications, its committed AGENTS.md can describe code that is not
# what is checked out - worth knowing before the first edit, not after.
#
# The drift warning is driven by TRACKED changes only: an untracked
# __pycache__/*.pyc is noise, and warning on it cried wolf every session.
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# The hook payload arrives on stdin; read it before the heredoc below takes over.
payload=$(cat)
source_kind=$(printf '%s' "$payload" |
  python3 -c "import json,sys
try:
    print((json.load(sys.stdin) or {}).get('source', ''))
except Exception:
    print('')" 2>/dev/null)

# require_check's state lives on disk, so a session that ended mid-edit would
# make the NEXT session owe a `make check` it never triggered. Clear it on a
# real start only - a compact is the same session and still owes its gate.
case "$source_kind" in
  startup|clear) "$(dirname "$0")/require-check.sh" reset ;;
esac

root=$(git status --short 2>/dev/null)
sub=$(git -C shared/threatfeed-collector status --short 2>/dev/null)
sub_tracked=$(git -C shared/threatfeed-collector status --short --untracked-files=no 2>/dev/null)
ptr=$(git submodule status 2>/dev/null)

python3 - "$root" "$sub" "$sub_tracked" "$ptr" <<'PY'
import json, sys
root, sub, sub_tracked, ptr = (a.strip() for a in sys.argv[1:5])
lines = ["Working tree at session start:", "",
         "Root repo (git status --short):", root or "  clean", "",
         "Submodule shared/threatfeed-collector (git status --short):",
         sub or "  clean", "",
         "Submodule pointer (git submodule status):", ptr or "  n/a"]
if sub_tracked:
    lines += ["", "The submodule has uncommitted changes to tracked files. Its "
              "committed AGENTS.md may describe code that differs from what is "
              "checked out - check before trusting either. Its test suite is "
              "otherwise expected green (71 passed); a failure is real."]
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "\n".join(lines)}}))
PY
