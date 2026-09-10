#!/bin/bash
# PreToolUse / Bash|WebFetch - deny any fetch whose host is not in
# .claude/allowed-domains.json.
#
# Why a hook and not a permission rule: permissions can allow a set of domains,
# but cannot express "and deny every other one". AGENTS.md rule 2 says the URLs,
# IPs, and FQDNs in this repo are live malicious indicators, so the default has
# to be deny, not prompt.
#
# Reads the tool call as JSON on stdin, writes a PreToolUse decision on stdout.
exec python3 "$(dirname "$0")/guard_network.py"
