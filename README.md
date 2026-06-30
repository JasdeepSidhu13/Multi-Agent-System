# Setup

This repository contains a Python-based multi-agent system for Beaver's Choice Paper Company. The system reads customer quote and order requests, checks inventory and historical quote context, decides whether orders can be fulfilled on time, records supplier and sales transactions, and produces customer-facing responses.

Repository: https://github.com/JasdeepSidhu13/Multi-Agent-System

## 1. Prerequisites

- Python 3.10 or newer is recommended.
- Access to the model endpoint used by the project.
- A valid `UDACITY_OPENAI_API_KEY` value for the Vocareum OpenAI-compatible API.
- Git, if you are cloning the repository locally.

## 2. Clone the repository

```bash
git clone https://github.com/JasdeepSidhu13/Multi-Agent-System.git
cd Multi-Agent-System
```

## 3. Create and activate a virtual environment

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

After activation, your terminal prompt should show the virtual environment name, usually `(.venv)`.

## 4. Install dependencies

Install the pinned dependencies from `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The project currently depends on:

- `pandas` for CSV loading, tabular transformations, and result exports
- `numpy` for deterministic sample inventory generation
- `SQLAlchemy` for SQLite access
- `python-dotenv` for environment variable loading
- `pydantic-ai` for agent definitions, model calls, tools, and structured outputs
- `pydantic` models through `pydantic-ai`

## 5. Configure environment variables

The repository includes `example.env` as a safe template. Copy it to a local `.env` file:

```bash
cp example.env .env
```

Then replace the placeholder value with your actual key:

```env
UDACITY_OPENAI_API_KEY="OUR OPEN AI API KEY"
```

The code creates OpenAI-compatible models through:

```python
OpenAIProvider(
    api_key=os.getenv("UDACITY_OPENAI_API_KEY"),
    base_url="https://openai.vocareum.com/v1",
)
```

Do not commit real API keys or other secrets. Keep real credentials only in your local `.env` file.

## 6. Verify required data files

Run the project from the repository root so the script can find the CSV files and SQLite database path. The main runtime expects these files:

- `project_solution.py` - main application and multi-agent system
- `requirements.txt` - Python dependency list
- `example.env` - safe environment variable template to copy into a local `.env`
- `quote_requests.csv` - historical customer quote request data loaded into SQLite
- `quotes.csv` - historical quote outcomes and quote explanations
- `quote_requests_sample.csv` - sample requests used by `run_test_scenarios()`
- `munder_difflin.db` - SQLite database file created or refreshed by the script

## 7. Run the multi-agent system

From the repository root with the virtual environment active:

```bash
python project_solution.py
```

The script will:

1. Initialize the SQLite database.
2. Load historical quote request data and quote records.
3. Generate sample inventory records.
4. Process every row in `quote_requests_sample.csv`.
5. Run the multi-agent orchestration flow for each request.
6. Write individual response logs and aggregate results.

## 8. Runtime outputs

Running the script can create or update the following files:

- `munder_difflin.db` - SQLite database containing inventory, quotes, requests, and transactions
- `agent_trace.log` - local trace/log output for agent activity
- `output_YYYY-MM-DD_HH-MM-SS.txt` - per-request prompt and response logs
- `test_results.csv` - aggregate results from the sample scenario run

If you want a clean run, delete old `output_*.txt`, `test_results.csv`, `agent_trace.log`, and `munder_difflin.db` before executing the script again. The script also calls `init_database(db_engine)` at startup, which recreates the main database tables for the test scenario.

# Project overview

The project models a paper supplier's sales workflow with a multi-agent architecture. Instead of using one monolithic prompt for every task, the system separates responsibilities across specialist agents. A central orchestration agent receives the customer request and delegates focused work to inventory, quoting, ordering, and data-extraction agents. These agents use structured Pydantic models and tool functions to read and update shared state.

At a high level, the system answers questions such as:

- What products did the customer request?
- Which internal catalog items best match those products?
- How much inventory is currently available?
- Does Beaver's Choice need to place supplier stock orders?
- Can the requested items arrive by the customer's desired delivery date?
- What price should the customer be quoted?
- Which sales and stock-order transactions should be recorded?
- What customer-safe response should be returned?

# Repository structure

```text
.
|-- Agentic_system_diagram.png
|-- beavers-choice-multi-agent-reflection-report.pdf
|-- project_solution.py
|-- requirements.txt
|-- example.env
|-- quote_requests.csv
|-- quote_requests_sample.csv
|-- quotes.csv
|-- munder_difflin.db
|-- agent_trace.log
|-- output_*.txt
`-- test_results.csv
```

