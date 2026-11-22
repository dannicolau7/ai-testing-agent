"""How generated tests read a real server's answers. Each case here was found on a real application."""

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import agent
import permissions

SOURCE = (
    "@bp.route('/')\n"
    "def index():\n    return ''\n"
    "@bp.route('/create', methods=('GET', 'POST'))\n"
    "@login_required\n"
    "def create():\n    return ''\n"
    "@bp.route('/<int:id>/update', methods=('GET', 'POST'))\n"
    "@login_required\n"
    "def update(id):\n    return ''\n"
    "@bp.route('/<int:id>/delete', methods=('POST',))\n"
    "def delete(id):\n    return ''\n"          # the planted fault: no sign-in
)
TABLE = (
    "roles: [anonymous, user]\nrules:\n"
    "  - {route: GET /, allow: [anonymous, user]}\n"
    "  - {route: GET /create, allow: [user]}\n"
    "  - {route: POST /create, allow: [user]}\n"
    "  - {route: 'GET /<int:id>/update', allow: [user]}\n"
    "  - {route: 'POST /<int:id>/delete', allow: [user]}\n"
)


class _Site(BaseHTTPRequestHandler):
    """Signs in with a session cookie and sends strangers to its login page, as many sites do."""

    hole = True
    deleted = []

    def _go(self, code, location=None):
        self.send_response(code)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _answer(self):
        signed_in = "session=good" in (self.headers.get("Cookie") or "")
        path = self.path
        if path == "/auth/login":
            self._go(200)                        # following a redirect here must not read as "let through"
        elif path == "/":
            self._go(200)
        elif path == "/create":
            if not signed_in:
                self._go(302, "/auth/login")
            else:
                self._go(302, "/") if self.command == "POST" else self._go(200)   # success redirects home
        elif path.endswith("/update") and path.split("/")[1].isdigit():
            if not signed_in:
                self._go(302, "/auth/login")
            else:
                self._go(200 if path.split("/")[1] == "1" else 404)                # only row 1 exists
        elif path.endswith("/delete") and path.split("/")[1].isdigit():
            if not signed_in and not _Site.hole:
                self._go(302, "/auth/login")
            else:
                _Site.deleted.append(path)
                self._go(302, "/")
        else:
            self._go(404)

    do_GET = do_POST = _answer  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path, monkeypatch):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "blog.py").write_text(SOURCE)
    _Site.hole, _Site.deleted = True, []
    httpd = HTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("ROLE_USER_COOKIE", "session=good")
    for name in ("ROLE_USER_TOKEN", "FINDINGS_PATH_ID", "SIGN_IN_PATH"):
        monkeypatch.delenv(name, raising=False)
    yield agent.Config(path=str(folder), policy=permissions.load(TABLE), browse=False, allow_writes=True,
                       url=f"http://127.0.0.1:{httpd.server_port}")
    httpd.shutdown()
    httpd.server_close()


def _cells(run):
    return {(c.role, c.method, c.path): (c.verdict, c.evidence) for c in run.cells}


def test_a_redirect_to_the_login_page_is_a_refusal_and_any_other_redirect_is_not(site):
    cells = _cells(agent.run(site))
    # Sent to sign in: refused. The test does not follow the redirect to the login page's 200.
    assert cells[("anonymous", "GET", "/create")] == ("holds", "refused")
    assert cells[("anonymous", "POST", "/create")] == ("holds", "refused")
    assert cells[("anonymous", "GET", "/<int:id>/update")] == ("holds", "refused")
    # A signed-in POST that succeeds redirects home. That is being let through, not refused.
    assert cells[("user", "POST", "/create")] == ("holds", "let through")
    # The hole: an anonymous delete is carried out and redirects home.
    verdict, evidence = cells[("anonymous", "POST", "/<int:id>/delete")]
    assert verdict == "broken" and evidence == "anonymous should be refused, got 302 to /"
    assert _Site.deleted and all(p == "/1/delete" for p in _Site.deleted), "the Flask-style parameter was filled in"


def test_the_same_hole_is_listed_once(site):
    run = agent.run(site)
    wrong = [i for i in run.report.items if i.group == "wrong_now"]
    assert len(wrong) == 1 and "Confirmed by a request to the running system" in wrong[0].detail
    assert "302 to /" in wrong[0].detail
    _Site.hole = False
    fixed = agent.run(site)
    assert fixed.ok and _cells(fixed)[("anonymous", "POST", "/<int:id>/delete")] == ("holds", "refused")
    assert [f.title for f in fixed.cleared], "the code still shows no check, but the running system refuses"


def test_not_found_shows_nothing_about_access(site, monkeypatch):
    monkeypatch.setenv("FINDINGS_PATH_ID", "7")          # no row 7: the update page answers 404
    _Site.hole = False
    cells = _cells(agent.run(site))
    verdict, evidence = cells[("user", "GET", "/<int:id>/update")]
    assert verdict == "not run" and "404" in evidence and "PERMISSIONS_PATH_ID" in evidence
    assert cells[("anonymous", "GET", "/<int:id>/update")][0] == "holds", "sent to sign in before any lookup"


def test_a_sign_in_that_never_works_proves_no_refusal(site, monkeypatch):
    table = TABLE + "  - {route: POST /admin, allow: []}\n"
    site.policy = permissions.load(table)
    monkeypatch.setenv("ROLE_USER_COOKIE", "session=expired")
    cells = _cells(agent.run(site))
    # Every route turns this cookie away, so the role is never seen to work...
    assert cells[("user", "GET", "/create")][0] == "broken"
    # ...and the one refusal it "passed" is not counted.
    verdict, evidence = cells[("user", "POST", "/admin")]
    assert verdict == "not run", evidence
    monkeypatch.setenv("ROLE_USER_COOKIE", "session=good")
    assert _cells(agent.run(site))[("user", "GET", "/create")][0] == "holds"


def test_the_sign_in_page_can_be_named(site, monkeypatch):
    # An application whose sign-in page has an unusual address is told so, not guessed at.
    monkeypatch.setenv("SIGN_IN_PATH", "^/$")
    cells = _cells(agent.run(site))
    assert cells[("anonymous", "POST", "/<int:id>/delete")][0] == "holds", "a redirect to / now counts as sign-in"
    assert cells[("anonymous", "GET", "/create")][0] == "broken", "and /auth/login no longer does"


def test_generated_files_stand_alone(site, tmp_path):
    import finding_tests
    import app_audit

    report = app_audit.audit(app_audit.build_model(site.path), policy=site.policy)
    for name, text in (("p.py", permissions.tests(site.policy)), ("f.py", finding_tests.generate(report.findings)[0])):
        assert "import live_checks" not in text and "def _answer(response):" in text
        assert "allow_redirects=False" in text
        (tmp_path / name).write_text(text)
        done = subprocess.run([sys.executable, "-m", "pytest", str(tmp_path / name), "-q", "-p", "no:cacheprovider",
                               "-o", "addopts="], capture_output=True, text=True, cwd=str(tmp_path),
                              env={k: v for k, v in os.environ.items()
                                   if not k.startswith(("FINDINGS_", "PERMISSIONS_", "ROLE_"))})
        assert "skipped" in done.stdout and "passed" not in done.stdout and "error" not in done.stdout, done.stdout
    assert Path(tmp_path / "p.py").is_file()
