"""
full_report.py — one report from every check.

`audit` reads the source, `browse` watches the running application, `trace` lines tests up
with requirements and `validate` shows whether each test can fail. Each prints its own
report. This module puts whatever was run into one document, in the order a reader needs:

1. the verdict;
2. what was run and what was not, with the reason;
3. what is wrong now, then what is likely to go wrong, then what is unclear, each finding
   marked with the check it came from;
4. the requirements, one row each: linked code, what was checked, tests;
5. the permissions table;
6. what was not examined.

A part that was not run is listed as not run. It is never counted as passed.

    python cli.py report path/to/app -r requirements.md -p permissions.yaml \
        --tests tests/ --url http://localhost:3000 -o report.md --html report.html
"""

from __future__ import annotations

import datetime
import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import app_audit

_GROUPS = [
    ("wrong_now", "Wrong now", "A fault that exists today."),
    ("likely", "Likely to go wrong", "Nothing is broken yet, but nothing would stop a mistake."),
    ("unclear", "Unclear", "The checks could not tell. A person should look."),
]


@dataclass
class Part:
    name: str
    ran: bool
    summary: str          # what it found, or why it was not run


@dataclass
class Item:
    group: str
    source: str           # Source | Browser | Tests
    title: str
    detail: str
    where: str = ""


@dataclass
class FullReport:
    app_name: str
    date: str
    parts: List[Part] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    requirement_rows: List[List[str]] = field(default_factory=list)   # id, linked to, checked, result, tests
    permissions_table: List[str] = field(default_factory=list)        # Markdown lines
    not_examined: List[str] = field(default_factory=list)

    def of(self, group: str) -> List[Item]:
        return [i for i in self.items if i.group == group]

    @property
    def ok(self) -> bool:
        return not self.of("wrong_now")


