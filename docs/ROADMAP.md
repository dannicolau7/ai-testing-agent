# Roadmap: from test generator to product audit

## Where this is going

Today this tool generates API tests from requirements and OpenAPI specs.

The goal is an agent that audits a whole product. Given a repository, the product's
requirements, and a safe test environment, it should:

1. **Understand the product's behaviour** across the frontend, the backend, the database
   and the permission rules.
2. **Report what is wrong**: places where the code does not do what the requirements say.
3. **Report what could be better**: weak spots that are likely to cause problems later,
   such as an untested permission rule or a requirement nothing implements.
4. **Generate and run tests** for the gaps, and show that each test really checks something.
5. **Re-check on every change**, so a new problem is caught when it is introduced.

The standard is always the expectations for the finished product, never the code alone. A
test written only from the code repeats the code's bugs and calls them correct.

## The rule that comes before any feature

**Never report a result that was not measured.** A test counts as passed only if it ran and
passed. A placeholder is shown as skipped. A finding names the evidence behind it. An
audit tool that overstates what it checked is worse than no tool.

## Where it is today

| Capability | State |
| --- | --- |
| Requirements as input (text, Markdown, PDF, Word) | Works; they are passed to a model as a prompt |
| OpenAPI and Swagger specs | Works |
| Backend routes from source (FastAPI, Flask, Express) | Reads decorators and route definitions only |
| Do the layers agree (frontend, backend, API spec, database) | First version: `python cli.py audit` |
| Chains across endpoints (create → read → update → delete, login → profile) | Works |
| Running generated tests | Works as of this change; it used to be simulated |
| Link from a requirement to its tests | Works: `python cli.py trace` (not yet to the code) |
| Proof that a test can fail | Works for tests that call the system through `requests`: `python cli.py validate` |
| Database | Reads SQL and SQLAlchemy tables; checks keys only. Migrations not read |
| Permissions (who may do what) | A table of roles against routes, compared with the code; one generated test per cell |
| Frontend | Reads `fetch` and `axios` calls from source; `browse` opens the running app in a browser |
| Re-checking on change | First version: `audit --baseline` (findings only) |
| One run that does every stage and checks its own findings | First version: `python cli.py agent` |

## Build order

Each stage is useful on its own and makes the next one possible.

### Stage 1: honest results (done in this change)

- The pipeline runs the generated tests with pytest and reports real counts.
- Placeholder tests are skipped, never passed.
- Model calls work with current models.

### Stage 2: traceability (first version done)

Every requirement gets an id. Every generated test names the requirement it checks. The
report then shows three lists that matter more than a pass count:

- requirements with no test;
- tests that trace to no requirement;
- requirements the code does not appear to implement.

This is the cheapest step towards "report what is wrong", and it needs no new analysis.

Built: `python cli.py trace requirements.md tests/` reads requirement ids (REQ-12, US-7,
AC-2.1) and the ids each test points at, and lists requirements with no test, tests with
no requirement, and tests that point at a requirement that does not exist.

Generated tests now carry the ids too: a test case's `requirement_ids` become a
`# Requirement:` comment above each generated test. Ids are never guessed from other text.

Still to do: nothing links a requirement to the code that implements it, and the id
linking has not been run against a live model.

### Stage 3: proof that a test checks something (first version done)

For each generated test, change the behaviour it claims to check (for example, make the
endpoint return the wrong status) and confirm the test fails. A test that still passes is
reported as not validating anything. This is what turns generated tests into evidence.

Built: `python cli.py validate tests/` runs the tests normally, then again with every HTTP
response replaced by a wrong one, and sorts them: validated, not validating, made no
request, already failing.

Still to do: it covers only tests that use the `requests` library, and tries one kind of
wrong response. Changing the application itself (a real mutation) would be stronger.

### Stage 4: a behaviour model of the backend (first step done)

Built: `python cli.py audit <dir>` builds one model of the application from source (routes
with their visible access checks, frontend requests, spec operations, tables) and reports
where the layers disagree, sorted into wrong now, likely to go wrong, unclear and not
examined. See `app_audit.py` and `examples/audit-demo`.

Also built (`data_access.py`): for Python handlers the audit follows the handler, and the
project functions it calls, to the SQL statements and SQLAlchemy calls it makes. Each route
now knows which tables it reads and writes. From that it reports: a table or column the
database does not define; a row fetched by id with no sign that the caller owns it; SQL
built by inserting values into the text; a GET that changes data; tables no route touches.

