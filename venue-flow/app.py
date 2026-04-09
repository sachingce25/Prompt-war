"""
VenueFlow — AI-Powered Smart Venue Assistant Backend
Flask API server with Gemini AI concierge, crowd simulation, and wait time tracking.
"""

import os
import json
import time
import random
import re
import logging
from collections import defaultdict
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("venueflow")

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

@app.after_request
def add_security_headers(response):
    """Attach security headers to every response."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    # Cache-Control for API routes
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------
# Simple In-Memory Rate Limiter (per IP, per endpoint)
# ---------------------------------------------------------------------------

_rate_buckets: dict = defaultdict(list)
RATE_LIMITS = {
    "/api/chat": (10, 60),   # 10 requests per 60 seconds
    "default":   (60, 60),   # 60 requests per 60 seconds
}


def _is_rate_limited(ip: str, path: str) -> bool:
    limit, window = RATE_LIMITS.get(path, RATE_LIMITS["default"])
    now = time.time()
    key = f"{ip}:{path}"
    _rate_buckets[key] = [t for t in _rate_buckets[key] if now - t < window]
    if len(_rate_buckets[key]) >= limit:
        return True
    _rate_buckets[key].append(now)
    return False


@app.before_request
def check_rate_limit():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if _is_rate_limited(ip, request.path):
        logger.warning("Rate limit hit: ip=%s path=%s", ip, request.path)
        return jsonify({"error": "Too many requests. Please slow down."}), 429


# ---------------------------------------------------------------------------
# Gemini AI Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="""You are VenueFlow AI Concierge — a friendly, knowledgeable assistant
for a large-scale sports stadium called "Apex Arena". You help attendees navigate the venue,
find amenities, and have the best possible experience.

VENUE LAYOUT:
- Oval stadium with 8 sections labeled A through H (clockwise from north)
- 4 entry gates: Gate 1 (North), Gate 2 (East), Gate 3 (South), Gate 4 (West)
- Total capacity: 60,000 seats

FACILITIES:
- Food Stalls: "Burger Blitz" (Section A), "Taco Fiesta" (Section C), "Noodle Bar" (Section E), "Pizza Planet" (Section G), "Hydration Station" (Sections B, D, F, H)
- Restrooms: Located between every two sections (A-B, C-D, E-F, G-H), plus VIP restrooms near Gate 1
- First Aid: Main medical center near Gate 1, satellite stations at Gates 2 and 4
- Merchandise: Official store near Gate 1, pop-up kiosks at Gates 2 and 3
- VIP Lounges: Above sections A and E

PARKING ZONES:
- Zone A (North lot, 2000 spaces): Closest to Gate 1
- Zone B (East lot, 1500 spaces): Closest to Gate 2
- Zone C (South lot, 2500 spaces): Closest to Gate 3, largest lot
- Zone D (West lot, 1000 spaces): Closest to Gate 4, VIP parking

CURRENT EVENT: Championship Finals — kickoff at 7:00 PM

