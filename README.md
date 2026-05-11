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

## Definition of Done

```bash
pytest -q                  # both smoke tests pass on a clean checkout
ruff check src/ tests/
mypy src/
```

## Layout

```
src/ahs/
  benchmarks/_smoke.py     # trivial Inspect Task + scorer + fake harness
  harnesses/               # harness adapters (filled in by later phases)
  models/registry.py       # named model presets
  runner.py                # `ahs run` CLI
configs/smoke.yaml         # smoke run config
tests/
  test_bridge_redirect.py  # asserts HTTP requests hit the bridge, not anthropic.com
  test_token_accounting.py # asserts model_usage.total_tokens > 0 over the bridge
```
