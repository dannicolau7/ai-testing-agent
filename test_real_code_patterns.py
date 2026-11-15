"""Ways real FastAPI projects are written that the first readers missed.

Each case here was found by running the audit on an open-source application
(see docs/real-code-trial.md). The fixtures are written for this test, not copied.
"""

import app_audit
import permissions


def _write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


PROJECT = {
    "backend/app/core/config.py": "class Settings:\n    API_PREFIX: str = '/api/v2'\nsettings = Settings()\n",
    "backend/app/deps.py": (
        "from typing import Annotated\n"
        "def get_db(): ...\n"
        "def get_current_user(): ...\n"
        "def get_current_active_superuser(): ...\n"
        "SessionDep = Annotated[Session, Depends(get_db)]\n"
        "CurrentUser = Annotated[User, Depends(get_current_user)]\n"
        # Python 3.14 syntax: older interpreters refuse the whole file for this line.
        "def check():\n    try:\n        pass\n    except KeyError, ValueError:\n        pass\n"
    ),
    "backend/app/models.py": (
        "class NoteBase(SQLModel):\n"
        "    title: str = Field(max_length=100)\n"
        "    slug: str = Field(unique=True)\n"
        "class NoteCreate(NoteBase):\n"
        "    pass\n"
        "class User(SQLModel, table=True):\n"
        "    id: int = Field(primary_key=True)\n"
        "    email: str = Field(unique=True)\n"
        "    notes: list['Note'] = Relationship(back_populates='owner')\n"
        "class Note(NoteBase, table=True):\n"
        "    __tablename__ = 'notes'\n"
        "    id: int = Field(primary_key=True)\n"
        "    owner_id: int = Field(foreign_key='user.id', nullable=False)\n"
        "    body: str | None = None\n"
        "    owner: User | None = Relationship(back_populates='notes')\n"
    ),
    "backend/app/crud.py": (
        "def create_note(*, session, note_in, owner_id):\n"
        "    db_note = Note.model_validate(note_in, update={'owner_id': owner_id})\n"
        "    session.add(db_note)\n"
        "    return db_note\n"
    ),
    "backend/app/routes/notes.py": (
        "router = APIRouter(prefix='/notes', tags=['notes'])\n"
        "@router.get('/')\n"
        "def read_notes(session: SessionDep, current_user: CurrentUser):\n"
        "    return session.exec(select(Note).where(Note.owner_id == current_user.id)).all()\n"
        "@router.get('/{id}')\n"
        "def read_note(session: SessionDep, current_user: CurrentUser, id: int):\n"
        "    return session.get(Note, id)\n"
        "@router.post('/')\n"
        "def create_note(session: SessionDep, current_user: CurrentUser, note_in: NoteCreate):\n"
        "    return crud.create_note(session=session, note_in=note_in, owner_id=current_user.id)\n"
        "@router.delete('/{id}')\n"
        "def delete_note(session: SessionDep, current_user: CurrentUser, id: int):\n"
        "    note = session.get(Note, id)\n"
        "    if note.owner_id != current_user.id:\n"
        "        raise HTTPException(403)\n"
        "    session.delete(note)\n"
    ),
    "backend/app/routes/admin.py": (
        "router = APIRouter(prefix='/admin', dependencies=[Depends(get_current_active_superuser)])\n"
        "@router.post('/purge')\n"
        "def purge(session: SessionDep): ...\n"
    ),
    "backend/app/routes/login.py": (
        "router = APIRouter()\n"
        "@router.post('/login/access-token')\n"
        "def login(session: SessionDep): ...\n"
        "@router.post('/users/signup')\n"
        "def register_user(session: SessionDep): ...\n"
        "@router.patch('/me')\n"
        "def update_me(session: SessionDep, current_user: CurrentUser):\n"
        "    session.add(current_user)\n"
        "@router.post('/feedback')\n"
        "def feedback(session: SessionDep): ...\n"
    ),
    "backend/app/api.py": (
        "from app.routes import admin, login, notes\n"
        "api_router = APIRouter()\n"
        "api_router.include_router(notes.router)\n"
        "api_router.include_router(admin.router)\n"
        "api_router.include_router(login.router)\n"
    ),
    "backend/app/main.py": "app = FastAPI()\napp.include_router(api_router, prefix=settings.API_PREFIX)\n",
    "backend/app/alembic/versions/001_init.py": "@app.post('/only-in-a-migration')\ndef x(): ...\n",
    "backend/tests/conftest.py": "@app.post('/only-in-tests')\ndef y(): ...\n",
    "frontend/src/client/sdk.gen.ts": (
        "export class NotesService {\n"
        "  public static readNotes<T extends boolean = true>(options?: Options<ReadData, T>) {\n"
        "    return (options?.client ?? client).get<Responses, Errors, T>({\n"
        "      responseType: 'json',\n      url: '/api/v2/notes/',\n      ...options\n    });\n  }\n"
        "  public static deleteNote(options) {\n"
        "    return (options?.client ?? client).delete({ url: '/api/v2/notes/{id}', ...options });\n  }\n"
        "  public static ghost(options) {\n"
        "    return __request(OpenAPI, { method: 'PUT', url: '/api/v2/notes/{id}/archive' });\n  }\n"
        "}\n"
    ),
}


