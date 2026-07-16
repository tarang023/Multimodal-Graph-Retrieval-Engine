"""
Gemini financial data extractor.
Uses the NEW google-genai SDK (google.genai) — the old google.generativeai is deprecated.
Install: pip install google-genai
"""
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import os
import json
import logging
import traceback
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── SDK initialisation ────────────────────────────────────────────────────────
_api_key = os.environ.get("GEMINI_API_KEY", "")
if _api_key:
    _client = genai.Client(api_key=_api_key)
    logger.info("[gemini_extractor] google.genai client created ✓")
else:
    _client = None
    logger.warning("[gemini_extractor] GEMINI_API_KEY is not set — extraction will fail.")

# ── Model name ────────────────────────────────────────────────────────────────
# gemini-2.5-flash is the current latest model as of mid-2026.
# The user-chosen name is kept exactly as-is here; the API will reject it with
# a clear NOT_FOUND error if the name is wrong.
_MODEL = "gemini-3.5-flash"

# ── Response schema ───────────────────────────────────────────────────────────
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor":   {"type": "string"},
        "amount":   {"type": "number"},
        "date":     {"type": "string"},
        "category": {"type": "string"},
    },
    "required": ["vendor", "amount", "date", "category"],
}

_EXTRACTION_PROMPT = (
    "You are a financial-document OCR assistant. "
    "Carefully read the attached receipt or financial document image and extract "
    "the following four fields:\n"
    "  • vendor   – the name of the merchant or vendor\n"
    "  • amount   – the total transaction amount as a decimal number (no currency symbol)\n"
    "  • date     – the transaction date in ISO-8601 format (YYYY-MM-DD) if possible\n"
    "  • category – the most appropriate expense category "
    "(e.g. 'Food & Dining', 'Travel', 'Office Supplies', 'Accommodation', 'Fuel', etc.)\n\n"
    "Return ONLY a valid JSON object with exactly these four keys. "
    "Do not include explanations, markdown fences, or any extra text."
)


def extract_financial_data(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Uploads the image via the Gemini Files API, then calls the model with
    enforced JSON output. Returns a validated dict or None on any failure.
    """
    logger.info("━━━ [GEMINI EXTRACTOR] START ━━━")
    logger.info(f"  image_path : {image_path}")
    logger.info(f"  model      : {_MODEL}")

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    if not _client:
        logger.error("  ✗ FAILED — GEMINI_API_KEY is not set in environment.")
        return None

    if not os.path.exists(image_path):
        logger.error(f"  ✗ FAILED — File does not exist: '{image_path}'")
        return None

    file_size = os.path.getsize(image_path)
    logger.info(f"  file size  : {file_size} bytes")
    if file_size == 0:
        logger.error("  ✗ FAILED — File is empty (0 bytes).")
        return None

    uploaded_file = None

    try:
        # ── Step 1: Upload to Gemini Files API ────────────────────────────────
        logger.info("  [1/3] Uploading image to Gemini Files API ...")
        with open(image_path, "rb") as f:
            uploaded_file = _client.files.upload(
                file=f,
                config=types.UploadFileConfig(mime_type="image/png"),
            )
        logger.info(f"  ✓ Uploaded — name: {uploaded_file.name}  uri: {uploaded_file.uri}")

        # ── Step 2: Generate with JSON mode ───────────────────────────────────
        logger.info(f"  [2/3] Calling {_MODEL} (JSON mode, temp=0.1) ...")
        response = _client.models.generate_content(
            model=_MODEL,
            contents=[
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="image/png"),
                _EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.1,
            ),
        )

        # ── Step 3: Log exact raw response then parse ─────────────────────────
        logger.info("  [3/3] Received response from Gemini.")
        logger.info(f"  ── RAW GEMINI RESPONSE (exact) ──────────────────────")
        logger.info(f"  {response.text}")
        logger.info(f"  ─────────────────────────────────────────────────────")

        if not response.text:
            logger.error("  ✗ FAILED — Gemini returned an empty response body.")
            return None

        raw = json.loads(response.text)
        extracted: Dict[str, Any] = {
            "vendor":   str(raw.get("vendor", "Unknown")),
            "amount":   float(raw.get("amount") or 0.0),
            "date":     str(raw.get("date", "")),
            "category": str(raw.get("category", "Uncategorised")),
        }

        logger.info(f"  ✓ Parsed result : {extracted}")
        logger.info("━━━ [GEMINI EXTRACTOR] SUCCESS ━━━")
        return extracted

    except genai_errors.APIError as exc:
        # ── All Gemini API errors come through here in google.genai ──────────
        # Log the EXACT raw response so nothing is hidden.
        raw_response = str(exc)
        logger.error(f"  ✗ GEMINI API ERROR — exact raw response:")
        logger.error(f"  {raw_response}")

        # Also attempt to parse the structured error for a friendlier hint
        code    = getattr(exc, 'code',    None) or getattr(exc, 'status_code', '???')
        status  = getattr(exc, 'status',  None) or ''
        message = getattr(exc, 'message', None) or raw_response

        logger.error(f"  ── Parsed details ───────────────────────────────────")
        logger.error(f"    HTTP status : {code}")
        logger.error(f"    Error status: {status}")
        logger.error(f"    Message     : {message}")

        # Specific hints per error type
        if 'API_KEY_INVALID' in raw_response or code == 400:
            logger.error(
                "  → Hint: The API key was rejected.\n"
                "  → Make sure GEMINI_API_KEY in .env is the correct key from\n"
                "  → https://aistudio.google.com/app/apikey\n"
                "  → Then restart the server so dotenv reloads it."
            )
        elif 'PERMISSION_DENIED' in raw_response or code == 403:
            logger.error(
                "  → Hint: The key exists but lacks permission.\n"
                "  → Enable 'Generative Language API' at https://console.cloud.google.com/apis"
            )
        elif 'RESOURCE_EXHAUSTED' in raw_response or code == 429:
            logger.error(
                "  → Hint: Rate limit or daily quota exceeded.\n"
                "  → Wait a minute and retry, or upgrade your Gemini plan."
            )
        elif 'NOT_FOUND' in raw_response or code == 404:
            logger.error(
                f"  → Hint: Model '{_MODEL}' was not found.\n"
                "  → Check valid model names at https://ai.google.dev/gemini-api/docs/models"
            )
        elif 'UNAVAILABLE' in raw_response or code == 503:
            logger.error(
                "  → Hint: Gemini is temporarily unavailable.\n"
                "  → Check https://status.cloud.google.com and retry."
            )
        return None

    except json.JSONDecodeError as exc:
        logger.error(
            f"  ✗ JSON PARSE ERROR — Gemini returned non-JSON output.\n"
            f"  ── RAW GEMINI RESPONSE (exact) ──────────────────────\n"
            f"  {exc.doc}\n"
            f"  ─────────────────────────────────────────────────────\n"
            f"    Error position: line {exc.lineno}, col {exc.colno}\n"
            f"    Message       : {exc.msg}"
        )
        return None

    except Exception as exc:
        logger.error(f"  ✗ UNEXPECTED EXCEPTION: {type(exc).__name__}")
        logger.error(f"  ── Full exception (exact) ───────────────────────────")
        logger.error(f"  {exc}")
        logger.error(f"  ── Traceback ────────────────────────────────────────")
        logger.error(traceback.format_exc())
        return None

    finally:
        # Clean up the uploaded file from Gemini Files API to save quota
        if uploaded_file:
            try:
                _client.files.delete(name=uploaded_file.name)
                logger.info(f"  ✓ Cleaned up uploaded file: {uploaded_file.name}")
            except Exception:
                pass  # non-critical
