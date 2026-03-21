# AI Testing Agent

**Autonomous pytest generation powered by Claude AI.**
Feed it requirements or an OpenAPI spec — get a complete test suite out.

[![Tests](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/dannicolau7/ai-testing-agent/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## 30-second demo

```bash
git clone https://github.com/dannicolau7/ai-testing-agent.git
cd ai-testing-agent
pip install -r requirements.txt

# Run with built-in mock AI (no API key needed)
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

With a real Claude API key, the agent generates richer test cases, adds security scenarios, and provides failure analysis.

---

## OpenAPI spec demo

Feed any OpenAPI/Swagger spec directly — the agent auto-detects it:

```bash
# Auto-detected by .yaml extension and openapi: key
python cli.py run test_specs/petstore.yaml
```

The agent parses the spec, resolves `$ref` schemas, and writes one pytest file
per tag group:

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

Generated `test_pets.py` (mock AI, free tier):

```python
"""
Tests for pets endpoints — generated from OpenAPI spec
API: Petstore API
"""
import pytest
import requests

BASE_URL = "https://petstore.swagger.io/v2"


@pytest.fixture(scope='session')
def api_client():
    """Shared requests session for all tests in this module."""
    session = requests.Session()
    return session


def test_listPets_success(api_client):
    """List all pets — expects 200."""
    url = f'{BASE_URL}/pets'
    response = api_client.get(url, params={"limit": 20})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "id" in data[0]
        assert "name" in data[0]


def test_createPet_success(api_client):
    """Create a pet — expects 201."""
    url = f'{BASE_URL}/pets'
    payload = {"name": "Fluffy", "tag": "cat"}
    response = api_client.post(url, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "name" in data


def test_createPet_missing_required_field(api_client):
    """POST /pets with empty body — expects 4xx."""
    url = f'{BASE_URL}/pets'
    response = api_client.post(url, json={})
    assert response.status_code in [400, 422]


def test_getPet_not_found(api_client):
    """GET /pets/{petId} with non-existent ID — expects 404."""
    url = f'{BASE_URL}/pets/99999'
    response = api_client.get(url)
    assert response.status_code == 404
```

With `ANTHROPIC_API_KEY` set, Claude generates deeper tests including security
scenarios, schema validation edge cases, and auth token flows.

---

## What it does

1. **Reads** requirements documents (txt, md, PDF, docx) or OpenAPI/Swagger specs
2. **Generates** comprehensive test cases — happy paths, error scenarios, edge cases
3. **Writes** production-ready pytest files with fixtures, parametrize, and docstrings
4. **Executes** the tests and captures results
5. **Analyzes** failures using Claude AI — explains root cause and suggests fixes
6. **Reports** in HTML, JSON, or Markdown

---

## How it works

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
- Plain text requirements
- Markdown user stories and acceptance criteria
- OpenAPI 3.x / Swagger 2.x specs (YAML or JSON)
- PDF and Word documents

**AI-powered failure analysis** — see [docs/failure-analysis.md](docs/failure-analysis.md)
- Runs pytest, captures tracebacks and assertion errors
- Sends each failure to Claude for root cause analysis
- Returns structured report: severity, likely cause, recommended fix
- Free-tier mock classifies failures by pattern (connection, auth, schema, timeout)
- `python cli.py failures test_output/` or `run openapi.yaml --analyze`

**CLI interface**

```bash
python cli.py run requirements.txt          # generate + execute tests
python cli.py run openapi.yaml              # spec ingestion (auto-detected)
python cli.py run openapi.yaml --analyze    # generate, run, and analyze failures
python cli.py failures test_output/         # analyze failures in existing test files
python cli.py analyze requirements.txt      # analyze only, no execution
python cli.py report requirements.txt       # generate HTML/JSON/MD report
python cli.py usage                         # show monthly usage stats
python cli.py tier                          # show current configuration
```

**Environment management** (like Postman, for your test configs)
```bash
python cli.py env create staging
python cli.py env set staging BASE_URL https://api.staging.example.com
python cli.py env use staging
```

**CI/CD ready**
- GitHub Actions workflow included
- JUnit XML output for any CI system
- Docker support for isolated runs

---

## Installation

**Requirements:** Python 3.8+

```bash
# Clone
git clone https://github.com/dannicolau7/ai-testing-agent.git
cd ai-testing-agent

# Install
pip install -r requirements.txt

# Configure (optional — works without for mock AI)
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env for full Claude AI capability
```

---

## Usage

### From a requirements file

```bash
# Write your requirements
cat > reqs.txt << 'EOF'
Feature: User authentication
- POST /auth/login accepts email + password, returns JWT
- Invalid credentials return 401
- Account locks after 5 failed attempts
- GET /auth/me returns current user (requires valid JWT)
- POST /auth/logout invalidates the token
EOF

python cli.py run reqs.txt
```

### From an OpenAPI spec

```bash
python cli.py run openapi.yaml --format spec
```

### Python API

```python
from ai_testing_agent import AITestingAgent

agent = AITestingAgent()  # uses mock AI by default

# Or with Claude API for full capability
agent = AITestingAgent(api_key="sk-ant-...")

with open("reqs.txt") as f:
    result = agent.run_autonomous(f.read())

print(f"Generated {result['test_cases']} test cases")
print(f"Report: {result['report']}")
```

### Failure analysis

```bash
# Run tests — if any fail, analyze them
python cli.py run reqs.txt --analyze
```

Example analysis output:
```
FAILURE ANALYSIS: test_login_invalid_credentials
Severity: Medium
Likely cause: API returns 200 with {"error": "invalid"} instead of 401.
              The test asserts status_code == 401 but received 200.
Recommended fix: Update assertion to check response body, or confirm with
                 API team that 401 is the intended contract for bad credentials.
```

---

## Project structure

```
ai-testing-agent/
├── ai_testing_agent.py     # core orchestration engine
├── cli.py                  # command-line interface
├── code_analyzer.py        # parses endpoints from specs and code
├── request_runner.py       # sends HTTP requests, saves as tests
├── request_body_handler.py # generates test code for request body types
├── auth_handler.py         # authentication fixture generation
├── data_manager.py         # test data loading (YAML, JSON, Excel)
├── env_manager.py          # environment management (like Postman)
├── project_generator.py    # generates full project structure
├── analytics.py            # privacy-first usage telemetry (opt-out)
├── tests/
│   ├── test_ai_routing.py
│   ├── test_analytics.py
│   ├── test_endpoint_limits.py
│   └── ...
├── .github/workflows/
│   ├── tests.yml           # runs on every push
│   └── publish.yml         # publishes to PyPI on release
└── docs/                   # documentation
```

---

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | Claude API key. Without it, mock AI is used. |
| `AI_AGENT_LICENSE_KEY` | No | For extended limits (coming soon). |
| `AI_TESTING_NO_ANALYTICS` | No | Set to `1` to disable telemetry. |

The tool works out of the box with no keys. Mock AI produces realistic test structures useful for learning, prototyping, and CI pipelines that don't need real API access.

---

## Telemetry

Anonymous usage statistics are collected by default (no code, no test content, no PII). To opt out:

```bash
export AI_TESTING_NO_ANALYTICS=1
```

See [ANALYTICS.md](ANALYTICS.md) for exactly what is collected.

---

## Roadmap

- [x] Core autonomous test generation
- [x] Mock AI (no API key needed)
- [x] Multi-format reports (HTML, JSON, Markdown)
- [x] Environment management
- [x] Docker support
- [x] OpenAPI spec ingestion — YAML/JSON, $ref resolution, per-tag output (Week 2)
- [x] AI failure analysis — `--analyze` flag + `failures` command (Week 3)
- [ ] Compliance tagging — HIPAA, NIST, ISO 27001 (Week 4)
- [ ] Multi-endpoint test chaining (Month 2)
- [ ] Playwright support for OAuth flows (Month 3)
- [ ] LLM endpoint validation — hallucination detection (Month 3)

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss approach.

```bash
# Run tests
python -m pytest test_ai_routing.py test_analytics.py test_endpoint_limits.py -v

# Lint
flake8 --select=E9,F63,F7,F82 .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

---

## License

MIT — see [LICENSE](LICENSE).