def _model(tmp_path):
    _write(tmp_path, PROJECT)
    return app_audit.build_model(str(tmp_path))


def test_router_prefixes_are_applied_through_every_include(tmp_path):
    model = _model(tmp_path)
    assert model.files_skipped == [], "a file with newer syntax is still read"
    assert sorted(f"{r.method} {r.path}" for r in model.routes) == [
        "DELETE /api/v2/notes/{id}", "GET /api/v2/notes/", "GET /api/v2/notes/{id}", "PATCH /api/v2/me",
        "POST /api/v2/admin/purge", "POST /api/v2/feedback", "POST /api/v2/login/access-token",
        "POST /api/v2/notes/", "POST /api/v2/users/signup",
    ], "migrations and test folders are not application routes"


def test_access_checks_are_seen_through_aliases_and_router_dependencies(tmp_path):
    evidence = {f"{r.method} {r.path}": r.auth_evidence for r in _model(tmp_path).routes}
    assert evidence["GET /api/v2/notes/"] == ["Depends(get_current_user)"], "current_user: CurrentUser"
    assert evidence["POST /api/v2/admin/purge"] == ["Depends(get_current_active_superuser)"], "APIRouter(dependencies=...)"
    assert evidence["POST /api/v2/feedback"] == [], "a session dependency is not an access check"


def test_sqlmodel_tables_and_their_inherited_columns_are_read(tmp_path):
    tables = {t.name: {c.name: c for c in t.columns} for t in _model(tmp_path).tables}
    assert set(tables) == {"user", "notes"}, "only classes with table=True; __tablename__ wins"
    notes = tables["notes"]
    assert set(notes) == {"title", "slug", "id", "owner_id", "body"}, "base columns, and no relationship"
    assert notes["id"].primary_key and notes["slug"].unique and notes["owner_id"].foreign_key == "user.id"
    assert notes["body"].nullable and not notes["owner_id"].nullable


def test_data_access_is_followed_through_model_variables_and_module_calls(tmp_path):
    seen = {f"{r.method} {r.path}": sorted({(a.kind, a.table) for a in r.data.accesses}) for r in _model(tmp_path).routes}
    assert seen["GET /api/v2/notes/"] == [("read", "notes")]
    assert seen["POST /api/v2/notes/"] == [("write", "notes")], "crud.create_note, though the handler has the same name"
    assert seen["DELETE /api/v2/notes/{id}"] == [("read", "notes"), ("write", "notes")], "session.delete(note)"
    assert seen["PATCH /api/v2/me"] == [("write", "user")], "session.add(current_user): CurrentUser is a User"


def test_the_audit_of_this_project_reports_only_what_is_real(tmp_path):
    report = app_audit.audit(_model(tmp_path))
    assert [f.title for f in report.of("wrong_now")] == [
        "The frontend calls PUT /api/v2/notes/{id}/archive, which no backend route defines"]
    likely = [f.title for f in report.of("likely")]
    assert likely == [
        "POST /api/v2/feedback changes data and shows no access check",
        "GET /api/v2/notes/{id} reads `notes` without checking who owns the row",
    ]
    assert any("open by design" in n and "POST /api/v2/login/access-token" in n and "signup" in n
               for n in report.not_examined)


