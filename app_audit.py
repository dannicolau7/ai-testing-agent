"""
app_audit.py — read an application's source and check that its layers agree.

Stage 4 of docs/ROADMAP.md, first version. No AI involved. Given a repository it builds a
model from four kinds of source:

- backend routes      FastAPI and Flask (Python), Express (JavaScript / TypeScript)
- frontend API calls  fetch(...) and axios in JavaScript / TypeScript
- the OpenAPI spec    openapi / swagger files (YAML or JSON)
- the database        CREATE TABLE in .sql files, SQLAlchemy models in Python

and reports where they disagree, in four groups:

- wrong now            one layer relies on something another layer does not provide
- likely to go wrong   nothing is broken yet, but nothing would stop a mistake
- unclear              the tool could not tell; a person should look
- not examined         what this audit did not look at, stated plainly

It reads source text. It does not run the application, follow what a handler does, or
know the requirements. A clean report means these layers agree with each other, not that
the product is right.

Public API:

    model  = build_model("path/to/repo")
    report = audit(model)
    print(render_markdown(report))
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import data_access

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", ".next",
    "out", "coverage", ".pytest_cache", ".mypy_cache", "site-packages", "vendor", "target",
}
HTTP_METHODS = ("get", "post", "put", "patch", "delete")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
MAX_FILE_BYTES = 1_000_000
# Names that suggest a route checks who is calling. Evidence, not proof.
AUTH_WORDS = re.compile(
    r"auth|login|logged|current_user|get_user|token|jwt|session|permission|role|admin|"
    r"require|verify|protect|guard|api_key|apikey|oauth|bearer|principal|identity",
    re.IGNORECASE,
)
NOT_AUTH = re.compile(r"^(get_)?(db|session|database|settings|config|conn|connection)$", re.IGNORECASE)


@dataclass
class Route:
    method: str
    path: str
    file: str
    line: int
    handler: str = ""
    auth_evidence: List[str] = field(default_factory=list)
    # What the handler reads and writes. None when the handler's code was not followed.
    data: Optional[data_access.HandlerData] = None

    @property
    def key(self) -> Tuple[str, str]:
        return self.method, normalize_path(self.path)


@dataclass
class ApiCall:
    method: str
    path: str  # "" when the URL could not be read from the source
    file: str
    line: int
    raw: str = ""

    @property
    def key(self) -> Tuple[str, str]:
        return self.method, normalize_path(self.path)


@dataclass
class Column:
    name: str
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    foreign_key: str = ""


@dataclass
class Table:
    name: str
    file: str
    line: int
    columns: List[Column] = field(default_factory=list)
    model_class: str = ""  # the SQLAlchemy class, when the table came from one


@dataclass
class AppModel:
    root: str
    routes: List[Route] = field(default_factory=list)
    calls: List[ApiCall] = field(default_factory=list)
    spec_operations: List[Route] = field(default_factory=list)
    spec_files: List[str] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    files_read: int = 0
    files_skipped: List[str] = field(default_factory=list)


@dataclass
class Finding:
    group: str  # wrong_now | likely | unclear
    title: str
    detail: str
    where: str


@dataclass
class AuditReport:
    model: AppModel
    findings: List[Finding] = field(default_factory=list)
    not_examined: List[str] = field(default_factory=list)

    def of(self, group: str) -> List[Finding]:
        return [f for f in self.findings if f.group == group]

    @property
    def ok(self) -> bool:
        return not self.of("wrong_now")


# ── Paths ─────────────────────────────────────────────────────────────────────


def normalize_path(path: str) -> str:
    """One form for a path whatever the framework: parameters become {}."""
    path = path.split("?", 1)[0].split("#", 1)[0].strip()
    path = re.sub(r"\$\{[^}]*\}", "{}", path)          # JS template: ${id}
    path = re.sub(r"\{[^}/]*\}", "{}", path)           # OpenAPI / FastAPI: {id}
    path = re.sub(r"<[^>/]*>", "{}", path)             # Flask: <int:id>
    path = re.sub(r"(?<=/):[A-Za-z_][A-Za-z0-9_]*", "{}", path)  # Express: :id
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"/{2,}", "/", path)
    return path.rstrip("/") or "/"


def _files(root: Path, suffixes: Sequence[str], model: AppModel) -> List[Path]:
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                model.files_skipped.append(f"{path.relative_to(root)} (larger than 1 MB)")
                continue
        except OSError:
            continue
        found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# ── Backend: Python ───────────────────────────────────────────────────────────


def _const(node: Optional[ast.AST]) -> Optional[str]:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _depends_names(func: ast.AST) -> List[str]:
    """Names inside Depends(...) / Security(...) in a handler's parameters and decorators."""
    names = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _name(node.func).split(".")[-1] in ("Depends", "Security"):
            for arg in node.args:
                names.append(_name(arg))
    return [n for n in names if n]


