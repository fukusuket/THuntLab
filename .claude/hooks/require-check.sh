#!/bin/bash
# Tracks whether `make check` ran after the last edit.
#
#   mark-dirty    PostToolUse / Edit|Write|NotebookEdit (project files only)
#   mark-checked  PostToolUse + PostToolUseFailure / Bash, if: Bash(make check*)
#   verify        Stop - exit 2 if files were edited and the gate never ran
#   reset         SessionStart - drop state left behind by a previous session
#
# AGENTS.md anti-pattern: "Report success after editing but before running."
# CLAUDE.md: run `make check` after your last edit, not before.
exec python3 "$(dirname "$0")/require_check.py" "$1"
