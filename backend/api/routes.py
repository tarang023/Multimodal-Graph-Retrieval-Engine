from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import shutil
import os
import logging

from services.ocr_pii_redactor import sanitize_and_save_ocr
from services.gemini_extractor import extract_financial_data
from services.qdrant_client import search_policy
from services.neo4j_client import save_expense_to_graph, get_budget_context
from services.gemini import generate_financial_explanation

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Storage directories ───────────────────────────────────────────────────────
RAW_DIR       = os.path.join("uploads", "raw")        # uploads/raw/
SANITIZED_DIR = os.path.join("uploads", "sanitized")  # uploads/sanitized/

os.makedirs(RAW_DIR,       exist_ok=True)
os.makedirs(SANITIZED_DIR, exist_ok=True)


# ── Request / Response models ─────────────────────────────────────────────────

class ReceiptData(BaseModel):
    """Mirrors the schema returned by /upload so the frontend can pass it back."""
    vendor:   str   = Field(default="", description="Merchant / vendor name")
    amount:   float = Field(default=0.0, description="Total transaction amount")
    date:     str   = Field(default="",  description="Transaction date (ISO-8601)")
    category: str   = Field(default="",  description="Expense category")


class AskRequest(BaseModel):
    """
    Body expected by POST /ask.

    Example JSON:
    {
        "receipt_data": {"vendor": "Starbucks", "amount": 5.50, "date": "2024-01-10", "category": "Food & Dining"},
        "question": "Is this expense reimbursable?",
        "employee_id": "EMP-001"
    }
    """
    receipt_data: Optional[ReceiptData] = Field(default_factory=ReceiptData, description="Structured receipt data returned by /upload")
    question:     str                   = Field(..., min_length=1, description="Natural-language question about the expense")
    employee_id:  str                   = Field(default="anonymous",  description="Employee identifier")


class AnalyzeRequest(BaseModel):
    """
    Body expected by POST /analyze.
    """
    expense_data: ReceiptData = Field(..., description="Extracted expense data from /upload")
    question:     str         = Field(..., description="User's natural language question")
    employee_id:  str         = Field(default="anonymous", description="Employee identifier")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload a receipt image for PII redaction and data extraction")
