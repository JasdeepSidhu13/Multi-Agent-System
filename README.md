# Setup

This repository contains a Python multi-agent system for Beaver's Choice Paper
Company. The system reads customer quote and order requests, checks available
inventory, searches historical quote context, estimates fulfillment dates,
records supplier and customer transactions, and returns customer-friendly order
or quote responses.

Repository: <https://github.com/JasdeepSidhu13/Multi-Agent-System>

## Prerequisites

- Python 3.10 or newer.
- Git, if you are cloning the repository locally.
- Access to the Vocareum OpenAI-compatible API endpoint used by the project.
- A valid `UDACITY_OPENAI_API_KEY`.

The application uses Pydantic AI agents backed by OpenAI-compatible chat models.
Without a valid API key and endpoint access, dependency installation can still
succeed, but running the multi-agent workflow will fail when the agents call the
model.

## Clone the repository

```bash
git clone https://github.com/JasdeepSidhu13/Multi-Agent-System.git
cd Multi-Agent-System
```

## Create and activate a virtual environment

Create a virtual environment from the repository root.

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

After activation, your terminal prompt should usually include `(.venv)`.

## Install dependencies

Install the pinned dependencies from `requirements.txt`:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The project uses:

- `pandas` for loading CSV files, transforming data, writing result files, and
  moving tabular data into SQLite.
- `numpy` for deterministic sample inventory generation.
- `SQLAlchemy` for database access.
- `python-dotenv` for loading local environment variables from `.env`.
- `pydantic-ai` for defining agents, tools, model calls, usage limits, and
  structured outputs.
- `pydantic`, installed through `pydantic-ai`, for typed request, response, and
  shared-state schemas.

## Configure environment variables

The repository includes `example.env` as a safe template. Copy it to `.env`:

```bash
cp example.env .env
```

Edit `.env` and replace the placeholder with your real key:

```env
UDACITY_OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

The code reads this variable with `load_dotenv()` and passes it into an
OpenAI-compatible provider:

```python
OpenAIProvider(
    api_key=os.getenv("UDACITY_OPENAI_API_KEY"),
    base_url="https://openai.vocareum.com/v1",
)
```

Do not commit real API keys. Keep secrets only in your local `.env` file.

## Required project files

Run the project from the repository root so relative paths resolve correctly.
The main script expects these files to be present:

```text
.
|-- README.md
|-- example.env
|-- project_solution.py
|-- requirements.txt
|-- quote_requests.csv
|-- quote_requests_sample.csv
|-- quotes.csv
`-- test_results.csv
```

Important files:

- `project_solution.py`: Main application file. It contains database setup,
  catalog data, utility functions, Pydantic schemas, agent definitions, tools,
  orchestration logic, response sanitization, and scenario execution.
- `quote_requests.csv`: Historical customer quote requests loaded into SQLite.
- `quotes.csv`: Historical quote totals and quote explanations loaded into
  SQLite for quote-history retrieval.
- `quote_requests_sample.csv`: Sample customer requests processed when the main
  script runs.
- `test_results.csv`: Results from a previous run. Running the script can
  overwrite this file.
- `example.env`: Environment variable template for local configuration.

## Run the multi-agent system

With the virtual environment active and `.env` configured:

```bash
python project_solution.py
```

The script will:

1. Configure local Logfire/logging output.
2. Initialize `munder_difflin.db`.
3. Load historical quote requests from `quote_requests.csv`.
4. Load historical quotes from `quotes.csv`.
5. Generate a deterministic sample inventory from the in-code product catalog.
6. Load and sort sample customer requests from `quote_requests_sample.csv`.
7. Run the multi-agent orchestration workflow for each sample request.
8. Write per-request response logs.
9. Write aggregate results to `test_results.csv`.
10. Print a final financial report.

## Generated runtime files

Running the script can create or update:

- `munder_difflin.db`: SQLite database created by `project_solution.py`.
- `agent_trace.log`: Local trace/log file for Logfire-related logging.
- `output_YYYY-MM-DD_HH-MM-SS.txt`: Per-request prompt and response logs.
- `test_results.csv`: Aggregate scenario results.

For a clean run, remove old generated files before starting:

```bash
rm -f munder_difflin.db agent_trace.log output_*.txt test_results.csv
python project_solution.py
```

Be careful with `test_results.csv` if you want to preserve a previous run.

# Project overview

The project models an order-management workflow for Beaver's Choice Paper
Company. Customers ask for paper or paper-related products, quantities, and
delivery dates. The system decides whether Beaver's Choice can fulfill the
request, whether it must buy more stock from a supplier, what customer delivery
date is feasible, and how to respond with pricing.

