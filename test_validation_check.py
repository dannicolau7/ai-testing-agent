"""Test validation (roadmap stage 3): does a test fail when the response is wrong?"""

import json
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import validation


@pytest.fixture
def api():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            status = 404 if self.path.endswith("/missing") else 200
            body = json.dumps({"id": 7, "status": "paid"}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


SUITE = """
import requests

BASE = "{base}"
NO_PROXY = {{"http": None, "https": None}}


def test_checks_status_and_body():
    r = requests.get(BASE + "/orders/7", proxies=NO_PROXY)
    assert r.status_code == 200
    assert r.json()["status"] == "paid"


def test_expects_not_found():
    assert requests.get(BASE + "/orders/missing", proxies=NO_PROXY).status_code == 404


def test_calls_but_checks_nothing():
    requests.get(BASE + "/orders/7", proxies=NO_PROXY)
    assert True


def test_only_checks_a_response_came_back():
    r = requests.get(BASE + "/orders/7", proxies=NO_PROXY)
    assert r is not None


def test_makes_no_request():
    assert 1 + 1 == 2


def test_already_failing():
    assert requests.get(BASE + "/orders/7", proxies=NO_PROXY).status_code == 201
"""


def _suite(tmp_path, base):
    path = tmp_path / "test_orders.py"
    path.write_text(textwrap.dedent(SUITE.format(base=base)))
    return str(path)


def _names(items):
    return sorted(i.rsplit("::", 1)[-1] for i in items)


def test_tests_are_sorted_by_whether_they_notice_a_wrong_response(api, tmp_path):
    result = validation.validate_tests([_suite(tmp_path, api)])
    assert result.problem == ""
    assert _names(result.validated) == ["test_checks_status_and_body", "test_expects_not_found"]
    assert _names(result.not_validating) == [
        "test_calls_but_checks_nothing",
        "test_only_checks_a_response_came_back",
    ]
    assert _names(result.no_request) == ["test_makes_no_request"]
    assert _names(result.failing) == ["test_already_failing"]
    assert not result.ok

    markdown = validation.render_markdown(result)
    assert "## Tests that pass even when the response is wrong" in markdown
    assert "test_calls_but_checks_nothing" in markdown and "does not mean" in markdown


def test_tampering_is_off_in_a_normal_run(api, tmp_path):
    # The plugin must never leak into an ordinary pytest run of the same file.
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", _suite(tmp_path, api),
         "-k", "checks_status_and_body"],
        capture_output=True, text=True,
    )
    assert "1 passed" in proc.stdout, proc.stdout + proc.stderr


def test_nothing_to_run_is_a_problem_not_a_clean_result(tmp_path):
    empty = tmp_path / "test_empty.py"
    empty.write_text("x = 1\n")
    result = validation.validate_tests([str(empty)])
    assert result.problem and not result.ok
    assert "Could not be completed" in validation.render_markdown(result)


def test_command_line(api, tmp_path):
    out = tmp_path / "validation.md"
    proc = subprocess.run(
        [sys.executable, "cli.py", "validate", _suite(tmp_path, api), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Not validating (still passed): 2" in out.read_text()