Important files:

- `project_solution.py`: The main source file. It contains database setup, utility functions, Pydantic schemas, agent definitions, tools, orchestration logic, response sanitization, and scenario execution.
- `example.env`: Safe environment variable template. Copy this to `.env` locally and replace the placeholder value before running the system.
- `Agentic_system_diagram.png`: A visual diagram of the agentic system.
- `beavers-choice-multi-agent-reflection-report.pdf`: Supporting report/reflection for the project.
- `quote_requests.csv`: Historical quote requests used to seed the database.
- `quotes.csv`: Historical quote totals, explanations, and request metadata used by the quoting flow.
- `quote_requests_sample.csv`: Scenario inputs processed by the system when the main script runs.
- `test_results.csv`: Output summary from a completed run.

# How the multi-agent system works

## Core business scenario

Beaver's Choice Paper Company sells paper and paper-adjacent products such as A4 paper, cardstock, colored paper, glossy paper, poster paper, envelopes, paper cups, paper plates, napkins, and specialty paper stock.

Customer requests usually include:

- The products needed
- Quantities
- Event or business context
- Desired delivery date
- Request date

The system must decide whether each request can be quoted, fulfilled, partially fulfilled, or delayed. It also records inventory-impacting transactions in SQLite.

## Database layer

The database uses SQLite through SQLAlchemy:

```python
db_engine = create_engine("sqlite:///munder_difflin.db")
```

The main database setup happens in `init_database(db_engine)`. It creates and populates these tables:

- `quote_requests`: Customer request text loaded from `quote_requests.csv`
- `quotes`: Historical quote totals and explanations loaded from `quotes.csv`
- `inventory`: Generated inventory snapshot for a subset of catalog items
- `transactions`: Sales and supplier stock-order records

Key database helper functions include:

- `generate_sample_inventory(...)`: Creates a deterministic inventory sample using a random seed.
- `init_database(...)`: Rebuilds the SQLite tables and seeds initial stock and cash.
- `create_transaction(...)`: Records `stock_orders` and `sales`.
- `get_all_inventory(...)`: Computes inventory quantities as of a date.
- `get_stock_level(...)`: Computes current stock for one item as of a date.
- `get_cash_balance(...)`: Calculates available cash from sales minus stock purchases.
- `generate_financial_report(...)`: Produces cash, inventory valuation, total assets, inventory summary, and top-selling product data.
- `search_quote_history(...)`: Searches past quote requests and quote explanations.

## Catalog and inventory model

The product catalog is represented by the `paper_supplies` list in `project_solution.py`. Each catalog item includes:

- `item_name`
- `category`
- `unit_price`

The generated inventory covers a subset of the catalog. Inventory changes are not stored only as a static quantity. Instead, the system calculates stock from the transaction ledger:

- `stock_orders` add units.
- `sales` subtract units.

This means inventory is date-aware. A stock check for one date can produce different results than a stock check for a later date after additional transactions have been recorded.

## Pydantic schemas

The system uses Pydantic models to keep agent inputs and outputs structured. Important schemas include:

- `SharedState`: The central request state shared by all agents.
- `Deps`: Dataclass wrapper that passes `SharedState` into Pydantic AI tools.
- `EmailDetails`: Structured extraction result for customer requests.
- `OrchestrationCall`: Work order from the orchestration agent to a specialist agent.
- `OrchestrationResponse`: Final structured response with internal and customer-facing text.
- `WorkerOutput`: Standard response format from specialist agents.
- `FinancialReport`, `InventoryItemSummary`, `TopSellingProduct`: Financial reporting schemas.
- `StockLevel`: Structured inventory lookup result.
- `SupplierDelivery` and `CustomerDelivery`: Delivery estimate schemas.
- `OrderRecord`: Recorded transaction details.

Using explicit schemas helps reduce ambiguity between agents. Each agent is expected to return a defined structure rather than free-form text only.

## Model configuration

The project creates two OpenAI-compatible chat models with Pydantic AI:

