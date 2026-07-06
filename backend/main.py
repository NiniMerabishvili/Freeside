"""
Freeside API — FastAPI Backend
Main application entry point with CORS, Supabase client, and router includes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
from pathlib import Path
from dotenv import load_dotenv

# Explicit path so .env is always found regardless of working directory
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

app = FastAPI(
    title="Freeside API",
    description="Cognitive energy-aware productivity backend",
    version="0.1.0",
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Supabase client (service role — bypasses RLS for backend operations)
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_SERVICE_KEY", ""),
)

# Include route modules
from routes import energy, tasks, copilot, calendar, research, profile, sleep, integrations, goals

app.include_router(energy.router, prefix="/energy", tags=["energy"])
app.include_router(sleep.router, prefix="/sleep", tags=["sleep"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(goals.router, prefix="/goals", tags=["goals"])
app.include_router(copilot.router, prefix="/copilot", tags=["copilot"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "freeside-api"}