def build(app_path: str, audit_report: app_audit.AuditReport, browser=None, trace=None, validation=None,
          requirements_given: bool = False, tests_given: bool = False, url: str = "",
          today: Optional[datetime.date] = None) -> FullReport:
    """Put the results of every check that was run into one report."""
    report = FullReport(Path(app_path).resolve().name, (today or datetime.date.today()).isoformat())
    model = audit_report.model

    # Source.
    counts = (f"{len(model.routes)} backend routes, {len([c for c in model.calls if c.path])} frontend calls, "
              f"{len(model.spec_operations)} spec operations, {len(model.tables)} tables")
    report.parts.append(Part("Source audit", True, f"Read {model.files_read} files: {counts}."))
    report.items += [Item(f.group, "Source", f.title, f.detail, f.where) for f in audit_report.findings]
    report.not_examined += [f"Source: {n}" for n in audit_report.not_examined
                            if not n.startswith(("Permissions: no table", "Requirements: none were given"))]

    # Requirements against code.
    tests_by_requirement = dict(trace.covered) if trace is not None else {}
    if audit_report.requirements is not None:
        result = audit_report.requirements
        report.parts.append(Part("Requirements against code", True,
                                 f"{result.linked} of {result.total} requirements linked to code."))
        for row in result.rows:
            tests = str(len(tests_by_requirement.get(row.id, []))) if trace is not None else "not checked"
            report.requirement_rows.append([row.id, row.linked_to or "nothing", row.checked or "nothing", row.result, tests])
    else:
        report.parts.append(Part("Requirements against code", False, "No requirements file was given."))

    # Permissions.
    if audit_report.policy is not None:
        import permissions

        report.parts.append(Part("Permissions table against code", True,
                                 f"{len(audit_report.policy.rules)} rules for {len(audit_report.policy.roles)} roles."))
        report.permissions_table = permissions.table_markdown(model, audit_report.policy)[2:]
    else:
        report.parts.append(Part("Permissions table against code", False, "No permissions table was given."))

    # Browser.
    if browser is not None:
        seen = browser.seen
        report.parts.append(Part("Browser check", True,
                                 f"Opened {len(seen.pages)} pages at {url or seen.start}, saw {len(seen.api)} API requests."))
        report.items += [Item(f.group, "Browser", f.title, f.detail, f.where) for f in browser.findings]
        report.not_examined += ["Browser: forms were not filled in; "
                                + ("buttons that look destructive were not clicked."
                                   if seen.clicked else "buttons were not clicked.")]
        if seen.not_visited:
            report.not_examined.append(f"Browser: {seen.not_visited} link(s) were not opened (page limit).")
        if browser.routes_never_seen:
            report.not_examined.append(
                "Browser: these backend routes were never seen being called: "
                + ", ".join(browser.routes_never_seen[:20]) + ".")
    else:
        report.parts.append(Part("Browser check", False,
                                 "No address of a running test environment was given (--url)."))

    # Tests against requirements.
    if trace is not None:
        total = len(trace.requirements)
        report.parts.append(Part("Tests against requirements", True,
                                 f"{total - len(trace.uncovered)} of {total} requirements have a test; "
                                 f"{len(trace.tests)} tests read."))
        for req in trace.uncovered:
            report.items.append(Item("likely", "Tests", f"{req.id} has no test",
                                     f"“{req.text[:140]}” Nothing would notice if this stopped working.",
                                     f"requirements line {req.line}"))
        for req_id, labels in sorted(trace.unknown_references.items()):
            report.items.append(Item("likely", "Tests", f"A test points at {req_id}, which is not a requirement",
                                     "A typo, or a requirement that was removed.", labels[0]))
        if trace.untraced_tests:
            names = ", ".join(t.label for t in trace.untraced_tests[:8])
            more = f" and {len(trace.untraced_tests) - 8} more" if len(trace.untraced_tests) > 8 else ""
            report.items.append(Item("unclear", "Tests", f"{len(trace.untraced_tests)} test(s) point at no requirement",
                                     f"{names}{more}. They may be useful, but nothing says what they are for.", ""))
    else:
        why = ("No requirements file was given." if not requirements_given else "No tests were given (--tests).")
        report.parts.append(Part("Tests against requirements", False, why))

    # Whether the tests can fail.
    if validation is not None:
        if validation.problem:
            report.parts.append(Part("Whether each test can fail", False, f"The run did not complete: {validation.problem}"))
        else:
            report.parts.append(Part(
                "Whether each test can fail", True,
                f"{len(validation.validated)} proven able to fail, {len(validation.not_validating)} not, "
                f"{len(validation.failing)} already failing, {len(validation.no_request)} made no request, "
                f"{len(validation.skipped)} skipped."))
            for name in validation.failing:
                report.items.append(Item("wrong_now", "Tests", f"The test {name} fails",
                                         "It failed in a normal run, before any response was changed.", name))
            for name in validation.not_validating:
                report.items.append(Item("likely", "Tests", f"The test {name} passes even when the response is wrong",
                                         "It would not catch the fault it appears to check for.", name))
            if validation.no_request:
                report.not_examined.append(
                    f"Tests: {len(validation.no_request)} test(s) made no HTTP request, so whether they can fail was not shown.")
    else:
        why = "No tests were given (--tests)." if not tests_given else "Not asked for (--validate); it runs the tests twice."
        report.parts.append(Part("Whether each test can fail", False, why))

    order = {"wrong_now": 0, "likely": 1, "unclear": 2}
    report.items.sort(key=lambda i: order.get(i.group, 3))
    return report


