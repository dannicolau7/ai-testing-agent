# Automated tests to keep: backend and frontend

`audit` and `agent` report on an application once. `automate` writes the tests that go on
checking it: a folder with no dependency on this tool, to commit beside the application and
run on every change.

```bash
python cli.py automate path/to/app --url http://localhost:8000 \
    --sign-in sign-in.yaml --journeys journeys.yaml -o automation/

AUTOMATION_BASE_URL=http://localhost:8000 pytest automation -rs
```

## What it writes

| Folder | One test for | It passes when |
|---|---|---|
| `api/` | each operation in the API spec | the status is one the spec documents, and a success carries the fields the spec requires |
| `api/` | each operation that needs sign-in | a caller with no sign-in is refused |
| `api/` | each operation with required fields | a body with none of them is turned down, not accepted and not a crash |
| `ui/test_pages.py` | each page the browser reached | it loads, throws no error, and none of its own requests fail |
| `ui/test_journeys.py` | each journey in the journeys file | the steps work in the page, the page sends the request it should, and the backend holds the result |

Plus `support.py` (sign-in and reading answers), `sign-in.yaml` if you gave one, a `README.md`
for the team, `requirements.txt`, and `ci-example.yml` for GitHub Actions.

## What each test is checked against

- **Backend tests are checked against the API spec**, which is what the team has said the API
  does. The spec comes from `--spec`, the source, or the running test environment.
- **With no spec, no backend test is written.** A test written from the code alone repeats the
  code's bugs and calls them correct. The suite's README says this in place of the tests.
- **Page tests** need no standard beyond "works": a page that throws or whose own request
  fails is broken whatever it was meant to do.
- **Journeys are written by a person.** Each is a requirement carried out in the page. The tool
  turns the file into tests; it does not invent the steps.

## The suite is data plus fixed code

`operations.json`, `pages.json` and `journeys.json` say what to check. The `.py` files read
them and never change. To add or drop a check, edit the JSON. After the application changes,
generate the folder again (`--force` writes over it).

## Rules the suite keeps

- A test that would change data is skipped unless `AUTOMATION_ALLOW_WRITES=1`. Journeys always
  count as changing data.
- A test that got no answer, has no sign-in, or met a row that does not exist is **skipped
  with the reason, never passed**. Run with `-rs` to read the reasons.
- Being turned away as the test user is a skip, not a failure: many specs leave 401 and 403
  out, and it usually means the operation needs another role.
- No password, cookie or token is written. `sign-in.yaml` names environment variables.
- The tool that writes the suite opens only this machine, or one named with
  `--authorization`.

## What it has been tried on

| Application | What was generated | Result on the unmodified application |
|---|---|---|
| FastAPI full-stack template (real, PostgreSQL) | 47 backend tests for 23 operations, from the spec the application serves | 23 pass, 23 skipped with reasons, 1 fails: `POST /api/v1/private/users/` answers 500 for an address that already exists, where its spec documents 200 and 422. That is a real fault in the application |
| Flask tutorial application (real, no API spec) | 7 page tests and 1 journey; no backend tests, as it has no spec | 8 pass. The journey writes a post through the page and finds it in the backend |
| The demo site with planted problems | page tests and 3 journeys | 4 fail, one for each planted problem; 4 pass |

In this project's own tests, an application that keeps to its spec passes every backend test,
and each of five ways of breaking the spec fails exactly the test for it.

## What it does not do

- It does not write journeys. A person does.
- It tests one signed-in user, the role called `user`. Operations that need another role are
  skipped; the permissions table (`agent --permissions`) is the tool for roles.
- It checks that required fields are present in a reply, not their types or values.
- It sends the smallest body the spec accepts. A body that satisfies the schema can still be
  turned down (a wrong current password, an address already in use); that is a skip.
- It does not clean up what a run creates. Use a test environment you can reset.
- Two real applications and a demo are not many. Expect to find things on a third.