Also built (`shapes.py`): request bodies, query parameters and responses, compared between
the frontend (object literals and TypeScript types), the spec and FastAPI handlers with
Pydantic models. A shape is compared only when the source states it; a body passed as an
untyped variable, a spread, or a handler that reads the raw request is left alone.

Also built (`requirements_audit.py`): `audit --requirements FILE` checks the code against
requirements. A requirement is linked to code only where the link is written (it names a
route, or a handler names it). Four things are checked from the wording: sign-in,
ownership, administrators only, uniqueness in the database. This is the first place the
audit judges against what the product should do, not only whether the layers agree.

Also built (`model_backend.py`, `requirement_links.py`): the model is now a choice. No model
(everything that reads source), a local model through any OpenAI-compatible server (free,
nothing leaves the machine), or the Anthropic API. `python cli.py link` asks the model
which route each requirement is about and writes its proposals to a file; only links a
person confirms are used by `audit --links`. Measured with Llama 3.2 (3B) on the demo's nine
plain-worded requirements: seven right, two wrong routes. Earlier prompt forms did worse
(free-form JSON invented checks; yes/no per route said yes to 13 wrong routes or no to
nearly everything), so the model is asked one multiple-choice question per requirement.

Tried on real code: the sample application, plus two of our own projects (a FastAPI + React
app and a FastAPI + Next.js app). That run removed three kinds of false alarm: `_id` columns
that are not references, SQL assembled from fixed pieces (now "unclear", not "likely"), and
a long list of routes the frontend reaches through a helper (now one finding). One known
false alarm remains: a route protected by global middleware is reported as showing no
access check.

Still to do: two small codebases are not enough to know the false-alarm rate. The ownership check looks for the owner column's name
anywhere in the handler's code, which is evidence, not proof. Queries assembled across
variables, query builders, Django, and JavaScript backends are not read. Shapes compare
field names only, not types, and not what the frontend reads from a response. The
requirements check matches wording with fixed patterns, so it covers four kinds of
statement and has not been tried on a real requirements document. Model-proposed links are measured on nine made-up requirements only, with one small
model; a stronger model has not been tried.

Go beyond route decorators: which handler reads and writes which data, which checks run
before it, what it returns on each path. Store this as a model the later stages query, so a
finding can say "this endpoint changes orders without checking ownership" and point to the
line.

### Stage 5: the database

Read the schema and the migrations. Check that what the requirements say must be unique,
required or linked is actually enforced, and that tests cover the constraints.

### Stage 6: permissions (first version done)

