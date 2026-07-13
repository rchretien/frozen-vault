"""Tests for frozen_vault_backend.api.utils."""

from pathlib import Path

import pytest

from frozen_vault_backend.api.utils import get_env_var
from frozen_vault_backend.exceptions import EnvironmentVariableNotFoundError


def test_get_env_var_prefers_exact_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct environment variables should take precedence."""
    monkeypatch.setenv("API_SECRET", "from-env")
    monkeypatch.delenv("API-SECRET", raising=False)

    assert get_env_var("API_SECRET") == "from-env"


def test_get_env_var_falls_back_to_underscored_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hyphenated environment names should look up underscored variants."""
    monkeypatch.delenv("API-SECRET", raising=False)
    monkeypatch.setenv("API_SECRET", "underscored")

    assert get_env_var("API-SECRET") == "underscored"


def test_get_env_var_reads_from_env_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper should consult both ~/.env-local and ./.env-local files."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    (home_dir / ".env-local").write_text("FILE_VAR=from-home\n", encoding="utf-8")

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env-local").write_text("FILE_VAR=from-project\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("FILE_VAR", raising=False)
    monkeypatch.chdir(project_dir)

    # ~/.env-local should be preferred over local .env-local
    assert get_env_var("FILE_VAR") == "from-home"


def test_get_env_var_returns_default_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide default fallback when no source contains the variable."""
    for candidate in ["MISSING_VAR", "MISSING_VAR".replace("-", "_")]:
        monkeypatch.delenv(candidate, raising=False)

    assert get_env_var("MISSING_VAR", default="fallback") == "fallback"


def test_get_env_var_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raising behaviour when value cannot be found."""
    for candidate in ["NO_VALUE", "NO_VALUE".replace("-", "_")]:
        monkeypatch.delenv(candidate, raising=False)

    with pytest.raises(EnvironmentVariableNotFoundError):
        get_env_var("NO_VALUE")
