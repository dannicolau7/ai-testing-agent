"""Orders API (demo). Several things here are wrong on purpose."""
from fastapi import Depends, FastAPI

app = FastAPI()


def get_db():
    ...


def current_user():
    ...


@app.get("/api/orders")
def list_orders(db=Depends(get_db), user=Depends(current_user)):
    ...


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, user=Depends(current_user)):
    ...


@app.post("/api/orders")
def create_order(db=Depends(get_db), user=Depends(current_user)):
    ...


# No access check: only a database dependency.
@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int, db=Depends(get_db)):
    ...


# Not in the spec, and nothing in the frontend calls it.
@app.post("/api/admin/reindex")
def reindex(user=Depends(current_user)):
    ...
