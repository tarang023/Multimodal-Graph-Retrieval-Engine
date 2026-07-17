from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import os
import json
import logging
import traceback
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


_api_key = os.environ.get("GEMINI_API_KEY", "")
if _api_key:
    _client = genai.Client(api_key=_api_key)
    logger.info("[gemini_extractor] google.genai client created ✓")
else:
    _client = None
    logger.warning("[gemini_extractor] GEMINI_API_KEY is not set — extraction will fail.")

 
_MODEL = "gemini-3.5-flash"

#Response schema 
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor":   {"type": "string"},
        "amount":   {"type": "number"},
        "tax_amount": {"type": "number"},
        "date":     {"type": "string"},
        "category": {"type": "string"},
        "document_type": {"type": "string"},
        "payment_method": {"type": "string"},
        "is_itemized": {"type": "boolean"},
        "currency": {"type": "string"},
        "merchant_location": {"type": "string"},
        "additional_notes": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "amount": {"type": "number"}
                },
                "required": ["description", "amount"]
            }
        }
    },
    "required": ["vendor", "amount", "date", "category", "document_type", "is_itemized", "currency"]
}

_EXTRACTION_PROMPT = (
    """
    "You are an expert Forensic Accountant. Carefully analyze the attached financial document image.\n\n"
    "Step 1: Classify the document. \n"
    "- If it has 'Previous Balance', 'Payments', 'Statement Date' or is a bank ledger, classify as 'credit_card_statement'.\n"
    "- If it is a B2B bill with an 'Invoice Number' and 'Due Date', classify as 'invoice'.\n"
    "- If it is a store/restaurant printout with a subtotal and tax, classify as 'itemized_receipt'.\n\n"
    "Step 2: Extract the data exactly as seen into the required fields:\n"
    "vendor: the name of the merchant, company, or bank issuing the document\n"
    "amount: the total transaction or statement amount as a decimal number\n"
    "tax_amount: the total tax amount if visible\n"
    "date: the statement date or transaction date in ISO-8601 format (YYYY-MM-DD)\n"
    "category: the most appropriate expense category (e.g., Cloud Computing, Travel, Meals)\n"
    "document_type: your classification ('credit_card_statement', 'invoice', or 'itemized_receipt')\n"
    "payment_method: e.g. Visa, Cash, Apple Pay (if visible)\n"
    "is_itemized: true if there are distinct line items or individual charges listed\n"
    "currency: e.g. USD, EUR, GBP\n"
    "merchant_location: city or full address if visible\n"
    "additional_notes: catch-all for extra context\n"
    "line_items: array of objects with 'description' (string) and 'amount' (number) for every individual charge or item seen on the document.\n\n"
    "Return ONLY a raw, valid JSON object matching this exact schema. Do not include markdown formatting blocks like 
    json.
    """
)


def extract_financial_data(image_path: str) -> Optional[Dict[str, Any]]:
   
    logger.info(" [GEMINI EXTRACTOR] START ━━━")
    logger.info(f"  image_path : {image_path}")
    logger.info(f"  model      : {_MODEL}")

    # ── Pre-flight checks 
    if not _client:
        logger.error("FAILED — GEMINI_API_KEY is not set in environment.")
        return None

    if not os.path.exists(image_path):
        logger.error(f"FAILED — File does not exist: '{image_path}'")
        return None

    file_size = os.path.getsize(image_path)
    logger.info(f"  file size  : {file_size} bytes")
    if file_size == 0:
        logger.error(" FAILED — File is empty (0 bytes).")
        return None

    uploaded_file = None

    try:
        # ── Step 1: Upload to Gemini Files API 
        logger.info("[1/3] Uploading image to Gemini Files API ...")
        with open(image_path, "rb") as f:
            uploaded_file = _client.files.upload(
                file=f,
                config=types.UploadFileConfig(mime_type="image/png"),
            )
        logger.info(f"Uploaded — name: {uploaded_file.name}  uri: {uploaded_file.uri}")

        # ── Step 2: Generate with JSON mode 
        logger.info(f"[2/3] Calling {_MODEL} (JSON mode, temp=0.2) ...")
        response = _client.models.generate_content(
            model=_MODEL,
            contents=[
                types.Part.from_uri(file_uri=uploaded_file.uri, mime_type="image/png"),
                _EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_RESPONSE_SCHEMA,
                temperature=0.2,
            ),
        )

        # ── Step 3: Log exact raw response then parse  
        logger.info("  [3/3] Received response from Gemini.")
        
        if not response.text:
            logger.error("FAILED — Gemini returned an empty response body.")
            return None

        raw = json.loads(response.text)
        extracted: Dict[str, Any] = {
            "vendor":   str(raw.get("vendor", "Unknown")),
            "amount":   float(raw.get("amount") or 0.0),
            "tax_amount": float(raw.get("tax_amount") or 0.0),
            "date":     str(raw.get("date", "")),
            "category": str(raw.get("category", "Uncategorised")),
            "document_type": str(raw.get("document_type", "unknown")),
            "payment_method": str(raw.get("payment_method", "unknown")),
            "is_itemized": bool(raw.get("is_itemized", False)),
            "currency": str(raw.get("currency", "")),
            "merchant_location": str(raw.get("merchant_location", "")),
            "additional_notes": str(raw.get("additional_notes", "")),
            "line_items": [
                {
                    "description": str(item.get("description", "")),
                    "amount": float(item.get("amount") or 0.0)
                } for item in raw.get("line_items", []) if isinstance(item, dict)
            ]
        }

        logger.info(f"Parsed result : {extracted}")
        logger.info("━━━ [GEMINI EXTRACTOR] SUCCESS ━━━")
        return extracted

    except genai_errors.APIError as exc:
       
        raw_response = str(exc)
        logger.error(f"GEMINI API ERROR — exact raw response:")
        logger.error(f"  {raw_response}")

        return None

    except Exception as exc:
        logger.error(f"UNEXPECTED EXCEPTION: {type(exc).__name__}")
        logger.error(f"  {exc}")
        logger.error(traceback.format_exc())
        return None

    finally:
     
        if uploaded_file:
            try:
                _client.files.delete(name=uploaded_file.name)
                logger.info(f"Cleaned up uploaded file: {uploaded_file.name}")
            except Exception:
                pass   