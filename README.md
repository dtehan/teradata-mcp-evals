# teradata-mcp-evals

Eval suite for the [Teradata MCP Server](https://github.com/Teradata/teradata-mcp-server) community edition.

The cases ask an LLM agent to select the right MCP tool and to form valid parameters from natural language. A failed `ambiguous_selection` case usually means that two tool descriptions overlap, or that one description is unclear. [deepeval](https://github.com/confident-ai/deepeval) runs the cases. Claude on AWS Bedrock is the agent and the judge.

## Run the base module

You need Python 3.11 or newer, a Teradata MCP Server at `MCP_SERVER_URL`, and Bedrock credentials. The install steps and the `.env` keys are in [docs/setup.md](docs/setup.md).

```bash
uv venv
uv sync
cp .env.example .env
```

Set `MCP_SERVER_URL`, `EVALS_DATABASE`, and the Bedrock credentials in `.env`. Then create the eval tables and run the `base` module.

```bash
uv run python setup_test_data.py
uv run python run_evals.py --module base
```

The run writes `results/latest_summary.md`. Open that file to see which cases passed and which cases failed. Run `uv run python run_evals.py --list-runs` to print recent runs, with pass counts and fail counts.

## Test a description change

A baseline run reads tool descriptions from the MCP server. To test new descriptions before you edit the server:

1. Run `uv run python run_evals.py`.
2. If cases failed, run `uv run python suggest_overrides.py`. The command writes `results/suggested_overrides.json`.
3. Read `results/suggested_overrides.json`.
4. Run `uv run python suggest_overrides.py --apply`. The command replaces `description_overrides.json` with that draft.
5. Run `uv run python run_evals.py --with-description-overrides`.
6. If that run passes, copy the descriptions into the MCP server repository.
7. Run `uv run python run_evals.py` again.

Commands, result files, and a diagram are in [docs/workflow.md](docs/workflow.md).

## Documentation

| Doc | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Install, `.env`, test data, unit tests |
| [docs/workflow.md](docs/workflow.md) | Running evals, overrides, results |
| [docs/cases.md](docs/cases.md) | Case types, JSON format, scoring, adding cases |
| [docs/structure.md](docs/structure.md) | Repository layout |
| [backup/README.md](backup/README.md) | Optional case generation and audit scripts |