def test_generated_api_clients_are_read_as_frontend_calls(tmp_path):
    calls = sorted((c.method, c.path) for c in _model(tmp_path).calls)
    assert calls == [("DELETE", "/api/v2/notes/{id}"), ("GET", "/api/v2/notes/"), ("PUT", "/api/v2/notes/{id}/archive")]


def test_a_draft_permissions_table_tells_a_required_role_from_a_mentioned_one(tmp_path):
    _write(tmp_path, PROJECT)
    (tmp_path / "backend/app/routes/notes.py").write_text(
        PROJECT["backend/app/routes/notes.py"]
        + "@router.get('/all')\n"
          "def all_notes(session: SessionDep, current_user: CurrentUser):\n"
          "    if not current_user.is_superuser:\n"
          "        raise HTTPException(403)\n")
    model = app_audit.build_model(str(tmp_path))
    policy = permissions.load(permissions.draft(model, ["user", "superuser"]))
    allow = {r.name: r.allow for r in policy.rules}
    assert allow["POST /api/v2/admin/purge"] == ["superuser"], "the route itself requires the role"
    assert allow["GET /api/v2/notes/"] == ["user", "superuser"], "get_current_user means signed in, not a role"
    assert allow["GET /api/v2/notes/all"] == ["user", "superuser"], "mentioned in the handler: left for a person"
    assert "the handler treats superuser differently" in permissions.draft(model, ["user", "superuser"])
    assert allow["POST /api/v2/users/signup"] == ["anonymous", "user", "superuser"]


def test_a_role_the_handler_mentions_in_order_to_refuse_it_is_not_a_fault(tmp_path):
    _write(tmp_path, PROJECT)
    (tmp_path / "backend/app/routes/login.py").write_text(
        PROJECT["backend/app/routes/login.py"]
        + "@router.delete('/me')\n"
          "def delete_me(session: SessionDep, current_user: CurrentUser):\n"
          "    if current_user.is_superuser:\n"
          "        raise HTTPException(403)\n"
          "    session.delete(current_user)\n")
    model = app_audit.build_model(str(tmp_path))
    policy = permissions.load(
        "roles: [user, superuser]\nrules:\n"
        "  - {route: DELETE /api/v2/me, allow: [user]}\n"
        "  - {route: POST /api/v2/admin/purge, allow: [user]}\n")
    titles = [f.title for f in permissions.compare(model, policy)]
    assert not [t for t in titles if "DELETE /api/v2/me" in t]
    assert "POST /api/v2/admin/purge must refuse superuser, but the route requires that role" in titles
    table = "\n".join(permissions.table_markdown(model, policy))
    assert "| DELETE /api/v2/me | refuse | allow | refuse | no | sign-in; the handler mentions superuser |" in table
    assert "| POST /api/v2/admin/purge | refuse | allow | refuse | no | requires superuser |" in table


# ── Found on a Flask application and an Express application ───────────────────

FLASK = {
    "app/schema.sql": (
        "CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL);\n"
        "CREATE TABLE post (\n"
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "  author_id INTEGER NOT NULL,\n"
        "  title TEXT NOT NULL,\n"
        "  FOREIGN KEY (author_id) REFERENCES user (id)\n"
        ");\n"
    ),
    "app/blog.py": (
        "bp = Blueprint('blog', __name__, url_prefix='/blog')\n"
        "def get_post(id, check_author=True):\n"
        "    post = get_db().execute('SELECT p.id, title, author_id FROM post p JOIN user u ON p.author_id = u.id WHERE p.id = ?', (id,)).fetchone()\n"
        "    if check_author and post['author_id'] != g.user['id']:\n"
        "        abort(403)\n"
        "    return post\n"
        "@bp.route('/create', methods=('GET', 'POST'))\n"
        "@login_required\n"
        "def create():\n"
        "    if request.method == 'POST':\n"
        "        get_db().execute('INSERT INTO post (title, author_id) VALUES (?, ?)', (title, g.user['id']))\n"
        "    return render_template('create.html')\n"
        "@bp.route('/<int:id>/update', methods=('GET', 'POST'))\n"
        "@login_required\n"
        "def update(id):\n"
        "    post = get_post(id)\n"
        "    if request.method == 'POST':\n"
        "        get_db().execute('UPDATE post SET title = ? WHERE id = ?', (title, id))\n"
        "@bp.route('/<int:id>/visit')\n"
        "@login_required\n"
        "def visit(id):\n"
        "    get_post(id)\n"
        "    get_db().execute('UPDATE post SET title = ? WHERE id = ?', ('seen', id))\n"
    ),
}


