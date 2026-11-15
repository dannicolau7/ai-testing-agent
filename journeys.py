"""
journeys.py — carry out a requirement in the page, then check the backend agrees.

Stage 7 of docs/ROADMAP.md, second step. The browser check (`browse`) only watches pages
load. A journey does what a user would do for one requirement and checks three things:

1. the steps can be carried out in the page, and the page shows what it should;
2. the page sent the request it was supposed to, and the server accepted it;
3. afterwards the backend really holds the result.

The third is the point. A page that says "Saved" while the server stored nothing looks
fine to a user and to a test that only reads the page.

A journey is written by a person, in a small file:

    journeys:
      - id: REQ-4
        name: A user can add a note
        steps:
          - open: /notes
          - fill: {field: Title, value: Buy milk}
          - click: Save
          - see: Buy milk
        page_must_call: POST /api/notes
        backend_must_show: {get: /api/notes, contains: Buy milk}

Steps: `open` a path; `fill` a field found by its label, placeholder or name; `click` a
button or link by its text; `see` text on the page; `not_see` text that must be absent.

    python cli.py journey journeys.yaml --url http://localhost:3000

Safety. A journey does exactly what its steps say, including saving and deleting. Run it
against a test environment only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import app_audit

STEP_KINDS = ("open", "fill", "click", "see", "not_see")


@dataclass
class Journey:
    id: str
    name: str
    steps: List[Tuple[str, object]]
    page_must_call: Optional[Tuple[str, str]] = None        # (METHOD, /path)
    backend_get: str = ""
    backend_contains: str = ""
    backend_not_contains: str = ""


@dataclass
class JourneyResult:
    journey: Journey
    outcome: str = "passed"          # passed | failed | not_run
    failed_at: str = ""              # which of the three checks failed: steps | page_call | backend
    detail: str = ""
    calls: List[Tuple[str, str, int]] = field(default_factory=list)   # what the page sent: method, path, status


def load(text: str) -> Tuple[List[Journey], List[str]]:
    """Journeys from a file, and what is wrong with the file. A bad journey is named and left out."""
    import yaml

    problems: List[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [], [f"not valid YAML: {str(exc)[:120]}"]
    entries = data.get("journeys") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], ["the file needs a `journeys` list"]
    journeys: List[Journey] = []
    for index, entry in enumerate(entries, 1):
        label = str(entry.get("id") or f"journey {index}") if isinstance(entry, dict) else f"journey {index}"
        if not isinstance(entry, dict) or not isinstance(entry.get("steps"), list) or not entry["steps"]:
            problems.append(f"{label}: needs a list of steps")
            continue
        steps: List[Tuple[str, object]] = []
        bad = ""
        for step in entry["steps"]:
            if not isinstance(step, dict) or len(step) != 1 or next(iter(step)) not in STEP_KINDS:
                bad = f"a step must be one of {', '.join(STEP_KINDS)}: {str(step)[:60]}"
                break
            kind, value = next(iter(step.items()))
            if kind == "fill" and not (isinstance(value, dict) and "field" in value and "value" in value):
                bad = "a fill step needs `field` and `value`"
                break
            if kind != "fill" and not isinstance(value, (str, int, float)):
                bad = f"`{kind}` needs text"
                break
            steps.append((kind, value if kind == "fill" else str(value)))
        if not bad and steps[0][0] != "open":
            bad = "the first step must open a page"
        call = entry.get("page_must_call")
        parsed_call = None
        if not bad and call is not None:
            m = re.match(r"^\s*(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)\s*$", str(call))
            if not m:
                bad = f"`page_must_call` must look like `POST /api/notes`: {str(call)[:40]}"
            else:
                parsed_call = (m.group(1), m.group(2))
        backend = entry.get("backend_must_show")
        if not bad and backend is not None and not (
                isinstance(backend, dict) and isinstance(backend.get("get"), str)
                and ("contains" in backend or "not_contains" in backend)):
            bad = "`backend_must_show` needs `get` and `contains` or `not_contains`"
        if bad:
            problems.append(f"{label}: {bad}")
            continue
        backend = backend or {}
        journeys.append(Journey(
            label, str(entry.get("name") or label), steps, parsed_call, backend.get("get", ""),
            str(backend["contains"]) if "contains" in backend else "",
            str(backend["not_contains"]) if "not_contains" in backend else ""))
    return journeys, problems


def _field(page, name: str):
    """A form field by its label, then its placeholder, then its name attribute."""
    for locator in (page.get_by_label(name, exact=False), page.get_by_placeholder(name, exact=False),
                    page.locator(f'[name="{name}"]')):
        if locator.count() > 0:
            return locator.first
    return None


def _clickable(page, text: str):
    for locator in (page.get_by_role("button", name=text, exact=False), page.get_by_role("link", name=text, exact=False),
                    page.get_by_text(text, exact=False)):
        if locator.count() > 0:
            return locator.first
    return None


def run(journeys: List[Journey], base_url: str, headers: Optional[Dict[str, str]] = None,
        timeout_ms: int = 8000) -> List[JourneyResult]:
    """Carry out each journey in a fresh browser page and check the page and the backend."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        import browser_audit

        raise browser_audit.BrowserUnavailable(
            "Journeys need Playwright: pip install playwright && playwright install chromium") from exc

    origin = "{0.scheme}://{0.netloc}".format(urlparse(base_url))
    results: List[JourneyResult] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=os.environ.get("ATA_BROWSER_PATH") or None)
        except PlaywrightError as exc:
            import browser_audit

            raise browser_audit.BrowserUnavailable(
                "No browser could be started. Run `playwright install chromium`, or set ATA_BROWSER_PATH. "
                f"({str(exc).splitlines()[0][:120]})") from exc
        try:
            for journey in journeys:
                result = JourneyResult(journey)
                results.append(result)
                context = browser.new_context(extra_http_headers=headers or {})
                page = context.new_page()
                page.set_default_timeout(timeout_ms)

                def on_response(response, result=result):
                    request = response.request
                    if request.resource_type in ("fetch", "xhr") and response.url.startswith(origin):
                        result.calls.append((request.method, urlparse(response.url).path or "/", response.status))

                page.on("response", on_response)
                try:
                    for number, (kind, value) in enumerate(journey.steps, 1):
                        where = f"step {number} ({kind})"
                        if kind == "open":
                            response = page.goto(urljoin(base_url.rstrip("/") + "/", str(value).lstrip("/")),
                                                 wait_until="networkidle")
                            if response is None or response.status >= 400:
                                raise _StepFailed(f"{where}: the page {value} answered "
                                                  f"{response.status if response else 'nothing'}")
                        elif kind == "fill":
                            target = _field(page, str(value["field"]))
                            if target is None:
                                raise _StepFailed(f"{where}: no field called “{value['field']}” on the page")
                            target.fill(str(value["value"]))
                        elif kind == "click":
                            target = _clickable(page, str(value))
                            if target is None:
                                raise _StepFailed(f"{where}: nothing to click called “{value}”")
                            target.click()
                            page.wait_for_timeout(300)                 # let the click's requests start
                            page.wait_for_load_state("networkidle")
                        elif kind == "see":
                            try:
                                page.get_by_text(str(value), exact=False).first.wait_for(state="visible")
                            except PlaywrightError:
                                raise _StepFailed(f"{where}: the page does not show “{value}”") from None
                        elif kind == "not_see":
                            if page.get_by_text(str(value), exact=False).count() > 0:
                                raise _StepFailed(f"{where}: the page shows “{value}”, which it must not")
                except _StepFailed as failure:
                    result.outcome, result.failed_at, result.detail = "failed", "steps", str(failure)
                except PlaywrightError as exc:
                    result.outcome, result.failed_at = "failed", "steps"
                    result.detail = "the browser could not carry out a step: " + str(exc).splitlines()[0][:160]

                if result.outcome == "passed" and journey.page_must_call:
                    method, path = journey.page_must_call
                    key = (method, app_audit.normalize_path(path))
                    sent = [c for c in result.calls
                            if c[0] == method and _same_route(app_audit.normalize_path(path), c[1])]
                    if not sent:
                        seen = ", ".join(f"{m} {u}" for m, u, _ in result.calls) or "no request at all"
                        result.outcome, result.failed_at = "failed", "page_call"
                        result.detail = f"the page never sent {key[0]} {path}. It sent: {seen}."
                    elif all(status >= 400 for _, _, status in sent):
                        result.outcome, result.failed_at = "failed", "page_call"
                        result.detail = (f"the page sent {method} {path} and the server answered {sent[-1][2]}, "
                                         "while the page went on as if it had worked.")

                if result.outcome == "passed" and journey.backend_get:
                    try:
                        response = context.request.get(urljoin(base_url.rstrip("/") + "/", journey.backend_get.lstrip("/")))
                        body, status = response.text(), response.status
                    except PlaywrightError as exc:
                        body, status = "", 0
                        result.detail = str(exc).splitlines()[0][:120]
                    if status >= 400 or status == 0:
                        result.outcome, result.failed_at = "failed", "backend"
                        result.detail = f"GET {journey.backend_get} answered {status or 'nothing'}, so the result could not be checked."
                    elif journey.backend_contains and journey.backend_contains not in body:
                        result.outcome, result.failed_at = "failed", "backend"
                        result.detail = (f"the page showed it worked, but GET {journey.backend_get} does not contain "
                                         f"“{journey.backend_contains}”. The frontend and the backend disagree.")
                    elif journey.backend_not_contains and journey.backend_not_contains in body:
                        result.outcome, result.failed_at = "failed", "backend"
                        result.detail = (f"the page showed it worked, but GET {journey.backend_get} still contains "
                                         f"“{journey.backend_not_contains}”. The frontend and the backend disagree.")
                context.close()
        finally:
            browser.close()
    return results


