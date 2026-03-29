# Agent Harness Suite

Python 3.11+ project using pytest, ruff, and mypy.

## Setup

```bash
pip install -e ".[dev,claude]"
```

## Definition of Done

```bash
# Tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
```
