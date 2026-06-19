# Teradata MCP Evals — Enhancement TODO

Backlog for improving MCP **tool description quality** via the eval suite.

**Last updated:** 2026-06-18

---

## Resolved decisions

| Question | Decision |
|----------|----------|
| **Primary goal** | Improve **tool description quality** — evals stress-test whether descriptions are distinct and complete enough for correct tool routing. Not optimising for long-horizon agent competence. |
| **Determinism** | As **deterministic as possible**. Prefer `{EVALS_DATABASE}.evals_*` tables and schema-accurate expected params. |
| **LLM judge** | Acceptable as primary scorer. **Deterministic checks** run first and fail fast on structural mismatches. |
| **Multi-turn** | **Shallow only** — 2–3 turns typical, hard cap 7. Purpose: correct tool routing after user supplies missing info. |
| **Module priority** | **P0:** `base` · **P1:** `dba`, `sec` · **P2:** `qlty` · **Lower:** `chat`, `plot`, `tmpl` |
| **MCP description churn** | Regenerate happy paths; manually review ambiguous cases; fix descriptions in MCP server based on failures. |

### Out of scope (for now)

- End-to-end Teradata result correctness (row counts, chart output)
- Long multi-step agent workflows (>7 turns)
- Broad cross-module orchestration beyond description disambiguation
- Full fixtures for every dba/sec system view

---

## Current state

- **~100 cases** across 6 active modules (+ empty `tmpl` stub)
- **Case types:** `happy_path`, `ambiguous_selection`, `missing_parameter`, `multi_tool`, plus optional **`turns`** (multi-turn)
- **Scoring:** deterministic checks (`judge/checks.py`) → `ToolCorrectnessMetric` + `Clarification Check` (GEval)
- **Test data:** `evals_employees`, `evals_orders` in `{EVALS_DATABASE}`
- **Docs:** `README.md` and `AGENTS.md` synced to current features

### Coverage snapshot

| Module | Pri | Cases | happy | ambiguous | missing | multi | multi-turn | Status |
|--------|-----|------:|------:|----------:|--------:|------:|-----------:|--------|
| **base** | P0 | 29 | 9 | 9 | 9† | 2 | 3 | Strong — audit pairs covered |
| **dba** | P1 | 32 | 12 | 10 | 6 | 0 | 3 | Ambiguous + multi-turn pilots |
| **sec** | P1 | 16 | 3 | 5 | 4 | 1 | 3 | Pairs covered; multi-turn pilots |
| **qlty** | P2 | 14 | 8 | 4 | 1 | 1 | 0 | Adequate |
| plot | — | 10 | 4 | 2 | 3 | 1 | 0 | Maintain only |
| chat | — | 5 | 2 | 1 | 2 | 0 | 0 | Maintain only |
| tmpl | — | 0 | — | — | — | — | — | Out of scope until P0–P2 stable |

† base `missing` includes 6 single-turn + 3 multi-turn (`clarify_then_call`) cases.

### Completed infrastructure

| Item | Location |
|------|----------|
| Deterministic structural checks | `judge/checks.py` |
| Ambiguous pair coverage audit | `audit_cases.py` (`--strict`) |
| Live MCP tool-list diff | `audit_cases.py` (`--live-mcp --strict`) |
| CI (unit tests + offline audit) | `.github/workflows/ci.yml` |
| Shallow multi-turn runner | `agent/client.py` → `run_agent_turns()` |
| Case execution + scoring | `tests/case_runner.py` → `assert_eval_case()` |
| `--type` filter (maps to case ID keywords) | `run_evals.py` |
| Unit tests (no Bedrock/MCP) | `tests/test_checks.py`, `tests/test_multi_turn.py` |
| Description churn workflow (documented) | `README.md`, `AGENTS.md` |

---

## Phase 1 — P0 base

Goal: every semantically overlapping base tool pair has an `ambiguous_selection` case.

- [x] Add ambiguous cases for registered pairs (readQuery/tablePreview, tableDDL/columnMetadata, tableList/databaseList, saveDDL/tableDDL, tableAffinity/tableUsage)
- [x] Deterministic checks — tool names, structural params, `{EVALS_DATABASE}` substitution before compare
- [x] Shallow multi-turn pilot (3 cases: tablePreview, tableList, readQuery)
- [x] Live MCP tool-list diff — `--live-mcp` flags missing happy paths and stale case tool names
- [ ] Tighten loose `multi_tool` / cross-module `{}` expected params in plot/sec cases referenced from base workflows
- [ ] Review ambiguous prompts — ensure vocabulary does not mirror tool descriptions

---

## Phase 2 — P1 dba, sec

### dba

