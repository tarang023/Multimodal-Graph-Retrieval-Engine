import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Initialize Google GenAI Client
_api_key = os.environ.get("GEMINI_API_KEY", "")
if _api_key:
    client = genai.Client(api_key=_api_key)
else:
    client = None
    logger.warning("GEMINI_API_KEY not set. Gemini API calls will fail.")

def generate_financial_explanation(question: str, expense_json: dict, policy_context: list, graph_context: dict) -> str:
    """
    Uses Gemini to reason about an expense given budget and policy context.
    """
    if not client:
        raise ValueError("GEMINI_API_KEY is not configured.")

    system_prompt = (
        "You are an expert corporate financial auditor. You will be provided with extracted receipt data, "
        "the company expense policy, and the employee's budget context. Answer the user's question clearly "
        "and step-by-step. Determine if the expense is compliant or flagged, and explicitly cite the policy "
        "rule that justifies your decision."
    )

    prompt_content = f"""
    User Question: {question}
    
    Receipt Data:
    {json.dumps(expense_json, indent=2)}
    
    Relevant Company Policies:
    {json.dumps(policy_context, indent=2)}
    
    Employee Graph Context (Neo4j):
    {json.dumps(graph_context, indent=2)}
    """
    
    logger.info("Calling Gemini 3.5 Flash for RAG reasoning...")
    
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        )
    )
    
    if not response.text:
        raise ValueError("Gemini returned an empty response.")
        
    return response.text
