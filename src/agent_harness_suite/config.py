"""Configuration loading for Agent Harness Suite.

Loads settings from environment variables (with .env support) and optional YAML config files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessConfig(BaseSettings):
    """Per-harness configuration block."""

    enabled: bool = True
    model: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ClaudeHarnessConfig(HarnessConfig):
    """Claude Agent SDK specific configuration."""

    model: str = "claude-sonnet-4-20250514"


class CopilotHarnessConfig(HarnessConfig):
    """GitHub Copilot SDK specific configuration."""

    model: str = "gpt-4o"


class Settings(BaseSettings):
    """Top-level application settings.

    Values are resolved in order: environment variables > .env file > config YAML > defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="AHS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys (loaded from env, no AHS_ prefix needed)
    anthropic_api_key: str = ""
    github_token: str = ""

    # General
    log_level: str = "INFO"
    results_dir: Path = Path("./results")

    # Harness configs
    claude: ClaudeHarnessConfig = Field(default_factory=ClaudeHarnessConfig)
    copilot: CopilotHarnessConfig = Field(default_factory=CopilotHarnessConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        """Load settings from a YAML config file, merged with env vars."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from environment and optional config file.

    Args:
        config_path: Optional path to a YAML config file. If None, loads from
                     env vars and .env only.
    """
    if config_path:
        return Settings.from_yaml(config_path)
    return Settings()
