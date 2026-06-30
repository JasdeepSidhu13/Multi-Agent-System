import random
from multiprocessing.pool import rebuild_exc
import string
import pandas as pd
import numpy as np
import os
import time
import re
import ast
from sqlalchemy.sql import text
from datetime import datetime, timedelta, date
from typing import Dict, List, Union, Literal, Optional
from sqlalchemy import create_engine, Engine
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from enum import Enum
from dataclasses import dataclass, field
import json
import asyncio
import logfire
import logging
from pydantic_ai.models.instrumented import InstrumentationSettings, instrument_model
from pydantic_ai import Agent


logfire.configure(service_name="beavers-choice", send_to_logfire=False)
file_handler = logging.FileHandler("agent_trace.log")
formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
logger = logging.getLogger("logfire")
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)


# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the Munder Difflin database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_customer_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the customer delivery date (from beaver's choice to customer) based on the requested order quantity and
    a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_customer_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_customer_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 2
    else:
        days = 3

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date AND item_name IS NOT NULL 
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row) for row in result]

########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################
"""Decided to use pydantic_ai for my agent framework: https://ai.pydantic.dev/ as it appears to be the best choice
 for enterprise level agentic systems."""

# Set up and load your env parameters and instantiate your model.
load_dotenv()
model_1 = OpenAIChatModel(model_name='gpt-5-mini',
                        provider=OpenAIProvider(api_key=os.getenv("UDACITY_OPENAI_API_KEY"),
                                                base_url="https://openai.vocareum.com/v1"))

instr = InstrumentationSettings(include_content=True,
    include_binary_content=False,
    event_mode="full",
    version=2)
model = instrument_model(model_1, instr)

model_2 = OpenAIChatModel(model_name='gpt-5-nano',
                        provider=OpenAIProvider(api_key=os.getenv("UDACITY_OPENAI_API_KEY"),
                                                base_url="https://openai.vocareum.com/v1"))

model_nano = instrument_model(model_2, instr)


# Set up your agents and create an orchestration agent that will manage them.
### PYDANTIC MODELS ###
class Address(BaseModel):
    attention: str
    street_line: str
    city: str
    province: str
    country: str
    postal_code: str

class SupplierDelivery(BaseModel):
    item_name: str
    starting_date: date
    quantity: int
    supplier_delivery_date: date

class CustomerDelivery(BaseModel):
    item_name: str
    starting_date: date
    quantity: int
    customer_delivery_date: date

class OrderRecord(BaseModel):
    item_name: str
    transaction_type: Literal["stock_orders", "sales"]
    quantity: int
    price: float
    date: Union[str, datetime]
    transaction_id: int

class AssignAgent(str, Enum):
    inventory_agent = "inventory_agent"
    quoting_agent = "quoting_agent"
    ordering_agent = "ordering_agent"
    general_agent = "general_agent"

class OrchestrationCall(BaseModel):
    """
    orchestrator provides this to a helper agent.
    """
    goal: str = Field(...,  description="what is the goal the agent is looking to accomplish?")
    notes_for_agent: str = Field(...,  description="More details relevant to accomplishing the goals.")

class OrchestrationResponse(BaseModel):
    """
    orchestrator agent provides this back to the customer.
    """
    internal_response: str = Field(..., description="A description of what the system carried out to address the customer request. ")
    response_to_client: str = Field(..., description="A final customer friendly response")

class InventoryItemSummary(BaseModel):
    item_name: str
    stock: int
    unit_price: float
    value: float

class InventoryNeeded(BaseModel):
    item_name: str = Field(..., decriptipon="Name of the item")
    quantity: int = Field(..., description="The number of items needed to stock order for inventory to meet customer request")

class InventoryItem(BaseModel):
    item_name: str = Field(..., decriptipon="Name of the item")
    quantity: int = Field(..., description="The number of items needed to stock order for inventory to meet customer request")

class InventoryListNeed(BaseModel):
    needed: List[InventoryItem]

class TopSellingProduct(BaseModel):
    item_name: str
    total_units: int
    total_revenue: float

class FinancialReport(BaseModel):
    as_of_date: str
    cash_balance: float
    inventory_value: float
    total_assets: float
    inventory_summary: List[InventoryItemSummary] = Field(default_factory=list)
    top_selling_products: List[TopSellingProduct] = Field(default_factory=list)

class StockLevel(BaseModel):
    item_name: str
    current_stock: float
    record_found: bool

class SharedState(BaseModel):
    goals_of_request: List[str] = Field(default_factory=list)
    request_date: Optional[date] = None
    items_names_requested_from_customer: List[str] = Field(default_factory=list)
    items_names_requested_match_from_financial_report: List[str] = Field(default_factory=list)
    quantity_of_items_requested: List[int] = Field(default_factory=list)
    quantity_of_items_stock_order:  List[InventoryNeeded]  = Field(default_factory=list)
    desired_delivery_date: Optional[date] = None
    shipping_address: Optional[Address] = None
    inventory_levels_of_all_products: Dict[str, float] = Field(default_factory=dict)
    stock_level_specific_items: List[StockLevel] = Field(default_factory=list)
    quote_history: List[str] = Field(default_factory=list)
    cash_balance: Optional[float] = None
    financial_report: Optional[FinancialReport] = None
    supplier_delivery_date: List[SupplierDelivery] = Field(default_factory=list)
    customer_delivery_date: List[CustomerDelivery] = Field(default_factory=list)
    orders_completed: List[OrderRecord] = Field(default_factory=list)
    response_to_customer: Optional[str] = None
    process_completed: Optional[bool] = None


class EmailDetails(BaseModel):
    goals_of_request: List[str] = Field(default_factory=list)
    request_date: Optional[date] = None
    items_names_requested_from_customer: List[str] = Field(default_factory=list)
    items_names_requested_match_from_financial_report: List[str] = Field(default_factory=list)
    quantity_of_items_requested: List[int] = Field(default_factory=list)
    desired_delivery_date: Optional[date] = None

