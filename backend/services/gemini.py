import google.generativeai as genai
import os
import json

# genai.configure(api_key=os.environ["GEMINI_API_KEY"])
# model = genai.GenerativeModel('gemini-1.5-flash-latest')

def extract_receipt_data(image_path: str) -> dict:
    """
    Uses Gemini to extract structured JSON data from a receipt image.
    """
    # Stub
    return {
        "vendor": "Stub Vendor",
        "amount": 0.0,
        "date": "2023-01-01",
        "category": "Stub"
    }

def reason_about_expense(receipt_data: dict, budget_context: str, policy_context: str, question: str) -> str:
    """
    Uses Gemini to reason about an expense given budget and policy context.
    """
    # Stub
    return "Approved based on stub logic."
