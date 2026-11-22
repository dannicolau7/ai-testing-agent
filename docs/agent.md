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
4. **Tries the permissions table** (only with `--permissions` and `--url`). One request for
   every role and route in the table, refusals included. See "The permissions table" below.
5. **Browses the application** (only with `--url`, unless `--no-browser`). It follows links
   and reports pages that throw errors, requests answered 404 or 5xx, and broken links.
6. **Carries out journeys** (only with `--journeys` and `--url`).
7. **Lines existing tests up with requirements** (only with `--tests`; `--validate` also
   checks each can fail).
8. **Writes one report.**

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

## The permissions table

With `--permissions` the agent sends one request per cell of the table and sorts each cell:

| What happened | Result |
|---|---|
| The system did what the table says | **Holds** |
| A role the table refuses got through, or a role it allows was turned away | **Broken**: listed under Wrong now |
| No token for that role, a write that was not allowed, no answer | **Not run** |

Give each signed-in role a token in `ROLE_<NAME>_TOKEN`, for example `ROLE_ADMIN_TOKEN`.

This also settles a suspicion the source audit cannot: "this route must refuse customers, but
no role check is visible". If every refusal the table asks of that route was tried and held,
the finding is cleared. If one was broken, the broken cell is reported in its place. If any
was not run, the finding stays.

One id is used for every path parameter, so "own rows only" is not tried here with two
users' data. The ownership test under "Sorting a finding" does that.

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
- **Secrets stay out.** Tokens are read from `FINDINGS_USER_TOKEN`, `FINDINGS_OTHER_ID`,
  `FINDINGS_PATH_ID` and `ROLE_<NAME>_TOKEN`. The report says which were set, never their values.

## What it writes (`--out-dir`)

| File | What it is |
|---|---|
| `report.md`, `report.html` | The report. The HTML reads well on a phone and prints cleanly. |
| `run.json` | Every step, every confirmation, what needs a person. Same input, same output. |
| `tests-from-findings.py`, `tests-from-permissions.py` | The tests it ran. Run them yourself to see the same result. |
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

Two small applications with planted faults, in this project's tests: three real faults
confirmed and one false alarm cleared; and a permissions table of twelve cells where one
planted hole is found, eleven cells hold and one false suspicion is cleared. Writes are
withheld until allowed, and no answer is treated as no evidence. That is all. It has not been run against a real application's test environment,
and its browser and journey steps have run only on the demo site.

## What it cannot do yet

- It does not repeat itself. Each run starts from the source. Comparing two runs (what was
  confirmed last time and is fixed now) uses the existing `audit --save` and `--baseline`.
- It cannot settle findings about missing columns or request shapes, which need a request
  body.
- It does not write journeys from requirements. A person writes them.
- It does not sign in through a login form. Pass `--header` for the browser and the token
  variables for the tests.
- It does not read requirements from a ticket system.
