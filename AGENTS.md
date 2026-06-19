# PROJECT KNOWLEDGE BASE

**Updated:** 2026-06-18

## OVERVIEW

**Project:** teradata-mcp-evals

**Purpose:** Eval suite for the [Teradata MCP Server](https://github.com/Teradata/teradata-mcp-server) community edition. Primary goal is **MCP tool description quality** — tests whether an LLM agent selects the right tool and forms valid parameters from natural language. Failures on `ambiguous_selection` cases usually indicate overlapping or unclear tool descriptions in the MCP server.

**Stack:**
- **Language:** Python ≥ 3.11
- **Package manager / build tool:** `uv` (recommended) or standard `venv` + `pip`
- **Core dependencies:**
  - `deepeval>=1.4.0`
  - `mcp>=1.0.0`
  - `boto3>=1.34.0`
  - `python-dotenv>=1.0.0`
  - `pytest>=8.0.0`
  - `pytest-asyncio>=0.23.0`
  - `teradatasql>=20.0.0`
- **Auxiliary tools:** `uv`, `dotenv`, deepeval CLI, `teradatasql` driver, AWS Bedrock (Claude) for agent + judge LLM calls

**Case types:**

| Type | Purpose |
|------|---------|
| `happy_path` | Unambiguous prompt → correct tool + params |
| `ambiguous_selection` | Two tools could apply → tests description distinctness |
| `missing_parameter` | Vague prompt → agent must ask, not hallucinate |
| `multi_tool` | Chained tool calls in order |
| `multi_turn` (optional) | 2–7 turns: clarify first, then correct tool after user supplies info |

**Module priority:** P0 `base` · P1 `dba`, `sec` · P2 `qlty` · maintained `chat`, `plot`, `tmpl`

## STRUCTURE

```
agent/
  client.py           # run_agent() single-turn; run_agent_turns() shallow multi-turn
judge/
  bedrock_llm.py      # DeepEvalBaseLLM wrapper for Bedrock Converse API
  checks.py           # Deterministic structural checks (fail before LLM judge)
  metrics.py          # ToolCorrectnessMetric + Clarification GEval
cases/
  <module>.json       # Eval case definitions per MCP module prefix
tests/
  conftest.py         # Fixtures, {EVALS_DATABASE} substitution, assert_eval_case()
  case_runner.py      # Single/multi-turn execution and per-turn scoring
  test_<module>.py    # One pytest file per module (all use assert_eval_case)
  test_checks.py      # Unit tests for judge/checks.py
  test_multi_turn.py  # Unit tests for multi-turn schema validation
audit_cases.py        # Ambiguous tool-pair coverage audit (--strict for CI)
generate_cases.py     # Draft happy_path cases from live MCP tool descriptions
run_evals.py          # CLI entry point (deepeval + pytest)
setup_test_data.py    # Create evals_employees / evals_orders in EVALS_DATABASE
preflight.py          # Verify eval tables exist before live eval runs
teardown_test_data.py
todo.md               # Enhancement backlog and resolved decisions
README.md             # Full user documentation
.env.example          # Required environment variables
pyproject.toml        # Project metadata, Ruff config, pytest paths
```

## COMMANDS

| Action | Command |
|--------|---------|
| **Install dependencies** (recommended) | `curl -LsSf https://astral.sh/uv/install.sh \| sh && uv venv && uv sync` |
| **Install dependencies** (standard) | `python3 -m venv .venv && source .venv/bin/activate && pip install -e .` |
| **Run test data setup** | `python setup_test_data.py` (or `uv run python setup_test_data.py`) |
| **Verify eval tables** | `python preflight.py` (also runs automatically via `run_evals.py`) |
| **Generate happy-path cases** | `python generate_cases.py` (or `uv run python generate_cases.py`) |
| **Regenerate after description change** | `python generate_cases.py --module base --overwrite` |
| **Audit ambiguous pair coverage** | `python audit_cases.py --strict` |
| **Audit against live MCP tools** | `python audit_cases.py --live-mcp --strict` (requires running MCP server) |
| **CI (local equivalent)** | `uv run pytest tests/test_checks.py tests/test_multi_turn.py tests/test_audit_cases.py -v && uv run python audit_cases.py --strict` |
| **Run full eval suite** | `python run_evals.py` (or `uv run python run_evals.py`) |
| **Run one module** | `python run_evals.py --module base` |
| **Filter by case type** | `python run_evals.py --module base --type ambiguous_selection` |
| **Run multi-turn cases only** | `python run_evals.py --module base --type multi_turn` |
| **Verbose output** | `python run_evals.py --verbose` |
| **Unit tests (no MCP/Bedrock)** | `uv run pytest tests/test_checks.py tests/test_multi_turn.py` |
| **Run tests directly (pytest)** | `pytest` (or `uv run pytest`) |
| **Tear down test data** | `python teardown_test_data.py` |
| **Package script** | `run-evals` (installed via `[project.scripts]` in `pyproject.toml`) |

### `--type` filter keywords (maps to pytest `-k` on case IDs)

| `--type` | Matches IDs containing |
|----------|------------------------|
| `happy_path` | `happy` |
| `ambiguous_selection` | `ambiguous` |
| `missing_parameter` | `missing` |
| `multi_tool` | `multi_tool` |
| `multi_turn` | `clarify_then_call` |

## CODING STANDARDS

- **Language:** Python 3.11+ with full type hints (`typing`, `dataclasses`).
- **Style:** PEP 8; line length 120 (Ruff in `pyproject.toml`).
- **Docstrings:** Triple-quoted module- and function-level docstrings.
- **Error handling:** Exceptions caught and surfaced as readable messages (e.g. tool errors in `agent/client.py`).
- **Configuration:** `python-dotenv`; secrets in `.env` (never commit). Key vars:
  - `MCP_SERVER_URL`, `EVALS_DATABASE`, `BEDROCK_MODEL_ID`
  - `BEDROCK_JUDGE_MODEL_ID` (optional, defaults to agent model)
  - `AGENT_MAX_STEPS` (default 5, single-turn)
  - `AGENT_MAX_STEPS_PER_TURN` (default 3, multi-turn)
- **Testing:** Pytest + DeepEval for integration evals; pure unit tests for `judge/checks.py` and schema validation without Bedrock/MCP.

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Agent loop / MCP session | `agent/client.py` |
| Deterministic checks | `judge/checks.py` |
| LLM judge metrics | `judge/metrics.py` |
| Run + score any case | `tests/case_runner.py` → `assert_eval_case()` |
| Case JSON definitions | `cases/<module>.json` |
| Ambiguous pair registry / live MCP diff | `audit_cases.py` → `AMBIGUOUS_PAIRS`, `--live-mcp` |
| CI workflow | `.github/workflows/ci.yml` |
| Happy-path generator | `generate_cases.py` |
| Test data setup / preflight | `setup_test_data.py`, `preflight.py` |
| `{EVALS_DATABASE}` substitution | `tests/conftest.py` → `_substitute()` |
| Enhancement backlog | `todo.md` |
| User-facing docs | `README.md` |

## EVAL FLOW

1. Test loads case from `cases/<module>.json` via `load_cases()`.
2. `{EVALS_DATABASE}` placeholder substituted at runtime.
3. **Single-turn:** `run_agent()` → deterministic checks → deepeval metrics.
4. **Multi-turn:** `run_agent_turns()` (one MCP session, max 7 turns) → per-turn checks:
   - Clarification turns: no tools + Clarification GEval
   - Tool turns: deterministic checks + ToolCorrectnessMetric
5. Structural failures in `judge/checks.py` raise `AssertionError` before the judge runs.

## CASE JSON CONVENTIONS

**Single-turn:** top-level `input`, `type`, `expected_tools`.

**Multi-turn:** top-level `turns` (2–7 entries), each with `input` and exactly one of:
- `"expect": "clarification"`
- `"expected_tools": [...]`

Multi-turn case IDs should contain `clarify_then_call` for `--type multi_turn` filtering.

Param names in `expected_tools` must match live MCP schemas (e.g. `sql` for `base_readQuery`, `user_name` for sec tools). Use `{EVALS_DATABASE}.evals_*` tables for deterministic grounding in base, qlty, plot, and dba cases where applicable.

## MCP DESCRIPTION CHURN WORKFLOW

When a tool description changes in the MCP server:

1. `generate_cases.py --module <m> --overwrite` for happy paths
2. Manually review `ambiguous_selection` cases in that module
3. `audit_cases.py --module <m> --strict`
4. Optionally `audit_cases.py --live-mcp --strict` before MCP server releases
5. Run evals; fix descriptions in MCP server repo based on ambiguous failures
6. Add new tool pairs to `AMBIGUOUS_PAIRS` in `audit_cases.py` when overlap is discovered

## NOTES

- Requires running **Teradata MCP Server** at `MCP_SERVER_URL` and **ClearScape** database `EVALS_DATABASE` with demo tables from `setup_test_data.py`.
- AWS Bedrock credentials via standard boto3 chain. Default model: `anthropic.claude-3-5-sonnet-20241022-v2:0`.
- Eval results stored in `results/` (not committed).
- Do not commit `.env` or credentials.
- Hand-author edge cases (`ambiguous_selection`, `missing_parameter`, `multi_tool`, `multi_turn`) after generating happy paths — generator cannot replace human judgement on description boundaries.
- Prompt vocabulary should differ from tool descriptions (same rule enforced in `generate_cases.py` DRAFT_PROMPT).
