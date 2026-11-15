CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    -- Looks like a reference, but nothing enforces it.
    shipping_address_id INTEGER,
    total NUMERIC(10, 2) NOT NULL
);

-- No primary key.
CREATE TABLE order_events (
    order_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
