"""
Tests for failure_analyzer.py

Covers: pytest output parsing, FailureRecord extraction, mock analysis
classification, report formatting, and AI response parsing.
"""

import textwrap
import pytest

from failure_analyzer import FailureAnalyzer, FailureRecord, FailureAnalysis


# ── Sample pytest output ──────────────────────────────────────────────────────

ASSERTION_ERROR_OUTPUT = textwrap.dedent("""
    ============================= test session starts ==============================
    collected 3 items

    test_output/test_pets.py::test_listPets_success PASSED
    test_output/test_pets.py::test_createPet_success FAILED
    test_output/test_pets.py::test_getPet_not_found FAILED

    ================================== FAILURES ===================================
    _________________________ test_createPet_success __________________________

        def test_createPet_success(api_client):
            \"\"\"Create a pet — expects 201.\"\"\"
            url = f'{BASE_URL}/pets'
            payload = {"name": "Fluffy", "tag": "cat"}
            response = api_client.post(url, json=payload)
    >       assert response.status_code == 201
    E       AssertionError: assert 405 == 201

    test_output/test_pets.py:37: AssertionError
    _________________________ test_getPet_not_found ____________________________

        def test_getPet_not_found(api_client):
            \"\"\"GET /pets/{petId} with non-existent ID — expects 404.\"\"\"
            url = f'https://petstore.swagger.io/v2/pets/99999'
    >       response = api_client.get(url)
    >       assert response.status_code == 404
    E       AssertionError: assert 200 == 404

    test_output/test_pets.py:64: AssertionError
    =========================== short test summary info ============================
    FAILED test_output/test_pets.py::test_createPet_success
    FAILED test_output/test_pets.py::test_getPet_not_found
    2 failed, 1 passed in 1.23s
""").strip()

CONNECTION_ERROR_OUTPUT = textwrap.dedent("""
    ================================== FAILURES ===================================
    _________________________ test_listPets_success ____________________________

        def test_listPets_success(api_client):
            url = f'{BASE_URL}/pets'
    >       response = api_client.get(url)
    E       requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=8080):
    E       Max retries exceeded. Caused by: Failed to establish a new connection.

    test_output/test_pets.py:23: ConnectionError
    =========================== short test summary info ============================
    FAILED test_output/test_pets.py::test_listPets_success
    1 failed in 0.45s
""").strip()

MISSING_KEY_OUTPUT = textwrap.dedent("""
    ================================== FAILURES ===================================
    _________________________ test_createPet_success ____________________________

        def test_createPet_success(api_client):
            response = api_client.post(url, json=payload)
            data = response.json()
    >       assert "id" in data
    E       AssertionError: assert 'id' in {'petId': 1, 'name': 'Fluffy'}

    test_output/test_pets.py:40: AssertionError
    =========================== short test summary info ============================
    FAILED test_output/test_pets.py::test_createPet_success
    1 failed in 0.89s
""").strip()

AUTH_FAILURE_OUTPUT = textwrap.dedent("""
    ================================== FAILURES ===================================
    _________________________ test_list_users_success __________________________

        def test_list_users_success(api_client):
    >       response = api_client.get(url)
    E       AssertionError: assert 401 == 200

    test_users.py:18: AssertionError
    =========================== short test summary info ============================
    FAILED test_users.py::test_list_users_success
    1 failed in 0.33s
""").strip()

JSON_DECODE_OUTPUT = textwrap.dedent("""
    ================================== FAILURES ===================================
    _________________________ test_parse_response ______________________________

        def test_parse_response(api_client):
    >       data = response.json()
    E       json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

    test_api.py:55: JSONDecodeError
    =========================== short test summary info ============================
    FAILED test_api.py::test_parse_response
    1 failed in 0.12s
""").strip()

TIMEOUT_OUTPUT = textwrap.dedent("""
    ================================== FAILURES ===================================
    _________________________ test_slow_endpoint _______________________________

        def test_slow_endpoint(api_client):
    >       response = api_client.get(url, timeout=5)
    E       requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.example.com', port=443):
    E       Read timed out. (read timeout=5)

    test_api.py:70: ReadTimeout
    =========================== short test summary info ============================
    FAILED test_api.py::test_slow_endpoint
    1 failed in 5.01s
""").strip()

