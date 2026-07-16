# ── Stage: runtime ────────────────────────────────────────────────────────────
# python:3.10-slim keeps the image small while providing a full CPython runtime.
# We use the *headless* OpenCV wheel (opencv-python-headless) so we don't need
# any X11 / display libraries inside the container.
FROM python:3.10-slim

# Metadata
LABEL maintainer="Multimodal Financial Graph-RAG Assistant"
LABEL description="FastAPI backend – receipt PII redaction + Gemini extraction"

# ── System dependencies ────────────────────────────────────────────────────────
# pytesseract requires tesseract-ocr, and opencv-python-headless requires libgl1.
RUN apt-get update && apt-get install -y tesseract-ocr libgl1 && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────────
# Copy requirements first so Docker can cache this layer independently of code
# changes – rebuild is only triggered when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Application source ─────────────────────────────────────────────────────────
COPY . .

# Ensure the uploads directory exists inside the container
RUN mkdir -p uploads

# ── Runtime configuration ──────────────────────────────────────────────────────
# GEMINI_API_KEY must be provided at runtime via:
#   docker run -e GEMINI_API_KEY=... or docker-compose environment / secrets.
# Never hard-code secrets in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