The key design choice is to split work across specialist agents instead of
asking one model prompt to do everything. A central orchestration agent manages
the request and delegates narrower tasks to inventory, quoting, ordering, and
data-extraction agents. Shared Pydantic state connects these agents so each
agent can reuse facts already discovered by earlier steps.

At a high level, the system answers:

- What does the customer want?
- What date was the request made?
- Which internal catalog items match the customer wording?
- How many units were requested?
- What stock is available on the request date?
- What stock must be ordered from the supplier?
- Can items reach the customer by the desired date?
- What quote should the customer receive?
- Which supplier stock orders and customer sales should be recorded?
- What response can be safely shown to the customer?

# How the multi-agent system works

## End-to-end flow

When `python project_solution.py` runs, `run_test_scenarios()` performs the main
workflow:

1. Rebuilds the SQLite database by calling `init_database(db_engine)`.
2. Reads `quote_requests_sample.csv`.
3. Converts and sorts request dates.
4. Generates an initial financial report for the earliest sample date.
5. For each sample request:
   - Adds the request date to the prompt.
   - Creates a fresh `SharedState`.
   - Wraps that state in `Deps`.
   - Runs the orchestration agent synchronously.
   - Lets the orchestrator call worker agents through tools.
   - Sanitizes the customer-facing response.
   - Writes an `output_*.txt` file containing the prompt, internal response,
     and final customer response.
   - Recomputes cash and inventory value after the request.
   - Adds the result to an in-memory list.
6. Writes all results to `test_results.csv`.
7. Prints final cash and inventory value.

## Architecture summary

```text
Customer/sample request
        |
        v
Orchestration Agent
        |
        |-- Data Extraction Agent
        |-- Inventory Agent
        |-- Quoting Agent
        `-- Ordering Agent
        |
        v
SharedState + SQLite tools
        |
        v
