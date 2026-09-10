"""Deny Bash commands that read or overwrite a secret through a subprocess.

Existence checks are allowed - AGENTS.md rule 3 says to assert on existence,
never on value - so `ls`, `test -f`, `stat`, `find`, and `git check-ignore` pass
even when they name the file.

Two things this deliberately does NOT do:

* It does not require the reader to be the first word of the command. It used to,
  and `docker compose exec x cat /shared/authkey.txt`, `timeout 5 cat ...`,
  `xargs cat`, and `find ... -exec cat ...` all walked straight through.
* It does not treat a grep-family PATTERN operand as a path. `grep -rn .env
  AGENTS.md` searches *for* the string in a file that is not a secret; denying
  that made ordinary documentation work impossible. File operands after the
  pattern are still scanned, so `grep -n MISP shared/.env` is still denied.

The backstop for what no command-text matcher can see - `grep -r . shared/`,
a script that opens the file itself - is the sandbox credential deny-list in
.claude/settings.json, which refuses the read at the OS level.
"""
import json
import re
import shlex
import sys

# .env.example is tracked and non-secret; it is deliberately not matched here.
SECRET = re.compile(
    r"""authkey\.txt
      | (?<![\w.-])\.env(?![\w.-])
      | (?<![\w.-])\.env\.local(?![\w.-])""",
    re.VERBOSE | re.IGNORECASE,
)

# Anything that can surface file *contents*. Matched anywhere in the command,
# not only at a command boundary: the reader is often not the first word.
READS_CONTENT = re.compile(
    r"""(?<![\w.-])
        (?: cat | head | tail | sed | awk | less | more | nl | tac | rev
          | xxd | od | strings | base64 | hexdump | cut | tr | sort | uniq
          | cp | mv | scp | rsync | tar | zip | gzip | install | dd | tee
          | cmp | bat | jq | yq | paste | fold | split | expand
          | python3? | perl | ruby | node | php | osascript
          | source | eval
          | grep | rg | ag | ripgrep | diff | vim | vi | nano | emacs | open
        )(?![\w.-])
      | <\s*\S*(?:authkey\.txt|\.env)   # input redirection from the secret
      | \$\(<""",
    re.VERBOSE | re.IGNORECASE,
)

# Clobbering a secret is not a read, but it destroys the lab just as thoroughly:
# authkey.txt is what every containerised run authenticates with.
WRITES_SECRET = re.compile(
    r""">>?\s*['"]?\S*(?:authkey\.txt|\.env)(?![\w.-])
      | \bof=\S*(?:authkey\.txt|\.env)(?![\w.-])""",
    re.VERBOSE | re.IGNORECASE,
)

GREP_CMDS = {"grep", "egrep", "fgrep", "rg", "ripgrep", "ag", "ack"}

# Short flags that take NO argument, so the operand after them is the pattern.
# Anything outside this set - `-e PATTERN`, `-f FILE`, `-m NUM`, `-A2`, `-g GLOB`,
# `--include=...` - means the next operand may be something else entirely, and
# `grep -f shared/authkey.txt notes.md` reads the secret just as surely as `cat`
# does. Unknown flag => drop nothing => the secret is seen => denied.
SAFE_SHORT_FLAGS = set("rRnilLcwxvHhqsaIoEFPUz")
SAFE_LONG_FLAGS = {
    "--recursive", "--line-number", "--ignore-case", "--invert-match",
    "--files-with-matches", "--files-without-match", "--count", "--word-regexp",
    "--line-regexp", "--fixed-strings", "--extended-regexp", "--perl-regexp",
    "--with-filename", "--no-filename", "--quiet", "--silent", "--text",
    "--hidden", "--no-ignore", "--color", "--colour", "--only-matching",
}


def _is_argumentless_flag(token):
    if token.startswith("--"):
        return token.split("=")[0] in SAFE_LONG_FLAGS and "=" not in token
    return len(token) > 1 and set(token[1:]) <= SAFE_SHORT_FLAGS


def strip_grep_patterns(command):
    """Return the command text with grep-family PATTERN operands removed.

    `grep -rn .env AGENTS.md` searches *for* a string in a file that is not a
    secret, and denying that made ordinary documentation work impossible. Only
    the plain `grep [flags] PATTERN [files...]` shape is recognised, and only
    when every flag is known to take no argument - anything else keeps the whole
    command under scrutiny.

    Best effort: if the command does not tokenise (unbalanced quotes), it is
    returned unchanged, which errs towards denying.
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return command

    kept, i = [], 0
    while i < len(tokens):
        token = tokens[i]
        kept.append(token)
        i += 1
        if token.split("/")[-1] not in GREP_CMDS:
            continue
        while i < len(tokens) and tokens[i].startswith("-"):
            if not _is_argumentless_flag(tokens[i]):
                break  # this flag may own the next operand: drop nothing
            kept.append(tokens[i])
            i += 1
        else:
            if i < len(tokens):
                i += 1  # positional pattern: drop it
    return " ".join(kept)


def deny(reason):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def main():
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if event.get("tool_name") not in ("Bash", "PowerShell"):
        sys.exit(0)

    command = str((event.get("tool_input") or {}).get("command", ""))

    if WRITES_SECRET.search(command):
        deny(
            "This command would overwrite a secret (shared/authkey.txt holds the "
            "MISP admin API key; .env files hold LLM, MISP, and SIEM "
            "credentials). authkey.txt is regenerated by `sudo make dev`, not by "
            "hand - if it really needs to change, hand the command to the user."
        )

    scan = strip_grep_patterns(command)
    if not SECRET.search(scan):
        sys.exit(0)
    if not READS_CONTENT.search(command):
        sys.exit(0)  # existence check (ls, test, stat, find, git check-ignore)

    deny(
        "This command would read the contents of a secret "
        "(shared/authkey.txt holds the MISP admin API key; .env files "
        "hold LLM, MISP, and SIEM credentials). AGENTS.md rule 3: "
        "assert on their existence, never on their value. Use "
        "`test -f`, `ls`, or `git check-ignore -v` instead."
    )


if __name__ == "__main__":
    main()