RULES:
- Always be concise but helpful (2-3 sentences max unless asked for detail)
- Suggest the least crowded options when possible
- If asked about real-time data, reference the crowd density and wait times
- Be enthusiastic about the event experience
- For directions, give clear landmark-based guidance
- Never make up safety or emergency information — direct to staff
""",
        )
        logger.info("Gemini AI concierge initialized successfully.")
    except Exception as e:
        logger.warning("Gemini initialization failed: %s", e)
        gemini_model = None

# ---------------------------------------------------------------------------
# Simulated Venue Data
# ---------------------------------------------------------------------------

BASE_CROWD_DATA = {
    "A": {"density": 72, "label": "Section A", "status": "high"},
    "B": {"density": 45, "label": "Section B", "status": "moderate"},
    "C": {"density": 88, "label": "Section C", "status": "high"},
    "D": {"density": 30, "label": "Section D", "status": "low"},
    "E": {"density": 65, "label": "Section E", "status": "moderate"},
    "F": {"density": 22, "label": "Section F", "status": "low"},
    "G": {"density": 55, "label": "Section G", "status": "moderate"},
    "H": {"density": 38, "label": "Section H", "status": "low"},
}

BASE_WAIT_TIMES = {
    "gates": [
        {"id": "gate1", "name": "Gate 1 (North)", "wait": 12, "status": "moderate"},
        {"id": "gate2", "name": "Gate 2 (East)", "wait": 4, "status": "low"},
        {"id": "gate3", "name": "Gate 3 (South)", "wait": 18, "status": "high"},
        {"id": "gate4", "name": "Gate 4 (West)", "wait": 7, "status": "moderate"},
    ],
    "food": [
        {"id": "burger", "name": "Burger Blitz", "section": "A", "wait": 15, "status": "high"},
        {"id": "taco", "name": "Taco Fiesta", "section": "C", "wait": 8, "status": "moderate"},
        {"id": "noodle", "name": "Noodle Bar", "section": "E", "wait": 5, "status": "low"},
        {"id": "pizza", "name": "Pizza Planet", "section": "G", "wait": 11, "status": "moderate"},
    ],
    "restrooms": [
        {"id": "rr_ab", "name": "Restroom A-B", "wait": 6, "status": "moderate"},
        {"id": "rr_cd", "name": "Restroom C-D", "wait": 12, "status": "high"},
        {"id": "rr_ef", "name": "Restroom E-F", "wait": 3, "status": "low"},
        {"id": "rr_gh", "name": "Restroom G-H", "wait": 8, "status": "moderate"},
        {"id": "rr_vip", "name": "VIP Restroom", "wait": 1, "status": "low"},
    ],
    "parking": [
        {"id": "exit_a", "name": "Zone A Exit", "wait": 25, "status": "high"},
        {"id": "exit_b", "name": "Zone B Exit", "wait": 15, "status": "moderate"},
        {"id": "exit_c", "name": "Zone C Exit", "wait": 35, "status": "high"},
        {"id": "exit_d", "name": "Zone D Exit", "wait": 10, "status": "moderate"},
    ],
}

PARKING_ZONES = {
    "A": {"name": "Zone A — North Lot", "capacity": 2000, "occupied": 1720, "gate": "Gate 1", "exit_time": 25},
    "B": {"name": "Zone B — East Lot", "capacity": 1500, "occupied": 1050, "gate": "Gate 2", "exit_time": 15},
    "C": {"name": "Zone C — South Lot", "capacity": 2500, "occupied": 2350, "gate": "Gate 3", "exit_time": 35},
    "D": {"name": "Zone D — West Lot (VIP)", "capacity": 1000, "occupied": 620, "gate": "Gate 4", "exit_time": 10},
}

_crowd_cache: dict = {"data": None, "timestamp": 0}
_waits_cache: dict = {"data": None, "timestamp": 0}
CACHE_TTL = 10  # seconds


def _jitter(value: float, pct: float = 0.15) -> int:
    """Add random variation to a numeric value (simulates live data)."""
    delta = int(value * pct)
    return max(0, min(100, value + random.randint(-delta, delta)))


def _status_from_value(val: float, thresholds: tuple = (30, 60)) -> str:
    """Determine status label from a numeric value."""
    if val <= thresholds[0]:
        return "low"
    elif val <= thresholds[1]:
        return "moderate"
    return "high"


def get_crowd_data() -> dict:
    """Return crowd density data with simulated jitter, cached for CACHE_TTL seconds."""
    now = time.time()
    if _crowd_cache["data"] and (now - _crowd_cache["timestamp"]) < CACHE_TTL:
        return _crowd_cache["data"]

    data = {}
    for zone, info in BASE_CROWD_DATA.items():
        density = _jitter(info["density"])
        data[zone] = {
            "density": density,
            "label": info["label"],
            "status": _status_from_value(density),
        }

    min_density = min(d["density"] for d in data.values())
    least_crowded = [z for z, d in data.items() if d["density"] == min_density]

    result = {
        "zones": data,
        "recommendation": f"Section {least_crowded[0]} is the least crowded right now" if least_crowded else "",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    }

    _crowd_cache["data"] = result
    _crowd_cache["timestamp"] = now
    return result


def get_wait_times() -> dict:
    """Return wait time data with simulated jitter, cached for CACHE_TTL seconds."""
    now = time.time()
    if _waits_cache["data"] and (now - _waits_cache["timestamp"]) < CACHE_TTL:
        return _waits_cache["data"]

    result: dict = {}
    for category, items in BASE_WAIT_TIMES.items():
        result[category] = []
        for item in items:
            wait = _jitter(item["wait"], pct=0.25)
            entry = {**item, "wait": wait, "status": _status_from_value(wait, (5, 12))}
            result[category].append(entry)

    alerts = []
    for category, items in result.items():
        for item in items:
            if item["wait"] < 5:
                alerts.append({
                    "type": "low_wait",
                    "message": f"{item['name']} is under 5 min wait!",
                    "facility": item["name"],
                    "wait": item["wait"],
                    "category": category,
                })

    data = {
        "waits": result,
        "alerts": alerts,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    }

    _waits_cache["data"] = data
    _waits_cache["timestamp"] = now
    return data


def get_parking_data() -> dict:
    """Return parking zone data with jitter on occupancy."""
    data: dict = {}
    for zone, info in PARKING_ZONES.items():
        occupied = _jitter(info["occupied"], pct=0.03)
        occupied = min(occupied, info["capacity"])
        occupancy_pct = round((occupied / info["capacity"]) * 100)
        exit_time = _jitter(info["exit_time"], pct=0.1)

        data[zone] = {
            **info,
            "occupied": occupied,
            "occupancy_pct": occupancy_pct,
            "exit_time": exit_time,
            "status": _status_from_value(occupancy_pct, (50, 80)),
        }

    return {
        "zones": data,
        "stagger_plan": [
            {"zone": "D", "suggested_exit": "T+0 min", "reason": "VIP — lowest congestion"},
            {"zone": "B", "suggested_exit": "T+10 min", "reason": "Moderate occupancy"},
            {"zone": "A", "suggested_exit": "T+20 min", "reason": "High occupancy, north route"},
            {"zone": "C", "suggested_exit": "T+30 min", "reason": "Highest occupancy, allow clearance"},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    }


# ---------------------------------------------------------------------------
# Input Validation Helpers
# ---------------------------------------------------------------------------

def sanitize_input(text, max_length: int = 1000) -> str:
    """Sanitize user input: strip, truncate, remove control characters."""
    if not isinstance(text, str):
        return ""
    text = text.strip()[:max_length]
    text = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", "", text)
    return text


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    """Serve the main frontend page."""
    return send_from_directory(".", "index.html")


@app.route("/health")
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "VenueFlow",
        "gemini_available": gemini_model is not None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
    })


@app.route("/api/crowd", methods=["GET"])
def api_crowd():
    """Return crowd density data for all venue zones."""
    try:
        return jsonify(get_crowd_data())
    except Exception as e:
        logger.error("Crowd data error: %s", e)
        return jsonify({"error": "Failed to fetch crowd data"}), 500


@app.route("/api/waits", methods=["GET"])
def api_waits():
    """Return wait times for all facility categories."""
    try:
        return jsonify(get_wait_times())
    except Exception as e:
        logger.error("Wait time error: %s", e)
        return jsonify({"error": "Failed to fetch wait times"}), 500


@app.route("/api/parking", methods=["GET"])
def api_parking():
    """Return parking zone occupancy and exit plan."""
    try:
        return jsonify(get_parking_data())
    except Exception as e:
        logger.error("Parking data error: %s", e)
        return jsonify({"error": "Failed to fetch parking data"}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Send a message to the Gemini AI concierge."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid JSON payload"}), 400

        message = sanitize_input(data.get("message", ""))
        if not message:
            return jsonify({"error": "Message is required"}), 400

        crowd = get_crowd_data()
        waits = get_wait_times()
        venue_context = sanitize_input(data.get("venue_context", ""), 500)

        context_block = (
            f"LIVE VENUE DATA (as of now):\n"
            f"Crowd Density: {json.dumps({z: d['density'] for z, d in crowd['zones'].items()})}\n"
            f"Gate Wait Times: {json.dumps([{'name': g['name'], 'wait': g['wait']} for g in waits['waits']['gates']])}\n"
            f"Food Wait Times: {json.dumps([{'name': f['name'], 'wait': f['wait']} for f in waits['waits']['food']])}\n"
            f"Restroom Wait Times: {json.dumps([{'name': r['name'], 'wait': r['wait']} for r in waits['waits']['restrooms']])}\n"
            f"Recommendation: {crowd.get('recommendation', 'N/A')}\n"
            f"Additional Context: {venue_context}\n"
        )

        if gemini_model:
            prompt = f"{context_block}\n\nUser Question: {message}"
            response = gemini_model.generate_content(prompt)
            reply = response.text
            source = "gemini"
        else:
            reply = _fallback_response(message, crowd, waits)
            source = "fallback"

        logger.info("Chat handled [source=%s] len=%d", source, len(reply))

        return jsonify({
            "reply": reply,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
            "source": source,
        })

    except Exception as e:
        logger.error("Chat error: %s", e)
        return jsonify({"error": "Chat request failed"}), 500


def _fallback_response(message: str, crowd: dict, waits: dict) -> str:
    """Provide intelligent fallback responses when Gemini is not available."""
    msg = message.lower()

    if any(w in msg for w in ("restroom", "bathroom", "toilet", "washroom")):
        best = min(waits["waits"]["restrooms"], key=lambda x: x["wait"])
        return f"🚻 The nearest low-wait restroom is **{best['name']}** with only a {best['wait']}-minute wait. Head towards the section signs and follow the restroom icons!"

    if any(w in msg for w in ("food", "eat", "hungry", "stall", "restaurant")):
        best = min(waits["waits"]["food"], key=lambda x: x["wait"])
        return f"🍔 **{best['name']}** has the shortest wait at {best['wait']} minutes! It's located in Section {best.get('section', 'N/A')}. Enjoy your meal!"

    if any(w in msg for w in ("gate", "entry", "enter", "entrance")):
        best = min(waits["waits"]["gates"], key=lambda x: x["wait"])
        return f"🚪 **{best['name']}** is your best bet with only a {best['wait']}-minute wait right now. Much faster than the other gates!"

    if any(w in msg for w in ("crowd", "busy", "packed", "empty", "quiet")):
        least = min(crowd["zones"].items(), key=lambda x: x[1]["density"])
        most = max(crowd["zones"].items(), key=lambda x: x[1]["density"])
        return (
            f"📊 **Section {least[0]}** is the least crowded ({least[1]['density']}% full), "
            f"while **Section {most[0]}** is the busiest ({most[1]['density']}%). "
            f"I'd recommend heading to Section {least[0]}!"
        )

    if any(w in msg for w in ("park", "exit", "leave", "car")):
        return "🅿️ For the fastest exit, use **Zone D (West Lot)** — it typically has the shortest exit time. Consider leaving 5 minutes before the final whistle to beat the rush!"

    if any(w in msg for w in ("seat", "section", "upgrade", "view")):
        least = min(crowd["zones"].items(), key=lambda x: x[1]["density"])
        return f"💺 **Section {least[0]}** has great availability right now at only {least[1]['density']}% capacity. Check with guest services near any gate for upgrade options!"

    if any(w in msg for w in ("help", "hi", "hello", "hey")):
        return "👋 Welcome to **Apex Arena**! I'm your AI concierge. Ask me about restrooms, food stalls, crowd levels, parking, or anything else to make your experience amazing!"

    return "🏟️ I'm your Apex Arena concierge! Try asking me about restroom locations, food stall wait times, crowd levels, parking exits, or seat upgrades. I'm here to help you have the best experience!"


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
