"""
VenueFlow — Test Suite
5 pytest tests covering API routes, input validation, and data simulation.
"""

import json
import pytest
from app import app, sanitize_input, get_crowd_data, get_wait_times, get_parking_data


@pytest.fixture
def client():
    """Create a Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    """Test that the health check endpoint returns 200 with correct structure."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "VenueFlow"
    assert "gemini_available" in data
    assert "timestamp" in data


def test_crowd_endpoint(client):
    """Test that /api/crowd returns valid crowd density data for all zones."""
    resp = client.get("/api/crowd")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "zones" in data
    assert "timestamp" in data
    # All 8 sections should be present
    for zone in "ABCDEFGH":
        assert zone in data["zones"]
        zone_data = data["zones"][zone]
        assert 0 <= zone_data["density"] <= 100
        assert zone_data["status"] in ("low", "moderate", "high")


def test_waits_endpoint(client):
    """Test that /api/waits returns all facility categories with valid structure."""
    resp = client.get("/api/waits")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "waits" in data
    assert "alerts" in data
    for category in ("gates", "food", "restrooms", "parking"):
        assert category in data["waits"]
        assert len(data["waits"][category]) > 0
        for item in data["waits"][category]:
            assert "name" in item
            assert "wait" in item
            assert isinstance(item["wait"], int)


def test_chat_endpoint_validation(client):
    """Test that /api/chat validates input properly."""
    # Missing message
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()

    # Empty message
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 400

    # Valid message (uses fallback since no API key in tests)
    resp = client.post("/api/chat", json={"message": "Where is the nearest restroom?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data
    assert len(data["reply"]) > 0


def test_sanitize_input():
    """Test input sanitization strips control characters and truncates."""
    # Normal input passes through
    assert sanitize_input("Hello world") == "Hello world"

    # Control characters are removed
    assert sanitize_input("Hello\x00world") == "Helloworld"

    # Newlines are preserved
    assert "\n" in sanitize_input("Line1\nLine2")

    # Truncation works
    long_text = "A" * 2000
    assert len(sanitize_input(long_text)) == 1000

    # Non-string input returns empty
    assert sanitize_input(None) == ""
    assert sanitize_input(123) == ""

    # Whitespace is stripped
    assert sanitize_input("  hello  ") == "hello"
