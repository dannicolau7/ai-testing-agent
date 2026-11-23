# Trials on real applications

## Trial 1: a FastAPI application

Until this trial the audit had only been run on its own sample application and on two small
projects of ours. This is the first run on code written by someone else, with no knowledge
of this tool.

**Application:** `fastapi/full-stack-fastapi-template` (MIT licence), commit `aabb901`. A
FastAPI backend with SQLModel and a React frontend that calls the API through a generated
client. 23 backend routes, 2 database tables.

**What was run:** the source audit and the permissions comparison. The application was not
started, so the browser check and the generated permission tests were not run.

## Result of the first run: the audit was wrong about almost everything

| What | First run | Truth |
|---|---|---|
| Route paths | `/{id}`, `/me`, `/` | `/api/v1/items/{id}`, `/api/v1/users/me`, ... |
| Frontend calls found | 0 | 23 |
| Database tables found | 0 | 2 |
| Routes whose data access was read | 0 of 23 | 17 of 23 have some |
| "No access check" findings | 17 | 1 is real |

Sixteen of the seventeen findings were false. A report like that would have cost a customer's
trust in the first five minutes. Every miss came from a way of writing FastAPI that the
sample application did not use:

| Missed | Why |
|---|---|
| Path prefixes | `APIRouter(prefix=...)` and `include_router(..., prefix=settings.X)` were not followed |
| Access checks | They are declared as type aliases (`current_user: CurrentUser`) and as `dependencies=[...]` on the route |
| One whole file | It uses Python 3.14 syntax (`except A, B:`), which an older Python refuses to parse; the file defining the access checks was silently unread |
| Tables | SQLModel classes (`class User(UserBase, table=True)`) were not read |
| Data access | `session.add(item)` on a variable; `crud.create_user(...)` where a route handler has the same name |
| Frontend calls | A generated client (`client.get({ url: '/api/v1/items/' })`), not `fetch` or `axios` |
| Sign-in routes | Login, sign-up and password reset were reported for having no access check |

All of these are now read, and each has a regression test in `test_real_code_patterns.py`.

## Result after the fixes

| What | Now |
|---|---|
| Route paths | all 23 correct |
| Frontend calls found | 23, each matching a backend route |
| Database tables found | 2, with keys and foreign keys |
| Routes whose data access was read | 17 of 23 |
| Findings | 1 |

The one finding: **`POST /api/v1/private/users/` changes data and shows no access check.**
This is true. The route creates a user with no sign-in. The project includes it only when
the environment is `development`, which the audit cannot see. It is the kind of thing an
auditor should raise and a developer should be able to answer.

With a permissions table written by hand (22 rules, 3 roles) the comparison adds nothing
false: the same route appears once more as having no rule. The table's "the code shows"
column is right for all 22 routes on inspection.

## What this trial does not show

- **One application.** It is a well-kept template written by the author of FastAPI. Messier
  code will expose more.
- **No planted faults.** We know the audit raised no false alarm here after the fixes; we do
  not know what real faults it would miss, because this code has few.
- **Nothing was run.** The 66 generated permission tests were written but not executed; the
  browser check was not used.
- **Request shapes were not compared.** The frontend's bodies are typed in a generated file
  the shape reader does not follow yet.
- **The fixes were made by looking at this application.** They are general FastAPI
  patterns, but the second real application is the fairer test.

## Trial 2: a Flask application and an Express application

The fairer test: two applications in styles the audit had not been adjusted for. The first
run was recorded before anything was changed.

- **Flask:** the tutorial application in `pallets/flask` (`examples/tutorial`, BSD-3-Clause),
  commit `49943b5`. Blueprints, raw SQL on SQLite, server-rendered pages. 12 routes, 2 tables.
- **Express:** `gothinkster/node-express-realworld-example-app` (MIT), commit `30b68e1`.
  TypeScript, Prisma, JWT middleware. 20 routes, 8 tables.

| | Flask, first run | Express, first run |
|---|---|---|
| Routes read correctly | 12 of 12 | 20 of 20 (without the `/api` mount prefix) |
| Tables read | 2 of 2 | 8 of 8 |
| Findings | 6 | 12 |
| Of which false | 6 | 11, and 1 open by design |

Better than Trial 1's first run, since paths, tables and decorators were right, but every
finding was still false or unhelpful. The causes:

| False finding | Why |
|---|---|
| "GET changes data" (Flask, 3) | One Flask handler serves GET and POST and writes only on POST |
| "No ownership check" (Flask, 3) | The check is written `post["author_id"] != g.user["id"]`; dictionary keys were not read |
| "No access check" (Express, 8) | A formatter had put the route over several lines, and the middleware was on a later line |
| "No primary key" (Express, 3) | Join tables keyed by a unique index that a later statement adds |
| "No access check" on `POST /users` (Express, 1) | Sign-up, open by design; the path does not say so |

After the fixes: Flask reports nothing, Express reports the sign-up route only. Each fix has
a regression test.

## Trial 3: planted faults

Trials 1 and 2 show what the audit wrongly reports. They do not show what it misses, because
these applications have few faults. So fourteen realistic faults were planted, one at a
time, in copies of the three applications, and the audit was run on each copy.

