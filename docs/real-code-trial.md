# First trial on a real application

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

## What to take from it

The gap between "works on our sample" and "works on real code" was large, and one run
on one real project closed more of it than more work on the sample would have.
The next real application should be one we have not seen, in a different style: Flask or
Django, or an Express backend.