NO_FAILURES_OUTPUT = textwrap.dedent("""
    ============================= test session starts ==============================
    collected 3 items

    test_pets.py::test_listPets_success PASSED
    test_pets.py::test_createPet_success PASSED
    test_pets.py::test_getPet_not_found PASSED

    ============================== 3 passed in 0.82s ==============================
""").strip()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def analyzer():
    return FailureAnalyzer()


# ── parse_failures ─────────────────────────────────────────────────────────────

def test_parse_no_failures_returns_empty(analyzer):
    failures = analyzer.parse_failures(NO_FAILURES_OUTPUT)
    assert failures == []


def test_parse_two_assertion_errors(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    assert len(failures) == 2


def test_parse_failure_names(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    names = {f.test_name for f in failures}
    assert "test_createPet_success" in names
    assert "test_getPet_not_found" in names


def test_parse_failure_error_type_assertion(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    create_failure = next(f for f in failures if "createPet" in f.test_name)
    assert create_failure.error_type == "AssertionError"


def test_parse_failure_short_message_contains_values(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    create_failure = next(f for f in failures if "createPet" in f.test_name)
    assert "405" in create_failure.short_message or "201" in create_failure.short_message


def test_parse_failure_traceback_contains_code(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    create_failure = next(f for f in failures if "createPet" in f.test_name)
    assert "assert response.status_code" in create_failure.traceback


def test_parse_connection_error(analyzer):
    failures = analyzer.parse_failures(CONNECTION_ERROR_OUTPUT)
    assert len(failures) == 1
    assert failures[0].test_name == "test_listPets_success"
    assert "ConnectionError" in failures[0].error_type or "Error" in failures[0].error_type


def test_parse_single_missing_key_failure(analyzer):
    failures = analyzer.parse_failures(MISSING_KEY_OUTPUT)
    assert len(failures) == 1
    assert failures[0].test_name == "test_createPet_success"


def test_parse_json_decode_error(analyzer):
    failures = analyzer.parse_failures(JSON_DECODE_OUTPUT)
    assert len(failures) == 1


def test_parse_failure_file_extracted(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    create_failure = next(f for f in failures if "createPet" in f.test_name)
    assert "test_pets" in create_failure.test_file


# ── Mock analysis classification ──────────────────────────────────────────────

def test_mock_connection_error_is_critical(analyzer):
    failures = analyzer.parse_failures(CONNECTION_ERROR_OUTPUT)
    analysis = analyzer.analyze_failure(failures[0], call_ai_fn=None)
    assert analysis.severity == "critical"
    assert analysis.is_mock is True


def test_mock_auth_failure_is_critical(analyzer):
    failures = analyzer.parse_failures(AUTH_FAILURE_OUTPUT)
    analysis = analyzer.analyze_failure(failures[0], call_ai_fn=None)
    assert analysis.severity == "critical"


def test_mock_json_decode_is_high(analyzer):
    failures = analyzer.parse_failures(JSON_DECODE_OUTPUT)
    analysis = analyzer.analyze_failure(failures[0], call_ai_fn=None)
    assert analysis.severity == "high"


def test_mock_timeout_is_high(analyzer):
    failures = analyzer.parse_failures(TIMEOUT_OUTPUT)
    analysis = analyzer.analyze_failure(failures[0], call_ai_fn=None)
    assert analysis.severity == "high"


def test_mock_assertion_error_has_reasonable_cause(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    create_failure = next(f for f in failures if "createPet" in f.test_name)
    analysis = analyzer.analyze_failure(create_failure, call_ai_fn=None)
    assert len(analysis.likely_cause) > 10
    assert len(analysis.recommended_action) > 10


def test_mock_analysis_test_name_preserved(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    for failure in failures:
        analysis = analyzer.analyze_failure(failure, call_ai_fn=None)
        assert analysis.test_name == failure.test_name


# ── AI response parsing ────────────────────────────────────────────────────────

def test_parse_valid_ai_response(analyzer):
    fake_ai_response = """
    {
      "severity": "high",
      "likely_cause": "The API returned 405 because POST is not allowed on this endpoint.",
      "recommended_action": "Check if the server accepts POST or update the test to match.",
      "code_suggestion": "assert response.status_code in [200, 201]"
    }
    """
    dummy_failure = FailureRecord(
        test_id="test_foo",
        test_name="test_foo",
        test_file="test_x.py",
        error_type="AssertionError",
        short_message="assert 405 == 201",
        traceback="...",
    )
    analysis = analyzer._parse_ai_response(fake_ai_response, "test_foo")
    assert analysis is not None
    assert analysis.severity == "high"
    assert "405" in analysis.likely_cause
    assert analysis.is_mock is False


def test_parse_ai_response_with_markdown_fences(analyzer):
    fenced = "```json\n{\"severity\": \"medium\", \"likely_cause\": \"test\", \"recommended_action\": \"fix\", \"code_suggestion\": \"\"}\n```"
    analysis = analyzer._parse_ai_response(fenced, "test_foo")
    assert analysis is not None
    assert analysis.severity == "medium"


def test_parse_invalid_ai_response_returns_none(analyzer):
    assert analyzer._parse_ai_response("not json at all", "test_foo") is None


def test_parse_unknown_severity_defaults_to_medium(analyzer):
    bad_severity = '{"severity": "extreme", "likely_cause": "x", "recommended_action": "y", "code_suggestion": ""}'
    analysis = analyzer._parse_ai_response(bad_severity, "test_foo")
    assert analysis is not None
    assert analysis.severity == "medium"


# ── analyze_all ───────────────────────────────────────────────────────────────

def test_analyze_all_returns_one_per_failure(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    analyses = analyzer.analyze_all(failures, call_ai_fn=None)
    assert len(analyses) == len(failures)


def test_analyze_all_with_no_failures(analyzer):
    assert analyzer.analyze_all([], call_ai_fn=None) == []


# ── format_report ─────────────────────────────────────────────────────────────

def test_format_report_no_analyses(analyzer):
    report = analyzer.format_report([])
    assert "No failures" in report


def test_format_report_contains_test_names(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    analyses = analyzer.analyze_all(failures, call_ai_fn=None)
    report = analyzer.format_report(analyses)
    assert "test_createPet_success" in report
    assert "test_getPet_not_found" in report


def test_format_report_contains_severity(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    analyses = analyzer.analyze_all(failures, call_ai_fn=None)
    report = analyzer.format_report(analyses)
    assert "Severity" in report


def test_format_report_sorted_by_severity(analyzer):
    """Critical failures should appear before lower-severity ones."""
    failures = analyzer.parse_failures(
        CONNECTION_ERROR_OUTPUT + "\n" + MISSING_KEY_OUTPUT
    )
    analyses = analyzer.analyze_all(failures, call_ai_fn=None)
    report = analyzer.format_report(analyses)
    crit_pos = report.find("CRITICAL")
    medium_pos = report.find("MEDIUM")
    if crit_pos >= 0 and medium_pos >= 0:
        assert crit_pos < medium_pos


def test_format_json_structure(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    analyses = analyzer.analyze_all(failures, call_ai_fn=None)
    json_out = analyzer.format_json(analyses)
    assert isinstance(json_out, list)
    assert len(json_out) == 2
    for item in json_out:
        assert "test_name" in item
        assert "severity" in item
        assert "likely_cause" in item
        assert "recommended_action" in item


# ── Prompt building ───────────────────────────────────────────────────────────

def test_prompt_contains_test_name(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    prompt = analyzer._build_prompt(failures[0])
    assert failures[0].test_name in prompt


def test_prompt_contains_error_type(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    prompt = analyzer._build_prompt(failures[0])
    assert failures[0].error_type in prompt


def test_prompt_requests_json_output(analyzer):
    failures = analyzer.parse_failures(ASSERTION_ERROR_OUTPUT)
    prompt = analyzer._build_prompt(failures[0])
    assert "JSON" in prompt
    assert "severity" in prompt
