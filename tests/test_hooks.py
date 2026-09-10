"""Tests for the agent guard hooks in .claude/hooks/.

These hooks are the walls that .claude/settings.json cannot express: a
deny-by-default network allowlist, a secret-read guard that survives a
subprocess, and the Stop-hook gate that demands `make check` after an edit.
Nothing verified them before, so a syntax error or a regex slip disabled a wall
silently while `make check` stayed green.

Offline and hermetic: every case is a synthetic hook payload. No IoC, no
network, no real secret is read - only command *strings* naming those paths.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / ".claude" / "hooks"

ALLOW = "allow"
DENY = "deny"


def run_hook(script, event, args=(), env=None):
    """Run a hook with `event` on stdin; return (decision, returncode, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(HOOKS / script), *args],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
    )
    decision = ALLOW
    if proc.stdout.strip():
        payload = json.loads(proc.stdout)
        decision = payload["hookSpecificOutput"]["permissionDecision"]
    return decision, proc.returncode, proc.stderr


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def web(url):
    return {"tool_name": "WebFetch", "tool_input": {"url": url}}


def search(query):
    return {"tool_name": "WebSearch", "tool_input": {"query": query}}


# --------------------------------------------------------------------------
# guard_network.py
# --------------------------------------------------------------------------

NETWORK_CASES = [
    # (expected decision, event, why)
    (ALLOW, web("https://docs.claude.com/en/docs"), "allowlisted documentation host"),
    (DENY, web("https://evil.example.org/x"), "host not on the allowlist"),
    (DENY, web("hxxp://bad[.]com"), "defanged URL is an IoC, never fetch it"),
    (ALLOW, bash("make check"), "not a network-capable command"),
    (ALLOW, bash("git ls-remote https://github.com/foo/bar"), "allowlisted host"),
    (DENY, bash("curl https://evil.example.org"), "scheme-qualified host, not allowed"),
    (DENY, bash("curl evil.example.org"), "bare host operand"),
    (DENY, bash("ssh user@evil.example.org 'ls'"), "user@host with no trailing colon"),
    (DENY, bash("ping 8.8.8.8"), "bare IP operand"),
    (
        DENY,
        bash("python3 - <<'PY'\nimport urllib.request\nurllib.request.urlopen('https://evil.example.org')\nPY"),
        "`python3 -` executes its heredoc",
    ),
    (DENY, bash("python3 -m urllib.request https://evil.example.org"), "-m any module"),
    (ALLOW, bash("grep -rn 'http://schemas.xmlsoap.org/x' jobs/"), "grep is not a fetch"),
    (ALLOW, bash("echo 'see https://docs.claude.com' > note.md"), "echo is not a fetch"),
    (ALLOW, bash("python3 -m pytest tests/ -q"), "no host in the command"),
    (ALLOW, bash("python3 -m py_compile shared/hunt.py"), "no host in the command"),
    (ALLOW, bash("scp report.txt backup.txt"), "file names are not hosts"),
    (ALLOW, bash("rsync -a src/ dst/"), "local paths are not hosts"),
    (ALLOW, bash("hostname"), "substring of a network command name"),
    (ALLOW, bash("openssl version"), "not the s_client subcommand"),
    (DENY, bash("openssl s_client -connect evil.example.org:443"), "host:port operand"),
    (DENY, bash("nc evil.example.org 443"), "host as a bare operand"),
    (DENY, bash("pip install --index-url https://evil.example.org/simple foo"), "index URL"),
    (DENY, bash("git clone https://evil.example.org/repo"), "clone from an IoC host"),
    # A search is an outbound request too.
    (DENY, search("what is bad[.]com"), "defanged indicator in a search query"),
    (DENY, search("https://evil.example.org malware"), "IoC URL in a search query"),
    (ALLOW, search("streamlit glob docker-compose.yml"), "ordinary words with dots"),
    (ALLOW, search("pymisp add_event https://github.com/MISP/PyMISP"), "allowlisted"),
]


@pytest.mark.parametrize(
    "expected,event,why",
    NETWORK_CASES,
    ids=[f"{e}-{w}" for e, _, w in NETWORK_CASES],
)
def test_guard_network(expected, event, why):
    decision, rc, stderr = run_hook("guard_network.py", event)
    assert rc == 0, stderr
    assert decision == expected, why


