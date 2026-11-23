"""
sign_in.py — let the agent sign in to the test environment itself.

Without this, a person has to sign in with a browser, find the session cookie or token, and
paste it into an environment variable for each role. That is the step most likely to stop
someone running the agent at all. A small file says how each role signs in instead:

    roles:
      user:
        request: POST /auth/login
        form: {username: alice, password: {env: ALICE_PASSWORD}}
      admin:
        request: POST /api/v1/login/access-token
        form: {username: admin@example.com, password: {env: ADMIN_PASSWORD}}
        token: access_token            # the field of the JSON reply that holds the token
        scheme: Bearer                 # default; some applications use "Token"

`form:` sends a form, `json:` sends JSON. Without `token:` the sign-in is the cookies the
reply sets. A role called `user` is also used for the ownership tests and the browser.

Passwords never go in the file. A field whose name looks secret must be `{env: NAME}`, and
the file is refused otherwise. What the sign-in returns is held in memory for the run and
passed to the generated tests through their environment. It is never printed or written.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SECRET_NAME = re.compile(r"pass|secret|token|key|pin\b|otp", re.IGNORECASE)
ROLE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_ -]{0,40}")


class SignInError(RuntimeError):
    """A role could not be signed in. The message never contains a password, cookie or token."""


@dataclass
class Role:
    name: str
    method: str
    path: str
    fields: Dict[str, object]
    as_json: bool = False
    token_field: str = ""
    scheme: str = "Bearer"


@dataclass
class Credentials:
    role: str
    token: str = ""
    cookie: str = ""
    scheme: str = "Bearer"

    @property
    def kind(self) -> str:
        return " and ".join(k for k, v in (("a token", self.token), ("a cookie", self.cookie)) if v) or "nothing"


@dataclass
class SignedIn:
    credentials: List[Credentials] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)

    def environment(self) -> Dict[str, str]:
        """What the generated tests read. Names are safe to record; values are not."""
        env: Dict[str, str] = {}
        for c in self.credentials:
            prefixes = ["ROLE_" + re.sub(r"\W+", "_", c.role).upper()]
            if c.role.lower() == "user":
                prefixes.append("FINDINGS_USER")
            for prefix in prefixes:
                if c.token:
                    env[prefix + "_TOKEN"] = c.token
                    if c.scheme != "Bearer":
                        env[prefix + "_SCHEME"] = c.scheme
                if c.cookie:
                    env[prefix + "_COOKIE"] = c.cookie
        return env

    def headers_for(self, role: str = "user") -> Dict[str, str]:
        """Headers that sign a browser in as this role."""
        for c in self.credentials:
            if c.role.lower() == role:
                out = {}
                if c.token:
                    out["Authorization"] = f"{c.scheme} {c.token}"
                if c.cookie:
                    out["Cookie"] = c.cookie
                return out
        return {}


def load(text: str) -> Tuple[List[Role], List[str]]:
    """Roles from a sign-in file, and what is wrong with it. A role with a mistake is left out."""
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [], [f"the sign-in file is not valid YAML: {str(exc)[:120]}"]
    entries = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(entries, dict) or not entries:
        return [], ["the sign-in file needs a `roles` section with at least one role"]
    roles: List[Role] = []
    problems: List[str] = []
    for name, entry in entries.items():
        name = str(name)
        if not ROLE_NAME.fullmatch(name) or not isinstance(entry, dict):
            problems.append(f"role {name[:30]!r}: not a role (a name, then how it signs in)")
            continue
        request = re.fullmatch(r"\s*(GET|POST|PUT)\s+(/\S*)\s*", str(entry.get("request") or ""))
        if not request:
            problems.append(f"role {name}: `request` must look like `POST /auth/login`")
            continue
        given = [k for k in ("form", "json") if isinstance(entry.get(k), dict)]
        if len(given) != 1:
            problems.append(f"role {name}: give the fields to send under exactly one of `form` or `json`")
            continue
        fields = entry[given[0]]
        literal = [k for k, v in fields.items() if SECRET_NAME.search(str(k)) and not _is_env(v)]
        if literal:
            problems.append(f"role {name}: `{literal[0]}` looks like a secret, so it must be given as "
                            "{env: NAME}, the name of an environment variable. Nothing secret goes in this file")
            continue
        bad = [k for k, v in fields.items() if not _is_env(v) and not isinstance(v, (str, int, float, bool))]
        if bad:
            problems.append(f"role {name}: `{bad[0]}` must be a plain value or {{env: NAME}}")
            continue
        scheme = str(entry.get("scheme") or "Bearer")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,20}", scheme):
            problems.append(f"role {name}: `scheme` must be one word, such as Bearer or Token")
            continue
        roles.append(Role(name, request.group(1), request.group(2), dict(fields), given[0] == "json",
                          str(entry.get("token") or ""), scheme))
    return roles, problems


def _is_env(value) -> bool:
    return isinstance(value, dict) and list(value) == ["env"] and isinstance(value["env"], str) and bool(value["env"])


def _values(role: Role, env) -> Dict[str, object]:
    out = {}
    for name, value in role.fields.items():
        if _is_env(value):
            found = env.get(value["env"])
            if not found:
                raise SignInError(f"role {role.name}: environment variable {value['env']} is not set")
            out[name] = found
        else:
            out[name] = value
    return out


def sign_in_one(role: Role, base_url: str, env=None, timeout: int = 20) -> Credentials:
    import requests

    values = _values(role, os.environ if env is None else env)
    session = requests.Session()
    try:
        reply = session.request(role.method, base_url.rstrip("/") + role.path, timeout=timeout,
                                allow_redirects=False, **({"json": values} if role.as_json else {"data": values}))
    except requests.exceptions.RequestException as exc:
        raise SignInError(f"role {role.name}: could not reach the sign-in address ({type(exc).__name__})") from None
    if reply.status_code >= 400:
        raise SignInError(f"role {role.name}: the sign-in was turned down ({reply.status_code}). Check the "
                          "user name, the password variable and the field names")
    out = Credentials(role.name, scheme=role.scheme)
    if role.token_field:
        try:
            token = reply.json().get(role.token_field)
        except (ValueError, AttributeError):
            token = None
        if not isinstance(token, str) or not token:
            raise SignInError(f"role {role.name}: the reply has no `{role.token_field}` field holding a token")
        out.token = token
    cookies = session.cookies.get_dict()
    if cookies:
        out.cookie = "; ".join(f"{k}={v}" for k, v in sorted(cookies.items()))
    if not out.token and not out.cookie:
        raise SignInError(f"role {role.name}: the sign-in was accepted ({reply.status_code}) but set no cookie. "
                          "If it returns a token, name its field with `token:`")
    return out


def sign_in(roles: List[Role], base_url: str, env=None) -> SignedIn:
    """Sign every role in. One role failing does not stop the others."""
    done = SignedIn()
    for role in roles:
        try:
            done.credentials.append(sign_in_one(role, base_url, env))
        except SignInError as exc:
            done.failures.append(str(exc))
    return done


def describe(done: Optional[SignedIn]) -> str:
    if done is None:
        return ""
    parts = [f"{c.role} ({c.kind})" for c in done.credentials]
    text = "signed in: " + (", ".join(parts) or "nobody")
    if done.failures:
        text += ". Not signed in: " + "; ".join(done.failures)
    return text
