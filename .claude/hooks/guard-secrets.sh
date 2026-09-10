#!/bin/bash
# PreToolUse / Bash - deny reading a secret through a subprocess.
#
# Read/Edit deny rules cover Claude's file tools and the file commands Claude
# Code recognises in Bash (cat, head, tail, sed) plus redirect targets. They do
# NOT cover "arbitrary subprocesses that read files indirectly, like a Python or
# Node script that opens files itself" - which is exactly how shared/hunt.py
# reads shared/authkey.txt. This hook closes that gap.
#
# AGENTS.md rule 3: assert on a secret's existence, never on its value.
exec python3 "$(dirname "$0")/guard_secrets.py"
