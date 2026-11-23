"""
automation.py — write an automated test suite a team can keep: backend and frontend.

`audit` and `agent` report on an application once. This writes the tests that go on checking
it: a folder with no dependency on this tool, to commit beside the application and run on
every change.

    python cli.py automate path/to/app --url http://localhost:8000 -o automation/

What it writes, and what each test is checked against:

  api/   one set of tests per operation in the application's API spec. The standard is the
         spec, which is what the team has said the API does:
           - it answers with a status the spec documents, and a success carries the fields
             the spec says are required;
           - an operation that needs sign-in refuses a caller who has none;
           - an operation with required fields turns down a body that has none of them.
  ui/    one test per page the browser reached: it loads, throws no error, and none of its
         own requests fail. And one test per journey from a journeys file: the steps work in
         the page, the page sends the request it should, and the backend holds the result.

The standard is never "what the code does today". A test written from the code alone repeats
the code's bugs and calls them correct, so with no API spec no backend tests are written, and
the README says so.

Everything is plain data plus fixed test code: `operations.json`, `pages.json` and
`journeys.json` say what to check, and the test files read them. Regenerate after the
application changes; edit the JSON to add or remove a check.

The same rules as the rest of this tool hold in the suite it writes: a test that could change
data is skipped unless AUTOMATION_ALLOW_WRITES=1, a test that got no answer is skipped and
never passed, and no password, cookie or token is written anywhere.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import app_audit
import live_checks
import request_bodies

MUTATING = ("POST", "PUT", "PATCH", "DELETE")
TEMPLATES = Path(__file__).resolve().parent / "automation_templates"


@dataclass
class Suite:
    files: Dict[str, str] = field(default_factory=dict)
    operations: int = 0
    api_tests: int = 0
    pages: int = 0
    journeys: int = 0
    not_written: List[str] = field(default_factory=list)     # what is missing and why


def _base(spec: dict) -> str:
    return request_bodies._base(spec)


def _documented(operation: dict) -> List[int]:
    codes = []
    for code in (operation.get("responses") or {}):
        if re.fullmatch(r"\d{3}", str(code)):
            codes.append(int(code))
    return sorted(codes)


def _required_in_reply(operation: dict, spec: dict) -> Dict[str, List[str]]:
    """For each documented success, the fields the spec says the JSON reply must carry."""
    out: Dict[str, List[str]] = {}
    for code, reply in (operation.get("responses") or {}).items():
        if not re.fullmatch(r"2\d\d", str(code)) or not isinstance(reply, dict):
            continue
        schema = None
        content = reply.get("content")
        if isinstance(content, dict) and isinstance(content.get("application/json"), dict):
            schema = content["application/json"].get("schema")
        elif "schema" in reply:                      # Swagger 2
            schema = reply["schema"]
        resolved = request_bodies._resolve(schema, spec) if schema is not None else {}
        required = [str(name) for name in (resolved.get("required") or [])
                    if isinstance(resolved.get("properties"), dict) and name in resolved["properties"]]
        if required:
            out[str(code)] = required
    return out


def _required_in_body(operation: dict, spec: dict) -> List[str]:
    content = (operation.get("requestBody") or {}).get("content") if isinstance(
        operation.get("requestBody"), dict) else None
    schema = None
    if isinstance(content, dict):
        for kind in request_bodies.JSON_TYPES + request_bodies.FORM_TYPES:
            if isinstance(content.get(kind), dict):
                schema = content[kind].get("schema")
                break
    else:
        for parameter in operation.get("parameters") or []:
            if isinstance(parameter, dict) and parameter.get("in") == "body":
                schema = parameter.get("schema")
    resolved = request_bodies._resolve(schema, spec) if schema is not None else {}
    return [str(name) for name in (resolved.get("required") or [])]


def operations(spec: dict, model: Optional[app_audit.AppModel] = None) -> List[dict]:
    """One entry per operation in the spec: what to send and what the spec says comes back."""
    out: List[dict] = []
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        return out
    base, bodies = _base(spec), request_bodies.from_spec(spec)
    routes = {r.key: r for r in (model.routes if model else [])}
    for path, item in spec["paths"].items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            method = str(method).upper()
            if method not in ("GET",) + MUTATING or not isinstance(operation, dict):
                continue
            full = base + str(path)
            security = operation.get("security", spec.get("security"))
            route = next((r for key, r in routes.items()
                          if app_audit._match((method, app_audit.normalize_path(full)), {key})), None)
            body = bodies.get(f"{method} {full}")
            out.append({
                "name": f"{method} {full}",
                "method": method,
                "path": full,
                "needs_sign_in": bool(security) or bool(route and route.auth_evidence),
                "body": body,
                "body_required": _required_in_body(operation, spec),
                "documented": _documented(operation),
                "reply_required": _required_in_reply(operation, spec),
                "in_source": f"{route.file}:{route.line}" if route else "",
            })
    out.sort(key=lambda o: (o["path"], o["method"]))
    return out


def _count_api_tests(ops: List[dict]) -> int:
    return sum(1 + bool(o["needs_sign_in"]) + bool(o["body_required"]) for o in ops)


def pages(observation) -> List[dict]:
    """One entry per page the browser reached and got an answer from."""
    seen, out = set(), []
    for page in getattr(observation, "pages", []) or []:
        path = live_checks_path(page.url)
        if path in seen or page.status == 0:
            continue
        seen.add(path)
        console = [e for e in page.console_errors if not e.startswith("Failed to load resource")]
        out.append({"path": path, "status_when_written": page.status,
                    "had_errors_when_written": bool(page.errors or console or page.status >= 400)})
    return out


def live_checks_path(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")


def journeys_data(journeys: Optional[list]) -> List[dict]:
    out = []
    for j in journeys or []:
        out.append({
            "id": j.id, "name": j.name,
            "steps": [{kind: value} for kind, value in j.steps],
            "page_must_call": list(j.page_must_call) if j.page_must_call else None,
            "backend_get": j.backend_get, "backend_contains": j.backend_contains,
            "backend_not_contains": j.backend_not_contains,
        })
    return out


def _dump(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def generate(model: Optional[app_audit.AppModel], spec: Optional[dict], spec_origin: str = "",
             observation=None, journeys: Optional[list] = None, sign_in_text: str = "",
             app_name: str = "the application", why_no_browser: str = "") -> Suite:
    """The suite as file name → text. Nothing is written to disk here."""
    suite = Suite()
    def template(name: str) -> str:
        # Stored as .tmpl so linters do not read a file with a placeholder in it as Python.
        stored = TEMPLATES / (name + ".tmpl" if name.endswith(".py") else name)
        return stored.read_text(encoding="utf-8")

    suite.files["support.py"] = template("support.py").replace("@@HELPERS@@", live_checks.HELPERS)
    suite.files["conftest.py"] = template("conftest.py")
    suite.files["requirements.txt"] = "pytest>=7.4\nrequests>=2.31\npyyaml>=6.0\nplaywright>=1.45\n"
    suite.files["ci-example.yml"] = template("ci-example.yml")
    if sign_in_text:
        suite.files["sign-in.yaml"] = sign_in_text

    ops = operations(spec, model) if spec else []
    if ops:
        suite.operations, suite.api_tests = len(ops), _count_api_tests(ops)
        suite.files["api/operations.json"] = _dump({"from": spec_origin, "operations": ops})
        suite.files["api/test_contract.py"] = template("test_contract.py")
    else:
        suite.not_written.append(
            "Backend tests: no API spec was found, so none were written. A test written from the code alone "
            "would repeat the code's bugs. Give a spec with --spec, or have the application serve one.")

    page_list = pages(observation) if observation is not None else []
    if page_list:
        suite.pages = len(page_list)
        suite.files["ui/pages.json"] = _dump({"pages": page_list})
        suite.files["ui/test_pages.py"] = template("test_pages.py")
    else:
        suite.not_written.append(
            "Page tests: " + (why_no_browser or "the browser reached no page, so none were written."))

    journey_list = journeys_data(journeys)
    if journey_list:
        suite.journeys = len(journey_list)
        suite.files["ui/journeys.json"] = _dump({"journeys": journey_list})
        suite.files["ui/test_journeys.py"] = template("test_journeys.py")
    else:
        suite.not_written.append(
            "Journey tests: no journeys file was given (--journeys). A journey is a requirement carried out "
            "in the page; a person writes the steps.")

    suite.files["README.md"] = _readme(suite, app_name, spec_origin, bool(sign_in_text))
    return suite


def _readme(suite: Suite, app_name: str, spec_origin: str, has_sign_in: bool) -> str:
    lines = [
        f"# Automated tests for {app_name}",
        "",
        "Written by `python cli.py automate`. This folder stands alone: commit it beside the application "
        "and run it on every change.",
        "",
        "## What is here",
        "",
        "| Tests | Count | Checked against |",
        "|---|---|---|",
    ]
    if suite.operations:
        lines.append(f"| `api/` backend | {suite.api_tests} tests for {suite.operations} operations | "
                     f"The API spec ({spec_origin or 'given'}) |")
    if suite.pages:
        lines.append(f"| `ui/test_pages.py` frontend | {suite.pages} pages | Each page loads, throws no error, "
                     "and none of its own requests fail |")
    if suite.journeys:
        lines.append(f"| `ui/test_journeys.py` frontend and backend | {suite.journeys} journeys | The steps work "
                     "in the page, the page sends the right request, and the backend holds the result |")
    lines += ["", "## Not written", ""]
    lines += [f"- {note}" for note in suite.not_written] or ["- Nothing: every kind of test was written."]
    lines += [
        "",
        "## Run it",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "playwright install chromium          # for the ui/ tests",
        "AUTOMATION_BASE_URL=http://localhost:8000 pytest",
        "```",
        "",
        "Run it against a TEST environment only. These tests send real requests.",
        "",
        "| Variable | What it does |",
        "|---|---|",
        "| `AUTOMATION_BASE_URL` | Where the application runs. Without it every test is skipped |",
        "| `AUTOMATION_ALLOW_WRITES=1` | Also run tests that send POST, PUT, PATCH or DELETE. They change data |",
        "| `PATH_IDS` | An id for each path parameter by name: `PATH_IDS=\"id=42,user_id=7\"` |",
        "| `AUTOMATION_USER_TOKEN`, `AUTOMATION_USER_COOKIE` | A signed-in test user, if not using `sign-in.yaml` |",
        "| `AUTOMATION_USER_SCHEME` | The word before the token, if not `Bearer` |",
        "",
    ]
    if has_sign_in:
        lines += ["`sign-in.yaml` says how the test user signs in, so the suite signs in itself. It names the "
                  "environment variables that hold the passwords; set those. No password is in the file.", ""]
    lines += [
        "## How to read a result",
        "",
        "- **Failed:** the application answered, and not as the spec or the journey says it should.",
        "- **Passed:** it answered as it should.",
        "- **Skipped:** the test was not run, and says why: no address, no sign-in, a write that was not "
        "allowed, a row that does not exist, no answer. A skip is never a pass.",
        "",
        "## Changing it",
        "",
        "The `.json` files say what to check and the `.py` files are fixed. Edit the JSON to add or remove a "
        "check, or generate the folder again after the application changes.",
        "",
        "A backend test checks the application against its API spec. If the spec is wrong, the test is wrong "
        "the same way: fix the spec first.",
        "",
    ]
    return "\n".join(lines)


def write(suite: Suite, out_dir: Path) -> List[str]:
    written = []
    for name, text in sorted(suite.files.items()):
        target = out_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(name)
    return written