class WorkerOutput(BaseModel):
    goal:  Optional[str] = None
    accomplishment: str = Field(...,  description="what was done to help accomplish this goal")
    report: str = Field(...,  description="A paragraph reporting relevant details to manager.")

@dataclass
class Deps:
    state: SharedState

orchestration_agent = Agent(model,
                            deps_type=Deps,
                            retries=3,
                            system_prompt=(
                                f"""You are an agent tasked with managing Beaver's Choice Paper Company's customer
                                requests. 
                             
                                IMPORTANT:
                                - Always check State for the needed information before using a tool. The
                                information may already be available.
                                - Unless mentioned here never ask customer clarifications, confirmations, or more 
                                details.
                                - The customer never has the option to choose shipping priority. Never ask.
                                - There is no cost to customer or supplier for shipping. 
                                - Always breakdown the price to the customer before tax, the tax amount, and total. 
                                    Tax is HST at 13%.
                                - There is no taxes to consider (they are already included) when ordering from 
                                supplier with a stock_order.
                                                                
                                ORDERING DECISION:
                                - If all items requested can be delivered on time, place the order and return to the 
                                customer confirmation and the pricing quote
                                - If one or more items cannot be delivered in time, place the order for the viable items
                                 and ask in the response to the customer if the customer wants to
                                    a) Cancel this order entirely
                                    b) Complete the order for the delayed item as well, and ship all at once. 
                                    c) Cancel the delayed item only
                                - If the customer requested one or more item that cannot be ordered or supplied to the 
                                customer (because it doesn't exist in inventory or from our supplier) response by 
                                completing order for any viable items and inform the customer that you completed the 
                                order for products you carry, but you do not carry the invalid item. Offer them the 
                                option to cancel the entire order you already placed.
                            
                                
                                You never need additional details like shipping priority options or final confirmation 
                                from the customer or supplier to complete requested orders or transactions that you can 
                                accurately fulfil. 
                                To complete an sales order you need to have completed the following:
                                - Ensure product is available with inventory manager
                                - confirm with the ordering manager that the order can arrive in time to the customer
                                - Have a price set by the quoting manager 
                                - Successfully have the ordering manager record the sale
                                Before responding check state for details you have collected. Decipher whether the 
                                request is for a order (then complete if possible to do so accurately), quote, or just 
                                information and respond accordingly. 
                                                                
                                TOOLS:
                                1) finalize_output
                                2) record_email_details
                                3) get_delivery_address
                                4) determine_stock_needs
                                5) call_inventory_manager
                                6) call_quoting_manager
                                7) call_ordering_manager
                                
                                
                                
                                ALWAYS FOLLOW THIS PLAN:
                                Step 1: call generate_financial_report_dict  with the request date.
                                Step 2: Call record_email_details on the original customer prompt.
                                Step 3: Call get_delivery_address
                                Step 4: Check inventory available, call inventory manager, request calling get_stock_level_item
                                Step 5: Call determine_stock_needs
                                Step 6: Set price to customer, call quoting manager
                                Step 7: Check delivery timing, call ordering manager. 
                                Step 8: If there is insufficient stock quantity to complete the sale order to customer, 
                                call ordering manager to order stock
                                Step 9: Reason which items are viable: can be delivered on or before desired delivery date. 
                                Step 10: Call ordering manager to place sales order for viable items 
                                Step 11: Summarize actions + results
                                WAIT UNTIL ALL STEPS ABOVE ARE FINISHED
                                Step 12: Return OrchestrationResponse
                                
                                Desired Output schema:
                                {json.dumps(OrchestrationResponse.model_json_schema(), indent=2)}"""
                            )
                            )