def _auth_evidence(func: ast.AST, decorators: List[ast.AST]) -> List[str]:
    evidence = []
    for name in _depends_names(func):
        last = name.split(".")[-1]
        if AUTH_WORDS.search(last) and not NOT_AUTH.match(last):
            evidence.append(f"Depends({name})")
    for decorator in decorators:
        name = _name(decorator)
        last = name.split(".")[-1]
        if last.lower() in HTTP_METHODS or last in ("route", "api_route"):
            continue
        if AUTH_WORDS.search(last):
            evidence.append(f"@{name}")
    return evidence


def python_routes(source: str, filename: str) -> List[Route]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            attr = decorator.func.attr
            path = _const(decorator.args[0]) if decorator.args else None
            if path is None:
                continue
            methods: List[str] = []
            if attr in HTTP_METHODS:
                methods = [attr.upper()]
            elif attr in ("route", "api_route"):
                for kw in decorator.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        methods = [m.upper() for m in (_const(e) for e in kw.value.elts) if m]
                methods = methods or ["GET"]
            evidence = _auth_evidence(node, node.decorator_list) if methods else []
            for method in methods:
                routes.append(Route(method, path, filename, node.lineno, node.name, list(evidence)))
    return routes


# ── Backend and frontend: JavaScript / TypeScript ─────────────────────────────

