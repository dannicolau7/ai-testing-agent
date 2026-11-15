"""What changed between two audits (roadmap stage 8)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import app_audit
import audit_diff

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "audit-demo"


def _copy(tmp_path):
    app = tmp_path / "app"
    shutil.copytree(DEMO, app)
    return app


def _report(app):
    return app_audit.audit(app_audit.build_model(str(app)))


def test_an_unchanged_application_has_no_changes(tmp_path):
    app = _copy(tmp_path)
    baseline = audit_diff.load(audit_diff.to_json(_report(app)))
    change = audit_diff.compare(_report(app), baseline)
    assert change.new == [] and change.fixed == [] and change.ok
    assert sum(change.unchanged.values()) == len(baseline) > 10
    text = audit_diff.render_markdown(change)
    assert "**No change in the audit\'s findings.**" in text and "## New" not in text
    assert "Already there before this change, and still there:" in text


def test_a_new_fault_a_fix_and_moved_code_are_told_apart(tmp_path):
    app = _copy(tmp_path)
    baseline = audit_diff.load(audit_diff.to_json(_report(app)))
    backend = app / "backend" / "app.py"
    source = backend.read_text()
    # Fix one planted fault, add a new one, and push every line down the file.
    source = source.replace("def delete_order(order_id: int, db=Depends(get_db)):",
                            "def delete_order(order_id: int, db=Depends(get_db), user=Depends(current_user)):")
    source = "# a new comment at the top\n# and another\n" + source + (
        "\n\n@app.post(\"/api/orders/{order_id}/cancel\")\n"
        "def cancel_order(order_id: int, db=Depends(get_db), user=Depends(current_user)):\n"
        "    db.execute(\"UPDATE orders SET cancelled = 1 WHERE id = ? AND customer_id = ?\", (order_id, user.id))\n")
    backend.write_text(source)
    change = audit_diff.compare(_report(app), baseline)
    assert [f["title"] for f in change.new if f["group"] == "wrong_now"] == [
        "The code uses column `orders.cancelled`, which the table does not have"]
    assert "The spec says DELETE /api/orders/{order_id} needs authentication, but the code shows no check" in [
        f["title"] for f in change.fixed]
    assert not change.ok
    # Findings that only moved to another line are neither new nor fixed.
    moved = "The code uses column `orders.status`, which the table does not have"
    assert moved not in [f["title"] for f in change.new + change.fixed]
    text = audit_diff.render_markdown(change)
    assert text.splitlines()[2] == "**This change adds 1 problem(s) that are wrong now.**"
    assert text.index("## New") < text.index("## Fixed")


def test_new_things_to_look_at_do_not_fail_the_change(tmp_path):
    app = _copy(tmp_path)
    baseline = audit_diff.load(audit_diff.to_json(_report(app)))
    (app / "db" / "schema.sql").write_text(
        (app / "db" / "schema.sql").read_text() + "\nCREATE TABLE coupons (code TEXT, order_id INTEGER);\n")
    change = audit_diff.compare(_report(app), baseline)
    assert change.ok and {f["group"] for f in change.new} <= {"likely", "unclear"} and change.new
    assert "**No new faults.**" in audit_diff.render_markdown(change)


def test_the_same_finding_twice_counts_twice():
    class F:
        def __init__(self, where):
            self.group, self.title, self.detail, self.where = "likely", "Same title", "", where

    class R:
        findings = [F("a.py:1"), F("a.py:9")]

    one = [{"group": "likely", "title": "Same title", "detail": "", "where": "a.py:4"}]
    change = audit_diff.compare(R, one)
    assert len(change.new) == 1 and change.unchanged == {"likely": 1} and change.fixed == []


def test_a_bad_baseline_is_refused():
    for text in ("not json", "{}", json.dumps({"format": 99, "findings": []}),
                 json.dumps({"format": 1, "findings": [{"title": "x"}]})):
        with pytest.raises(audit_diff.BaselineError):
            audit_diff.load(text)


def test_command_line(tmp_path):
    app = _copy(tmp_path)
    base = tmp_path / "baseline.json"

    def run(*args):
        return subprocess.run([sys.executable, "cli.py", "audit", str(app)] + list(args),
                              capture_output=True, text=True, cwd=str(HERE))

    saved = run("--save", str(base))
    assert saved.returncode == 1 and json.loads(base.read_text())["format"] == 1, "the full audit still reports its faults"
    same = run("--baseline", str(base))
    assert same.returncode == 0 and "No change in the audit" in same.stdout, "known faults do not fail a change"
    (app / "frontend" / "src" / "api.js").write_text(
        (app / "frontend" / "src" / "api.js").read_text() + "export const x = () => fetch('/api/nowhere');\n")
    worse = run("--baseline", str(base), "--save", str(base))
    assert worse.returncode == 1 and "The frontend calls GET /api/nowhere" in worse.stdout
    again = run("--baseline", str(base))
    assert again.returncode == 0, "the baseline was updated after the comparison"
    assert run("--baseline", str(tmp_path / "missing.json")).returncode == 2
