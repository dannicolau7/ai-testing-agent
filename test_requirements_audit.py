"""The code checked against written requirements (roadmap stage 4, fourth step)."""

import subprocess
import sys
from pathlib import Path

import app_audit
import traceability

DEMO = Path(__file__).resolve().parent / "examples" / "audit-demo"

SCHEMA = (
    "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, phone_number TEXT);\n"
    "CREATE TABLE notes (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), body TEXT);\n"
)
APP = (
    "@app.get('/notes/{note_id}')\n"
    "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
    "    return db.execute('SELECT body FROM notes WHERE id = ?', (note_id,))\n"
    "\n"
    "# Requirement: REQ-2, REQ-77\n"
    "@app.delete(\n"
    "    '/notes/{note_id}',\n"
    ")\n"
    "def delete_note(note_id, db=Depends(get_db)):\n"
    "    db.execute('DELETE FROM notes WHERE id = ?', (note_id,))\n"
    "\n"
    "@app.post('/admin/purge')\n"
    "def purge(db=Depends(get_db), user=Depends(current_user)):\n"
    "    \"\"\"Remove everything.\n"
    "\n"
    "    Covers: REQ-3\n"
    "    \"\"\"\n"
    "    db.execute('DELETE FROM notes')\n"
    "\n"
    "@app.post('/notes')\n"
    "def add(db=Depends(get_db), user=Depends(current_user)):\n"
    "    db.execute('INSERT INTO notes (user_id, body) VALUES (?, ?)', (user.id, ''))\n"
)


def _run(tmp_path, requirements, app=APP):
    (tmp_path / "app.py").write_text(app)
    (tmp_path / "schema.sql").write_text(SCHEMA)
    reqs = traceability.extract_requirements(requirements)
    return app_audit.audit(app_audit.build_model(str(tmp_path)), reqs)


def _titles(report, group):
    return [f.title for f in report.of(group)]


def test_requirements_are_linked_by_route_name_comment_and_docstring(tmp_path):
    report = _run(tmp_path,
        "REQ-1 A signed-in user can read only their own notes (GET /notes/{id}).\n"
        "REQ-2 A signed-in user can delete a note.\n"
        "REQ-3 Administrators only: purge all notes.\n"
        "REQ-4 An email must be unique for every user.\n"
        "REQ-5 A user's phone number must be unique.\n"
        "REQ-6 A user can share a note (POST /notes/{id}/share).\n"
        "REQ-7 Notes can be printed.\n")
    rows = {r.id: (r.linked_to, r.checked, r.result) for r in report.requirements.rows}
    assert rows == {
        "REQ-1": ("GET /notes/{note_id}", "sign-in, ownership", "Problem: no ownership check"),
        "REQ-2": ("DELETE /notes/{note_id}", "sign-in", "Problem: no access check"),
        "REQ-3": ("POST /admin/purge", "admin only", "Problem: no role check seen"),
        "REQ-4": ("users.email", "unique", "No problem found in what was checked"),
        "REQ-5": ("users.phone_number", "unique", "Problem: not enforced"),
        "REQ-6": ("POST /notes/{id}/share (missing)", "", "Problem: route missing"),
        "REQ-7": ("", "", "Not linked to code"),
    }
    assert (report.requirements.linked, report.requirements.total) == (6, 7)
    assert _titles(report, "wrong_now") == [
        "REQ-1 limits GET /notes/{note_id} to the owner, but the code does not check who owns the row",
        "REQ-2 requires sign-in, but DELETE /notes/{note_id} shows no access check",
        "REQ-5 says users.phone_number is unique, but the database does not enforce it",
        "REQ-6 describes POST /notes/{id}/share, which the backend does not define",
    ]
    likely = _titles(report, "likely")
    assert "DELETE /notes/{note_id} points at REQ-77, which is not a requirement" in likely
    assert "REQ-3 limits POST /admin/purge to administrators, but no role check is visible" in likely
    # The requirement's finding replaces the weaker copy of the same problem.
    assert not [t for t in likely if "without checking who owns" in t or "shows no access check" in t]
    assert [t for t in _titles(report, "unclear") if "table" not in t] == [
        "1 requirement(s) are not linked to any route",
        "1 route(s) that change data trace to no requirement",
    ]
    markdown = app_audit.render_markdown(report)
    assert "| REQ-7 | nothing | nothing | Not linked to code |" in markdown
    assert "| Requirements linked to code | 6 of 7 |" in markdown
    assert "Pass --requirements" not in markdown


def test_requirements_that_are_met_raise_nothing(tmp_path):
    app = (
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.execute('SELECT body FROM notes WHERE id = ? AND user_id = ?', (note_id, user.id))\n"
        "@app.post('/admin/purge')\n"
        "def purge(db=Depends(get_db), user=Depends(require_admin)):\n"
        "    db.execute('DELETE FROM notes')\n"
        "@app.get('/status/{code}')\n"
        "def status(code): ...\n")
    report = _run(tmp_path,
        "REQ-1 A logged-in user sees only their own notes: GET /notes/{id}\n"
        "REQ-2 Only administrators may purge notes: POST /admin/purge.\n"
        "REQ-3 Anyone can read a status page without signing in (GET /status/{code}).\n"
        "REQ-4 Email addresses are unique per user: users email.\n", app)
    assert [f.title for f in report.findings] == ["No route reads or writes table `users`"]
    assert [r.result for r in report.requirements.rows] == [
        "No problem found in what was checked", "No problem found in what was checked",
        "Linked; nothing in the wording could be checked", "No problem found in what was checked"]


def test_requirements_with_no_links_are_not_examined_rather_than_many_findings(tmp_path):
    report = _run(tmp_path, "REQ-1 Users are happy.\nREQ-2 Notes are fast.\n",
                  APP.replace("# Requirement: REQ-2, REQ-77\n", "").replace("    Covers: REQ-3\n", ""))
    assert not [f for f in report.findings if "REQ" in f.title or "requirement" in f.title]
    assert any("none of them names a route" in n for n in report.not_examined)
    assert report.requirements.linked == 0


def test_without_requirements_the_report_says_so(tmp_path):
    (tmp_path / "app.py").write_text(APP)
    report = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert report.requirements is None
    assert any("Pass --requirements" in n for n in report.not_examined)
    assert "## Requirements" not in app_audit.render_markdown(report)


def test_demo_and_command_line(tmp_path):
    out = tmp_path / "audit.md"
    proc = subprocess.run(
        [sys.executable, "cli.py", "audit", str(DEMO), "-r", str(DEMO / "requirements.md"), "-o", str(out)],
        capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    text = out.read_text()
    assert "| Requirements linked to code | 7 of 8 |" in text
    assert "| REQ-2 | GET /api/orders/{order_id} | sign-in, ownership | Problem: no ownership check |" in text
    assert "REQ-8 says customers.phone_number is unique, but the database does not enforce it" in text
    empty = tmp_path / "empty.md"
    empty.write_text("nothing here\n")
    for bad in (empty, tmp_path / "missing.md"):
        proc = subprocess.run([sys.executable, "cli.py", "audit", str(DEMO), "-r", str(bad)],
                              capture_output=True, text=True)
        assert proc.returncode == 2