inventory_agent = Agent(model_nano,
                        deps_type=Deps,
                        retries=3,
                        system_prompt=f"""ROLE:
                                        You are the Inventory Agent for Beaver’s Choice Paper Company. Your job is to 
                                        answer inventory questions for a specific request date and then STOP. The
                                        User is an orchestration agent looking to get details needed to address a 
                                        customer query.
                                        
                                        IMPORTANT:
                                        Always check State for the needed information before using a tool. The
                                        information may already be available.
                                        
                                        OUTPUT:
                                        Return exactly one WorkerOutput with:
                                        - accomplishment: what you did (which tools, at a high level)
                                        - report: concise, user-safe facts for the orchestrator (matched quotes, totals, 
                                        assumptions, limits)
                                        - Desired output schema to follow: 
                                            {json.dumps(WorkerOutput.model_json_schema(), indent=2)}
                                        
                                        SINGLE-PASS PLAN (ABSOLUTELY NO LOOPING):
                                        1) Read goals from the prompt.
                                        2) Choose the MINIMUM set of tools to answer the goals.
                                        3) Choose the MINIMUM set of unique inputs for each tool to answer the goal.
                                        4) Check state if results needed are not already acquired - indicating tool has 
                                        already been run for this request before.
                                        5) If results are not in state, then call the chosen tool ONLY ONCE 
                                        per unique input.
                                        6) Summarize results into WorkerOutput and RETURN. Do not call more tools after 
                                        summarizing.
                                        
                                        DATE RULE:
                                        Never use your internal clock. Use the request date provided by the user/state.
                                        If an as_of_date is missing, extract it from the prompt or read it from 
                                        state.request_date. If neither exists, return a clear error in report.
                                        
                                        TOOLS:
                                        - get_inventory_for_date(as_of_date): Call only ONCE to get a full snapshot when 
                                        the user asks for overall availability or when multiple items are unknown and 
                                        matching is hard. Seldom necessary to use.
                                        - get_stock_level_item(item_name, as_of_date): Call only ONCE PER ITEM to check a 
                                        specific item. The preferred method of getting stock level details.
                                        
                                        
                                        IDEMPOTENCY & STATE AWARENESS:
                                        NEVER run the same tool twice with identical inputs just to try to change the 
                                        result. ALWAYS CHECK state before any call:
                                        - If state.inventory_levels_of_all_products is already populated for that 
                                        as_of_date, DO NOT call get_inventory_for_date again, just reuse it.
                                        - If state.stock_level_specific_items already includes (item_name, as_of_date), 
                                        DO NOT call get_stock_level_item again, just reuse it.
                                       
                                        
                                        WHEN TO USE WHICH TOOL:
                                        - The user asked 'what is in stock' or 'send me availability': use 
                                        get_inventory_for_date ONCE.
                                        - The user asked 'do you have X?' or 'how many Y?': use get_stock_level_item 
                                        ONCE PER ITEM.
                                        
                                        BOUNDS & BUDGET:
                                        - Respect any tool_call_budget in shared state if present.
                                        - Never re-try the same failing tool more than once; instead, write the error 
                                        into report and RETURN.
                                        
                                        OUTPUT CONTENT RULES:
                                        - If an item name isn’t found, say so in report and suggest the nearest internal 
                                        name if known.
                                        - If multiple items were requested, list each with stock found (or not found).
                                        - No internal errors, stack traces, or secrets in the report. Return only user 
                                        appropriate summaries.
                                        
                                        STOP CONDITIONS:
                                        MUST Return immediately after:
                                        - You’ve answered the inventory questions using the minimum tools.
                                        - A blocking error prevents further progress (e.g. missing request date) and 
                                        you’ve written a clear report.
                                        
                                        EXAMPLES:
                                        
                                        Example: A single item:
                                        Goal: 'Do you have 250 gsm cardstock on 2025-03-01?'                                        
                                        Plan: 
                                        1) get_stock_level_item('250 gsm cardstock', '2025-03-01') 
                                        2) summarize 
                                        3) RETURN
                                        
                                        Example B: broad availability:
                                        Goal: 'What do you have in stock on 2025-04-10?'
                                        Plan: 
                                        1) get_inventory_for_date('2025-04-10') 
                                        2) summarize  
                                        3) RETURN
                                        
                                        Example C: name mapping needed:
                                        Goal: 'Do you have heavyweight poster paper on 2025-02-12?'
                                        Plan: 
                                        1) get_stock_level_item(matched_name, '2025-02-12') 
                                        2) summarize 
                                        3) RETURN
                                        """
                                 )

quoting_agent = Agent(model_nano,
                      deps_type=Deps,
                      retries=3,
                      system_prompt=f"""
                                    ROLE:
                                    You are the Quoting Agent for Beaver’s Choice. Your job is to retrieve prior quote 
                                    context and relevant cash status for a specific request date, then STOP. The
                                    User is an orchestration agent looking to get details needed to address a customer 
                                    query.
                                    
                                    IMPORTANT:
                                    - Always check State for the needed information before using a tool. The
                                    information may already be available.
                                    - Always breakdown the price to the customer before tax, the tax amount, and total. 
                                    Tax is HST at 13%.
                                    - There is no taxes to consider (they are already included) when ordering from 
                                    supplier.
                                    
                                    OUTPUT:
                                    Return exactly one WorkerOutput with:
                                    - accomplishment: what you did (which tools, at a high level)
                                    - report: concise, user-safe facts for the orchestrator (matched quotes, totals, 
                                    assumptions, limits)
                                    - Desired output schema to follow: 
                                            {json.dumps(WorkerOutput.model_json_schema(), indent=2)}
                                    
                                    SINGLE-PASS PLAN (ABSOLUTELY NO LOOPING):
                                    1) Read the goals from the prompt and shared state (customer items, request date).
                                    2) Choose the MINIMUM set of tools that answer the goal.
                                    3) Choose the MINIMUM set of unique inputs for each tool to answer the goal.
                                    4) Check state if results needed are not already acquired - indicating tool has 
                                    already been run for this request before.
                                    5) If results are not in state, then call the chosen tool ONLY ONCE 
                                    per unique input.
                                    6) Summarize results in WorkerOutput and RETURN. Do not call more tools after 
                                    summarizing.
                                    
                                    DATE RULE:
                                    Never use your internal clock. Use the request date from the prompt or 
                                    state.request_date.If no date can be determined, write a clear error in report and 
                                    RETURN.
                                    
                                    TOOLS:
                                    - get_cash_balance_value(as_of_date): Call ONCE if you need to buy stock inventory 
                                    to check available cash.
                                    - search_quote_history_retrieve(search_terms, limit=5): Call at most ONCE per 
                                    distinct item/term-set to surface similar historical quotes that inform pricing 
                                    or messaging.
                                    
                                    IDEMPOTENCY & STATE AWARENESS:
                                    NEVER run the same tool twice with identical inputs just to try to change the 
                                    result. ALWAYS CHECK state before any call:
                                    - If state.cash_balance is already present for the same as_of_date, DO NOT call 
                                    get_cash_balance_value again, instead reuse it.
                                    - If state.quote_history already contains entries for the given search terms (or 
                                    for all requested items), DO NOT call search_quote_history_retrieve again, instead
                                    reuse them.
                                    
                                    WHEN TO USE WHICH TOOL:
                                    - use search_quote_history_retrieve when asked something like 'give me price 
                                    similar to *item*?' or 'have you ever quoted *item* before?', or you determine you 
                                    need comparables.
                                    - use get_cash_balance_value when you must order from supplier and need to draw upon
                                    cash reserves to do so.
                                    - If neither financial context nor history is relevant DO NOT call any tools. 
                                    Instead just return a brief report explaining no tools were needed.
                                    
                                    INPUTS:
                                    - Build search_terms from the best available names: prefer 
                                    state.items_names_requested_match_from_financial_report; otherwise fall back to 
                                    state.items_names_requested_from_customer.
                                    - Keep search_terms minimal and specific; avoid repeating the exact same set with 
                                    different punctuation.
                                    - Respect a tool_call_budget in state if present.
                                    
                                    ERROR & BOUNDS:
                                    - Never retry a failing tool more than once. If it fails, record a short error 
                                    summary in report and RETURN.
                                    - Do not include stack traces, secrets, or internal details in report.
                                    
                                    REPORT CONTENT:
                                    - List each requested item with: whether history was found, top 1 to 3 relevant 
                                    totals or notes, and any obvious price anchors from history (do not fabricate).
                                    - If cash balance was retrieved, include the numeric balance and one-line 
                                    interpretation (“sufficient for typical stock orders”, etc.) without exposing 
                                    margins.
                                    
                                    STOP CONDITIONS:
                                    MUST Return IMMEDIATELY after:
                                    - You’ve gathered the necessary history/cash info for the current request and 
                                    summarized it, or
                                    - A blocking issue prevents progress (e.g., missing date), which you documented in 
                                    report.
                                    
                                    EXAMPLES:
                                    Example A: history only:
                                    Goal: 'Quote 5k ‘A4 paper’ like last time on 2025-03-01.'
                                    Plan: 
                                    1) search_quote_history_retrieve(["A4 paper", "5000"])
                                    2) summarize (top matches, ranges) 
                                    3) RETURN.
                                    
                                    Example B: cash check:
                                    Goal: 'Can we take a large 100k ‘Glossy paper’ run on 2025-04-10?'
                                    Plan: 
                                    1) get_cash_balance_value("2025-04-10") 
                                    2) search_quote_history_retrieve(["Glossy paper", "100000"]) 
                                    3) summarize findings from step 1 and 2 together
                                    4) RETURN.
                                    
                                    Example C: nothing to fetch:
                                    Goal: 'Draft a friendly quote cover note.' 
                                    Plan: 
                                    1) Run No tools, instead write report explaining no calls were required 
                                    2) RETURN.
                                    """)