| Planted fault | Found |
|---|---|
| FastAPI: sign-in removed from "create item" | Yes |
| FastAPI: owner check removed from "read item" | Yes |
| FastAPI: frontend calls a route that was renamed | Yes |
| FastAPI: backend route removed that the frontend calls | Yes |
| FastAPI: superuser check removed from "delete user" | Only with a permissions table |
| FastAPI: foreign key dropped from `item.owner_id` | **No** |
| Flask: `login_required` removed from "delete" | Yes |
| Flask: author check removed | Yes |
| Flask: query uses a column that does not exist | Yes |
| Flask: query uses a table that does not exist | Yes |
| Flask: SQL built from a request value | Yes |
| Express: auth removed from "delete article" | Yes |
| Express: auth made optional on "update article" | Yes |
| Express: owner check removed from "delete article" | **No** |

**11 of 14 with no inputs, 12 of 14 with a permissions table.**

The misses, and why:

- **Superuser check removed.** The route still asks for sign-in, so nothing looks wrong
  until a permissions table says ordinary users must be refused. This is what the table is for.
- **Foreign key dropped.** The column is `owner_id` and the table is `user`. The audit
  only treats an `_id` column as a reference when a table of that name exists, a rule added
  earlier to stop false alarms. Here it costs a real finding.
- **Express owner check.** The check is in a TypeScript service using Prisma. The audit
  does not read data access in JavaScript or TypeScript at all.

## Trial 4: closing the largest hole

Trial 3's Express miss came from not reading JavaScript or TypeScript data access at all.
`js_data_access.py` now reads it as text: Prisma calls and SQL strings, following calls into
the project's own functions. On the Express application it finds the tables for 19 of 20
routes.

Turning it on immediately produced six new false alarms on that application: every public
article and every "favourite this article" route was reported as missing an ownership
check. Two rules were tightened as a result, for Python and JavaScript alike:

- **A mention is not a check.** The owner column must be compared or filtered on
  (`note.authorId !== userId`, `WHERE owner_id = ?`), or a function whose name says it
  decides access must be called. Selecting the column does not count.
- **The route must address one row and need sign-in.** `/orders/{id}` and
  `/orders/{id}/edit` qualify. An action on someone else's row (`/articles/{slug}/favorite`)
  and a row anyone may read without signing in do not.

Result: the planted Express owner-check fault is now found, with no finding on the three
applications beyond the two already listed.

**12 of 14 planted faults with no inputs, 13 of 14 with a permissions table.** Still missed:
the dropped foreign key on `owner_id`.

A regression was also caught by re-running Trial 3 after the change: handling `DROP TABLE`
removed the Flask application's tables, because its schema drops each table before creating
it. Three planted faults went from found to missed until it was fixed.

## The trial is now a check

`python trials/planted_faults.py` fetches the three applications at pinned commits, audits
them as they are, plants each fault in a copy, and compares every result with the record
written in the script. It runs in CI on every change. It fails when a new finding appears on
an unmodified application, when a planted fault that was found is now missed, and also when
one that was missed is now found, so that this document is updated when the audit improves.

## The first live trial: the agent against a running application

Everything above reads source. On 2026-11-22 the agent was run for the first time against a
real application that was actually running: the Flask project's tutorial application, at the
same pinned commit, started on the local machine, with a permissions table of who may reach
which page.

The application is correct. The agent's first run reported **five of its permission cells
broken. All five were false.** Three causes, none of which the sample applications had shown:

| What the application does | What the generated tests did wrong | Fix |
|---|---|---|
| Sends a visitor who is not signed in to the login page (a 302 redirect) | Followed the redirect, saw the login page's 200, and reported "let through" | Redirects are not followed. A redirect to a sign-in page is a refusal; any other redirect is not |
| Writes path parameters as `<int:id>` | The permission tests filled in only `{id}`, so the request went to a path that does not exist | All three styles are filled in: `{id}`, `<id>`, `:id` |
| Answers 404 for a row that does not exist | Counted "404" as "was not refused", so as a hole | 404, 405 and 5xx show nothing about access. The test is skipped, and says to set an id that exists |

Two more things had to be added before the trial could say anything about a signed-in user:

- **Cookie sign-in.** The tests could only send a bearer token. This application, like many,
  signs in with a session cookie. `ROLE_<NAME>_COOKIE` and `FINDINGS_USER_COOKIE` now work.
- **A refusal proves nothing if the sign-in is broken.** An expired cookie is turned away
  everywhere, which made every "must refuse" cell look fine. A role's refusals now count only
  if that role was seen to get through on at least one route the table allows it.

After the fixes, on the unmodified application: 10 cells, 9 hold, none broken, nothing
reported. The tenth is a form posted with no fields, which the application turns down as
incomplete; it has no API spec to build the form from, so that cell is not run.

Then with a fault planted in a copy:

- **Sign-in and the author check removed from the delete route.** The agent confirms the hole
  by a request (an anonymous delete is carried out) and lists it once.
