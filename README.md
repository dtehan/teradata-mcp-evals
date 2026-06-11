# teradata-mcp-evals

Eval suite for the [Teradata MCP Server](https://github.com/Teradata/teradata-mcp-server) community edition.

Tests whether an LLM agent correctly selects the right MCP tool and forms valid parameters given a natural language prompt. Uses [deepeval](https://github.com/confident-ai/deepeval) as the evaluation framework and Claude via AWS Bedrock as both the agent and judge.

## What it tests

Each eval case sends a natural language prompt to a Claude agent connected to your running MCP server. The agent's tool selection and parameter choices are then scored by a judge LLM.

Three edge case types are tested per tool:

| Type | What it catches |
|---|---|
| `happy_path` | Normal usage — agent picks the right tool with correct params |
| `ambiguous_selection` | Two tools could plausibly apply — tests whether descriptions are distinct enough |
| `missing_parameter` | Required info is absent — agent must ask for clarification, not hallucinate |
| `multi_tool` | Task requires chaining multiple tools in order |

**In-scope modules:** `base`, `dba`, `sec`, `qlty`, `chat`, `plot`, `tmpl`

## Prerequisites

- Python 3.11+
- Teradata MCP Server running at `http://127.0.0.1:8001` connected to a ClearScape Analytics Experience instance
- AWS account with Bedrock access to an Anthropic Claude model

## Setup

### Option A — uv (recommended)

[uv](https://docs.astral.sh/uv/) manages the virtual environment automatically.

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone <this-repo>
cd teradata-mcp-evals

# Create .venv and install dependencies
uv venv
uv sync

# Activate the virtual environment
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

cp .env.example .env
```

With the venv active you can call scripts directly (`python run_evals.py`). Alternatively, skip activation and prefix every command with `uv run` — it uses the project venv automatically.

### Option B — standard venv + pip

```bash
git clone <this-repo>
cd teradata-mcp-evals

python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

pip install -e .

cp .env.example .env
```

Edit `.env` with your AWS credentials and Bedrock model ID:

```dotenv
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
```

Credentials follow the standard boto3 chain — env vars, `~/.aws/credentials`, or an IAM instance profile all work. Set `AWS_SESSION_TOKEN` as well if using temporary credentials.

## Generating test cases

The `base`, `sec`, `chat`, and `plot` modules ship with hand-authored cases. For `dba`, `qlty`, and `tmpl`, generate happy path cases from the live tool descriptions first:

```bash
# Make sure the MCP server is running, then:
python generate_cases.py --module dba
python generate_cases.py --module qlty
python generate_cases.py --module tmpl

# Or generate all in-scope modules at once:
python generate_cases.py
```

> If you skipped venv activation, prefix each command with `uv run` (e.g. `uv run python generate_cases.py`).

The generator connects to the MCP server, reads each tool's description, and asks Bedrock Claude to draft a natural language prompt and expected parameters. Results are written to `cases/<module>.json`.

After generating, open the JSON files and hand-author `ambiguous_selection`, `missing_parameter`, and `multi_tool` cases — these require human judgement and cannot be generated cleanly from descriptions alone.

### Generator flags

```bash
# Preview without writing to disk
python generate_cases.py --dry-run

# Overwrite existing happy_path cases (e.g. after a description change)
python generate_cases.py --overwrite
```

## Setting up test data

The eval suite needs two tables in your ClearScape database. Create them once before running evals:

```bash
python setup_test_data.py
```

This creates:

| Table | Purpose |
|---|---|
| `evals_employees` | employee_id, name, department, salary, region, hire_date, manager_id — used by base, qlty (stats), plot (radar) |
| `evals_orders` | order_id, customer_name, order_date, ship_date, amount, product_category, quantity — used by base, qlty (missing/negative values), plot (line/pie/polar) |

`ship_date` is nullable in `evals_orders` (unshipped orders) and `amount` includes negative values (refunds) to support the qlty edge case tests.

Set `EVALS_DATABASE` in `.env` to the database where these tables should be created — this is usually your ClearScape username.

All test cases use `{EVALS_DATABASE}` as a placeholder which is substituted at runtime, so the same JSON works across environments.

To clean up after testing:

```bash
python teardown_test_data.py
```

To recreate tables from scratch:

```bash
python setup_test_data.py --drop-first
```

## Running evals

The MCP server must be running before you start evals.

```bash
# Run all modules
python run_evals.py

# Run a single module
python run_evals.py --module base

# Filter by case type
python run_evals.py --type ambiguous_selection

# Verbose output
python run_evals.py --verbose
```

deepeval generates a results summary in the terminal. Full results are stored locally in the `results/` directory (not committed).

## Project structure

```
teradata-mcp-evals/
  agent/
    client.py          # Multi-turn MCP agent loop (boto3 Converse API + mcp SDK)
  judge/
    bedrock_llm.py     # DeepEvalBaseLLM wrapper for Bedrock Claude
    metrics.py         # ToolCorrectnessMetric + clarification GEval
  cases/
    base.json          # Test cases — base module (pre-populated)
    sec.json           # Test cases — security module (pre-populated)
    chat.json          # Test cases — chat module (pre-populated)
    plot.json          # Test cases — plot module (pre-populated)
    dba.json           # Test cases — DBA module (run generator)
    qlty.json          # Test cases — data quality module (run generator)
    tmpl.json          # Test cases — template module (run generator)
  tests/
    conftest.py        # Shared fixtures (bedrock_client, judge_llm, agent runner)
    test_base.py       # pytest file — base module
    test_dba.py        # pytest file — DBA module
    test_sec.py        # pytest file — security module
    test_qlty.py       # pytest file — data quality module
    test_chat.py       # pytest file — chat module
    test_plot.py       # pytest file — plot module
    test_tmpl.py       # pytest file — template module
  generate_cases.py    # Bootstrap generator — drafts happy_path cases from live descriptions
  run_evals.py         # CLI entry point
  pyproject.toml
  .env.example
```

## Test case format

Cases are stored as JSON per module. Each case has:

```json
{
  "id": "base_readQuery_happy",
  "type": "happy_path",
  "description": "What this tests",
  "input": "The natural language prompt sent to the agent",
  "expected_tools": [
    {
      "name": "base_readQuery",
      "params": { "query": "SELECT * FROM sales SAMPLE 10" }
    }
  ]
}
```

For `missing_parameter` cases, `expected_tools` is an empty array — the agent should ask for clarification rather than call any tool. For `multi_tool` cases, list the expected tool calls in order.

## Evaluation logic

| Metric | Applies to | How it scores |
|---|---|---|
| `ToolCorrectnessMetric` | All cases | LLM judge: was the right tool called with correct params? |
| `Clarification Check` (GEval) | `missing_parameter` only | LLM judge: did the agent ask for the missing info rather than hallucinate? |

Tool name selection uses the judge LLM to evaluate correctness. Parameter correctness is evaluated semantically — equivalent SQL written differently still passes.

## Adding cases for a new tool

1. Run `generate_cases.py` to draft a happy path case.
2. Open `cases/<module>.json`.
3. Add an `ambiguous_selection` case: find another tool in the same module whose purpose overlaps, then write a prompt that could plausibly call either tool — set `expected_tools` to the one that should win.
4. Add a `missing_parameter` case: write a vague prompt that omits a required parameter, set `expected_tools` to `[]`.
5. Add a `multi_tool` case if the tool is naturally part of a workflow with other tools.
