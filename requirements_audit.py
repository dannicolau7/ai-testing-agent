"""
requirements_audit.py — check the code against written requirements.

Stage 4 of docs/ROADMAP.md, fourth step. No AI involved, so it does not try to understand
a requirement. It links a requirement to code only where someone wrote the link down:

- the requirement names a route:    "REQ-3  Only the owner may delete an order (DELETE /api/orders/{id})"
- a handler names the requirement:  "# Requirement: REQ-3" above it, or "Covers: REQ-3" in its docstring

For a linked requirement it checks the few things it can read from the wording:

- "signed in", "authenticated", "must log in"     → the route shows an access check
- "their own", "only the owner"                   → the handler checks who owns the row
- "administrators only", "only an admin"          → the route or handler mentions a role check
- "<column> must be unique" (no link needed)      → the database enforces it

Everything else in the requirement is listed as not checked. A requirement linked to
nothing is reported as unclear, never as met.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import app_audit
from traceability import ID_PATTERN

_ROUTE_IN_TEXT = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s,;)`\]]*)")
_REFERENCE = re.compile(r"(?:requirements?|covers|implements|verifies|traces? to)\s*:\s*(.+)", re.IGNORECASE)

SIGNED_IN = re.compile(
    r"signed[ -]in|logged[ -]in|log(ged)? in\b|sign(ed)? in\b|authenticat|authori[sz]ed user|registered user", re.IGNORECASE)
PUBLIC = re.compile(r"without (signing|logging) in|anonymous|anyone|public(ly)?\b|no (login|sign[ -]in)", re.IGNORECASE)
OWN = re.compile(r"\b(their|his|her|its|your) own\b|only the owner|owner only|belongs? to (them|the user|the customer)|"
                 r"other (users|customers|people)[\u2019']?s?\b", re.IGNORECASE)
ADMIN = re.compile(r"admin(istrator)?s? only|only (an? |the )?admin|restricted to admin|staff only|only staff", re.IGNORECASE)
UNIQUE = re.compile(r"\bunique\b|no two\b|must not be duplicated|only once", re.IGNORECASE)


@dataclass
class Row:
    id: str
    linked_to: str = ""
    checked: str = ""
    result: str = ""


@dataclass
class RequirementsResult:
    total: int = 0
    linked: int = 0
    rows: List[Row] = field(default_factory=list)
    findings: List[app_audit.Finding] = field(default_factory=list)
    supersedes: Set[str] = field(default_factory=set)
    not_examined: List[str] = field(default_factory=list)


def _handler_references(model: app_audit.AppModel) -> Dict[int, List[str]]:
    """Requirement ids written on each handler: index of the route → ids."""
    out: Dict[int, List[str]] = {}
    cache: Dict[str, List[str]] = {}
    for index, route in enumerate(model.routes):
        if not route.line or not route.file.endswith(".py"):
            continue
        if route.file not in cache:
            try:
                cache[route.file] = (Path(model.root) / route.file).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                cache[route.file] = []
        lines = cache[route.file]
        ids: List[str] = []
        # Comments directly above the handler and its decorators.
        i = min(route.line - 2, len(lines) - 1)
        while i >= 0:
            stripped = lines[i].strip()
            continuation = bool(stripped) and lines[i][:1] in (" ", "\t")   # a decorator split over lines
            if not (stripped.startswith(("#", "@", ")")) or continuation):
                break
            m = _REFERENCE.search(stripped) if stripped.startswith("#") else None
            if m:
                ids += ID_PATTERN.findall(m.group(1))
            i -= 1
        # The docstring, if the reference is in its first lines.
        for line in lines[route.line:route.line + 12]:
            stripped = line.strip()
            if stripped.startswith(("def ", "async def ", "@", "class ")):
                break
            m = _REFERENCE.search(stripped)
            if m and not stripped.startswith("#"):
                ids += ID_PATTERN.findall(m.group(1))
        if ids:
            out[index] = sorted(set(ids))
    return out


def _table_words(name: str) -> Set[str]:
    name = name.lower()
    words = {name, name.replace("_", " ")}
    for form in list(words):
        if form.endswith("ies"):
            words.add(form[:-3] + "y")
        if form.endswith("es"):
            words.add(form[:-2])
        if form.endswith("s"):
            words.add(form[:-1])
    return words


def _mentions(text: str, word: str) -> bool:
    return bool(re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", text, re.IGNORECASE))


def check(model: app_audit.AppModel, requirements: list, links: Optional[dict] = None,
          link_notes: Optional[List[str]] = None) -> RequirementsResult:
    """links: confirmed links by requirement id (requirement_links.as_overrides)."""
    links = links or {}
    result = RequirementsResult(total=len(requirements))
    known = {r.id for r in requirements}
    by_handler = _handler_references(model)
    add = lambda group, title, detail, where: result.findings.append(  # noqa: E731
        app_audit.Finding(group, title, detail, where))
    traced_routes: Set[int] = set()

    for index, ids in by_handler.items():
        route = model.routes[index]
        for unknown in [i for i in ids if i not in known]:
            add("likely", f"{route.method} {route.path} points at {unknown}, which is not a requirement",
                "A typo, or a requirement that was removed.", f"{route.file}:{route.line}")

    for req in requirements:
        row = Row(req.id)
        routes: List[app_audit.Route] = []
        missing: List[str] = []
        for method, path in _ROUTE_IN_TEXT.findall(req.text):
            path = path.rstrip(".:")
            key = (method, app_audit.normalize_path(path))
            found = [(i, r) for i, r in enumerate(model.routes) if app_audit._match(key, {r.key})]
            if found:
                for i, r in found:
                    traced_routes.add(i)
                    if r not in routes:
                        routes.append(r)
            elif model.routes:
                missing.append(f"{method} {path}")
        for index, ids in by_handler.items():
            if req.id in ids:
                traced_routes.add(index)
                if model.routes[index] not in routes:
                    routes.append(model.routes[index])
        link = links.get(req.id)
        wanted: Set[str] = set(link.checks) if link else set()
        if link:
            for name in link.routes:
                method, _, path = name.partition(" ")
                key = (method.upper(), app_audit.normalize_path(path))
                found = [(i, r) for i, r in enumerate(model.routes) if app_audit._match(key, {r.key})]
                if not found:
                    add("unclear", f"The confirmed link for {req.id} names {name}, which the backend no longer defines",
                        "The route was removed or renamed after the link was confirmed.", "links file")
                for i, r in found:
                    traced_routes.add(i)
                    if r not in routes:
                        routes.append(r)
        for name in missing:
            add("wrong_now", f"{req.id} describes {name}, which the backend does not define",
                f"\u201c{req.text[:140]}\u201d Nothing implements this route.", f"requirements line {req.line}")

        checked: List[str] = []
        problems: List[str] = []
        columns: List[str] = []
        text = req.text

        if routes and ("sign_in" in wanted or (SIGNED_IN.search(text) and not PUBLIC.search(text))):
            checked.append("sign-in")
            for route in routes:
                if not route.auth_evidence:
                    problems.append("no access check")
                    add("wrong_now", f"{req.id} requires sign-in, but {route.method} {route.path} shows no access check",
                        f"\u201c{text[:140]}\u201d No dependency, decorator or middleware on this route looks like "
                        "an access check.", app_audit._where(route))
                    result.supersedes.add(f"{route.method} {route.path} changes data and shows no access check")
        if routes and ("ownership" in wanted or OWN.search(text)):
            checked.append("ownership")
            for route in routes:
                gap = app_audit.ownership_gap(route, model.tables)
                if gap is not None:
                    table, owner, access = gap
                    problems.append("no ownership check")
                    add("wrong_now", f"{req.id} limits {route.method} {route.path} to the owner, but the code does not check who owns the row",
                        f"\u201c{text[:140]}\u201d `{table.name}` has an owner column (`{owner}`), and nothing this "
                        "handler runs mentions it.", f"{access.file}:{access.line}")
                    result.supersedes.add(app_audit.ownership_title(route, table, access))
                elif route.data is None or not route.data.accesses:
                    checked[-1] = "ownership (could not be read)"
        if routes and ("admin_only" in wanted or ADMIN.search(text)):
            checked.append("admin only")
            for route in routes:
                names = " ".join(route.auth_evidence) + " " + " ".join(sorted(route.data.names) if route.data else [])
                if not re.search(r"admin|staff|superuser|role|permission|scope", names, re.IGNORECASE):
                    problems.append("no role check seen")
                    add("likely", f"{req.id} limits {route.method} {route.path} to administrators, but no role check is visible",
                        f"\u201c{text[:140]}\u201d Nothing on the route or in its handler mentions an admin, role or "
                        "permission. Any signed-in user may be able to call it.", app_audit._where(route))
        named = {c[len("unique:"):].lower() for c in wanted if c.startswith("unique:")}
        if (UNIQUE.search(text) or named) and model.tables:
            for table in model.tables:
                by_wording = UNIQUE.search(text) and any(_mentions(text, w) for w in _table_words(table.name))
                for column in table.columns:
                    if column.primary_key or column.name.lower() == "id":
                        continue
                    if f"{table.name}.{column.name}".lower() in named or (by_wording and (
                            _mentions(text, column.name) or _mentions(text, column.name.replace("_", " ")))):
                        checked.append("unique")
                        columns.append(f"{table.name}.{column.name}")
                        if not column.unique:
                            problems.append("not enforced")
                            add("wrong_now", f"{req.id} says {table.name}.{column.name} is unique, but the database does not enforce it",
                                f"\u201c{text[:140]}\u201d The column has no UNIQUE constraint, so duplicates will be "
                                "accepted.", app_audit._where(table))

        linked = [f"{r.method} {r.path}" for r in routes] + [f"{m} (missing)" for m in missing] + columns
        row.linked_to = ", ".join(linked)
        row.checked = ", ".join(dict.fromkeys(checked))
        if linked:
            result.linked += 1
        if problems or missing:
            row.result = "Problem: " + ", ".join(sorted(set(problems + (["route missing"] if missing else []))))
        elif checked:
            row.result = "No problem found in what was checked"
        elif linked:
            row.result = "Linked; nothing in the wording could be checked"
        else:
            row.result = "Not linked to code"
        result.rows.append(row)

    unlinked = [row.id for row in result.rows if row.result == "Not linked to code"]
    if unlinked and result.linked:
        listed = ", ".join(unlinked[:15]) + (f" and {len(unlinked) - 15} more" if len(unlinked) > 15 else "")
        add("unclear", f"{len(unlinked)} requirement(s) are not linked to any route",
            f"{listed}. They may be met, unmet, or not about the API. Link one by naming its route in "
            "the requirement, or by writing `# Requirement: <id>` above the handler.", "requirements")
    if result.linked:
        untraced = [r for i, r in enumerate(model.routes) if i not in traced_routes and r.method in app_audit.MUTATING]
        if untraced:
            listed = ", ".join(f"{r.method} {r.path}" for r in untraced[:12])
            more = f" and {len(untraced) - 12} more" if len(untraced) > 12 else ""
            add("unclear", f"{len(untraced)} route(s) that change data trace to no requirement",
                f"{listed}{more}. Either a requirement is missing, or the link is.", app_audit._where(untraced[0]))
    else:
        result.not_examined.append(
            "Requirements: none of them names a route and no handler names a requirement, so nothing "
            "could be checked against them.")
    for note in link_notes or []:
        result.not_examined.append(f"Links file: {note}.")
    result.not_examined.append(
        "Requirements are matched by wording, for four things only: sign-in, ownership, admin-only and "
        "uniqueness. The rest of each requirement was not checked; see the Requirements table."
        + (" Links confirmed by a person were used where given." if links else ""))
    return result