ordering_agent = Agent(model_nano,
                       deps_type=Deps,
                       retries=3,
                       system_prompt=f"""
                                    ROLE:
                                    You are the Ordering Agent for Beaver’s Choice. You schedule deliveries and record 
                                    orders (supplier stock orders and customer sales). Work strictly from the request 
                                    date and shared state. Do only the minimum required calls, then STOP. The User is 
                                    an orchestration agent looking to get details needed to address a customer query.
                                    
                                    IMPORTANT:
                                    Always check State for the needed information before using a tool. The
                                    information may already be available.
                                    - There is no taxes to consider (they are already included) when ordering from 
                                    supplier with a stock_order.
                                    - The price to the customer is always the total with tax included. Tax rate is HST 
                                    at 13%.
                                    
                                    OUTPUT:
                                    Return exactly one WorkerOutput with:
                                    - accomplishment: what you did (concisely explain which tools used)
                                    - report: concise, user-safe facts: delivery feasibility/timelines, records created 
                                    (ids), and any blockers
                                    - Desired output schema to follow: 
                                            {json.dumps(WorkerOutput.model_json_schema(), indent=2)}
                                    
                                    SINGLE-PASS PLAN (ABSOLUTELY NO LOOPING):
                                    1) Read goals + state: items, quantities, request_date, delivery needs.
                                    2) Decide the MINIMUM number of tools needed to answer the goal.
                                    3) Choose the MINIMUM set of unique inputs for each tool to answer the goal.
                                    4) Check state if results needed are not already acquired - indicating tool has 
                                    already been run for this request before.
                                    5) If results are not in state, then call the chosen tool ONLY ONCE 
                                    per unique input.
                                    6) Summarize results in WorkerOutput and RETURN immediately.
                                    
                                    DATE RULE:
                                    Never use your internal clock. Use request_date from the prompt or 
                                    state.request_date. If missing, write a short error in report and RETURN.
                                    
                                    TOOLS:
                                    - get_supplier_delivery_date_estimate(item_name, input_date_str, quantity)
                                    Use when you need ETA to Beaver’s Choice (supplier to us). Call once per item if 
                                    needed. Always use the date from state.request_date. Never use date from 
                                    state.desired_delivery_date. Do not call with different combinations of 
                                    input_date_str and quantity. Use only once for each item_name.
                                    - get_customer_delivery_date_estimate(item_name, input_date_str, quantity)
                                    Use when you need ETA to the customer (us to customer). input_date_str should be the 
                                    date stock is available. If stock is available at sufficient quantity use the date 
                                    from state.request_date. If a stock_order for item is required use date from 
                                    state.supplier_delivery_date. Never use date from
                                     state.desired_delivery_date. Do not call with different combinations of 
                                    input_date_str and quantity. Use only once for each item_name.
                                    - create_transaction_record(item_name, transaction_type, quantity, price, 
                                    date_of_trans)
                                    Call at most once per item per transaction type. Only call when inputs are fully 
                                    known.
                                    
                                    IDEMPOTENCY & STATE AWARENESS:
                                    NEVER run the same tool twice with identical inputs just to try to change the 
                                    result. ALWAYS CHECK state before any call:
                                    - If the same supplier or customer ETA for (item, quantity, date) already exists, 
                                    do not recalculate.
                                    - If an identical transaction has already been recorded in state.orders_completed, 
                                    do not create it again.
                                    
                                    PRECONDITIONS FOR TRANSACTIONS:
                                    - For 'stock_orders' (to supplier): you should have (item_name, quantity, price, 
                                    date_of_trans=request_date) and (if relevant) supplier ETA recorded or explicitly 
                                    deemed unnecessary.
                                    - For 'sales' (to customer): you should have (item_name, quantity, price, 
                                    date_of_trans=request_date), and either:
                                        a) in-stock confirmation from inventory (present in state), OR
                                        b) supplier ETA such that a customer ETA can be computed. If neither, report the 
                                        blocker and RETURN.
                                    - absolutely Never fabricate price. If price is missing, report the missing input 
                                    and RETURN without recording the transaction.
                                    
                                    ETA CALCULATION GUIDE:
                                    - If item is already in stock (state.stock_level_specific_items or inventory 
                                    snapshot shows >0):
                                        - For customer shipments: compute customer ETA from request_date.
                                    - If item is not in stock:
                                        - Compute supplier ETA from request_date, then compute customer ETA starting 
                                        from supplier ETA.
                                    - Only compute ETAs actually required by the goal.
                                    
                                    ERROR & BOUNDS:
                                    - Do not retry failing tools. If a tool errors, note a one-line error in report 
                                    and RETURN.
                                    - Do not expose stack traces or secrets.
                                    
                                    REPORT CONTENT:
                                    - For each item: quantity, whether in stock vs. requires supplier order, ETAs 
                                    (supplier and/or customer) if computed, and any transaction_ids created.
                                    - If blocked: list the exact missing inputs (e.g., price, date).
                                    
                                    STOP CONDITIONS:
                                    MUST Return immediately after:
                                    - You have already computed the necessary ETA(s) and created any required 
                                    transaction(s), OR
                                    - A blocking issue prevents progress (missing price/date/stock info), which 
                                    you documented.
                                    
                                    EXAMPLES:
                                    
                                    Example A: not in stock, needs supplier then customer:
                                    Goal: Sell 200 Glossy paper on 2025-04-01.
                                    Plan: 
                                    1) get_supplier_delivery_date_estimate('Glossy paper','2025-04-01',200) 
                                    2) derive customer start date from supplier ETA 
                                    3) get_customer_delivery_date_estimate 
                                    4) if price provided 
                                    5) create_transaction_record('Glossy paper','sales',200,price,'2025-04-01') 
                                    6) RETURN.
                                    
                                    Example B: supplier restock only:
                                    Goal: Place supplier order of 5000 Letterhead paper on 2025-05-10.
                                    Plan: 
                                    1) get_supplier_delivery_date_estimate
                                    2) create_transaction_record('Letterhead paper",'stock_orders',5000,price,
                                    '2025-05-10') 
                                    3) RETURN.
                                    
                                    Example C: blocked by missing price:
                                    Goal: Book sale of 300 Cardstock on 2025-04-02 but price not provided.
                                    Plan: 
                                    1) Compute ETAs if requested/needed; 
                                    2) then report 'price is required for transaction' 
                                    3) RETURN (with no transaction created).
                                    """)

