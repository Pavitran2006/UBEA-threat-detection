# 🛡️ UBEA Threat Detection — User & Entity Behavior Analytics

A production-ready full-stack User and Entity Behavior Analytics (UEBA) application built with Python FastAPI, featuring real-time event telemetry, heuristic risk evaluation, scikit-learn Isolation Forest anomaly detection, JWT authentication, and a dark neon glassmorphism SOC dashboard.

🔗 **GitHub Repository:** [github.com/Pavitran2006/UBEA-threat-detection](https://github.com/Pavitran2006/UBEA-threat-detection)

---

## ✨ Features

- 🔐 **JWT Authentication & RBAC:** Secure cookie session handling with bcrypt password hashing, token revocation, and role-based access control (Admin / Analyst / User).
- 🧠 **ML Anomaly Detection (Isolation Forest):** Unsupervised outlier detection using scikit-learn to detect structural deviations in login timing, velocity, frequency, and device/location access.
- ⚡ **Real-Time Risk Scoring Engine:** Heuristic evaluation engine identifying rapid successive logins, new devices, unexpected geolocations, and brute-force indicators.
- 📊 **Security Operations Center (SOC) Dashboard:** Real-time metrics, live threat feeds, geolocation attack maps, and interactive security charts.
- 🚨 **Alert Management & Feedback:** Security alert tracking with severity levels, alert status, and ML feedback loops.
- 🔑 **Secure Password Recovery & OTP:** Time-limited tokenized reset flows with rate limiting and optional SMTP delivery.
- 🎨 **Glassmorphism Dark UI:** Cyberpunk SOC interface with backdrop blur filters, responsive layouts, and telemetry animations.
- 🏥 **Health Monitoring & Cloud Ready:** Built-in `/health` check with database connectivity diagnostics and 1-click cloud deployment.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph Frontend [FastAPI / Jinja2 Glassmorphism UI]
        Landing[Home & Landing Page]
        AuthUI[Login, Signup & OTP Views]
        Dash[SOC Security Monitoring Dashboard]
        AdminUI[Admin Console & User Management]
    end

    subgraph Backend [FastAPI Application Core]
        Auth[JWT & Bcrypt Security Layer]
        Routes[REST API & View Routers]
        ML[Isolation Forest & Risk Engine]
        ORM[SQLAlchemy ORM Layer]
        Health[/health Diagnostic Monitoring]
    end

    subgraph Persistence [Production Database Support]
        DB[(PostgreSQL / MySQL / SQLite)]
    end

    Frontend -->|HTTPS / REST API| Routes
    Routes --> Auth
    Routes --> ML
    Routes --> ORM
    ORM --> DB
    Health --> DB
```

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy 2.0, PyJWT, Passlib (Bcrypt), Pydantic v2
- **Machine Learning:** Scikit-learn (Isolation Forest), Pandas, NumPy, Joblib
- **Frontend:** Jinja2 HTML5 Templates, CSS3 Glassmorphism (`soc.css`, `background.css`), Chart.js, FontAwesome
- **Database Support:** Managed PostgreSQL (Render, Supabase, Neon), MySQL 8+, SQLite
- **Deployment:** Render (`render.yaml`), Procfile, Docker

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- (Optional) PostgreSQL or MySQL

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Pavitran2006/UBEA-threat-detection.git
cd UBEA-threat-detection

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your configuration:

```bash
cp .env.example .env
```

Key environment variables:
- `DATABASE_URL`: Connection URL (e.g., `postgresql://user:pass@host:5432/db` or `sqlite:///ueba.db`)
- `SECRET_KEY`: Strong cryptographic key for JWT and session signing
- `ENABLE_SIMULATION`: Set to `false` for production (default), or `true` for live simulated events

### 3. Launch the Server

```bash
python run_server.py
```
Or directly with Uvicorn:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your web browser.

---

## 🧪 Automated Testing

Execute the automated integration test suite:

```bash
pytest tests/test_monolith.py -v
```

Tests verify:
- Health diagnostics endpoint (`/health`, `/api/health`)
- Landing and authentication page rendering
- Login validation and credential rejection
- Route protection and access control
- Anomaly detection pipeline cold-start safety

---

## ☁️ Deployment

### Option A: Render (1-Click Blueprint)

The repository includes a ready-to-deploy [`render.yaml`](render.yaml) specification configuring:
- Web service with automatic Python environment and startup command
- Managed PostgreSQL database with automatic `DATABASE_URL` linking
- Health check monitoring on `/health`

To deploy:
1. Push repository to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com), choose **New → Blueprint**.
3. Select your repository. Render will automatically provision the PostgreSQL instance and web service.

### Option B: Procfile Dynos / Containers

A [`Procfile`](Procfile) is provided:
```text
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## 👨‍💻 Author

**Pavitran Anand**  
- GitHub: [github.com/Pavitran2006](https://github.com/Pavitran2006)  
- LinkedIn: [linkedin.com/in/pavitrananand](https://linkedin.com/in/pavitrananand)  