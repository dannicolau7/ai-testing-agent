#!/usr/bin/env python3
"""
The live trial: the agent against a real application that is actually running.

`planted_faults.py` reads source only. This one starts the Flask project's own tutorial
application (at the same pinned commit), signs a user in the way a browser would, and runs
the agent against it twice:

- as it is: every cell of the permissions table that is tried must hold, and nothing may
  be reported wrong;
- with sign-in and the author check removed from the delete route: the agent must confirm
  exactly that hole, by a request, and list it once;
- with only the sign-in decorator removed: the route crashes for a visitor, and the agent
  must report "not run", not a fault.

The first time this was run by hand the unmodified application showed five "broken" cells,
all false. docs/real-code-trial.md says why. This script keeps them from coming back.

    pip install flask
    python trials/live_flask.py            # clones into trials/.apps on first use

It needs Flask installed and a free port. It runs the application on this machine only, in a
temporary folder, and deletes it afterwards.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import agent  # noqa: E402
import permissions  # noqa: E402
import planted_faults  # noqa: E402

# Two edits, because one is not a working hole: with only the decorator gone, the route's own
# author check crashes for a visitor who is not signed in, the server answers 500, and the
# agent rightly reports that as "not run", not as a fault. Removing the check as well makes
# the delete really happen.
PLANTS = [
    ('@bp.route("/<int:id>/delete", methods=("POST",))\n@login_required\n',
     '@bp.route("/<int:id>/delete", methods=("POST",))\n'),
    ('    get_post(id)\n    db = get_db()\n    db.execute("DELETE FROM post WHERE id = ?", (id,))',
     '    db = get_db()\n    db.execute("DELETE FROM post WHERE id = ?", (id,))'),
]
TABLE = """roles: [anonymous, user]
rules:
  - {route: GET /auth/login, allow: [anonymous, user]}
  - {route: GET /create, allow: [user]}
  - {route: POST /create, allow: [user]}
  - {route: 'GET /<int:id>/update', allow: [user]}
  - {route: 'POST /<int:id>/delete', allow: [user]}
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Running:
    """The tutorial application, started from a folder, with one signed-in user and three posts."""

    def __init__(self, folder: Path):
        self.folder, self.port = folder, _free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.cookie = ""

    def __enter__(self) -> "Running":
        import requests

        flask = [sys.executable, "-m", "flask", "--app", "flaskr"]
        subprocess.run(flask + ["init-db"], cwd=self.folder, check=True, capture_output=True)
        self.process = subprocess.Popen(flask + ["run", "--port", str(self.port)], cwd=self.folder,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                requests.get(self.url + "/auth/login", timeout=2)
                break
            except requests.exceptions.RequestException:
                time.sleep(0.2)
        else:
            raise SystemExit("the tutorial application did not start")
        session = requests.Session()
        who = {"username": "trial-user", "password": "trial-password"}
        session.post(self.url + "/auth/register", data=who, timeout=10)
        session.post(self.url + "/auth/login", data=who, timeout=10)
        for n in (1, 2, 3):
            session.post(self.url + "/create", data={"title": f"Post {n}", "body": "x"}, timeout=10)
        self.cookie = "session=" + session.cookies.get("session", "")
        return self

    def __exit__(self, *exc) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _run(folder: Path, app: Running, path_id: str):
    os.environ["ROLE_USER_COOKIE"] = app.cookie
    os.environ["FINDINGS_PATH_ID"] = path_id
    try:
        cfg = agent.Config(path=str(folder), policy=permissions.load(TABLE), url=app.url, browse=False,
                           allow_writes=True)
        return agent.run(cfg)
    finally:
        os.environ.pop("ROLE_USER_COOKIE", None)
        os.environ.pop("FINDINGS_PATH_ID", None)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apps-dir", default=str(HERE / ".apps"))
    args = parser.parse_args(argv)
    try:
        import flask  # noqa: F401
    except ImportError:
        print("Flask is not installed, so the live trial was NOT run. pip install flask")
        return 2
    source = planted_faults.checkout("flask", Path(args.apps_dir))
    problems = []
    with tempfile.TemporaryDirectory() as scratch:
        clean, faulty = Path(scratch) / "clean", Path(scratch) / "faulty"
        for target in (clean, faulty):
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "instance"))
        blog = faulty / "flaskr" / "blog.py"
        text = blog.read_text(encoding="utf-8")
        for before, after in PLANTS:
            if before not in text:
                print("BROKEN  the text to replace is not in flaskr/blog.py")
                return 1
            text = text.replace(before, after, 1)
        half = Path(scratch) / "half"
        shutil.copytree(clean, half)
        original = (clean / "flaskr" / "blog.py").read_text(encoding="utf-8")
        (half / "flaskr" / "blog.py").write_text(original.replace(*PLANTS[0], 1), encoding="utf-8")
        blog.write_text(text, encoding="utf-8")

        print("The application as it is")
        with Running(clean) as app:
            run = _run(clean, app, "1")
        tally = {v: len([c for c in run.cells if c.verdict == v]) for v in ("holds", "broken", "not run")}
        wrong = [i.title for i in run.report.items if i.group == "wrong_now"]
        ok = tally == {"holds": 10, "broken": 0, "not run": 0} and not wrong
        print(f"  {'ok      ' if ok else 'CHANGED '}{tally['holds']} cells hold, {tally['broken']} broken, "
              f"{tally['not run']} not run; {len(wrong)} reported wrong")
        if not ok:
            problems.append(f"unmodified application: {tally}, wrong: {wrong}, "
                            f"cells: {[(c.role, c.method, c.path, c.verdict, c.evidence) for c in run.cells if c.verdict != 'holds']}")

        print("\nWith sign-in and the author check removed from the delete route")
        with Running(faulty) as app:
            run = _run(faulty, app, "2")
        wrong = [i for i in run.report.items if i.group == "wrong_now"]
        broken = [(c.role, c.method, c.path) for c in run.cells if c.verdict == "broken"]
        confirmed = [c for c in run.confirmations if c.verdict == "confirmed"]
        ok = (len(wrong) == 1 and "delete" in wrong[0].title and "Confirmed by a request" in wrong[0].detail
              and broken == [("anonymous", "POST", "/<int:id>/delete")] and len(confirmed) == 1)
        print(f"  {'ok      ' if ok else 'CHANGED '}{len(confirmed)} finding confirmed by a request, "
              f"{len(broken)} broken cell, listed {len(wrong)} time(s)")
        if not ok:
            problems.append(f"planted fault: wrong={[i.title for i in wrong]}, broken={broken}")

        print("\nWith only the decorator removed (the route then crashes for a visitor)")
        with Running(half) as app:
            run = _run(half, app, "2")
        wrong = [i for i in run.report.items if "Confirmed by a request" in i.detail]
        crashed = [c for c in run.cells if c.verdict == "not run" and "500" in c.evidence]
        ok = not wrong and len(crashed) == 1 and not [c for c in run.cells if c.verdict == "broken"]
        print(f"  {'ok      ' if ok else 'CHANGED '}{len(wrong)} confirmed, {len(crashed)} cell not run because the "
              "server failed")
        if not ok:
            problems.append(f"half-planted fault: confirmed={[i.title for i in wrong]}, "
                            f"cells={[(c.role, c.path, c.verdict, c.evidence) for c in run.cells if c.verdict != 'holds']}")

    if problems:
        print("\nThe live trial does not match the written record:")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("\nThe live trial matches the written record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