data_extraction_agent = Agent(model,
                      deps_type=Deps,
                      retries=3,
                      system_prompt=f"""You are a data extraction agent. 
                      
                                        Your purpose is to accurately extract details from a customer request. 
                                        
                                        Your goal is to fill the following:
                                         - goals_of_request: What the customer is looking to get back (e.g. order fullfilled for items)
                                         - request_date: when the request was made according to the text, not your system time 
                                         - items_names_requested_from_customer: A list of items requested by the client 
                                         - items_names_requested_match_from_financial_report: find closest matches in the financial report item_names to the 
                                         item_names_requested_from_customer items 
                                         - quantity_of_items_requested: quantity of each item requested 
                                         - desired_delivery_date: When the customer asked the order to be delivered to them by.
                                        
                                        desired output follows this format: 
                                        {json.dumps(EmailDetails.model_json_schema(), indent=2)}""")
                                                        


"""Set up tools for your agents to use, these should be methods that combine the database functions above
 and apply criteria to them to ensure that the flow of the system is correct."""
# Tools for orchestration_agent
@orchestration_agent.tool
async def call_quoting_manager(ctx:RunContext[Deps], request:OrchestrationCall) -> WorkerOutput:
    """
    Call the quoting manager. It oversees quoting to ensure accuracy, efficiency, and customer satisfaction by 
    delivering competitive price quotes to clients.

    Tools Available to quoting Agent:

    - search_quote_history_retrieve: Retrieves historical quotes matching search terms
    Inputs:
      search_terms (List[str]): List of terms to match against customer requests and explanations.
      limit (int, optional): Maximum number of quote records to return. Default is 5.
    - get_cash_balance_value: Computes cash balance from sales vs stock orders up to a 
    given date for Beaver's Choice Paper Company.
    Inputs:
      as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    :param ctx:
    :param request: {}
    :return:
    """.format(json.dumps(OrchestrationCall.model_json_schema(), indent=2))
    try:
        instructions = (f"""Goal: {request.goal}
                    Items requested: {ctx.deps.state.items_names_requested_match_from_financial_report}
                    Notes for accomplishing goal: {request.notes_for_agent}""")

        response_from_quoting = await quoting_agent.run(deps=ctx.deps,user_prompt= instructions, output_type=WorkerOutput)
        return response_from_quoting.output
    except Exception as e:
        print(e)
        return(str(e))
    

