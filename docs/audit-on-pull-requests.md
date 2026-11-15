# Running the audit on every pull request

The audit reads source only. It needs no model, no API key, no running application and no
secrets, so it is safe to run on pull requests from forks.

The idea: audit the main branch to get a baseline, audit the pull request, and report only
the difference.

## GitHub Actions example

This is an example to copy into the repository you want audited, as
`.github/workflows/audit.yml`. It has not been run in a real repository yet; treat it as a
starting point. Change `APP_DIR` to the folder that holds your application.

```yaml
name: Application audit
on: pull_request
permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    env:
      APP_DIR: .
      AI_AGENT_TELEMETRY: "false"   # the tool's anonymous usage statistics, off in CI
    steps:
      - uses: actions/checkout@v4
        with:
          path: change
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: base
      - uses: actions/checkout@v4
        with:
          repository: dannicolau7/ai-testing-agent
          path: tool
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install pyyaml
      - name: Audit the base branch
        run: python tool/cli.py audit "base/$APP_DIR" --save baseline.json || true
      - name: Audit the change
        run: |
          python tool/cli.py audit "change/$APP_DIR" --baseline baseline.json --output audit.md
      - name: Show the result
        if: always()
        run: cat audit.md >> "$GITHUB_STEP_SUMMARY"
```

What it does:

- The base audit is allowed to fail (`|| true`): the main branch may have known problems.
- The second audit fails the job only when the pull request adds something that is wrong
  now. New "likely" and "unclear" items are shown but do not fail it.
- The result appears on the run's summary page.

## Add your requirements and permissions

If the repository has a requirements file and a permissions table, pass them to both
audits so they are compared as well:

```bash
python tool/cli.py audit "$APP_DIR" -r docs/requirements.md -p permissions.yaml --baseline baseline.json
```

## What a pass means

The change added no finding that is wrong now. It does not mean the application is right:
the audit reads declarations and data access, not all of a handler's logic, and it does not
run anything.