class _StepFailed(Exception):
    pass


def _same_route(wanted: str, actual_path: str) -> bool:
    """/api/notes/{} matches /api/notes/7."""
    pattern = "^" + re.escape(wanted.rstrip("/")).replace(r"\{\}", "[^/]+") + "/?$"
    return bool(re.match(pattern, actual_path))


def render_markdown(results: List[JourneyResult], problems: List[str], base_url: str) -> str:
    failed = [r for r in results if r.outcome == "failed"]
    passed = [r for r in results if r.outcome == "passed"]
    if failed:
        verdict = f"**{len(failed)} of {len(results)} journeys failed.**"
    elif results:
        verdict = f"**All {len(results)} journeys passed.**"
    else:
        verdict = "**No journey was run.**"
    lines = ["# Journeys", "", f"Carried out in a browser at `{base_url}`.", "", verdict, ""]
    if problems:
        lines += ["## Problems in the journeys file", ""] + [f"- {p}" for p in problems] + [""]
    names = {"steps": "The steps in the page", "page_call": "The request the page sends",
             "backend": "What the backend holds afterwards"}
    if failed:
        lines += [f"## Failed ({len(failed)})", ""]
        for r in failed:
            lines += [f"- **{r.journey.id}: {r.journey.name}**", f"  {names[r.failed_at]}: {r.detail}"]
        lines.append("")
    if results:
        lines += ["## Every journey", "", "| Journey | Steps in the page | Request sent | Backend afterwards |", "|---|---|---|---|"]
        order = ["steps", "page_call", "backend"]
        for r in results:
            cells = []
            for stage in order:
                asked = (stage == "steps" or (stage == "page_call" and r.journey.page_must_call)
                         or (stage == "backend" and r.journey.backend_get))
                if not asked:
                    cells.append("not asked")
                elif r.outcome == "failed" and r.failed_at == stage:
                    cells.append("FAILED")
                elif r.outcome == "failed" and order.index(stage) > order.index(r.failed_at):
                    cells.append("not reached")
                else:
                    cells.append("ok")
            lines.append(f"| {r.journey.id} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += [
        "## Not examined",
        "",
        "- Only the journeys in the file. A requirement with no journey was not tried.",
        "- Only what each journey says to check. A journey with no backend check proves the page, not the data.",
        "- Each journey ran once, in a fresh browser, in the order written. Journeys are not undone afterwards.",
        "",
    ]
    del passed
    return "\n".join(lines).rstrip() + "\n"