@orchestration_agent.tool
async def call_ordering_manager(ctx:RunContext[Deps], request:OrchestrationCall) -> WorkerOutput:
    """
    Call the ordering manager. This agent manages ordering. It oversees orders to suppliers and sales to customers and
    ensures deliveries are on time and orders for supplies and from customers are recorded accurately.

    Tools Available to ordering Agent:

     - get_supplier_delivery_date_estimate: Estimates delivery date based on order quantity from supplier to
     beaver's choice paper company and date from the supplier to Beaver's Choice Paper Company.
     Inputs:
       input_date_str (str): The starting date in ISO format (YYYY-MM-DD). Default to request date from user input" or an optimized date for inventory management."
       quantity (int): The number of units in the order.
     - get_customer_delivery_date_estimate:  Estimates delivery date based on order quantity from beaver's choice paper company to customer.
     Inputs:
       input_date_str (str): The starting date in ISO format (YYYY-MM-DD). Use when inventory arrives or when item is in inventory stock.
       quantity (int): The number of units in the order.
     - create_transaction_record: Makes a stock order to a supplier or sales transaction into the database
     Inputs:
       item_name (str): The name of the item involved in the transaction.
       transaction_type (str): Either 'stock_orders' (order to supplier) or 'sales' (order to customer).
       quantity (int): Number of units involved in the transaction.
       price (float): Total price of the transaction.
       date_of_trans (str or datetime): Date of the transaction in ISO 8601 format.


    :param ctx: 
    :param request: {}
    :return:
    """.format(json.dumps(OrchestrationCall.model_json_schema(), indent=2))

    try:
        instructions = (f"""Goal: {request.goal}
                        Date request from customer was made (request_date): {ctx.deps.state.request_date}
                        Inventory needed: {ctx.deps.state.quantity_of_items_stock_order}
                        Items requested: {ctx.deps.state.items_names_requested_match_from_financial_report}
                        Quantity requested by customer: {ctx.deps.state.quantity_of_items_requested}
                        Supplier delivery dates: {ctx.deps.state.supplier_delivery_date}
                        Customer delivery dates: {ctx.deps.state.customer_delivery_date}
                        Notes for accomplishing goal: {request.notes_for_agent}""")

        response_from_ordering = await ordering_agent.run(deps=ctx.deps,user_prompt= instructions, output_type=WorkerOutput)
        print('successfully ran call_ordering_manager')
        return response_from_ordering.output
    except Exception as e:
        print(e)
        return str(e)
    



@orchestration_agent.tool
async def call_inventory_manager(ctx:RunContext[Deps], request:OrchestrationCall) -> WorkerOutput:
    """Call the inventory manager. This agent manages inventory, which involves overseeing a Beaver's Choice Paper
    company's products to ensure sufficient stock levels while preventing shortages or overages. Key responsibilities
    include monitoring inventory levels.

    Tools Available to Inventory Agent:

    - get_inventory_for_date: Returns current stock levels of all items as of a given date
    Input: as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff date.
    - get_stock_level_item: Returns stock level of a specific item as of a given date
    Inputs:
    -item_name (str): The name of the item to look up.
    -as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock."


    :param ctx:
    :param request: {}
    :return:
    """.format(json.dumps(OrchestrationCall.model_json_schema(), indent=2))
    try:
        instructions = (f"""Goal: {request.goal}
                        Date request from customer was made (request_date): {ctx.deps.state.request_date}
                        Items requested: {ctx.deps.state.items_names_requested_match_from_financial_report}
                        Quantity requested by customer: {ctx.deps.state.quantity_of_items_requested}
                        Notes for accomplishing goal: {request.notes_for_agent}""")

        response_from_inventory = await inventory_agent.run(deps=ctx.deps,user_prompt= instructions, output_type=WorkerOutput)
        return response_from_inventory.output
    except Exception as e:
        print(e)
        return str(e)
    

@orchestration_agent.tool
async def determine_stock_needs(ctx: RunContext[Deps]) -> list:
    """Asks the Inventory Manager to calculate the needed quantity of stock_orders. Must have the following to calculate need.
    - items_names_requested_match_from_financial_report: The internal name of the items
    - quantity_of_items_requested: the amount the customer requested
    - stock_level_specific_items: the current stock quantity of the items requested
    with these values you should be able to fill in the quantity_of_items_stock_order

    Output: Quantity of Stock needed"""
    try:
        instructions = f"""Please calculate the quantity_of_items_stock_order (the quantity needed to stock order).
                        
                        You need the following variables to calculate this value:
                        - items_names_requested_match_from_financial_report: The internal name of the items
                        - quantity_of_items_requested: the amount the customer requested
                        - stock_level_specific_items: the current stock quantity of the items requested
                        
                        - items_names_requested_match_from_financial_report: : {ctx.deps.state.items_names_requested_match_from_financial_report}
                        - quantity_of_items_requested: {ctx.deps.state.quantity_of_items_requested}
                        - stock_level_specific_items: {ctx.deps.state.stock_level_specific_items}

                        return: list

                        """

        response = await inventory_agent.run(instructions, output_type=InventoryListNeed, deps=ctx.deps)
        result_details = response.output

        ctx.deps.state.quantity_of_items_stock_order.extend(result_details.needed)
    
        return result_details
    except Exception as e:
        print(e)
        return str(e)



@orchestration_agent.tool
async def record_email_details(ctx: RunContext[Deps], prompt: str) -> EmailDetails:
    """Extracts details from the user prompt (email or request from customer).
    Looks for goals_of_request, request_date, items_names_requested_from_customer, matches and finds
    items_names_requested_match_from_financial_report, quantity_of_items_requested, desired_delivery_date in
    the user prompt and adds it to the shared state.

    :param prompt - the user prompt a.k.a. the request from the customer

    :return EmailDetails. """
    try:
        instructions = f"""Message to extract details from:{prompt}
                        If financial_report is missing or empty, proceed using item names verbatim.
                        When financial_report is present, match each customer item name to exactly ONE item_name from it.
                        financial report: {ctx.deps.state.financial_report}"""

        response = await data_extraction_agent.run(instructions, output_type=EmailDetails, deps=ctx.deps)
        result_details = response.output

        ctx.deps.state.goals_of_request.extend(result_details.goals_of_request)
        ctx.deps.state.request_date = result_details.request_date
        ctx.deps.state.items_names_requested_from_customer.extend(result_details.items_names_requested_from_customer)
        ctx.deps.state.items_names_requested_match_from_financial_report.extend(result_details.items_names_requested_match_from_financial_report)
        ctx.deps.state.quantity_of_items_requested.extend(result_details.quantity_of_items_requested)
        ctx.deps.state.desired_delivery_date = result_details.desired_delivery_date

        return result_details
    except Exception as e:
        print(e)
        return str(e)


