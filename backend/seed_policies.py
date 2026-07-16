import os
from dotenv import load_dotenv
import logging

# Load environment variables (like GEMINI_API_KEY) before importing our services
load_dotenv()

# Configure logging so we can see the output
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

from services.qdrant_client import initialize_policies

MOCK_COMPANY_POLICIES = """
Travel & Accommodation Policy:
Employees are allowed a maximum of $1000 per night for hotel accommodations in major cities, and $500 in other locations.
Flights must be booked in economy class unless the flight duration exceeds 8 hours, in which case business class is permitted.

Food & Dining Policy:
The daily meal allowance is $75 per day. Alcohol is not a reimbursable expense under any circumstances.
Meals involving clients (Business Meals) have a higher limit of $150 per person, provided a receipt and list of attendees is included.

Office Supplies Policy:
Employees may expense up to $200 per year for home office supplies (e.g., monitors, keyboards, ergonomic chairs).
Any single item exceeding $100 requires pre-approval from a direct manager.

Transportation Policy:
Uber, Lyft, and taxi rides are reimbursable for travel to and from the airport, or between business meeting locations.
Daily commuting from home to the primary office is not reimbursable.
"""

if __name__ == "__main__":
    logger.info("Starting database seed...")
    initialize_policies(MOCK_COMPANY_POLICIES)
    logger.info("Done seeding Qdrant database.")
