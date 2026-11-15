"""
permissions.py — who may do what: the table of roles against actions.

Stage 6 of docs/ROADMAP.md, first version. No AI involved.

The expected table is a small file a person writes (or starts from `--init`):

    roles: [anonymous, customer, admin]
    rules:
      - route: GET /api/orders/{id}
        allow: [customer, admin]
        own: true            # a customer may reach only their own rows
      - route: POST /api/admin/reindex
        allow: [admin]

`anonymous` is the caller who is not signed in. A route with no rule is reported: a route
nobody decided about is the usual way a permission hole gets in.

Two things are done with the table:

1. compare()  reads the code (through app_audit's model) and reports where what the code
              shows disagrees with the table. This is evidence from names, not proof.
2. tests()    writes one pytest test for every cell of the table, including every cell
              that must be refused. Run against a test environment, those are proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import app_audit

ANONYMOUS = "anonymous"
_ROLE_WORDS = re.compile(r"admin|staff|superuser|role|permission|scope|moderator|manager|owner_only", re.IGNORECASE)


@dataclass
class Rule:
    method: str
    path: str
    allow: List[str]
    own: bool = False

    @property
    def name(self) -> str:
        return f"{self.method} {self.path}"

    @property
    def key(self) -> Tuple[str, str]:
        return self.method, app_audit.normalize_path(self.path)


@dataclass
class Policy:
    roles: List[str] = field(default_factory=list)
    rules: List[Rule] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)   # things wrong with the file itself


def load(text: str) -> Policy:
    """Read a permissions file. A mistake in the file is a problem, never a silent default."""
    import yaml

    policy = Policy()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        policy.problems.append(f"not valid YAML: {str(exc)[:120]}")
        return policy
    if not isinstance(data, dict) or not isinstance(data.get("roles"), list) or not isinstance(data.get("rules"), list):
        policy.problems.append("the file needs a `roles` list and a `rules` list")
        return policy
    policy.roles = [str(r) for r in data["roles"]]
    if ANONYMOUS not in policy.roles:
        policy.roles.insert(0, ANONYMOUS)
    seen = set()
    for entry in data["rules"]:
        route = entry.get("route") if isinstance(entry, dict) else None
        m = re.match(r"^\s*(GET|POST|PUT|PATCH|DELETE)\s+(/\S*)\s*$", route) if isinstance(route, str) else None
        if not m:
            policy.problems.append(f"a rule without a readable `route` (METHOD /path): {str(entry)[:60]}")
            continue
        allow = entry.get("allow")
        if not isinstance(allow, list):
            policy.problems.append(f"{route}: `allow` must be a list of roles (use [] to refuse everyone)")
            continue
        unknown = [str(r) for r in allow if str(r) not in policy.roles]
        if unknown:
            policy.problems.append(f"{route}: unknown role(s) {', '.join(unknown)}")
            continue
        rule = Rule(m.group(1), m.group(2), [str(r) for r in allow], entry.get("own") is True)
        if rule.key in seen:
            policy.problems.append(f"{route}: a second rule for the same route")
            continue
        seen.add(rule.key)
        policy.rules.append(rule)
    return policy


# ── What the code shows ───────────────────────────────────────────────────────


@dataclass
class Shown:
    signed_in: bool                  # some access check is visible
    role_check: bool                 # something that looks like a role or permission check
    roles: List[str]                 # roles named on the route or in its handler
    on_route: List[str] = field(default_factory=list)   # roles named by the route's own dependencies


def shown(route: app_audit.Route, roles: List[str]) -> Shown:
    """What a route's decorators, dependencies and handler names say about who may call it."""
    # Identifiers in the route's decorators and dependencies: Depends(deps.require_admin) → require_admin
    evidence = re.findall(r"[A-Za-z_]\w*", " ".join(route.auth_evidence))
    names = sorted(route.data.names) if route.data else []
    named, on_route = [], []
    signed_in_roles = [r for r in roles if r != ANONYMOUS]
    for role in signed_in_roles:
        word = re.escape(role.lower())
        # Only a name that is about the role itself counts: is_admin, require_admin or
        # get_current_active_superuser. customer_id is a column.
        about_role = re.compile(
            r"^((is|require|requires|required|ensure|check|assert|only|must_be|get|current)_(\w+_)?)?" + word
            + r"s?(_required|_only|_user|_role)?$")
        gate = any(about_role.match(n.lower()) for n in evidence)
        # get_current_user says "signed in", not "has the role called user": the plainest role is no gate.
        if gate and not (role == signed_in_roles[0] and len(signed_in_roles) > 1 and "current" in " ".join(evidence).lower()):
            on_route.append(role)
        # A bare name in the handler (a variable called `user`) says nothing either.
        plainest = role == signed_in_roles[0] and len(signed_in_roles) > 1
        if role in on_route or (not plainest and any(
                about_role.match(n.lower()) and n.lower() not in (role.lower(), role.lower() + "s") for n in names)):
            named.append(role)
    text = " ".join(route.auth_evidence) + " " + " ".join(names)
    return Shown(bool(route.auth_evidence), bool(_ROLE_WORDS.search(text)) or bool(named), named, on_route)


