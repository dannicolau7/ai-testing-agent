"""The browser check (roadmap stage 7). Runs a real browser against a small local site.

Skipped where Playwright or a browser is not installed; CI has a job that installs both.
"""

import importlib.util
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

import app_audit
import browser_audit

HERE = Path(__file__).resolve().parent

pytest.importorskip("playwright.sync_api")


def _load_demo():
    spec = importlib.util.spec_from_file_location("browser_demo_server", HERE / "examples" / "browser-demo" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def site():
    demo = _load_demo()
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


SOURCE = (
    "@app.get('/api/orders')\n"
    "def list_orders(user=Depends(current_user)): ...\n"
    "@app.get('/api/orders/{order_id}')\n"
    "def get_order(order_id, user=Depends(current_user)): ...\n"
    "@app.delete('/api/orders')\n"
    "def delete_all(user=Depends(require_admin)): ...\n"
    "@app.get('/api/me')\n"
    "def me(user=Depends(current_user)): ...\n"
    "@app.get('/health')\n"
    "def health(): ...\n"
)


def _titles(result, group):
    return [f.title for f in result.of(group)]


def test_pages_are_opened_and_planted_problems_are_seen(site, tmp_path):
    url, demo = site
    (tmp_path / "app.py").write_text(SOURCE)
    seen = browser_audit.browse(url)
    result = browser_audit.report(seen, app_audit.build_model(str(tmp_path)))
    assert sorted(browser_audit._path(p.url) for p in seen.pages) == ["/", "/account", "/help", "/orders", "/reports"]
    assert _titles(result, "wrong_now") == [
        "The page /help throws an error",
        "A link on / leads to /old-page, which answers 404",
        "The page /reports calls GET /api/reports/summary, and the server answers 404",
        "The page /reports calls GET /api/reports/slow, and the server fails with 500",
    ]
    assert _titles(result, "likely") == ["The page /help writes an error to the console"]
    assert _titles(result, "unclear") == ["The page /account calls GET /api/me, and is refused with 401"]
    assert not result.ok
    assert result.routes_seen_called == ["GET /api/me", "GET /api/orders"]
    assert result.routes_never_seen == ["DELETE /api/orders", "GET /api/orders/{order_id}"]
    markdown = browser_audit.render_markdown(result)
    assert "| Pages opened | 5 |" in markdown and "| Backend routes seen being called | 2 of 4 |" in markdown
    assert "Buttons were not clicked." in markdown and "Forms were not filled in" in markdown


def test_nothing_is_clicked_unless_asked_and_destructive_buttons_never(site):
    url, demo = site
    before = demo.calls["delete_all"]
    seen = browser_audit.browse(url + "/orders", max_pages=1)
    assert [(c.method, c.path) for c in seen.api] == [("GET", "/api/orders")]
    clicked = browser_audit.browse(url + "/orders", max_pages=1, click=True)
    page = clicked.pages[0]
    assert page.buttons_clicked == ["Refresh"] and page.buttons_skipped == ["Delete all orders"]
    assert ("GET", "/api/orders/7") in [(c.method, c.path) for c in clicked.api]
    assert demo.calls["delete_all"] == before, "the destructive button and the form were left alone"
    assert "Skipped because the label looks destructive" in browser_audit.render_markdown(browser_audit.report(clicked))


def test_a_header_signs_the_browser_in_and_the_page_limit_is_reported(site):
    url, _ = site
    signed_in = browser_audit.report(browser_audit.browse(
        url + "/account", max_pages=1, headers={"Authorization": "Bearer demo-token"}))
    assert signed_in.findings == [] and signed_in.ok
    limited = browser_audit.browse(url, max_pages=2)
    assert len(limited.pages) == 2 and limited.not_visited >= 3
    assert "more link(s) were found and not opened" in browser_audit.render_markdown(browser_audit.report(limited))


def test_a_start_page_that_is_down_is_wrong_now(site):
    url, _ = site
    missing = browser_audit.report(browser_audit.browse(url + "/nothing-here", max_pages=1))
    assert _titles(missing, "wrong_now") == ["The page /nothing-here did not load"]
    dead = browser_audit.report(browser_audit.browse("http://127.0.0.1:9/", max_pages=1, timeout_ms=3000))
    assert _titles(dead, "wrong_now") == ["The page / did not load"]


def test_command_line(site, tmp_path):
    url, _ = site
    (tmp_path / "app.py").write_text(SOURCE)
    out = tmp_path / "browse.md"
    env = dict(os.environ, AI_AGENT_TELEMETRY="false")
    run = subprocess.run([sys.executable, "cli.py", "browse", url, "--source", str(tmp_path), "-o", str(out)],
                         capture_output=True, text=True, cwd=str(HERE), env=env)
    assert run.returncode == 1, run.stdout + run.stderr
    assert "## Wrong now (4)" in out.read_text()
    ok = subprocess.run([sys.executable, "cli.py", "browse", url + "/account", "--max-pages", "1",
                         "--header", "Authorization: Bearer demo-token"],
                        capture_output=True, text=True, cwd=str(HERE), env=env)
    assert ok.returncode == 0 and "## Wrong now (0)" in ok.stdout
    bad = subprocess.run([sys.executable, "cli.py", "browse", url, "--header", "no-colon"],
                         capture_output=True, text=True, cwd=str(HERE), env=env)
    assert bad.returncode == 2
    assert urllib.request.urlopen(url + "/api/_calls").status == 200
