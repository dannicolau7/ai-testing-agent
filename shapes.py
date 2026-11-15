"""
shapes.py — what each layer says a request and a response look like.

Stage 4 of docs/ROADMAP.md, third step. Three readers produce the same small record:

- backend   FastAPI handlers: the Pydantic model taken as the body, plain parameters taken
            from the query string, and response_model
- API spec  requestBody, query parameters and the success response of each operation
- frontend  the object literal a fetch/axios call sends, and the query string in its URL

A shape is recorded only when the source states it. A body passed as a variable, a model
this reader cannot resolve, or a spread (`...rest`) is left unknown, and unknown shapes are
never compared.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

_SIMPLE_TYPES = {"int", "str", "float", "bool", "date", "datetime", "UUID", "Decimal"}
_WRAPPERS = {"Optional", "List", "list", "Sequence", "Union", "Annotated"}


@dataclass
class Shape:
    # name → required. None means "not stated in the source", which is different from empty.
    body: Optional[Dict[str, bool]] = None
    body_open: bool = False          # the body may carry more fields than the ones read
    query: Optional[Dict[str, bool]] = None
    response: Optional[List[str]] = None
    source: str = ""                 # what the shape was read from, for the report
    body_type: str = ""              # frontend: the TypeScript type of the body, until resolved


# ── Backend: FastAPI and Pydantic ─────────────────────────────────────────────


def _last(node: Optional[ast.AST]) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _inner_names(annotation: Optional[ast.AST]) -> List[str]:
    """Type names inside an annotation: Optional[List[Item]] → Optional, List, Item."""
    if annotation is None:
        return []
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return re.findall(r"[A-Za-z_]\w*", annotation.value)
    return [_last(n) for n in ast.walk(annotation) if isinstance(n, (ast.Name, ast.Attribute)) and _last(n)]


def _field_required(value: Optional[ast.AST]) -> bool:
    if value is None:
        return True
    if isinstance(value, ast.Call) and _last(value.func) == "Field":
        if any(k.arg in ("default", "default_factory") for k in value.keywords):
            return False
        return not value.args or (isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis)
    return False


def pydantic_models(trees: Iterable[Tuple[str, ast.AST]]) -> Dict[str, Dict[str, bool]]:
    """Every Pydantic model in the project: class name → {field: required}."""
    classes: Dict[str, ast.ClassDef] = {}
    for _, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, node)
    models: Dict[str, Dict[str, bool]] = {}

    def resolve(name: str, depth: int = 0) -> Optional[Dict[str, bool]]:
        if name in models:
            return models[name]
        node = classes.get(name)
        if node is None or depth > 8:
            return None
        fields: Dict[str, bool] = {}
        is_model = False
        for base in node.bases:
            base_name = _last(base)
            if base_name in ("BaseModel", "SQLModel"):
                is_model = True
            else:
                inherited = resolve(base_name, depth + 1)
                if inherited is not None:
                    is_model = True
                    fields.update(inherited)
        if not is_model:
            return None
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                if item.target.id.startswith("_") or item.target.id == "model_config":
                    continue
                if "ClassVar" in _inner_names(item.annotation):
                    continue
                fields[item.target.id] = _field_required(item.value)
        models[name] = fields
        return fields

    for name in list(classes):
        resolve(name)
    return models


def handler_shape(func: ast.AST, path: str, models: Dict[str, Dict[str, bool]]) -> Optional[Shape]:
    """The shape a FastAPI handler declares, or None when it is not a FastAPI handler."""
    decorator = None
    for d in getattr(func, "decorator_list", []):
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in (
                "get", "post", "put", "patch", "delete"):
            decorator = d
    if decorator is None:
        return None
    shape = Shape(source=getattr(func, "name", ""))
    path_params = set(re.findall(r"\{(\w+)[^}]*\}", path))
    args = func.args
    positional = args.posonlyargs + args.args
    defaults: List[Optional[ast.AST]] = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    params = list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    query: Dict[str, bool] = {}
    takes_raw_request = False
    for arg, default in params:
        if arg.arg in ("self", "cls") or arg.arg in path_params:
            continue
        names = _inner_names(arg.annotation)
        default_call = _last(default.func) if isinstance(default, ast.Call) else ""
        if default_call in ("Depends", "Security", "Header", "Cookie", "Path", "File", "Form"):
            continue
        if any(n in ("Request", "WebSocket", "UploadFile", "BackgroundTasks", "Response") for n in names):
            takes_raw_request = takes_raw_request or "Request" in names
            continue
        model = next((n for n in names if n in models), None)
        if model is not None and default_call != "Query":
            if shape.body is None:
                shape.body = dict(models[model])
                shape.source = model
            else:
                shape.body_open = True  # two body models are nested under their names; not modelled
            continue
        if default_call == "Body" or any(n in ("dict", "Dict", "Any") for n in names):
            shape.body_open = True
            continue
        if not names or all(n in _SIMPLE_TYPES or n in _WRAPPERS or n == "None" for n in names):
            required = default is None or (
                default_call == "Query" and (not default.args or (
                    isinstance(default.args[0], ast.Constant) and default.args[0].value is Ellipsis))
                and not any(k.arg == "default" for k in default.keywords))
            query[arg.arg] = required
    shape.query = query
    if takes_raw_request:
        shape.body_open = True   # the handler can read anything from the raw request
        shape.query = None
    for kw in decorator.keywords:
        if kw.arg == "response_model":
            model = next((n for n in _inner_names(kw.value) if n in models), None)
            if model is not None:
                shape.response = sorted(models[model])
    return shape


# ── API spec ──────────────────────────────────────────────────────────────────


def _deref(node, spec, depth: int = 0):
    while isinstance(node, dict) and "$ref" in node and depth < 10:
        target = spec
        for part in str(node["$ref"]).lstrip("#/").split("/"):
            target = target.get(part) if isinstance(target, dict) else None
        node, depth = target, depth + 1
    return node if isinstance(node, dict) else None


def _schema_fields(schema, spec) -> Optional[Dict[str, bool]]:
    schema = _deref(schema, spec)
    if schema is None:
        return None
    if schema.get("type") == "array":
        return _schema_fields(schema.get("items"), spec)
    fields: Dict[str, bool] = {}
    found = False
    for part in [schema] + [p for p in schema.get("allOf", []) if isinstance(p, dict)]:
        part = _deref(part, spec)
        if part and isinstance(part.get("properties"), dict):
            found = True
            required = set(part.get("required") or [])
            for name in part["properties"]:
                fields[str(name)] = name in required
    return fields if found else None


def _json_schema(content):
    if not isinstance(content, dict):
        return None
    for media, value in content.items():
        if "json" in str(media) and isinstance(value, dict):
            return value.get("schema")
    return None


def operation_shape(operation: dict, path_item: dict, spec: dict) -> Shape:
    shape = Shape(source="the spec")
    body = _deref(operation.get("requestBody"), spec)
    if body:
        shape.body = _schema_fields(_json_schema(body.get("content")), spec)
    parameters = [(_deref(p, spec) or {}) for p in (path_item.get("parameters") or []) + (operation.get("parameters") or [])]
    for p in parameters:   # Swagger 2 puts the body among the parameters
        if p.get("in") == "body" and shape.body is None:
            shape.body = _schema_fields(p.get("schema"), spec)
    shape.query = {str(p.get("name")): bool(p.get("required")) for p in parameters if p.get("in") == "query"}
    responses = operation.get("responses")
    if isinstance(responses, dict):
        for code in ("200", "201", 200, 201):
            response = _deref(responses.get(code), spec)
            if response:
                fields = _schema_fields(_json_schema(response.get("content")) or response.get("schema"), spec)
                if fields is not None:
                    shape.response = sorted(fields)
                    break
    return shape


# ── Frontend ──────────────────────────────────────────────────────────────────

_PAIRS = {"(": ")", "{": "}", "[": "]"}


def _balanced(source: str, start: int) -> str:
    """The text from an opening bracket at `start` to its match, brackets included."""
    stack, i, quote = [], start, ""
    while i < len(source):
        ch = source[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
        elif ch in _PAIRS:
            stack.append(_PAIRS[ch])
        elif stack and ch == stack[-1]:
            stack.pop()
            if not stack:
                return source[start:i + 1]
        i += 1
        if i - start > 4000:
            break
    return ""


def _split_top(inner: str, separators: str) -> List[str]:
    """Split on separators that are not inside brackets or quotes."""
    parts, depth, quote, current = [], 0, "", ""
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            current += ch
            if ch == "\\" and i + 1 < len(inner):
                current += inner[i + 1]
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "'\"`":
            quote = ch
            current += ch
        elif ch in _PAIRS:
            depth += 1
            current += ch
        elif ch in ")}]":
            depth -= 1
            current += ch
        elif ch in separators and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
        i += 1
    parts.append(current)
    return parts


_TS_TYPE = re.compile(r"\b(?:interface\s+(\w+)([^{=;]*)|type\s+(\w+)\s*=\s*)\{")


def ts_types(source: str) -> Dict[str, Tuple[Dict[str, bool], bool]]:
    """TypeScript object types in one file: name → ({field: required}, may have more fields)."""
    found: Dict[str, Tuple[Dict[str, bool], bool]] = {}
    for m in _TS_TYPE.finditer(source):
        block = _balanced(source, m.end() - 1)
        if not block:
            continue
        fields: Dict[str, bool] = {}
        extends = "extends" in (m.group(2) or "")
        tail = source[m.end() - 1 + len(block):][:3].strip()
        if m.group(3) and tail[:1] in ("&", "|"):
            extends = True   # an intersection or union: this block is not the whole type
        for part in _split_top(block[1:-1], ";,\n"):
            part = re.sub(r"//.*|/\*.*?\*/", "", part).strip()
            f = re.match(r"""^(?:readonly\s+)?(?:['"]([^'"]+)['"]|([A-Za-z_$][\w$]*))\s*(\?)?\s*:""", part)
            if f:
                fields[f.group(1) or f.group(2)] = not f.group(3)
            elif part.startswith("["):
                extends = True   # an index signature: any key is allowed
        found[m.group(1) or m.group(3)] = (fields, extends)
    return found


def resolve_body_types(call_shapes: Iterable[Shape], types: Dict[str, Tuple[Dict[str, bool], bool]]) -> None:
    for shape in call_shapes:
        if shape.body is None and shape.body_type in types:
            fields, more = types[shape.body_type]
            shape.body, shape.body_open = dict(fields), more
            shape.source = f"the frontend type `{shape.body_type}`"


def object_keys(literal: str) -> Tuple[Optional[List[str]], bool]:
    """Top-level keys of a JavaScript object literal, and whether it spreads another object."""
    if not (literal.startswith("{") and literal.endswith("}")):
        return None, False
    keys, spread = [], False
    for part in _split_top(literal[1:-1], ","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("..."):
            spread = True
            continue
        m = re.match(r"""^(?:['"]([^'"]+)['"]|([A-Za-z_$][\w$]*))\s*(?::|$|\()""", part)
        if not m:
            return None, False   # a computed key or something else this reader does not follow
        keys.append(m.group(1) or m.group(2))
    return keys, spread


def call_shape(source: str, call_start: int, url: str, axios_method: str = "") -> Shape:
    """What one fetch(...) or axios.<method>(...) call sends."""
    shape = Shape(source="the frontend")
    query = url.split("?", 1)[1].split("#", 1)[0] if "?" in url else ""
    if query and not query.startswith("${"):
        names = [p.split("=", 1)[0] for p in query.split("&") if p and not p.startswith("${")]
        if all(re.match(r"^[\w\-\[\].]+$", n) for n in names):
            shape.query = {n: True for n in names}
    paren = source.find("(", call_start)
    call = _balanced(source, paren) if paren != -1 else ""
    if not call:
        return shape
    literal, variable = "", ""
    if axios_method:
        if axios_method.lower() in ("post", "put", "patch"):
            m = re.match(r"\(\s*(['\"`])(?:\\.|(?!\1).)*\1\s*,\s*", call, re.DOTALL)
            if m and call[m.end():m.end() + 1] == "{":
                literal = _balanced(call, m.end())
            elif m:
                variable = (re.match(r"([A-Za-z_$][\w$]*)\s*[,)]", call[m.end():]) or [None, ""])[1]
    else:
        m = re.search(r"\bbody\s*:\s*JSON\.stringify\(\s*", call)
        if m and call[m.end():m.end() + 1] == "{":
            literal = _balanced(call, m.end())
        elif m:
            variable = (re.match(r"([A-Za-z_$][\w$]*)\s*\)", call[m.end():]) or [None, ""])[1]
    if variable:
        # The nearest earlier declaration of that name with a type: (req: NewOrder) or const req: NewOrder
        before = source[max(0, call_start - 1500):call_start]
        typed = re.findall(r"\b" + re.escape(variable) + r"\s*:\s*([A-Z]\w*)\b(?!\s*[<\[.(])", before)
        if typed:
            shape.body_type = typed[-1]
    if literal:
        keys, spread = object_keys(literal)
        if keys is not None:
            shape.body = {k: True for k in keys}
            shape.body_open = spread
    return shape


# ── Comparison ────────────────────────────────────────────────────────────────


@dataclass
class ShapeFinding:
    group: str
    title: str
    detail: str
    where: str = ""


def _list(names: Iterable[str]) -> str:
    return ", ".join(f"`{n}`" for n in sorted(names))


def compare_spec_to_backend(name: str, spec: Shape, backend: Shape, where: str) -> List[ShapeFinding]:
    out: List[ShapeFinding] = []
    if spec.body is not None and backend.body is not None and not backend.body_open:
        required_unlisted = {f for f, req in backend.body.items() if req and f not in spec.body}
        if required_unlisted:
            out.append(ShapeFinding(
                "wrong_now", f"{name}: the backend requires {_list(required_unlisted)}, which the spec does not list",
                "A client written from the spec will be refused.", where))
        unknown = set(spec.body) - set(backend.body)
        if unknown:
            out.append(ShapeFinding(
                "likely", f"{name}: the spec lists {_list(unknown)}, which the backend does not accept",
                f"The backend model `{backend.source}` has no such field, so the value is ignored or refused.", where))
        looser = {f for f, req in backend.body.items() if req and f in spec.body and not spec.body[f]}
        if looser:
            out.append(ShapeFinding(
                "likely", f"{name}: the spec says {_list(looser)} is optional, but the backend requires it",
                "A client that leaves it out, as the spec allows, will be refused.", where))
    elif spec.body is None and backend.body and any(backend.body.values()) and not backend.body_open:
        out.append(ShapeFinding(
            "likely", f"{name}: the backend takes a request body the spec does not describe",
            f"Required: {_list(f for f, req in backend.body.items() if req)}.", where))
    if spec.query is not None and backend.query is not None:
        required_unlisted = {f for f, req in backend.query.items() if req and f not in spec.query}
        if required_unlisted:
            out.append(ShapeFinding(
                "wrong_now",
                f"{name}: the backend requires the query parameter {_list(required_unlisted)}, which the spec does not list",
                "A client written from the spec will be refused.", where))
        unknown = set(spec.query) - set(backend.query)
        if unknown:
            out.append(ShapeFinding(
                "likely", f"{name}: the spec lists the query parameter {_list(unknown)}, which the backend does not read",
                "The value is silently ignored.", where))
    if spec.response is not None and backend.response is not None:
        missing = set(spec.response) - set(backend.response)
        extra = set(backend.response) - set(spec.response)
        if missing:
            out.append(ShapeFinding(
                "wrong_now", f"{name}: the spec promises {_list(missing)} in the response, which the backend does not return",
                "A client that reads it gets nothing.", where))
        if extra:
            out.append(ShapeFinding(
                "likely", f"{name}: the backend returns {_list(extra)}, which the spec does not mention",
                "Check that nothing private is returned by accident.", where))
    return out


def compare_frontend_to_backend(name: str, call: Shape, backend: Shape, where: str) -> List[ShapeFinding]:
    out: List[ShapeFinding] = []
    if call.body is not None and backend.body is not None and not backend.body_open:
        missing = {f for f, req in backend.body.items() if req and f not in call.body}
        if missing and not call.body_open:
            out.append(ShapeFinding(
                "wrong_now", f"{name}: the frontend does not send {_list(missing)}, which the backend requires",
                "The request will be refused.", where))
        unknown = set(call.body) - set(backend.body)
        if unknown:
            out.append(ShapeFinding(
                "likely", f"{name}: the frontend sends {_list(unknown)}, which the backend does not accept",
                f"The backend model `{backend.source}` has no such field, so what the user entered is dropped or refused.",
                where))
    if call.query is not None and backend.query is not None:
        unknown = set(call.query) - set(backend.query)
        if unknown:
            out.append(ShapeFinding(
                "likely", f"{name}: the frontend sends the query parameter {_list(unknown)}, which the backend does not read",
                "The value is silently ignored.", where))
        # A call with no query string in its text may still add one in code, so only a
        # written query string is checked for missing parameters.
        missing = {f for f, req in backend.query.items() if req and f not in call.query}
        if missing:
            out.append(ShapeFinding(
    "wrong_now", f"{name}: the frontend does not send the query parameter {_list(missing)}, which the backend requires",
    "The request will be refused.", where))
    return out
