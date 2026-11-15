"""Request and response shapes compared between the layers (roadmap stage 4, third step)."""

import ast

import app_audit
import shapes


def _titles(report, group=None):
    return [f.title for f in report.findings if group is None or f.group == group]


def _models(source):
    return shapes.pydantic_models([("m.py", ast.parse(source))])


def test_pydantic_models_are_read_with_inheritance_and_defaults():
    models = _models(
        "class Base(BaseModel):\n"
        "    id: int\n"
        "class Item(Base):\n"
        "    model_config = {}\n"
        "    name: str\n"
        "    note: Optional[str] = None\n"
        "    tags: List[str] = Field(default_factory=list)\n"
        "    size: int = Field(..., gt=0)\n"
        "    kind: ClassVar[str] = 'x'\n"
        "    _private: int = 0\n"
        "class NotAModel:\n"
        "    name: str\n"
    )
    assert models == {"Base": {"id": True},
                      "Item": {"id": True, "name": True, "note": False, "tags": False, "size": True}}


def test_a_fastapi_handler_declares_body_query_and_response():
    source = (
        "class Item(BaseModel):\n"
        "    name: str\n"
        "@app.post('/items/{item_id}', response_model=List[Item])\n"
        "def save(item_id: int, item: Item, page: int = 1, q: str = Query(...), token: str = Header(None),\n"
        "         db=Depends(get_db), background: BackgroundTasks = None):\n"
        "    ...\n"
        "@app.post('/raw')\n"
        "async def raw(request: Request): ...\n"
        "@login_required\n"
        "def not_a_route(x: int): ...\n"
    )
    tree = ast.parse(source)
    models = shapes.pydantic_models([("a.py", tree)])
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    save = shapes.handler_shape(funcs["save"], "/items/{item_id}", models)
    assert (save.body, save.query, save.response, save.source) == (
        {"name": True}, {"page": False, "q": True}, ["name"], "Item")
    raw = shapes.handler_shape(funcs["raw"], "/raw", models)
    assert raw.body is None and raw.body_open and raw.query is None
    assert shapes.handler_shape(funcs["not_a_route"], "/", models) is None


def test_frontend_bodies_are_read_from_literals_and_typescript_types():
    source = (
        "interface NewItem { name: string; note?: string; 'unit-price': number }\n"
        "type Patch = { name?: string } & Other\n"
        "export const a = (name) => fetch('/items?page=1&q=${q}', {\n"
        "  method: 'POST', body: JSON.stringify({ name, nested: { deep: 1 }, 'quoted-key': [1, 2], fn() {} }) })\n"
        "export const b = (item: NewItem) => axios.post('/items', item)\n"
        "export const c = (rest) => axios.put('/items/1', { ...rest, name: 'x' })\n"
        "export const d = (body) => fetch('/items', { method: 'POST', body: JSON.stringify(body) })\n"
        "export const e = (p: Patch) => fetch('/items/1', { method: 'PATCH', body: JSON.stringify(p) })\n"
    )
    calls = app_audit.js_calls(source, "api.ts")
    shapes.resolve_body_types([c.shape for c in calls], shapes.ts_types(source))
    by = {(c.method, c.path.split("?")[0]): c.shape for c in calls}
    posts = [c.shape for c in calls if c.method == "POST"]   # fetch calls first (a, d), then axios (b)
    assert posts[0].body == {"name": True, "nested": True, "quoted-key": True, "fn": True}
    assert posts[0].query == {"page": True, "q": True}
    assert posts[2].body == {"name": True, "note": False, "unit-price": True} and not posts[2].body_open
    assert posts[1].body is None, "a body passed as an untyped variable is unknown, not empty"
    put = by[("PUT", "/items/1")]
    assert put.body == {"name": True} and put.body_open
    patch = by[("PATCH", "/items/1")]
    assert patch.body == {"name": False} and patch.body_open, "an intersection type may carry more fields"