def render_markdown(report: FullReport) -> str:
    wrong, likely, unclear = (len(report.of(g)) for g in ("wrong_now", "likely", "unclear"))
    not_run = [p.name for p in report.parts if not p.ran]
    if wrong:
        verdict = f"**{wrong} thing(s) are wrong now.**"
    elif likely:
        verdict = f"**Nothing found wrong now.** {likely} thing(s) are likely to go wrong."
    else:
        verdict = "**Nothing found wrong in what was checked.**"
    if not_run:
        verdict += f" {len(not_run)} of {len(report.parts)} checks were not run, so this is a partial picture."
    lines = [
        f"# Application audit report: {report.app_name}",
        "",
        f"{report.date}",
        "",
        verdict,
        "",
        "| | Count |",
        "|---|---|",
        f"| Wrong now | {wrong} |",
        f"| Likely to go wrong | {likely} |",
        f"| Unclear | {unclear} |",
        "",
        "## What was run",
        "",
        "| Check | Run | Result or reason |",
        "|---|---|---|",
    ]
    lines += [f"| {p.name} | {'Yes' if p.ran else 'No'} | {p.summary} |" for p in report.parts]
    lines.append("")
    for key, title, meaning in _GROUPS:
        items = report.of(key)
        lines += [f"## {title} ({len(items)})", "", meaning, ""]
        for item in items:
            where = f" `{item.where}`" if item.where else ""
            lines += [f"- **{item.title}**", f"  {item.source}. {item.detail}{where}"]
        if not items:
            lines.append("- None found.")
        lines.append("")
    if report.requirement_rows:
        lines += ["## Requirements", "", "| Requirement | Linked to | Checked in code | Result | Tests |", "|---|---|---|---|---|"]
        lines += ["| " + " | ".join(row) + " |" for row in report.requirement_rows]
        lines.append("")
    if report.permissions_table:
        lines += ["## Permissions", ""] + report.permissions_table
    lines += ["## Not examined", ""]
    lines += [f"- {p.name}: not run. {p.summary}" for p in report.parts if not p.ran]
    lines += [f"- {n}" for n in report.not_examined]
    lines += [
        "",
        "## How to read this report",
        "",
        "- Source findings come from reading the code. They are evidence, and a few may be false alarms.",
        "- Browser and test findings were observed on a running system.",
        "- A check that was not run says nothing either way.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


# ── HTML ──────────────────────────────────────────────────────────────────────

_CSS = """
body{font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;color:#1a1a1a;background:#fff;
     max-width:54rem;margin:0 auto;padding:1.25rem}
h1{font-size:1.6rem;line-height:1.25;margin:0 0 .5rem}
h2{font-size:1.2rem;margin:2rem 0 .5rem;padding-top:.75rem;border-top:1px solid #d0d0d0}
p{margin:.5rem 0}ul{padding-left:1.2rem}li{margin:.6rem 0}
code{font:0.85em ui-monospace,Menlo,Consolas,monospace;background:#f1f1f1;padding:.1em .3em;border-radius:3px;
     overflow-wrap:anywhere}
.scroll{overflow-x:auto}table{border-collapse:collapse;margin:.5rem 0;font-size:.92rem}
th,td{border:1px solid #c8c8c8;padding:.35rem .6rem;text-align:left;vertical-align:top}
th{background:#f1f1f1}
@media (prefers-color-scheme:dark){body{background:#151515;color:#e8e8e8}code,th{background:#262626}
  th,td{border-color:#444}h2{border-color:#444}}
@media print{body{max-width:none;padding:0}h2{break-after:avoid}li,tr{break-inside:avoid}}
"""


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def to_html(markdown: str, title: str = "Application audit report") -> str:
    """A self-contained HTML page from the report's Markdown. Handles only what the report uses."""
    out: List[str] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            out.append('<div class="scroll"><table><thead><tr>' + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>")
            out += ["<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body]
            out.append("</tbody></table></div>")
            continue
        elif line.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                item = _inline(lines[i][2:])
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip():
                    item += "<br>" + _inline(lines[i].strip())
                    i += 1
                out.append(f"<li>{item}</li>")
            out.append("</ul>")
            continue
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{_CSS}</style></head>\n<body>\n"
            + "\n".join(out) + "\n</body></html>\n")
