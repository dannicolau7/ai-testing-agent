"""
Demo test file with intentional failures — used to demonstrate
the AI failure analysis feature (Week 3).

Run:  python cli.py failures test_specs/demo_failures.py
"""
import pytest
import requests

BASE_URL = "https://httpbin.org"


@pytest.fixture(scope="session")
def api_client():
    return requests.Session()


def test_get_status_200(api_client):
    """GET /status/200 — expects 200. Should PASS."""
    response = api_client.get(f"{BASE_URL}/status/200", timeout=10)
    assert response.status_code == 200


def test_get_json_has_required_field(api_client):
    """GET /json — checks for a field that does not exist. Should FAIL."""
    response = api_client.get(f"{BASE_URL}/json", timeout=10)
    assert response.status_code == 200
    data = response.json()
    # httpbin /json returns {"slideshow": {...}}, not "items"
    assert "items" in data, f"Expected 'items' key, got: {list(data.keys())}"


def test_wrong_status_code(api_client):
    """GET /status/404 — asserts 200 instead of 404. Should FAIL."""
    response = api_client.get(f"{BASE_URL}/status/404", timeout=10)
    assert response.status_code == 200  # intentionally wrong


def test_post_with_body(api_client):
    """POST /post — echoes the body back. Should PASS."""
    payload = {"name": "test_user", "role": "engineer"}
    response = api_client.post(f"{BASE_URL}/post", json=payload, timeout=10)
    assert response.status_code == 200
    data = response.json()
    assert data["json"] == payload