Customer-safe response + transaction/results files
```

The orchestration agent is the manager. It does not directly perform every
business operation itself. Instead, it calls tools that either update shared
state or delegate to worker agents. Worker agents return structured
`WorkerOutput` objects so the orchestrator can reason over their results.

## Models and provider configuration

`project_solution.py` configures two OpenAI-compatible chat models through
Pydantic AI:

- `gpt-5-mini`: Used by the orchestration agent and data-extraction agent.
- `gpt-5-nano`: Used by worker agents such as inventory, quoting, and ordering.

Both models use:

```python
base_url="https://openai.vocareum.com/v1"
```

The API key is loaded from:

```python
UDACITY_OPENAI_API_KEY
```

Model instrumentation is configured through
`pydantic_ai.models.instrumented.instrument_model`. Logfire is configured with
`send_to_logfire=False`, so the repository writes local trace/log output instead
of sending traces to a hosted Logfire service.

## Shared state

Every request starts with a new shared state object:

```python
shared_state = SharedState()
deps = Deps(state=shared_state)
```

`SharedState` is the in-memory coordination object used by tools and agents.
Important fields include:

- `goals_of_request`: What the customer is asking for.
- `request_date`: Date the request was made.
- `items_names_requested_from_customer`: Item names as written by the customer.
- `items_names_requested_match_from_financial_report`: Internal item-name
  matches.
- `quantity_of_items_requested`: Requested quantities.
- `quantity_of_items_stock_order`: Additional supplier stock required.
- `desired_delivery_date`: Customer's target delivery date.
- `shipping_address`: Generated delivery address.
- `inventory_levels_of_all_products`: Full stock snapshot when requested.
- `stock_level_specific_items`: Per-item stock checks.
- `quote_history`: Historical quote search results.
- `cash_balance`: Cash balance as of a date.
- `financial_report`: Current financial report.
- `supplier_delivery_date`: Supplier-to-company delivery estimates.
- `customer_delivery_date`: Company-to-customer delivery estimates.
- `orders_completed`: Supplier stock orders and customer sales recorded during
  the request.
- `response_to_customer`: Final customer response, when set.
- `process_completed`: Workflow completion marker.

The worker prompts instruct agents to check shared state before calling tools.
That reduces duplicate tool calls and helps preserve a single source of truth
during each request.

# Agent roles

## Orchestration Agent

The orchestration agent coordinates the full customer workflow. It receives the
customer request, follows a required step-by-step plan, and returns an
`OrchestrationResponse` containing:

- `internal_response`: Summary of what the system did.
- `response_to_client`: Customer-facing response.

Its main responsibilities are:

- Generate a financial report for the request date.
- Extract structured request details from the prompt.
- Generate or retrieve a customer delivery address.
- Ask the inventory agent to check stock.
- Determine supplier stock needs.
- Ask the quoting agent for quote history and cash context.
- Ask the ordering agent for delivery estimates.
- Ask the ordering agent to record supplier stock orders and customer sales.
- Decide whether all, some, or none of the requested items can be fulfilled on
  time.
- Produce customer-safe pricing and delivery messaging.

Orchestration tools:

- `generate_financial_report_dict`
- `record_email_details`
- `get_delivery_address`
- `determine_stock_needs`
- `call_inventory_manager`
- `call_quoting_manager`
- `call_ordering_manager`

## Data Extraction Agent

The data-extraction agent turns the original customer message into an
`EmailDetails` object. It extracts:

- Customer goals.
- Request date.
- Requested item names.
- Closest matching internal item names.
- Requested quantities.
- Desired delivery date.

The `record_email_details` orchestration tool runs this agent and writes the
result into `SharedState`.

## Inventory Agent

The inventory agent answers stock questions. It is instructed to make the
minimum number of tool calls needed and then stop.

Inventory tools:

- `get_inventory_for_date(as_of_date)`: Returns a full inventory snapshot for a
  date.
- `get_stock_level_item(item_name, as_of_date)`: Returns stock for a specific
  item on a date.

The inventory agent updates:

- `inventory_levels_of_all_products`
- `stock_level_specific_items`

## Quoting Agent

The quoting agent provides quote context and cash context. It can search similar
historical quotes and retrieve the cash balance when supplier purchasing
decisions require financial context.

Quoting tools:

- `search_quote_history_retrieve(search_terms, limit=5)`
- `get_cash_balance_value(as_of_date)`

Customer-facing quotes are expected to include:

- Subtotal before tax.
- HST at 13%.
- Final total.

The orchestration prompt states that customer shipping is free.

## Ordering Agent

The ordering agent handles delivery estimates and transaction recording.

Ordering tools:

- `get_supplier_delivery_date_estimate(item_name, input_date_str, quantity)`:
  Estimates when supplier stock can arrive at Beaver's Choice.
- `get_customer_delivery_date_estimate(item_name, input_date_str, quantity)`:
  Estimates when Beaver's Choice can deliver to the customer.
- `create_transaction_record(item_name, transaction_type, quantity, price,
  date_of_trans)`: Records a `stock_orders` or `sales` transaction in SQLite.

The ordering agent is instructed to avoid duplicate transactions by checking
`SharedState.orders_completed`.

# Database and data model

The repository uses SQLite through SQLAlchemy:

```python
db_engine = create_engine("sqlite:///munder_difflin.db")
```

`init_database(db_engine)` rebuilds and seeds the database each time the script
runs. It creates or refreshes these tables:

- `quote_requests`: Historical request text loaded from `quote_requests.csv`.
- `quotes`: Historical quote totals and explanations loaded from `quotes.csv`.
- `inventory`: Generated reference inventory for a subset of catalog items.
- `transactions`: Ledger of starting cash, starting stock orders, supplier
  stock orders, and customer sales.

## Product catalog

The product catalog is the `paper_supplies` list in `project_solution.py`. Each
catalog item has:

- `item_name`
- `category`
- `unit_price`

The catalog includes paper types, paper-adjacent products, large-format items,
and specialty papers, such as:

- A4 paper
- Letter-sized paper
- Cardstock
- Colored paper
- Glossy paper
- Poster paper
- Paper plates
- Paper cups
- Envelopes
- Large poster paper
- Rolls of banner paper
- 250 gsm cardstock

## Inventory generation

`generate_sample_inventory(paper_supplies, coverage=0.4, seed=137)` selects a
deterministic subset of catalog items and assigns each selected item:

- A random starting stock quantity between 200 and 800.
- A random minimum stock level between 50 and 150.

The seed makes the inventory reproducible across runs.

## Transaction ledger

Inventory is computed from transactions, not only from a static field.

- `stock_orders` add units.
- `sales` subtract units.

At startup, `init_database` adds:

- A dummy `sales` transaction with `price=50000.0` to represent starting cash.
- One `stock_orders` transaction for each generated inventory item.

Later, the ordering agent can add supplier stock orders and customer sales.

## Key database helper functions

- `create_transaction(...)`: Appends a `stock_orders` or `sales` transaction.
- `get_all_inventory(as_of_date)`: Calculates stock for all positive-stock
  items as of a date.
- `get_stock_level(item_name, as_of_date)`: Calculates stock for one item as of
  a date.
- `get_supplier_delivery_date(input_date_str, quantity)`: Estimates supplier
  delivery date.
- `get_customer_delivery_date(input_date_str, quantity)`: Estimates customer
  delivery date.
- `get_cash_balance(as_of_date)`: Computes cash from sales minus stock orders
  up to a date.
- `generate_financial_report(as_of_date)`: Computes cash balance, inventory
  value, total assets, inventory summary, and top-selling products.
- `search_quote_history(search_terms, limit=5)`: Searches historical request and
  quote text.

# Business rules

## Fulfillment decisions

The orchestration prompt defines three main fulfillment cases.

### All requested items can arrive on time

The system should:

- Place the order.
- Record the customer sales transaction.
- Include itemized pricing.
- Include HST at 13%.
- Confirm delivery timing.

### Some items can arrive on time and others cannot

The system should:

- Place or prepare the viable portion.
- Identify delayed items.
- Explain the earliest available delivery timing.
- Ask whether the customer wants to:
  - Cancel the entire order.
  - Complete the delayed item too and ship all items together.
  - Cancel only the delayed item.

### An item is not carried or cannot be supplied

The system should:

- Complete any viable items.
- Tell the customer which requested item is unavailable.
- Offer the option to cancel the entire order already placed.

## Delivery date rules

Supplier delivery lead time from supplier to Beaver's Choice:

| Quantity | Lead time |
| --- | --- |
| 10 or fewer | Same day |
| 11 to 100 | 1 day |
| 101 to 1000 | 4 days |
| More than 1000 | 7 days |

Customer delivery lead time from Beaver's Choice to the customer:

| Quantity | Lead time |
| --- | --- |
| 10 or fewer | Same day |
| 11 to 100 | 1 day |
| 101 to 1000 | 2 days |
| More than 1000 | 3 days |

If stock is available immediately, customer delivery starts from the request
date. If supplier stock is needed, customer delivery starts after the supplier
delivery date.

## Pricing and tax rules

- Customer quotes should show subtotal, HST, and final total.
- HST is 13%.
- Customer shipping is free.
- Supplier stock orders do not add a separate customer-facing tax.
- Historical quote search can inform context, while catalog unit prices provide
  the internal price anchors.

# Response sanitization

Before customer text is saved, it is passed through
`sanitize_customer_response(text)`. This function replaces or blocks internal
implementation details such as:

- Tool calls.
- Function calls.
- API references.
- Database references.
- Stack traces.
- Internal request limit wording.
- Raw transaction identifiers.
- Cash-balance wording.

If forbidden internal wording remains after replacement, the function returns a
generic customer-safe fallback response.

# Observability

The script configures Logfire locally:

```python
logfire.configure(service_name="beavers-choice", send_to_logfire=False)
```

It also attaches a file handler:

```python
file_handler = logging.FileHandler("agent_trace.log")
logger = logging.getLogger("logfire")
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
```

This produces `agent_trace.log` during execution. The per-request `output_*.txt`
files are also useful for auditing prompts, internal responses, and
customer-facing responses.

# Troubleshooting

## Missing API key

If model calls fail because the API key is missing, create `.env` from the
template and add a valid key:

```bash
cp example.env .env
```

```env
UDACITY_OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