def test_spec_shapes_follow_references():
    spec = {
        "components": {"schemas": {
            "Base": {"type": "object", "required": ["id"], "properties": {"id": {}}},
            "Item": {"allOf": [{"$ref": "#/components/schemas/Base"},
                               {"type": "object", "properties": {"name": {}}}]},
        }},
    }
    operation = {
        "parameters": [{"name": "q", "in": "query", "required": True}, {"name": "id", "in": "path"}],
        "requestBody": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}}},
        "responses": {"200": {"content": {"application/json": {
            "schema": {"type": "array", "items": {"$ref": "#/components/schemas/Base"}}}}}},
    }
    shape = shapes.operation_shape(operation, {"parameters": [{"name": "page", "in": "query"}]}, spec)
    assert shape.body == {"id": True, "name": False}
    assert shape.query == {"page": False, "q": True} and shape.response == ["id"]
    assert shapes.operation_shape({"responses": {}}, {}, {}).body is None


BACKEND = (
    "class NewItem(BaseModel):\n"
    "    name: str\n"
    "    price: float\n"
    "    note: Optional[str] = None\n"
    "@app.post('/items')\n"
    "def add(item: NewItem, user=Depends(current_user)): ...\n"
    "@app.get('/items')\n"
    "def listing(page: int = 1, user=Depends(current_user)): ...\n"
)


def _report(tmp_path, frontend, backend=BACKEND):
    (tmp_path / "app.py").write_text(backend)
    (tmp_path / "api.ts").write_text(frontend)
    return app_audit.audit(app_audit.build_model(str(tmp_path)))


def test_a_frontend_that_agrees_with_the_backend_is_clean(tmp_path):
    report = _report(tmp_path,
        "interface NewItem { name: string; price: number; note?: string }\n"
        "export const add = (item: NewItem) => fetch('/items', { method: 'POST', body: JSON.stringify(item) })\n"
        "export const list = () => fetch('/items?page=2')\n"
        "export const quick = (name) => axios.post('/items', { name, price: 1 })\n")
    assert _titles(report) == []


def test_missing_and_unknown_fields_between_frontend_and_backend(tmp_path):
    report = _report(tmp_path,
        "export const add = (name) => fetch('/items', { method: 'POST', body: JSON.stringify({ name, colour: 'red' }) })\n"
        "export const list = () => fetch('/items?page=2&limit=5')\n")
    assert _titles(report, "wrong_now") == ["POST /items: the frontend does not send `price`, which the backend requires"]
    assert _titles(report, "likely") == [
        "POST /items: the frontend sends `colour`, which the backend does not accept",
        "GET /items: the frontend sends the query parameter `limit`, which the backend does not read",
    ]


def test_unknown_shapes_are_never_compared(tmp_path):
    # A spread, an untyped variable, a raw-request handler and a Flask route: nothing can be said.
    backend = BACKEND + (
        "@app.post('/raw')\n"
        "async def raw(request: Request, user=Depends(current_user)): ...\n"
        "@bp.route('/flask', methods=['POST'])\n"
        "@login_required\n"
        "def flask_view(): ...\n")
    report = _report(tmp_path,
        "export const a = (rest) => fetch('/items', { method: 'POST', body: JSON.stringify({ ...rest }) })\n"
        "export const b = (body) => fetch('/items', { method: 'POST', body: JSON.stringify(body) })\n"
        "export const c = () => fetch('/raw', { method: 'POST', body: JSON.stringify({ anything: 1 }) })\n"
        "export const d = () => fetch('/flask', { method: 'POST', body: JSON.stringify({ anything: 1 }) })\n"
        "export const e = () => fetch('/items')\n", backend)
    assert _titles(report) == []


def test_spec_and_backend_disagreements(tmp_path):
    (tmp_path / "openapi.yaml").write_text(
        "openapi: 3.0.0\n"
        "paths:\n"
        "  /items:\n"
        "    post:\n"
        "      requestBody:\n"
        "        content:\n"
        "          application/json:\n"
        "            schema:\n"
        "              type: object\n"
        "              required: [name]\n"
        "              properties: {name: {}, note: {}, colour: {}}\n"
        "      responses: {'201': {description: ok}}\n"
        "    get:\n"
        "      parameters:\n"
        "        - {name: page, in: query}\n"
        "        - {name: sort, in: query}\n"
        "      responses: {'200': {description: ok}}\n")
    report = _report(tmp_path, "", BACKEND.replace("price: float", "price: float\n    name2: str = ''"))
    assert _titles(report, "wrong_now") == ["POST /items: the backend requires `price`, which the spec does not list"]
    assert _titles(report, "likely") == [
        "GET /items: the spec lists the query parameter `sort`, which the backend does not read",
        "POST /items: the spec lists `colour`, which the backend does not accept",
    ]