def compare(model: app_audit.AppModel, policy: Policy) -> List[app_audit.Finding]:
    out: List[app_audit.Finding] = []
    add = lambda group, title, detail, where: out.append(app_audit.Finding(group, title, detail, where))  # noqa: E731
    for problem in policy.problems:
        add("wrong_now", "The permissions file has a mistake", problem, "permissions file")
    signed_in_roles = [r for r in policy.roles if r != ANONYMOUS]
    ruled = set()
    for rule in policy.rules:
        routes = [(i, r) for i, r in enumerate(model.routes) if app_audit._match(rule.key, {r.key})]
        if not routes:
            add("unclear", f"The permissions table has a rule for {rule.name}, which the backend does not define",
                "The route was removed or renamed, or the rule has a typo.", "permissions file")
            continue
        for index, route in routes:
            ruled.add(index)
            name = f"{route.method} {route.path}"
            where = app_audit._where(route)
            seen = shown(route, policy.roles)
            if ANONYMOUS not in rule.allow and not seen.signed_in:
                add("wrong_now", f"{name} must refuse a caller who is not signed in, but the code shows no access check",
                    f"Allowed: {', '.join(rule.allow) or 'nobody'}. No dependency, decorator or middleware on "
                    "this route looks like an access check.", where)
                continue
            if ANONYMOUS in rule.allow and seen.signed_in:
                add("likely", f"{name} is meant to be open to everyone, but the code asks for sign-in",
                    f"Seen: {', '.join(route.auth_evidence)}.", where)
            refused = [r for r in signed_in_roles if r not in rule.allow]
            if refused and ANONYMOUS not in rule.allow:
                if not seen.role_check:
                    add("likely", f"{name} must refuse {_join(refused)}, but no role check is visible",
                        f"Allowed: {', '.join(rule.allow) or 'nobody'}. The route asks for sign-in "
                        f"({', '.join(route.auth_evidence)}) and nothing on it or in its handler mentions a "
                        "role or permission, so any signed-in user may get through.", where)
                else:
                    # Only a role the route itself requires. A role the handler mentions may be
                    # mentioned in order to refuse it.
                    wrongly = [r for r in seen.on_route if r in refused]
                    if wrongly:
                        add("likely", f"{name} must refuse {_join(wrongly)}, but the route requires that role",
                            f"Allowed: {', '.join(rule.allow) or 'nobody'}. Seen: {', '.join(route.auth_evidence)}.", where)
            if rule.own:
                gap = app_audit.ownership_gap(route, model.tables)
                if gap is not None:
                    table, owner, access = gap
                    add("wrong_now", f"{name} is limited to the owner's rows, but the code does not check who owns the row",
                        f"`{table.name}` has an owner column (`{owner}`), and nothing this handler runs compares it or filters on it.",
                        f"{access.file}:{access.line}")
                elif route.data is None or not route.data.accesses:
                    add("unclear", f"{name} is limited to the owner's rows, and the handler's data access could not be read",
                        "The ownership check could not be looked for.", where)
    missing = [r for i, r in enumerate(model.routes) if i not in ruled
               and not app_audit.OPERATIONAL.match(app_audit.normalize_path(r.path))]
    if missing and policy.rules:
        listed = ", ".join(f"{r.method} {r.path}" for r in missing[:15])
        more = f" and {len(missing) - 15} more" if len(missing) > 15 else ""
        add("likely", f"{len(missing)} route(s) have no rule in the permissions table",
            f"{listed}{more}. Nobody has decided who may call them.", app_audit._where(missing[0]))
    return out


