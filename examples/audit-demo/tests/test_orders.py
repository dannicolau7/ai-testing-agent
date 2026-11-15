"""A few tests for the demo, some linked to requirements and some not. They are read by
`trace`; they are not run in this project's own test suite (the demo backend does not run)."""
import os

import pytest
import requests

BASE = os.environ.get("DEMO_BASE_URL", "http://localhost:8000")


@pytest.mark.requirement("REQ-1")
def test_list_orders_needs_sign_in():
    assert requests.get(BASE + "/api/orders", timeout=10).status_code == 401


def test_view_own_order():
    """Covers: REQ-2"""
    response = requests.get(BASE + "/api/orders/1", headers={"Authorization": "Bearer customer"}, timeout=10)
    assert response.status_code == 200


# Requirement: REQ-3, REQ-12
def test_delete_needs_sign_in():
    assert requests.delete(BASE + "/api/orders/1", timeout=10).status_code == 401


def test_health():
    assert requests.get(BASE + "/health", timeout=10).status_code == 200
