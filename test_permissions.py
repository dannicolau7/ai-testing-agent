"""Who may do what: the table of roles against actions (roadmap stage 6)."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import app_audit
import permissions

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "audit-demo"

APP = (
    "@app.get('/notes')\n"
    "def listing(db=Depends(get_db), user=Depends(current_user)):\n"
    "    return db.execute('SELECT body FROM notes WHERE user_id = ?', (user.id,))\n"
    "@app.get('/notes/{note_id}')\n"
    "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
    "    return db.execute('SELECT body FROM notes WHERE id = ?', (note_id,))\n"
    "@app.delete('/notes/{note_id}')\n"
    "def delete_note(note_id, db=Depends(get_db)):\n"
    "    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))\n"
    "@app.post('/admin/purge')\n"
    "def purge(db=Depends(get_db), user=Depends(current_user)):\n"
    "    db.execute('DELETE FROM notes')\n"
    "@app.post('/admin/export')\n"
    "def export(db=Depends(get_db), user=Depends(require_admin)): ...\n"
    "@app.get('/about')\n"
    "def about(user=Depends(current_user)): ...\n"
    "@app.post('/feedback')\n"
    "def feedback(): ...\n"
    "@app.get('/health')\n"
    "def health(): ...\n"
)
SCHEMA = "CREATE TABLE notes (id INTEGER PRIMARY KEY, user_id INTEGER, body TEXT);\n"
TABLE = (
    "roles: [user, admin]\n"
    "rules:\n"
    "  - {route: GET /notes, allow: [user, admin]}\n"
    "  - {route: 'GET /notes/{id}', allow: [user, admin], own: true}\n"
    "  - {route: 'DELETE /notes/{id}', allow: [user], own: true}\n"
    "  - {route: POST /admin/purge, allow: [admin]}\n"
    "  - {route: POST /admin/export, allow: [admin]}\n"
    "  - {route: GET /about, allow: [anonymous, user, admin]}\n"
    "  - {route: POST /gone, allow: []}\n"
)


def _model(tmp_path):
    (tmp_path / "app.py").write_text(APP)
    (tmp_path / "schema.sql").write_text(SCHEMA)
    return app_audit.build_model(str(tmp_path))


def test_the_table_is_read_and_mistakes_in_it_are_named():
    policy = permissions.load(TABLE)
    assert policy.roles == ["anonymous", "user", "admin"] and policy.problems == []
    assert [(r.name, r.allow, r.own) for r in policy.rules][:3] == [
        ("GET /notes", ["user", "admin"], False), ("GET /notes/{id}", ["user", "admin"], True),
        ("DELETE /notes/{id}", ["user"], True)]
    bad = permissions.load(
        "roles: [user]\nrules:\n"
        "  - {route: GET /a, allow: [user, owner]}\n"
        "  - {route: fetch /b, allow: [user]}\n"
        "  - {route: GET /c, allow: user}\n"
        "  - {route: GET /d, allow: [user]}\n"
        "  - {route: 'GET /d/', allow: []}\n")
    assert [r.name for r in bad.rules] == ["GET /d"]
    assert len(bad.problems) == 4 and "unknown role(s) owner" in bad.problems[0]
    assert "a second rule for the same route" in bad.problems[3]
    assert permissions.load("rules: [").problems[0].startswith("not valid YAML")
    assert permissions.load("roles: user").problems == ["the file needs a `roles` list and a `rules` list"]


def test_the_code_is_compared_with_the_table(tmp_path):
    model = _model(tmp_path)
    report = app_audit.audit(model, policy=permissions.load(TABLE))
    assert [f.title for f in report.of("wrong_now")] == [
        "GET /notes/{note_id} is limited to the owner's rows, but the code does not check who owns the row",
        "DELETE /notes/{note_id} must refuse a caller who is not signed in, but the code shows no access check",
    ]
    likely = [f.title for f in report.of("likely")]
    assert "POST /admin/purge must refuse user, but no role check is visible" in likely
    assert "GET /about is meant to be open to everyone, but the code asks for sign-in" in likely
    assert "1 route(s) have no rule in the permissions table" in likely, "POST /feedback; /health is operational"
    assert not [t for t in likely if "export" in t], "require_admin is a visible role check"
    assert not [t for t in likely if "notes" in t and ("shows no access check" in t or "who owns" in t)], \
        "the table's finding replaces the general suspicion"
    assert "POST /feedback changes data and shows no access check" in likely, "no rule, so the suspicion stays"
    assert "The permissions table has a rule for POST /gone, which the backend does not define" in [
        f.title for f in report.of("unclear")]
    markdown = app_audit.render_markdown(report)
    assert "| GET /notes/{id} | refuse | allow | allow | yes | sign-in only |" in markdown
    assert "| POST /admin/export | refuse | refuse | allow | no | requires admin |" in markdown
    assert "| DELETE /notes/{id} | refuse | allow | refuse | yes | no access check |" in markdown


def test_a_column_name_is_not_a_role_check(tmp_path):
    (tmp_path / "app.py").write_text(
        "@app.get('/orders')\n"
        "def orders(db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.execute('SELECT id FROM orders WHERE customer_id = ?', (user.id,))\n"
        "@app.get('/staff')\n"
        "def staff(db=Depends(get_db), user=Depends(current_user)):\n"
        "    if not user.is_admin:\n"
        "        raise HTTPException(403)\n")
    model = app_audit.build_model(str(tmp_path))
    roles = ["anonymous", "customer", "admin"]
    assert permissions.shown(model.routes[0], roles).roles == []
    assert permissions.shown(model.routes[1], roles).roles == ["admin"]


def test_a_mistake_in_the_table_fails_the_audit(tmp_path):
    report = app_audit.audit(_model(tmp_path), policy=permissions.load("roles: [user]\nrules:\n  - {route: nope}\n"))
    assert not report.ok and report.of("wrong_now")[0].title == "The permissions file has a mistake"


def test_without_a_table_the_report_says_so(tmp_path):
    report = app_audit.audit(_model(tmp_path))
    assert any("Pass --permissions" in n for n in report.not_examined)
    assert "## Permissions" not in app_audit.render_markdown(report)


def test_a_draft_describes_the_code_as_it_is(tmp_path):
    text = permissions.draft(_model(tmp_path), ["user", "admin"])
    policy = permissions.load(text)
    assert policy.problems == []
    allow = {r.name: r.allow for r in policy.rules}
    assert allow["DELETE /notes/{note_id}"] == ["anonymous", "user", "admin"]
    assert allow["GET /notes"] == ["user", "admin"] and allow["POST /admin/export"] == ["admin"]
    assert "GET /health" not in allow


class _App(BaseHTTPRequestHandler):
    """A tiny application with a planted hole: any signed-in user can purge."""

    def _answer(self):
        token = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        role = {"u-token": "user", "a-token": "admin"}.get(token)
        if self.path == "/about":
            code = 200
        elif role is None:
            code = 401
        elif self.path == "/admin/export" and role != "admin":
            code = 403
        else:
            code = 200   # /admin/purge lands here for a plain user: the hole
        self.send_response(code)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_GET = do_POST = do_DELETE = _answer  # noqa: N815

    def log_message(self, *args):
        pass


def test_generated_tests_run_and_catch_a_real_hole(tmp_path):
    table = tmp_path / "permissions.yaml"
    table.write_text(
        "roles: [user, admin]\nrules:\n"
        "  - {route: GET /about, allow: [anonymous, user, admin]}\n"
        "  - {route: POST /admin/export, allow: [admin]}\n"
        "  - {route: POST /admin/purge, allow: [admin]}\n"
        "  - {route: 'GET /notes/{id}', allow: [user, admin]}\n")
    out = tmp_path / "test_generated_permissions.py"
    made = subprocess.run([sys.executable, str(HERE / "cli.py"), "permissions", "--tests", str(table), "-o", str(out)],
                          capture_output=True, text=True, cwd=str(HERE))
    assert made.returncode == 0, made.stdout + made.stderr
    assert "12 permission tests (5 of them refusals)" in made.stdout

    httpd = HTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        env = dict(os.environ, PERMISSIONS_BASE_URL=f"http://127.0.0.1:{httpd.server_port}",
                   ROLE_USER_TOKEN="u-token", ROLE_ADMIN_TOKEN="a-token")
        # Nothing that changes data is sent until that is allowed: the six POST tests wait.
        held = subprocess.run(
            [sys.executable, "-m", "pytest", str(out), "-q", "-p", "no:cacheprovider", "--tb=no", "-o", "addopts=", "-rs"],
            capture_output=True, text=True, env=env, cwd=str(tmp_path))
        assert "6 skipped" in held.stdout and "failed" not in held.stdout, held.stdout
        assert "set PERMISSIONS_ALLOW_WRITES=1" in held.stdout
        env["PERMISSIONS_ALLOW_WRITES"] = "1"
        report = tmp_path / "report.json"
        run = subprocess.run(
            [sys.executable, "-m", "pytest", str(out), "-q", "-p", "no:cacheprovider", "--tb=no",
             "-o", "addopts=", f"--junitxml={report}"], capture_output=True, text=True, env=env, cwd=str(tmp_path))
        assert "1 failed, 11 passed" in run.stdout, run.stdout
        assert "test_user_may_not_post_admin_purge" in run.stdout

        # Without a token a test is skipped, never passed.
        env.pop("ROLE_ADMIN_TOKEN")
        run = subprocess.run(
            [sys.executable, "-m", "pytest", str(out), "-q", "-p", "no:cacheprovider", "--tb=no", "-o", "addopts="],
            capture_output=True, text=True, env=env, cwd=str(tmp_path))
        assert "4 skipped" in run.stdout and "1 failed, 7 passed" in run.stdout, run.stdout
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert json.dumps("ok")


def test_command_line(tmp_path):
    out = tmp_path / "draft.yaml"
    made = subprocess.run([sys.executable, "cli.py", "permissions", str(DEMO), "--init", "--roles", "customer,admin",
                           "-o", str(out)], capture_output=True, text=True, cwd=str(HERE))
    assert made.returncode == 0 and "roles: [anonymous, customer, admin]" in out.read_text()
    audit = subprocess.run([sys.executable, "cli.py", "audit", str(DEMO), "-p", str(DEMO / "permissions.yaml")],
                           capture_output=True, text=True, cwd=str(HERE))
    assert audit.returncode == 1
    assert "POST /api/admin/reindex must refuse customer, but no role check is visible" in audit.stdout
    assert "| GET /api/orders | refuse | allow | allow | no | sign-in only |" in audit.stdout
    for args in (["permissions"], ["permissions", "--tests", str(tmp_path / "missing.yaml")],
                 ["permissions", "--init"], ["audit", str(DEMO), "-p", str(tmp_path / "missing.yaml")]):
        assert subprocess.run([sys.executable, "cli.py"] + args, capture_output=True, text=True,
                              cwd=str(HERE)).returncode == 2
