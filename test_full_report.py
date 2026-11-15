"""One report from every check."""

import datetime
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import app_audit
import full_report
import permissions
import traceability
import validation

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "audit-demo"


def _parts(tests=True, policy=True):
    requirements = traceability.extract_requirements((DEMO / "requirements.md").read_text())
    table = permissions.load((DEMO / "permissions.yaml").read_text()) if policy else None
    audit = app_audit.audit(app_audit.build_model(str(DEMO)), requirements, policy=table)
    trace = traceability.build_report(requirements, traceability.scan_tests([str(DEMO / "tests")])) if tests else None
    return audit, trace


def test_every_check_is_listed_as_run_or_not_run_with_a_reason():
    audit, trace = _parts()
    report = full_report.build(str(DEMO), audit, trace=trace, requirements_given=True, tests_given=True,
                               today=datetime.date(2026, 1, 2))
    assert [(p.name, p.ran) for p in report.parts] == [
        ("Source audit", True), ("Requirements against code", True), ("Permissions table against code", True),
        ("Browser check", False), ("Tests against requirements", True), ("Whether each test can fail", False)]
    text = full_report.render_markdown(report)
    assert text.startswith("# Application audit report: audit-demo\n\n2026-01-02\n")
    assert "2 of 6 checks were not run, so this is a partial picture." in text.splitlines()[4]
    assert "| Browser check | No | No address of a running test environment was given (--url). |" in text
    assert "- Browser check: not run." in text and "- Whether each test can fail: not run." in text
    assert not report.ok


def test_findings_from_every_check_are_merged_and_marked_with_their_source():
    audit, trace = _parts()
    report = full_report.build(str(DEMO), audit, trace=trace, requirements_given=True, tests_given=True)
    by_source = {s: [i.title for i in report.items if i.source == s] for s in ("Source", "Tests")}
    assert "REQ-8 says customers.phone_number is unique, but the database does not enforce it" in by_source["Source"]
    assert "REQ-4 has no test" in by_source["Tests"] and "REQ-1 has no test" not in by_source["Tests"]
    assert "A test points at REQ-12, which is not a requirement" in by_source["Tests"]
    assert "1 test(s) point at no requirement" in by_source["Tests"]
    groups = [i.group for i in report.items]
    assert groups == sorted(groups, key=["wrong_now", "likely", "unclear"].index), "worst first"
    rows = {r[0]: r for r in report.requirement_rows}
    assert rows["REQ-2"] == ["REQ-2", "GET /api/orders/{order_id}", "sign-in, ownership", "Problem: no ownership check", "1"]
    assert rows["REQ-7"][1:] == ["nothing", "nothing", "Not linked to code", "0"]
    text = full_report.render_markdown(report)
    assert "| GET /api/orders/{order_id} | refuse | allow | allow | yes | sign-in only |" in text
    assert text.index("## Wrong now") < text.index("## Requirements") < text.index("## Permissions") < text.index("## Not examined")


def test_test_results_and_browser_results_are_included_when_given():
    audit, trace = _parts()
    result = validation.ValidationResult(validated=["t::a"], not_validating=["t::b"], failing=["t::c"], no_request=["t::d"])

    class Seen:
        pages, api, clicked, not_visited, start = [1, 2], [1], False, 3, "http://x"

    class Browser:
        seen = Seen
        findings = [app_audit.Finding("wrong_now", "The page /help throws an error", "boom", "/help")]
        routes_never_seen = ["DELETE /api/orders/{order_id}"]

    report = full_report.build(str(DEMO), audit, Browser, trace, result, True, True, "http://x")
    assert all(p.ran for p in report.parts)
    titles = {(i.source, i.group, i.title) for i in report.items}
    assert ("Browser", "wrong_now", "The page /help throws an error") in titles
    assert ("Tests", "wrong_now", "The test t::c fails") in titles
    assert ("Tests", "likely", "The test t::b passes even when the response is wrong") in titles
    text = full_report.render_markdown(report)
    assert "1 proven able to fail, 1 not, 1 already failing, 1 made no request, 0 skipped." in text
    assert "Browser: 3 link(s) were not opened (page limit)." in text
    assert "never seen being called: DELETE /api/orders/{order_id}." in text
    assert "checks were not run" not in text

    broken = full_report.build(str(DEMO), audit, validation=validation.ValidationResult(problem="pytest timed out"),
                               tests_given=True)
    part = [p for p in broken.parts if p.name == "Whether each test can fail"][0]
    assert not part.ran and "pytest timed out" in part.summary, "a run that did not complete is not a pass"


def test_with_nothing_but_source_the_report_says_what_is_missing(tmp_path):
    (tmp_path / "app.py").write_text("@app.get('/x')\ndef x(user=Depends(current_user)): ...\n")
    report = full_report.build(str(tmp_path), app_audit.audit(app_audit.build_model(str(tmp_path))))
    assert report.ok and [p.ran for p in report.parts] == [True, False, False, False, False, False]
    text = full_report.render_markdown(report)
    assert "**Nothing found wrong in what was checked.** 5 of 6 checks were not run" in text
    assert "## Requirements" not in text and "## Permissions" not in text


class _Check(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.open, self.tags, self.external = [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag not in ("meta", "br"):
            self.open.append(tag)
        self.external += [v for k, v in attrs if k in ("src", "href")]

    def handle_endtag(self, tag):
        assert self.open and self.open.pop() == tag, f"unbalanced </{tag}>"


def test_html_is_self_contained_and_escapes_what_it_is_given():
    audit, trace = _parts()
    markdown = full_report.render_markdown(full_report.build(str(DEMO), audit, trace=trace))
    page = full_report.to_html(markdown + "\n- **<script>alert(1)</script>**\n  detail with <b>tags</b> `code<i>`\n")
    parsed = _Check(page)
    assert parsed.open == [] and parsed.external == [], "balanced, and nothing loaded from elsewhere"
    assert "script" not in parsed.tags and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<code>code&lt;i&gt;</code>" in page and 'name="viewport"' in page
    assert parsed.tags.count("table") == len([x for x in markdown.splitlines() if x.startswith("|---")]) and parsed.tags.count("h2") == markdown.count("\n## ")


def test_command_line(tmp_path):
    md, page = tmp_path / "r.md", tmp_path / "r.html"
    run = subprocess.run(
        [sys.executable, "cli.py", "full-report", str(DEMO), "-r", str(DEMO / "requirements.md"),
         "-p", str(DEMO / "permissions.yaml"), "--tests", str(DEMO / "tests"), "-o", str(md), "--html", str(page)],
        capture_output=True, text=True, cwd=str(HERE))
    assert run.returncode == 1, run.stdout + run.stderr
    assert "## What was run" in md.read_text() and page.read_text().startswith("<!DOCTYPE html>")
    plain = subprocess.run([sys.executable, "cli.py", "full-report", str(DEMO)], capture_output=True, text=True, cwd=str(HERE))
    assert plain.returncode == 1 and "# Application audit report: audit-demo" in plain.stdout
    for args in ([str(tmp_path / "nope")], [str(DEMO), "--links", str(md)], [str(DEMO), "-r", str(tmp_path / "nope.md")]):
        assert subprocess.run([sys.executable, "cli.py", "full-report"] + args, capture_output=True, text=True,
                              cwd=str(HERE)).returncode == 2
    # The older `report` command is still there.
    assert subprocess.run([sys.executable, "cli.py", "report", "--help"], capture_output=True, cwd=str(HERE)).returncode == 0
