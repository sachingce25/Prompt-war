# 🏟️ VenueFlow — AI-Powered Smart Venue Assistant

VenueFlow is a real-time, AI-driven venue management assistant designed for large-scale sporting events. It combines crowd analytics, intelligent routing, and a Gemini-powered AI concierge to deliver a premium event experience.

![VenueFlow](https://img.shields.io/badge/Powered_by-Google_Gemini-4285F4?style=for-the-badge&logo=google&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask)
![Cloud Run](https://img.shields.io/badge/Deploy-Cloud_Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)

## ✨ Features

- **Smart Crowd Navigation** — Interactive SVG venue map with real-time crowd density heatmap
- **Live Wait Times** — Auto-refreshing wait times for gates, food, restrooms, and parking
- **AI Concierge** — Gemini-powered chat assistant with full venue context
- **Smart Parking** — Exit coordination, staggered departure plans, and QR codes
- **Personal Planner** — Custom schedule, reminders, and in-app notifications

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [Google Gemini API Key](https://aistudio.google.com/apikey)

### Local Development

```bash
# 1. Clone or navigate to the project
cd venue-flow

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\Activate  # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Gemini API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 5. Run the server
python app.py
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

### Running Tests

```bash
pytest test_app.py -v
```

## 🐳 Docker

```bash
# Build
docker build -t venueflow .

# Run
docker run -p 8080:8080 -e GEMINI_API_KEY=your_key_here venueflow
```

## ☁️ Deploy to Google Cloud Run

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy venueflow \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=your_key_here \
  --port 8080
```

## 📡 API Endpoints

| Method | Endpoint       | Description                          |
|--------|---------------|--------------------------------------|
| GET    | `/health`      | Health check for Cloud Run           |
| GET    | `/api/crowd`   | Crowd density data per zone          |
| GET    | `/api/waits`   | Wait times for all facilities        |
| GET    | `/api/parking`  | Parking occupancy and exit plans     |
| POST   | `/api/chat`    | AI concierge chat (Gemini-powered)   |

### Chat API Example

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Where is the nearest restroom?"}'
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│           Frontend (index.html)             │
│   Tailwind CSS · SVG Maps · Vanilla JS      │
└──────────────────┬──────────────────────────┘
                   │ fetch()
┌──────────────────▼──────────────────────────┐
│           Flask Backend (app.py)            │
│   /api/crowd · /api/waits · /api/chat       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         Google Gemini API (Flash)           │
│   Context-aware venue AI concierge          │
└─────────────────────────────────────────────┘
```

## 📁 File Structure

```
venue-flow/
├── index.html         # Full frontend (all tabs, SVG map, chat UI)
├── app.py             # Flask backend with API routes
├── test_app.py        # 5 pytest tests
├── requirements.txt   # Python dependencies
├── Dockerfile         # Cloud Run deployment
├── .env.example       # Environment variable template
└── README.md          # This file
```

## 🔒 Security

- API keys loaded from environment variables (never hardcoded)
- Input sanitization on all user inputs
- CORS configured for API routes
- Control character stripping and length limits

## ♿ Accessibility

- ARIA labels on all interactive elements
- Keyboard navigation support
- Sufficient color contrast ratios
- Screen reader friendly structure

## 📄 License

MIT License — built for the Google Cloud hackathon.
