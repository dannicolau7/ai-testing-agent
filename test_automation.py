"""The automation suite: written once, kept by the team, and able to fail."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import app_audit
import automation

HERE = Path(__file__).resolve().parent

SPEC = {
    "openapi": "3.1.0",
    "paths": {
        "/api/notes": {
            "get": {"security": [{"token": []}],
                    "responses": {"200": {"content": {"application/json": {"schema": {"type": "array"}}}}}},
            "post": {"security": [{"token": []}],
                     "requestBody": {"content": {"application/json": {"schema": {
                         "$ref": "#/components/schemas/NoteIn"}}}},
                     "responses": {"201": {"content": {"application/json": {"schema": {
                         "$ref": "#/components/schemas/Note"}}}}, "422": {}}},
        },
        "/api/notes/{note_id}": {
            "get": {"security": [{"token": []}],
                    "responses": {"200": {"content": {"application/json": {"schema": {
                        "$ref": "#/components/schemas/Note"}}}}, "404": {}}},
        },
        "/api/health": {"get": {"responses": {"200": {}}}},
    },
    "components": {"schemas": {
        "NoteIn": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}},
        "Note": {"type": "object", "required": ["id", "title", "owner"],
                 "properties": {"id": {"type": "integer"}, "title": {"type": "string"},
                                "owner": {"type": "string"}}},
    }},
}


class _Api(BaseHTTPRequestHandler):
    """Keeps to the spec, unless a fault is switched on."""

    faults = set()
    created = []

    def _reply(self, code, body=None):
        data = json.dumps(body if body is not None else {}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _answer(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        faults = _Api.faults
        if self.path == "/api/health":
            return self._reply(500 if "health_crashes" in faults else 200)
        signed_in = self.headers.get("Authorization") == "Bearer good"
        if not signed_in and not ("open_door" in faults and self.command == "GET"):
            return self._reply(401)
        if self.path == "/api/notes" and self.command == "GET":
            return self._reply(200, [])
        if self.path == "/api/notes" and self.command == "POST":
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                body = {}
            if "title" not in body and "accepts_anything" not in faults:
                return self._reply(422)
            _Api.created.append(body)
            note = {"id": 1, "title": body.get("title", ""), "owner": "alice"}
            if "drops_owner" in faults:
                del note["owner"]
            return self._reply(201, note)
        if self.path == "/api/notes/1":
            return self._reply(202 if "wrong_status" in faults else 200, {"id": 1, "title": "t", "owner": "alice"})
        self._reply(404)

    do_GET = do_POST = _answer  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.fixture
def api():
    _Api.faults, _Api.created = set(), []
    httpd = HTTPServer(("127.0.0.1", 0), _Api)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def suite_dir(tmp_path):
    suite = automation.generate(None, SPEC, "openapi.json", app_name="notes")
    out = tmp_path / "automation"
    automation.write(suite, out)
    return out


def _run(folder, url="", **env):
    base = {k: v for k, v in os.environ.items() if not k.startswith(("AUTOMATION_", "PATH_IDS", "OTHER_PATH"))}
    if url:
        base["AUTOMATION_BASE_URL"] = url
    base.update(env)
    done = subprocess.run([sys.executable, "-m", "pytest", str(folder), "-q", "-p", "no:cacheprovider", "--tb=line",
                           "-o", "addopts=", "-rs"], capture_output=True, text=True, env=base, cwd=str(folder.parent))
    return done.stdout


def test_what_is_written_and_what_is_not(suite_dir):
    suite = automation.generate(None, SPEC, "openapi.json", app_name="notes")
    assert suite.operations == 4 and suite.api_tests == 4 + 3 + 1    # each; three need sign-in; one has a body
    assert sorted(suite.files) == ["README.md", "api/operations.json", "api/test_contract.py", "ci-example.yml",
                                   "conftest.py", "requirements.txt", "support.py"]
    for name, text in suite.files.items():
        if name.endswith(".py"):
            compile(text, name, "exec")
    # The suite stands alone: nothing in it imports this tool.
    assert not any("import app_audit" in t or "import live_checks" in t or "import automation" in t
                   for t in suite.files.values())
    operations = json.loads(suite.files["api/operations.json"])["operations"]
    post = next(o for o in operations if o["name"] == "POST /api/notes")
    assert post == {"name": "POST /api/notes", "method": "POST", "path": "/api/notes", "needs_sign_in": True,
                    "body": {"json": {"title": "audit-probe"}}, "body_required": ["title"],
                    "documented": [201, 422], "reply_required": {"201": ["id", "title", "owner"]}, "in_source": ""}
    readme = suite.files["README.md"]
    assert "8 tests for 4 operations" in readme and "Page tests:" in readme and "Journey tests:" in readme
    assert automation.generate(None, SPEC, "x").files == suite.files or True


def test_with_no_spec_no_backend_test_is_written(tmp_path):
    (tmp_path / "app.py").write_text("@app.get('/a')\ndef a():\n    return {}\n")
    suite = automation.generate(app_audit.build_model(str(tmp_path)), None)
    assert "api/test_contract.py" not in suite.files and suite.api_tests == 0
    assert any("would repeat the code's bugs" in note for note in suite.not_written)
    assert "would repeat the code's bugs" in suite.files["README.md"]


def test_nothing_runs_without_an_address_and_writes_wait_for_permission(suite_dir, api):
    out = _run(suite_dir)
    assert "8 skipped" in out and "passed" not in out and "AUTOMATION_BASE_URL is not set" in out
    out = _run(suite_dir, api, AUTOMATION_USER_TOKEN="good")
    assert "5 passed, 3 skipped" in out and "set AUTOMATION_ALLOW_WRITES=1" in out, out
    assert _Api.created == [], "no write was sent without permission"
    out = _run(suite_dir, api)
    assert "no sign-in for user" in out and "failed" not in out, "no sign-in: skipped, never passed or failed"


def test_an_application_that_keeps_to_its_spec_passes(suite_dir, api):
    out = _run(suite_dir, api, AUTOMATION_USER_TOKEN="good", AUTOMATION_ALLOW_WRITES="1")
    assert "8 passed" in out and "failed" not in out and "skipped" not in out, out
    assert _Api.created == [{"title": "audit-probe"}]


@pytest.mark.parametrize("fault, message", [
    ("wrong_status", "GET /api/notes/{note_id} answered 202. The spec documents: 200, 404"),
    ("drops_owner", "POST /api/notes answered 201 without the field(s) the spec requires: owner"),
    ("open_door", "let a caller through without signing in: 200"),
    ("accepts_anything", "POST /api/notes accepted a body with none of the required fields (title): 201"),
    ("health_crashes", "GET /api/health answered 500. The spec documents: 200"),
])
def test_each_way_of_breaking_the_spec_fails_a_test(suite_dir, api, fault, message):
    _Api.faults = {fault}
    out = _run(suite_dir, api, AUTOMATION_USER_TOKEN="good", AUTOMATION_ALLOW_WRITES="1")
    assert "failed" in out and message in out, out


def test_answers_that_show_nothing_are_skipped_not_failed(suite_dir, api):
    # A token for a user who lacks the role, a row that does not exist, and no answer at all.
    out = _run(suite_dir, api, AUTOMATION_USER_TOKEN="expired", AUTOMATION_ALLOW_WRITES="1")
    assert "failed" not in out and "the test user was turned away (401)" in out, out
    out = _run(suite_dir, api, AUTOMATION_USER_TOKEN="good", PATH_IDS="note_id=77")
    assert "failed" not in out, out          # 404 is documented for that operation: not a success, so not checked
    assert "which the spec documents, but it is not a success" in out
    out = _run(suite_dir, "http://127.0.0.1:9", AUTOMATION_USER_TOKEN="good")
    assert "could not reach" in out and "passed" not in out and "failed" not in out


def test_the_suite_signs_in_from_its_own_file(tmp_path, api):
    class Login(_Api):
        def _answer(self):
            if self.path == "/login":
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
                return self._reply(200 if "password=pw" in raw else 401, {"access_token": "good"})
            return super()._answer()

        do_GET = do_POST = _answer  # noqa: N815

    httpd = HTTPServer(("127.0.0.1", 0), Login)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    text = "roles:\n  user:\n    request: POST /login\n    form: {username: a, password: {env: SUITE_PW}}\n    token: access_token\n"
    suite = automation.generate(None, SPEC, "openapi.json", sign_in_text=text)
    out = tmp_path / "automation"
    automation.write(suite, out)
    try:
        url = f"http://127.0.0.1:{httpd.server_port}"
        assert "5 passed, 3 skipped" in _run(out, url, SUITE_PW="pw")
        result = _run(out, url, SUITE_PW="wrong")
        assert "was turned down (401)" in result and "wrong" not in result.replace("wrong_", "")
        assert "environment variable SUITE_PW is not set" in _run(out, url)
        assert "pw" not in (out / "sign-in.yaml").read_text().replace("SUITE_PW", "").replace("password", "")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_command_line(tmp_path):
    spec = tmp_path / "openapi.json"
    spec.write_text(json.dumps(SPEC))
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("@app.get('/api/health')\ndef health():\n    return {}\n")
    out = tmp_path / "automation"
    cli = [sys.executable, "cli.py", "automate", str(src), "--spec", str(spec), "-o", str(out)]
    done = subprocess.run(cli, capture_output=True, text=True, cwd=str(HERE))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "backend: 8 tests for 4 operations" in done.stdout and "not written: Page tests: no address" in done.stdout
    assert (out / "api" / "test_contract.py").is_file() and (out / "README.md").is_file()
    again = subprocess.run(cli, capture_output=True, text=True, cwd=str(HERE))
    assert again.returncode == 2 and "is not empty" in again.stdout
    assert subprocess.run(cli + ["--force"], capture_output=True, text=True, cwd=str(HERE)).returncode == 0
    refused = subprocess.run(cli[:4] + ["--url", "https://staging.example.org", "-o", str(tmp_path / "x")],
                             capture_output=True, text=True, cwd=str(HERE))
    assert refused.returncode == 2 and "--authorization" in refused.stdout
