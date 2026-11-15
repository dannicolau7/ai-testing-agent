"""
data_access.py — what each backend handler reads and writes.

Stage 4 of docs/ROADMAP.md, second step. For a Python handler it follows the function, and
the project functions it calls, and collects the SQL statements and SQLAlchemy calls it
finds: which table, read or write, which columns the statement filters on, and whether the
SQL text is built by inserting values into it.

It reads source. It does not run anything, and it sees only statements written as text or
as direct ORM calls. A query assembled across several variables is missed, and that is
reported as "not examined", never as "clean".
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple

MAX_DEPTH = 4
GUARD = "(a call that looks like a permission check)"
# Functions whose name says they decide whether the caller may proceed.
GUARD_CALL = re.compile(r"owner|permission|authori[sz]e|allowed|can_|has_access|check_access|ensure_|forbid", re.IGNORECASE)

_SQL_START = r"^\s*(SELECT\b.+?\bFROM\b|INSERT\s+INTO\b|UPDATE\s+[\w.\"`]+\s+SET\b|DELETE\s+FROM\b)"
# Text counts as SQL when its keywords are in capitals, or (any case) when it is handed
# straight to a call that runs SQL. "Select a file from the list" is neither.
_IS_SQL = re.compile(_SQL_START, re.DOTALL)
_IS_SQL_ANY_CASE = re.compile(_SQL_START, re.IGNORECASE | re.DOTALL)
_RUNS_SQL = {"execute", "executemany", "executescript", "text", "fetch", "fetchrow", "fetchval",
             "fetch_all", "fetch_one", "read_sql", "read_sql_query", "raw", "exec_driver_sql"}
_IDENT = r"[\"`\[]?([A-Za-z_][\w]*)[\"`\]]?"
_INSERT = re.compile(r"INSERT\s+INTO\s+(?:\w+\.)?" + _IDENT + r"\s*(?:\(([^)]*)\))?", re.IGNORECASE)
_UPDATE = re.compile(r"UPDATE\s+(?:\w+\.)?" + _IDENT + r"\s+SET\b(.*?)(?:\bWHERE\b(.*))?$", re.IGNORECASE | re.DOTALL)
_DELETE = re.compile(r"DELETE\s+FROM\s+(?:\w+\.)?" + _IDENT + r"(?:.*?\bWHERE\b(.*))?$", re.IGNORECASE | re.DOTALL)
_FROM = re.compile(r"\b(?:FROM|JOIN)\s+(?:\w+\.)?" + _IDENT, re.IGNORECASE)
_WHERE = re.compile(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bRETURNING\b|$)", re.IGNORECASE | re.DOTALL)
_COMPARED = re.compile(r"(?:\b\w+\.)?\b([A-Za-z_]\w*)\s*(?:=|!=|<>|<=|>=|<|>|\bIN\b|\bLIKE\b|\bIS\b|\bBETWEEN\b)", re.IGNORECASE)
_SQL_WORDS = {"and", "or", "not", "null", "true", "false", "where", "select", "from", "set", "in", "is", "like"}

_ORM_READ = {"query", "select", "select_from", "get", "scalars", "get_or_404"}
_ORM_WRITE = {"add", "merge", "insert", "update", "delete", "add_all"}


@dataclass
class DataAccess:
    kind: str                 # read | write
    table: str                # table name, or a model class name until resolved
    file: str
    line: int
    filters: List[str] = field(default_factory=list)   # columns the statement filters on
    columns: List[str] = field(default_factory=list)   # columns the statement writes
    built_from_values: bool = False                    # SQL text assembled with values
    inserted: List[str] = field(default_factory=list)  # names inserted into the text
    from_parameter: bool = False                       # one of them is a parameter of the function
    sql: bool = True                                   # False for ORM calls
    single_table: bool = True


@dataclass
class HandlerData:
    accesses: List[DataAccess] = field(default_factory=list)
    names: Set[str] = field(default_factory=set)       # every name the handler's code mentions
    # Names the code compares or filters on: `item.owner_id != user.id`, `WHERE owner_id = ?`.
    # A column that is only selected or assigned has not been checked.
    checked: Set[str] = field(default_factory=set)
    functions_followed: int = 0


# ── SQL text ──────────────────────────────────────────────────────────────────


def _compared(clause: str) -> List[str]:
    found = []
    for name in _COMPARED.findall(clause or ""):
        if name.lower() not in _SQL_WORDS and name not in found:
            found.append(name)
    return found


def parse_sql(text: str, file: str = "", line: int = 0, built: bool = False) -> List[DataAccess]:
    """The tables one SQL statement touches. Empty when the text is not SQL."""
    if not _IS_SQL_ANY_CASE.match(text):
        return []
    flat = " ".join(text.split())
    head = flat.split(None, 1)[0].upper()
    if head == "INSERT":
        m = _INSERT.search(flat)
        if not m:
            return []
        columns = [c.strip(' "`[]') for c in (m.group(2) or "").split(",") if c.strip()]
        out = [DataAccess("write", m.group(1), file, line, columns=columns, built_from_values=built)]
        # INSERT ... SELECT also reads.
        rest = flat[m.end():]
        out += [DataAccess("read", t, file, line, built_from_values=built, single_table=False)
                for t in _FROM.findall(rest)]
        return out
    if head == "UPDATE":
        m = _UPDATE.search(flat)
        if not m:
            return []
        return [DataAccess("write", m.group(1), file, line, filters=_compared(m.group(3)),
                           columns=_compared(m.group(2)), built_from_values=built)]
    if head == "DELETE":
        m = _DELETE.search(flat)
        if not m:
            return []
        return [DataAccess("write", m.group(1), file, line, filters=_compared(m.group(2)),
                           built_from_values=built)]
    tables = []
    for t in _FROM.findall(flat):
        if t.lower() not in _SQL_WORDS and t not in tables:
            tables.append(t)
    where = _WHERE.search(flat)
    filters = _compared(where.group(1)) if where else []
    return [DataAccess("read", t, file, line, filters=list(filters), built_from_values=built,
                       single_table=len(tables) == 1) for t in tables]


def _sql_text(node: ast.AST, any_case: bool = False) -> Optional[Tuple[str, bool, List[ast.AST]]]:
    """(text, built from values) when this expression is SQL text, else None."""
    _IS_SQL = _IS_SQL_ANY_CASE if any_case else globals()["_IS_SQL"]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value, False, []) if _IS_SQL.match(node.value) else None
    if isinstance(node, ast.JoinedStr):
        parts, inserted = [], []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{}")
                inserted.append(value)
        text = "".join(parts)
        return (text, bool(inserted), inserted) if _IS_SQL.match(text) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        left = _sql_text(node.left, any_case)
        if left is None:
            return None
        right = _sql_text(node.right, any_case) if isinstance(node.op, ast.Add) else None
        if isinstance(node.op, ast.Add) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
            return left[0] + node.right.value, left[1], left[2]  # two literals joined: not built from values
        return left[0] + (right[0] if right else " {}"), True, left[2] + [node.right]
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"):
        inner = _sql_text(node.func.value, any_case)
        return (inner[0], True, inner[2] + list(node.args) + [k.value for k in node.keywords]) if inner else None
    return None


# ── Following a handler ───────────────────────────────────────────────────────


def _last(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


FunctionIndex = Dict[str, List[Tuple[str, ast.AST]]]


def index_functions(trees: Iterable[Tuple[str, ast.AST]]) -> FunctionIndex:
    """Every function and method in the project, by name."""
    index: FunctionIndex = {}
    for file, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(node.name, []).append((file, node))
    return index


def _model_variables(func: ast.AST) -> Dict[str, str]:
    """Variables in a function that hold a model instance: item = Item(...), item = session.get(Item, id)."""
    found: Dict[str, str] = {}
    args = getattr(func, "args", None)
    for arg in (args.posonlyargs + args.args + args.kwonlyargs) if args else []:
        name = _last(arg.annotation) if arg.annotation is not None else ""
        if name[:1].isupper():
            found[arg.arg] = name                                # item: Item, current_user: CurrentUser
    for node in _walk_own(func):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        value = node.value
        if not isinstance(value, ast.Call):
            continue
        cls = ""
        if isinstance(value.func, ast.Name) and value.func.id[:1].isupper():
            cls = value.func.id                                  # Item(...)
        elif isinstance(value.func, ast.Attribute):
            owner = _last(value.func.value)
            if owner[:1].isupper():
                cls = owner                                      # Item.model_validate(...)
            elif value.func.attr in ("get", "get_or_404", "merge") and value.args:
                first = _last(value.args[0])
                cls = first if first[:1].isupper() else ""       # session.get(Item, id)
        if cls:
            found[node.targets[0].id] = cls
    return found


def _orm_accesses(call: ast.Call, file: str, variables: Optional[Dict[str, str]] = None) -> List[DataAccess]:
    method = _last(call.func)
    out = []
    if method in _ORM_READ or method in _ORM_WRITE:
        kind = "write" if method in _ORM_WRITE else "read"
        for arg in call.args:
            target = arg.func if (isinstance(arg, ast.Call) and method in ("add", "merge")) else arg
            name = _last(target) if isinstance(target, (ast.Name, ast.Attribute)) else ""
            if method in ("add", "delete", "merge", "refresh") and isinstance(target, ast.Name) and variables:
                name = variables.get(name, name)                 # session.add(item) where item is an Item
            if name[:1].isupper():   # a model class by convention
                out.append(DataAccess(kind, name, file, call.lineno, sql=False))
    return out


def _walk_own(func: ast.AST):
    """Nodes of a function, without the bodies of functions defined inside it."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def handler_data(func: ast.AST, file: str, index: FunctionIndex) -> HandlerData:
    data = HandlerData()
    seen: Set[int] = set()

    def visit(node: ast.AST, where: str, depth: int) -> None:
        if id(node) in seen or depth > MAX_DEPTH:
            return
        seen.add(id(node))
        data.functions_followed += 1
        consumed: Set[int] = set()   # string nodes that are part of a larger SQL expression
        variables = _model_variables(node)
        args = getattr(node, "args", None)
        params = {a.arg for a in (args.posonlyargs + args.args + args.kwonlyargs)} if args else set()

        def record(sql, line) -> None:
            names = sorted({n.id for expr in sql[2] for n in ast.walk(expr) if isinstance(n, ast.Name)})
            found = parse_sql(sql[0], where, line, sql[1])
            for access in found:
                access.inserted = names
                access.from_parameter = bool(params & set(names))
                data.names.update(access.filters)
                data.checked.update(access.filters)
            data.accesses.extend(found)
        nodes = sorted(_walk_own(node), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
        for child in nodes:
            if isinstance(child, ast.Name):
                data.names.add(child.id)
            elif isinstance(child, ast.Attribute):
                data.names.add(child.attr)
            elif isinstance(child, ast.keyword) and child.arg:
                data.names.add(child.arg)
            elif isinstance(child, ast.Subscript):
                key = child.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    data.names.add(key.value)        # post["author_id"]
            if isinstance(child, ast.Compare):
                for part in ast.walk(child):
                    if isinstance(part, ast.Name):
                        data.checked.add(part.id)
                    elif isinstance(part, ast.Attribute):
                        data.checked.add(part.attr)
                    elif isinstance(part, ast.Subscript) and isinstance(part.slice, ast.Constant) \
                            and isinstance(part.slice.value, str):
                        data.checked.add(part.slice.value)
            if isinstance(child, ast.Call):
                called = _last(child.func)
                if called in ("filter_by", "get_by", "find_by", "where", "filter"):
                    data.checked.update(k.arg for k in child.keywords if k.arg)
                if GUARD_CALL.search(called):
                    data.checked.add(GUARD)
            if isinstance(child, ast.Call) and _last(child.func) in _RUNS_SQL and child.args:
                direct = _sql_text(child.args[0], any_case=True)
                if direct is not None and id(child.args[0]) not in consumed:
                    for sub in ast.walk(child.args[0]):
                        consumed.add(id(sub))
                    record(direct, child.lineno)
            if isinstance(child, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.Call)) and id(child) not in consumed:
                sql = _sql_text(child)
                if sql is not None:
                    for sub in ast.walk(child):
                        consumed.add(id(sub))
                    record(sql, child.lineno)
                    continue
            if isinstance(child, ast.Call):
                data.accesses += _orm_accesses(child, where, variables)
                name = _last(child.func)
                targets = index.get(name, [])
                if len(targets) > 1 and isinstance(child.func, ast.Attribute):
                    # crud.create_user(...) means the create_user in crud.py, whatever else shares the name.
                    module = _last(child.func.value)
                    in_module = [t for t in targets if t[0].replace("\\", "/").rsplit("/", 1)[-1] == module + ".py"]
                    targets = in_module if len(in_module) == 1 else targets
                # Follow a call only when the project defines exactly one function of that name.
                if len(targets) == 1 and targets[0][1] is not node:
                    visit(targets[0][1], targets[0][0], depth + 1)

    visit(func, file, 0)
    return data
