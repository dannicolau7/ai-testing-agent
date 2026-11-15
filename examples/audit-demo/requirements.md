# Orders: requirements (demo)

- REQ-1 A signed-in customer can list their own orders (GET /api/orders).
- REQ-2 A signed-in customer can view only their own orders (GET /api/orders/{id}).
- REQ-3 Only a signed-in customer may delete an order (DELETE /api/orders/{id}).
- REQ-4 A customer's email must be unique.
- REQ-5 Only administrators may rebuild the search index: POST /api/admin/reindex.
- REQ-6 A customer can ask for a refund (POST /api/orders/{id}/refund).
- REQ-7 Orders can be exported as a CSV file.
- REQ-8 A customer's phone number must be unique.
