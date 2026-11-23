# AI Testing Agent

Autonomous pytest generation from requirements documents and OpenAPI specs.

[![Tests](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## What it does

Feed it a requirements document (txt, md, PDF, docx) or an OpenAPI/Swagger spec. It reads the endpoints and user stories, generates a comprehensive pytest suite, runs the tests, and if any fail, sends the tracebacks to Claude for root cause analysis.

Without an API key it writes placeholder tests that are reported as skipped, so you can see the shape of the output. Set `ANTHROPIC_API_KEY` for real, model-written test cases including security scenarios.

```
requirements.txt / openapi.yaml
         │
         ▼
  ┌─────────────────┐
  │  Code Analyzer  │  ← parses endpoints, schemas, user stories
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │   Claude API    │  ← generates test cases + pytest code
  │  (mock fallback)│
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Test Runner    │  ← executes pytest, captures results
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ Failure Analyst │  ← AI explains failures, suggests fixes
  └────────┬────────┘
           │
           ▼
  HTML / JSON / Markdown report
```

---

## Features

**Test generation**
- Positive, negative, and edge case tests from natural language or specs
- Proper pytest fixtures, `conftest.py`, and `pytest.ini`
- Parametrized tests for data-driven scenarios
- Auth handling: Bearer, API key, OAuth2, Basic

**Input formats**
- Plain text requirements and Markdown user stories
- OpenAPI 3.x / Swagger 2.x specs (YAML or JSON) with `$ref` resolution
- PDF and Word documents

**AI failure analysis**
- Runs pytest, captures tracebacks and assertion errors
- Sends each failure to Claude for root cause analysis
- Returns structured report: severity, likely cause, recommended fix
- Without API key: classifies failures by pattern (connection, auth, schema, timeout)

**Compliance tagging** — HIPAA · NIST 800-53 · ISO 27001
- Maps endpoints to applicable regulatory controls
- Injects `@pytest.mark.nist_ia_2` / `@pytest.mark.hipaa_164_312_d` decorators
- Generates coverage reports showing which controls have tests and which have gaps

**Environment management**
- Per-environment variable sets (like Postman, for test configs)
- Switch between staging, production, and local with one command

**CI/CD ready**
- GitHub Actions workflow included
- JUnit XML output for any CI system
- Docker support for isolated runs

---

## Installation

Requires Python 3.9+.

```bash
git clone https://github.com/dannicolau7/ai-testing-agent.git
cd ai-testing-agent
pip install -r requirements.txt

# Optional: set your Claude API key for real AI generation
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

---

## Quick start

```bash
# Runs without an API key, but see the note below
echo "POST /api/checkout — validate card, process payment, return confirmation or error" > reqs.txt
python cli.py run reqs.txt
```

Without `ANTHROPIC_API_KEY` the tool writes **placeholder tests**. They show the shape of
the output and check nothing, so they are reported as skipped, never as passed:

```
✅ Generated 4 pytest files
🧪 Executing tests...
✅ Tests ran: 0 passed, 0 failed, 0 errors, 4 skipped
⚠️  Nothing was actually checked: every test was skipped (placeholder output?).
```

With a key set, the tests are written by the model and then really run with pytest. The
counts in the report are pytest's own.

### Check the tests themselves

Two commands that need no model:

```bash
python cli.py trace requirements.md tests/     # which requirement does each test check?
python cli.py validate tests/                  # does each test fail when the response is wrong?
```

- `trace` reads requirement ids such as `REQ-12` or `US-7` and lists requirements with no
  test, tests that point at no requirement, and tests that point at a requirement that does
  not exist. A test points at a requirement with `@pytest.mark.requirement("REQ-12")`, a
  `Covers: REQ-12` line in its docstring, or a `# Requirement: REQ-12` comment above it.
- `validate` runs the tests, then runs them again with every HTTP response replaced by a
  wrong one. A test that still passes does not check the response it gets. It covers tests
  that call the system through the `requests` library.

Both exit 1 when they find gaps. `docs/ROADMAP.md` says where this is going.

### Audit an application's source

```bash
python cli.py audit path/to/app            # do the frontend, backend, API spec and database agree?
python cli.py audit examples/audit-demo    # a small sample with planted problems
```

`audit` reads the source and needs no model and no running application. It finds backend
routes (FastAPI, Flask, Express), frontend requests (`fetch`, `axios`), OpenAPI specs and
database tables (SQL `CREATE TABLE` in `.sql` files or Python strings, SQLAlchemy models), then reports where they disagree:

- **Wrong now:** the frontend calls a route that does not exist; the spec documents an
  operation nobody implemented; the spec says a route needs authentication and the code
  shows no check.
  For Python backends it also follows each handler to the SQL and SQLAlchemy or SQLModel
  calls it makes, and reports code that uses a table or column the database does not define.
  JavaScript and TypeScript backends are read more roughly: Prisma calls and SQL strings.
  For FastAPI backends it compares request bodies, query parameters and responses: a field
  the backend requires that the frontend does not send or the spec does not list, and a
  response field the spec promises that the backend does not return. Frontend bodies are
  read from object literals and from TypeScript types.
- **Likely to go wrong:** a field the frontend sends or the spec lists that the backend
  ignores; a response field the spec does not mention; a route that changes data with no visible access check; a row
  fetched by id with no sign that the caller owns it; SQL built by inserting a function
  argument into the text; a GET that changes data; a route missing from the spec; a table with no primary
  key; an `_id` column with no foreign key.
- **Unclear:** things the audit could not decide, for a person to look at.
- **Not examined:** stated every time, including any layer it did not find.

Add your requirements to check the code against them:

```bash
python cli.py audit path/to/app --requirements requirements.md
```

No model reads the requirements, so a requirement is linked to code only where the link is
written down: the requirement names a route (`GET /api/orders/{id}`), or a handler has
`# Requirement: REQ-3` above it. For a linked requirement the audit checks four things it
can read from the wording: sign-in, "their own" (ownership), administrators only, and
"must be unique" against the database. A table in the report shows, per requirement, what
it was linked to, what was checked and the result. Unlinked requirements are listed as
unclear, never as met.

Most requirements do not name a route. A model can propose the links, and you confirm them:

```bash
python cli.py link path/to/app -r requirements.md -o links.yaml    # a model proposes
# read links.yaml, set `confirmed: true` on the right ones
python cli.py audit path/to/app -r requirements.md --links links.yaml
```

The model picks, from a numbered list, the one route each requirement is about, or none. It
is shown route and handler names, never source code, and nothing it proposes is used until
a person confirms it.

### Who may do what

```bash
python cli.py permissions path/to/app --init --roles customer,admin   # a draft table from the code
python cli.py audit path/to/app --permissions permissions.yaml        # the code against the table
python cli.py permissions --tests permissions.yaml                    # one test for every cell
```

The permissions table lists, for each route, which roles are allowed and whether a caller
may reach only their own rows. `--init` writes a draft describing what the code appears to
do today; you correct it to what the product should do. `audit --permissions` then reports
a route that must refuse someone and shows no check for it, and routes nobody wrote a rule
for. `--tests` writes one pytest test per role and route, including every cell that must be
refused. Run those against a test environment only: they send real requests. A test with no
token for its role is skipped, never passed, and a test that would change data is skipped
unless you set `PERMISSIONS_ALLOW_WRITES=1`.

### From findings to proof

```bash
python cli.py audit path/to/app -r requirements.md --tests-out test_findings.py
FINDINGS_BASE_URL=http://localhost:8000 pytest test_findings.py
```

The audit reads source, so a finding is evidence, not proof. `--tests-out` writes one test
for each finding a request can settle:

- a route the frontend or the spec relies on **exists**;
- a route that shows no access check **refuses a caller who is not signed in**;
- a route that shows no ownership check **refuses a user asking for someone else's row**.

A test that fails means the fault is real. A test that passes means the finding was a false
alarm, or has been fixed. Tests carry the requirement they came from, so `trace` counts
them. Findings a request cannot settle are listed at the top of the generated file.

These tests send real requests. One that would change data is skipped unless you set
`FINDINGS_ALLOW_WRITES=1`, because if the fault is real the change happens. Use a test
environment only.

### The agent: every stage in one run

```bash
python cli.py agent path/to/app -r requirements.md --url http://localhost:8000 --out-dir agent-run
```

The agent does the stages in order and uses what each one learned. It reads the source, then
takes every finding a request can settle, writes the test, runs it against your test
environment, and sorts the finding by what happened:

- **confirmed:** the server answered, and answered wrongly. The fault is real.
- **cleared:** the server behaved as it should. The audit was wrong, or the fault is fixed.
  The finding is removed from the lists.
- **not run:** the test was skipped or could not complete. The finding stays as it was.

With `--permissions` it also sends one request for every role and route in the table and
reports each cell as holds, broken or not run (tokens come from `ROLE_<NAME>_TOKEN`).

Then it opens the app in a browser, carries out `--journeys` if given, and writes one report
with a plain list of what it did, what it could not do, and what needs a person.

If a model is configured (a local one is free; see below) it also proposes which route each
requirement is about. Those proposals never change the verdict. The report shows separately
what the audit would find if they were right, and writes `requirement-links.yaml` for you
to confirm.

Rules it keeps:

- A model proposes; a request or a person decides.
- A step that was not run is listed as not run, with the reason. Never as passed.
- No answer from the server is not evidence: a fault is confirmed only when the server answered.
- It sends requests only to this machine, or to one you name with `--authorization` (who
  gave written permission, where it is filed). That line goes in the report.
- It changes data only with `--allow-writes`.
- With `--sign-in FILE` the agent signs each role in itself; passwords are named as
  environment variables, never written in the file. Otherwise sign-in comes from
  `FINDINGS_USER_TOKEN` and `ROLE_<NAME>_TOKEN`, or the `_COOKIE` forms. No value is ever
  written down.
- Requests that need a body get the smallest one the application's API spec accepts
  (`--spec`, or found in the source or at the test address).
- Name ids for the paths with `PATH_IDS`, and ids of another user's rows with
  `OTHER_PATH_IDS`, so a refusal is tried against someone else's row too.
- A redirect to the sign-in page counts as refused; "not found" and server errors count as
  nothing shown.

With `--memory FILE` the agent remembers each run and the report says what was fixed, what
is new, what came back after being fixed, and which checks stopped running.

`--out-dir` writes `report.md`, `report.html`, `run.json` (every step and result), the
generated tests and the proposed links. See [docs/agent.md](docs/agent.md).

### Automated tests to keep

```bash
python cli.py automate path/to/app --url http://localhost:8000 --sign-in sign-in.yaml -o automation/
AUTOMATION_BASE_URL=http://localhost:8000 pytest automation -rs
```

`automate` writes a test suite for the team to commit and run on every change. It has no
dependency on this tool.

- **Backend:** for every operation in the API spec, the answer is one the spec documents, a
  success carries the fields the spec requires, a caller who is not signed in is refused, and
  a body with no required field is turned down.
- **Frontend:** every page the browser reached loads without an error or a failed request,
  and every journey in `--journeys` works in the page and leaves the result in the backend.

Backend tests are checked against the API spec. With no spec none are written: a test written
from the code alone would repeat the code's bugs. A test that could change data waits for
`AUTOMATION_ALLOW_WRITES=1`, and a test that cannot run is skipped with the reason, never
passed. See [docs/automation.md](docs/automation.md).

### On every pull request

```bash
python cli.py audit path/to/app --save baseline.json        # on the main branch
python cli.py audit path/to/app --baseline baseline.json    # on the pull request
```

With `--baseline` the report shows only what the change did: new findings, fixed findings,
and a count of what was already there. It exits 1 only when the change adds something that
is wrong now, so known problems do not block every pull request. A finding that only moved
to another line is not new. `docs/audit-on-pull-requests.md` has a GitHub Actions example.

### In a real browser

```bash
pip install playwright && playwright install chromium
python cli.py browse http://localhost:3000 --source path/to/app
python examples/browser-demo/server.py 8765 &      # a small site with planted problems
python cli.py browse http://127.0.0.1:8765
```

`browse` opens the running application in a browser, follows its links, and reports what it
sees: a page that throws an error, a request to the API answered "not found" or with a
server error, a link that leads nowhere. With `--source` it also lists which backend routes
it saw being called. It only opens pages and follows links; it never fills in forms, and
it clicks buttons only with `--click`, skipping any whose label looks destructive. Use it
against a test environment, never production. `--header 'Authorization: Bearer ...'`
signs it in.

### One report from everything

```bash
python cli.py full-report path/to/app -r requirements.md -p permissions.yaml \
    --tests tests/ --url http://localhost:3000 -o report.md --html report.html
```

`full-report` runs every check it has the inputs for and writes one document: the verdict,
a table of which checks were run and which were not (with the reason), every finding marked
with the check it came from, one row per requirement (linked code, what was checked,
tests), the permissions table, and what was not examined. A check that was not run is
listed as not run, never as passed. `--html` writes a self-contained page that reads well on
a phone and prints cleanly. Try it on the sample:

```bash
D=examples/audit-demo
python cli.py full-report $D -r $D/requirements.md -p $D/permissions.yaml --tests $D/tests --html report.html
```

### A requirement, carried out in the page

```bash
python examples/browser-demo/server.py 8765 &
python cli.py journey examples/browser-demo/journeys.yaml --url http://127.0.0.1:8765
```

A journey does what a user would do for one requirement, then checks three things: the
steps work in the page, the page sent the request it should and the server accepted it,
and afterwards the backend really holds the result. The last check catches a page that says
"Saved" while the server stored nothing.

```yaml
journeys:
  - id: REQ-4
    name: A user can add a note
    steps:
      - open: /notes
      - fill: {field: Title, value: Buy milk}
      - click: Save
      - see: Buy milk
    page_must_call: POST /api/notes
    backend_must_show: {get: /api/notes, contains: Buy milk}
```

A person writes the journeys. They do exactly what their steps say, including saving and
deleting, so run them against a test environment only.

### Which model, and what it costs

| Setting | Model | Cost |
|---|---|---|
| nothing | none: `audit`, `trace` and `validate` need no model | free |
| `ATA_MODEL_URL=http://localhost:11434/v1` and `ATA_MODEL_NAME=llama3.2` | a local model (Ollama, llama.cpp, LM Studio, or any OpenAI-compatible server) | free; nothing leaves the machine |
| `ANTHROPIC_API_KEY=...` | Claude through the Anthropic API | paid per use |

A local model wins when both are set, so nobody is billed by surprise. A small local model
is much weaker than Claude: on the demo's nine plain-worded requirements, Llama 3.2 (3B)
proposed the right answer for seven and a wrong route for two, in about 20 seconds on a
CPU. That is why every proposal needs a person's confirmation.

How well this works on code we did not write is recorded honestly in
`docs/real-code-trial.md`, and checked on every change by `python trials/planted_faults.py`.

It exits 1 when there is a "wrong now" finding. It compares the layers with each other; it
reads data access but not the rest of the handler logic, and does not know your requirements, so a clean result means the layers
agree, not that the product is right.

From an OpenAPI spec (auto-detected by `.yaml` extension):

```bash
python cli.py run test_specs/petstore.yaml
```

```
📄 Loading spec: test_specs/petstore.yaml
   Title   : Petstore API
   Version : OpenAPI 3.x
   Base URL: https://petstore.swagger.io/v2
   Endpoints: 4

🔧 Generating tests for tag: [pets] (4 endpoints)
   ✓ Wrote test_pets.py (72 lines)

✅ Spec ingestion complete — 1 file(s) written to test_output/
```

---

## Usage

```bash
python cli.py run requirements.txt           # generate + execute tests
python cli.py run openapi.yaml              # spec ingestion (auto-detected)
python cli.py run openapi.yaml --analyze    # generate, run, and analyze failures
python cli.py chains openapi.yaml           # detect and generate chain tests
python cli.py chains openapi.yaml --list    # print detected chains, no output file
python cli.py failures test_output/         # analyze failures in existing test output
python cli.py analyze requirements.txt      # analyze only, no execution
python cli.py report requirements.txt       # generate report (HTML/JSON/MD)
python cli.py usage                         # show session usage stats
python cli.py analytics                     # show telemetry status
python cli.py analytics-disable             # disable telemetry permanently
```

**Key flags:**

| Flag | Description |
|---|---|
| `--api-key KEY` | Claude API key (overrides `ANTHROPIC_API_KEY`) |
| `--analyze` | Run failure analysis after test execution |
| `--format html\|json\|markdown` | Report format (default: html) |
| `--compliance compliance.yaml` | Apply compliance tagging |
| `--no-telemetry` | Disable analytics for this run |
| `--verbose` | Detailed output |

**Python API:**

```python
from ai_testing_agent import AITestingAgent

agent = AITestingAgent()                        # mock AI
agent = AITestingAgent(api_key="sk-ant-...")    # real Claude

with open("reqs.txt") as f:
    result = agent.run_autonomous(f.read())

print(f"Generated {result['test_cases']} test cases")
print(f"Report: {result['report']}")
```

**Environment management:**

```bash
python cli.py env create staging
python cli.py env set staging BASE_URL https://api.staging.example.com
python cli.py env use staging
```

---

## Compliance

The compliance module maps endpoints to controls from HIPAA, NIST 800-53, and ISO 27001, then injects pytest marks into generated test files.

```bash
# Copy the example config and select your frameworks
cp compliance.yaml.example compliance.yaml

# Generate tests with compliance marks
python cli.py run openapi.yaml --compliance compliance.yaml

# Check control coverage
python cli.py compliance-report test_output/ --compliance compliance.yaml
python cli.py compliance-report test_output/ --compliance compliance.yaml --format markdown > compliance_report.md
```

Example generated mark:

```python
@pytest.mark.hipaa_164_312_d
@pytest.mark.nist_ia_2
def test_login_requires_authentication(api_client):
    ...
```

The coverage report shows which controls have test coverage and which have gaps, by framework and by endpoint.

---

## Project structure

```
ai-testing-agent/
├── ai_testing_agent.py     # core orchestration engine
├── cli.py                  # command-line interface
├── code_analyzer.py        # parses endpoints from specs and requirements
├── spec_ingestion.py       # OpenAPI/Swagger parsing and $ref resolution
├── request_body_handler.py # generates test code for request body types
├── auth_handler.py         # authentication fixture generation
├── failure_analyzer.py     # AI-powered failure root cause analysis
├── data_manager.py         # test data loading (YAML, JSON, Excel)
├── env_manager.py          # per-environment variable management
├── compliance.py           # HIPAA/NIST/ISO control mapping and mark injection
├── compliance.yaml.example # template compliance config — copy to compliance.yaml
├── analytics.py            # anonymous usage telemetry (opt-out)
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/
    ├── tests.yml           # runs on every push
    └── publish.yml         # publishes to PyPI on release
```

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key. Without it, mock AI is used. |
| `AI_TESTING_NO_ANALYTICS` | Set to `1` to disable telemetry. |

**Telemetry:** Anonymous usage events are collected by default (no code, no requirements content, no PII). To opt out permanently:

```bash
export AI_AGENT_TELEMETRY=false
```

See [ANALYTICS.md](ANALYTICS.md) for exactly what is collected.

---

## Contributing

Open an issue before starting significant changes.

```bash
# Run the test suite
python -m pytest test_ai_routing.py test_analytics.py test_usage_tracking.py \
  test_spec_ingestion.py test_failure_analyzer.py test_compliance.py -v

# Check for syntax errors
flake8 --select=E9,F63,F7,F82 .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## License

MIT — see [LICENSE](LICENSE).
