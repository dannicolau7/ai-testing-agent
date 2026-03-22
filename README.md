# AI Testing Agent

Autonomous pytest generation from requirements documents and OpenAPI specs.

[![Tests](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## What it does

Feed it a requirements document (txt, md, PDF, docx) or an OpenAPI/Swagger spec. It reads the endpoints and user stories, generates a comprehensive pytest suite, runs the tests, and if any fail, sends the tracebacks to Claude for root cause analysis.

Works without an API key — mock AI produces structurally valid tests for prototyping and CI pipelines. Set `ANTHROPIC_API_KEY` to get full Claude-generated test cases including security scenarios, schema edge cases, and auth flows.

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
# Works without an API key
echo "POST /api/checkout — validate card, process payment, return confirmation or error" > reqs.txt
python cli.py run reqs.txt
```

Output:
```
Analyzing requirements...
Generating test cases...

  ✓ test_valid_payment_returns_200
  ✓ test_missing_card_number_returns_400
  ✓ test_expired_card_returns_402
  ✓ test_insufficient_funds_returns_402
  ✓ test_invalid_cvv_returns_422
  ✓ test_concurrent_checkout_idempotency

Generated 6 test cases → test_output/test_checkout.py
Report → test_output/test_report.html
```

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