def generate_delivery_address():
    first = random.choice(["richard","barak","mark","emanuel","zhi","manlok","jason","ken","rose","evelyn","claire","nancy","patricia","yulanda", "george"])
    last = random.choice(["trump","carney","macron","stuart","stone","parker","ng","obama","smith","sanders","grant","preston","yip","ganupe", "bakshi", "singh"])
    street_number = str(random.randint(1,9999))
    street_name = random.choice(["cochrane", "lockridge", "cherry", "maple", "bloor", "dundas", "yonge", "montrose",
                                 "fire rt 33", "munch", "trudeau", "carney","erica","dump","lakeside"])
    street_type = random.choice([" cres."," st."," rd.", " ave."])
    city = random.choice(["paris","waterloo","london","toronto","whitby","oshawa","missisauga","markham","ottawa"])
    prov = random.choice(['Ontario','Quebec','Manitoba','British Columbia'])
    country = 'Canada'


    postal_code_1 = (random.choice(string.ascii_uppercase)) + str(random.randint(0, 9))
    postal_code_2 = (random.choice(string.ascii_uppercase)) + str(random.randint(0, 9))
    postal_code_3 = (random.choice(string.ascii_uppercase)) + str(random.randint(0, 9))
    postal_code =  postal_code_1+ postal_code_2+ postal_code_3

    address = Address(attention=first+' '+last,
                      street_line= street_number+' '+street_name+' '+street_type,
                      city=city,
                      province=prov,
                      country=country,
                      postal_code=postal_code)

    return(address)

@orchestration_agent.tool
async def get_delivery_address(ctx: RunContext[Deps]) -> str:
    """
    Provides the shipping address for the customer from the customer database.

    WHEN TO USE:
    - When you need a customers shipping address.

    :return str of customer address.
    """
    
    output = generate_delivery_address()
    ctx.deps.state.shipping_address = output
    return output



@orchestration_agent.tool
async def generate_financial_report_dict(ctx: RunContext[Deps], as_of_date: Union[str, datetime]) -> FinancialReport:
    """
    Generate a complete financial report for the Beaver's Choice Paper company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    :return FinancialReport.
    """
    try:
        output = generate_financial_report(as_of_date)

        financial_repo = FinancialReport(
            as_of_date=output["as_of_date"],
            cash_balance=output["cash_balance"],
            inventory_value=output["inventory_value"],
            total_assets=output["total_assets"],
            inventory_summary=[InventoryItemSummary(**row) for row in output["inventory_summary"]],
            top_selling_products=[TopSellingProduct(**row) for row in output["top_selling_products"]],
        )

        ctx.deps.state.financial_report = financial_repo

        return financial_repo
    except Exception as e:
        print(e)

# Tools for inventory agent
@inventory_agent.tool
async def get_inventory_for_date(ctx: RunContext[Deps], as_of_date: str) -> dict:
    """
    Gets Beaver's Choice Paper Company's s stock levels of all item on a given date (as_of_date: often the request
    date, never the system time.).

    WHEN TO USE:
        - When requested to check inventory levels of all products (what is in stock, availability of products) as of
        a specific date. Always the request date, not the system time.

    WHEN NOT TO USE:
        - When looking whether a specific item is in stock. Use get_stock_level_item for this instead.

    :param as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff date. Default to request date from user input.
    :return dict of inventory report.
    """
    try:
        output = get_all_inventory(as_of_date)
        ctx.deps.state.inventory_levels_of_all_products = dict(output)
        return dict(output)
    except Exception as e:
        print(e)





@inventory_agent.tool
async def get_stock_level_item(ctx: RunContext[Deps], item_name: str, as_of_date: Union[str, datetime]) -> StockLevel:
    """
    Retrieve Beaver's Choice Paper Company's stock level of a specific item as of a given date (Always the request
    date, not the system time.).

    This function calculates the net stock by summing all 'stock_orders' and
    subtracting all 'sales' transactions for the specified item up to the given date.

    WHEN TO USE:
        - When checking whether a specific item is in stock, or how many are available.

    WHEN NOT TO USE:
        - When requested to check inventory levels of all products (what is in stock, availability of products) as of
        a specific date. Use get_inventory_for_date instead

    :param item_name (str): The name of the item to look up. Use items_names_requested_match_from_financial_report as this is the internal name.
    :param as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock. Default to request date from user input.
    :return StockLevel.
    """
    try:
        df = get_stock_level(item_name, as_of_date)
        if df.empty:
            record_found = False
            current_stock = 0.0
        else:
            row = df.iloc[0]
            record_found  = True

            current_stock = float(row["current_stock"])
        stock_level = StockLevel(item_name=item_name, current_stock=current_stock, record_found = record_found)
        ctx.deps.state.stock_level_specific_items.append(
            stock_level
        )
        return stock_level
    except Exception as e:
            print(e)



# Tools for quoting agent
@quoting_agent.tool
async def search_quote_history_retrieve(ctx: RunContext[Deps], search_terms: List[str], limit: int = 5) -> list:
    """
    Retrieve a list of historical quotes that match any of the provided search terms: such as item names with or without quantity.
    For item names use items_names_requested_match_from_financial_report as the default name,
    then if search is not successful try to use items_names_requested_from_customer for item name.

    WHEN TO USE:
    - When you need previous quotes on specific customer requests or explanations.

    :param search_terms (List[str]): List of terms to match against customer requests and explanations.
    :param limit (int, optional): Maximum number of quote records to return. Default is 5.

    :return list of historical quotes.
    """
    try:
    
        output = search_quote_history(search_terms, limit)
        ctx.deps.state.quote_history.extend(str(output))
    

        return output
    except Exception as e:
        print(e)



@quoting_agent.tool
async def get_cash_balance_value(ctx: RunContext[Deps], as_of_date: Union[str, datetime]) -> float:
    """Computes cash balance for Beaver's Choice Paper Company from sales vs stock orders up to a given date.

    :param as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    :return float.
    """ 
    try:

        output = get_cash_balance(as_of_date)
        ctx.deps.state.cash_balance = output
        return output
    except Exception as e:
        print(e)



