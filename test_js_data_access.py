"""What a JavaScript or TypeScript handler reads and writes."""

import app_audit
import data_access
import js_data_access

SERVICE = (
    "import prisma from './prisma-client';\n"
    "export const getNote = async (id: number) => {\n"
    "  return prisma.note.findUnique({ where: { id }, select: { title: true, author: { select: { id: true } } } });\n"
    "};\n"
    "export const deleteNote = async (id: number, userId: number): Promise<void> => {\n"
    "  const note = await prisma.note.findFirst({ where: { id } });\n"
    "  if (note.authorId !== userId) {\n"
    "    throw new HttpException(403, {});\n"
    "  }\n"
    "  await prisma.note.delete({ where: { id } });\n"
    "};\n"
    "export async function renameNote(id, title) {\n"
    "  await prisma.note.update({ where: { id }, data: { title } });\n"
    "}\n"
    "export const likeNote = async (id, userId) => {\n"
    "  await prisma.note.update({ where: { id }, data: { likedBy: { connect: { id: userId } } } });\n"
    "};\n"
    "function rawCount(db) {\n"
    "  return db.query('select count(*) from note where archived = $1', [false]);\n"
    "}\n"
    "const search = async (db, term) => db.query(`SELECT id FROM note WHERE title LIKE '%${term}%'`);\n"
)
CONTROLLER = (
    "const router = Router();\n"
    "router.get('/notes/:id', auth.required, async (req, res) => { res.json(await getNote(req.params.id)); });\n"
    "router.delete(\n  '/notes/:id',\n  auth.required,\n  async (req, res) => {\n    await deleteNote(req.params.id, req.auth.user.id);\n  },\n);\n"
    "router.put('/notes/:id', auth.required, async (req, res) => { await renameNote(req.params.id, req.body.title); });\n"
    "router.post('/notes/:id/like', auth.required, async (req, res) => { await likeNote(req.params.id, req.auth.user.id); });\n"
    "router.get('/public/notes/:id', async (req, res) => { res.json(await getNote(req.params.id)); });\n"
    "router.get('/search', auth.required, async (req, res) => { res.json(await search(db, req.query.q)); });\n"
)
SCHEMA = (
    'CREATE TABLE "User" ("id" SERIAL PRIMARY KEY);\n'
    'CREATE TABLE "Note" ("id" SERIAL PRIMARY KEY, "title" TEXT, "authorId" INTEGER NOT NULL REFERENCES "User"("id"));\n'
)


def _model(tmp_path, service=SERVICE):
    (tmp_path / "note.service.ts").write_text(service)
    (tmp_path / "note.controller.ts").write_text(CONTROLLER)
    (tmp_path / "migration.sql").write_text(SCHEMA)
    return app_audit.build_model(str(tmp_path))


def test_functions_are_indexed_whatever_way_they_are_written():
    index = js_data_access.index_functions([("s.ts", SERVICE)])
    assert set(index) >= {"getNote", "deleteNote", "renameNote", "likeNote", "rawCount"}
    assert "prisma.note.delete" in index["deleteNote"][0][1] and index["deleteNote"][0][2] == 5
    assert "prisma.note.update" in index["renameNote"][0][1]


def test_prisma_calls_and_sql_strings_are_read(tmp_path):
    model = _model(tmp_path)
    seen = {f"{r.method} {r.path}": sorted({(a.kind, a.table) for a in r.data.accesses}) for r in model.routes}
    assert seen == {
        "GET /notes/:id": [("read", "Note")],
        "DELETE /notes/:id": [("read", "Note"), ("write", "Note")],
        "PUT /notes/:id": [("write", "Note")],
        "POST /notes/:id/like": [("write", "Note")],
        "GET /public/notes/:id": [("read", "Note")],
        "GET /search": [],
    }, "a Prisma model is matched to its table whatever the case; an arrow function with no braces is not followed"
    data = js_data_access.handler_data("{ rawCount(db); }", "x.ts", 1, js_data_access.index_functions([("s.ts", SERVICE)]))
    assert [(a.kind, a.table, a.filters) for a in data.accesses] == [("read", "note", ["archived"])]


