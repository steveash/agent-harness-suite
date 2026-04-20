# Agent Harness Suite

Benchmark suite for evaluating multi-agent coding harnesses across repeatable end-to-end scenarios.

## Overview

Agent Harness Suite runs the same benchmark scenarios against different agent SDK backends (Claude Agent SDK, GitHub Copilot SDK, etc.) and collects comparable metrics: token usage, turns, spawned agents, wall-clock time, and output quality.

**v1 scenario — Repo-to-Plan:** Given a GitHub repo, the agent researches the codebase, proposes a strong next feature, and produces a detailed implementation plan with task decomposition.

## Requirements

- Python 3.11+
- API keys for the harnesses you want to benchmark (see [External Dependencies](#external-dependencies))

## Setup

```bash
git clone https://github.com/steveash/agent-harness-suite.git
cd agent-harness-suite

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,claude]"

cp .env.example .env
# Edit .env and add your keys
```

## External Dependencies

The suite talks to external services. The table below lists every required
credential, what it unlocks, and whether the core offline test suite needs
it. Keys are read from environment variables or a local `.env` file.

| Variable | Required for | Offline tests? | Obtain from |
|----------|--------------|----------------|-------------|
| `ANTHROPIC_API_KEY` | `claude` harness — Claude Agent SDK live runs | No | [console.anthropic.com](https://console.anthropic.com/) |
| `GITHUB_TOKEN` | `copilot` harness — GitHub Copilot SDK; repo access | No | [github.com/settings/tokens](https://github.com/settings/tokens) (scopes: `repo`, `read:user`) |

Optional environment variables (all prefixed with `AHS_`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AHS_LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `AHS_RESULTS_DIR` | `./results` | Directory where benchmark outputs are written |
| `AHS_CLAUDE__MODEL` | `claude-sonnet-4-20250514` | Override the Claude model |
| `AHS_COPILOT__MODEL` | `gpt-4o` | Override the Copilot model |

### Python package dependencies

Installed by `pip install -e ".[dev,claude]"`:

| Package | Purpose |
|---------|---------|
| `pydantic` / `pydantic-settings` | Typed settings loading |
| `click`, `rich` | CLI parsing and terminal output |
| `pyyaml` | YAML config file support |
| `anthropic`, `claude-agent-sdk` | Claude harness (extra: `claude`) |
| `pytest`, `pytest-asyncio`, `ruff`, `mypy` | Dev gates (extra: `dev`) |

The Copilot harness relies on a `copilot-sdk` Python package that is not yet
pinned in `pyproject.toml`; installation instructions will follow once the
live Copilot adapter is finalized (see `ahs-3hn.2`).

### Network dependencies

Live runs reach the following endpoints — allowlist them if you operate
behind an egress proxy:

- `api.anthropic.com` (Claude harness)
- `api.githubcopilot.com` / `api.github.com` (Copilot harness, repo fetch)

## Usage

```bash
ahs info                                           # show config + harnesses
ahs run https://github.com/owner/repo              # run default harness (claude)
ahs run https://github.com/owner/repo --harness claude
ahs run https://github.com/owner/repo --harness claude --harness copilot
ahs --config config.yaml run https://github.com/owner/repo
```

## Configuration

Settings are resolved in priority order:

1. Environment variables (prefix `AHS_` for general settings)
2. `.env` file
3. YAML config file (via `--config`)
4. Defaults

See `config.example.yaml` for all available options.

## Development

```bash
pip install -e ".[dev,claude]"

pytest                     # tests (offline — no API keys required)
ruff check src/ tests/     # lint
mypy src/                  # type check
```

### Definition of Done

Per `CLAUDE.md`, all three gates must pass before submitting work:

```bash
pytest && ruff check src/ tests/ && mypy src/
```

## Manual Verification

Automated tests cover the core wiring (CLI → settings → registry → runner →
adapter → metrics) using stub harnesses — they run offline and need no
credentials. The live SDK paths require real keys and are validated manually.
Follow this checklist after any change that touches the CLI, the runner, or
a harness adapter.

### 1. Offline smoke test (no keys needed)

```bash
pytest                     # expect all tests to pass
ahs info                   # expect a warning about missing keys and both harnesses listed
```

### 2. Settings and key detection

```bash
ANTHROPIC_API_KEY= GITHUB_TOKEN= ahs run https://github.com/python/cpython
# Expect: exits with "Missing API keys: ANTHROPIC_API_KEY, GITHUB_TOKEN" and exit code 1.

AHS_LOG_LEVEL=DEBUG ahs info
# Expect: DEBUG-level logs enabled; harness table lists "claude" and "copilot".
```

### 3. Claude harness — live run (requires `ANTHROPIC_API_KEY`)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...         # still required by the key check
ahs run https://github.com/pallets/click --harness claude
```

Expected:

- CLI prints `Results for claude:` with `status: success`.
- `wall_clock` > 0.
- Non-empty output containing a feature proposal and plan.
- If the run errors, the CLI should still exit cleanly and print the error
  message rather than a traceback.

### 4. Copilot harness — live run (requires `GITHUB_TOKEN`)

```bash
export GITHUB_TOKEN=ghp_...
pip install copilot-sdk             # not yet pinned in pyproject.toml
ahs run https://github.com/pallets/click --harness copilot
```

Expected: same shape as the Claude run. If `copilot-sdk` is not installed,
the adapter's `setup()` raises a clear `RuntimeError` telling you how to fix
it — verify that message is surfaced rather than a raw `ImportError`.

### 5. Multi-harness comparison

```bash
ahs run https://github.com/pallets/click --harness claude --harness copilot
```

Expected: two `Results for <harness>:` blocks, each with its own metrics.
Wall-clock times should differ by more than measurement noise.

### 6. YAML config file

```bash
ahs --config config.example.yaml run https://github.com/pallets/click
```

Expected: settings from the YAML file are applied (check via
`AHS_LOG_LEVEL=DEBUG`, which should now reflect the YAML's log level).

### 7. Failure modes

```bash
ahs run https://github.com/pallets/click --harness nonexistent
# Expect: non-zero exit with "Unknown harness: 'nonexistent'".

ahs run https://github.com/pallets/click --scenario nonexistent
# Expect: non-zero exit with "Unknown scenario: 'nonexistent'".
```

## Architecture

```
src/agent_harness_suite/
  cli.py              # CLI entrypoint (click)
  config.py           # Settings loading (pydantic-settings + YAML)
  runner.py           # Benchmark orchestrator
  adapter.py          # Core HarnessAdapter protocol
  registry.py         # Adapter registry
  adapters/           # Core-protocol adapter implementations
    claude_agent.py   # Claude Agent SDK adapter (live)
    copilot.py        # GitHub Copilot SDK adapter (live)
  harnesses/          # Settings-based harness abstractions
    base.py           # HarnessAdapter base (invoke-based)
    claude_harness.py # Stubbed — see ahs-3hn.2
    copilot_harness.py# Stubbed — see ahs-3hn.2
  scenarios/
    base.py           # Scenario ABC
    repo_to_plan.py   # v1 scenario: repo analysis → feature plan
  metrics/
    collector.py      # Per-run metrics collection
  types.py            # RunResult, RunMetrics, LifecycleEvent, ScenarioConfig
```

## Project Status

This is v1. Current state:

- [x] Project scaffold, config, CLI
- [x] Generic harness adapter layer (ahs-3hn.2)
- [ ] Repo-to-plan scenario — live implementation (ahs-3hn.3)
- [x] Metrics capture and reporting (ahs-3hn.4)
- [x] End-to-end test coverage + dependency docs (ahs-3hn.5)
