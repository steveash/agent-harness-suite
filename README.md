# Agent Harness Suite

Benchmark suite for evaluating coding agent harnesses on top of the
[Inspect AI](https://inspect.aisi.org.uk/) backbone.

## Stack

- Python **3.12+**
- [`inspect-ai`](https://inspect.aisi.org.uk/) — task framework, sandboxing, agent bridge
- [`inspect-swe`](https://meridianlabs-ai.github.io/inspect_swe/) — SWE-style task helpers
- [`inspect-harbor`](https://github.com/UKGovernmentBEIS/inspect_harbor) — benchmark adapters
- `ruff`, `mypy`, `pytest` + `pytest-asyncio` for the dev gate

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Set `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY` / `GEMINI_API_KEY`) to run a real
benchmark. The tests do not need API access — they use the `mockllm` provider.

## Run the smoke benchmark

```bash
ahs run --benchmark smoke --model haiku45
```

This routes the (no-op fake) harness's HTTP traffic through the Inspect
`sandbox_agent_bridge()` and writes an Inspect log to `./results/`.

Available model presets are defined in `src/ahs/models/registry.py`:
`opus47`, `sonnet46`, `haiku45`, `gpt55`, `gpt54mini`, `gemini25pro`,
`gemini25flash`. You can also pass a fully qualified spec directly, e.g.
`--model mockllm/model` for offline runs.

## Running Terminal-Bench

We wrap [Terminal-Bench 2.1](https://www.tbench.ai/) (Harbor Hub slug
`terminal-bench/terminal-bench-2-1`) via Meridian's
[`inspect_harbor`](https://github.com/meridianlabs-ai/inspect_harbor) adapter,
which delivers TB tasks as native Inspect Tasks. The driving harness is
selected with `--harness`; by default we pair TB with
[`mini-swe-agent`](https://github.com/SWE-agent/mini-swe-agent) — the cheapest
reasonable agent.

Terminal-Bench requires Docker (`sandbox_env_name=docker`) for the per-task
sandboxes Harbor materialises.

### Smoke (5 tasks, fast)

```bash
ahs run --benchmark tb-smoke --model haiku45 --harness mini-swe
```

Target: completes in <15 min on a single host. Override the default 5-task
slice with one or more `--task-names` (glob patterns supported):

```bash
ahs run --benchmark tb-smoke --model haiku45 --harness mini-swe \
    --task-names hello-world --task-names 'fs-*'
```

### Full pass (89 tasks)

```bash
ahs run --benchmark tb --model haiku45 --harness mini-swe --log-dir ./results/tb
```

Target: completes in <8h on a single host. Per-task score, tokens, and
wall-clock are recorded in the Inspect log under `--log-dir`.

### Gotchas

- We pin **Terminal-Bench 2.1** (not 2.0); the 2.1 point release revised 26
  tasks for reward-hacking robustness. `src/ahs/benchmarks/_terminal_bench.py`
  defensively falls back to 2.0 only if `inspect_harbor` ever drops the 2.1
  export.
- We deliberately use `inspect_swe.mini_swe_agent()` rather than
  `inspect_swe.claude_code()` here: the latter had an interactive-mode
  regression ([anthropics/claude-code#36998](https://github.com/anthropics/claude-code/issues/36998))
  at pin time.
- Bridge token accounting was verified in Phase 0. If a real TB run shows
  zero tokens, that's a backbone regression, not a TB issue.

## Definition of Done

```bash
pytest -q                  # both smoke tests pass on a clean checkout
ruff check src/ tests/
mypy src/
```

## Layout

```
src/ahs/
  benchmarks/_smoke.py           # trivial Inspect Task + scorer + fake harness
  benchmarks/_terminal_bench.py  # TB 2.1 wrappers (tb2, tb2_smoke) via inspect_harbor
  harnesses/registry.py          # named harness presets (mini-swe, ...)
  models/registry.py             # named model presets
  runner.py                      # `ahs run` CLI
configs/smoke.yaml               # smoke profiles (smoke, tb_smoke)
configs/lite.yaml                # full-pass profiles (tb)
tests/
  test_bridge_redirect.py  # asserts HTTP requests hit the bridge, not anthropic.com
  test_token_accounting.py # asserts model_usage.total_tokens > 0 over the bridge
  test_terminal_bench.py   # asserts TB 2.1 wiring + filtering + harness override
```
