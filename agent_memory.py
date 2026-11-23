"""
agent_memory.py — what the agent found last time, so this run can say what changed.

Without it every run starts from nothing: the report cannot tell a fault that has been there
for a month from one that appeared today, or notice that a fault fixed last week is back.

The memory is one JSON file you choose (`agent --memory FILE`), meant to be kept with the
application, in its repository or its CI cache. Each run adds a short record: the date, the
application's commit if it has one, and the state of every finding, permission cell and
journey. Nothing else: no source, no request bodies, no cookie or token, no finding detail.

From the last record and this run the agent reports:

    fixed            wrong last time, not wrong now
    new              wrong now, not wrong last time
    back again       wrong now, fine last time, and wrong in an earlier run: a fix that came undone
    still wrong      wrong both times, with the date it was first seen
    stopped running  checked last time, not run this time: the check was lost, not passed

"Stopped running" matters as much as the others. A check that quietly stops running looks,
in a pass count, exactly like a check that passes.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

FORMAT = "ata-agent-memory/1"
KEEP = 50
WRONG, FINE, NOT_RUN = "wrong", "fine", "not run"


@dataclass
class Changes:
    since: str = ""                      # date of the run compared with
    commit_then: str = ""
    fixed: List[str] = field(default_factory=list)
    new: List[str] = field(default_factory=list)
    back_again: List[str] = field(default_factory=list)
    still_wrong: List[Tuple[str, str]] = field(default_factory=list)      # (what, first seen)
    stopped_running: List[str] = field(default_factory=list)
    runs_remembered: int = 0


class MemoryError_(ValueError):
    """The memory file cannot be used. The message says why."""


def _commit(path: str) -> str:
    try:
        done = subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _where(where: str) -> str:
    return re.sub(r":\d+$", "", where or "")


def snapshot(run, app_path: str, today: Optional[datetime.date] = None) -> dict:
    """This run as a record: one state per thing checked. Names and states only."""
    states: Dict[str, str] = {}
    for item in run.report.items:
        if item.source == "Permissions test":
            continue                                       # recorded below, once, as a cell
        key = f"finding: {item.title} [{_where(item.where)}]"
        if item.group == "wrong_now":
            states[key] = WRONG
        else:
            states.setdefault(key, item.group)             # likely | unclear: open, not proven wrong
    for finding in run.cleared:
        states[f"finding: {finding.title} [{_where(finding.where)}]"] = FINE
    for c in run.confirmations:
        key = f"test: {c.check} {c.method} {c.path}"
        states[key] = {"confirmed": WRONG, "cleared": FINE}.get(c.verdict, NOT_RUN)
    for cell in run.cells:
        key = f"cell: {cell.role} {'may' if cell.allowed else 'may not'} {cell.method} {cell.path}"
        states[key] = {"holds": FINE, "broken": WRONG}.get(cell.verdict, NOT_RUN)
    return {
        "date": (today or datetime.date.today()).isoformat(),
        "commit": _commit(app_path),
        "ok": bool(run.ok),
        "states": dict(sorted(states.items())),
    }


def load(path: Path) -> List[dict]:
    """The remembered runs, oldest first. A missing file is an empty memory, not an error."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MemoryError_(f"the memory file {path} cannot be read: {str(exc)[:100]}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("runs"), list):
        raise MemoryError_(f"{path} is not an agent memory file. Choose another file, or delete this one")
    return [r for r in data["runs"] if isinstance(r, dict) and isinstance(r.get("states"), dict)]


def save(path: Path, runs: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"format": FORMAT, "runs": runs[-KEEP:]}, indent=1, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def _label(key: str) -> str:
    return key.split(": ", 1)[1] if ": " in key else key


def compare(now: dict, runs: List[dict]) -> Optional[Changes]:
    """What changed between the last remembered run and this one. None when nothing is remembered."""
    if not runs:
        return None
    last = runs[-1]
    changes = Changes(since=str(last.get("date", "")), commit_then=str(last.get("commit", "")),
                      runs_remembered=len(runs))
    before, current = last["states"], now["states"]
    for key, state in current.items():
        was = before.get(key)
        if state == WRONG:
            if was == WRONG:
                first = next((str(r.get("date", "")) for r in runs if r["states"].get(key) == WRONG), changes.since)
                changes.still_wrong.append((_label(key), first))
            elif any(r["states"].get(key) == WRONG for r in runs[:-1]):
                changes.back_again.append(_label(key))
            else:
                changes.new.append(_label(key))
        elif state == NOT_RUN and was in (WRONG, FINE):
            changes.stopped_running.append(f"{_label(key)} (was {was})")
    for key, was in before.items():
        if was == WRONG and current.get(key) != WRONG and current.get(key) != NOT_RUN:
            changes.fixed.append(_label(key))
        elif key not in current and was in (FINE,) and key.startswith(("test: ", "cell: ")):
            changes.stopped_running.append(f"{_label(key)} (was {was}, no longer checked)")
    return changes


def render(changes: Optional[Changes]) -> List[str]:
    """Markdown lines for the report."""
    if changes is None:
        return ["## Since the last run", "",
                "This is the first run remembered in this memory file, so there is nothing to compare with yet.", ""]
    then = changes.since + (f", commit {changes.commit_then}" if changes.commit_then else "")
    lines = [f"## Since the last run ({then})", "",
             "| | Count |", "|---|---|",
             f"| Fixed | {len(changes.fixed)} |",
             f"| New | {len(changes.new)} |",
             f"| Back again | {len(changes.back_again)} |",
             f"| Still wrong | {len(changes.still_wrong)} |",
             f"| Stopped running | {len(changes.stopped_running)} |", ""]
    sections = [
        ("Back again", "Wrong now, fine last time, and wrong in an earlier run. A fix came undone.", changes.back_again),
        ("New", "Wrong now and not wrong last time.", changes.new),
        ("Stopped running", "Checked last time and not run this time. These were not passed; they were lost.",
         changes.stopped_running),
        ("Fixed", "Wrong last time and not wrong now.", changes.fixed),
    ]
    for title, meaning, items in sections:
        if items:
            lines += [f"**{title}.** {meaning}", ""] + [f"- {item}" for item in items] + [""]
    if changes.still_wrong:
        lines += ["**Still wrong.**", ""]
        lines += [f"- {what} (first seen {first})" for what, first in changes.still_wrong] + [""]
    lines += [f"{changes.runs_remembered} earlier run(s) are remembered. The memory holds names and states only: "
              "no source, no request, no sign-in.", ""]
    return lines
