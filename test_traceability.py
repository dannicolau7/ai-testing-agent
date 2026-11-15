"""Requirement traceability (roadmap stage 2)."""

import subprocess
import sys
import textwrap

import traceability

REQUIREMENTS = """
# Checkout
- REQ-1: A valid card is charged once.
- REQ-2 Expired cards are refused.
| REQ-3 | Refunds need a manager |
See REQ-1 for the charging rules.
US-7: As a user I can log out.
AC-2.1 - The total includes tax.
"""

TESTS = '''
import pytest


@pytest.mark.requirement("REQ-1")
def test_charge():
    pass


def test_expired():
    """Expired cards.

    Covers: REQ-2, REQ-9
    """


# Requirement: US-7
@pytest.mark.slow
def test_logout():
    pass


def test_misc():
    pass


class TestRefunds:
    """Requirement: REQ-3"""

    def test_needs_manager(self):
        pass


def helper_not_a_test():
    """Covers: REQ-1"""
'''


def _report():
    requirements = traceability.extract_requirements(REQUIREMENTS)
    return traceability.build_report(requirements, traceability.scan_test_source(TESTS, "t.py"))


def test_requirements_are_lines_that_start_with_an_id():
    found = {r.id: r.text for r in traceability.extract_requirements(REQUIREMENTS)}
    assert list(found) == ["REQ-1", "REQ-2", "REQ-3", "US-7", "AC-2.1"]
    assert found["REQ-1"] == "A valid card is charged once."
    assert found["REQ-3"] == "Refunds need a manager"
    # A sentence that mentions REQ-1 does not redefine it.
    assert "See" not in found["REQ-1"]


def test_tests_point_at_requirements_three_ways():
    refs = {t.name: t.requirements for t in traceability.scan_test_source(TESTS, "t.py")}
    assert refs == {
        "test_charge": ["REQ-1"],
        "test_expired": ["REQ-2", "REQ-9"],
        "test_logout": ["US-7"],
        "test_misc": [],
        "TestRefunds::test_needs_manager": ["REQ-3"],
    }


def test_report_lists_gaps_not_just_a_percentage():
    report = _report()
    assert [r.id for r in report.uncovered] == ["AC-2.1"]
    assert [t.name for t in report.untraced_tests] == ["test_misc"]
    assert report.unknown_references == {"REQ-9": ["t.py::test_expired"]}
    assert report.coverage == 0.8 and not report.ok
    markdown = traceability.render_markdown(report)
    assert "## Requirements with no test" in markdown and "**AC-2.1** The total includes tax." in markdown
    assert "## Tests that point at a requirement that does not exist" in markdown
    assert "not proof the requirement is met" in markdown


def test_everything_traced_is_ok_and_broken_files_are_ignored():
    requirements = traceability.extract_requirements("REQ-1: one thing")
    tests = traceability.scan_test_source('def test_a():\n    """Covers: REQ-1"""\n', "a.py")
    assert traceability.build_report(requirements, tests).ok
    assert traceability.scan_test_source("def broken(:", "bad.py") == []


def test_command_line(tmp_path):
    (tmp_path / "reqs.md").write_text(REQUIREMENTS)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_checkout.py").write_text(textwrap.dedent(TESTS))
    (tests / "helpers.py").write_text("def test_ignored():\n    pass\n")
    out = tmp_path / "trace.md"
    cli = [sys.executable, "cli.py", "trace", str(tmp_path / "reqs.md"), str(tests), "-o", str(out)]
    result = subprocess.run(cli, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr  # gaps were found
    assert "AC-2.1" in out.read_text() and "test_ignored" not in out.read_text()

    (tmp_path / "empty.md").write_text("no ids here")
    none = subprocess.run(
        [sys.executable, "cli.py", "trace", str(tmp_path / "empty.md"), str(tests)],
        capture_output=True, text=True,
    )
    assert none.returncode == 2 and "No requirement ids found" in none.stdout


# ---- generated tests carry the requirement ids they were written for ----


def test_generated_code_is_tagged_and_then_traces():
    code = textwrap.dedent(
        '''
        import pytest


        @pytest.mark.parametrize("n", [1, 2])
        def test_charge(n):
            assert n


        class TestRefunds:
            def test_needs_manager(self):
                assert True

            def test_already_linked(self):
                """Covers: REQ-9"""


        def helper():
            return 1
        '''
    )
    tagged = traceability.tag_with_requirements(code, ["REQ-1", "REQ-3"])
    refs = {t.name: t.requirements for t in traceability.scan_test_source(tagged, "g.py")}
    assert refs == {
        "test_charge": ["REQ-1", "REQ-3"],
        "TestRefunds::test_needs_manager": ["REQ-1", "REQ-3"],
        "TestRefunds::test_already_linked": ["REQ-9"],  # an existing link is kept
    }
    assert "# Requirement: REQ-1, REQ-3\n@pytest.mark.parametrize" in tagged
    assert "    # Requirement: REQ-1, REQ-3\n    def test_needs_manager" in tagged
    compile(tagged, "g.py", "exec")  # still valid Python
    assert traceability.tag_with_requirements(code, []) == code
    assert traceability.tag_with_requirements("def broken(:", ["REQ-1"]) == "def broken(:"


def test_ids_are_read_only_from_the_requirement_ids_field():
    ids = traceability.requirement_ids_of
    assert ids({"requirement_ids": ["REQ-1", "US-7", "REQ-1"]}) == ["REQ-1", "US-7"]
    assert ids({"requirement_ids": "REQ-2 and AC-2.1"}) == ["REQ-2", "AC-2.1"]
    # Never guessed from a description that happens to mention one.
    assert ids({"description": "like REQ-5 but different"}) == []
    assert ids({"requirement_ids": None}) == [] and ids({"requirement_ids": [5, {}]}) == []


def test_the_pipeline_tags_what_it_generates(tmp_path, monkeypatch):
    from ai_testing_agent import AITestingAgent

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    agent = AITestingAgent(api_key=None, verbose=False)
    agent.state["test_cases"] = [
        {"test_id": "TC900", "test_name": "test_x", "requirement_ids": ["REQ-42"], "description": "d"}
    ]
    files = agent.generate_pytest_code()
    assert "# Requirement: REQ-42" in open(files[0]).read()
