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


# ── Sign-in stays with the site it is for ────────────────────────────────────

from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402


def _recording_server(body_for):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            seen.append((self.path, self.headers.get("Cookie"), self.headers.get("Authorization")))
            data = body_for(self.path).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if self.path == "/" else "application/javascript")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


def test_the_cookie_and_the_token_are_never_sent_to_another_site(site, tmp_path):
    """A page loads a script from somewhere else. That somewhere else must not be handed the sign-in."""
    other, other_seen = _recording_server(lambda path: "window.loaded = true;")
    # A different host name: cookies are shared across ports of one host, so a second port on
    # 127.0.0.1 would not count as another site.
    other_url = f"http://localhost:{other.server_port}"
    ours, our_seen = _recording_server(
        lambda path: f"<html><body><h1>Home</h1><script src='{other_url}/lib.js'></script></body></html>"
        if path == "/" else "")
    our_url = f"http://127.0.0.1:{ours.server_port}"
    secret = {"Cookie": "session=s3cret-cookie", "Authorization": "Bearer s3cret-token"}
    try:
        seen = browser_audit.browse(our_url, max_pages=1, headers=secret)
        assert seen.pages and seen.pages[0].status == 200
        home = next(entry for entry in our_seen if entry[0] == "/")
        assert home[1] == "session=s3cret-cookie" and home[2] == "Bearer s3cret-token", "our site gets both"
        assert any(path == "/lib.js" for path, _, _ in other_seen), "the other site was really asked"
        assert all(cookie is None and token is None for _, cookie, token in other_seen), other_seen

        # The same holds for the suite it writes.
        suite = automation.generate(None, None, observation=seen, app_name="demo")
        out = tmp_path / "automation"
        automation.write(suite, out)
        other_seen.clear()
        result = _run(out, our_url, AUTOMATION_USER_COOKIE="session=s3cret-cookie", AUTOMATION_USER_TOKEN="s3cret-token")
        assert "1 passed" in result, result
        assert other_seen and all(cookie is None and token is None for _, cookie, token in other_seen), other_seen
        assert any(cookie == "session=s3cret-cookie" and token == "Bearer s3cret-token" for _, cookie, token in our_seen)
    finally:
        other.shutdown()
        ours.shutdown()


def test_a_failing_browser_test_leaves_a_trace_and_a_passing_one_does_not(site, tmp_path):
    url, seen = site
    suite = automation.generate(None, None, observation=seen, app_name="demo")
    out = tmp_path / "automation"
    automation.write(suite, out)
    (out / "ui" / "pages.json").write_text('{"pages": [{"path": "/"}, {"path": "/help"}]}')
    traces = tmp_path / "traces"
    result = _run(out, url, AUTOMATION_TRACE_DIR=str(traces))
    assert "1 failed, 1 passed" in result, result            # /help throws by design
    assert [p.name for p in traces.iterdir()] == ["page-help.zip"], "a trace for the failure only"
    assert (traces / "page-help.zip").stat().st_size > 1000