- **Only the sign-in decorator removed.** This is not a working hole: the route's own author
  check then crashes for a visitor, and the server answers 500. The agent reports the cell as
  not run because the server failed, and confirms nothing. That is the right answer, and it
  was not planned: the first version of this trial expected a confirmed fault here.

`python trials/live_flask.py` repeats all three runs and compares them with this record. It
runs in CI on every change.

## The second live trial: API tokens, an admin role and a real database

Also on 2026-11-22, the agent was run against the FastAPI full-stack template's backend at
the pinned commit: started on the local machine with PostgreSQL, three accounts (two users
and an administrator), and a permissions table of 23 routes by three roles, 69 cells.

The application is correct, so every problem below was the agent's.

| What happened | Why | Fix |
|---|---|---|
| 26 cells could not be tried | POST, PUT and PATCH were sent with no body, and the application turns those down as incomplete (422) | Bodies are built from the application's API spec: the smallest value each schema accepts (`request_bodies.py`). The spec comes from `--spec`, the source, or the running test environment |
| A request turned down as incomplete was read as "let through" | 400 and 422 were not recognised | They now count as nothing shown, like "not found" |
| One id did not fit every path | Items, users and email addresses each need their own | `PATH_IDS="id=…,user_id=…,email=…"` names an id for each parameter |
| "A user may delete their own account" ran early, and every later cell for that user answered "not found" | Cells ran in table order | Cells that could destroy the test data run last, and an administrator's delete is aimed at another user's row when one is supplied |
| **A real hole was reported as cleared** | See below | Refusals are also tried against another user's row |

The last one is the serious one, and it only showed with a fault planted. With the
administrator check removed from "delete a user", any signed-in user could delete any other.
The agent tried the refusal with the caller's own id, the application answered 403 because
it does not let anyone delete themselves through that route, and the agent recorded the
refusal as holding. It then **cleared the source audit's correct suspicion** that the route
showed no role check. A wrong "cleared" is worse than a false alarm: it tells the reader a
real hole is not there.

Two changes:

- With `OTHER_PATH_IDS` (ids of rows that belong to a different user), each refusal on a
  route with an id is tried against both rows. The planted hole is then found: "user should be
  refused, but got 200 for a row that belongs to someone else".
- Without it, a refusal seen with one id is still shown as holding, but it **no longer clears
  a suspicion**, and the report says which variable to set.

Results after the fixes, with writes allowed on the test database:

| | Cells that hold | Broken | Not run |
|---|---|---|---|
| The application as it is | 49 | 0 | 20 |
| With two faults planted (admin check off "delete a user"; owner check off "read an item") | 47 | 1 | 21 |

On the faulty copy the owner-check fault is confirmed by a finding test ("gave one user
another user's row: 200") and the admin-check fault by a broken cell. The cells not run are
honest ones: routes that need a mail server, a correct current password or a valid reset
token, none of which the agent has.

This trial is not in CI: it needs PostgreSQL and Python 3.14. The behaviours it exposed are
each reproduced by a small stand-in server in `test_request_bodies.py`.

## The generated test suites, on the same two applications

`python cli.py automate` writes a suite for a team to keep (`docs/automation.md`). On
2026-11-23 it was run against both applications as they are.

- **FastAPI template:** 47 backend tests for 23 operations, from the spec the application
  serves. 23 pass and 23 are skipped with a reason (another role needed, a body the
  application turned down, no mail server). One fails: `POST /api/v1/private/users/` answers
  500 when the address already exists, where its spec documents 200 and 422. That is a real
  fault in the application, on a route meant for local use.
- **Flask tutorial application:** it has no API spec, so no backend test is written. 7 page
  tests and 1 journey, all passing; the journey writes a post through the page and finds it
  in the backend.

Three things were wrong on the first run and fixed before these numbers:

- A missing favicon was reported as a page error. It is not one.
- The test user being turned away from an administrator's operation (403, which the spec
  leaves out) was a failure. It is now a skip: it says the user lacks the role, nothing more.
- A request the application turned down as invalid, with a status the spec does not document,
  was a failure. The body came from us, so it is now a skip.

## What these trials do not show

- **Three applications, all small and well kept.** Larger and messier code will expose more.
- **The planted faults were chosen by the person who wrote the audit.** They are the kinds
  of fault it was built to find. An outsider's list would score lower.
- **Two applications have been run, both small and well kept.** One Flask application with
  cookie sign-in, one FastAPI application with tokens and an admin role. Neither has CSRF
  protection, multi-step sign-in or more than two roles. The browser check has not been used
  on a real application.
- **No requirements document.** None of these projects has one, so the requirements checks
  are still untested on real material.

## What to take from it

The gap between "works on our sample" and "works on real code" was large: 17 findings with
16 false on the first application, then 18 findings with 17 false on the next two. Each
round on real code removed a class of false alarm that no amount of work on the sample
would have shown. The same held the first time anything was run: five false alarms out of
five, from three causes. And the second application run showed a wrong "cleared", which no
false-alarm count would have revealed.

Next: Django, request shapes through generated clients, query builders in JavaScript
(Knex, Sequelize, TypeORM), and a real requirements document.
