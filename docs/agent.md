# The audit agent

`python cli.py agent` runs the audit as one job instead of eight commands. This page says
what it does, what it will not do, and what it has and has not been tried on.

## What it does, in order

1. **Reads the source** and builds the audit's model of the application: routes, frontend
   calls, spec operations, tables, and the checks the code shows.
2. **Proposes links** (only if a model is configured and requirements were given). A model
   picks which route each requirement is about. Nothing it says changes the verdict.
3. **Tests the findings** (only with `--url`). Each finding a request can settle becomes a
   test, run against your test environment. See "Sorting a finding" below.
4. **Browses the application** (only with `--url`, unless `--no-browser`). It follows links
   and reports pages that throw errors, requests answered 404 or 5xx, and broken links.
5. **Carries out journeys** (only with `--journeys` and `--url`).
6. **Lines existing tests up with requirements** (only with `--tests`; `--validate` also
   checks each can fail).
7. **Writes one report.**

Each step that cannot run says why and is listed as not run. The report's verdict says how
many of the checks did not run, so a partial run cannot pass for a full one.

## Sorting a finding

The audit reads source, so a finding is a suspicion. The agent asks the running system.

| Result of the test | What the agent does |
|---|---|
| Failed an assertion (the server answered, wrongly) | **Confirmed.** Listed under Wrong now with what the server said. |
| Passed | **Cleared.** Removed from the lists and shown under "Settled by a request". |
| Skipped (no token, writes not allowed, no answer) | **Not run.** The finding stays where it was. |
| Failed for any other reason | **Not run.** The test itself broke; that is not evidence about the application. |

Only three kinds of finding can be settled by a request today: a route the frontend relies
on does not exist, a route shows no access check, a route shows no ownership check. Every
other finding is listed under "Needs a person".

## Rules

- **A model proposes; a request or a person decides.** A model never sets a verdict.
- **No answer is not evidence.** If nothing answers at the address, the test step fails and
  no finding is confirmed or cleared.
- **It sends requests only where it may.** On this machine freely. Any other machine needs
  `--authorization` with who gave written permission and where it is filed, at least ten
  characters; the text is recorded in the report. An address with a user name or password in
  it, or one that is not http or https, is refused.
- **It changes data only with `--allow-writes`.** Without it, a test that sends POST, PUT,
  PATCH or DELETE is skipped, and the finding stays.
- **Secrets stay out.** Tokens are read from `FINDINGS_USER_TOKEN`, `FINDINGS_OTHER_ID` and
  `FINDINGS_PATH_ID`. The report says which were set, never their values.

## What it writes (`--out-dir`)

| File | What it is |
|---|---|
| `report.md`, `report.html` | The report. The HTML reads well on a phone and prints cleanly. |
| `run.json` | Every step, every confirmation, what needs a person. Same input, same output. |
| `tests-from-findings.py` | The tests it ran. Run them yourself to see the same result. |
| `requirement-links.yaml` | The links a model proposed, all `confirmed: false`. |

## Using a model

No model is needed. With one, it proposes links. A local model through any OpenAI-compatible
server is free and sends nothing out:

```bash
ATA_MODEL_URL=http://localhost:11434/v1 ATA_MODEL_NAME=llama3.2 \
  python cli.py agent app -r requirements.md --out-dir agent-run
```

The model is sent each requirement and the names of routes and handlers. It is never sent
source code. `--no-model` turns it off even if one is configured. Confirm the proposals in
`requirement-links.yaml`, then pass the file back with `--links`.

## What it has been tried on

A small application with planted faults, in this project's tests: three real faults
confirmed, one false alarm cleared, writes withheld until allowed, no answer treated as no
evidence. That is all. It has not been run against a real application's test environment,
and its browser and journey steps have run only on the demo site.

## What it cannot do yet

- It does not repeat itself. Each run starts from the source. Comparing two runs (what was
  confirmed last time and is fixed now) uses the existing `audit --save` and `--baseline`.
- It cannot settle findings about missing columns, request shapes or role rules, which need
  a request body or a second role.
- It does not write journeys from requirements. A person writes them.
- It does not sign in through a login form. Pass `--header` for the browser and the token
  variables for the tests.
- It does not read requirements from a ticket system.
