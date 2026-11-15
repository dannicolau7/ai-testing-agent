"""The pipeline must run the generated tests and report what really happened."""

import textwrap

import pytest

from ai_testing_agent import AITestingAgent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    return AITestingAgent(api_key=None, verbose=False)


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    return str(path)


def test_results_come_from_pytest_not_from_assumption(agent, tmp_path):
    agent.state["generated_code"] = [
        _write(tmp_path, "test_good.py", "def test_a():\n    assert 1 + 1 == 2\n"),
        _write(
            tmp_path,
            "test_bad.py",
            """
            def test_ok():
                assert True

            def test_wrong():
                assert 1 + 1 == 3
            """,
        ),
        _write(tmp_path, "test_broken.py", "import does_not_exist\n\ndef test_x():\n    assert True\n"),
    ]
    results = agent.execute_tests()
    by_file = {d["file"].rsplit("/", 1)[-1]: d for d in results["details"]}
    assert by_file["test_good.py"]["status"] == "passed"
    assert by_file["test_bad.py"]["status"] == "failed" and by_file["test_bad.py"]["failed"] == 1
    assert by_file["test_broken.py"]["status"] == "error"
    assert (results["passed"], results["failed"]) == (2, 1) and results["errors"] >= 1
    assert "assert 1 + 1 == 3" in by_file["test_bad.py"]["output"] or "assert (1 + 1) == 3" in (
        by_file["test_bad.py"]["output"]
    )


def test_a_file_with_no_tests_is_an_error_not_a_pass(agent, tmp_path):
    agent.state["generated_code"] = [_write(tmp_path, "test_empty.py", "x = 1\n")]
    results = agent.execute_tests()
    assert results["passed"] == 0 and results["details"][0]["status"] == "error"


def test_placeholders_without_an_api_key_are_skipped_never_passed(agent):
    result = agent.run_autonomous("POST /api/checkout: validate card and process payment")
    assert result["success"], result.get("error")
    results = result["results"]
    assert results["passed"] == 0 and results["failed"] == 0
    assert results["skipped"] >= 1
    assert all(d["status"] in ("skipped", "error") for d in results["details"])


def test_pytest_summary_lines_are_parsed():
    parse = AITestingAgent._parse_pytest_counts
    assert parse("3 passed, 1 failed, 2 skipped in 0.1s") == {
        "passed": 3, "failed": 1, "skipped": 2, "errors": 0,
    }
    assert parse("1 error in 0.02s")["errors"] == 1
    assert parse("2 passed, 2 errors in 1s") == {"passed": 2, "failed": 0, "skipped": 0, "errors": 2}
    assert parse("no summary here") == {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}


def test_model_call_sends_no_sampling_parameter_and_reads_text_blocks():
    import inspect

    source = inspect.getsource(AITestingAgent._call_claude_api)
    assert "temperature=" not in source and "content[0]" not in source
