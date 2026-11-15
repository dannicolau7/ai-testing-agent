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
| Permissions (who may do what) | Detects a visible access check and a missing ownership check; no model of roles |
| Frontend | Reads `fetch` and `axios` calls from source; no browser |
| Re-checking on change | Missing |

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
model; a stronger model has not been tried. Next: Stage 6, the table of roles against
actions.

Go beyond route decorators: which handler reads and writes which data, which checks run
before it, what it returns on each path. Store this as a model the later stages query, so a
finding can say "this endpoint changes orders without checking ownership" and point to the
line.

### Stage 5: the database

Read the schema and the migrations. Check that what the requirements say must be unique,
required or linked is actually enforced, and that tests cover the constraints.

### Stage 6: permissions

Build the table of roles against actions from the requirements. Generate a test for every
cell, including the ones that must be refused. Missing refusals are the most common
serious finding in real products.

### Stage 7: the frontend

Drive the application in a browser. Check that each user-facing requirement can be carried
out, that the frontend and backend agree on what is allowed, and that a control hidden in
the interface is also refused by the server.

### Stage 8: every change

Run the audit on each pull request and report only what changed: new gaps, tests that no
longer validate, requirements that lost coverage.

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