def test_guard_network_denies_when_allowlist_is_unreadable(tmp_path, monkeypatch):
    """A broken allowlist must fail closed.

    A PreToolUse hook that exits non-zero without a decision is a non-blocking
    error - the tool call goes through. Raising on a missing allowlist therefore
    opened the wall instead of closing it.
    """
    broken = tmp_path / "guard_network.py"
    source = (HOOKS / "guard_network.py").read_text()
    broken.write_text(source.replace("allowed-domains.json", "no-such-file.json"))

    proc = subprocess.run(
        [sys.executable, str(broken)],
        input=json.dumps(web("https://evil.example.org")),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == DENY


# --------------------------------------------------------------------------
# guard_secrets.py
# --------------------------------------------------------------------------

SECRET_CASES = [
    (DENY, bash("cat shared/authkey.txt"), "plain read"),
    (DENY, bash("awk '{print}' shared/authkey.txt"), "reader that is not cat"),
    (DENY, bash("while read l; do echo $l; done < shared/authkey.txt"), "redirection"),
    (DENY, bash("docker compose exec x cat /shared/authkey.txt"), "reader mid-command"),
    (DENY, bash("timeout 5 cat shared/authkey.txt"), "reader behind a wrapper"),
    (DENY, bash("find . -name x -exec cat shared/authkey.txt {} \\;"), "reader in -exec"),
    (DENY, bash("dd if=shared/authkey.txt of=/tmp/x"), "dd reads it too"),
    (DENY, bash("grep -n MISP shared/.env"), "secret as a file operand"),
    (DENY, bash("echo leaked > shared/.env"), "clobbering a secret"),
    (DENY, bash("cat shared/.env >> notes.md"), "read into another file"),
    (ALLOW, bash("test -f shared/authkey.txt && echo ok"), "existence check"),
    (ALLOW, bash("ls -l shared/authkey.txt"), "existence check"),
    (ALLOW, bash("git check-ignore -v shared/.env"), "ignore check"),
    (ALLOW, bash("grep -rn .env AGENTS.md"), "secret name as the search pattern"),
    (ALLOW, bash("grep -rn 'authkey.txt' .claude/rules/"), "search pattern, quoted"),
    (ALLOW, bash("rg -n .env --glob '*.md'"), "ripgrep pattern"),
    (ALLOW, bash("grep --color -rn .env docs/"), "long flag that takes no argument"),
    # ...but only the plain `grep [argumentless flags] PATTERN [files]` shape is
    # exempt. A flag that owns the next operand can point it at the secret.
    (DENY, bash("grep -f shared/authkey.txt notes.md"), "-f reads patterns FROM the file"),
    (DENY, bash("grep --file=shared/authkey.txt notes.md"), "--file= reads the file"),
    (DENY, bash("rg -f shared/.env notes.md"), "ripgrep -f reads the file"),
    (DENY, bash("grep -eMISP shared/.env"), "attached -e, so the operand is a file"),
    (DENY, bash("grep -m 5 KEY shared/authkey.txt"), "-m takes a number, not the pattern"),
    (DENY, bash("grep -A2 KEY shared/authkey.txt"), "-A2 is not argumentless"),
    (DENY, bash("grep -- -x shared/authkey.txt"), "end-of-flags marker"),
    (ALLOW, bash("python3 shared/hunt.py"), "the script reads it, the command does not"),
    (ALLOW, bash("sed -n '1,5p' shared/.env.example"), ".env.example is tracked"),
    (ALLOW, bash("make check"), "the gate"),
]


@pytest.mark.parametrize(
    "expected,event,why",
    SECRET_CASES,
    ids=[f"{e}-{w}" for e, _, w in SECRET_CASES],
)
def test_guard_secrets(expected, event, why):
    decision, rc, stderr = run_hook("guard_secrets.py", event)
    assert rc == 0, stderr
    assert decision == expected, why


# --------------------------------------------------------------------------
# require_check.py
# --------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    """A throwaway CLAUDE_PROJECT_DIR so the real .claude/.state is untouched."""
    import os

    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))

    def call(action, event=None):
        proc = subprocess.run(
            [sys.executable, str(HOOKS / "require_check.py"), action],
            input=json.dumps(event or {}),
            capture_output=True,
            text=True,
            env=env,
        )
        return proc.returncode

    call.dir = tmp_path
    return call


def edit_of(path):
    return {"tool_input": {"file_path": str(path)}}


def ran(command):
    return {"tool_input": {"command": command}}


def test_read_only_turn_is_never_blocked(project):
    assert project("verify") == 0


def test_edit_without_the_gate_blocks_the_turn(project):
    assert project("mark-dirty", edit_of(project.dir / "shared" / "hunt.py")) == 0
    assert project("verify") == 2


def test_it_warns_only_once_per_dirty_state(project):
    project("mark-dirty", edit_of(project.dir / "a.py"))
    assert project("verify") == 2
    assert project("verify") == 0, "a Stop hook that can never be satisfied is worse"


def test_the_gate_clears_the_block(project):
    project("mark-dirty", edit_of(project.dir / "a.py"))
    project("mark-checked", ran("cd /repo && make check"))
    assert project("verify") == 0


def test_tier0_alone_does_not_satisfy_the_gate(project):
    project("mark-dirty", edit_of(project.dir / "a.py"))
    project("mark-checked", ran("make check-tier0"))
    assert project("verify") == 2, "the gate is Tier 0 + Tier 1 together"


def test_merely_mentioning_the_gate_does_not_satisfy_it(project):
    project("mark-dirty", edit_of(project.dir / "a.py"))
    project("mark-checked", ran('echo "run make check later"'))
    assert project("verify") == 2


def test_edits_outside_the_project_do_not_demand_the_gate(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("scratchpad") / "note.md"
    assert project("mark-dirty", edit_of(outside)) == 0
    assert project("verify") == 0


def test_reset_drops_state_from_a_previous_session(project):
    project("mark-dirty", edit_of(project.dir / "a.py"))
    project("reset")
    assert project("verify") == 0
