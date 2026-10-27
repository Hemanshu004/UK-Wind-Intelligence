# UK Wind Forecast Analytics

A full-stack software engineering platform for analyzing UK national-level wind energy generation and supporting purchasing decisions relevant to January 2026.

---

## 1. Project Overview

This platform is designed to provide actionable intelligence regarding UK wind power generation outturn and forecast accuracy:
- **Actual Generation**: Monitored via the official Elexon BMRS `FUELHH` dataset (filtered specifically to `fuelType = WIND`).
- **Forecast Generation**: Evaluated via the official Elexon BMRS `WINDFOR` dataset (incorporating `startTime`, `publishTime`, and `generation`).
- **Decision Context**: Enables energy traders and system analysts to review forecast deviations and inform power purchasing decisions.

> **Academic / Assessment Note**: AI tools will be acknowledged in the final project documentation.

---

## 2. Technology Stack

- **Frontend**: React (JavaScript) + Vite
- **Backend**: Python 3.9+ with FastAPI & Uvicorn
- **Data Source**: Official [Elexon BMRS API](https://bmrs.elexon.co.uk/api-documentation/endpoint)
- **Containerization**: Docker (planned)
- **Deployment**: Vercel / Heroku (or alternative cloud host)

---

## 3. Monorepo Structure

```text
.
├── backend/                  # Python + FastAPI backend service
│   ├── .dockerignore         # Docker build exclusion rules for backend
│   ├── .env.example          # Local backend environment template
│   ├── Dockerfile            # Production Python 3.11-slim container image
│   ├── main.py               # FastAPI application & API endpoints
│   ├── requirements.txt      # Python dependencies (FastAPI, httpx, pytest, etc.)
│   ├── schemas.py            # Pydantic schemas for data validation and API responses
│   ├── services/             # Core backend business logic and API client
│   │   ├── __init__.py
│   │   ├── elexon_client.py  # Async Elexon BMRS API client (FUELHH & WINDFOR streams)
│   │   ├── forecast_analysis.py # Policy cutoff selection, temporal alignment & metrics
│   │   └── wind_data.py      # Wind data validation, normalisation, and parsing
│   └── tests/                # Automated test suite
│       ├── __init__.py
│       ├── test_backend.py   # Data-access & endpoint unit tests
│       └── test_forecast_analysis.py # Policy selection, alignment & metrics tests
├── docs/                     # Architecture and documentation
│   ├── architecture.md       # High-level architecture, containerization & deployment
│   └── elexon-api-investigation.md # Empirical Elexon API investigation report
├── frontend/                 # React + Vite frontend client
│   ├── .dockerignore         # Docker build exclusion rules for frontend
│   ├── Dockerfile            # Multi-stage production build (Node 20 -> Nginx Alpine)
│   ├── nginx.conf            # Nginx web server & reverse-proxy configuration
│   ├── public/               # Static assets
│   ├── src/                  # React source components
│   │   ├── components/       # Dashboard components (Charts, KPIs, Table, Controls)
│   │   ├── services/         # Reusable API client (api.js)
│   │   ├── App.jsx           # Main application dashboard component
│   │   └── main.jsx          # Vite React mounting point
│   ├── index.html            # Application HTML shell
│   └── package.json          # Frontend dependencies & scripts
├── .dockerignore             # Root Docker exclusion rules
├── .env.example              # Root environment configuration template
├── .gitignore                # Git exclusions (venv, node_modules, secrets)
├── docker-compose.yml        # Multi-container orchestration (Frontend + Backend)
└── README.md                 # Project overview, setup, and deployment guide
```

---

## 4. Setup & Installation Guide

### Prerequisites
- **Node.js** (v18 or higher recommended; verified on v24)
- **npm** (v9 or higher recommended; verified on v11)
- **Python** (v3.9 or higher; verified on v3.9.6)

---

### 4.1 Backend Setup (Python Virtual Environment)

The backend uses a standard Python virtual environment (`venv`) to isolate dependencies without polluting the global environment.

1. **Navigate to the project root:**
   ```bash
   cd /path/to/RentAi
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv backend/venv
   ```

3. **Activate the virtual environment:**
   - **macOS / Linux:**
     ```bash
     source backend/venv/bin/activate
     ```
   - **Windows (Command Prompt):**
     ```cmd
     backend\venv\Scripts\activate.bat
     ```
   - **Windows (PowerShell):**
     ```powershell
     backend\venv\Scripts\Activate.ps1
     ```

4. **Install backend dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

5. **Configure environment variables:**
   ```bash
   cp backend/.env.example backend/.env
   ```

6. **Run automated unit tests:**
   ```bash
   backend/venv/bin/python -m pytest backend/tests/ -v
   ```
   All 75 unit tests run against mocked Elexon responses to guarantee 100% deterministic test execution without external network dependence.

7. **Run the FastAPI development server:**
   ```bash
   backend/venv/bin/uvicorn backend.main:app --reload --port 8000
   ```
   Or from within the `backend/` directory:
   ```bash
   cd backend && uvicorn main:app --reload --port 8000
   ```

8. **Verify backend endpoints:**
   Interactive API documentation (Swagger UI) is available at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### 4.2 Backend API Endpoints

The backend exposes clean, validated endpoints for wind generation data:

#### `GET /health`
Health check verifying the service status.
```bash
curl http://localhost:8000/health
```
Response:
```json
{
  "status": "ok",
  "service": "UK Wind Forecast Analytics API",
  "version": "0.1.0"
}
```

#### `GET /api/v1/wind/actuals`
Retrieves actual wind generation outturn from Elexon's `FUELHH` stream filtered to `fuelType=WIND`.

- **Query Parameters**:
  - `start_date` (*string*, required, format: `YYYY-MM-DD`): First settlement date, inclusive.
  - `end_date` (*string*, required, format: `YYYY-MM-DD`): Last settlement date, inclusive.
- **Example**:
  ```bash
  curl "http://localhost:8000/api/v1/wind/actuals?start_date=2026-01-01&end_date=2026-01-02"
  ```
- **Response**:
  ```json
  {
    "start_date": "2026-01-01",
    "end_date": "2026-01-02",
    "fuel_type": "WIND",
    "unit": "MW",
    "record_count": 96,
    "records": [
      {
        "start_time": "2026-01-01T00:00:00Z",
        "settlement_date": "2026-01-01",
        "settlement_period": 1,
        "generation": 14210,
        "fuel_type": "WIND",
        "publish_time": null
      }
    ]
  }
  ```

#### `GET /api/v1/wind/forecasts`
Retrieves wind generation forecasts from Elexon's `WINDFOR` stream for the requested delivery window.

- **Query Parameters**:
  - `start_date` (*string*, required, format: `YYYY-MM-DD`): First delivery date, inclusive.
  - `end_date` (*string*, required, format: `YYYY-MM-DD`): Last delivery date, inclusive.
- **Semantics & Revision Handling**:
  - Automatically expands the publication query window to retrieve forecasts published starting 3 days prior (`start_date - 3 days`), capturing all day-ahead and earlier forecast publications.
  - Preserves **all historical forecast revisions** per delivery interval (un-deduplicated) so the frontend or analytical engine can apply configurable purchasing cutoffs (e.g. Day-Ahead D-1 12:00 UTC).
- **Example**:
  ```bash
  curl "http://localhost:8000/api/v1/wind/forecasts?start_date=2026-01-01&end_date=2026-01-02"
  ```
- **Response**:
  ```json
  {
    "start_date": "2026-01-01",
    "end_date": "2026-01-02",
    "publication_window_start": "2025-12-29T00:00:00Z",
    "publication_window_end": "2026-01-03T23:59:59Z",
    "unit": "MW",
    "record_count": 1152,
    "records": [
      {
        "start_time": "2026-01-01T00:00:00Z",
        "publish_time": "2025-12-30T10:00:00Z",
        "generation": 13950
      }
    ]
  }
  ```

#### `GET /api/v1/wind/analysis`
Evaluates wind forecast accuracy against actual outturn for a delivery date range (inclusive), applying configurable purchasing cutoff policies and half-hourly to hourly temporal alignment.

- **Query Parameters**:
  - `start_date` (*string*, required, format: `YYYY-MM-DD`): First delivery date, inclusive.
  - `end_date` (*string*, required, format: `YYYY-MM-DD`): Last delivery date, inclusive.
  - `policy` (*string*, optional, default: `"day_ahead"`):
    - `"day_ahead"`: Selects latest forecast published at or before $(D-1)$ at `day_ahead_cutoff_time` UTC (default `12:00` UTC). *Note: Configurable project assumption based on Day-Ahead auction timings, not an official Elexon market rule.*
    - `"rolling"`: Selects latest forecast published at or before `startTime - lead_time_hours`.
    - `"latest_before_delivery"`: Operational benchmark selecting latest forecast published at or before `startTime`.
  - `lead_time_hours` (*float*, optional): Required when `policy="rolling"`. Positive number of hours (e.g. `24`, `12`, `4`, `1`).
  - `day_ahead_cutoff_time` (*string*, optional, default: `"12:00"`): Cutoff time in `HH:MM` UTC for `"day_ahead"` policy.
- **Temporal Alignment**:
  - Calculates hourly actual generation as the arithmetic mean of the two half-hourly `FUELHH` readings: $(H_1 + H_2) / 2.0$.
  - Requires both half-hourly readings; missing one marks the interval `INCOMPLETE_ACTUAL` and excludes it from accuracy metrics.
- **Accuracy Metrics & Sign Convention**:
  - **Signed Error**: $\text{Forecast} - \text{Actual}$. Positive = over-forecasting (buyer over-purchased / long); negative = under-forecasting.
  - **MAE**: Mean Absolute Error in MW.
  - **RMSE**: Root Mean Squared Error in MW.
  - **Bias**: Mean Signed Error in MW.
  - **MAPE**: Mean Absolute Percentage Error (%), zero actuals excluded from denominator. Returns `null` if no non-zero actuals exist.
  - **Coverage**: $\text{Matched Intervals} / \text{Expected Intervals}$ (reported as ratio and percentage).
- **Example Request**:
  ```bash
  curl "http://localhost:8000/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01&policy=day_ahead"
  ```
- **Example Response**:
  ```json
  {
    "start_date": "2026-01-01",
    "end_date": "2026-01-01",
    "policy": "day_ahead",
    "cutoff_rule": "Day-ahead D-1 at 12:00 UTC (configurable project assumption; not an official market rule)",
    "lead_time_hours": null,
    "expected_interval_count": 24,
    "matched_interval_count": 24,
    "missing_forecast_count": 0,
    "missing_actual_count": 0,
    "coverage_ratio": 1.0,
    "coverage_percentage": 100.0,
    "metrics": {
      "mae": 4233.58,
      "rmse": 4283.02,
      "bias": 4233.58,
      "mape": 27.74,
      "unit": "MW",
      "bias_interpretation": "Positive bias indicates over-forecasting (forecast > actual); negative indicates under-forecasting."
    },
    "records": [
      {
        "delivery_start_time": "2026-01-01T00:00:00Z",
        "settlement_date": "2026-01-01",
        "settlement_period_start": 1,
        "settlement_period_end": 2,
        "cutoff_time": "2025-12-31T12:00:00Z",
        "forecast_generation": 19563.0,
        "forecast_publish_time": "2025-12-31T11:30:00Z",
        "actual_generation": 13814.5,
        "half_hourly_actuals": [13756.0, 13873.0],
        "error": 5748.5,
        "absolute_error": 5748.5,
        "status": "MATCHED"
      }
    ],
    "data_notes": null
  }
  ```

---

### 4.3 Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the Vite development server:**
   ```bash
   npm run dev
   ```
   The application will be accessible at [http://localhost:5173](http://localhost:5173).

4. **Verify production build:**
   ```bash
   npm run build
   ```

---

### 4.4 Docker Containerized Setup

The project includes production-ready Docker configurations with a complete multi-container orchestration via Docker Compose.

```
                  +-----------------------------------+
                  |            Host Browser           |
                  +-----------------+-----------------+
                                    |
                    http://localhost:3000 (UI & /api proxy)
                                    v
+-----------------------------------+-----------------------------------+
| Docker Compose Environment                                            |
|                                                                       |
|   +---------------------------------------------------------------+   |
|   | frontend service (rentai-frontend)                            |   |
|   | - Multi-stage build (node:20-alpine -> nginx:alpine)          |   |
|   | - Static SPA serving with fallback routing                    |   |
|   | - Reverse proxy /api/ & /health -> http://backend:8000        |   |
|   | - Port 3000:80                                                |   |
|   +-------------------------------+-------------------------------+   |
|                                   | (Docker internal network)         |
|                                   v                                   |
|   +---------------------------------------------------------------+   |
|   | backend service (rentai-backend)                              |   |
|   | - Python 3.11-slim, non-root user (appuser)                   |   |
|   | - FastAPI + Uvicorn server                                    |   |
|   | - Health check: curl/urllib GET /health                       |   |
|   | - Port 8000:8000                                              |   |
|   +---------------------------------------------------------------+   |
+-----------------------------------------------------------------------+
```

#### Prerequisites
- Docker Engine 20.10+ or Docker Desktop 4.0+
- Docker Compose v2.0+

#### Quickstart: Build & Launch
From the repository root directory, run:
```bash
docker compose up --build -d
```

#### Accessing Local Services
- **Web Application Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Backend API Direct Endpoint**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check (Direct)**: [http://localhost:8000/health](http://localhost:8000/health)
- **Backend Health Check (Proxied via Frontend)**: [http://localhost:3000/health](http://localhost:3000/health)
- **Nginx Liveness Probe**: [http://localhost:3000/nginx-health](http://localhost:3000/nginx-health)

#### Stopping the Application
To stop and remove running containers and their network:
```bash
docker compose down
```

To stop containers and purge unused volumes:
```bash
docker compose down -v
```

#### Viewing Container Logs
```bash
# Follow logs for all services
docker compose logs -f

# Follow backend service logs only
docker compose logs -f backend

# Follow frontend service logs only
docker compose logs -f frontend
```

#### Troubleshooting Docker Setup
1. **Port Conflicts**:
   - The frontend is mapped to host port `3000` (container port `80`) to avoid conflicts with common host web servers. If port `3000` is already in use, update the port mapping in `docker-compose.yml` (e.g. `"3001:80"`).
   - If backend port `8000` is already occupied by a local process, modify the backend port mapping in `docker-compose.yml` (e.g. `"8080:8000"`).
2. **Browser Network Resolution**:
   - Browsers execute on the host machine and cannot resolve Docker internal service names such as `http://backend:8000`. The frontend Nginx container automatically proxies all requests beginning with `/api/` and `/health` directly to `http://backend:8000` over the internal Docker network, ensuring seamless operation without host DNS resolution issues or CORS errors.
3. **Clean Rebuild**:
   - To force a clean build without Docker layer caches:
     ```bash
     docker compose build --no-cache
     docker compose up -d
     ```

---

### 4.5 Production Deployment Preparation

The project is architected for decoupled deployment across cloud platforms:

#### 1. Deployment Topology
- **Frontend**: Deployable as a static Single Page Application (SPA) on modern edge CDN platforms such as **Vercel**, **Netlify**, or **Cloudflare Pages**.
- **Backend**: Deployable as a containerized Python service on platforms such as **Render**, **Heroku**, **Fly.io**, or **AWS ECS / App Runner**.

#### 2. Environment Configuration Matrix

| Variable | Scope | Target Environment | Default / Example | Purpose |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | Frontend | Build-time (Vercel) | `https://uk-wind-backend.onrender.com` | Backend API base URL baked into static bundle. Leave empty `""` for Docker Nginx proxying. |
| `PORT` | Backend | Runtime (Render/Heroku) | `8000` | Port on which Uvicorn binds and listens. |
| `CORS_ORIGINS` | Backend | Runtime (Render/Heroku) | `https://uk-wind-intelligence.vercel.app` | Comma-separated list of allowed frontend origins for CORS. |
| `ELEXON_API_BASE_URL` | Backend | Runtime | `https://data.elexon.co.uk/bmrs/api/v1` | Official Elexon BMRS endpoint base URL. |
| `HTTP_TIMEOUT` | Backend | Runtime | `30.0` | HTTP request timeout in seconds for upstream queries. |

> [!IMPORTANT]
> **Security & Secrets Hygiene**:
> - Never store secrets or sensitive credentials in `VITE_*` environment variables, as they are permanently compiled into public client-side JavaScript bundles.
> - The modern Elexon BMRS Insights Solution API (`/datasets/FUELHH/stream` and `/datasets/WINDFOR/stream`) is open data and does not require an API key or bearer token.
> - Do not enable wildcard CORS (`*`) in production. Explicitly set `CORS_ORIGINS` to the exact deployed frontend origin.

#### 3. Production Health Check & Monitoring
- **Health Check URL**: `GET /health`
- **Expected Status**: HTTP 200 OK
- **Expected Payload**:
  ```json
  {
    "status": "ok",
    "service": "UK Wind Forecast Analytics API",
    "version": "0.1.0"
  }
  ```
- Cloud orchestrators (Render, Heroku, Kubernetes) should be configured to probe `GET /health` with an initial delay of 5 seconds and an interval of 15 seconds.

---

## 5. Current Implementation Status

| Component | Status | Details |
|---|---|---|
| Monorepo Structure | ✅ Complete | Clean layout (`frontend/`, `backend/`, `docs/`) |
| Git Configuration | ✅ Complete | Excludes venv, dependencies, build outputs, and `.env` secrets |
| Backend Core & Health | ✅ Complete | FastAPI service with verified `GET /health` endpoint |
| API Investigation | ✅ Complete | Empirically verified FUELHH (actuals) & WINDFOR (forecasts) for Jan 2026 |
| Backend Data-Access Layer | ✅ Complete | Robust client for Elexon BMRS `/stream` endpoints with retries, Pydantic schemas, error handling |
| Normalized API Endpoints | ✅ Complete | `GET /api/v1/wind/actuals` and `GET /api/v1/wind/forecasts` with inclusive dates & revision preservation |
| Forecast Selection & Alignment | ✅ Complete | Configurable policies (`day_ahead`, `rolling`, `latest_before_delivery`), D-1 12:00 UTC assumption, arithmetic mean alignment |
| Accuracy Metrics & Analysis API | ✅ Complete | `GET /api/v1/wind/analysis` providing MAE, RMSE, Bias, MAPE, coverage, and per-interval evaluation |
| Automated Backend Tests | ✅ Complete | 75 unit tests passing (`pytest`), mocked HTTP responses for deterministic CI/CD verification |
| UK Wind Intelligence Dashboard | ✅ Complete | Production React SPA with KPI cards, Forecast vs Actual chart, Error profile, data table & CSV export |
| Docker Containerization | ✅ Complete | Multi-stage Dockerfiles (`backend/Dockerfile`, `frontend/Dockerfile`), Nginx reverse proxy, `.dockerignore` files, `docker-compose.yml` with health checks |
| Deployment Preparation | ✅ Complete | Decoupled deployment architecture documented (Vercel + Render/Heroku), runtime vs build-time environment matrix, CORS specification |




