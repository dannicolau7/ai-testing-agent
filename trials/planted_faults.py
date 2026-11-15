#!/usr/bin/env python3
"""
The real-code trial, as a repeatable check.

Three open-source applications, each pinned to one commit, are audited as they are and then
with one realistic fault planted at a time. The script fails when any result differs from
what is written down here:

- a new finding on an unmodified application (a false alarm has appeared, or a real change);
- a planted fault that used to be found and is now missed (the audit got worse);
- a planted fault that used to be missed and is now found (the audit got better: update
  EXPECTED_MISSES and docs/real-code-trial.md, so the record stays true).

    python trials/planted_faults.py                  # clones into trials/.apps on first use
    python trials/planted_faults.py --apps-dir DIR   # use or create checkouts in DIR

It reads source only. Nothing from the three applications is run, and none of their code is
kept in this repository: they are fetched from GitHub at the pinned commits.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import app_audit  # noqa: E402

APPS = {
    "fastapi": {
        "repo": "https://github.com/fastapi/full-stack-fastapi-template",
        "commit": "aabb90126964a164e02aff39e7c385bb0598236d",
        "subdir": "",
        "expected": ["likely: POST /api/v1/private/users/ changes data and shows no access check"],
    },
    "flask": {
        "repo": "https://github.com/pallets/flask",
        "commit": "49943b5a94413a530761350f04e896f76e8d620e",
        "subdir": "examples/tutorial",
        "expected": [],
    },
    "express": {
        "repo": "https://github.com/gothinkster/node-express-realworld-example-app",
        "commit": "30b68e1e881462b2f4164ea09ab4c4f5699c7b0b",
        "subdir": "",
        "expected": ["likely: POST /users changes data and shows no access check"],
    },
}

# (name, application, file, text to replace, replacement, a phrase a NEW finding must contain)
PLANTS = [
    ("FastAPI: superuser check removed from delete user", "fastapi", "backend/app/api/routes/users.py",
     '@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])',
     '@router.delete("/{user_id}")', "users/{user_id}"),
    ("FastAPI: sign-in removed from create item", "fastapi", "backend/app/api/routes/items.py",
     "    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate\n",
     "    *, session: SessionDep, item_in: ItemCreate\n",
     "POST /api/v1/items/ changes data and shows no access check"),
    ("FastAPI: owner check removed from read item", "fastapi", "backend/app/api/routes/items.py",
     "    if not current_user.is_superuser and (item.owner_id != current_user.id):\n"
     '        raise HTTPException(status_code=403, detail="Not enough permissions")\n    return item\n',
     "    return item\n", "without checking who owns"),
    ("FastAPI: frontend calls a route that was renamed", "fastapi", "frontend/src/client/sdk.gen.ts",
     "url: '/api/v1/items/',", "url: '/api/v1/things/',", "which no backend route defines"),
    ("FastAPI: backend route removed that the frontend calls", "fastapi", "backend/app/api/routes/utils.py",
     '@router.get("/health-check/")', '@router.get("/healthz/")', "which no backend route defines"),
    ("FastAPI: foreign key dropped from item.owner_id", "fastapi", "backend/app/models.py",
     'foreign_key="user.id", nullable=False, ondelete="CASCADE"', "nullable=False", "owner_id looks like a reference"),
    ("Flask: login_required removed from delete", "flask", "flaskr/blog.py",
     '@bp.route("/<int:id>/delete", methods=("POST",))\n@login_required\n',
     '@bp.route("/<int:id>/delete", methods=("POST",))\n', "delete changes data and shows no access check"),
    ("Flask: author check removed", "flask", "flaskr/blog.py",
     '    if check_author and post["author_id"] != g.user["id"]:\n        abort(403)\n', "", "without checking who owns"),
    ("Flask: query uses a column that does not exist", "flask", "flaskr/blog.py",
     '"UPDATE post SET title = ?, body = ? WHERE id = ?"', '"UPDATE post SET title = ?, content = ? WHERE id = ?"',
     "post.content"),
    ("Flask: query uses a table that does not exist", "flask", "flaskr/auth.py",
     '"INSERT INTO user (username, password) VALUES (?, ?)"', '"INSERT INTO users (username, password) VALUES (?, ?)"',
     "table `users`"),
    ("Flask: SQL built from a request value", "flask", "flaskr/blog.py",
     '        " ORDER BY created DESC"\n    ).fetchall()', '        f" ORDER BY {order}"\n    ).fetchall()', "SQL on"),
    ("Express: auth removed from delete article", "express", "src/app/routes/article/article.controller.ts",
     "router.delete(\n  '/articles/:slug',\n  auth.required,", "router.delete(\n  '/articles/:slug',",
     "DELETE /articles/:slug changes data"),
    ("Express: auth made optional on update article", "express", "src/app/routes/article/article.controller.ts",
     "router.put(\n  '/articles/:slug',\n  auth.required,", "router.put(\n  '/articles/:slug',\n  auth.optional,",
     "PUT /articles/:slug changes data"),
    ("Express: owner check removed from delete article", "express", "src/app/routes/article/article.service.ts",
     "existingArticle.author.id !== id", "false", "who owns"),
]

# Planted faults the audit is known to miss. docs/real-code-trial.md explains each.
EXPECTED_MISSES = {
    "FastAPI: superuser check removed from delete user",   # found only with a permissions table
    "FastAPI: foreign key dropped from item.owner_id",
}


def checkout(name: str, apps_dir: Path) -> Path:
    """The application's source at its pinned commit, fetched once."""
    app = APPS[name]
    target = apps_dir / name
    if not (target / ".git").is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for command in (["git", "init", "-q"], ["git", "remote", "add", "origin", app["repo"]],
                        ["git", "fetch", "-q", "--depth", "1", "origin", app["commit"]],
                        ["git", "checkout", "-q", "FETCH_HEAD"]):
            subprocess.run(command, cwd=target, check=True, env={"GIT_LFS_SKIP_SMUDGE": "1", "PATH": _path()})
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target, capture_output=True, text=True, check=True).stdout.strip()
    if head != app["commit"]:
        raise SystemExit(f"{target} is at {head[:10]}, not the pinned {app['commit'][:10]}. Delete it and run again.")
    return target / app["subdir"] if app["subdir"] else target