- [x] Add **ambiguous_selection** cases (10 pairs: tableSpace/databaseSpace/systemSpace, tableSqlList/userSqlList, tableUsageImpact/resusageSummary/sessionInfo, userDelay/flowControl)
- [x] Ground table/database-scoped happy paths on `{EVALS_DATABASE}` / `evals_orders`
- [ ] Add 1–2 **multi_tool** cases where description boundaries require sequencing
- [ ] Document which dba cases are routing-only (system-wide tools with fictional params)

### sec

- [x] Fix param name drift (`username` → `user_name`)
- [x] Add missing ambiguous pair (userRoles vs rolePermissions)
- [x] Deterministic checks apply via global `judge/checks.py`
- [ ] Add shallow **multi_turn** pilots if single-turn missing_parameter results are inconclusive

---

## Phase 3 — P2 qlty

- [x] Ambiguous pairs registered and covered in `audit_cases.py`
- [x] Deterministic checks for `database_name`, `table_name`, `column_name` via global checks
- [ ] Optional `forbidden_tools` field on ambiguous cases — fail if agent calls the wrong tool from the pair

---

## Phase 4 — Shallow multi-turn

- [x] `turns` schema (2–7 turns) with validation in `tests/case_runner.py`
- [x] Turn 1: no tool calls (deterministic) + Clarification GEval
- [x] Turn 2+: ToolCorrectnessMetric + deterministic param checks
- [x] `AGENT_MAX_STEPS_PER_TURN` (default 3) separate from single-turn budget
- [x] Base pilot cases; single-turn missing cases retained
- [x] Expand multi-turn to **dba** / **sec** missing-parameter scenarios (3 cases each)
- [ ] 3-turn cases only where a two-turn flow is insufficient (stay ≤7)

---

## Phase 5 — MCP description churn & CI

- [x] Ambiguous pair audit script (`audit_cases.py --strict`)
- [x] Regeneration policy documented (`README.md`, `AGENTS.md`)
- [x] Extend audit to **live MCP server** — `--live-mcp` diff (missing happy paths, stale tool names)
- [x] CI gate: unit tests + `audit_cases.py --strict` on every PR (`.github/workflows/ci.yml`)
- [ ] CI eval runs by priority: `--module base`, then `dba`, `sec`, `qlty` (requires Bedrock + MCP secrets)
- [ ] Store MCP server version / git SHA in eval results metadata

---

## Infrastructure (remaining)

- [x] Fix `run_evals.py --type` filter
- [x] `judge/checks.py` with fail-fast behaviour before LLM judge
- [ ] Separate `BEDROCK_AGENT_MODEL_ID` from judge model (reduce agent/judge correlation)
- [ ] Consolidate seven identical `test_*.py` files (nice-to-have)

---

## Deprioritised / later

- Full outcome verification (row counts, response content)
- Deep multi-turn (>7 turns)
- `tmpl` module cases until P0–P2 pass consistently
- `chat` / `plot` expansion beyond maintenance

---

## Success criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Every in-scope tool in base, dba, sec, qlty has a happy_path synced to live schema | ⚠️ Use `audit_cases.py --live-mcp --strict` locally before releases |
| 2 | Every overlapping pair in P0–P1 has an ambiguous_selection case | ✅ Registered pairs covered (`audit_cases.py --strict` passes) |
| 3 | Deterministic checks catch param-name and required-key errors | ✅ `judge/checks.py` |
| 4 | Description churn has documented regenerate → review → fix loop | ✅ README + AGENTS |
| 5 | Shallow multi-turn validates clarify → correct tool on base | ✅ 3 pilot cases |

---

## Next up (recommended order)

1. **Multi-turn expansion** — ~~2-turn pilots for dba/sec missing-parameter cases~~ done
2. **Run live evals** on base + dba + sec ambiguous and multi-turn cases
3. **`audit_cases.py --live-mcp --strict`** before MCP server releases
4. **`BEDROCK_AGENT_MODEL_ID`** — optional split from judge model
5. **CI eval job** (optional) — Bedrock + MCP secrets for scheduled full eval runs

---

## Changelog

### 2026-06-18 — deterministic checks + dba/sec coverage

- `judge/checks.py`, `audit_cases.py`, `tests/test_checks.py`
- 4 base + 10 dba ambiguous cases; dba grounding on eval tables
- sec param normalisation + userRoles/rolePermissions pair

### 2026-06-18 — shallow multi-turn

- `run_agent_turns()`, `tests/case_runner.py`, 3 base pilot cases
- `tests/test_multi_turn.py`; all tests use `assert_eval_case()`

### 2026-06-18 — documentation

- `README.md` fully updated (audit, churn workflow, evaluation logic, project structure)
- `AGENTS.md` synced to match
- `run_evals.py --type` filter fixed

### 2026-06-18 — live MCP audit + CI

- `audit_cases.py --live-mcp` — diff live tools vs cases; stale names + missing happy paths
- `tests/test_audit_cases.py` — unit tests for audit logic
- `.github/workflows/ci.yml` — unit tests + `audit_cases.py --strict` on PRs