_EXPRESS = re.compile(
    r"\b(\w+)\.(get|post|put|patch|delete)\(\s*(['\"`])(/[^'\"`]*)\3\s*,([^\n]*)", re.IGNORECASE
)
_FETCH = re.compile(r"\bfetch\(\s*(['\"`])((?:\\.|(?!\1).)*)\1\s*(?:,\s*\{([^}]*)\})?", re.DOTALL)
_AXIOS = re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*(['\"`])((?:\\.|(?!\2).)*)\2", re.IGNORECASE)
_FETCH_DYNAMIC = re.compile(r"\bfetch\(\s*([A-Za-z_$][\w$.]*)\s*[,)]")
_METHOD_OPTION = re.compile(r"method\s*:\s*['\"`](\w+)['\"`]", re.IGNORECASE)
_EXPRESS_OBJECTS = {"app", "router", "api", "server", "routes"}


def _line(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _url_path(url: str) -> str:
    """The path part of a URL written in source, or "" if it cannot be told."""
    url = url.strip()
    url = re.sub(r"^\$\{[^}]*\}", "", url)                 # ${API_BASE}/orders -> /orders
    url = re.sub(r"^https?://[^/]+", "", url)              # http://host/orders -> /orders
    if not url.startswith("/"):
        return ""
    return url


def js_routes(source: str, filename: str) -> List[Route]:
    routes = []
    for m in _EXPRESS.finditer(source):
        obj, method, _, path, rest = m.groups()
        if obj.lower() not in _EXPRESS_OBJECTS and not obj.lower().endswith("router"):
            continue  # axios.get("/x", ...) and similar are calls, not routes
        middleware = [w for w in re.findall(r"[A-Za-z_$][\w$]*", rest.split("=>")[0])
                      if AUTH_WORDS.search(w) and w not in ("req", "res", "next", "async", "function")]
        routes.append(Route(method.upper(), path, filename, _line(source, m.start()), "", middleware[:3]))
    return routes


def js_calls(source: str, filename: str) -> List[ApiCall]:
    calls = []
    for m in _FETCH.finditer(source):
        url, options = m.group(2), m.group(3) or ""
        method = (_METHOD_OPTION.search(options) or [None, "GET"])[1].upper()
        calls.append(ApiCall(method, _url_path(url), filename, _line(source, m.start()), url[:80]))
    for m in _AXIOS.finditer(source):
        calls.append(ApiCall(m.group(1).upper(), _url_path(m.group(3)), filename,
                             _line(source, m.start()), m.group(3)[:80]))
    for m in _FETCH_DYNAMIC.finditer(source):
        calls.append(ApiCall("?", "", filename, _line(source, m.start()), m.group(1)[:80]))
    return calls


# ── OpenAPI ───────────────────────────────────────────────────────────────────


def spec_operations(path: Path, root: Path) -> List[Route]:
    text = _read(path)
    if not re.search(r"^\s*[\"']?(openapi|swagger)[\"']?\s*:", text, re.MULTILINE):
        return []
    try:
        if path.suffix.lower() == ".json":
            spec = json.loads(text)
        else:
            import yaml

            spec = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 - an unreadable spec is reported as not examined
        return []
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        return []
    base = ""
    servers = spec.get("servers")
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        base = re.sub(r"^https?://[^/]+", "", str(servers[0].get("url", ""))).rstrip("/")
    base = base or str(spec.get("basePath", "")).rstrip("/")
    operations = []
    rel = str(path.relative_to(root))
    for route_path, item in spec["paths"].items():
        if not isinstance(item, dict):
            continue
        for method in HTTP_METHODS:
            if isinstance(item.get(method), dict):
                security = item[method].get("security", spec.get("security"))
                evidence = ["security in the spec"] if security else []
                operations.append(Route(method.upper(), base + str(route_path), rel, 0,
                                        str(item[method].get("operationId", "")), evidence))
    return operations


# ── Database ──────────────────────────────────────────────────────────────────

_CREATE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?([\w.]+)[`\"\]]?\s*\((.*?)\)\s*(?:;|$)",
    re.IGNORECASE | re.DOTALL,
)


def _split_columns(body: str) -> List[str]:
    parts, depth, current = [], 0, ""
    for ch in body:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    return [p.strip() for p in [*parts, current] if p.strip()]


def sql_tables(source: str, filename: str) -> List[Table]:
    # Comments go first, keeping line breaks so line numbers stay right.
    source = re.sub(r"--[^\n]*", "", source)
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.DOTALL)
    tables = []
    for m in _CREATE.finditer(source):
        table = Table(m.group(1).split(".")[-1], filename, _line(source, m.start()))
        constraints = []
        for part in _split_columns(m.group(2)):
            upper = part.upper()
            if re.match(r"(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CONSTRAINT|CHECK|KEY|INDEX)\b", upper):
                constraints.append(part)
                continue
            name = re.match(r"[`\"\[]?(\w+)[`\"\]]?", part)
            if not name:
                continue
            ref = re.search(r"REFERENCES\s+[`\"\[]?([\w.]+)", part, re.IGNORECASE)
            table.columns.append(Column(
                name=name.group(1),
                primary_key="PRIMARY KEY" in upper,
                nullable="NOT NULL" not in upper and "PRIMARY KEY" not in upper,
                unique=bool(re.search(r"\bUNIQUE\b", upper)),
                foreign_key=ref.group(1) if ref else "",
            ))
        by_name = {c.name.lower(): c for c in table.columns}
        for constraint in constraints:
            cols = [c.strip(" `\"[]").lower() for c in
                    (re.search(r"\(([^)]*)\)", constraint) or [None, ""])[1].split(",")]
            upper = constraint.upper()
            for col in cols:
                if col not in by_name:
                    continue
                if "PRIMARY KEY" in upper:
                    by_name[col].primary_key, by_name[col].nullable = True, False
                elif "FOREIGN KEY" in upper:
                    ref = re.search(r"REFERENCES\s+[`\"\[]?([\w.]+)", constraint, re.IGNORECASE)
                    by_name[col].foreign_key = ref.group(1) if ref else "?"
                elif "UNIQUE" in upper and len(cols) == 1:
                    by_name[col].unique = True
        tables.append(table)
    return tables


def sqlalchemy_tables(source: str, filename: str) -> List[Table]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    tables = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        name = None
        columns = []
        for stmt in node.body:
            target = None
            value = getattr(stmt, "value", None)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = _name(stmt.targets[0])
            elif isinstance(stmt, ast.AnnAssign):
                target = _name(stmt.target)
            if target == "__tablename__":
                name = _const(value)
            elif target and isinstance(value, ast.Call) and _name(value.func).split(".")[-1] in (
                "Column", "mapped_column"
            ):
                column = Column(name=target)
                for kw in value.keywords:
                    flag = kw.value.value if isinstance(kw.value, ast.Constant) else None
                    if kw.arg == "primary_key" and flag is True:
                        column.primary_key, column.nullable = True, False
                    elif kw.arg == "nullable" and flag is False:
                        column.nullable = False
                    elif kw.arg == "unique" and flag is True:
                        column.unique = True
                for arg in value.args:
                    if isinstance(arg, ast.Call) and _name(arg.func).split(".")[-1] == "ForeignKey":
                        column.foreign_key = _const(arg.args[0]) if arg.args else "?"
                columns.append(column)
        if name:
            tables.append(Table(name, filename, node.lineno, columns, node.name))
    return tables


# ── Model ─────────────────────────────────────────────────────────────────────


def _attach_handler_data(model: AppModel, trees: List[Tuple[str, ast.AST]]) -> None:
    """Follow each Python handler into the code it calls and record its data access."""
    index = data_access.index_functions(trees)
    by_place = {}
    for file, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                by_place[(file, node.lineno, node.name)] = node
    for route in model.routes:
        node = by_place.get((route.file, route.line, route.handler))
        if node is not None:
            route.data = data_access.handler_data(node, route.file, index)


def build_model(root_path: str) -> AppModel:
    root = Path(root_path).resolve()
    model = AppModel(root=str(root))
    trees: List[Tuple[str, ast.AST]] = []
    for path in _files(root, (".py",), model):
        source, rel = _read(path), str(path.relative_to(root))
        if path.name.startswith("test_") or path.name.endswith("_test.py") or "tests" in path.parts:
            continue
        model.files_read += 1
        model.routes += python_routes(source, rel)
        model.tables += sqlalchemy_tables(source, rel)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            model.files_skipped.append(f"{rel} (could not be parsed as Python)")
            continue
        trees.append((rel, tree))
        # Tables created from Python, as in db.execute("CREATE TABLE ...").
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "CREATE TABLE" in node.value.upper():
                for table in sql_tables(node.value, rel):
                    table.line += node.lineno - 1
                    model.tables.append(table)
    _attach_handler_data(model, trees)
    for path in _files(root, (".js", ".jsx", ".ts", ".tsx", ".mjs", ".vue", ".svelte"), model):
        source, rel = _read(path), str(path.relative_to(root))
        if re.search(r"\.(test|spec)\.[jt]sx?$", path.name):
            continue
        model.files_read += 1
        model.routes += js_routes(source, rel)
        model.calls += js_calls(source, rel)
    for path in _files(root, (".sql",), model):
        model.files_read += 1
        model.tables += sql_tables(_read(path), str(path.relative_to(root)))
    for path in _files(root, (".yaml", ".yml", ".json"), model):
        operations = spec_operations(path, root)
        if operations:
            model.files_read += 1
            model.spec_files.append(str(path.relative_to(root)))
            model.spec_operations += operations
    classes = {t.model_class: t.name for t in model.tables if t.model_class}
    for route in model.routes:
        if route.data is None:
            continue
        for access in route.data.accesses:
            if not access.sql:
                access.table = classes.get(access.table, "")
        # A capitalised name passed to the ORM that is not a known model is not data access.
        route.data.accesses = [a for a in route.data.accesses if a.table]
    return model


# ── Audit ─────────────────────────────────────────────────────────────────────


def _show(path: str) -> str:
    """A path as a person would write it: /orders/${id} becomes /orders/{id}."""
    return re.sub(r"\$\{\s*([\w.]*)[^}]*\}", lambda m: "{" + (m.group(1).split(".")[-1] or "") + "}", path)


def _where(item) -> str:
    return f"{item.file}:{item.line}" if getattr(item, "line", 0) else item.file


def _match(key: Tuple[str, str], keys: Set[Tuple[str, str]]) -> bool:
    """Exact match, or the same route under a common prefix such as /api or /api/v1."""
    if key in keys:
        return True
    method, path = key
    stripped = re.sub(r"^/(api/v\d+|api|v\d+)(?=/)", "", path)
    return any(m == method and (p == stripped or re.sub(r"^/(api/v\d+|api|v\d+)(?=/)", "", p) == path
                                or re.sub(r"^/(api/v\d+|api|v\d+)(?=/)", "", p) == stripped)
               for m, p in keys)


# Routes a frontend is not expected to call.
OPERATIONAL = re.compile(r"^/$|^/(health|healthz|ready|readyz|live|livez|metrics|ping|status|docs|openapi\.json)$")
# A column that says whose row this is.
OWNER_COLUMN = re.compile(
    r"^(user|owner|customer|account|tenant|org|organi[sz]ation|member|author|creator|created_by)(_id)?$",
    re.IGNORECASE,
)
# Evidence that the caller is meant to reach every row.
ADMIN_WORDS = re.compile(r"admin|staff|superuser|role|permission|scope", re.IGNORECASE)
# Tables a read may reasonably write to.
LOG_LIKE = re.compile(r"log|audit|event|metric|stat|view|visit|session|token|cache|history", re.IGNORECASE)


def _audit_data_access(model: AppModel, add) -> None:
    """Checks that need to know what a handler reads and writes."""
    followed = [r for r in model.routes if r.data is not None]
    tables = {t.name.lower(): t for t in model.tables}
    touched: Set[str] = set()
    reported: Set[Tuple[str, str, int]] = set()

    def once(group, title, detail, access) -> None:
        key = (title, access.file, access.line)
        if key not in reported:
            reported.add(key)
            add(group, title, detail, f"{access.file}:{access.line}")

    for route in followed:
        name = f"{route.method} {route.path}"
        for access in route.data.accesses:
            table = tables.get(access.table.lower())
            touched.add(access.table.lower())
            if access.built_from_values and access.from_parameter:
                once("likely", f"SQL on `{access.table}` is built by inserting a function argument into the text",
                     f"Reached from {name}. Inserted: {', '.join(access.inserted)}. If the argument comes "
                     "from the request, a caller can change the query. Pass values as parameters.", access)
            elif access.built_from_values:
                once("unclear", f"SQL on `{access.table}` is assembled from pieces",
                     f"Reached from {name}. Inserted: {', '.join(access.inserted) or 'an expression'}. "
                     "This is safe only if every piece is fixed text; a person should confirm.", access)
            if not model.tables or not access.sql:
                continue
            if table is None:
                once("wrong_now", f"The code uses table `{access.table}`, which the database does not define",
                     f"Reached from {name}. The statement will fail when it runs, unless the table is "
                     "created somewhere this audit did not read.", access)
                continue
            known = {c.name.lower() for c in table.columns}
            if known and access.single_table:
                for column in access.columns + access.filters:
                    if column.lower() not in known:
                        once("wrong_now",
                             f"The code uses column `{access.table}.{column}`, which the table does not have",
                             f"Reached from {name}. The statement will fail when it runs.", access)

        # A read that also writes.
        if route.method == "GET":
            for access in route.data.accesses:
                if access.kind == "write" and not LOG_LIKE.search(access.table):
                    add("likely", f"{name} changes `{access.table}`",
                        "A GET request is expected to read only. Browsers, crawlers and caches repeat GET "
                        "requests freely.", f"{access.file}:{access.line}")
                    break

        # A row fetched by its id, with no sign that the caller owns it.
        if "{}" not in normalize_path(route.path):
            continue
        if route.method in MUTATING and not route.auth_evidence:
            continue  # already reported: no access check at all
        if any(ADMIN_WORDS.search(e) for e in route.auth_evidence):
            continue
        for access in route.data.accesses:
            table = tables.get(access.table.lower())
            if table is None or (access.kind == "write" and not access.filters):
                continue
            owners = [c.name for c in table.columns if OWNER_COLUMN.match(c.name) and not c.primary_key]
            mentioned = {n.lower() for n in route.data.names}
            if owners and not any(o.lower() in mentioned for o in owners):
                verb = "reads" if access.kind == "read" else "changes"
                add("likely", f"{name} {verb} `{table.name}` without checking who owns the row",
                    f"`{table.name}` has an owner column (`{owners[0]}`), and nothing this handler runs "
                    "mentions it. A signed-in user may be able to reach another user's row by changing "
                    "the id.", f"{access.file}:{access.line}")
                break

    if followed and touched and model.tables:
        for table in model.tables:
            if table.name.lower() not in touched:
                add("unclear", f"No route reads or writes table `{table.name}`",
                    "It may be used by code this audit did not follow, or it may be unused.", _where(table))


def _names_a_table(column: str, tables: List[Table]) -> bool:
    """True when an _id column is named after a table: address_id or shipping_address_id → addresses."""
    stem = column.lower()[:-3]
    for table in tables:
        name = table.name.lower()
        singular = {name, name[:-1] if name.endswith("s") else name, name[:-2] if name.endswith("es") else name}
        if any(stem == s or stem.endswith("_" + s) for s in singular):
            return True
    return False


def audit(model: AppModel) -> AuditReport:
    report = AuditReport(model=model)
    add = lambda group, title, detail, where: report.findings.append(  # noqa: E731
        Finding(group, title, detail, where))
    route_keys = {r.key for r in model.routes}
    spec_keys = {o.key for o in model.spec_operations}
    call_keys = {c.key for c in model.calls if c.path}

    # Frontend against backend.
    if model.routes and model.calls:
        seen = set()
        for call in model.calls:
            if not call.path:
                if (call.file, call.raw) not in seen:
                    seen.add((call.file, call.raw))
                    add("unclear", "A frontend request whose address is built at run time",
                        f"`{call.raw}` is not a literal address, so it was not checked.", _where(call))
                continue
            if call.key in seen:
                continue
            seen.add(call.key)
            if not _match(call.key, route_keys):
                other = sorted(m for m, p in route_keys if _match((m, call.key[1]), {(m, p)}))
                hint = f" The backend defines {', '.join(other)} for that path." if other else ""
                add("wrong_now", f"The frontend calls {call.method} {_show(call.path)}, which no backend route defines",
                    "A user action that makes this request will fail." + hint, _where(call))

    # Spec against backend.
    if model.spec_operations and model.routes:
        for op in model.spec_operations:
            if not _match(op.key, route_keys):
                add("wrong_now", f"The API spec documents {op.method} {op.path}, which the backend does not implement",
                    "Anyone building against the spec will call something that is not there.", op.file)
        for route in model.routes:
            if not _match(route.key, spec_keys):
                add("likely", f"{route.method} {route.path} is not in the API spec",
                    "An undocumented route is easy to change or break without anyone noticing.", _where(route))

    # Routes that change data with no sign of an access check.
    for route in model.routes:
        if route.method in MUTATING and not route.auth_evidence:
            documented = [o for o in model.spec_operations if o.key == route.key and o.auth_evidence]
            if documented:
                add("wrong_now", f"The spec says {route.method} {route.path} needs authentication, but the code shows no check",
                    "No dependency, decorator or middleware on this route looks like an access check.", _where(route))
            else:
                add("likely", f"{route.method} {route.path} changes data and shows no access check",
                    "No dependency, decorator or middleware on this route looks like an access check. "
                    "It may be applied somewhere this audit cannot see, such as a global middleware.",
                    _where(route))

    # Backend routes the frontend never uses.
    if model.routes and model.calls:
        uncalled = [r for r in model.routes if not _match(r.key, call_keys)
                    and not OPERATIONAL.match(normalize_path(r.path))]
        if len(uncalled) > 5:
            # This many usually means the frontend calls the API in a way this audit cannot read.
            listed = ", ".join(f"{r.method} {r.path}" for r in uncalled[:12])
            more = f" and {len(uncalled) - 12} more" if len(uncalled) > 12 else ""
            add("unclear", f"{len(uncalled)} backend routes are not called by any frontend request this audit could read",
                f"{listed}{more}. With this many, the frontend probably calls them through a helper, or "
                "they serve another client.", _where(uncalled[0]))
        else:
            for route in uncalled:
                add("unclear", f"Nothing in the frontend calls {route.method} {route.path}",
                    "It may serve another client, or it may be dead code.", _where(route))

    _audit_data_access(model, add)

    # Database structure.
    for table in model.tables:
        if table.columns and not any(c.primary_key for c in table.columns):
            add("likely", f"Table {table.name} has no primary key",
                "Rows cannot be told apart reliably, and duplicates are not prevented.", _where(table))
        for column in table.columns:
            if (column.name.lower().endswith("_id") and not column.foreign_key and not column.primary_key
                    and _names_a_table(column.name, model.tables)):
                add("likely", f"{table.name}.{column.name} looks like a reference but has no foreign key",
                    "The database will accept a value that points at nothing.", _where(table))

    layers = [("backend routes", model.routes), ("frontend API calls", model.calls),
              ("API spec operations", model.spec_operations), ("database tables", model.tables)]
    for label, found in layers:
        if not found:
            report.not_examined.append(f"No {label} were found, so checks that need them were skipped.")
    report.not_examined += [
        "Handler logic beyond data access: for Python handlers this audit follows the code to the "
        "SQL and ORM calls it makes; it does not check conditions, validation or what is returned.",
        "Queries assembled across several variables, and data access in JavaScript backends.",
        "The running application: nothing was started, called or queried.",
        "Requirements: use `trace` to compare requirements with tests.",
        "Access checks applied globally (middleware, gateways) or in languages other than Python and JavaScript/TypeScript.",
        "Frontend requests made through wrappers other than fetch and axios.",
    ]
    report.not_examined += [f"Skipped: {item}" for item in model.files_skipped]
    return report


# ── Rendering ─────────────────────────────────────────────────────────────────

_GROUPS = [
    ("wrong_now", "Wrong now", "One layer relies on something another layer does not provide."),
    ("likely", "Likely to go wrong", "Nothing is broken yet, but nothing would stop a mistake."),
    ("unclear", "Unclear", "The audit could not tell. A person should look."),
]


def render_markdown(report: AuditReport) -> str:
    m = report.model
    lines = [
        "# Application audit",
        "",
        f"Read {m.files_read} source files under `{Path(m.root).name}`.",
        "",
        "| Layer | Found |",
        "|---|---|",
        f"| Backend routes | {len(m.routes)} |",
        f"| Frontend API calls | {len([c for c in m.calls if c.path])} |",
        f"| Operations in the API spec | {len(m.spec_operations)} |",
        f"| Database tables | {len(m.tables)} |",
        f"| Routes whose data access was found | {len([r for r in m.routes if r.data and r.data.accesses])} of {len(m.routes)} |",
        "",
        "This compares the layers with each other. It does not run the application or know the",
        "requirements, so a clean result means the layers agree, not that the product is right.",
        "",
    ]
    for key, title, meaning in _GROUPS:
        items = report.of(key)
        lines += [f"## {title} ({len(items)})", "", meaning, ""]
        for f in items:
            lines += [f"- **{f.title}**", f"  {f.detail} `{f.where}`"]
        if not items:
            lines.append("- None found.")
        lines.append("")
    lines += ["## Not examined", ""] + [f"- {item}" for item in report.not_examined] + [""]
    return "\n".join(lines).rstrip() + "\n"
