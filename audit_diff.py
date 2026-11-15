"""
audit_diff.py — what changed between two audits.

Stage 8 of docs/ROADMAP.md, first version. An audit of a real application has findings
people already know about. On a pull request the useful question is narrower: did this
change add a problem, or fix one?

    python cli.py audit app/ --save baseline.json          # on the main branch
    python cli.py audit app/ --baseline baseline.json      # on the pull request

A finding is the same finding when its group, its title and its file are the same. The line
number is left out, so code moving up or down a file does not make an old finding look new.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

FORMAT = 1
_GROUP_NAMES = {"wrong_now": "Wrong now", "likely": "Likely to go wrong", "unclear": "Unclear"}
_ORDER = {"wrong_now": 0, "likely": 1, "unclear": 2}


def _key(finding: dict) -> Tuple[str, str, str]:
    return finding["group"], finding["title"], re.sub(r":\d+$", "", finding.get("where", ""))


def to_json(report) -> str:
    """The findings of an audit, in a form a later audit can be compared with."""
    return json.dumps({
        "format": FORMAT,
        "findings": [{"group": f.group, "title": f.title, "detail": f.detail, "where": f.where}
                     for f in report.findings],
    }, indent=2) + "\n"


class BaselineError(ValueError):
    """The baseline file cannot be used."""


def load(text: str) -> List[dict]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise BaselineError("the baseline is not valid JSON") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("findings"), list):
        raise BaselineError("the baseline was not written by `audit --save`, or by a different version")
    findings = []
    for item in data["findings"]:
        if not (isinstance(item, dict) and isinstance(item.get("group"), str) and isinstance(item.get("title"), str)):
            raise BaselineError("the baseline has a finding with no group or title")
        findings.append({"group": item["group"], "title": item["title"],
                         "detail": str(item.get("detail", "")), "where": str(item.get("where", ""))})
    return findings


@dataclass
class Change:
    new: List[dict] = field(default_factory=list)
    fixed: List[dict] = field(default_factory=list)
    unchanged: Dict[str, int] = field(default_factory=dict)   # group → count

    @property
    def ok(self) -> bool:
        """A change passes unless it adds something that is wrong now."""
        return not [f for f in self.new if f["group"] == "wrong_now"]


def compare(report, baseline: List[dict]) -> Change:
    current = [{"group": f.group, "title": f.title, "detail": f.detail, "where": f.where} for f in report.findings]
    before, change = Counter(_key(f) for f in baseline), Change()
    unchanged: Counter = Counter()
    for finding in current:
        key = _key(finding)
        if before[key] > 0:
            before[key] -= 1          # the same finding twice in a file counts twice
            unchanged[finding["group"]] += 1
        else:
            change.new.append(finding)
    remaining = Counter(before)
    for finding in baseline:
        key = _key(finding)
        if remaining[key] > 0:
            remaining[key] -= 1
            change.fixed.append(finding)
    change.new.sort(key=lambda f: _ORDER.get(f["group"], 3))
    change.fixed.sort(key=lambda f: _ORDER.get(f["group"], 3))
    change.unchanged = dict(unchanged)
    return change


def render_markdown(change: Change) -> str:
    """A short report for a pull request: the verdict first, then what is new, then what was fixed."""
    new_wrong = [f for f in change.new if f["group"] == "wrong_now"]
    if new_wrong:
        verdict = f"**This change adds {len(new_wrong)} problem(s) that are wrong now.**"
    elif change.new:
        verdict = f"**No new faults.** This change adds {len(change.new)} thing(s) to look at."
    elif change.fixed:
        verdict = f"**No new findings.** This change fixes {len(change.fixed)}."
    else:
        verdict = "**No change in the audit's findings.**"
    lines = ["# Application audit: what this change does", "", verdict, ""]
    if change.new:
        lines += [f"## New ({len(change.new)})", ""]
        for f in change.new:
            lines += [f"- **{f['title']}**", f"  {_GROUP_NAMES.get(f['group'], f['group'])}. {f['detail']} `{f['where']}`"]
        lines.append("")
    if change.fixed:
        lines += [f"## Fixed ({len(change.fixed)})", ""]
        lines += [f"- {f['title']}" for f in change.fixed]
        lines.append("")
    total = sum(change.unchanged.values())
    if total:
        parts = [f"{change.unchanged[g]} {_GROUP_NAMES[g].lower()}" for g in _ORDER if change.unchanged.get(g)]
        lines += [f"Already there before this change, and still there: {total} ({', '.join(parts)}).", ""]
    lines += ["The audit reads source and compares its layers. It does not run the application.", ""]
    return "\n".join(lines).rstrip() + "\n"
