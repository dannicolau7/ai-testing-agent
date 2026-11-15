"""What a handler reads and writes (roadmap stage 4, second step)."""

import ast

import app_audit
import data_access


def _data(source, handler="handler"):
    tree = ast.parse(source)
    index = data_access.index_functions([("app.py", tree)])
    node = index[handler][0][1]
    return data_access.handler_data(node, "app.py", index)


def _titles(report, group):
    return [f.title for f in report.of(group)]


def test_sql_statements_are_read():
    read = data_access.parse_sql(
        "SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id WHERE o.id = ? AND c.email LIKE ?")
    assert [(a.kind, a.table, a.single_table) for a in read] == [
        ("read", "orders", False), ("read", "customers", False)]
    assert read[0].filters == ["id", "email"]
    insert = data_access.parse_sql("insert into orders (customer_id, total) values (?, ?)")[0]
    assert (insert.kind, insert.table, insert.columns) == ("write", "orders", ["customer_id", "total"])
    update = data_access.parse_sql("UPDATE orders SET total = ?, status = 'x' WHERE id = ? AND customer_id = ?")[0]
    assert (update.columns, update.filters) == (["total", "status"], ["id", "customer_id"])
    delete = data_access.parse_sql("DELETE FROM orders WHERE id = ?")[0]
    assert (delete.kind, delete.filters) == ("write", ["id"])
    assert data_access.parse_sql("Hello") == []


def test_ordinary_sentences_are_not_taken_for_sql():
    data = _data(
        "def handler(db):\n"
        "    message = 'Select a file from the list'\n"
        "    other = 'Update your profile set up and delete from the menu'\n"
        "    db.execute('select id from items where id = ?')\n"
    )
    assert [(a.kind, a.table) for a in data.accesses] == [("read", "items")]


def test_sql_built_from_values_is_marked_and_parameters_are_not():
    data = _data(
        "def handler(db, name, ident):\n"
        "    db.execute(f\"SELECT id FROM a WHERE name = '{name}'\")\n"
        "    db.execute('SELECT id FROM b WHERE name = %s' % name)\n"
        "    db.execute('SELECT id FROM c WHERE name = ' + name)\n"
        "    db.execute('SELECT id FROM d WHERE name = {}'.format(name))\n"
        "    db.execute('SELECT id FROM e ' 'WHERE id = ?', (ident,))\n"
        "    db.execute('SELECT id FROM f ' + 'WHERE id = ?', (ident,))\n"
        "    db.execute('SELECT id FROM g WHERE id = %s', (ident,))\n"
    )
    assert {a.table: a.built_from_values for a in data.accesses} == {
        "a": True, "b": True, "c": True, "d": True, "e": False, "f": False, "g": False}
    assert len(data.accesses) == 7, "each statement is counted once"


def test_calls_are_followed_into_project_functions_but_not_ambiguous_ones():
    data = _data(
        "def save(db, x):\n"
        "    db.execute('INSERT INTO items (name) VALUES (?)', (x,))\n"
        "class A:\n"
        "    def load(self): return self.db.execute('SELECT id FROM first')\n"
        "class B:\n"
        "    def load(self): return self.db.execute('SELECT id FROM second')\n"
        "def handler(db, repo, x):\n"
        "    save(db, x)\n"
        "    repo.load()\n"
        "    handler(db, repo, x)\n"
    )
    assert [(a.kind, a.table) for a in data.accesses] == [("write", "items")]
    assert data.functions_followed == 2


def _app(tmp_path, body, schema=None):
    (tmp_path / "app.py").write_text(body)
    (tmp_path / "schema.sql").write_text(schema or (
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT);\n"
        "CREATE TABLE notes (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), body TEXT);\n"
    ))
    return app_audit.audit(app_audit.build_model(str(tmp_path)))


OWNERSHIP = "GET /notes/{note_id} reads `notes` without checking who owns the row"


