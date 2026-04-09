# VenueFlow — AI-Powered Smart Venue Management Assistant

## Overview
VenueFlow is an AI-powered smart venue management assistant designed for large-scale sporting events, simulated for a stadium called "Apex Arena". It provides real-time crowd analytics, wait time tracking, a Gemini-powered AI concierge, and parking coordination.

## Architecture
- **Backend:** Flask (Python) — serves both the API and static frontend files
- **Frontend:** Vanilla JavaScript, HTML5, CSS3 with an interactive SVG stadium map
- **AI:** Google Gemini 1.5 Flash (via `google-generativeai`) — optional AI concierge
- **All files live in:** `venue-flow/`

## Project Layout
```
venue-flow/
├── app.py          # Flask backend & API server (main entry point)
├── app.js          # Frontend application logic
├── index.html      # Main single-page application
├── styles.css      # UI styling (Aurora dark theme)
├── test_app.py     # Backend tests (pytest)
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Running the App
- The app runs on port 5000 via: `cd venue-flow && python app.py`
- Configured as a webview workflow named "Start application"

## Key API Endpoints
- `GET /` — serves the frontend SPA
- `GET /health` — health check
- `GET /api/crowd` — crowd density data
- `GET /api/waits` — facility wait times
- `GET /api/parking` — parking zone data
- `POST /api/chat` — AI concierge (Gemini or fallback)

## Environment Variables
- `GEMINI_API_KEY` — Optional. Enables the Gemini AI concierge. Without it, a rule-based fallback is used.
- `PORT` — Optional. Defaults to 5000.

## Dependencies
Managed via pip in `requirements.txt`:
- flask, flask-cors, python-dotenv, gunicorn
- google-generativeai (Gemini AI)
- pytest (testing)

## Deployment
Configured for autoscale deployment using gunicorn:
`gunicorn --bind=0.0.0.0:5000 --reuse-port --chdir=venue-flow app:app`