def test_a_flask_handler_shared_by_get_and_post_is_not_a_get_that_writes(tmp_path):
    _write(tmp_path, FLASK)
    report = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert [f.title for f in report.findings] == ["GET /blog/<int:id>/visit changes `post`"], \
        "the GET-only handler that writes is still reported; the shared ones are not"


def test_an_owner_check_written_as_a_dictionary_key_is_seen(tmp_path):
    _write(tmp_path, FLASK)
    with_check = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert not [f for f in with_check.findings if "who owns" in f.title]
    blog = tmp_path / "app/blog.py"
    blog.write_text(blog.read_text().replace(
        "    if check_author and post['author_id'] != g.user['id']:\n        abort(403)\n", ""))
    without = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert "POST /blog/<int:id>/update reads `post` without checking who owns the row" in [f.title for f in without.findings]


EXPRESS = (
    "const router = Router();\n"
    "router.get('/articles', auth.optional, async (req, res, next) => {});\n"
    "router.put(\n"
    "  '/articles/:slug',\n"
    "  auth.required,\n"
    "  async (req: Request, res: Response, next: NextFunction) => {\n"
    "    const token = req.auth;\n"
    "  },\n"
    ");\n"
    "router.delete(\n"
    "  '/articles/:slug',\n"
    "  async (req: Request, res: Response) => { const authorized = true; },\n"
    ");\n"
    "router.post('/articles/:slug/favorite', auth.optional, async (req, res) => {});\n"
)


def test_express_routes_spread_over_lines_keep_their_middleware(tmp_path):
    (tmp_path / "article.controller.ts").write_text(EXPRESS)
    model = app_audit.build_model(str(tmp_path))
    evidence = {f"{r.method} {r.path}": r.auth_evidence for r in model.routes}
    assert evidence == {
        "GET /articles": [], "PUT /articles/:slug": ["auth.required"],
        "DELETE /articles/:slug": [], "POST /articles/:slug/favorite": [],
    }, "optional auth is not an access check, and names inside the handler are not middleware"
    titles = [f.title for f in app_audit.audit(model).findings]
    assert titles == ["DELETE /articles/:slug changes data and shows no access check",
                      "POST /articles/:slug/favorite changes data and shows no access check"]


def test_keys_added_by_a_later_migration_are_read(tmp_path):
    _write(tmp_path, {
        "migrations/001/migration.sql": (
            'CREATE TABLE "User" ("id" SERIAL NOT NULL, "email" TEXT NOT NULL, PRIMARY KEY ("id"));\n'
            'CREATE TABLE "Article" ("id" SERIAL NOT NULL, "authorId" INTEGER NOT NULL, PRIMARY KEY ("id"));\n'
            'CREATE TABLE "_UserFavorites" ("A" INTEGER NOT NULL, "B" INTEGER NOT NULL);\n'
            'CREATE TABLE "Orphan" ("A" INTEGER NOT NULL, "B" INTEGER NOT NULL);\n'
            'CREATE UNIQUE INDEX "User.email_unique" ON "User"("email");\n'
        ),
        "migrations/002/migration.sql": (
            'CREATE UNIQUE INDEX "_UserFavorites_AB_unique" ON "_UserFavorites"("A", "B");\n'
            'ALTER TABLE "Article" ADD FOREIGN KEY ("authorId") REFERENCES "User"("id") ON DELETE CASCADE;\n'
        ),
    })
    model = app_audit.build_model(str(tmp_path))
    tables = {t.name: t for t in model.tables}
    assert tables["_UserFavorites"].keyed and not tables["Orphan"].keyed
    assert {c.name: c.unique for c in tables["User"].columns}["email"]
    assert {c.name: c.foreign_key for c in tables["Article"].columns}["authorId"] == "User"
    assert [f.title for f in app_audit.audit(model).findings] == ["Table Orphan has no primary key"]
