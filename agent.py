"""
agent.py — the application audit as one run that plans, acts, checks its own suspicions,
and says what it could not do.

Until now each stage was a separate command: read the source, write tests from the
findings, run them, open the app in a browser, assemble a report. The agent does the
stages in order, uses what each one learned in the next, and keeps a record of every step.

What makes it an agent and not a script: the audit reads source and only *suspects*. The
agent takes each suspicion that a request can settle, writes the test, runs it against a
running test environment, and sorts the finding by what happened:

    confirmed   the test failed (the server answered, and answered wrongly): the fault is real
    cleared     the test passed: the audit was wrong, or the fault has been fixed. Removed
    not run     the test was skipped or could not complete. The finding stays as it was

Where a model is configured it does one more thing: it proposes which route each
requirement is about. Those proposals are never used for the verdict. The agent shows what
the audit *would* find if they were right, under its own heading, and writes them to a file
for a person to confirm.

Rules the agent keeps, in the order they matter:

1. A model proposes; a request or a person decides. Nothing a model said reaches the verdict.
2. A step that was not run is listed as not run, with the reason. It is never counted as passed.
3. A failure counts as a fault only if the server answered. No answer is not evidence.
4. It sends requests only to a machine it may: this one, or one named in `--authorization`
   with who gave written permission and where it is filed. That line goes in the report.
5. It changes data only with `--allow-writes`.

    python cli.py agent path/to/app -r requirements.md --url http://localhost:8000 \\
        --out-dir agent-run
"""

from __future__ import annotations

import dataclasses
import datetime
import ipaddress
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import app_audit
import finding_tests
import full_report

CONFIRMED, CLEARED, NOT_RUN = "confirmed", "cleared", "not run"
PASSTHROUGH = ("FINDINGS_USER_TOKEN", "FINDINGS_OTHER_ID", "FINDINGS_PATH_ID")


class Refused(RuntimeError):
    """The agent will not send requests to this address on these terms. The message says why."""


@dataclass
class Config:
    path: str
    requirements: Optional[list] = None
    links: Optional[dict] = None            # confirmed links, by requirement id
    link_notes: List[str] = field(default_factory=list)
    policy: Optional[object] = None
    url: str = ""
    authorization: str = ""
    allow_writes: bool = False
    headers: Dict[str, str] = field(default_factory=dict)
    browse: bool = True
    journeys: Optional[list] = None
    journey_problems: List[str] = field(default_factory=list)
    tests: Optional[list] = None            # existing tests, for the traceability check
    validate: bool = False
    backend: Optional[object] = None        # a model_backend backend, or None to run without a model
    test_timeout: int = 600


@dataclass
class Step:
    name: str
    status: str          # done | not run | failed
    detail: str


@dataclass
class Confirmation:
    title: str
    check: str
    method: str
    path: str
    verdict: str         # confirmed | cleared | not run
    evidence: str


@dataclass
class AgentRun:
    report: full_report.FullReport
    audit: app_audit.AuditReport
    steps: List[Step] = field(default_factory=list)
    confirmations: List[Confirmation] = field(default_factory=list)
    cleared: List[app_audit.Finding] = field(default_factory=list)
    untestable: List[str] = field(default_factory=list)
    provisional: List[app_audit.Finding] = field(default_factory=list)
    proposed_links: list = field(default_factory=list)
    proposed_by: str = ""
    tests_text: str = ""
    needs_person: List[str] = field(default_factory=list)
    where: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.report.ok


# ── The rules about where it may send requests ────────────────────────────────


