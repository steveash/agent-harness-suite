"""Tests for configuration loading."""

from pathlib import Path

from agent_harness_suite.config import Settings, load_settings


def test_default_settings():
    """Settings load with sensible defaults when no env/config is provided."""
    settings = Settings(
        anthropic_api_key="test-key",
        github_token="test-token",
    )
    assert settings.log_level == "INFO"
    assert settings.results_dir == Path("./results")
    assert settings.claude.enabled is True
    assert settings.copilot.enabled is True
    assert settings.claude.model == "claude-sonnet-4-20250514"


def test_load_settings_no_config():
    """load_settings() works without a config file path."""
    settings = load_settings()
    assert isinstance(settings, Settings)


def test_harness_registry():
    """Built-in harnesses are discoverable."""
    import pytest

    from agent_harness_suite.harnesses import get_harness

    settings = Settings(anthropic_api_key="k", github_token="t")
    harness = get_harness("claude", settings)
    assert harness.name == "claude"

    with pytest.raises(ValueError, match="Unknown harness"):
        get_harness("nonexistent", settings)


def test_scenario_registry():
    """Built-in scenarios are discoverable."""
    import pytest

    from agent_harness_suite.scenarios import get_scenario

    scenario = get_scenario("repo-to-plan")
    assert scenario.name == "repo-to-plan"

    with pytest.raises(ValueError, match="Unknown scenario"):
        get_scenario("nonexistent")
