"""Tests for Feast apply script (Task 5.2)."""

from __future__ import annotations

import pytest
from feast import RepoConfig


class TestBuildConfig:
    """Tests for _build_config function."""

    def test_build_config_returns_repo_config(self) -> None:
        from data_engineering.feature_store.apply import _build_config

        config = _build_config()
        assert isinstance(config, RepoConfig)

    def test_default_config_project_name(self) -> None:
        from data_engineering.feature_store.apply import _build_config

        config = _build_config("development")
        assert config.project == "vycescore"

    def test_default_config_provider(self) -> None:
        from data_engineering.feature_store.apply import _build_config

        config = _build_config()
        assert config.provider == "local"

    def test_production_config_uses_s3_registry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from data_engineering.feature_store.apply import _build_config

        monkeypatch.setenv("FEAST_S3_REGISTRY_PATH", "s3://test-bucket/registry.db")
        config = _build_config("production")
        assert "s3://" in config.registry.path


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_default_env(self) -> None:
        from data_engineering.feature_store.apply import parse_args

        args = parse_args([])
        assert args.env == "development"

    def test_production_env(self) -> None:
        from data_engineering.feature_store.apply import parse_args

        args = parse_args(["--env", "production"])
        assert args.env == "production"

    def test_invalid_env_raises(self) -> None:
        from data_engineering.feature_store.apply import parse_args

        with pytest.raises(SystemExit):
            parse_args(["--env", "invalid"])
