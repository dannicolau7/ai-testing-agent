"""
request_bodies.py — the smallest body each operation will accept, built from the API spec.

Generated tests used to send every POST, PUT and PATCH with no body. On a real application
most of those are turned down as incomplete (422) before anything is learned about who may
call the route. Found on the FastAPI full-stack template: of 69 permission cells, 26 could
not be tried for that reason.

From an OpenAPI or Swagger document this builds, for each operation that takes a body, one
value that satisfies the schema: required properties only, each with the plainest value its
type and format allow. The values are fixed, so the same spec always gives the same bodies.

It reads the spec from a file, from the running test environment (a GET to the usual
addresses), or from a document already parsed. It never invents a field the spec does not
name, and an operation whose schema it cannot follow gets no body and is tested without one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

PROBE_EMAIL = "audit-probe@example.com"
PROBE_TEXT = "audit-probe"
PROBE_PASSWORD = "Audit-probe-pw-1"
PROBE_UUID = "00000000-0000-4000-8000-000000000000"
DISCOVER = ("/openapi.json", "/api/openapi.json", "/api/v1/openapi.json", "/swagger.json", "/v3/api-docs",
            "/api-docs")
JSON_TYPES = ("application/json",)
FORM_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data")
MAX_DEPTH = 6


def _resolve(schema, spec: dict, depth: int = 0):
    while isinstance(schema, dict) and "$ref" in schema and depth < MAX_DEPTH:
        node = spec
        for part in str(schema["$ref"]).lstrip("#/").split("/"):
            node = node.get(part.replace("~1", "/").replace("~0", "~")) if isinstance(node, dict) else None
        schema, depth = node, depth + 1
    return schema if isinstance(schema, dict) else {}


def _text(schema: dict) -> str:
    kind = schema.get("format")
    if kind == "email":
        value = PROBE_EMAIL
    elif kind == "uuid":
        value = PROBE_UUID
    elif kind == "date":
        value = "2026-01-01"
    elif kind == "date-time":
        value = "2026-01-01T00:00:00Z"
    elif kind in ("uri", "url"):
        value = "https://example.com/"
    elif kind == "password":
        value = PROBE_PASSWORD
    else:
        literal = re.fullmatch(r"\^([\w .@-]+)\$", str(schema.get("pattern") or ""))
        value = literal.group(1) if literal else PROBE_TEXT
        low, high = schema.get("minLength"), schema.get("maxLength")
        if not literal:
            if isinstance(low, int) and len(value) < low:
                value = (value * (low // len(value) + 1))[:low]
            if isinstance(high, int) and len(value) > high:
                value = value[:high]
    return value


def example(schema, spec: dict, depth: int = 0):
    """One value that satisfies the schema, or None when it cannot be worked out."""
    if depth > MAX_DEPTH:
        return None
    schema = _resolve(schema, spec)
    for key in ("example", "default", "const"):
        if key in schema and schema[key] is not None:
            return schema[key]
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    for key in ("anyOf", "oneOf"):
        if isinstance(schema.get(key), list):
            options = [_resolve(o, spec) for o in schema[key]]
            options = [o for o in options if o.get("type") != "null"] or options
            return example(options[0], spec, depth + 1) if options else None
    if isinstance(schema.get("allOf"), list):
        merged: dict = {}
        for part in schema["allOf"]:
            value = example(part, spec, depth + 1)
            if isinstance(value, dict):
                merged.update(value)
        return merged
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), None)
    if kind == "object" or "properties" in schema:
        out = {}
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for name in schema.get("required") or []:
            if name in properties:
                out[name] = example(properties[name], spec, depth + 1)
        return out
    if kind == "array":
        if schema.get("minItems"):
            return [example(schema.get("items") or {}, spec, depth + 1)]
        return []
    if kind == "string":
        return _text(schema)
    if kind in ("integer", "number"):
        low = schema.get("minimum", schema.get("exclusiveMinimum"))
        return (int(low) + 1) if isinstance(low, (int, float)) and low >= 1 else 1
    if kind == "boolean":
        return False
    return None


def _base(spec: dict) -> str:
    servers = spec.get("servers")
    base = ""
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        base = re.sub(r"^https?://[^/]+", "", str(servers[0].get("url", ""))).rstrip("/")
    return base or str(spec.get("basePath", "")).rstrip("/")


def from_spec(spec: dict) -> Dict[str, dict]:
    """"METHOD /path" → {"json": value} or {"data": value}, for each operation that takes a body."""
    out: Dict[str, dict] = {}
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        return out
    base = _base(spec)
    for path, item in spec["paths"].items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            if method.lower() not in ("post", "put", "patch", "delete") or not isinstance(operation, dict):
                continue
            body = None
            content = (operation.get("requestBody") or {}).get("content") if isinstance(
                operation.get("requestBody"), dict) else None
            if isinstance(content, dict):
                for kinds, how in ((JSON_TYPES, "json"), (FORM_TYPES, "data")):
                    schema = next((content[k].get("schema") for k in kinds
                                   if isinstance(content.get(k), dict)), None)
                    if schema is not None:
                        value = example(schema, spec)
                        if isinstance(value, (dict, list)):
                            body = {how: value}
                        break
            else:   # Swagger 2: a parameter with `in: body`
                for parameter in operation.get("parameters") or []:
                    if isinstance(parameter, dict) and parameter.get("in") == "body":
                        value = example(parameter.get("schema") or {}, spec)
                        if isinstance(value, (dict, list)):
                            body = {"json": value}
            if body is not None:
                out[f"{method.upper()} {base}{path}"] = body
    return out


def _blank(path: str) -> str:
    return re.sub(r"\{[^}]*\}|<[^>]*>|:[A-Za-z_][A-Za-z0-9_]*", "{}", path).rstrip("/") or "/"


def find(bodies: Optional[Dict[str, dict]], method: str, path: str) -> Optional[dict]:
    """The body for a route, matching whatever the path parameters are called, with or without
    a common prefix such as /api or /api/v1."""
    if not bodies:
        return None
    strip = lambda p: re.sub(r"^/(api/v\d+|api|v\d+)(?=/)", "", p)  # noqa: E731
    want = _blank(path)
    for key, body in bodies.items():
        other_method, _, other_path = key.partition(" ")
        have = _blank(other_path)
        if other_method == method.upper() and (have == want or strip(have) == strip(want)):
            return body
    return None


def parse(text: str) -> Optional[dict]:
    try:
        if text.lstrip().startswith("{"):
            spec = json.loads(text)
        else:
            import yaml

            spec = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 - an unreadable spec simply gives no bodies
        return None
    return spec if isinstance(spec, dict) and isinstance(spec.get("paths"), dict) else None


def discover(url: str, timeout: int = 10) -> Tuple[Optional[dict], str]:
    """Ask the running test environment for its spec at the usual addresses. GET only."""
    import requests

    for path in DISCOVER:
        try:
            reply = requests.get(url.rstrip("/") + path, timeout=timeout, allow_redirects=False)
        except requests.exceptions.RequestException:
            return None, ""
        if reply.status_code == 200:
            spec = parse(reply.text)
            if spec is not None:
                return spec, url.rstrip("/") + path
    return None, ""


def load(source: str, timeout: int = 10) -> Tuple[Optional[dict], str]:
    """A spec from a file or an address. Returns (spec or None, where it came from or why not)."""
    if re.match(r"https?://", source):
        import requests

        try:
            reply = requests.get(source, timeout=timeout, allow_redirects=False)
        except requests.exceptions.RequestException as exc:
            return None, f"could not fetch {source}: {type(exc).__name__}"
        spec = parse(reply.text) if reply.status_code == 200 else None
        return spec, source if spec is not None else f"{source} did not return an API spec"
    try:
        spec = parse(Path(source).read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"cannot read {source}: {exc}"
    return spec, source if spec is not None else f"{source} is not an API spec"
