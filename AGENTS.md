# PROJECT KNOWLEDGE BASE

**Generated:** 2026-06-10

## OVERVIEW
**Project:** teradata-mcp-evals
**Stack:**
- **Language:** Python ≥ 3.11
- **Package manager / build tool:** `uv` (recommended) or standard `venv` + `pip`
- **Core dependencies:**
  - `deepeval>=1.4.0`
  - `mcp>=1.0.0`
  - `boto3>=1.34.0`
  - `python-dotenv>=1.0.0`
  - `pytest>=8.0.0`
  - `pytest-asyncio>=0.23.0`
  - `teradatasql>=20.0.0`
- **Auxiliary tools:** `uv` (for virtual‑env & dependency sync), `dotenv` for env files, `deepeval` CLI, `teradatasql` driver, AWS Bedrock (Claude) for LLM calls.

## STRUCTURE
- `agent/` – MCP client wrapper (`client.py`) that runs the LLM‑driven multi‑turn agent.
- `judge/` – LLM wrapper (`bedrock_llm.py`) and evaluation metrics (`metrics.py`).
- `cases/` – JSON files (`<module>.json`) containing generated and hand‑crafted eval cases.
- `tests/` – Pytest suite that drives the evaluation via DeepEval.
- `generate_cases.py` – CLI to auto‑generate happy‑path cases from live MCP tool descriptions.
- `run_evals.py` – Entry point that invokes DeepEval on the test suite.
- `setup_test_data.py` / `teardown_test_data.py` – Helpers to create/drop demo tables in a Teradata database.
- `README.md` – Project overview and usage instructions.
- `.env.example` – Template for required environment variables (AWS, Bedrock, MCP server, Teradata connection, etc.).
- `pyproject.toml` – Project metadata, optional script (`run‑evals`), and Ruff linter configuration.

## COMMANDS
| Action | Command |
|--------|---------|
| **Install dependencies** (recommended) | `curl -LsSf https://astral.sh/uv/install.sh \| sh && uv venv && uv sync` |
| **Install dependencies** (standard) | `python3 -m venv .venv && source .venv/bin/activate && pip install -e .` |
| **Run test data setup** | `python setup_test_data.py` (or `uv run python setup_test_data.py`) |
| **Generate happy‑path cases** | `python generate_cases.py` (or `uv run python generate_cases.py`) |
| **Run the full evaluation suite** | `python run_evals.py` (or `uv run python run_evals.py`) |
| **Run a single module** | `python run_evals.py --module base` |
| **Run with DeepEval verbose output** | `python run_evals.py --verbose` |
| **Run tests directly (pytest)** | `pytest` (or `uv run pytest`) |
| **Tear down test data** | `python teardown_test_data.py` |
| **Package script** | `run‑evals` (installed via `[project.scripts]` in `pyproject.toml`) |

## CODING STANDARDS
- **Language:** Python 3.11+ with full type hints (`typing`, `dataclasses`).
- **Style:** PEP 8‑compliant; line‑length enforced at 120 characters by **Ruff** (configured in `pyproject.toml`).
- **Linting / Formatting:** Ruff is the primary linter/formatter (`ruff` command can be added to CI). No explicit Black config, but Ruff can auto‑fix formatting.
- **Docstrings:** Triple‑quoted module‑level and function docstrings are used throughout.
- **Error handling:** Exceptions are caught and turned into readable messages (e.g., tool errors in `agent/client.py`).
- **Configuration:** Environment variables are loaded via `python-dotenv`; `.env.example` documents required keys.
- **Testing:** Pytest + DeepEval; test cases live in `cases/` (JSON) and `tests/` (pytest files). Async tests use `pytest-asyncio`.

## WHERE TO LOOK
- **Source code:** `agent/`, `judge/`, top‑level scripts (`generate_cases.py`, `run_evals.py`).
- **Tests:** `tests/` directory.
- **Documentation:** `README.md`, `.env.example`, `pyproject.toml`.
- **Eval case definitions:** `cases/` JSON files.
- **Configuration / secrets:** `.env.example` (copy to `.env` and fill in values).

## NOTES
- The suite requires a running **Teradata MCP Server** reachable at `MCP_SERVER_URL` and a **ClearScape database** defined by `EVALS_DATABASE`.
- AWS **Bedrock** credentials must be available (via environment variables or standard AWS credential chain). The LLM model used by default is `anthropic.claude-3-5-sonnet-20241022-v2:0`.
- Before running evals, ensure you have created the demo tables with `setup_test_data.py` (or `teardown_test_data.py` to clean up).
- Use the `generate_cases.py` tool to refresh happy‑path cases whenever MCP tool descriptions change; then hand‑author the ambiguous, missing‑parameter, and multi‑tool cases.
- The repository is installable in editable mode (`pip install -e .`) which also registers the `run‑evals` console script.
