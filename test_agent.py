"""The audit agent: it tests its own suspicions, and says what it did not do."""

import json
import os
import subprocess
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

import agent
import app_audit
import model_backend
import test_finding_tests as live
import traceability

HERE = Path(__file__).resolve().parent
DEMO = HERE / "examples" / "audit-demo"


@pytest.fixture
def source(tmp_path):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "app.py").write_text(live.SOURCE)
    (folder / "schema.sql").write_text(live.SCHEMA)
    (folder / "ui.js").write_text(live.FRONTEND)
    return folder


@pytest.fixture
def server(monkeypatch):
    live._App.deleted.clear()
    httpd = HTTPServer(("127.0.0.1", 0), live._App)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("FINDINGS_USER_TOKEN", "user-a")
    monkeypatch.setenv("FINDINGS_OTHER_ID", "42")
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


def _config(source, **options):
    return agent.Config(path=str(source), requirements=traceability.extract_requirements(live.REQUIREMENTS),
                        browse=False, **options)


def _verdicts(run):
    return {(c.method, c.path): c.verdict for c in run.confirmations}


def test_each_suspicion_is_tested_and_sorted_by_what_happened(source, server):
    run = agent.run(_config(source, url=server, allow_writes=True), workdir=source.parent / "work")
    assert _verdicts(run) == {
        ("POST", "/notes/{id}/share"): "confirmed",
        ("GET", "/notes/{note_id}"): "confirmed",
        ("DELETE", "/notes/{note_id}"): "confirmed",
        ("POST", "/feedback"): "cleared",
    }
    wrong = [i.title for i in run.report.items if i.group == "wrong_now"]
    assert len(wrong) == 3 and not run.ok
    assert all("Confirmed by a request to the running system" in i.detail
               for i in run.report.items if i.group == "wrong_now")
    # The false alarm is gone from every list, and listed as cleared.
    assert [f.title for f in run.cleared] == ["POST /feedback changes data and shows no access check"]
    assert all("POST /feedback changes data" not in i.title for i in run.report.items)
    text = agent.render_markdown(run)
    assert "| Cleared |" in text and "Fault is real" in text
    assert "Source: The running application was asked about the findings it could settle" in text
    assert live._App.deleted == ["/notes/1"], "writes were allowed, so the delete was really sent"


def test_nothing_that_changes_data_is_sent_without_permission(source, server):
    run = agent.run(_config(source, url=server))
    assert live._App.deleted == []
    verdicts = _verdicts(run)
    assert verdicts[("GET", "/notes/{note_id}")] == "confirmed"
    # Not run is not cleared, and the finding stays where it was.
    assert verdicts[("DELETE", "/notes/{note_id}")] == "not run"
    assert verdicts[("POST", "/feedback")] == "not run"
    assert any("REQ-2 requires sign-in" in i.title for i in run.report.items)
    assert run.cleared == []
    assert any("FINDINGS_ALLOW_WRITES=1" in line or "may change data" in line for line in run.needs_person)
    assert "- Requests that change data: not sent." in agent.render_markdown(run)


def test_a_missing_sign_in_leaves_ownership_untested_not_cleared(source, server, monkeypatch):
    monkeypatch.delenv("FINDINGS_USER_TOKEN")
    monkeypatch.delenv("FINDINGS_OTHER_ID")
    run = agent.run(_config(source, url=server, allow_writes=True))
    assert _verdicts(run)[("GET", "/notes/{note_id}")] == "not run"
    assert any("FINDINGS_USER_TOKEN is not set" in line for line in run.needs_person)


def test_no_answer_is_not_evidence_either_way(source):
    run = agent.run(_config(source, url="http://127.0.0.1:9"))
    assert run.confirmations == [] and run.cleared == []
    step = next(s for s in run.steps if s.name == "Test the findings")
    assert step.status == "failed" and "nothing answered" in step.detail
    assert next(s for s in run.steps if s.name == "Browse the application").status == "not run"
    wrong = [i.title for i in run.report.items if i.group == "wrong_now"]
    assert not any("Confirmed" in i.detail for i in run.report.items)
    assert len(wrong) == 0 or all("Confirmed" not in i.detail for i in run.report.items)


def test_without_an_address_nothing_is_sent_anywhere(source):
    run = agent.run(_config(source))
    assert run.confirmations == [] and run.where["url"] == ""
    assert [s.status for s in run.steps if s.name in ("Test the findings", "Browse the application")] == ["not run"] * 2
    text = agent.render_markdown(run)
    assert "no address of a test environment was given" in text and "Where it ran" not in text


def test_only_a_failed_assertion_counts_as_a_fault():
    assert agent._assertion("AssertionError: DELETE /x let a caller through: 204\nassert 204 in (401, 403)") == \
        "DELETE /x let a caller through: 204"
    for broken in ("NameError: name 'x' is not defined", "ConnectionError: refused", "", "assert False"):
        assert agent._assertion(broken) is None


def test_it_refuses_machines_it_has_no_permission_for():
    assert agent.check_environment("http://127.0.0.1:8000") is True
    assert agent.check_environment("http://localhost:3000/app") is True
    with pytest.raises(agent.Refused, match="not on this machine"):
        agent.check_environment("https://staging.example.org")
    with pytest.raises(agent.Refused, match="not on this machine"):
        agent.check_environment("https://staging.example.org", "ok")
    permission = "Rules of engagement signed by the owner, 2026-11-01, file RoE-7"
    assert agent.check_environment("https://staging.example.org", permission) is False
    for bad in ("ftp://127.0.0.1", "127.0.0.1:8000", "file:///etc/passwd", "http://"):
        with pytest.raises(agent.Refused, match="http"):
            agent.check_environment(bad, permission)
    with pytest.raises(agent.Refused, match="user name or password"):
        agent.check_environment("http://user:pw@127.0.0.1:8000")
    with pytest.raises(agent.Refused):
        agent.run(agent.Config(path=str(DEMO), url="https://staging.example.org"))


