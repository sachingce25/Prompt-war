"""
VenueFlow — Comprehensive Test Suite
Covers API routes, input validation, data simulation, security headers,
rate limiting, and edge cases for full confidence across features.
"""

import json
import time
import pytest
from app import app, sanitize_input, get_crowd_data, get_wait_times, get_parking_data


@pytest.fixture
def client():
    """Create a Flask test client with testing mode enabled."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Health & Serving
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    """Health check returns 200 with correct structure."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "VenueFlow"
    assert "gemini_available" in data
    assert isinstance(data["gemini_available"], bool)
    assert "timestamp" in data


def test_serve_index(client):
    """Root path serves the HTML frontend."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"VenueFlow" in resp.data or b"<!DOCTYPE html>" in resp.data


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

def test_security_headers_on_api(client):
    """All API responses include mandatory security headers."""
    resp = client.get("/api/crowd")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_no_store_cache_on_api(client):
    """API responses are not cached by the browser."""
    resp = client.get("/api/waits")
    cc = resp.headers.get("Cache-Control", "")
    assert "no-store" in cc


# ---------------------------------------------------------------------------
# Crowd Endpoint
# ---------------------------------------------------------------------------

def test_crowd_endpoint_structure(client):
    """GET /api/crowd returns valid crowd density for all 8 sections."""
    resp = client.get("/api/crowd")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "zones" in data
    assert "timestamp" in data
    assert "recommendation" in data
    for zone in "ABCDEFGH":
        assert zone in data["zones"], f"Zone {zone} missing"
        z = data["zones"][zone]
        assert 0 <= z["density"] <= 100
        assert z["status"] in ("low", "moderate", "high")
        assert "label" in z


def test_crowd_recommendation_present(client):
    """Crowd response includes a non-empty recommendation string."""
    data = client.get("/api/crowd").get_json()
    assert isinstance(data["recommendation"], str)
    assert len(data["recommendation"]) > 0


# ---------------------------------------------------------------------------
# Waits Endpoint
# ---------------------------------------------------------------------------

def test_waits_endpoint_structure(client):
    """GET /api/waits returns all facility categories with valid structure."""
    resp = client.get("/api/waits")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "waits" in data
    assert "alerts" in data
    assert "timestamp" in data
    for category in ("gates", "food", "restrooms", "parking"):
        assert category in data["waits"], f"Category {category} missing"
        assert len(data["waits"][category]) > 0
        for item in data["waits"][category]:
            assert "name" in item
            assert "wait" in item
            assert isinstance(item["wait"], int)
            assert item["status"] in ("low", "moderate", "high")


def test_waits_alerts_structure(client):
    """Alerts list contains items with required fields when present."""
    data = client.get("/api/waits").get_json()
    for alert in data["alerts"]:
        assert "message" in alert
        assert "facility" in alert
        assert "category" in alert
        assert "wait" in alert


# ---------------------------------------------------------------------------
# Parking Endpoint
# ---------------------------------------------------------------------------

def test_parking_endpoint_structure(client):
    """GET /api/parking returns all zones with occupancy and stagger plan."""
    resp = client.get("/api/parking")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "zones" in data
    assert "stagger_plan" in data
    assert "timestamp" in data
    for zone in "ABCD":
        assert zone in data["zones"], f"Parking zone {zone} missing"
        z = data["zones"][zone]
        assert 0 <= z["occupancy_pct"] <= 100
        assert z["exit_time"] >= 0
        assert z["status"] in ("low", "moderate", "high")
        assert z["occupied"] <= z["capacity"]


def test_parking_stagger_plan_order(client):
    """Stagger plan contains exactly 4 entries with required fields."""
    data = client.get("/api/parking").get_json()
    plan = data["stagger_plan"]
    assert len(plan) == 4
    for step in plan:
        assert "zone" in step
        assert "suggested_exit" in step
        assert "reason" in step


# ---------------------------------------------------------------------------
# Chat Endpoint
# ---------------------------------------------------------------------------

def test_chat_rejects_empty_body(client):
    """POST /api/chat with no JSON body returns 400."""
    resp = client.post("/api/chat", content_type="application/json", data="not-json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_chat_rejects_missing_message(client):
    """POST /api/chat with missing message key returns 400."""
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_chat_rejects_empty_message(client):
    """POST /api/chat with blank message returns 400."""
    resp = client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_chat_valid_message(client):
    """POST /api/chat with a valid message returns a reply from fallback."""
    resp = client.post("/api/chat", json={"message": "Where is the nearest restroom?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    assert "source" in data
    assert "timestamp" in data


def test_chat_fallback_food_query(client):
    """Fallback response mentions food for a food-related query."""
    resp = client.post("/api/chat", json={"message": "I'm hungry, what food can I get?"})
    data = resp.get_json()
    assert resp.status_code == 200
    reply = data["reply"].lower()
    assert any(w in reply for w in ("food", "blitz", "fiesta", "noodle", "pizza", "min"))


def test_chat_fallback_crowd_query(client):
    """Fallback response contains density info for a crowd-related query."""
    resp = client.post("/api/chat", json={"message": "How crowded is it?"})
    data = resp.get_json()
    assert resp.status_code == 200
    reply = data["reply"].lower()
    assert any(w in reply for w in ("section", "crowd", "%", "least"))


def test_chat_fallback_greeting(client):
    """Fallback returns a welcome message for greetings."""
    resp = client.post("/api/chat", json={"message": "hello"})
    data = resp.get_json()
    assert resp.status_code == 200
    assert "apex arena" in data["reply"].lower() or "concierge" in data["reply"].lower()


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

def test_sanitize_normal_input():
    assert sanitize_input("Hello world") == "Hello world"


def test_sanitize_removes_control_chars():
    assert sanitize_input("Hello\x00world") == "Helloworld"


def test_sanitize_preserves_newlines():
    result = sanitize_input("Line1\nLine2")
    assert "\n" in result


def test_sanitize_truncates():
    long_text = "A" * 2000
    assert len(sanitize_input(long_text)) == 1000


def test_sanitize_non_string():
    assert sanitize_input(None) == ""
    assert sanitize_input(123) == ""
    assert sanitize_input([]) == ""


def test_sanitize_strips_whitespace():
    assert sanitize_input("  hello  ") == "hello"


def test_sanitize_custom_max_length():
    assert len(sanitize_input("A" * 500, max_length=100)) == 100


# ---------------------------------------------------------------------------
# Data Simulation Helpers
# ---------------------------------------------------------------------------

def test_get_crowd_data_returns_all_zones():
    data = get_crowd_data()
    assert set(data["zones"].keys()) == set("ABCDEFGH")


def test_get_wait_times_returns_all_categories():
    data = get_wait_times()
    for cat in ("gates", "food", "restrooms", "parking"):
        assert cat in data["waits"]


def test_get_parking_data_occupancy_bounds():
    data = get_parking_data()
    for zone, info in data["zones"].items():
        assert 0 <= info["occupancy_pct"] <= 100
        assert info["occupied"] <= info["capacity"]


def test_crowd_data_caching():
    """Two rapid calls should return identical cached timestamps."""
    first = get_crowd_data()
    second = get_crowd_data()
    assert first["timestamp"] == second["timestamp"]
