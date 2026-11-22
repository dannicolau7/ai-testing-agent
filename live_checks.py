"""
live_checks.py — how a generated test reads a server's answer.

Generated tests must stand alone, so this text is copied into each generated file. It lives
here once so the finding tests and the permission tests read answers the same way.

A request is never followed through a redirect, and an answer is one of five things:

    refused   401 or 403, or a redirect to a sign-in page
    through   the request was served: 2xx, or a redirect anywhere else
    absent    404, 405 or 410: the route or the row was not found, which shows nothing
              about who may reach it
    unfinished 400, 409, 415 or 422: the request was turned down as incomplete. These tests
              send no body, and a framework may reject that before or after the access
              check, so it shows nothing either
    error     5xx: the server failed, which shows nothing either

Found by running against a real application: one that sends an anonymous visitor to its
login page answers 302, and a test that follows the redirect sees the login page's 200 and
calls that "let through".
"""

PARAMETER = r"\{[^}]*\}|<[^>]*>|:[A-Za-z_][A-Za-z0-9_]*"

HELPERS = r'''
PARAMETER = r"\{[^}]*\}|<[^>]*>|:[A-Za-z_][A-Za-z0-9_]*"
PATH_IDS = dict(pair.split("=", 1) for pair in os.environ.get("PATH_IDS", "").split(",") if "=" in pair)
OTHER_IDS = dict(pair.split("=", 1) for pair in os.environ.get("OTHER_PATH_IDS", "").split(",") if "=" in pair)
SIGN_IN = re.compile(os.environ.get("SIGN_IN_PATH") or r"log[-_]?in|sign[-_]?in|sign[-_]?on|sso|authorize", re.I)


def _answer(response):
    """refused | through | absent | unfinished | error. See live_checks.py in the tool that wrote this file."""
    code = response.status_code
    if code in (401, 403):
        return "refused"
    if 300 <= code < 400:
        return "refused" if SIGN_IN.search(response.headers.get("Location", "")) else "through"
    if code in (404, 405, 410):
        return "absent"
    if code in (400, 409, 415, 422):
        return "unfinished"
    if code >= 500:
        return "error"
    return "through"


def _said(response):
    """The answer in words, for a failure or skip message."""
    where = response.headers.get("Location", "")
    return str(response.status_code) + (" to " + where if 300 <= response.status_code < 400 and where else "")


def _nothing_shown(response, id_variable):
    """Skip when the answer says nothing about who may reach the route."""
    kind = _answer(response)
    if kind == "absent":
        pytest.skip("the server answered " + _said(response) + ": the route or the row was not found, so this "
                    "shows nothing. If the path has an id, set " + id_variable + " to one that exists")
    if kind == "unfinished":
        pytest.skip("the server turned the request down as incomplete or invalid (" + _said(response) + "), so it "
                    "may never have reached the access check: this shows nothing. A body is sent only when "
                    "the API spec describes one")
    if kind == "error":
        pytest.skip("the server failed with " + _said(response) + ", which shows nothing about access")


def _fill(path, default, ids=None):
    """Put an id in each path parameter: its own from PATH_IDS (name=value,name=value), else the default."""
    ids = PATH_IDS if ids is None else ids
    def one(match):
        name = re.sub(r"^.*:", "", match.group(0).strip("{}<>:"))
        return ids.get(name, PATH_IDS.get(name, default))
    return re.sub(PARAMETER, one, path)


def _others_row(path):
    """True when the path has a parameter and an id belonging to someone else was supplied for it."""
    names = [re.sub(r"^.*:", "", m.strip("{}<>:")) for m in re.findall(PARAMETER, path)]
    return any(name in OTHER_IDS for name in names)


def _body(method, path):
    """Keyword arguments that send the body the API spec describes for this route, if any."""
    return dict(BODIES.get(method + " " + path) or {})


def _credentials(token, cookie, scheme=None):
    headers = {}
    if token:
        headers["Authorization"] = (scheme or "Bearer") + " " + token
    if cookie:
        headers["Cookie"] = cookie
    return headers
'''