- `gpt-5-mini`: Used for the orchestration agent and data extraction agent.
- `gpt-5-nano`: Used for worker agents such as inventory, quoting, and ordering.

Both models use the Vocareum OpenAI-compatible endpoint and are wrapped with Pydantic AI instrumentation settings. Logfire is configured locally with:

```python
logfire.configure(service_name="beavers-choice", send_to_logfire=False)
```

Because `send_to_logfire=False`, tracing is configured for local logging rather than remote Logfire export.

# Agent roles

## 1. Orchestration Agent

The orchestration agent is the manager. It receives the customer request and coordinates the rest of the workflow.

Its responsibilities include:

- Generate a financial report for the request date.
- Extract request details from the customer message.
- Retrieve or generate a delivery address.
- Ask the inventory agent to check stock.
- Determine supplier stock needs.
- Ask the quoting agent for quote and cash context.
- Ask the ordering agent to check delivery timing and create transactions.
- Decide which items are viable, delayed, or unavailable.
- Return an `OrchestrationResponse`.

The orchestration agent has tools such as:

- `generate_financial_report_dict`
- `record_email_details`
- `get_delivery_address`
- `determine_stock_needs`
- `call_inventory_manager`
- `call_quoting_manager`
- `call_ordering_manager`

## 2. Data Extraction Agent

The data extraction agent parses the original customer prompt into structured fields:

- Customer goals
- Request date
- Requested item names
- Internal item-name matches
- Requested quantities
- Desired delivery date

It returns an `EmailDetails` object and updates `SharedState`.

## 3. Inventory Agent

The inventory agent answers inventory-specific questions. It should make the minimum number of tool calls needed and then stop.

It can use:

- `get_inventory_for_date(as_of_date)`
- `get_stock_level_item(item_name, as_of_date)`

Its results are stored in shared state fields such as:

- `inventory_levels_of_all_products`
- `stock_level_specific_items`

## 4. Quoting Agent

The quoting agent supports pricing decisions and historical quote lookup. It can:

- Search similar historical quotes.
- Retrieve cash balance when supplier purchasing decisions need financial context.
- Return pricing context to the orchestrator.

It can use:

- `search_quote_history_retrieve(search_terms, limit=5)`
- `get_cash_balance_value(as_of_date)`

Customer-facing quotes must show:

- Subtotal before tax
- HST at 13%
- Final total

The system assumes no shipping charge.

## 5. Ordering Agent

The ordering agent handles delivery estimates and transaction recording. It can:

- Estimate supplier delivery dates.
- Estimate customer delivery dates.
- Record supplier stock orders.
- Record customer sales.

It can use:

- `get_supplier_delivery_date_estimate(item_name, input_date_str, quantity)`
- `get_customer_delivery_date_estimate(item_name, input_date_str, quantity)`
- `create_transaction_record(item_name, transaction_type, quantity, price, date_of_trans)`

The ordering agent is instructed to avoid duplicate transactions by checking `SharedState.orders_completed`.

# Shared state and tool flow

Every request creates a fresh `SharedState` instance:

```python
shared_state = SharedState()
deps = Deps(state=shared_state)
```

Agents and tools read from and write to this shared state. For example:

1. `record_email_details` extracts requested products and quantities.
2. `generate_financial_report_dict` stores a `FinancialReport`.
3. `get_stock_level_item` appends `StockLevel` records.
4. `determine_stock_needs` records supplier replenishment quantities.
5. Delivery estimate tools append supplier and customer delivery dates.
6. Transaction tools append completed order records.

This pattern gives worker agents context without requiring every fact to be repeated in every prompt.

# End-to-end request lifecycle

When `python project_solution.py` runs, `run_test_scenarios()` performs the complete workflow:

1. Print `Initializing Database...`.
2. Rebuild the SQLite database with historical quote and inventory data.
3. Load `quote_requests_sample.csv`.
4. Sort sample requests by request date.
5. Generate an initial financial report.
6. For each sample request:
   - Add the request date to the prompt.
   - Create a fresh `SharedState`.
   - Run the orchestration agent synchronously.
   - Sanitize the customer-facing response.
   - Write prompt and response details to an `output_*.txt` file.
   - Regenerate the financial report after the request.
   - Append the result to an in-memory results list.
7. Write all results to `test_results.csv`.
8. Print a final financial report.

# Fulfillment decision logic

The orchestration prompt defines the central order policy:

