"""
traceability.py — which requirement does each test check?

Stage 2 of docs/ROADMAP.md. No AI involved: it reads a requirements document and a set of
test files and reports how they line up.

A requirement is a line that carries an id such as REQ-12, FR-3, US-7 or AC-2.1. A test
points at a requirement in any of these ways:

    @pytest.mark.requirement("REQ-12")
    def test_x(): ...

    def test_y():
        \"\"\"Covers: REQ-12, REQ-13\"\"\"

    # Requirement: REQ-12
    def test_z(): ...

The report lists what matters more than a pass count:

- requirements with no test;
- tests that point at no requirement;
- tests that point at a requirement that does not exist (a typo, or a deleted requirement).

Public API:

    reqs   = extract_requirements(text)
    tests  = scan_tests(["tests/"])
    report = build_report(reqs, tests)
    print(render_markdown(report))
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

# REQ-12, FR-3, NFR-10, US-7, AC-2.1, BR-4, SEC-9 ...
ID_PATTERN = re.compile(r"\b([A-Z]{2,5}-\d+(?:\.\d+)*)\b")
_REFERENCE_LINE = re.compile(r"(?:requirements?|covers|verifies|traces? to)\s*:\s*(.+)", re.IGNORECASE)


@dataclass
class Requirement:
    id: str
    text: str
    line: int


@dataclass
class TestRef:
    file: str
    name: str
    line: int
    requirements: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.file}::{self.name}"


@dataclass
class TraceReport:
    requirements: List[Requirement]
    tests: List[TestRef]
    covered: Dict[str, List[str]]  # requirement id -> test labels
    uncovered: List[Requirement]
    untraced_tests: List[TestRef]
    unknown_references: Dict[str, List[str]]  # id that is not a requirement -> test labels

    @property
    def coverage(self) -> float:
        total = len(self.requirements)
        return (total - len(self.uncovered)) / total if total else 0.0

    @property
    def ok(self) -> bool:
        return not (self.uncovered or self.untraced_tests or self.unknown_references)


def extract_requirements(text: str) -> List[Requirement]:
    """Every line that starts a requirement: the first id on the line names it."""
    found: Dict[str, Requirement] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().lstrip("-*#>| ").strip()
        match = ID_PATTERN.search(line)
        # The id has to lead the line (after list or heading marks), so a sentence that
        # merely mentions "see REQ-3" does not define a second REQ-3.
        if not match or match.start() > 2:
            continue
        req_id = match.group(1)
        body = line[match.end():].lstrip(" :.-–—|").rstrip(" |").strip()
        if req_id not in found:
            found[req_id] = Requirement(id=req_id, text=body, line=number)
    return list(found.values())


def _ids_in(text: str) -> List[str]:
    ids: List[str] = []
    for line in text.splitlines():
        match = _REFERENCE_LINE.search(line)
        if match:
            ids += ID_PATTERN.findall(match.group(1))
    return ids


def _marker_ids(node: ast.AST) -> List[str]:
    ids: List[str] = []
    for decorator in getattr(node, "decorator_list", []):
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if isinstance(target, ast.Attribute) and target.attr in ("requirement", "requirements", "req"):
            for arg in decorator.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    ids += ID_PATTERN.findall(arg.value)
    return ids


def scan_test_source(source: str, filename: str) -> List[TestRef]:
    """Tests in one file, with the requirement ids each one points at."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    tests: List[TestRef] = []

    def visit(node: ast.AST, prefix: str, inherited: List[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef) and child.name.startswith("Test"):
                class_ids = _marker_ids(child) + _ids_in(ast.get_docstring(child) or "")
                visit(child, f"{child.name}::", inherited + class_ids)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"):
                ids = list(inherited) + _marker_ids(child) + _ids_in(ast.get_docstring(child) or "")
                # Comment lines directly above the test (and above its decorators).
                first = min([child.lineno] + [d.lineno for d in child.decorator_list])
                index = first - 2
                while index >= 0 and lines[index].strip().startswith("#"):
                    ids += _ids_in(lines[index].strip().lstrip("# "))
                    index -= 1
                unique = list(dict.fromkeys(ids))
                tests.append(TestRef(filename, prefix + child.name, child.lineno, unique))

    visit(tree, "", [])
    return tests


def scan_tests(paths: Sequence[str]) -> List[TestRef]:
    """Scan test files (test_*.py or *_test.py) under the given files and directories."""
    files: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files += sorted(p for p in path.rglob("*.py") if p.name.startswith("test_") or p.name.endswith("_test.py"))
        elif path.is_file():
            files.append(path)
    tests: List[TestRef] = []
    for file in files:
        try:
            source = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        tests += scan_test_source(source, str(file))
    return tests


def build_report(requirements: List[Requirement], tests: List[TestRef]) -> TraceReport:
    known = {r.id for r in requirements}
    covered: Dict[str, List[str]] = {}
    unknown: Dict[str, List[str]] = {}
    for test in tests:
        for req_id in test.requirements:
            (covered if req_id in known else unknown).setdefault(req_id, []).append(test.label)
    return TraceReport(
        requirements=requirements,
        tests=tests,
        covered=covered,
        uncovered=[r for r in requirements if r.id not in covered],
        untraced_tests=[t for t in tests if not t.requirements],
        unknown_references=unknown,
    )


def render_markdown(report: TraceReport) -> str:
    total = len(report.requirements)
    lines = [
        "# Requirement traceability",
        "",
        f"- Requirements: {total}",
        f"- Requirements with at least one test: {total - len(report.uncovered)} ({report.coverage:.0%})",
        f"- Tests: {len(report.tests)}",
        f"- Tests that point at no requirement: {len(report.untraced_tests)}",
        "",
        "A requirement with a test is not proof the requirement is met: the test may check",
        "too little. `validate` shows whether a test can fail at all.",
        "",
    ]
    if report.uncovered:
        lines += ["## Requirements with no test", ""]
        lines += [f"- **{r.id}** {r.text}" for r in report.uncovered]
        lines.append("")
    if report.unknown_references:
        lines += ["## Tests that point at a requirement that does not exist", ""]
        for req_id, labels in sorted(report.unknown_references.items()):
            lines.append(f"- **{req_id}**: " + ", ".join(f"`{label}`" for label in labels))
        lines.append("")
    if report.untraced_tests:
        lines += ["## Tests that point at no requirement", ""]
        lines += [f"- `{t.label}`" for t in report.untraced_tests]
        lines.append("")
    if report.covered:
        lines += ["## Covered requirements", "", "| Requirement | Tests |", "|---|---|"]
        for r in report.requirements:
            if r.id in report.covered:
                lines.append(f"| {r.id} | {len(report.covered[r.id])} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def requirement_ids_of(test_case: dict) -> List[str]:
    """Requirement ids a generated test case names, in order, without duplicates.

    Only the `requirement_ids` field is read. Ids are never guessed from other text: a wrong
    link is worse than a missing one, because it hides a gap.
    """
    raw = test_case.get("requirement_ids") if isinstance(test_case, dict) else None
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    ids: List[str] = []
    for item in raw:
        if isinstance(item, str):
            ids += ID_PATTERN.findall(item)
    return list(dict.fromkeys(ids))


def tag_with_requirements(source: str, requirement_ids: Sequence[str]) -> str:
    """Put a `# Requirement: ...` comment above every test function in generated code.

    Tests that already point at a requirement are left alone. Code that cannot be parsed is
    returned unchanged.
    """
    if not requirement_ids:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    already = {t.line for t in scan_test_source(source, "generated") if t.requirements}
    lines = source.splitlines()
    comment = "# Requirement: " + ", ".join(requirement_ids)
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            if node.lineno not in already:
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                targets.append(first)
    for line_number in sorted(set(targets), reverse=True):
        text = lines[line_number - 1]
        indent = text[: len(text) - len(text.lstrip())]
        lines.insert(line_number - 1, indent + comment)
    return "\n".join(lines) + ("\n" if source.endswith("\n") else "")
