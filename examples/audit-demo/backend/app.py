"""Orders API (demo). Several things here are wrong on purpose."""
from fastapi import Depends, FastAPI

app = FastAPI()


def get_db():
    ...


def current_user():
    ...


def record_event(db, order_id, kind):
    db.execute("INSERT INTO order_events (order_id, kind) VALUES (?, ?)", (order_id, kind))


@app.get("/api/orders")
def list_orders(sort: str = "id", db=Depends(get_db), user=Depends(current_user)):
    # The sort column comes from the request and goes straight into the SQL text.
    return db.execute(
        f"SELECT id, total FROM orders WHERE customer_id = ? ORDER BY {sort}", (user.id,)
    ).fetchall()


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, db=Depends(get_db), user=Depends(current_user)):
    # Signed in, but any customer can read any order.
    record_event(db, order_id, "viewed")
    return db.execute("SELECT id, total FROM orders WHERE id = ?", (order_id,)).fetchone()


@app.post("/api/orders")
def create_order(total: float, db=Depends(get_db), user=Depends(current_user)):
    # The orders table has no status column.
    db.execute(
        "INSERT INTO orders (customer_id, total, status) VALUES (?, ?, 'new')", (user.id, total)
    )


# No access check: only a database dependency.
@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, db=Depends(get_db)):
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))


# Not in the spec, and nothing in the frontend calls it. The table does not exist.
@app.post("/api/admin/reindex")
def reindex(db=Depends(get_db), user=Depends(current_user)):
    db.execute("INSERT INTO search_jobs (kind) VALUES ('orders')")