def test_secrets_are_never_written_down(source, server, monkeypatch, tmp_path):
    monkeypatch.setenv("FINDINGS_USER_TOKEN", "super-secret-token-9917")
    run = agent.run(_config(source, url=server, allow_writes=True))
    out = tmp_path / "out"
    agent.write_outputs(run, out)
    for name in ("report.md", "report.html", "run.json", "tests-from-findings.py"):
        assert "super-secret-token-9917" not in (out / name).read_text(), name
    assert run.where["token_variables_set"] == ["FINDINGS_USER_TOKEN", "FINDINGS_OTHER_ID"]


class _Model:
    """Stands in for a model: answers with a fixed number, and records what it was sent."""

    def __init__(self, answer="1"):
        self.answer, self.prompts = answer, []

    def describe(self):
        return "a test model"

    def complete(self, prompt, max_tokens=6):
        self.prompts.append(prompt)
        return self.answer


def _plain(**options):
    reqs = traceability.extract_requirements((DEMO / "requirements-plain.md").read_text())
    return agent.Config(path=str(DEMO), requirements=reqs, browse=False, **options)


def test_what_a_model_proposed_never_reaches_the_verdict(tmp_path):
    without = agent.run(_plain())
    model = _Model("2")
    run = agent.run(_plain(backend=model))
    # The verdict and every counted finding are exactly what they were without the model.
    assert run.ok == without.ok
    assert [(i.group, i.title) for i in run.report.items] == [(i.group, i.title) for i in without.report.items]
    assert run.proposed_links and all(len(p.routes) <= 1 for p in run.proposed_links)
    assert model.prompts and all("def " not in p and "SELECT" not in p for p in model.prompts), "no source code sent"
    text = agent.render_markdown(run)
    assert "Needs a person" in text and "requirement-links.yaml" in text
    if run.provisional:
        assert "If the proposed links are right" in text
        assert not any(f.title in [i.title for i in run.report.items] for f in run.provisional)
    written = agent.write_outputs(run, tmp_path / "out")
    assert "requirement-links.yaml" in written
    assert "confirmed: false" in (tmp_path / "out" / "requirement-links.yaml").read_text()
    saved = (tmp_path / "out" / "requirement-links.yaml").read_text()
    assert not [line for line in saved.splitlines() if line.strip() == "confirmed: true"]


def test_a_model_that_fails_stops_nothing_else(tmp_path):
    class Broken(_Model):
        def complete(self, prompt, max_tokens=6):
            raise model_backend.ModelError("the model server is not running")

    run = agent.run(_plain(backend=Broken()))
    step = next(s for s in run.steps if s.name == "Propose links")
    assert step.status == "failed" and "not running" in step.detail
    assert run.proposed_links == [] and run.report.items
    assert agent.run(_plain()).ok == run.ok
    none = next(s for s in agent.run(_plain()).steps if s.name == "Propose links")
    assert none.status == "not run" and "no model is configured" in none.detail


def test_the_run_record_is_stable_and_lists_every_step(source, server, tmp_path):
    cfg = _config(source, url=server, allow_writes=True)
    first, second = agent.run(cfg), agent.run(cfg)
    a, b = json.loads(agent.to_json(first)), json.loads(agent.to_json(second))
    assert a == b
    assert [s["name"] for s in a["steps"]] == ["Read the source", "Propose links", "Test the findings",
                                               "Browse the application", "Carry out journeys"]
    assert a["ok"] is False and set(a) >= {"where", "confirmations", "cleared", "needs_person", "steps"}
    written = agent.write_outputs(first, tmp_path / "out")
    assert written == ["report.md", "report.html", "run.json", "tests-from-findings.py"]
    compile((tmp_path / "out" / "tests-from-findings.py").read_text(), "generated", "exec")


def test_generated_tests_say_not_run_when_nothing_answers():
    text = finding_tests_text()
    assert "could not reach" in text and "pytest.skip" in text


def finding_tests_text():
    import finding_tests

    report = app_audit.audit(app_audit.build_model(str(DEMO)))
    return finding_tests.generate(report.findings)[0]


def test_command_line(tmp_path):
    out = tmp_path / "run"
    result = subprocess.run([sys.executable, "cli.py", "agent", str(DEMO), "-r", str(DEMO / "requirements.md"),
                             "--no-model", "--out-dir", str(out)], capture_output=True, text=True, cwd=str(HERE),
                            env={k: v for k, v in os.environ.items() if k != "ATA_MODEL_URL"})
    assert result.returncode in (0, 1), result.stderr
    assert "[done] Read the source" in result.stdout and "[not run] Test the findings" in result.stdout
    assert (out / "report.md").is_file() and (out / "run.json").is_file()

    refused = subprocess.run([sys.executable, "cli.py", "agent", str(DEMO), "--url", "https://staging.example.org"],
                             capture_output=True, text=True, cwd=str(HERE))
    assert refused.returncode == 2 and "--authorization" in refused.stdout
    assert subprocess.run([sys.executable, "cli.py", "agent", str(tmp_path / "nope")], capture_output=True,
                          text=True, cwd=str(HERE)).returncode == 2
