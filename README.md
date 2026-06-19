# teradata-mcp-evals

Eval suite for the [Teradata MCP Server](https://github.com/Teradata/teradata-mcp-server) community edition.

Tests whether an LLM agent correctly selects the right MCP tool and forms valid parameters given a natural language prompt. The primary goal is to **improve MCP tool description quality** — ambiguous or incomplete descriptions show up as routing failures. Uses [deepeval](https://github.com/confident-ai/deepeval) as the evaluation framework and Claude via AWS Bedrock as both the agent and judge.

## What it tests

Each eval case sends a natural language prompt to a Claude agent connected to your running MCP server. The agent's tool selection and parameter choices are scored by deterministic structural checks first, then by a judge LLM where semantic judgement is needed.

| Type | What it catches |
|---|---|
| `happy_path` | Normal usage — agent picks the right tool with correct params |
| `ambiguous_selection` | Two tools could plausibly apply — tests whether descriptions are distinct enough |
| `missing_parameter` | Required info is absent — agent must ask for clarification, not hallucinate |
| `multi_tool` | Task requires chaining multiple tools in order |
| `multi_turn` (optional) | Shallow clarification dialog — ask first, then call the right tool once the user supplies missing info |

**Priority modules:** `base`, `dba`, `sec`, `qlty` · **Maintained:** `chat`, `plot`, `tmpl`

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

Edit `.env` with your credentials and configuration:

```dotenv
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Optional — defaults to BEDROCK_MODEL_ID
# BEDROCK_JUDGE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

MCP_SERVER_URL=http://127.0.0.1:8001/mcp
EVALS_DATABASE=your_database_name

# Agent turn limits
AGENT_MAX_STEPS=5                  # single-turn cases
AGENT_MAX_STEPS_PER_TURN=3         # multi-turn cases (per conversation turn)
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

After generating, open the JSON files and hand-author `ambiguous_selection`, `missing_parameter`, `multi_tool`, and (optionally) shallow `multi_turn` cases — these require human judgement and cannot be generated cleanly from descriptions alone.

### Generator flags

```bash
# Preview without writing to disk
python generate_cases.py --dry-run

# Overwrite existing happy_path cases (e.g. after a description change)
python generate_cases.py --overwrite
```

## Auditing case coverage

`audit_cases.py` validates eval cases offline and can optionally diff against a **live MCP server**.

### Offline audit (CI-safe)

Checks registered ambiguous tool pairs in `cases/*.json` for base, dba, sec, and qlty:

```bash
# Report gaps for priority modules
python audit_cases.py

# Fail when pairs are missing coverage (used in CI)
python audit_cases.py --strict

# One module only
python audit_cases.py --module base --strict
```

Registered pairs live in `audit_cases.py` (e.g. `base_readQuery` vs `base_tablePreview`). Extend that registry when you identify new description overlap between tools.

### Live MCP diff (local / pre-release)

Requires a running MCP server at `MCP_SERVER_URL`:

```bash
# Diff live tool list vs cases — missing happy paths and stale tool names
python audit_cases.py --live-mcp

# Fail on any gap (priority modules require happy_path for every live tool)
python audit_cases.py --live-mcp --strict

# Live diff only, skip ambiguous pair checks
python audit_cases.py --live-mcp --skip-pairs --module base
```

| Check | Offline `--strict` | `--live-mcp --strict` |
|---|---|---|
| Ambiguous pair coverage | ✅ | ✅ (unless `--skip-pairs`) |
| Missing `happy_path` for live tools | — | ✅ (base, dba, sec, qlty) |
| Stale tool names in cases | — | ✅ |
| Non-priority modules (chat, plot) | — | stale names only; missing happy paths noted, not failed |

## Continuous integration

GitHub Actions runs on every push and pull request to `main` / `master`:

1. `pytest tests/test_checks.py tests/test_multi_turn.py tests/test_audit_cases.py`
2. `python audit_cases.py --strict`

Workflow file: `.github/workflows/ci.yml`. Live MCP evals are not run in CI — run `audit_cases.py --live-mcp --strict` locally before MCP server releases.

## When MCP tool descriptions change

Follow this workflow when a tool description is updated in the MCP server:

1. **Regenerate happy paths** for the affected module:
   ```bash
   python generate_cases.py --module base --overwrite
   ```
2. **Review hand-authored cases** — especially `ambiguous_selection` prompts for that module. Wording that relied on the old description boundary may need updating.
3. **Run the audit** to confirm pair coverage and (optionally) sync with live tools:
   ```bash
   python audit_cases.py --module base --strict
   python audit_cases.py --live-mcp --strict   # requires running MCP server
   ```
4. **Run evals** and treat `ambiguous_selection` failures as description feedback — fix descriptions in the MCP server repo, not just the eval prompts.
5. **Re-run** until routing stabilises.

See `todo.md` for the full enhancement backlog.

## Setting up test data

The eval suite needs two tables in your ClearScape database. Create them once before running evals:

```bash
python setup_test_data.py
```

This creates:

| Table | Purpose |
|---|---|
| `evals_employees` | employee_id, name, department, salary, region, hire_date, manager_id — used by base, qlty (stats), plot (radar) |
| `evals_orders` | order_id, customer_name, order_date, ship_date, amount, product_category, quantity — used by base, qlty (missing/negative values), plot (line/pie/polar), dba (where grounded) |

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

Before running live evals:

1. **Test tables** — `python setup_test_data.py` (once per environment)
2. **MCP server** — running at `MCP_SERVER_URL`
3. **Preflight** — `run_evals.py` checks eval tables automatically; or run standalone:

```bash
python preflight.py
```

```bash
# Run all modules (preflight check runs first)
python run_evals.py

# Run a single module
python run_evals.py --module base

# Filter by case type (maps to substrings in pytest case IDs)
python run_evals.py --module base --type ambiguous_selection
python run_evals.py --module base --type missing_parameter
python run_evals.py --module base --type multi_turn

# Verbose output
python run_evals.py --verbose

# Skip Teradata preflight (not recommended for live eval runs)
python run_evals.py --skip-preflight
```

| `--type` value | Matches case IDs containing |
|---|---|
| `happy_path` | `happy` |
| `ambiguous_selection` | `ambiguous` |
| `missing_parameter` | `missing` |
| `multi_tool` | `multi_tool` |
| `multi_turn` | `clarify_then_call` |

You can also pass pytest `-k` expressions directly via deepeval, e.g. `deepeval test run tests/ -k "test_base and tablePreview"`.

deepeval generates a results summary in the terminal. Full results are stored locally in the `results/` directory (not committed).

## Project structure

```
teradata-mcp-evals/
  agent/
    client.py          # MCP agent loop — single-turn (run_agent) and multi-turn (run_agent_turns)
  judge/
    bedrock_llm.py     # DeepEvalBaseLLM wrapper for Bedrock Claude
    checks.py          # Deterministic structural checks (tool names, required params)
    metrics.py         # ToolCorrectnessMetric + clarification GEval
  cases/
    base.json          # Test cases — base module (pre-populated)
    sec.json           # Test cases — security module (pre-populated)
    chat.json          # Test cases — chat module (pre-populated)
    plot.json          # Test cases — plot module (pre-populated)
    dba.json           # Test cases — DBA module (generator + hand-authored edge cases)
    qlty.json          # Test cases — data quality module (generator + hand-authored edge cases)
    tmpl.json          # Test cases — template module (run generator)
  tests/
    conftest.py        # Shared fixtures, {EVALS_DATABASE} substitution, assert_eval_case()
    case_runner.py     # Single- and multi-turn case execution and scoring
    test_base.py       # pytest file — base module
    test_dba.py        # pytest file — DBA module
    test_sec.py        # pytest file — security module
    test_qlty.py       # pytest file — data quality module
    test_chat.py       # pytest file — chat module
    test_plot.py       # pytest file — plot module
    test_tmpl.py       # pytest file — template module
    test_checks.py     # Unit tests — deterministic checks
    test_multi_turn.py # Unit tests — multi-turn case schema validation
  audit_cases.py       # Ambiguous pair audit (offline) + optional live MCP diff
  generate_cases.py    # Bootstrap generator — drafts happy_path cases from live descriptions
  run_evals.py         # CLI entry point
  preflight.py         # Verify evals_employees / evals_orders exist before live evals
  setup_test_data.py   # Create evals_employees / evals_orders tables
  teardown_test_data.py
  todo.md              # Enhancement backlog and decisions
  .github/workflows/ci.yml  # PR checks: unit tests + audit_cases.py --strict
  pyproject.toml
  .env.example
```

## Test case format

Cases are stored as JSON per module.

### Single-turn cases

```json
{
  "id": "base_readQuery_happy",
  "type": "happy_path",
  "description": "What this tests",
  "input": "The natural language prompt sent to the agent",
  "expected_tools": [
    {
      "name": "base_readQuery",
      "params": { "sql": "SELECT * FROM {EVALS_DATABASE}.evals_employees SAMPLE 10" }
    }
  ]
}
```

For `missing_parameter` cases, `expected_tools` is an empty array — the agent should ask for clarification rather than call any tool. For `multi_tool` cases, list the expected tool calls in order.

Param names in `expected_tools` must match the live MCP tool schema (e.g. `sql`, not `query`, for `base_readQuery`).

### Shallow multi-turn cases (optional)

Some cases use a `turns` array instead of top-level `input` / `expected_tools`. Each turn is scored in the same MCP session. **Minimum 2 turns, maximum 7.**

```json
{
  "id": "base_tablePreview_clarify_then_call",
  "type": "missing_parameter",
  "description": "Agent asks which table, then previews after user clarifies",
  "turns": [
    { "input": "Preview some rows for me", "expect": "clarification" },
    {
      "input": "Preview rows from {EVALS_DATABASE}.evals_employees",
      "expected_tools": [
        {
          "name": "base_tablePreview",
          "params": {
            "database_name": "{EVALS_DATABASE}",
            "table_name": "evals_employees"
          }
        }
      ]
    }
  ]
}
```

Each turn must set **exactly one** of:

- `"expect": "clarification"` — no tool call on that turn
- `"expected_tools": [...]` — tool routing scored on that turn

Multi-turn case IDs should contain `clarify_then_call` so `--type multi_turn` can filter them.

## Evaluation logic

Every case runs **deterministic checks first**, then LLM judge metrics where needed.

### Deterministic checks (`judge/checks.py`)

| Check | Applies to |
|---|---|
| No tool calls | `missing_parameter` (single-turn) and clarification turns |
| Exact tool name | Primary tool on happy/ambiguous cases; all tools on `multi_tool` |
| Exact param values | Structural keys: `database_name`, `table_name`, `column_name`, `user_name`, `role_name` |
| Param key presence | `sql` / `query` — key must exist; value judged semantically by LLM |

Structural failures fail the case immediately without invoking the judge.

### LLM judge metrics (`judge/metrics.py`)

| Metric | Applies to | How it scores |
|---|---|---|
| `ToolCorrectnessMetric` | Cases with `expected_tools` | LLM judge: was the right tool called with correct params? |
| `Clarification Check` (GEval) | `missing_parameter` (single-turn) and clarification turns | LLM judge: did the agent ask for the missing info rather than hallucinate? |

Tool name selection uses the judge LLM to evaluate correctness. Parameter correctness is evaluated semantically — equivalent SQL written differently still passes.

## Adding cases for a new tool

1. Run `generate_cases.py` to draft a happy path case.
2. Open `cases/<module>.json`.
3. Add an `ambiguous_selection` case: find another tool in the same module whose purpose overlaps, then write a prompt that could plausibly call either tool — set `expected_tools` to the one that should win.
4. Register the tool pair in `audit_cases.py` if not already listed.
5. Add a `missing_parameter` case: write a vague prompt that omits a required parameter, set `expected_tools` to `[]`.
6. Optionally add a shallow `multi_turn` case: turn 1 vague prompt with `"expect": "clarification"`, turn 2 user supplies the missing info with `expected_tools`.
7. Add a `multi_tool` case if the tool is naturally part of a workflow with other tools.
8. Run `python audit_cases.py --module <module> --strict` to confirm pair coverage.

When writing prompts, use vocabulary **different from the tool descriptions** — evals should stress-test descriptions, not parrot them.
