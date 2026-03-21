# AI Failure Analysis

The `--analyze` flag and `failures` command run your tests, capture any
failures, and send each one to Claude for a structured diagnosis.

---

## Usage

### After generating from a spec

```bash
# Generate tests AND run + analyze failures in one step
python cli.py run test_specs/petstore.yaml --analyze
```

### On existing test files

```bash
# Run and analyze a specific file
python cli.py failures test_output/test_pets.py

# Multiple files or a whole directory
python cli.py failures test_output/

# JSON output for CI/CD systems
python cli.py failures test_output/ --json
```

---

## Example: failure in vs. AI analysis out

### Input — pytest failure

```
FAILED test_output/test_pets.py::test_createPet_success

================================== FAILURES ===================================
_________________________ test_createPet_success __________________________

    def test_createPet_success(api_client):
        """Create a pet — expects 201."""
        url = f'{BASE_URL}/pets'
        payload = {"name": "Fluffy", "tag": "cat"}
        response = api_client.post(url, json=payload)
>       assert response.status_code == 201
E       AssertionError: assert 405 == 201

test_output/test_pets.py:37: AssertionError
```

### Output — AI analysis (with ANTHROPIC_API_KEY)

```
======================================================================
  FAILURE ANALYSIS REPORT  (1 failure(s))
======================================================================

  [1] test_createPet_success
  ──────────────────────────────────────────────────────────────────
  Severity  : HIGH
  Cause     : The Petstore demo server at petstore.swagger.io returned
              405 Method Not Allowed for POST /pets. The demo server
              is likely read-only and does not accept write operations.
  Fix       : Point BASE_URL to a local or writable test server.
              Alternatively, mock the POST request in the test.
  Suggestion:
      # Option 1: Use a local test server
      BASE_URL = "http://localhost:8080"

      # Option 2: Skip on read-only servers
      @pytest.mark.skip(reason="Demo server is read-only")
      def test_createPet_success(api_client):
          ...

======================================================================
```

### Output — mock analysis (free tier, no API key)

```
======================================================================
  FAILURE ANALYSIS REPORT  (1 failure(s))
======================================================================

  [1] test_createPet_success
  ──────────────────────────────────────────────────────────────────
  Severity  : HIGH [MOCK — add ANTHROPIC_API_KEY for AI analysis]
  Cause     : The API returned an unexpected HTTP status code.
              The test expected one code but received another.
  Fix       : Verify the endpoint contract. Check if auth headers,
              request body, or base URL are correct.

======================================================================
```

---

## Severity levels

| Level | When it applies |
|---|---|
| `critical` | Auth failures (401/403), connection refused, data corruption |
| `high` | Wrong status code, missing required field, JSON decode error, timeout |
| `medium` | Schema mismatch, assertion off-by-one, unexpected empty response |
| `low` | Test setup issue, flaky network, test data not seeded |

---

## JSON output (for CI)

```bash
python cli.py failures test_output/ --json
```

```json
{
  "exit_code": 1,
  "passed": 2,
  "failed": 1,
  "analyses": [
    {
      "test_name": "test_createPet_success",
      "severity": "high",
      "likely_cause": "The API returned 405 Method Not Allowed...",
      "recommended_action": "Point BASE_URL to a writable server...",
      "code_suggestion": "",
      "is_mock": false
    }
  ]
}
```

---

## How it works

```
pytest test_output/test_pets.py --tb=long
         │
         ▼
  FailureAnalyzer.parse_failures()
  ├── extract FAILURES block
  ├── split into per-test sections
  └── build FailureRecord (test_name, error_type, traceback, message)
         │
         ▼
  FailureAnalyzer.analyze_failure()
  ├── with API key  → Claude prompt → structured JSON response
  └── without key   → pattern-match mock (still useful)
         │
         ▼
  FailureAnalysis (severity, likely_cause, recommended_action, code_suggestion)
         │
         ▼
  format_report() → terminal output
  format_json()   → CI-friendly JSON
```

---

## Patterns detected without an API key

The free-tier mock recognizes these failure signatures:

- **Connection refused** → critical (server not running)
- **401 / 403 / Unauthorized** → critical (auth issue)
- **Timeout** → high (server too slow)
- **JSON decode error** → high (non-JSON response body)
- **Wrong status code** → high (endpoint contract mismatch)
- **Missing key in response** → medium (schema drift)
- **Generic assertion failure** → medium (review traceback)

With `ANTHROPIC_API_KEY` set, Claude provides context-specific diagnosis
rather than pattern-matching — including suggested code fixes.
