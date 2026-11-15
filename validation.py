"""
validation.py — can each test fail?

Stage 3 of docs/ROADMAP.md. A test that passes tells you little until you know it would
have failed on a wrong answer. This module runs a test file twice:

1. normally, to see which tests pass;
2. with every HTTP response replaced by a wrong one (see tamper_plugin.py).

Each test that passed the first time lands in one of three groups:

- validated:      it failed when the response was wrong. It checks something.
- not validating: it still passed with a wrong response. It does not check the response.
- no request:     it made no HTTP request through `requests`, so this method cannot say.

Tests that fail the normal run are listed as failing and are not assessed.

Limits, stated plainly: only tests that call the system through the `requests` library are
covered; one kind of wrong response is tried, so "validated" means "reacts to an obviously
wrong response", not "checks everything it should".

Public API:

    result = validate_tests(["tests/test_orders.py"])
    print(render_markdown(result))
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

_OUTCOME = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\s+(\S+)", re.MULTILINE)


@dataclass
class ValidationResult:
    validated: List[str] = field(default_factory=list)
    not_validating: List[str] = field(default_factory=list)
    no_request: List[str] = field(default_factory=list)
    failing: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    problem: str = ""  # set when the runs themselves could not be completed

    @property
    def assessed(self) -> int:
        return len(self.validated) + len(self.not_validating)

    @property
    def ok(self) -> bool:
        return not self.problem and not self.not_validating and not self.failing


def _run(paths: Sequence[str], extra: List[str], env: Dict[str, str], timeout: int) -> str:
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-rA", "--tb=no",
           "-p", "no:cacheprovider", *extra, *paths]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return ""
    return proc.stdout + proc.stderr


def _key(nodeid: str) -> str:
    """A test's id with its file as a real path, the same form the plugin records."""
    file, _, rest = nodeid.partition("::")
    return os.path.realpath(file) + "::" + rest


def _outcomes(output: str) -> Dict[str, str]:
    """Outcome per test. Lines without "::" are files that failed to load, not tests."""
    return {nodeid: outcome for outcome, nodeid in _OUTCOME.findall(output) if "::" in nodeid}


def validate_tests(paths: Sequence[str], timeout: int = 300) -> ValidationResult:
    """Run the tests normally and with wrong responses, and sort them by what happened."""
    result = ValidationResult()
    base_env = dict(os.environ)
    base_env.pop("ATA_TAMPER_REPORT", None)

    normal = _outcomes(_run(paths, [], base_env, timeout))
    if not normal:
        result.problem = "no tests ran: check the paths, or run pytest on them directly"
        return result

    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "requests.json"
        env = dict(base_env)
        env["ATA_TAMPER_REPORT"] = str(report)
        here = str(Path(__file__).resolve().parent)
        env["PYTHONPATH"] = here + os.pathsep + env.get("PYTHONPATH", "")
        tampered = _outcomes(_run(paths, ["-p", "tamper_plugin"], env, timeout))
        try:
            requests_made = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result.problem = "the tampered run did not complete, so nothing can be concluded"
            return result

    for nodeid, outcome in normal.items():
        if outcome in ("FAILED", "ERROR"):
            result.failing.append(nodeid)
        elif outcome != "PASSED":
            result.skipped.append(nodeid)
        elif not requests_made.get(_key(nodeid)):
            result.no_request.append(nodeid)
        elif tampered.get(nodeid) == "PASSED":
            result.not_validating.append(nodeid)
        else:
            result.validated.append(nodeid)
    return result


def render_markdown(result: ValidationResult) -> str:
    if result.problem:
        return f"# Test validation\n\nCould not be completed: {result.problem}.\n"
    lines = [
        "# Test validation",
        "",
        "Each passing test was run again with every HTTP response replaced by a wrong one.",
        "",
        f"- Validated (failed on a wrong response): {len(result.validated)}",
        f"- Not validating (still passed): {len(result.not_validating)}",
        f"- Made no HTTP request (cannot be assessed this way): {len(result.no_request)}",
        f"- Failing in the normal run (not assessed): {len(result.failing)}",
        f"- Skipped: {len(result.skipped)}",
        "",
        "\"Validated\" means the test reacts to an obviously wrong response. It does not mean",
        "the test checks everything it should.",
        "",
    ]
    for title, items in (
        ("Tests that pass even when the response is wrong", result.not_validating),
        ("Tests that made no HTTP request", result.no_request),
        ("Tests failing in the normal run", result.failing),
    ):
        if items:
            lines += [f"## {title}", ""] + [f"- `{item}`" for item in items] + [""]
    return "\n".join(lines).rstrip() + "\n"