# Tools for ordering agent
@ordering_agent.tool
async def get_supplier_delivery_date_estimate(ctx: RunContext[Deps], item_name: str, input_date_str: str, quantity: int) -> SupplierDelivery:
    """
    Estimates delivery date based on order quantity and date from the supplier to the Beaver's Choice Paper Company.

    WHEN TO USE:
    - When needing to check if a delivery will arrive in time to arrive by a certain date.

    WHEN NOT TO USE:
    - When recording an order or sale transaction. Instead use create_transaction for this.

    :param item_name (str): The name of the item to be delivered.
    :param input_date_str (str): The request date in ISO format (YYYY-MM-DD). Use request date,
    never use desired delivery date
    :param quantity (int): The number of units in the order.

    :return SupplierDelivery: The date the item will arrive into  Beaver's Choice Paper Company inventory.
    """
    try:
        output = get_supplier_delivery_date(input_date_str, quantity)
        delivery_details = SupplierDelivery(
                    item_name=item_name,
                    starting_date=datetime.strptime(input_date_str, "%Y-%m-%d").date(),
                    quantity=quantity,
                    supplier_delivery_date=datetime.strptime(output, "%Y-%m-%d").date(),
                )
        ctx.deps.state.supplier_delivery_date.append(
            delivery_details
            )
        return delivery_details
    except Exception as e:
        print(e)



@ordering_agent.tool
async def get_customer_delivery_date_estimate(ctx: RunContext[Deps], item_name: str, input_date_str: str, quantity: int) -> CustomerDelivery:
    """
    Estimates delivery date based on order quantity and date items are available (arrived from supplier to Beaver's
    Choice Paper Company or in inventory) from the Beaver's Choice Paper Company to the customer.

    WHEN TO USE:
    - When needing to check if a delivery will arrive in time to arrive by a certain date.

    WHEN NOT TO USE:
    - When recording an order or sale transaction. Instead use create_transaction for this.

    :param item_name (str): The name of the item to be delivered.
    :param input_date_str (str): The request date or supplier delivery date if available in ISO format (YYYY-MM-DD).
    never use customer delivery date.
    :param quantity (int): The number of units in the order.

    :return CustomerDelivery: The date the item will arrive to the customer.
    """
    try:
        output = get_customer_delivery_date(input_date_str, quantity)
        delivery_details = CustomerDelivery(
                    item_name=item_name,
                    starting_date=datetime.strptime(input_date_str, "%Y-%m-%d").date(),
                    quantity=quantity,
                    customer_delivery_date=datetime.strptime(output, "%Y-%m-%d").date(),
                )
        ctx.deps.state.customer_delivery_date.append(
            delivery_details
            )
        return delivery_details
    except Exception as e:
        print(e)

@ordering_agent.tool
async def create_transaction_record(ctx: RunContext[Deps], item_name: str, transaction_type: Literal["stock_orders","sales"],
                              quantity: int, price: float, date_of_trans: Union[str, datetime]) -> OrderRecord:
    """
    Records a stock order to a supplier or sales transaction with a customer into the database.

    WHEN NOT TO USE:
    - When recording an order or sale transaction.

    WHEN NOT TO USE:
    - When needing to check if a delivery will arrive in time to arrive by a certain date - instead use get_supplier_delivery_date_estimate.

    :param item_name (str): The name of the item involved in the transaction. Use item names from items_names_requested_match_from_financial_report
    :param transaction_type (str): Either 'stock_orders' or 'sales'.
    :param quantity (int): Number of units involved in the transaction.
    :param price (float): Total price of the transaction.
    :param date_of_trans (str or datetime): Date of the transaction in ISO 8601 format (Always the request date, not the system time.). Default to request date from user input.

    :return OrderRecord.
    """
    try:
        output = create_transaction(item_name, transaction_type, quantity, price, date_of_trans)
        order_record = OrderRecord(item_name=item_name,
                                                        transaction_type=transaction_type,
                                                        quantity= quantity,
                                                        price=price,
                                                        date=date_of_trans,
                                                        transaction_id=output
                                                        )
        ctx.deps.state.orders_completed.append(order_record)


        return order_record
    except Exception as e:
        print(e)



# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():

    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    quote_requests_sample = pd.read_csv("quote_requests_sample.csv")

    # Sort by date
    quote_requests_sample["request_date"] = pd.to_datetime(
        quote_requests_sample["request_date"]
    )
    quote_requests_sample = quote_requests_sample.sort_values("request_date")

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    ############
    ############
    ############
    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    ############
    ############
    ############
    def run_agentic_process(prompt):
        shared_state = SharedState()
        deps = Deps(state=shared_state)
        deps.state.process_completed = False

        current_time = datetime.now()
        timestamp_str = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"output_{timestamp_str}.txt"

        with open(filename, "w") as f:
            f.write(f"Prompt: {prompt}\n ")
        print(f"Prompt: {prompt}\n ")

        #try:
        response_orc = orchestration_agent.run_sync(prompt, deps=deps, output_type=OrchestrationResponse,  
        usage_limits=UsageLimits(request_limit=200))
        response_details = response_orc.output
    
        with open(filename, "w") as f:
            f.write(f"internal_response: {response_details.internal_response}\n ")
        print(f"internal_response: {response_details.internal_response}\n ")

        with open(filename, "a") as f:
            f.write(f"response_to_client: {response_details.response_to_client}\n ")
        print(f"response_to_client: {response_details.response_to_client}\n ")

        return response_details
    

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        ############
        ############
        ############
        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        ############
        ############
        ############

        try:
            response = run_agentic_process(request_with_date) # Running Multi Agent System Here.
        except:
            response = run_agentic_process(request_with_date)
        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()