"""The agent remembers earlier runs, and says what changed."""

import datetime
import json
import threading
from http.server import HTTPServer

import pytest

import agent
import agent_memory
import permissions
import test_permissions as roles_app
from test_agent import ROLE_SOURCE, ROLE_TABLE


class _App(roles_app._App):
    """The planted hole (any user can purge) can be switched off, like a fix being deployed."""

    fixed = False

    def _answer(self):
        token = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        if _App.fixed and self.path == "/admin/purge" and token == "u-token":
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super()._answer()

    do_GET = do_POST = do_DELETE = _answer  # noqa: N815


@pytest.fixture
def app(tmp_path, monkeypatch):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "app.py").write_text(ROLE_SOURCE)
    _App.fixed = False
    httpd = HTTPServer(("127.0.0.1", 0), _App)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("ROLE_USER_TOKEN", "u-token")
    monkeypatch.setenv("ROLE_ADMIN_TOKEN", "a-token")
    yield agent.Config(path=str(folder), policy=permissions.load(ROLE_TABLE), browse=False, allow_writes=True,
                       url=f"http://127.0.0.1:{httpd.server_port}", memory=str(tmp_path / "memory.json"))
    httpd.shutdown()
    httpd.server_close()


def _day(n):
    return datetime.date(2026, 11, n)


HOLE = "user may not POST /admin/purge"


def test_the_first_run_has_nothing_to_compare_with_and_is_remembered(app):
    run = agent.run(app, today=_day(1))
    assert run.changes is None and run.remembered
    step = next(s for s in run.steps if s.name == "Compare with the last run")
    assert step.status == "done" and step.detail == "the first run remembered"
    assert "This is the first run remembered" in agent.render_markdown(run)
    saved = json.loads(open(app.memory).read())
    assert saved["format"] == agent_memory.FORMAT and len(saved["runs"]) == 1
    assert saved["runs"][0]["states"][f"cell: {HOLE}"] == "wrong"


def test_fixed_then_back_again(app):
    agent.run(app, today=_day(1))                       # the hole is there

    second = agent.run(app, today=_day(2))              # nothing changed
    assert [what for what, _ in second.changes.still_wrong] == [HOLE]
    assert second.changes.still_wrong[0][1] == "2026-11-01", "the date it was first seen"
    assert not second.changes.new and not second.changes.fixed

    _App.fixed = True
    third = agent.run(app, today=_day(3))               # fixed
    assert third.changes.fixed == [HOLE] and third.ok
    assert not third.changes.new and not third.changes.back_again
    assert "| Fixed | 1 |" in agent.render_markdown(third)

    _App.fixed = False
    fourth = agent.run(app, today=_day(4))              # the fix came undone
    assert fourth.changes.back_again == [HOLE] and not fourth.changes.new
    text = agent.render_markdown(fourth)
    assert "**Back again.** Wrong now, fine last time, and wrong in an earlier run. A fix came undone." in text
    assert any("fixed are back" in line for line in fourth.needs_person)
    assert "since_last_run" in agent.to_json(fourth) and json.loads(agent.to_json(fourth))["since_last_run"]["since"] == "2026-11-03"


def test_a_check_that_stops_running_is_reported_not_passed(app, monkeypatch):
    agent.run(app, today=_day(1))
    monkeypatch.delenv("ROLE_USER_TOKEN")               # the user's token is gone: those cells cannot run
    second = agent.run(app, today=_day(2))
    stopped = second.changes.stopped_running
    assert f"{HOLE} (was wrong)" in stopped and any("(was fine)" in item for item in stopped)
    # The hole was not fixed. It was not looked at. It must not show as fixed.
    assert HOLE not in second.changes.fixed
    text = agent.render_markdown(second)
    assert "These were not passed; they were lost." in text
    assert any("did not run this time" in line for line in second.needs_person)


def test_a_new_fault_is_new(app):
    _App.fixed = True
    first = agent.run(app, today=_day(1))
    assert first.ok
    _App.fixed = False
    second = agent.run(app, today=_day(2))
    assert second.changes.new == [HOLE] and not second.changes.back_again


def test_the_memory_holds_names_and_states_only(app, monkeypatch):
    monkeypatch.setenv("ROLE_USER_TOKEN", "u-token")
    agent.run(app, today=_day(1))
    text = open(app.memory).read()
    for secret in ("u-token", "a-token", "Depends(", "def purge"):
        assert secret not in text
    record = json.loads(text)["runs"][0]
    assert set(record) == {"date", "commit", "ok", "states"}
    assert set(record["states"].values()) <= {"wrong", "fine", "not run", "likely", "unclear"}


def test_a_file_that_is_not_a_memory_is_refused_and_left_alone(app, tmp_path):
    other = tmp_path / "notes.json"
    other.write_text('{"mine": true}')
    app.memory = str(other)
    run = agent.run(app, today=_day(1))
    step = next(s for s in run.steps if s.name == "Compare with the last run")
    assert step.status == "failed" and "is not an agent memory file" in step.detail
    assert other.read_text() == '{"mine": true}', "someone else's file is never written over"
    assert not run.remembered and "Since the last run" not in agent.render_markdown(run)

    app.memory = ""
    run = agent.run(app, today=_day(1))
    assert next(s for s in run.steps if s.name == "Compare with the last run").status == "not run"


def test_only_the_last_fifty_runs_are_kept(tmp_path):
    path = tmp_path / "m.json"
    runs = [{"date": f"d{i}", "commit": "", "ok": True, "states": {}} for i in range(60)]
    agent_memory.save(path, runs)
    kept = agent_memory.load(path)
    assert len(kept) == 50 and kept[0]["date"] == "d10" and kept[-1]["date"] == "d59"
    assert agent_memory.load(tmp_path / "missing.json") == []