def test_a_row_read_by_id_with_no_owner_check_is_reported(tmp_path):
    report = _app(tmp_path,
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.execute('SELECT body FROM notes WHERE id = ?', (note_id,))\n")
    assert OWNERSHIP in _titles(report, "likely")
    assert report.ok, "a missing ownership check is a risk, not a proven fault"


def test_an_owner_check_in_the_query_or_in_code_or_an_admin_route_is_accepted(tmp_path):
    in_query = (
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.execute('SELECT body FROM notes WHERE id = ? AND user_id = ?', (note_id, user.id))\n")
    in_code = (
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    note = db.execute('SELECT * FROM notes WHERE id = ?', (note_id,)).fetchone()\n"
        "    if note.user_id != user.id:\n"
        "        raise HTTPException(403)\n"
        "    return note\n")
    admin = (
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(require_admin)):\n"
        "    return db.execute('SELECT body FROM notes WHERE id = ?', (note_id,))\n")
    no_owner_column = (
        "@app.get('/users/{user_id}')\n"
        "def get_user(user_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.execute('SELECT email FROM users WHERE id = ?', (user_id,))\n")
    for i, body in enumerate((in_query, in_code, admin, no_owner_column)):
        folder = tmp_path / str(i)
        folder.mkdir()
        report = _app(folder, body)
        assert not [t for t in _titles(report, "likely") if "who owns" in t], body


def test_missing_tables_and_columns_are_wrong_now_and_joins_are_left_alone(tmp_path):
    report = _app(tmp_path,
        "@app.post('/notes')\n"
        "def add(db=Depends(get_db), user=Depends(current_user)):\n"
        "    db.execute('INSERT INTO notes (user_id, title) VALUES (?, ?)')\n"
        "    db.execute('INSERT INTO drafts (body) VALUES (?)')\n"
        "    db.execute('SELECT n.body, u.email FROM notes n JOIN users u ON u.id = n.user_id WHERE u.email = ?')\n")
    assert _titles(report, "wrong_now") == [
        "The code uses column `notes.title`, which the table does not have",
        "The code uses table `drafts`, which the database does not define",
    ]


def test_a_get_that_changes_data_is_reported_except_for_log_like_tables(tmp_path):
    schema = ("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);\n"
              "CREATE TABLE view_log (id INTEGER PRIMARY KEY, note INTEGER);\n")
    report = _app(tmp_path,
        "@app.get('/notes/purge')\n"
        "def purge(db=Depends(get_db), user=Depends(current_user)):\n"
        "    db.execute('DELETE FROM notes WHERE body IS NULL')\n"
        "@app.get('/notes')\n"
        "def listing(db=Depends(get_db), user=Depends(current_user)):\n"
        "    db.execute('INSERT INTO view_log (note) VALUES (1)')\n"
        "    return db.execute('SELECT id FROM notes')\n", schema)
    assert [t for t in _titles(report, "likely") if "changes `" in t] == ["GET /notes/purge changes `notes`"]


def test_sqlalchemy_calls_are_linked_to_their_tables(tmp_path):
    (tmp_path / "app.py").write_text(
        "class Note(Base):\n"
        "    __tablename__ = 'notes'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    owner_id = Column(Integer, ForeignKey('users.id'))\n"
        "class Tag(Base):\n"
        "    __tablename__ = 'tags'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "@app.get('/notes/{note_id}')\n"
        "def get_note(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.query(Note).filter(Note.id == note_id).first()\n"
        "@app.get('/mine/{note_id}')\n"
        "def mine(note_id, db=Depends(get_db), user=Depends(current_user)):\n"
        "    return db.query(Note).filter(Note.id == note_id, Note.owner_id == user.id).first()\n"
        "@app.post('/notes')\n"
        "def add(db=Depends(get_db), user=Depends(current_user)):\n"
        "    db.add(Note(owner_id=user.id))\n"
        "    db.add(HTTPException(500))\n")
    model = app_audit.build_model(str(tmp_path))
    accesses = {r.path: [(a.kind, a.table) for a in r.data.accesses] for r in model.routes}
    assert accesses == {"/notes/{note_id}": [("read", "notes")], "/mine/{note_id}": [("read", "notes")],
                        "/notes": [("write", "notes")]}
    report = app_audit.audit(model)
    assert [t for t in _titles(report, "likely") if "who owns" in t] == [
        "GET /notes/{note_id} reads `notes` without checking who owns the row"]
    assert "No route reads or writes table `tags`" in _titles(report, "unclear")


def test_inserted_arguments_are_likely_and_inserted_local_pieces_are_unclear(tmp_path):
    report = _app(tmp_path,
        "@app.get('/notes')\n"
        "def listing(order: str, db=Depends(get_db), user=Depends(current_user)):\n"
        "    where = 'WHERE user_id = ?'\n"
        "    db.execute(f'SELECT id FROM notes {where}', (user.id,))\n"
        "    return db.execute(f'SELECT id FROM notes WHERE user_id = ? ORDER BY {order}', (user.id,))\n")
    assert [t for t in _titles(report, "likely") if "SQL" in t] == [
        "SQL on `notes` is built by inserting a function argument into the text"]
    assert [t for t in _titles(report, "unclear") if "SQL" in t] == ["SQL on `notes` is assembled from pieces"]