def _join(names: List[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def table_markdown(model: app_audit.AppModel, policy: Policy) -> List[str]:
    """The expected table, with what the code shows beside it."""
    if not policy.rules:
        return []
    lines = ["## Permissions", "", "| Route | " + " | ".join(policy.roles) + " | Own rows only | The code shows |",
             "|---|" + "---|" * (len(policy.roles) + 2)]
    for rule in policy.rules:
        route = next((r for r in model.routes if app_audit._match(rule.key, {r.key})), None)
        if route is None:
            code = "no such route"
        else:
            seen = shown(route, policy.roles)
            if not seen.signed_in:
                code = "no access check"
            elif seen.on_route:
                code = f"requires {', '.join(seen.on_route)}"
            elif seen.roles:
                code = f"sign-in; the handler mentions {', '.join(seen.roles)}"
            elif seen.role_check:
                code = "a role check"
            else:
                code = "sign-in only"
        cells = ["allow" if r in rule.allow else "refuse" for r in policy.roles]
        lines.append(f"| {rule.name} | " + " | ".join(cells) + f" | {'yes' if rule.own else 'no'} | {code} |")
    return lines + [""]


# ── A starting file, from the code as it is ───────────────────────────────────


def draft(model: app_audit.AppModel, roles: Optional[List[str]] = None) -> str:
    """A permissions file describing what the code does today, for a person to correct."""
    roles = [ANONYMOUS] + [r for r in (roles or ["user", "admin"]) if r != ANONYMOUS]
    signed_in = roles[1:]
    lines = [
        "# The table of who may do what. This draft describes what the code appears to do TODAY.",
        "# Correct it to what the product SHOULD do, then run:",
        "#   python cli.py audit <folder> --permissions <this file>",
        "# `own: true` means a caller may reach only their own rows.",
        f"roles: [{', '.join(roles)}]",
        "rules:",
    ]
    seen_keys = set()
    for route in model.routes:
        if route.key in seen_keys or app_audit.OPERATIONAL.match(app_audit.normalize_path(route.path)):
            continue
        seen_keys.add(route.key)
        seen = shown(route, roles)
        if not seen.signed_in:
            allow, note = roles, "no access check seen"
        elif seen.on_route:
            allow, note = seen.on_route, "role check seen on the route"
        elif seen.roles:
            allow, note = signed_in, f"sign-in seen; the handler treats {', '.join(seen.roles)} differently: check this line"
        elif seen.role_check:
            allow, note = signed_in, "a role check is seen, but not which role: correct this line"
        else:
            allow, note = signed_in, "sign-in seen"
        lines.append(f"  - route: {route.method} {route.path}")
        lines.append(f"    allow: [{', '.join(allow)}]    # {note}")
    return "\n".join(lines) + "\n"


# ── One test for every cell ───────────────────────────────────────────────────


def tests(policy: Policy) -> str:
    """A pytest file with one test per role and route, refusals included.

    The tests need a running test environment (PERMISSIONS_BASE_URL) and one token per
    signed-in role (ROLE_<NAME>_TOKEN). A test whose token is missing is skipped, never
    passed. Path parameters are filled with PERMISSIONS_PATH_ID (default 1).
    """
    cells: Dict[str, Tuple[str, str, str, bool]] = {}
    for rule in policy.rules:
        for role in policy.roles:
            verb = "may" if role in rule.allow else "may_not"
            slug = re.sub(r"_+", "_", re.sub(r"\W+", "_", f"{role}_{verb}_{rule.method}_{rule.path}".lower())).strip("_")
            cells[f"test_{slug}"] = (role, rule.method, rule.path, role in rule.allow)
    lines = [
        '"""Permission tests: one for every cell of the table of roles against actions.',
        "",
        "Generated by `python cli.py permissions --tests`. Do not edit; change the permissions",
        "file and generate again.",
        "",
        "Run against a TEST environment only. These tests send real requests, including",
        "DELETE and POST, with real tokens.",
        "",
        "    PERMISSIONS_BASE_URL   where the application runs, e.g. http://localhost:8000",
        "    ROLE_<NAME>_TOKEN      a bearer token for each signed-in role",
        "    PERMISSIONS_PATH_ID    the id used for path parameters (default 1)",
        '"""',
        "import os",
        "import re",
        "",
        "import pytest",
        "import requests",
        "",
        'BASE = os.environ.get("PERMISSIONS_BASE_URL", "").rstrip("/")',
        'PATH_ID = os.environ.get("PERMISSIONS_PATH_ID", "1")',
        "REFUSED = (401, 403)",
        "",
        "",
        "def _call(role, method, path):",
        "    if not BASE:",
        '        pytest.skip("PERMISSIONS_BASE_URL is not set")',
        "    headers = {}",
        f'    if role != "{ANONYMOUS}":',
        '        token = os.environ.get("ROLE_" + re.sub(r"\\W+", "_", role).upper() + "_TOKEN")',
        "        if not token:",
        '            pytest.skip("no token for role " + role)',
        '        headers["Authorization"] = "Bearer " + token',
        '    url = BASE + re.sub(r"\\{[^}]*\\}", PATH_ID, path)',
        "    return requests.request(method, url, headers=headers, timeout=20)",
        "",
    ]
    for name, (role, method, path, allowed) in cells.items():
        lines += ["", f"def {name}():"]
        lines.append(f'    response = _call("{role}", "{method}", "{path}")')
        if allowed:
            lines.append(f'    assert response.status_code not in REFUSED, "{role} should be allowed: " + str(response.status_code)')
            lines.append('    assert response.status_code < 500, "the server failed: " + str(response.status_code)')
        else:
            lines.append(f'    assert response.status_code in REFUSED, "{role} should be refused, got " + str(response.status_code)')
        lines.append("")
    return "\n".join(lines)
