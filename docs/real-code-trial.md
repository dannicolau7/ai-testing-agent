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

## What these trials do not show

- **Three applications, all small and well kept.** Larger and messier code will expose more.
- **The planted faults were chosen by the person who wrote the audit.** They are the kinds
  of fault it was built to find. An outsider's list would score lower.
- **Nothing was run.** No application was started, so the browser check and the generated
  permission tests were not used.
- **No requirements document.** None of these projects has one, so the requirements checks
  are still untested on real material.

## What to take from it

The gap between "works on our sample" and "works on real code" was large: 17 findings with
16 false on the first application, then 18 findings with 17 false on the next two. Each
round on real code removed a class of false alarm that no amount of work on the sample
would have shown.

Next: Django, request shapes through generated clients, query builders in JavaScript
(Knex, Sequelize, TypeORM), and a real requirements document.
