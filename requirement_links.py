"""
requirement_links.py — let a model propose which code each requirement is about.

Stage 4 of docs/ROADMAP.md, fifth step. `audit --requirements` only checks a requirement
that names its route. Most real requirements do not. Here a model reads each requirement
next to the list of routes the audit found, and proposes which route implements it, if any.

The model proposes; it does not decide. Every proposal is written to a file with
`confirmed: false`. A person reads it and changes that to `true`, and only confirmed links
are used by `audit --links`.

The model is asked one multiple-choice question per requirement: which one route on this
numbered list performs the action, or none. It cannot name a route that does not exist,
because it only ever answers with a number. This also means one route per requirement at
most; add more by hand in the file. The checks (sign-in, ownership, administrators only,
uniqueness) are not asked of the model: `audit` reads them from the requirement's wording,
and a person can add one to a link by hand.

The model never sees source code, only route names and handler names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import app_audit

CHECKS = ("sign_in", "ownership", "admin_only")

QUESTION = """Requirement: "{text}"

API routes:
0. none of these
{routes}

Which one route performs the action the requirement describes? Ignore who is allowed to do it. If no route performs that action, answer 0.
Answer with the number only."""

MAX_ROUTES_LISTED = 60


@dataclass
class Link:
    id: str
    text: str = ""
    routes: List[str] = field(default_factory=list)     # "METHOD /path"
    checks: List[str] = field(default_factory=list)     # sign_in | ownership | admin_only | unique:table.column
    reason: str = ""
    confirmed: bool = False
    discarded: List[str] = field(default_factory=list)  # answers that could not be read


def propose_one(req, model: app_audit.AppModel, backend) -> Link:
    """Ask the model to pick, by number, the one route a requirement is about, or none.

    The model answers with a number from a list, so it cannot name a route that does not
    exist. An answer that is not a number on the list is thrown away and recorded.
    """
    link = Link(req.id, req.text)
    routes = model.routes[:MAX_ROUTES_LISTED]
    if not routes:
        return link
    names = [f"{r.method} {r.path}" for r in routes]
    listing = "\n".join(f"{i + 1}. {name}  (function {routes[i].handler or 'unknown'})" for i, name in enumerate(names))
    answer = backend.complete(QUESTION.format(text=req.text, routes=listing), max_tokens=6)
    number = re.fullmatch(r"\D{0,12}?(\d{1,3})\D{0,3}", answer.strip())
    if number is None or int(number.group(1)) > len(names):
        link.discarded.append(f"answer {answer.strip()[:40]!r}")
    elif int(number.group(1)) > 0:
        link.routes.append(names[int(number.group(1)) - 1])
    if len(model.routes) > MAX_ROUTES_LISTED:
        link.discarded.append(f"{len(model.routes) - MAX_ROUTES_LISTED} route(s) were not shown to the model")
    return link


def propose(requirements: list, model: app_audit.AppModel, backend, progress=None) -> List[Link]:
    links = []
    for index, req in enumerate(requirements, 1):
        if progress:
            progress(index, len(requirements), req.id)
        links.append(propose_one(req, model, backend))
    return links


# ── The links file ────────────────────────────────────────────────────────────


def dump(links: List[Link], proposed_by: str) -> str:
    import yaml

    header = (
        "# Links between requirements and code, proposed by a model.\n"
        "# Read each one. Change `confirmed: false` to `confirmed: true` for the links that are\n"
        "# right, fix or delete the ones that are wrong. Only confirmed links are used by:\n"
        "#   python cli.py audit <folder> --requirements <file> --links <this file>\n"
    )
    data = {
        "proposed_by": proposed_by,
        "links": [
            {"id": link.id, "requirement": link.text, "routes": link.routes, "checks": link.checks,
             "confirmed": link.confirmed,
             **({"discarded": link.discarded} if link.discarded else {})}
            for link in links
        ],
    }
    return header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def load(text: str) -> Tuple[List[Link], List[str]]:
    """Links from a file, and the problems found in it. A malformed entry is skipped and named."""
    import yaml

    problems: List[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [], [f"the links file is not valid YAML: {str(exc)[:120]}"]
    entries = data.get("links") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], ["the links file has no `links` list"]
    links = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            problems.append("an entry without an id was skipped")
            continue
        routes = [r for r in (entry.get("routes") or []) if isinstance(r, str)]
        checks = [c for c in (entry.get("checks") or []) if isinstance(c, str)]
        bad = [c for c in checks if c not in CHECKS and not c.startswith("unique:")]
        if bad:
            problems.append(f"{entry['id']}: unknown check(s) {', '.join(bad)} ignored")
        links.append(Link(entry["id"], str(entry.get("requirement") or ""), routes,
                          [c for c in checks if c not in bad], str(entry.get("reason") or ""),
                          entry.get("confirmed") is True))
    return links, problems


def as_overrides(links: List[Link]) -> Dict[str, Link]:
    """Confirmed links only, by requirement id."""
    return {link.id: link for link in links if link.confirmed}
