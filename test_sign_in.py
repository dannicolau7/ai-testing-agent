"""The agent signs in to the test environment itself, and keeps what it receives to itself."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import pytest

import agent
import permissions
import sign_in

FILE = """
roles:
  user:
    request: POST /auth/login
    form: {username: alice, password: {env: ALICE_PASSWORD}}
  admin:
    request: POST /api/token
    json: {email: root@example.com, password: {env: ROOT_PASSWORD}}
    token: access_token
    scheme: Token
"""
SOURCE = (
    "@app.get('/me')\n"
    "def me(user=Depends(current_user)):\n    return {}\n"
    "@app.get('/admin/report')\n"
    "def report(user=Depends(current_user)):\n    return {}\n"
)
TABLE = (
    "roles: [anonymous, user, admin]\nrules:\n"
    "  - {route: GET /me, allow: [user, admin]}\n"
    "  - {route: GET /admin/report, allow: [admin]}\n"
)
COOKIE, TOKEN = "s3ss10n-value-771", "t0ken-value-992"


class _Site(BaseHTTPRequestHandler):
    def _reply(self, code, body=None, cookie=None):
        data = json.dumps(body or {}).encode()
        self.send_response(code)
        if cookie:
            self.send_header("Set-Cookie", f"session={cookie}; HttpOnly; Path=/")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _who(self):
        if f"session={COOKIE}" in (self.headers.get("Cookie") or ""):
            return "user"
        if self.headers.get("Authorization") == f"Token {TOKEN}":      # not "Bearer": this site says "Token"
            return "admin"
        return None

    def _answer(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if self.path == "/auth/login":
            form = parse_qs(raw)
            good = form.get("username") == ["alice"] and form.get("password") == ["alice-pw"]
            return self._reply(302 if good else 401, cookie=COOKIE if good else None)
        if self.path == "/api/token":
            try:
                body = json.loads(raw)
            except ValueError:
                body = {}
            good = body == {"email": "root@example.com", "password": "root-pw"}
            return self._reply(200 if good else 400, {"access_token": TOKEN} if good else {"detail": "no"})
        if self.path == "/quiet":
            return self._reply(200)
        who = self._who()
        if who is None:
            return self._reply(401)
        if self.path == "/admin/report" and who != "admin":
            return self._reply(403)
        self._reply(200 if self.path in ("/me", "/admin/report") else 404)

    do_GET = do_POST = _answer  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path, monkeypatch):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "app.py").write_text(SOURCE)
    httpd = HTTPServer(("127.0.0.1", 0), _Site)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("ALICE_PASSWORD", "alice-pw")
    monkeypatch.setenv("ROOT_PASSWORD", "root-pw")
    for name in ("ROLE_USER_TOKEN", "ROLE_USER_COOKIE", "ROLE_ADMIN_TOKEN", "FINDINGS_USER_TOKEN", "PATH_IDS"):
        monkeypatch.delenv(name, raising=False)
    roles, problems = sign_in.load(FILE)
    assert not problems
    yield agent.Config(path=str(folder), policy=permissions.load(TABLE), browse=False, sign_in=roles,
                       url=f"http://127.0.0.1:{httpd.server_port}")
    httpd.shutdown()
    httpd.server_close()


def test_the_agent_signs_each_role_in_and_every_cell_is_tried(site, tmp_path):
    run = agent.run(site)
    step = next(s for s in run.steps if s.name == "Sign in")
    assert step.status == "done" and step.detail == "signed in: user (a cookie), admin (a token)"
    cells = {(c.role, c.path): c.verdict for c in run.cells}
    assert set(cells.values()) == {"holds"} and len(cells) == 6, cells      # nobody pasted a cookie anywhere
    assert run.where["signed_in_by_the_agent"] == ["user", "admin"]
    assert run.where["token_variables_set"] == ["FINDINGS_USER_COOKIE", "ROLE_ADMIN_TOKEN", "ROLE_USER_COOKIE"]

    # Nothing it received, and no password, is written anywhere.
    agent.write_outputs(run, tmp_path / "out")
    for file in (tmp_path / "out").iterdir():
        text = file.read_text()
        for secret in (COOKIE, TOKEN, "alice-pw", "root-pw"):
            assert secret not in text, f"{secret} in {file.name}"
    assert "The agent signed in itself as: user, admin" in (tmp_path / "out" / "report.md").read_text()


def test_one_role_failing_does_not_stop_the_other(site, monkeypatch):
    monkeypatch.setenv("ROOT_PASSWORD", "wrong")
    run = agent.run(site)
    step = next(s for s in run.steps if s.name == "Sign in")
    assert step.status == "failed" and "role admin: the sign-in was turned down (400)" in step.detail
    assert "wrong" not in step.detail and "user (a cookie)" in step.detail
    cells = {(c.role, c.path): c.verdict for c in run.cells}
    assert cells[("user", "/me")] == "holds" and cells[("admin", "/me")] == "not run"
    assert any(line.startswith("Sign-in:") for line in run.needs_person)

    monkeypatch.delenv("ALICE_PASSWORD")
    run = agent.run(site)
    assert "environment variable ALICE_PASSWORD is not set" in next(s for s in run.steps if s.name == "Sign in").detail


def test_secrets_may_not_be_written_in_the_file():
    for field in ("password: hunter2", "api_key: abc", "client_secret: abc", "token: abc"):
        roles, problems = sign_in.load(f"roles:\n  user:\n    request: POST /login\n    form: {{username: a, {field}}}\n")
        assert roles == [] and "must be given as {env: NAME}" in problems[0], field
        assert "hunter2" not in problems[0] and "abc" not in problems[0]
    roles, problems = sign_in.load("roles:\n  user:\n    request: POST /login\n    form: {username: a, password: {env: P}}\n")
    assert len(roles) == 1 and not problems


def test_a_file_with_mistakes_says_what_they_are():
    cases = {
        "roles: [": "not valid YAML",
        "nothing: 1": "needs a `roles` section",
        "roles:\n  user: text": "not a role",
        "roles:\n  user:\n    request: login\n    form: {a: b}": "must look like `POST /auth/login`",
        "roles:\n  user:\n    request: POST /l": "exactly one of `form` or `json`",
        "roles:\n  user:\n    request: POST /l\n    form: {a: b}\n    json: {a: b}": "exactly one of",
        "roles:\n  user:\n    request: POST /l\n    form: {a: [1]}": "plain value or {env: NAME}",
        "roles:\n  user:\n    request: POST /l\n    form: {a: b}\n    scheme: 'Bearer x'": "one word",
    }
    for text, reason in cases.items():
        roles, problems = sign_in.load(text)
        assert roles == [] and reason in problems[0], text
    # A good role survives a bad neighbour.
    roles, problems = sign_in.load("roles:\n  user:\n    request: POST /l\n    form: {a: b}\n  bad: 7\n")
    assert [r.name for r in roles] == ["user"] and len(problems) == 1


def test_sign_ins_that_prove_nothing_are_refused(site):
    url = site.url
    quiet = sign_in.Role("user", "POST", "/quiet", {"a": "b"})
    with pytest.raises(sign_in.SignInError, match="set no cookie"):
        sign_in.sign_in_one(quiet, url)
    no_field = sign_in.Role("admin", "POST", "/quiet", {"a": "b"}, token_field="access_token")
    with pytest.raises(sign_in.SignInError, match="no `access_token` field"):
        sign_in.sign_in_one(no_field, url)
    with pytest.raises(sign_in.SignInError, match="could not reach"):
        sign_in.sign_in_one(quiet, "http://127.0.0.1:9")
    done = sign_in.sign_in([quiet, no_field], url)
    assert done.credentials == [] and len(done.failures) == 2 and done.environment() == {}
    assert done.headers_for("user") == {}


def test_without_an_address_or_an_answer_nobody_is_signed_in(site):
    import dataclasses

    for change, reason in ((dict(url=""), "no address"), (dict(url="http://127.0.0.1:9"), "nothing answered"),
                           (dict(sign_in=None), "no sign-in file was given")):
        run = agent.run(dataclasses.replace(site, **change))
        step = next(s for s in run.steps if s.name == "Sign in")
        assert step.status == "not run" and reason in step.detail, change
        assert run.signed_in == []
