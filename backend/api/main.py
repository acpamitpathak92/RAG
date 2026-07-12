from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import documents, health, ingest, query

app = FastAPI(title="Advanced RAG System for Issue Retrieval")

# Allows the React dev server (running on a different port, e.g. 5173) to call this API.
# Local-only tool, so a permissive dev-friendly policy is fine here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(documents.router)

# Simple static test UI (no build step), served at "/" if present. Optional: the
# React app in frontend/ (run separately via `npm run dev`) is the primary UI now,
# so a missing ui/ folder shouldn't prevent the API from starting.
# main.py lives at backend/api/main.py, so parent.parent.parent is the project root.
UI_DIR = Path(__file__).resolve().parent.parent.parent / "ui"
if UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
