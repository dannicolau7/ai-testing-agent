"""The frontend half of the automation suite, run in a real browser against the demo site.

Skipped where Playwright or a browser is not installed; the `browser` CI job installs both and
fails if these are skipped.
"""

import importlib.util
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

import automation
import browser_audit
import journeys

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "browser-demo"

pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def site():
    spec = importlib.util.spec_from_file_location("automation_demo_server", DEMO / "server.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    server = demo.make_server()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        seen = browser_audit.browse(url)
    except browser_audit.BrowserUnavailable as exc:
        server.shutdown()
        pytest.skip(str(exc))
    yield url, seen
    server.shutdown()
    server.server_close()


def _run(folder, url, **env):
    base = {k: v for k, v in os.environ.items() if not k.startswith("AUTOMATION_")}
    base["AUTOMATION_BASE_URL"] = url
    if os.environ.get("ATA_BROWSER_PATH"):
        base["AUTOMATION_BROWSER_PATH"] = os.environ["ATA_BROWSER_PATH"]
    base.update(env)
    done = subprocess.run([sys.executable, "-m", "pytest", str(folder), "-q", "-p", "no:cacheprovider", "--tb=line",
                           "-o", "addopts=", "-rs"], capture_output=True, text=True, env=base, cwd=str(folder.parent))
    return done.stdout


def test_pages_and_journeys_become_tests_that_catch_the_planted_problems(site, tmp_path):
    url, seen = site
    loaded, problems = journeys.load((DEMO / "journeys.yaml").read_text())
    assert not problems
    suite = automation.generate(None, None, observation=seen, journeys=loaded, app_name="demo")
    assert suite.pages >= 4 and suite.journeys == len(loaded) == 3
    assert {"ui/pages.json", "ui/test_pages.py", "ui/journeys.json", "ui/test_journeys.py"} <= set(suite.files)
    out = tmp_path / "automation"
    automation.write(suite, out)

    # Journeys save and delete, so they wait for permission. Pages are read-only and run.
    result = _run(out, url)
    assert "3 skipped" in result and "set AUTOMATION_ALLOW_WRITES=1" in result, result
    # The demo site has planted problems: a page that throws, and a page whose request fails.
    assert "failed" in result and ("threw:" in result or "made request(s) that failed" in result), result
    assert "passed" in result, "the healthy pages pass"

    result = _run(out, url, AUTOMATION_ALLOW_WRITES="1")
    # One journey works. Two catch a page that claims success the backend does not bear out.
    assert "does not contain “Renamed note”. The frontend and the backend disagree" in result, result
    assert "the server answered 404, while the page went on as if it had worked" in result, result
    assert "/help threw:" in result and "/reports made request(s) that failed" in result
    assert "4 failed" in result and "skipped" not in result, result


def test_a_page_that_is_gone_fails_and_no_answer_is_a_skip(site, tmp_path):
    url, seen = site
    suite = automation.generate(None, None, observation=seen, app_name="demo")
    out = tmp_path / "automation"
    automation.write(suite, out)
    pages = out / "ui" / "pages.json"
    pages.write_text('{"pages": [{"path": "/no-such-page"}]}')
    result = _run(out, url)
    assert "1 failed" in result and "/no-such-page answered 404" in result, result
    import socket

    with socket.socket() as probe:               # a port nothing is listening on
        probe.bind(("127.0.0.1", 0))
        closed = probe.getsockname()[1]
    result = _run(out, f"http://127.0.0.1:{closed}")
    assert "failed" not in result and "passed" not in result and "could not reach" in result, result
