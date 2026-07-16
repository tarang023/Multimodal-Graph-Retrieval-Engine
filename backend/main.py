from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging

# ── Logging ────────────────────────────────────────────────────────────────────
# Configure before any module imports so all loggers inherit this format.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

# Load .env for local development (no-op when env vars are already set, e.g. in Docker)
load_dotenv()

from api.routes import router as api_router

app = FastAPI(
    title="Multimodal Financial Graph-RAG Assistant",
    description=(
        "FastAPI backend that accepts receipt images, redacts PII with OpenCV, "
        "extracts structured financial data via Gemini 1.5 Flash, and exposes "
        "a Q&A endpoint backed by Neo4j + Qdrant (graph-RAG)."
    ),
    version="0.2.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict to the Next.js dev server in development; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["Health"])
def read_root():
    return {
        "message": "Welcome to the Multimodal Financial Graph-RAG Assistant API",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
