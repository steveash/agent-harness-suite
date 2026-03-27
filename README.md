# Agent Harness Suite

Benchmark suite for evaluating multi-agent coding harnesses across repeatable end-to-end scenarios.

## Overview

Agent Harness Suite runs the same benchmark scenarios against different agent SDK backends (Claude Agent SDK, GitHub Copilot SDK, etc.) and collects comparable metrics: token usage, turns, spawned agents, wall-clock time, and output quality.

**v1 scenario — Repo-to-Plan:** Given a GitHub repo, the agent researches the codebase, proposes a strong next feature, and produces a detailed implementation plan with task decomposition.

## Requirements

- Python 3.11+
- API keys for the harnesses you want to benchmark (see below)

## Setup

```bash
# Clone the repo
git clone https://github.com/steveash/agent-harness-suite.git
cd agent-harness-suite

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,claude]"

# Configure API keys
cp .env.example .env
# Edit .env and add your keys
```

### Required API Keys

| Key | Purpose | Where to get it |
|-----|---------|-----------------|
| `ANTHROPIC_API_KEY` | Claude Agent SDK harness | [console.anthropic.com](https://console.anthropic.com/) |
| `GITHUB_TOKEN` | Repo access + Copilot SDK | [github.com/settings/tokens](https://github.com/settings/tokens) |

Set these in `.env` or export them as environment variables.

## Usage

```bash
# Show current config and available harnesses
ahs info

# Run the repo-to-plan benchmark against a repo
ahs run https://github.com/owner/repo

# Run with a specific harness
ahs run https://github.com/owner/repo --harness claude

# Run with multiple harnesses for comparison
ahs run https://github.com/owner/repo --harness claude --harness copilot

# Use a YAML config file
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
# Install dev dependencies
pip install -e ".[dev,claude]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Architecture

```
src/agent_harness_suite/
  cli.py              # CLI entrypoint (click)
  config.py           # Settings loading (pydantic-settings + YAML)
  runner.py           # Benchmark orchestrator
  harnesses/
    base.py           # HarnessAdapter ABC
    claude_harness.py # Claude Agent SDK adapter
    copilot_harness.py# GitHub Copilot SDK adapter
  scenarios/
    base.py           # Scenario ABC
    repo_to_plan.py   # v1 scenario: repo analysis -> feature plan
  metrics/
    collector.py      # Per-run metrics collection
```

## Project Status

This is v1. Current state:

- [x] Project scaffold, config, CLI
- [ ] Harness adapter implementations (ahs-3hn.2)
- [ ] Repo-to-plan scenario (ahs-3hn.3)
- [ ] Metrics capture and reporting (ahs-3hn.4)
- [ ] End-to-end testing (ahs-3hn.5)
