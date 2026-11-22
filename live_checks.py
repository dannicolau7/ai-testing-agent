"""
live_checks.py — how a generated test reads a server's answer.

Generated tests must stand alone, so this text is copied into each generated file. It lives
here once so the finding tests and the permission tests read answers the same way.

A request is never followed through a redirect, and an answer is one of four things:

    refused   401 or 403, or a redirect to a sign-in page
    through   the request was served: 2xx, or a redirect anywhere else
    absent    404, 405 or 410: the route or the row was not found, which shows nothing
              about who may reach it
    error     5xx: the server failed, which shows nothing either

Found by running against a real application: one that sends an anonymous visitor to its
login page answers 302, and a test that follows the redirect sees the login page's 200 and
calls that "let through".
"""

HELPERS = r'''
PARAMETER = r"\{[^}]*\}|<[^>]*>|:[A-Za-z_][A-Za-z0-9_]*"
SIGN_IN = re.compile(os.environ.get("SIGN_IN_PATH") or r"log[-_]?in|sign[-_]?in|sign[-_]?on|sso|authorize", re.I)


def _answer(response):
    """refused | through | absent | error. See live_checks.py in the tool that wrote this file."""
    code = response.status_code
    if code in (401, 403):
        return "refused"
    if 300 <= code < 400:
        return "refused" if SIGN_IN.search(response.headers.get("Location", "")) else "through"
    if code in (404, 405, 410):
        return "absent"
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
    if kind == "error":
        pytest.skip("the server failed with " + _said(response) + ", which shows nothing about access")


def _credentials(token, cookie):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if cookie:
        headers["Cookie"] = cookie
    return headers
'''
