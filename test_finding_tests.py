"""Findings turned into tests that prove or clear them."""

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import app_audit
import finding_tests
import traceability

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "audit-demo"

# An application the audit will have four findings about. The live server below behaves as
# this source suggests for three of them, and proves the fourth a false alarm.
SOURCE = (
    "@app.get('/notes/{note_id}')\n"
    "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
    "    return db.execute('SELECT body FROM notes WHERE id = ?', (note_id,))\n"
    "@app.delete('/notes/{note_id}')\n"
    "def delete_note(note_id, db=Depends(get_db)):\n"
    "    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))\n"
    "@app.post('/feedback')\n"
    "def feedback(db=Depends(get_db)):\n"
    "    db.execute('INSERT INTO notes (body) VALUES (?)', ('x',))\n"
)
SCHEMA = "CREATE TABLE notes (id INTEGER PRIMARY KEY, owner_id INTEGER, body TEXT);\n"
FRONTEND = "export const share = (id) => fetch(`/notes/${id}/share`, { method: 'POST' });\n"
REQUIREMENTS = (
    "REQ-1 A signed-in user can read only their own notes (GET /notes/{id}).\n"
    "REQ-2 Only a signed-in user may delete a note (DELETE /notes/{id}).\n"
)


def _report(tmp_path):
    (tmp_path / "app.py").write_text(SOURCE)
    (tmp_path / "schema.sql").write_text(SCHEMA)
    (tmp_path / "ui.js").write_text(FRONTEND)
    reqs = traceability.extract_requirements(REQUIREMENTS)
    return app_audit.audit(app_audit.build_model(str(tmp_path)), reqs)


def test_a_test_is_written_for_each_finding_a_request_can_settle(tmp_path):
    report = _report(tmp_path)
    text, count, untested = finding_tests.generate(report.findings)
    compile(text, "generated", "exec")
    assert count == 4
    for name in ("test_exists_post_notes_id_share", "test_owner_only_get_notes_note_id",
                 "test_refuses_anonymous_delete_notes_note_id", "test_refuses_anonymous_post_feedback"):
        assert f"def {name}():" in text
    assert "# Requirement: REQ-1\ndef test_owner_only_get_notes_note_id" in text
    assert "# Requirement: REQ-2\ndef test_refuses_anonymous_delete_notes_note_id" in text
    assert untested and all(f"#   - {title}" in text for title in untested)
    assert "Table notes has no primary key" not in untested and any("notes.owner_id" in u or "trace to no" in u for u in untested)


def test_findings_carry_what_a_test_needs(tmp_path):
    by_check = {}
    for f in _report(tmp_path).findings:
        if f.check:
            by_check.setdefault(f.check, []).append((f.method, f.path, f.requirement))
    assert by_check == {
        "exists": [("POST", "/notes/{id}/share", "")],
        "owner_only": [("GET", "/notes/{note_id}", "REQ-1")],
        "refuses_anonymous": [("DELETE", "/notes/{note_id}", "REQ-2"), ("POST", "/feedback", "")],
    }


class _App(BaseHTTPRequestHandler):
    """Behaves as the faulty source would, except that /feedback is protected after all."""

    deleted = []

    def _answer(self):
        signed_in = self.headers.get("Authorization") == "Bearer user-a"
        if self.path.startswith("/notes/") and self.path.endswith("/share"):
            code = 404                                   # the frontend calls it; nothing is there
        elif self.command == "DELETE":
            _App.deleted.append(self.path)
            code = 204                                   # no access check: a real hole
        elif self.path == "/feedback":
            code = 201 if signed_in else 401             # protected by something the audit cannot see
        elif self.path.startswith("/notes/"):
            code = 200 if signed_in else 401             # any signed-in user reads any note: a real hole
        else:
            code = 404
        self.send_response(code)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST = do_DELETE = _answer  # noqa: N815

    def log_message(self, *args):
        pass


def _pytest(path, env, cwd):
    return subprocess.run([sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider", "--tb=line",
                           "-o", "addopts=", "-rs"], capture_output=True, text=True, env=env, cwd=str(cwd)).stdout


def test_generated_tests_prove_real_faults_and_clear_a_false_alarm(tmp_path):
    out = tmp_path / "test_generated_findings.py"
    source = tmp_path / "src"
    source.mkdir()
    out.write_text(finding_tests.generate(_report(source).findings)[0])
    httpd = HTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = {k: v for k, v in os.environ.items() if not k.startswith("FINDINGS_")}
    url = f"http://127.0.0.1:{httpd.server_port}"
    try:
        # With nothing set, nothing runs and nothing passes.
        result = _pytest(out, base, tmp_path)
        assert "4 skipped" in result and "passed" not in result, result

        # Read-only by default: tests that would change data stay skipped.
        _App.deleted.clear()
        result = _pytest(out, dict(base, FINDINGS_BASE_URL=url, FINDINGS_USER_TOKEN="user-a", FINDINGS_OTHER_ID="42"), tmp_path)
        assert "1 failed, 3 skipped" in result, result
        assert "gave one user another user\'s row: 200" in result and "set FINDINGS_ALLOW_WRITES=1" in result
        assert _App.deleted == [], "no write was sent without permission"

        # With writes allowed: three real faults fail, the false alarm passes.
        result = _pytest(out, dict(base, FINDINGS_BASE_URL=url, FINDINGS_USER_TOKEN="user-a", FINDINGS_OTHER_ID="42",
                                   FINDINGS_ALLOW_WRITES="1", FINDINGS_PATH_ID="7"), tmp_path)
        assert "3 failed, 1 passed" in result, result
        assert "POST /notes/{id}/share is not there: the server answered 404" in result
        assert "DELETE /notes/{note_id} let a caller through without signing in: 204" in result
        assert "test_refuses_anonymous_post_feedback" not in result, "protected after all: the finding was a false alarm"
        assert _App.deleted == ["/notes/7"], "the path parameter was filled in"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_command_line(tmp_path):
    out = tmp_path / "t.py"
    run = subprocess.run([sys.executable, "cli.py", "audit", str(DEMO), "-r", str(DEMO / "requirements.md"),
                          "--tests-out", str(out)], capture_output=True, text=True, cwd=str(HERE))
    assert run.returncode == 1 and "test(s) written from the findings" in run.stderr
    text = out.read_text()
    compile(text, "generated", "exec")
    assert "# Requirement: REQ-3\ndef test_refuses_anonymous_delete_api_orders_order_id" in text
    assert "# Application audit" in run.stdout, "the report itself is unchanged"
