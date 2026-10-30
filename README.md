# NetPriority

NetPriority is a Quality of Service (QoS) network priority management system.

This repository currently contains a **starter setup** that verifies connectivity
between a React + TypeScript frontend and a Python FastAPI backend. The full QoS
traffic-control system is not yet implemented — this is the foundation.

---

## Tech Stack

| Layer    | Technology                                  |
| -------- | ------------------------------------------ |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS   |
| Backend  | Python, FastAPI, Uvicorn                    |

## Project Structure

```
NetPriority/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── core/
│   │   │   └── config.py     # Project metadata + CORS settings
│   │   ├── routers/
│   │   │   ├── info.py       # GET /  – project information
│   │   │   └── health.py     # GET /api/health – health status
│   │   └── main.py           # FastAPI app entry point
│   ├── requirements.txt
│   └── venv/                 # Python virtual environment (created in setup)
├── frontend/                 # React + Vite frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── ConnectionStatus.tsx
│   │   │   └── CheckButton.tsx
│   │   ├── api.ts            # API client (real fetch requests)
│   │   ├── App.tsx           # Main UI
│   │   ├── main.tsx          # React entry point
│   │   └── index.css         # Tailwind directives
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
└── README.md
```

## Prerequisites

- **Python 3.10+** — <https://www.python.org/downloads/>
- **Node.js 18+** (includes npm) — <https://nodejs.org/>

Verify both are installed:

```powershell
python --version
node --version
npm --version
```

---

## Setup

You need **two terminals** — one for the backend, one for the frontend.

### 1. Backend setup (Terminal 1)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend setup (Terminal 2)

```powershell
cd frontend
npm install
```

---

## Running the Application

### Start the backend (Terminal 1)

```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API base URL: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>

### Start the frontend (Terminal 2)

```powershell
cd frontend
npm run dev
```

- Frontend URL: <http://localhost:5173>

### Verify the connection

1. Open <http://localhost:5173> in your browser.
2. Click **Check Backend Connection**.
3. The status indicator turns green and shows the backend response.

---

## API Endpoints

| Method | Path          | Description                                                   |
| ------ | ------------- | ------------------------------------------------------------- |
| GET    | `/`           | Returns project name, description, version, and status.       |
| GET    | `/api/health` | Returns backend health status, service name, and timestamp.   |

### Example responses

`GET /`

```json
{
  "name": "NetPriority",
  "description": "NetPriority is a Quality of Service (QoS) ...",
  "version": "0.1.0",
  "status": "running"
}
```

`GET /api/health`

```json
{
  "status": "healthy",
  "service": "NetPriority Backend",
  "timestamp": "2026-10-30T12:00:00.000000+00:00"
}
```

---

## Configuration

### CORS

CORS is configured for `http://localhost:5173` (the Vite dev server) in
`backend/app/core/config.py`. Update `BACKEND_CORS_ORIGINS` if you run the
frontend on a different origin.

### API base URL

The frontend defaults to `http://localhost:8000`. To override, create
`frontend/.env.local`:

```
VITE_API_BASE=http://localhost:8000
```