async def upload_receipt(file: UploadFile = File(...)):
    """
    Pipeline:
      1. Validate MIME type.
      2. Save raw upload  →  uploads/raw/{original_filename}
      3. Run PII redactor →  uploads/sanitized/{original_filename}
      4. Call Gemini      →  structured JSON extraction.
      5. Return extracted data + file paths.
    """
    allowed_image_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}

    logger.info("═" * 60)
    logger.info("[UPLOAD] New request received")
    logger.info(f"  filename     : {file.filename}")
    logger.info(f"  content_type : {file.content_type}")
    logger.info(f"  size (header): {file.size}")

    # ── MIME validation ───────────────────────────────────────────────────────
    if file.content_type not in allowed_image_types and file.content_type != "application/pdf":
        logger.warning(f"  ✗ Rejected — unsupported content type: '{file.content_type}'")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                "Please upload an image (JPEG, PNG, WEBP) or a PDF."
            ),
        )

    original_filename = file.filename or "upload"

    # ── STEP 1: Save raw upload → uploads/raw/ ────────────────────────────────
    raw_filename = f"raw_{original_filename}"
    raw_path     = os.path.join(RAW_DIR, raw_filename)
    logger.info(f"  [STEP 1] Saving raw file → {raw_path}")

    with open(raw_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    saved_size = os.path.getsize(raw_path)
    logger.info(f"  ✓ Raw file saved — {saved_size} bytes at '{raw_path}'")

    if saved_size == 0:
        logger.error("  ✗ Raw file is 0 bytes — aborting pipeline.")
        raise HTTPException(status_code=400, detail="Uploaded file appears to be empty.")

    # ── Image processing branch ───────────────────────────────────────────────
    if file.content_type in allowed_image_types:
        sanitized_filename = f"sanitized_{original_filename}"
        sanitized_path     = os.path.join(SANITIZED_DIR, sanitized_filename)

        # ── STEP 2: PII Redaction (OCR) → uploads/sanitized/ ──────────────────
        logger.info(f"  [STEP 2] Running OCR PII redactor ...")
        logger.info(f"    input  : {raw_path}")
        logger.info(f"    out_dir: {SANITIZED_DIR}")

        sanitized_result = sanitize_and_save_ocr(raw_path, SANITIZED_DIR)

        if not sanitized_result:
            logger.warning(
                f"  ✗ sanitize_and_save_ocr FAILED for '{raw_path}'. "
                "Falling back to raw image for Gemini extraction."
            )
            path_for_extraction = raw_path
            sanitized_filename  = None
        else:
            san_size = os.path.getsize(sanitized_result)
            logger.info(f"  ✓ Sanitised image saved — {san_size} bytes at '{sanitized_result}'")
            path_for_extraction = sanitized_result
            sanitized_filename = os.path.basename(sanitized_result)

        # ── STEP 3: Gemini data extraction ───────────────────────────────────
        logger.info(f"  [STEP 3] Calling Gemini extractor on '{path_for_extraction}' ...")
        extracted_data = extract_financial_data(path_for_extraction)

        if not extracted_data:
            logger.error("  ✗ Gemini extraction returned None — returning 502.")
            raise HTTPException(
                status_code=502,
                detail=(
                    "Failed to extract financial data from the image. "
                    "Ensure GEMINI_API_KEY is set and the image is legible."
                ),
            )

        logger.info(f"  ✓ Extraction complete: {extracted_data}")
        logger.info("[UPLOAD] Pipeline finished successfully")
        logger.info("═" * 60)

        return {
            "message":        "Receipt processed successfully.",
            "raw_file":       f"uploads/raw/{raw_filename}",
            "sanitized_file": f"uploads/sanitized/{sanitized_filename}" if sanitized_filename else None,
            "data":           extracted_data,
        }

    # ── PDF branch (stub — future work) ──────────────────────────────────────
    logger.info("  PDF detected — extraction not yet implemented.")
    return {
        "message":        "PDF uploaded. Text extraction not yet implemented.",
        "raw_file":       f"uploads/raw/{raw_filename}",
        "sanitized_file": None,
        "data":           None,
    }


@router.post("/ask", summary="Ask the AI assistant a question about an expense")
async def ask_assistant(request: AskRequest):
    """
    Accepts structured receipt data + a natural-language question and returns
    a reasoning response.

    Send a JSON body:
    ```json
    {
        "receipt_data": {
            "vendor": "Starbucks",
            "amount": 5.50,
            "date": "2024-01-10",
            "category": "Food & Dining"
        },
        "question": "Is this expense reimbursable?",
        "employee_id": "EMP-001"
    }
    ```
    Make sure the request Content-Type header is **application/json**.
    """
    # TODO: budget_context  = get_budget_context(request.employee_id)
    # TODO: policy_context  = get_policy_context(request.receipt_data.category)
    # TODO: answer = reason_about_expense(
    #     request.receipt_data.model_dump(), budget_context, policy_context, request.question
    # )

    # ── Stub response (replace with Gemini reasoning call) ───────────────────
    receipt = request.receipt_data
    answer = (
        f"The expense of ${receipt.amount:.2f} at '{receipt.vendor}' "
        f"on {receipt.date or 'unknown date'} "
        f"(category: {receipt.category or 'unspecified'}) "
        "appears to be within budget and complies with company policy. "
        f"[Employee: {request.employee_id}]"
    )

    return {
        "answer":      answer,
        "receipt_data": receipt.model_dump(),
        "question":    request.question,
    }


@router.post("/analyze", summary="Save expense and retrieve policies for reasoning")
async def analyze_expense(request: AnalyzeRequest):
    """
    Orchestrates the Graph DB and Vector DB integration:
    1. Saves the structured expense to Neo4j.
    2. Uses the expense category to query Qdrant for relevant policies.
    """
    logger.info("═" * 60)
    logger.info("[ANALYZE] New analyze request received")
    
    expense_dict = request.expense_data.model_dump()
    
    # ── STEP 1: Save to Neo4j ──────────────────────────────────────────────────
    graph_success = save_expense_to_graph(request.employee_id, expense_dict)
    if not graph_success:
        logger.warning("Failed to save expense to Graph DB (Neo4j might be unreachable).")
        
    # ── STEP 2: Retrieve policies from Qdrant ─────────────────────────────────
    # We use the category as the query to find relevant policies
    search_query = request.expense_data.category
    logger.info(f"Searching Qdrant for policies related to: '{search_query}'")
    
    retrieved_policies = search_policy(search_query)
    
    # ── STEP 3: Retrieve budget/graph context from Neo4j ─────────────────────
    logger.info(f"Retrieving budget context for employee: '{request.employee_id}'")
    graph_context = {"budget": get_budget_context(request.employee_id)}
    
    # ── STEP 4: Call Gemini for Reasoning ──────────────────────────────────────
    try:
        explanation = generate_financial_explanation(
            question=request.question,
            expense_json=expense_dict,
            policy_context=retrieved_policies,
            graph_context=graph_context
        )
    except Exception as e:
        logger.error(f"Gemini reasoning failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"AI Reasoning failed: {str(e)}"
        )
    
    # ── STEP 5: Return collected context & reasoning ──────────────────────────
    logger.info("[ANALYZE] Pipeline finished successfully")
    return {
        "explanation": explanation,
        "sources": retrieved_policies
    }