def test_ownership_needs_a_comparison_or_a_filter_not_a_mention(tmp_path):
    report = app_audit.audit(_model(tmp_path))
    titles = [f.title for f in report.findings if "who owns" in f.title]
    assert titles == [
        "GET /notes/:id reads `Note` without checking who owns the row",
        "PUT /notes/:id changes `Note` without checking who owns the row",
    ], ("getNote selects the author but never compares it; deleteNote compares authorId; "
        "liking is an action on someone else's row; the public route needs no sign-in")
    detail = [f.detail for f in report.findings if "who owns" in f.title][0]
    assert "compares it or filters on it" in detail

    # Take the comparison out of deleteNote and it is reported too.
    broken = SERVICE.replace("  if (note.authorId !== userId) {\n    throw new HttpException(403, {});\n  }\n", "")
    other = tmp_path / "other"
    other.mkdir()
    titles = [f.title for f in app_audit.audit(_model(other, broken)).findings if "who owns" in f.title]
    assert "DELETE /notes/:id reads `Note` without checking who owns the row" in titles


def test_a_filter_on_the_owner_or_a_guard_function_is_accepted(tmp_path):
    filtered = SERVICE.replace("prisma.note.update({ where: { id }, data: { title } })",
                               "prisma.note.update({ where: { id, authorId: userId }, data: { title } })")
    guarded = SERVICE.replace("export async function renameNote(id, title) {\n",
                              "export async function renameNote(id, title) {\n  await ensureOwner(id);\n")
    for index, service in enumerate((filtered, guarded)):
        folder = tmp_path / str(index)
        folder.mkdir()
        titles = [f.title for f in app_audit.audit(_model(folder, service)).findings]
        assert not [t for t in titles if t.startswith("PUT /notes/:id")], service[-200:]


def test_python_ownership_also_needs_a_comparison(tmp_path):
    (tmp_path / "schema.sql").write_text("CREATE TABLE notes (id INTEGER PRIMARY KEY, owner_id INTEGER, body TEXT);\n")
    (tmp_path / "app.py").write_text(
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    row = db.execute('SELECT body, owner_id FROM notes WHERE id = ?', (note_id,)).fetchone()\n"
        "    return {'body': row['body'], 'owner': row['owner_id']}\n"
        "@app.get('/checked/{note_id}')\n"
        "def checked(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    row = db.execute('SELECT body, owner_id FROM notes WHERE id = ?', (note_id,)).fetchone()\n"
        "    ensure_owner(row, user)\n"
        "    return row\n")
    report = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert [f.title for f in report.findings if "who owns" in f.title] == [
        "GET /notes/{note_id} reads `notes` without checking who owns the row"]
    assert data_access.GUARD in next(r for r in app_audit.build_model(str(tmp_path)).routes if "checked" in r.path).data.checked


def test_tables_dropped_then_created_stay_and_tables_dropped_later_go(tmp_path):
    (tmp_path / "001.sql").write_text(
        "DROP TABLE IF EXISTS post;\nCREATE TABLE post (id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE old_tags (id INTEGER PRIMARY KEY);\nCREATE TABLE _links (a INTEGER, b INTEGER);\n")
    (tmp_path / "002.sql").write_text("DROP TABLE old_tags;\n")
    (tmp_path / "app.py").write_text("@app.get('/posts')\ndef posts(db=Depends(get_db)):\n    return db.execute('SELECT id FROM post')\n")
    model = app_audit.build_model(str(tmp_path))
    assert sorted(t.name for t in model.tables) == ["_links", "post"]
    titles = [f.title for f in app_audit.audit(model).findings]
    assert "No route reads or writes table `_links`" not in titles, "a link table an ORM manages"
