"""
tamper_plugin.py — a pytest plugin that makes every HTTP response wrong.

Used by validation.py (stage 3 of docs/ROADMAP.md). Loaded only when a validation run asks
for it: `pytest -p tamper_plugin` with ATA_TAMPER_REPORT set. It is never active in a
normal test run.

While it is active, every response that comes back through `requests` is replaced:

- a success (status below 400) becomes a 500 with an empty JSON object as its body;
- a failure (400 and above) becomes a 200 with an empty JSON object as its body.

A test that still passes did not check the response it received. The plugin also counts the
requests each test made, so a test that made none can be reported as such, not as weak.
"""

import json
import os

import pytest

_counts = {}
_current = {"nodeid": None}


def _tamper(response):
    response.status_code = 500 if response.status_code < 400 else 200
    response.reason = "Tampered"
    response._content = b"{}"
    response._content_consumed = True
    response.headers["Content-Type"] = "application/json"
    response.headers.pop("Content-Encoding", None)
    return response


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    # Keyed by real file path, so the caller can match tests whatever directory it ran from.
    key = os.path.realpath(str(item.fspath)) + "::" + item.nodeid.split("::", 1)[-1]
    _current["nodeid"] = key
    _counts.setdefault(key, 0)
    yield
    _current["nodeid"] = None


def pytest_configure(config):
    try:
        import requests
    except ImportError:  # nothing to intercept
        return
    original = requests.Session.send

    def send(self, request, **kwargs):
        response = original(self, request, **kwargs)
        if _current["nodeid"] is not None:
            _counts[_current["nodeid"]] = _counts.get(_current["nodeid"], 0) + 1
        return _tamper(response)

    requests.Session.send = send
    config._ata_original_send = original


def pytest_unconfigure(config):
    original = getattr(config, "_ata_original_send", None)
    if original is not None:
        import requests

        requests.Session.send = original
    path = os.environ.get("ATA_TAMPER_REPORT")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(_counts, handle)