def _path() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin")


def findings(root: Path) -> list:
    return [f"{f.group}: {f.title}" for f in app_audit.audit(app_audit.build_model(str(root))).findings]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apps-dir", default=str(HERE / ".apps"), help="where the three applications are checked out")
    args = parser.parse_args(argv)
    apps_dir = Path(args.apps_dir)
    roots = {name: checkout(name, apps_dir) for name in APPS}
    problems = []

    print("Unmodified applications")
    for name, root in roots.items():
        got, want = findings(root), APPS[name]["expected"]
        ok = got == want
        print(f"  {'ok      ' if ok else 'CHANGED '}{name}: {len(got)} finding(s)")
        if not ok:
            extra = [g for g in got if g not in want]
            gone = [w for w in want if w not in got]
            problems.append(f"{name}: findings changed. New: {extra or 'none'}. No longer reported: {gone or 'none'}.")

    print("\nPlanted faults")
    found = 0
    with tempfile.TemporaryDirectory(dir=str(apps_dir)) as scratch:
        for index, (title, name, file, old, new, phrase) in enumerate(PLANTS):
            copy = Path(scratch) / str(index)
            shutil.copytree(roots[name], copy, symlinks=True, ignore=shutil.ignore_patterns(".git", "node_modules"))
            target = copy / file
            text = target.read_text(encoding="utf-8")
            if old not in text:
                problems.append(f"{title}: the text to replace is not in {file}")
                print(f"  BROKEN  {title}")
                continue
            before = findings(copy)
            target.write_text(text.replace(old, new, 1), encoding="utf-8")
            hit = any(phrase in t for t in findings(copy) if t not in before)
            expected_hit = title not in EXPECTED_MISSES
            found += hit
            state = "found " if hit else "missed"
            flag = "ok      " if hit == expected_hit else "CHANGED "
            print(f"  {flag}{state}  {title}")
            if hit and not expected_hit:
                problems.append(f"{title}: now FOUND. Good news: remove it from EXPECTED_MISSES and update "
                                "docs/real-code-trial.md.")
            elif not hit and expected_hit:
                problems.append(f"{title}: now MISSED. The audit got worse.")
            shutil.rmtree(copy, ignore_errors=True)

    print(f"\n{found} of {len(PLANTS)} planted faults found ({len(PLANTS) - len(EXPECTED_MISSES)} expected).")
    if problems:
        print("\nDifferent from the written record:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Everything matches the written record.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
