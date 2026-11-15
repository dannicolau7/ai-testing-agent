"""Journeys: a requirement carried out in the page, then checked in the backend.

Runs a real browser against the demo site. Skipped where Playwright or a browser is not
installed; the `browser` CI job installs both and fails if these are skipped.
"""

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import browser_audit
import journeys

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "browser-demo"

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def site():
    spec = importlib.util.spec_from_file_location("journey_demo_server", DEMO / "server.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    server = demo.make_server()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        browser_audit.browse(url + "/api/_calls", max_pages=1)
    except browser_audit.BrowserUnavailable as exc:
        server.shutdown()
        pytest.skip(str(exc))
    yield url, demo
    server.shutdown()
    server.server_close()


def test_the_file_is_read_and_mistakes_in_it_are_named():
    loaded, problems = journeys.load((DEMO / "journeys.yaml").read_text())
    assert problems == [] and [j.id for j in loaded] == ["REQ-1", "REQ-2", "REQ-3"]
    first = loaded[0]
    assert first.steps[0] == ("open", "/notes") and first.steps[1] == ("fill", {"field": "Title", "value": "Buy milk"})
    assert first.page_must_call == ("POST", "/api/notes") and (first.backend_get, first.backend_contains) == ("/api/notes", "Buy milk")
    loaded, problems = journeys.load(
        "journeys:\n"
        "  - {id: A, steps: [{click: Save}]}\n"
        "  - {id: B, steps: [{open: /x}, {hover: y}]}\n"
        "  - {id: C, steps: [{open: /x}, {fill: {field: T}}]}\n"
        "  - {id: D, steps: [{open: /x}], page_must_call: save it}\n"
        "  - {id: E, steps: [{open: /x}], backend_must_show: {get: /y}}\n"
        "  - {id: F}\n"
        "  - {id: G, steps: [{open: /x}, {see: 5}]}\n")
    assert [j.id for j in loaded] == ["G"]
    assert [p.split(":")[0] for p in problems] == ["A", "B", "C", "D", "E", "F"]
    assert "the first step must open a page" in problems[0]
    assert journeys.load("journeys: [")[1][0].startswith("not valid YAML")
    assert journeys.load("nothing: 1")[1] == ["the file needs a `journeys` list"]


def test_a_working_journey_passes_all_three_checks(site):
    url, demo = site
    loaded, _ = journeys.load((DEMO / "journeys.yaml").read_text())
    result = journeys.run(loaded[:1], url)[0]
    assert result.outcome == "passed", result.detail
    assert ("POST", "/api/notes", 201) in result.calls
    assert "Buy milk" in demo.notes, "the journey really saved it"


def test_a_page_that_says_saved_while_the_backend_stored_nothing_is_caught(site):
    url, demo = site
    loaded, _ = journeys.load((DEMO / "journeys.yaml").read_text())
    rename, archive = journeys.run(loaded[1:], url)
    # The page shows the new title and the server answered 200, but nothing was stored.
    assert (rename.outcome, rename.failed_at) == ("failed", "backend")
    assert "The frontend and the backend disagree" in rename.detail and "Renamed note" not in demo.notes
    # The page says "Archived" although the server answered 404.
    assert (archive.outcome, archive.failed_at) == ("failed", "page_call")
    assert "the server answered 404, while the page went on as if it had worked" in archive.detail

    text = journeys.render_markdown([rename, archive], [], url)
    assert text.splitlines()[4] == "**2 of 2 journeys failed.**"
    assert "| REQ-2 | ok | ok | FAILED |" in text and "| REQ-3 | ok | FAILED | not asked |" in text


def test_steps_that_cannot_be_carried_out_fail_with_the_reason(site):
    url, _ = site
    loaded, problems = journeys.load(
        "journeys:\n"
        "  - {id: NO-FIELD, steps: [{open: /notes}, {fill: {field: Colour, value: red}}]}\n"
        "  - {id: NO-BUTTON, steps: [{open: /notes}, {click: Publish}]}\n"
        "  - {id: NO-TEXT, steps: [{open: /notes}, {see: Nothing like this}]}\n"
        "  - {id: NO-PAGE, steps: [{open: /nowhere}]}\n"
        "  - {id: UNWANTED, steps: [{open: /notes}, {not_see: First note}]}\n"
        "  - {id: NEVER-SENT, steps: [{open: /notes}], page_must_call: DELETE /api/notes/5}\n"
        "  - {id: GONE, steps: [{open: /notes}, {see: First note}], backend_must_show: {get: /api/notes, not_contains: First note}}\n")
    assert problems == []
    results = {r.journey.id: r for r in journeys.run(loaded, url, timeout_ms=2500)}
    assert all(r.outcome == "failed" for r in results.values())
    assert "no field called “Colour”" in results["NO-FIELD"].detail
    assert "nothing to click called “Publish”" in results["NO-BUTTON"].detail
    assert "does not show “Nothing like this”" in results["NO-TEXT"].detail
    assert "answered 404" in results["NO-PAGE"].detail
    assert "which it must not" in results["UNWANTED"].detail
    assert results["NEVER-SENT"].failed_at == "page_call" and "never sent DELETE /api/notes/5" in results["NEVER-SENT"].detail
    assert results["GONE"].failed_at == "backend" and "still contains" in results["GONE"].detail


def test_command_line(site, tmp_path):
    url, _ = site
    out = tmp_path / "journeys.md"
    env = dict(os.environ, AI_AGENT_TELEMETRY="false")
    run = subprocess.run([sys.executable, "cli.py", "journey", str(DEMO / "journeys.yaml"), "--url", url, "-o", str(out)],
                         capture_output=True, text=True, cwd=str(HERE), env=env)
    assert run.returncode == 1, run.stdout + run.stderr
    assert "**2 of 3 journeys failed.**" in out.read_text()
    one = tmp_path / "one.yaml"
    one.write_text("journeys:\n  - {id: OK, steps: [{open: /notes}, {see: Notes}]}\n")
    assert subprocess.run([sys.executable, "cli.py", "journey", str(one), "--url", url], capture_output=True,
                          text=True, cwd=str(HERE), env=env).returncode == 0
    bad = tmp_path / "bad.yaml"
    bad.write_text("journeys:\n  - {id: X}\n")
    for args in ([str(bad), "--url", url], [str(tmp_path / "missing.yaml"), "--url", url]):
        assert subprocess.run([sys.executable, "cli.py", "journey"] + args, capture_output=True, text=True,
                              cwd=str(HERE), env=env).returncode == 2