def is_local(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def check_environment(url: str, authorization: str = "") -> bool:
    """True if the address is on this machine. Raises Refused if the agent may not use it."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Refused("the address must start with http:// or https://")
    if parts.username or parts.password:
        raise Refused("do not put a user name or password in the address")
    if is_local(parts.hostname):
        return True
    if len((authorization or "").strip()) < 10:
        raise Refused(
            f"{parts.hostname} is not on this machine. The agent sends requests a real fault would "
            "answer, so for any other machine it needs --authorization saying who gave written "
            "permission and where it is filed, for example "
            "'Rules of engagement signed by the owner 2026-11-01, file RoE-7'.")
    return False


def _reachable(url: str) -> Optional[str]:
    """None if anything answers at the address, else why not. Any answer counts, even an error."""
    import requests

    try:
        requests.get(url, timeout=10, allow_redirects=False)
    except requests.exceptions.RequestException as exc:
        return f"{type(exc).__name__}"
    return None


# ── Confirming findings with tests ────────────────────────────────────────────


def _read_junit(path: Path) -> Dict[str, Tuple[str, str]]:
    """Test name → (passed | failed | skipped | error, message)."""
    out: Dict[str, Tuple[str, str]] = {}
    for case in ET.parse(str(path)).getroot().iter("testcase"):
        name = case.get("name", "")
        failure, skipped, error = case.find("failure"), case.find("skipped"), case.find("error")
        if failure is not None:
            out[name] = ("failed", (failure.get("message") or "")[:300])
        elif error is not None:
            out[name] = ("error", (error.get("message") or "")[:300])
        elif skipped is not None:
            out[name] = ("skipped", (skipped.get("message") or "")[:300])
        else:
            out[name] = ("passed", "")
    return out


def _assertion(message: str) -> Optional[str]:
    """The text of a failed assertion, or None if the test broke for another reason."""
    first = message.strip().splitlines()[0] if message.strip() else ""
    if first.startswith("AssertionError:"):
        return first[len("AssertionError:"):].strip()
    return None


def confirm(findings: List[app_audit.Finding], url: str, allow_writes: bool, workdir: Path,
            timeout: int = 600) -> Tuple[str, List[Confirmation], List[str]]:
    """Write the tests for the findings a request can settle, run them, and sort the findings.

    Returns the test file, one Confirmation per testable finding, and the titles of findings
    no request can settle.
    """
    text, _, untestable = finding_tests.generate(findings)
    test_file = workdir / "test_findings.py"
    test_file.write_text(text, encoding="utf-8")
    results_file = workdir / "results.xml"
    env = {k: v for k, v in os.environ.items() if not k.startswith("FINDINGS_")}
    env.update({k: os.environ[k] for k in PASSTHROUGH if k in os.environ})
    env["FINDINGS_BASE_URL"] = url
    if allow_writes:
        env["FINDINGS_ALLOW_WRITES"] = "1"
    try:
        subprocess.run([sys.executable, "-m", "pytest", str(test_file), "--junitxml", str(results_file), "-q",
                        "-p", "no:cacheprovider", "-o", "addopts="],
                       capture_output=True, text=True, env=env, cwd=str(workdir), timeout=timeout)
        outcomes = _read_junit(results_file) if results_file.is_file() else {}
        why_missing = "the test run produced no result"
    except subprocess.TimeoutExpired:
        outcomes, why_missing = {}, f"the test run did not finish in {timeout} seconds"
    except ET.ParseError:
        outcomes, why_missing = {}, "the test results could not be read"

    seen = set()
    confirmations: List[Confirmation] = []
    for f in findings:
        if not (f.check and f.method and f.path):
            continue
        name = finding_tests.name_of_test(f.check, f.method, f.path)
        outcome, message = outcomes.get(name, ("missing", why_missing))
        if outcome == "failed" and _assertion(message) is not None:
            verdict, evidence = CONFIRMED, _assertion(message) or ""
        elif outcome == "passed":
            verdict, evidence = CLEARED, "the running system behaved as it should"
        elif outcome == "failed":
            verdict, evidence = NOT_RUN, f"the test itself broke: {message[:120]}"
        else:
            verdict, evidence = NOT_RUN, message or "it did not run"
        if name not in seen:      # one test settles every finding that shares it
            confirmations.append(Confirmation(f.title, f.check, f.method, f.path, verdict, evidence))
            seen.add(name)
    return text, confirmations, untestable


# ── The run ───────────────────────────────────────────────────────────────────


def _key(f: app_audit.Finding) -> Tuple[str, str]:
    return f.title, f.where


def run(cfg: Config, workdir: Optional[Path] = None, today: Optional[datetime.date] = None) -> AgentRun:
    """Do every stage the inputs allow, in order, and say what was not done."""
    local = True
    if cfg.url:
        local = check_environment(cfg.url, cfg.authorization)
    steps: List[Step] = []

    # 1. Read the source.
    model = app_audit.build_model(cfg.path)
    base = app_audit.audit(model, cfg.requirements, cfg.links, cfg.link_notes, cfg.policy)
    steps.append(Step("Read the source", "done",
                      f"{model.files_read} files, {len(model.routes)} routes, {len(base.findings)} findings"))

    run_ = AgentRun(report=None, audit=base, steps=steps)  # type: ignore[arg-type]

    # 2. Ask the model which code each requirement is about. Proposals never reach the verdict.
    provisional: List[app_audit.Finding] = []
    if cfg.requirements is None:
        steps.append(Step("Propose links", "not run", "no requirements were given"))
    elif cfg.backend is None:
        steps.append(Step("Propose links", "not run",
                          "no model is configured; requirements link to code only where they name their route"))
    else:
        import model_backend
        import requirement_links

        todo = [r for r in cfg.requirements if r.id not in (cfg.links or {})]
        try:
            proposed = requirement_links.propose(todo, model, cfg.backend)
            run_.proposed_links, run_.proposed_by = proposed, cfg.backend.describe()
            overrides = dict(cfg.links or {})
            overrides.update({p.id: p for p in proposed if p.routes})
            known = {_key(f) for f in base.findings}
            what_if = app_audit.audit(model, cfg.requirements, overrides, cfg.link_notes, cfg.policy)
            provisional = [f for f in what_if.findings if _key(f) not in known]
            steps.append(Step("Propose links", "done",
                              f"{cfg.backend.describe()} proposed a route for "
                              f"{len([p for p in proposed if p.routes])} of {len(todo)} requirements; "
                              f"{len(provisional)} extra finding(s) if they are right. None used."))
        except model_backend.ModelError as exc:
            steps.append(Step("Propose links", "failed", str(exc)[:200]))
    run_.provisional = provisional

    # 3. Take each finding a request can settle and settle it.
    final = list(base.findings)
    answered = False
    if not cfg.url:
        steps.append(Step("Test the findings", "not run", "no address of a test environment was given (--url)"))
    else:
        problem = _reachable(cfg.url)
        if problem:
            steps.append(Step("Test the findings", "failed", f"nothing answered at {cfg.url} ({problem})"))
        else:
            answered = True
            holder = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="ata-agent-"))
            holder.mkdir(parents=True, exist_ok=True)
            run_.tests_text, run_.confirmations, run_.untestable = confirm(
                base.findings, cfg.url, cfg.allow_writes, holder, cfg.test_timeout)
            by = {(c.method, c.path, c.check): c for c in run_.confirmations}
            final = []
            for f in base.findings:
                c = by.get((f.method, f.path, f.check)) if f.check else None
                if c is None or c.verdict == NOT_RUN:
                    final.append(f)
                elif c.verdict == CONFIRMED:
                    final.append(dataclasses.replace(
                        f, group="wrong_now",
                        detail=f"{f.detail} Confirmed by a request to the running system: {c.evidence}."))
                else:
                    run_.cleared.append(f)
            counts = {v: len([c for c in run_.confirmations if c.verdict == v]) for v in (CONFIRMED, CLEARED, NOT_RUN)}
            steps.append(Step("Test the findings", "done",
                              f"{len(run_.confirmations)} testable: {counts[CONFIRMED]} confirmed, "
                              f"{counts[CLEARED]} cleared, {counts[NOT_RUN]} not run"))

    settled = dataclasses.replace(base, findings=final)

    # 4. Look at the running application.
    browser = None
    if not cfg.url:
        steps.append(Step("Browse the application", "not run", "no address of a test environment was given (--url)"))
    elif not cfg.browse:
        steps.append(Step("Browse the application", "not run", "turned off (--no-browser)"))
    elif not answered:
        steps.append(Step("Browse the application", "not run", "nothing answered at the address"))
    else:
        import browser_audit

        try:
            browser = browser_audit.report(browser_audit.browse(cfg.url, headers=cfg.headers), model)
            steps.append(Step("Browse the application", "done",
                              f"{len(browser.seen.pages)} pages, {len(browser.findings)} finding(s)"))
        except browser_audit.BrowserUnavailable as exc:
            steps.append(Step("Browse the application", "not run", str(exc)[:200]))
        except Exception as exc:  # a browser can fail in many ways; the run goes on and says so
            steps.append(Step("Browse the application", "failed", f"{type(exc).__name__}: {str(exc)[:160]}"))

    # 5. Carry out the written journeys.
    journey_results: list = []
    if not cfg.journeys:
        steps.append(Step("Carry out journeys", "not run", "no journeys file was given"))
    elif not cfg.url:
        steps.append(Step("Carry out journeys", "not run", "no address of a test environment was given (--url)"))
    else:
        import journeys

        try:
            journey_results = journeys.run(cfg.journeys, cfg.url, headers=cfg.headers)
            failed = [r for r in journey_results if r.outcome == "failed"]
            steps.append(Step("Carry out journeys", "done",
                              f"{len(journey_results)} journeys, {len(failed)} failed"))
        except Exception as exc:
            steps.append(Step("Carry out journeys", "failed", f"{type(exc).__name__}: {str(exc)[:160]}"))

    # 6. Tests that already exist.
    trace = validation = None
    if cfg.tests and cfg.requirements is not None:
        import traceability

        trace = traceability.build_report(cfg.requirements, traceability.scan_tests(cfg.tests))
        steps.append(Step("Line existing tests up with requirements", "done",
                          f"{len(trace.uncovered)} requirement(s) have no test"))
        if cfg.validate:
            import validation as validation_module

            validation = validation_module.validate_tests(cfg.tests)
            steps.append(Step("Check that each test can fail", "done" if not validation.problem else "failed",
                              validation.problem or f"{len(validation.validated)} proven able to fail"))

    report = full_report.build(cfg.path, settled, browser, trace, validation,
                               requirements_given=cfg.requirements is not None, tests_given=bool(cfg.tests),
                               url=cfg.url, today=today)
    for part_name, step_name in (("Model-proposed links", "Propose links"),
                                 ("Findings tested on the running system", "Test the findings"),
                                 ("Journeys", "Carry out journeys")):
        step = next(s for s in steps if s.name == step_name)
        report.parts.append(full_report.Part(part_name, step.status == "done", step.detail))
    # The full report speaks for the source audit alone. Say what is true of this run.
    if cfg.url:
        for part in report.parts:
            if part.name == "Browser check" and not part.ran:
                step = next(x for x in steps if x.name == "Browse the application")
                part.summary = step.detail
    if answered:
        report.not_examined = [
            "Source: The running application was asked about the findings it could settle, and nothing else."
            if n.startswith("Source: The running application") else n for n in report.not_examined]
    for result in journey_results:
        if result.outcome == "failed":
            report.items.append(full_report.Item("wrong_now", "Journey", f"Journey “{result.journey.name}” failed",
                                                 result.detail, result.failed_at))
    report.items.sort(key=lambda i: {"wrong_now": 0, "likely": 1, "unclear": 2}.get(i.group, 3))

    run_.report = report
    run_.audit = settled
    run_.where = {
        "url": cfg.url, "on_this_machine": local if cfg.url else None, "authorization": cfg.authorization,
        "writes_allowed": cfg.allow_writes,
        "token_variables_set": [k for k in PASSTHROUGH if os.environ.get(k)],
    }
    run_.needs_person = _needs_person(run_, journey_results, cfg)
    return run_


def _needs_person(run_: AgentRun, journey_results: list, cfg: Config) -> List[str]:
    out: List[str] = []
    unclear = [i for i in run_.report.items if i.group == "unclear"]
    if unclear:
        out.append(f"{len(unclear)} finding(s) the checks could not settle (listed under Unclear).")
    waiting: Dict[str, int] = {}
    for c in run_.confirmations:
        if c.verdict == NOT_RUN:
            waiting[c.evidence] = waiting.get(c.evidence, 0) + 1
    for reason, count in sorted(waiting.items()):
        out.append(f"{count} finding(s) not tested: {reason}.")
    if run_.untestable:
        out.append(f"{len(run_.untestable)} finding(s) no request can settle, so each needs a person or another "
                   "kind of test.")
    if run_.proposed_links:
        guessed = len([p for p in run_.proposed_links if p.routes])
        out.append(f"{guessed} requirement(s) have a route proposed by {run_.proposed_by}. Confirm or correct them "
                   "in requirement-links.yaml; until then nothing from them counts.")
    for r in journey_results:
        if r.outcome == "not_run":
            out.append(f"Journey “{r.journey.name}” was not run: {r.detail}")
    out.extend(cfg.journey_problems)
    return out


# ── The report ────────────────────────────────────────────────────────────────


def render_markdown(run_: AgentRun) -> str:
    extra: List[str] = []
    w = run_.where
    if w.get("url"):
        extra += ["## Where it ran", "",
                  f"- Address: `{w['url']}` ({'on this machine' if w['on_this_machine'] else 'another machine'})."]
        if w.get("authorization"):
            extra.append(f"- Written permission: {w['authorization']}")
        extra.append("- Requests that change data: " + ("sent." if w["writes_allowed"] else "not sent."))
        extra.append("- Sign-in details supplied: " + (", ".join(w["token_variables_set"]) or "none")
                     + ". Their values are never recorded.")
        extra.append("")
    settled = [c for c in run_.confirmations if c.verdict in (CONFIRMED, CLEARED)]
    if settled:
        extra += ["## Settled by a request to the running system", "",
                  "The audit reads source and only suspects. These suspicions were tested.", "",
                  "| Finding | Result | What happened |", "|---|---|---|"]
        for c in settled:
            extra.append(f"| {c.title} | {'Fault is real' if c.verdict == CONFIRMED else 'Cleared'} | {c.evidence} |")
        extra += ["", "A cleared finding is removed from the lists above: the system behaved as it should "
                  "when asked, or the fault has been fixed. A real fault is listed under Wrong now.", ""]
    if run_.provisional:
        extra += [f"## If the proposed links are right ({len(run_.provisional)})", "",
                  f"{run_.proposed_by} proposed which route each requirement is about. A model can be wrong, so "
                  "these are not counted in the verdict. They show what confirming the links would add.", ""]
        for f in run_.provisional:
            extra += [f"- **{f.title}**", f"  {f.detail} `{f.where}`" if f.where else f"  {f.detail}"]
        extra.append("")
    if run_.needs_person:
        extra += ["## Needs a person", ""] + [f"- {line}" for line in run_.needs_person] + [""]
    extra += ["## What the agent did, in order", ""]
    extra += [f"{i}. **{s.name}** ({s.status}): {s.detail}" for i, s in enumerate(run_.steps, 1)]
    extra.append("")
    return full_report.render_markdown(run_.report, extra=extra)


def to_json(run_: AgentRun) -> str:
    data = {
        "app": run_.report.app_name,
        "date": run_.report.date,
        "ok": run_.ok,
        "where": run_.where,
        "steps": [dataclasses.asdict(s) for s in run_.steps],
        "confirmations": [dataclasses.asdict(c) for c in run_.confirmations],
        "cleared": [f.title for f in run_.cleared],
        "findings_no_request_can_settle": run_.untestable,
        "provisional_findings": [f.title for f in run_.provisional],
        "proposed_links": [{"id": p.id, "routes": p.routes} for p in run_.proposed_links],
        "proposed_by": run_.proposed_by,
        "needs_person": run_.needs_person,
    }
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def write_outputs(run_: AgentRun, out_dir: Path) -> List[str]:
    """Write the report, the run record, the generated tests and the proposed links."""
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(run_)
    written = []

    def put(name: str, text: str) -> None:
        (out_dir / name).write_text(text, encoding="utf-8")
        written.append(name)

    put("report.md", markdown)
    put("report.html", full_report.to_html(markdown, f"Application audit report: {run_.report.app_name}"))
    put("run.json", to_json(run_))
    if run_.tests_text:
        put("tests-from-findings.py", run_.tests_text)
    if run_.proposed_links:
        import requirement_links

        put("requirement-links.yaml", requirement_links.dump(run_.proposed_links, run_.proposed_by))
    return written
