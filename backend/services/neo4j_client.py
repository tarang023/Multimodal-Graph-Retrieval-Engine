import os
import logging
import uuid
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

try:
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
except Exception as e:
    logger.error(f"Failed to initialize Neo4j driver: {e}")
    driver = None
    

def save_expense_to_graph(user_id: str, expense_data: dict) -> bool:
    """
    Creates/merges Employee and Category nodes, creates an Expense node,
    and links them: (Employee)-[:SUBMITTED]->(Expense)-[:BELONGS_TO]->(Category).
    
    Returns True on success, False on failure.
    """
    if not driver:
        logger.error("Neo4j driver not initialized. Cannot save to graph.")
        return False
        
    vendor = expense_data.get("vendor", "Unknown")
    amount = float(expense_data.get("amount", 0.0))
    date = expense_data.get("date", "1970-01-01")
    category = expense_data.get("category", "Uncategorised")
    
    tax_amount = float(expense_data.get("tax_amount", 0.0))
    document_type = expense_data.get("document_type", "unknown")
    payment_method = expense_data.get("payment_method", "unknown")
    currency = expense_data.get("currency", "")
    merchant_location = expense_data.get("merchant_location", "")
    additional_notes = expense_data.get("additional_notes", "")
    line_items = expense_data.get("line_items", [])
    
    # Generate a unique ID for the expense
    expense_id = str(uuid.uuid4())
    
    query = """
    // 1. Ensure the employee exists
    MERGE (emp:Employee {id: $user_id})
    
    // 2. Ensure the category exists
    MERGE (cat:Category {name: $category})
    
    // 3. Create the unique expense node
    CREATE (exp:Expense {
        id: $expense_id,
        vendor: $vendor,
        amount: $amount,
        tax_amount: $tax_amount,
        date: $date,
        document_type: $document_type,
        payment_method: $payment_method,
        currency: $currency,
        merchant_location: $merchant_location,
        additional_notes: $additional_notes
    })
    
    // 4. Create the relationships
    CREATE (emp)-[:SUBMITTED]->(exp)
    CREATE (exp)-[:BELONGS_TO]->(cat)
    
    // 5. Create LineItems if they exist
    FOREACH (item IN $line_items |
        CREATE (li:LineItem {
            id: randomUUID(),
            description: item.description,
            amount: item.amount
        })
        CREATE (exp)-[:INCLUDES_ITEM]->(li)
    )
    
    RETURN exp.id AS saved_expense_id
    """
    
    parameters = {
        "user_id": user_id,
        "category": category,
        "expense_id": expense_id,
        "vendor": vendor,
        "amount": amount,
        "date": date,
        "tax_amount": tax_amount,
        "document_type": document_type,
        "payment_method": payment_method,
        "currency": currency,
        "merchant_location": merchant_location,
        "additional_notes": additional_notes,
        "line_items": line_items
    }
    
    try:
        with driver.session() as session:
            result = session.run(query, parameters)
            record = result.single()
            if record:
                logger.info(f"Successfully saved expense {record['saved_expense_id']} to Neo4j.")
                return True
            else:
                logger.warning("Query executed but no expense ID returned.")
                return False
    except Exception as e:
        logger.error(f"Failed to execute Cypher query: {e}")
        return False

def get_budget_context(employee_id: str) -> str:
    
    if not driver:
        return "Neo4j driver not initialized. Cannot retrieve budget context."
        
    query = """
    MATCH (emp:Employee {id: $employee_id})-[:SUBMITTED]->(exp:Expense)-[:BELONGS_TO]->(cat:Category)
    WITH cat.name AS category, sum(exp.amount) AS total_spent
    RETURN category, total_spent
    ORDER BY total_spent DESC
    """
    
    try:
        # for now it is fixed
        budget_limit = 1000.0
        context_lines = [f"Budget context for employee {employee_id}:", f"Total budget limit per category: ${budget_limit:.2f}"]
        
        with driver.session() as session:
            result = session.run(query, {"employee_id": employee_id})
            records = list(result)
            
            if not records:
                return f"No expenses found for employee {employee_id}. Full budget of ${budget_limit:.2f} is available across all categories."
                
            for record in records:
                category = record["category"]
                spent = record["total_spent"]
                remaining = budget_limit - spent
                
                status = "OVER BUDGET" if remaining < 0 else "under budget"
                context_lines.append(
                    f" - {category}: Spent ${spent:.2f}, Remaining: ${remaining:.2f} ({status})"
                )
                
            return "\n".join(context_lines)
            
    except Exception as e:
        logger.error(f"Failed to retrieve budget context: {e}")
        return f"Error retrieving budget context: {e}"
