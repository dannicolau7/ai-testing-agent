"""Application audit (roadmap stage 4, first version): do the layers agree?"""

import subprocess
import sys
from pathlib import Path

import app_audit

DEMO = Path(__file__).resolve().parent / "examples" / "audit-demo"


def _titles(report, group):
    return [f.title for f in report.of(group)]


def test_the_demo_application_is_read_layer_by_layer():
    model = app_audit.build_model(str(DEMO))
    assert sorted(r.key for r in model.routes) == [
        ("DELETE", "/api/orders/{}"),
        ("GET", "/api/orders"),
        ("GET", "/api/orders/{}"),
        ("POST", "/api/admin/reindex"),
        ("POST", "/api/orders"),
    ]
    assert len(model.spec_operations) == 5 and model.spec_files == ["openapi.yaml"]
    assert {t.name: len(t.columns) for t in model.tables} == {
        "customers": 2, "orders": 4, "order_events": 2,
    }
    by_route = {r.key: r for r in model.routes}
    # A database dependency is not an access check; a current-user dependency is evidence of one.
    assert by_route[("DELETE", "/api/orders/{}")].auth_evidence == []
    assert by_route[("POST", "/api/orders")].auth_evidence == ["Depends(current_user)"]
    orders = next(t for t in model.tables if t.name == "orders")
    columns = {c.name: c for c in orders.columns}
    assert columns["customer_id"].foreign_key == "customers" and not columns["customer_id"].nullable
    assert columns["shipping_address_id"].foreign_key == "" and columns["id"].primary_key


def test_planted_problems_are_found_and_sorted():
    report = app_audit.audit(app_audit.build_model(str(DEMO)))
    assert _titles(report, "wrong_now") == [
        "The frontend calls PATCH /api/orders/{id}, which no backend route defines",
        "The frontend calls POST /api/orders/{id}/refund, which no backend route defines",
        "The API spec documents GET /api/orders/{orderId}/invoice, which the backend does not implement",
        "The spec says DELETE /api/orders/{order_id} needs authentication, but the code shows no check",
    ]
    assert _titles(report, "likely") == [
        "POST /api/admin/reindex is not in the API spec",
        "orders.shipping_address_id looks like a reference but has no foreign key",
        "Table order_events has no primary key",
    ]
    assert _titles(report, "unclear") == [
        "A frontend request whose address is built at run time",
        "Nothing in the frontend calls POST /api/admin/reindex",
    ]
    assert not report.ok
    markdown = app_audit.render_markdown(report)
    assert "## Wrong now (4)" in markdown and "## Not examined" in markdown
    assert "The backend defines DELETE, GET for that path." in markdown
    assert "not that the product is right" in markdown


def test_paths_from_every_framework_compare_equal():
    same = {app_audit.normalize_path(p) for p in (
        "/orders/{order_id}", "/orders/{orderId}/", "/orders/<int:order_id>", "/orders/:id",
        "/orders/${id}", "orders/${order.id}?expand=1",
    )}
    assert same == {"/orders/{}"}
    assert app_audit.normalize_path("/") == "/" and app_audit.normalize_path("") == "/"


def test_flask_express_and_sqlalchemy_are_read(tmp_path):
    (tmp_path / "views.py").write_text(
        "from flask import Flask\n"
        "from flask_login import login_required\n"
        "app = Flask(__name__)\n"
        "@app.route('/items/<int:item_id>', methods=['GET', 'PUT'])\n"
        "@login_required\n"
        "def item(item_id): ...\n"
    )
    (tmp_path / "server.js").write_text(
        "router.post('/items', requireAuth, (req, res) => {});\n"
        "router.delete('/items/:id', (req, res) => {});\n"
        "axios.get('/items');\n"
    )
    (tmp_path / "models.py").write_text(
        "class Item(Base):\n"
        "    __tablename__ = 'items'\n"
        "    id = Column(Integer, primary_key=True)\n"
        "    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)\n"
        "    sku = mapped_column(String, unique=True)\n"
    )
    model = app_audit.build_model(str(tmp_path))
    routes = {r.key: r.auth_evidence for r in model.routes}
    assert routes == {
        ("GET", "/items/{}"): ["@login_required"],
        ("PUT", "/items/{}"): ["@login_required"],
        ("POST", "/items"): ["requireAuth"],
        ("DELETE", "/items/{}"): [],
    }
    assert [(c.method, c.path) for c in model.calls] == [("GET", "/items")]
    items = model.tables[0]
    cols = {c.name: c for c in items.columns}
    assert items.name == "items" and cols["owner_id"].foreign_key == "users.id"
    assert cols["sku"].unique and cols["id"].primary_key

    report = app_audit.audit(model)
    assert "DELETE /items/:id changes data and shows no access check" in _titles(report, "likely")
    assert not any("PUT" in t and "access check" in t for t in _titles(report, "likely"))


def test_a_prefix_such_as_api_does_not_count_as_a_mismatch(tmp_path):
    (tmp_path / "app.py").write_text(
        "@router.get('/orders')\ndef orders(user=Depends(current_user)): ...\n"
    )
    (tmp_path / "api.ts").write_text("export const f = () => fetch('/api/v1/orders');\n")
    report = app_audit.audit(app_audit.build_model(str(tmp_path)))
    assert report.of("wrong_now") == [] and report.ok


def test_a_missing_layer_is_reported_as_not_examined_not_as_clean(tmp_path):
    (tmp_path / "app.py").write_text("@app.get('/x')\ndef x(): ...\n")
    report = app_audit.audit(app_audit.build_model(str(tmp_path)))
    text = " ".join(report.not_examined)
    assert "No frontend API calls were found" in text and "No an API spec" not in text
    assert "No database tables were found" in text
    # Tests, dependencies and build output are not application source.
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "x.js").write_text("fetch('/nowhere');\n")
    (tmp_path / "test_app.py").write_text("@app.post('/only-in-a-test')\ndef t(): ...\n")
    model = app_audit.build_model(str(tmp_path))
    assert model.calls == [] and [r.path for r in model.routes] == ["/x"]


def test_command_line(tmp_path):
    out = tmp_path / "audit.md"
    proc = subprocess.run(
        [sys.executable, "cli.py", "audit", str(DEMO), "-o", str(out)], capture_output=True, text=True
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "## Wrong now (4)" in out.read_text()
    missing = subprocess.run(
        [sys.executable, "cli.py", "audit", str(tmp_path / "nope")], capture_output=True, text=True
    )
    assert missing.returncode == 2
