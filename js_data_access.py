"""
js_data_access.py — what a JavaScript or TypeScript handler reads and writes.

The Python reader (`data_access.py`) works on a syntax tree. There is no JavaScript parser
in the standard library, so this reader works on text: it finds each function's body by
matching brackets, follows calls to functions the project defines once, and looks for

- Prisma calls        prisma.article.findMany({ where: { authorId } })
- SQL in strings      db.query('SELECT ... FROM orders WHERE id = $1') and sql`...` templates

It is less exact than the Python reader and says less: it never checks column names, and a
query built by a query builder (Knex, Sequelize, TypeORM) is not read. What it does give is
which tables a route touches and which names its code mentions, which is what the
ownership check needs.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

import data_access
from shapes import _balanced

MAX_DEPTH = 4

_FUNCTION = re.compile(r"\b(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*(?:<[^>(]*>)?\s*\(")
_ARROW = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=;]{0,200}?)?=\s*(?:async\s*)?(?:<[^>(]*>\s*)?\(")
_METHOD = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[^{;]+)?\{",
                     re.MULTILINE)
_PRISMA = re.compile(
    r"\b(?:this\.)?(?:prisma|db|tx|client|prismaClient)\.([A-Za-z_$][\w$]*)\."
    r"(findMany|findFirst|findFirstOrThrow|findUnique|findUniqueOrThrow|count|aggregate|groupBy|"
    r"create|createMany|update|updateMany|upsert|delete|deleteMany)\s*\(")
_PRISMA_WRITES = {"create", "createMany", "update", "updateMany", "upsert", "delete", "deleteMany"}
_STRING = re.compile(r"(['\"`])((?:\\.|(?!\1).)*)\1", re.DOTALL)
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_CALL = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(|\.([A-Za-z_$][\w$]*)\s*\(")
_COMPARE = re.compile(r"([\w$.?!\[\]'\"]+)\s*(?:===|!==|==|!=)\s*([\w$.?!\[\]'\"]+)")
_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "await", "typeof", "new", "throw"}

FunctionIndex = Dict[str, List[Tuple[str, str, int]]]   # name → [(file, body, line)]


def _line(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def index_functions(sources: List[Tuple[str, str]]) -> FunctionIndex:
    """Every named function in the project's JavaScript and TypeScript, with its body."""
    index: FunctionIndex = {}
    for file, source in sources:
        for pattern in (_FUNCTION, _ARROW):
            for m in pattern.finditer(source):
                args = _balanced(source, m.end() - 1)
                if not args:
                    continue
                rest = source[m.end() - 1 + len(args):]
                opener = re.match(r"\s*(?::\s*[^={;]{0,200}?)?(?:=>\s*)?\{", rest)
                if not opener or (pattern is _ARROW and "=>" not in opener.group(0)):
                    continue
                start = m.end() - 1 + len(args) + opener.end() - 1
                body = _balanced(source, start)
                if body:
                    index.setdefault(m.group(1), []).append((file, body, _line(source, m.start())))
        for m in _METHOD.finditer(source):          # methods of a class or an object
            if m.group(1) in _KEYWORDS or m.group(1) == "constructor":
                continue
            body = _balanced(source, m.end() - 1)
            if body and all(known[2] != _line(source, m.start()) or known[0] != file
                            for known in index.get(m.group(1), [])):
                index.setdefault(m.group(1), []).append((file, body, _line(source, m.start())))
    return index


def handler_data(body: str, file: str, line: int, index: FunctionIndex) -> data_access.HandlerData:
    """What one handler's code reads and writes, following the project functions it calls."""
    data = data_access.HandlerData()
    seen: Set[Tuple[str, int]] = set()

    def visit(text: str, where: str, start_line: int, depth: int) -> None:
        if (where, start_line) in seen or depth > MAX_DEPTH:
            return
        seen.add((where, start_line))
        data.functions_followed += 1
        data.names.update(_IDENT.findall(text))
        for m in _PRISMA.finditer(text):
            call = _balanced(text, m.end() - 1)
            kind = "write" if m.group(2) in _PRISMA_WRITES else "read"
            keys = re.findall(r"([A-Za-z_$][\w$]*)\s*[:,}]", call)      # where: { slug, authorId: id }
            where_block = re.search(r"\bwhere\s*:\s*\{", call)
            filters = re.findall(r"([A-Za-z_$][\w$]*)\s*[:,}]", _balanced(call, where_block.end() - 1)) if where_block else []
            data.accesses.append(data_access.DataAccess(
                kind, m.group(1), where, start_line + text.count("\n", 0, m.start()),
                filters=list(dict.fromkeys(filters)), sql=False))
            data.names.update(keys)
            data.checked.update(filters)
        for m in _STRING.finditer(text):
            value = m.group(2)
            if not data_access._IS_SQL.match(value) and not (
                    data_access._IS_SQL_ANY_CASE.match(value)
                    and re.search(r"\b(query|execute|raw|run|all|get|prepare|sql)\w*\s*[(`]\s*$", text[:m.start()])):
                continue
            built = m.group(1) == "`" and "${" in value
            found = data_access.parse_sql(re.sub(r"\$\{[^}]*\}", "{}", value), where,
                                          start_line + text.count("\n", 0, m.start()), built)
            for access in found:
                access.inserted = sorted(set(re.findall(r"\$\{\s*([A-Za-z_$][\w$]*)", value)))
                data.names.update(access.filters)
                data.checked.update(access.filters)
            data.accesses.extend(found)
        for m in _COMPARE.finditer(text):               # existingArticle.author.id !== id
            data.checked.update(_IDENT.findall(m.group(1) + " " + m.group(2)))
        for m in _CALL.finditer(text):
            name = m.group(1) or m.group(2)
            if data_access.GUARD_CALL.search(name):
                data.checked.add(data_access.GUARD)
            targets = index.get(name, [])
            # Follow a call only when the project defines exactly one function of that name.
            if name not in _KEYWORDS and len(targets) == 1 and (targets[0][0], targets[0][2]) not in seen:
                visit(targets[0][1], targets[0][0], targets[0][2], depth + 1)

    visit(body, file, line, 0)
    return data
