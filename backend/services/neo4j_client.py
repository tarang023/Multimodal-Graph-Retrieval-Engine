import os
import logging
import uuid
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
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
        date: $date
    })
    
    // 4. Create the relationships
    CREATE (emp)-[:SUBMITTED]->(exp)
    CREATE (exp)-[:BELONGS_TO]->(cat)
    
    RETURN exp.id AS saved_expense_id
    """
    
    parameters = {
        "user_id": user_id,
        "category": category,
        "expense_id": expense_id,
        "vendor": vendor,
        "amount": amount,
        "date": date
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
    """
    Queries Neo4j for the employee's budget information.
    """
    # Stubbed fallback / future work
    return "Budget context for employee: $500 remaining for Travel."