Built (`permissions.py`): a permissions table in a small YAML file (roles, and for each
route who is allowed and whether only the owner's rows). `permissions --init` drafts one
from the code as it is. `audit --permissions` compares the code with the table.
`permissions --tests` writes one test for every cell, refusals included; in this project's
own tests the generated tests are run against a small live application with a planted hole
and catch it.

Still to do: the table comes from a person, not yet from the requirements. The comparison
with code reads names (`require_admin`, `is_admin`), which is evidence, not proof; the
generated tests are the proof, and they have not been run against a real application. The
tests use one id for every path parameter, so "own rows only" is not yet tested with two
users' data.

Build the table of roles against actions from the requirements. Generate a test for every
cell, including the ones that must be refused. Missing refusals are the most common
serious finding in real products.

### Stage 7: the frontend (first version done)

Built (`browser_audit.py`): `python cli.py browse URL` opens the running application in a
real browser, follows same-site links, and reports pages that throw errors, API requests
answered 404, 405 or 5xx, and broken links. With `--source` it lists which backend routes
it saw being called. It never fills in forms and clicks buttons only on request, skipping
destructive-looking labels. `examples/browser-demo` is a small site with planted problems.

Also built (`journeys.py`): `python cli.py journey FILE --url URL` carries out a
requirement in the page from a short file of steps (open, fill, click, see), then checks
that the page sent the right request and that the backend holds the result afterwards. On
the demo site it catches a page that shows a rename the server never stored, and a page
that reports success after the server answered "not found".

Still to do: both have been run on the demo site only. `browse` does not sign in through a
login form. Journeys are written by a person, not generated from requirements; they are
not undone afterwards; and their backend check is "the response contains this text". It does not yet
check that a control hidden in the interface is also refused by the server; the generated
permission tests cover the server side of that.

Drive the application in a browser. Check that each user-facing requirement can be carried
out, that the frontend and backend agree on what is allowed, and that a control hidden in
the interface is also refused by the server.

### Stage 8: every change (first version done)

Built (`audit_diff.py`): `audit --save FILE` stores an audit's findings; `audit --baseline
FILE` reports only what changed since then (new, fixed, and a count of the rest) and fails
only for a new fault. `docs/audit-on-pull-requests.md` shows how to run it in GitHub
Actions.

Still to do: it compares audit findings only. Tests that no longer validate and
requirements that lost test coverage are not compared yet, and the workflow example has not
been run in a real repository.

Run the audit on each pull request and report only what changed: new gaps, tests that no
longer validate, requirements that lost coverage.

## The agent (first version built)

`python cli.py agent` (`agent.py`, `docs/agent.md`) runs the stages in order and uses what
each learned: it takes the findings a request can settle, writes and runs the tests against a
test environment, and sorts each finding as confirmed, cleared or not run. A model, if
configured, proposes requirement links, which never reach the verdict. Every step is
recorded, and what was not done is listed. It sends requests only to this machine, or to one
named with written authorization, and changes data only with `--allow-writes`.

Still to do: it has run only against a small application with planted faults. It settles
three kinds of finding. It has no memory between runs, so "fixed since last time" still needs
`--baseline`. It does not write journeys from requirements, which is the next place a model
could help, always for a person to confirm.

## From findings to proof (built)

`audit --tests-out FILE` (`finding_tests.py`) writes a test for each finding a request can
settle: the route exists, it refuses a caller who is not signed in, it refuses a user asking
for another user's row. A failing test proves the fault; a passing one clears a false alarm.
In this project's own tests the generated tests run against a small live application: three
real faults fail and one false alarm passes.

Still to do: only three kinds of finding can be tested this way. Missing columns, request
shapes and role rules need a request body or a second role, which the generator does not
build yet. The tests have not been run against a real application. Browser journeys exist (see
Stage 7) but are written by hand, not generated from findings.

## Trials on real code

`docs/real-code-trial.md` records three trials on applications we did not write: FastAPI,
Flask and Express. First runs were mostly false alarms (35 findings across the three, 33
false); after the fixes they report two, one true and one open by design. With fourteen
faults planted in copies of those applications the audit finds 12, or 13 with a permissions
table. Read it before believing any claim in this file about what the audit can do.

The trials run on every change: `python trials/planted_faults.py`, and the `real-code` job
in CI.

JavaScript and TypeScript backends are read as text (`js_data_access.py`): Prisma calls and
SQL strings. Query builders are not read.

## One report (built)

`python cli.py full-report` puts the results of `audit`, `browse`, `trace` and `validate`
into one document, Markdown or self-contained HTML. It lists each check as run or not run
with the reason, so a partial audit cannot be mistaken for a complete one.

Still to do: it has been produced for the sample application only. There is no PDF, no
signature and no record of the exact code version audited; Attestor's evidence pack has all
three, and the two should meet.

## What the audit report should contain

- **Wrong now:** the code contradicts a requirement. Each item cites the requirement, the
  code location and the failing test.
- **Likely to go wrong:** nothing contradicts a requirement yet, but nothing would catch it
  if it did. Each item says what is unprotected and what test would protect it.
- **Unclear:** the requirement is missing, vague or contradicts another. These go to a
  person; the tool does not guess.
- **What was not examined**, stated plainly.

## Things to decide before Stage 4

- **Which stacks first.** Each language and framework is its own work. Pick one backend and
  one frontend stack and do them well.
- **Where requirements come from.** Files in the repository are simple. Tickets in Jira or
  a similar system need an integration and permission to read them.
- **Safety of the test environment.** The agent creates and deletes data. It must only ever
  run against an environment made for that, never production.
- **How this relates to the other tools.** Verdict already answers "did this change make it
  worse" for AI agents; Stage 8 should reuse its approach, not rebuild it.

## Known issues, not part of the roadmap

- The code is a set of loose modules in the repository root, which makes packaging hard.
- `examples/*/expected_output` contains tests that error when collected by pytest.
- The cost printed per model call uses fixed prices that may not match the model in use.