Run the script from the repository root so `load_dotenv()` can find `.env`.

## CSV file not found

The script uses relative paths. Run it from the repository root:

```bash
python project_solution.py
```

Required CSV files:

- `quote_requests.csv`
- `quotes.csv`
- `quote_requests_sample.csv`

## SQLite database is locked

Close any other process that may be using `munder_difflin.db`. If you do not
need the current generated database, delete it and rerun:

```bash
rm -f munder_difflin.db
python project_solution.py
```

## Dependency installation fails

Upgrade `pip` and reinstall:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If your Python version causes package compatibility issues, recreate the virtual
environment with Python 3.10 or 3.11 and reinstall.

## Model or endpoint errors

Check that:

- `UDACITY_OPENAI_API_KEY` is set and valid.
- The Vocareum OpenAI-compatible endpoint is reachable.
- Your environment has access to the configured model names.
- Your account has enough quota for all requests in `quote_requests_sample.csv`.

## Responses contain too little detail

The sanitizer intentionally removes internal implementation details from
customer-facing responses. Check the corresponding `output_*.txt` file for the
raw internal response and final sanitized response.

# Development notes

- Keep generated runtime files out of commits unless they are intentionally part
  of a report or evaluation.
- Keep `.env` private.
- When adding a new agent, define its Pydantic input/output schema before
  expanding its prompt.
- Prefer deterministic tools for business logic: database reads, transaction
  writes, inventory calculations, date calculations, and quote-history search.
- Keep customer-facing output free of implementation details.
- When changing fulfillment behavior, update both the orchestration prompt and
  affected worker-agent prompts so policies stay consistent.
- The agents are instructed to use request dates from the customer/sample data,
  not the system clock.

# Quick command reference

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure local environment variables
cp example.env .env
# Edit .env and set UDACITY_OPENAI_API_KEY.

# Run the scenario workflow
python project_solution.py
```
