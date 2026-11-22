"""Request bodies from the API spec, and what the second live trial (FastAPI on PostgreSQL) showed."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import agent
import permissions
import request_bodies

SPEC = {
    "openapi": "3.1.0",
    "paths": {
        "/api/v1/users/signup": {"post": {"requestBody": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/UserRegister"}}}}}},
        "/api/v1/login": {"post": {"requestBody": {"content": {"application/x-www-form-urlencoded": {
            "schema": {"$ref": "#/components/schemas/Login"}}}}}},
        "/api/v1/items/{item_id}": {
            "put": {"requestBody": {"content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/Item"}}}}},
            "delete": {},
            "get": {},
        },
        "/api/v1/odd": {"post": {"requestBody": {"content": {"text/plain": {"schema": {"type": "string"}}}}}},
    },
    "components": {"schemas": {
        "UserRegister": {"type": "object", "required": ["email", "password"], "properties": {
            "email": {"type": "string", "format": "email", "maxLength": 255},
            "password": {"type": "string", "minLength": 20, "maxLength": 128},
            "full_name": {"anyOf": [{"type": "string"}, {"type": "null"}]}}},
        "Login": {"type": "object", "required": ["username", "password", "grant_type"], "properties": {
            "grant_type": {"anyOf": [{"type": "string", "pattern": "^password$"}, {"type": "null"}]},
            "username": {"type": "string"}, "password": {"type": "string", "format": "password"}}},
        "Item": {"type": "object", "required": ["title", "count", "tags", "kind", "owner", "done", "ref"],
                 "properties": {
                     "title": {"type": "string", "maxLength": 5}, "count": {"type": "integer", "minimum": 3},
                     "tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                     "kind": {"enum": ["book", "tool"]}, "owner": {"$ref": "#/components/schemas/Owner"},
                     "done": {"type": "boolean"}, "ref": {"type": "string", "format": "uuid"},
                     "note": {"type": "string"}}},
        "Owner": {"allOf": [{"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
                            {"type": "object", "required": ["since"],
                             "properties": {"since": {"type": "string", "format": "date"}}}]},
    }},
}


def test_the_smallest_body_the_spec_accepts():
    bodies = request_bodies.from_spec(SPEC)
    assert set(bodies) == {"POST /api/v1/users/signup", "POST /api/v1/login", "PUT /api/v1/items/{item_id}"}
    # Required fields only, each with the plainest value its type and format allow.
    assert bodies["POST /api/v1/users/signup"] == {"json": {
        "email": "audit-probe@example.com", "password": "audit-probeaudit-pro"}}
    assert len(bodies["POST /api/v1/users/signup"]["json"]["password"]) == 20
    # A form is sent as a form; a pattern that is one fixed word gives that word.
    assert bodies["POST /api/v1/login"] == {"data": {
        "username": "audit-probe", "password": "Audit-probe-pw-1", "grant_type": "password"}}
    assert bodies["PUT /api/v1/items/{item_id}"]["json"] == {
        "title": "audit", "count": 4, "tags": ["audit-probe"], "kind": "book",
        "owner": {"id": 1, "since": "2026-01-01"}, "done": False,
        "ref": "00000000-0000-4000-8000-000000000000"}
    assert request_bodies.from_spec(SPEC) == bodies, "the same spec always gives the same bodies"


def test_a_body_is_found_whatever_the_parameter_is_called():
    bodies = request_bodies.from_spec(SPEC)
    for path in ("/api/v1/items/{id}", "/api/v1/items/<int:id>", "/api/v1/items/:id", "/items/{x}"):
        assert request_bodies.find(bodies, "PUT", path) is not None, path
    assert request_bodies.find(bodies, "put", "/api/v1/items/{id}") is not None
    assert request_bodies.find(bodies, "POST", "/api/v1/items/{id}") is None
    assert request_bodies.find(bodies, "PUT", "/api/v1/things/{id}") is None
    assert request_bodies.find(None, "PUT", "/x") is None and request_bodies.find({}, "PUT", "/x") is None


def test_specs_it_cannot_follow_give_no_body_and_no_crash(tmp_path):
    loop = {"paths": {"/a": {"post": {"requestBody": {"content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/A"}}}}}}},
        "components": {"schemas": {"A": {"type": "object", "required": ["a"],
                                         "properties": {"a": {"$ref": "#/components/schemas/A"}}}}}}
    assert isinstance(request_bodies.from_spec(loop)["POST /a"]["json"], dict)
    for junk in ({}, {"paths": []}, {"paths": {"/a": "x"}}, {"paths": {"/a": {"post": "x"}}},
                 {"paths": {"/a": {"post": {"requestBody": {"content": {"application/json": {
                     "schema": {"$ref": "#/nowhere"}}}}}}}}, None, "text"):
        assert request_bodies.from_spec(junk) in ({}, {"POST /a": {"json": {}}})
    swagger = {"swagger": "2.0", "basePath": "/v2", "paths": {"/pets": {"post": {"parameters": [
        {"in": "body", "schema": {"type": "object", "required": ["name"],
                                  "properties": {"name": {"type": "string"}}}}]}}}}
    assert request_bodies.from_spec(swagger) == {"POST /v2/pets": {"json": {"name": "audit-probe"}}}
    file = tmp_path / "openapi.json"
    file.write_text(json.dumps(SPEC))
    assert request_bodies.load(str(file))[0]["openapi"] == "3.1.0"
    assert request_bodies.load(str(tmp_path / "missing.json"))[0] is None
    (tmp_path / "bad.yaml").write_text("paths: [")
    spec, why = request_bodies.load(str(tmp_path / "bad.yaml"))
    assert spec is None and "not an API spec" in why


# ── A site that behaves the way the FastAPI template did ─────────────────────

SOURCE = (
    "@router.get('/api/items/{id}')\n"
    "def read_item(id, user=Depends(current_user)):\n    return {}\n"
    "@router.post('/api/items/')\n"
    "def create_item(user=Depends(current_user)):\n    return {}\n"
    "@router.delete('/api/users/me')\n"
    "def delete_me(user=Depends(current_user)):\n    return {}\n"
    "@router.delete('/api/users/{user_id}')\n"
    "def delete_user(user_id, user=Depends(current_user)):\n    return {}\n"   # the fault: no admin check
)
TABLE = (
    "roles: [anonymous, user, admin]\nrules:\n"
    "  - {route: 'DELETE /api/users/me', allow: [user]}\n"
    "  - {route: 'GET /api/items/{id}', allow: [user, admin]}\n"
    "  - {route: 'POST /api/items/', allow: [user, admin]}\n"
    "  - {route: 'DELETE /api/users/{user_id}', allow: [admin]}\n"
)
API = {"openapi": "3.1.0", "paths": {"/api/items/": {"post": {"requestBody": {"content": {"application/json": {
    "schema": {"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}}}}}}}}}}


class _Api(BaseHTTPRequestHandler):
    hole = True
    users = set()
    bodies = []

    def _reply(self, code):
        self.send_response(code)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def _answer(self):
        if self.command == "GET" and self.path == "/openapi.json":
            data = json.dumps(API).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        who = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if who not in ("alice", "root"):
            return self._reply(401)
        if who not in _Api.users:
            return self._reply(404)                      # the account no longer exists
        if self.path == "/api/items/":
            try:
                body = json.loads(raw or b"null")
            except ValueError:
                body = None
            if not isinstance(body, dict) or "title" not in body:
                return self._reply(422)                  # incomplete, before anything else is decided
            _Api.bodies.append(body)
            return self._reply(200)
        if self.path == "/api/users/me":
            if who == "root":
                return self._reply(403)
            _Api.users.discard(who)
            return self._reply(200)
        if self.path.startswith("/api/users/"):
            target = self.path.rsplit("/", 1)[1]
            if target == who:
                return self._reply(403)                  # "you cannot delete yourself"
            if who != "root" and not _Api.hole:
                return self._reply(403)
            _Api.users.discard(target)
            return self._reply(200)
        if self.path.startswith("/api/items/"):
            return self._reply(200)
        self._reply(404)

    do_GET = do_POST = do_DELETE = _answer  # noqa: N815

    def log_message(self, *args):
        pass


@pytest.fixture
def api(tmp_path, monkeypatch):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "routes.py").write_text(SOURCE)
    _Api.hole, _Api.users, _Api.bodies = True, {"alice", "root", "bob"}, []
    httpd = HTTPServer(("127.0.0.1", 0), _Api)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("ROLE_USER_TOKEN", "alice")
    monkeypatch.setenv("ROLE_ADMIN_TOKEN", "root")
    monkeypatch.setenv("PATH_IDS", "user_id=alice,id=1")
    monkeypatch.delenv("OTHER_PATH_IDS", raising=False)
    yield agent.Config(path=str(folder), policy=permissions.load(TABLE), browse=False, allow_writes=True,
                       url=f"http://127.0.0.1:{httpd.server_port}")
    httpd.shutdown()
    httpd.server_close()


def _cells(run):
    return {(c.role, c.method, c.path): (c.verdict, c.evidence) for c in run.cells}


def test_a_refusal_for_your_own_row_does_not_clear_a_suspicion(api):
    """The route refuses a user deleting themselves, which hid that they could delete anyone else."""
    run = agent.run(api)
    cells = _cells(run)
    assert cells[("user", "DELETE", "/api/users/{user_id}")] == ("holds", "refused")
    # Tried with one id only: the suspicion from the source is NOT cleared, and the report says why.
    suspicion = "DELETE /api/users/{user_id} must refuse user, but no role check is visible"
    assert suspicion not in [f.title for f in run.cleared]
    assert suspicion in [i.title for i in run.report.items]
    assert any("OTHER_PATH_IDS" in line for line in run.needs_person)
    assert "bob" in _Api.users


def test_with_another_users_id_the_hole_is_found(api, monkeypatch):
    monkeypatch.setenv("OTHER_PATH_IDS", "user_id=bob")
    run = agent.run(api)
    verdict, evidence = _cells(run)[("user", "DELETE", "/api/users/{user_id}")]
    assert verdict == "broken" and "for a row that belongs to someone else" in evidence
    assert [i.title for i in run.report.items if i.group == "wrong_now"] == [
        "user can call DELETE /api/users/{user_id}, which the permissions table refuses them"]
    assert "bob" not in _Api.users, "the hole is real: the request took effect"

    _Api.hole, _Api.users = False, {"alice", "root", "bob"}
    fixed = agent.run(api)
    assert _cells(fixed)[("user", "DELETE", "/api/users/{user_id}")] == (
        "holds", "refused, for its own row and for another user's")
    assert "DELETE /api/users/{user_id} must refuse user, but no role check is visible" in [
        f.title for f in fixed.cleared]


def test_requests_carry_the_body_the_spec_describes(api):
    _Api.hole = False
    run = agent.run(api)
    step = next(s for s in run.steps if s.name == "Find request bodies")
    assert step.status == "done" and "1 operation(s) take a body" in step.detail and "/openapi.json" in step.detail
    cells = _cells(run)
    assert cells[("user", "POST", "/api/items/")][0] == "holds"
    assert _Api.bodies and all(b == {"title": "audit-probe"} for b in _Api.bodies)


def test_without_a_spec_an_incomplete_request_shows_nothing(api, tmp_path):
    _Api.hole = False
    api.spec = str(tmp_path / "none.json")           # a spec that cannot be read: no bodies
    run = agent.run(api)
    assert next(s for s in run.steps if s.name == "Find request bodies").status == "not run"
    verdict, evidence = _cells(run)[("user", "POST", "/api/items/")]
    assert verdict == "not run" and "incomplete or invalid (422)" in evidence
    assert _Api.bodies == []


def test_cells_that_destroy_the_account_run_last(api, monkeypatch):
    """`a user may delete their own account` is first in the table. Run first, it would leave every
    later cell for that user answering "not found"."""
    _Api.hole = False
    monkeypatch.setenv("OTHER_PATH_IDS", "user_id=bob")
    run = agent.run(api)
    cells = _cells(run)
    # The administrator's delete is aimed at the other user's row, so the caller's own account is
    # still there when its turn comes to delete itself.
    assert cells[("admin", "DELETE", "/api/users/{user_id}")][0] == "holds" and "bob" not in _Api.users
    assert cells[("user", "DELETE", "/api/users/me")][0] == "holds"
    assert cells[("user", "GET", "/api/items/{id}")][0] == "holds"
    assert cells[("user", "POST", "/api/items/")][0] == "holds"
    text = permissions.tests(api.policy)
    order = [text.index(name) for name in ("def test_user_may_get_api_items_id", "def test_user_may_post_api_items",
                                           "def test_admin_may_delete_api_users_user_id",
                                           "def test_user_may_delete_api_users_me")]
    assert order == sorted(order)
