"""Deny fetches to hosts outside .claude/allowed-domains.json.

WebFetch:  the url parameter is checked directly.
WebSearch: the query is checked for defanged indicators and full URLs - looking
           an IoC up in a search engine discloses it just as a fetch would.
Bash:     only commands that can reach the network are inspected at all. Within
          such a command the ENTIRE text is scanned, heredoc bodies and quoted
          strings included. That is deliberate, not an oversight: `python3 - <<PY`
          executes its heredoc, so "it is only inside a string" is not a safe
          exemption, and this hook does not parse shell. The cost is that writing
          `curl https://example.org` inside a heredoc is denied too; write such
          examples as a fixture, or split the token.
          A defanged indicator ([.], hxxp, [://]) in a network-capable command is
          denied outright - that is a refang attempt, not a typo.

Known gaps (the permission deny rules in .claude/settings.json are the other
half of this wall): a script file that fetches on its own (`python3 fetch.py`)
is not detected, and neither is a host that never appears in the command text.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWLIST = os.path.join(HERE, "..", "allowed-domains.json")

# Commands that execute a network request with a URL in their arguments.
NETWORK_INVOCATION = re.compile(
    r"""(?:^|[;&|`(]|\$\()\s*
        (?: curl | wget | nc | ncat | netcat | telnet | ssh | scp | sftp | rsync
          | dig | nslookup | host | ping | traceroute | whois | nmap
          | openssl \s+ s_client
          | git \s+ (?: clone | fetch | pull | push | ls-remote | remote \s+ add )
          | pip3? \s+ (?:install|download)
          # -c, -m <anything>, and the bare `-` stdin form. The stdin form is
          # the one that matters: `python3 - <<PY` runs the heredoc, so treating
          # only -c as executable left an open door.
          | python3? \s+ -c | python3? \s+ -m \s+ \S+ | python3? \s+ - (?![\w-])
          | npm | npx | yarn | pnpm | bun
          | gh \b | docker \s+ (?:pull|push|login)
          | open | osascript | http | httpie | aria2c | lynx | links | w3m
        # Not \b: the `python3 -` form ends on a non-word character, and \b
        # would refuse to match it before a space.
        )(?![\w-])""",
    re.VERBOSE | re.IGNORECASE,
)

DEFANGED = re.compile(r"\[\.\]|\[:\/\/\]|hxxps?:", re.IGNORECASE)

URL_HOST = re.compile(r"[a-z][a-z0-9+.-]*://(?:[^/\s@]*@)?([^/\s:?#'\"]+)", re.IGNORECASE)
# A bare dotted token anywhere in a shell command is far more often a filename
# (AGENTS.md), an attribute (json.load), or a module path than a hostname, so
# hosts are only read out of three shapes: a scheme-qualified URL, an scp-style
# user@host: operand, and the first operand of a network command.
SCP_HOST = re.compile(
    r"(?<![\w.-])[\w.-]+@((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}):",
    re.IGNORECASE,
)

# `ssh user@host`, `curl example.org`, `ping 1.2.3.4` - a host with no scheme
# and no trailing colon, taken only from the operand position right after the
# command name (flags skipped). Most of these binaries are also denied outright
# in .claude/settings.json; this is the second half of that wall, for the ones
# that are not (rsync, sftp, aria2c, lynx, links, w3m) and for defence in depth.
_FILE_EXT = (
    r"txt|py|md|json|csv|ya?ml|sh|log|xml|html?|js|ts|toml|ini|cfg|conf|lock"
    r"|zip|gz|tar|tgz|pyc|ipynb|groovy|env|example|sample|pem|key|crt"
)
BARE_HOST = re.compile(
    rf"""(?<![\w.-])
        (?: curl | wget | nc | ncat | netcat | telnet | ssh | scp | sftp | rsync
          | dig | nslookup | host | ping | traceroute | whois | nmap
          | aria2c | lynx | links | w3m | http | httpie
          | openssl \s+ s_client          # its -connect operand is host:port
        )\s+
        (?: -{{1,2}}[\w-]+ (?:=\S+)? \s+ )*      # flags, skipped
        (?: [\w.-]+@ )?                          # optional user@
        (?P<host>
            (?: [a-z0-9](?:[a-z0-9-]*[a-z0-9])?\. )+ (?!(?:{_FILE_EXT})(?![\w-]))[a-z]{{2,24}}
          | \d{{1,3}}(?:\.\d{{1,3}}){{3}}
        )
        (?![\w.-])""",
    re.VERBOSE | re.IGNORECASE,
)


def load_allowlist():
    """Read the allowlist, or deny.

    An unreadable or empty allowlist used to raise, and a PreToolUse hook that
    exits non-zero without a decision is a *non-blocking* error: the tool call
    then goes through. That failed open on exactly the file the wall is made of,
    so a missing, malformed, or empty allowlist denies instead.
    """
    try:
        with open(ALLOWLIST) as fh:
            allow = [h.lower() for h in json.load(fh)["allow"]]
    except Exception as exc:  # missing file, bad JSON, wrong shape
        deny(
            f"Cannot read .claude/allowed-domains.json ({type(exc).__name__}): "
            f"{exc}. Fetches are deny-by-default here (AGENTS.md rule 2), so a "
            "broken allowlist denies rather than letting the call through. Fix "
            "the file, then retry."
        )
    if not allow:
        deny(
            "The 'allow' list in .claude/allowed-domains.json is empty, so no "
            "host is permitted. If that is not what you meant, fix the file."
        )
    return allow


def allowed(host, allowlist):
    host = host.strip().strip(".").lower()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    for rule in allowlist:
        if rule.startswith("*."):
            if host.endswith(rule[1:]):
                return True
        elif host == rule:
            return True
    return False


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
        sys.exit(0)  # unparseable input is not this hook's problem

    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    # The allowlist is loaded lazily, per branch: a broken allowlist must deny
    # network calls (it fails closed), but it must not brick every Bash command.

    if tool == "WebFetch":
        url = str(tool_input.get("url", ""))
        if DEFANGED.search(url):
            deny(
                "This URL is defanged, which means it came from repo data, MISP, "
                "or a report - it is a live IoC. AGENTS.md rule 2: never fetch it, "
                "and never refang it. Report it as a finding instead."
            )
        match = URL_HOST.search(url)
        host = match.group(1) if match else url
        if not allowed(host, load_allowlist()):
            deny(
                f"Host {host!r} is not in .claude/allowed-domains.json. "
                "Fetches are deny-by-default here because URLs in this repo are "
                "live IoCs (AGENTS.md rule 2). If this is a documentation lookup, "
                "ask the user to add the host to the allowlist."
            )
        sys.exit(0)

    if tool == "WebSearch":
        # A search is an outbound request too: querying an indicator hands it to
        # a search engine and tells whoever watches that engine that this lab
        # has it. Only the two shapes an IoC actually arrives in are checked -
        # defanged text and a full URL - because a bare dotted token in a search
        # query is usually just words ("docker-compose.yml", "AGENTS.md").
        query = str(tool_input.get("query", ""))
        if DEFANGED.search(query):
            deny(
                "This search query contains a defanged indicator ([.], hxxp, or "
                "[://]), so it came from repo data, MISP, or a report. Searching "
                "for a live IoC discloses it. AGENTS.md rule 2: report it as a "
                "finding, do not look it up."
            )
        bad = sorted(
            h for h in set(URL_HOST.findall(query)) if not allowed(h, load_allowlist())
        )
        if bad:
            deny(
                f"This search query carries URL(s) for host(s) not in "
                f".claude/allowed-domains.json: {', '.join(bad)}. Hosts in this "
                "repo's data are live IoCs (AGENTS.md rule 2)."
            )
        sys.exit(0)

    if tool in ("Bash", "PowerShell"):
        command = str(tool_input.get("command", ""))
        if not NETWORK_INVOCATION.search(command):
            sys.exit(0)  # not a network-capable command; nothing to check
        if DEFANGED.search(command):
            deny(
                "This command carries a defanged indicator ([.], hxxp, or [://]) "
                "into a network-capable invocation. That is a refang attempt "
                "against a live IoC. AGENTS.md rule 2 forbids it - use a synthetic "
                "fixture instead."
            )
        hosts = (
            set(URL_HOST.findall(command))
            | set(SCP_HOST.findall(command))
            | set(BARE_HOST.findall(command))
        )
        allowlist = load_allowlist()
        bad = sorted(h for h in hosts if not allowed(h, allowlist))
        if bad:
            deny(
                f"Network-capable command references host(s) not in "
                f".claude/allowed-domains.json: {', '.join(bad)}. "
                "Hosts in this repo's data are live IoCs (AGENTS.md rule 2)."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