## If all requested items can arrive on time

The system should:

- Place the order.
- Record the customer sales transaction.
- Include itemized pricing.
- Include HST at 13%.
- Confirm delivery timing.

## If some items can arrive on time and others cannot

The system should:

- Place or prepare the viable portion.
- Identify delayed items.
- Explain the earliest available delivery timing.
- Ask the customer to choose:
  - `a) Cancel this order entirely`
  - `b) Complete the order for the delayed item as well, and ship all at once`
  - `c) Cancel the delayed item only`

## If an item is not carried or cannot be supplied

The system should:

- Complete any viable items.
- Tell the customer which requested item is unavailable.
- Offer the customer the option to cancel the entire order.

# Delivery date logic

Supplier delivery lead time is estimated by `get_supplier_delivery_date(...)`:

- 10 units or fewer: same day
- 11 to 100 units: 1 day
- 101 to 1000 units: 4 days
- More than 1000 units: 7 days

Customer delivery lead time is estimated by `get_customer_delivery_date(...)`:

- 10 units or fewer: same day
- 11 to 100 units: 1 day
- 101 to 1000 units: 2 days
- More than 1000 units: 3 days

The ordering agent combines these rules:

- If stock is available now, customer delivery starts from the request date.
- If stock must be ordered from a supplier, customer delivery starts after supplier delivery.

# Pricing and tax rules

The system follows these pricing and tax assumptions:

- Customer quotes must show subtotal, HST, and total.
- HST is 13%.
- Shipping is free to customers.
- Supplier stock orders do not add a separate customer-facing tax.
- Supplier stock-order prices are treated as already tax-inclusive or tax-exempt for internal purchasing.
- Historical quote search can inform pricing, but the system also uses catalog unit prices from inventory data.

# Response sanitization

Before a customer response is saved, it passes through `sanitize_customer_response(text)`.

This function masks or replaces internal implementation details such as:

- Tool calls
- Function calls
- API references
- Database references
- Stack traces
- Internal request limit wording
- Raw transaction implementation details

If the response still contains forbidden internal terms after replacement, the function returns a generic customer-safe fallback.

# Logging and observability

The code configures a local log handler:

```python
file_handler = logging.FileHandler("agent_trace.log")
logger = logging.getLogger("logfire")
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
```

This creates `agent_trace.log` during execution. The project also writes per-request files named `output_YYYY-MM-DD_HH-MM-SS.txt`, each containing:

- The prompt sent to the agentic process
- The internal response
- The final customer-facing response

# Troubleshooting

## `UDACITY_OPENAI_API_KEY` is missing

Copy `example.env` to `.env` in the repository root:

```bash
cp example.env .env
```

Then update `.env` so it contains your actual API key:

```env
UDACITY_OPENAI_API_KEY="OUR OPEN AI API KEY"
```

Also make sure you run the script from the repository root so `load_dotenv()` can find the file.

## CSV file not found

Run the script from the repository root:

```bash
python project_solution.py
```

The script expects relative paths such as `quote_requests.csv`, `quotes.csv`, and `quote_requests_sample.csv`.

## SQLite database is locked

Close any process or notebook that may be using `munder_difflin.db`, then rerun the script. If you do not need the current database state, remove the database file and rerun:

```bash
rm munder_difflin.db
python project_solution.py
```

## Dependency installation fails

Upgrade `pip` and retry:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you are using a very new Python version and a backport package causes issues, create a fresh virtual environment with Python 3.10 or 3.11 and reinstall.

## Model or endpoint errors

Confirm:

- The API key is valid.
- The Vocareum endpoint is reachable.
- The configured model names are available to your environment.
- Your account has quota for the number of sample requests in `quote_requests_sample.csv`.

# Development notes

- Keep generated runtime files out of commits unless they are intentionally part of a report or evaluation.
- The system is designed around structured Pydantic outputs. When adding a new agent or tool, define the input and output schema first.
- Prefer adding tools that perform deterministic business operations, such as database reads, transaction writes, or date calculations.
- Keep customer-facing text free of internal implementation details.
- When changing fulfillment behavior, update the orchestration prompt and any affected worker-agent instructions together so the agents keep a consistent policy.

# Quick command reference

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure secrets
cp example.env .env
# Then edit .env and replace "OUR OPEN AI API KEY" with your actual key.

# Run the system
python project_solution.py
```
