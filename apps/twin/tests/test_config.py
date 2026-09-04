from pathlib import Path

import pytest

from twin import config
from twin.config import ConfigError, Settings, load_env_file

FULL_ENV = {
    "OPENAI_API_KEY": "sk-test",
    "TWIN_MODEL": "gpt-test",
    "KNOWLEDGE_DIR": "C:/somewhere/knowledge",
    "PUSHOVER_USER": "user",
    "PUSHOVER_TOKEN": "token",
}


def test_all_variables_present() -> None:
    settings = Settings.from_env(FULL_ENV)
    assert settings.openai_api_key == "sk-test"
    assert settings.model == "gpt-test"
    assert settings.knowledge_dir == Path("C:/somewhere/knowledge")
    assert settings.pushover_user == "user"
    assert settings.pushover_token == "token"
    assert settings.pushover_enabled is True


def test_defaults_apply_when_optional_variables_absent() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test"})
    assert settings.model == config.DEFAULT_MODEL
    assert settings.knowledge_dir == config.DEFAULT_KNOWLEDGE_DIR
    assert settings.pushover_user is None
    assert settings.pushover_token is None
    assert settings.pushover_enabled is False


def test_missing_required_variable_names_it() -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({})
    assert "OPENAI_API_KEY" in str(excinfo.value)


def test_empty_string_counts_as_missing() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"OPENAI_API_KEY": ""})


def test_several_missing_variables_are_all_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "REQUIRED_VARS", ("ALPHA_KEY", "BETA_KEY"))
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({"OPENAI_API_KEY": "sk-test"})
    message = str(excinfo.value)
    assert "ALPHA_KEY" in message and "BETA_KEY" in message


def test_pushover_needs_both_values() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test", "PUSHOVER_USER": "user"})
    assert settings.pushover_enabled is False


def test_settings_are_immutable() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test"})
    with pytest.raises(AttributeError):
        settings.model = "other"  # type: ignore[misc]


def test_repo_root_points_at_repository() -> None:
    assert (config.REPO_ROOT / "docs" / "superpowers").is_dir()


def test_repr_hides_secrets() -> None:
    settings = Settings.from_env(FULL_ENV)
    text = repr(settings)
    assert "sk-test" not in text
    assert "token" not in text
    assert "gpt-test" in text


def test_from_env_reads_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-process")
    monkeypatch.delenv("TWIN_MODEL", raising=False)
    settings = Settings.from_env()
    assert settings.openai_api_key == "sk-from-process"
    assert settings.model == config.DEFAULT_MODEL


def test_whitespace_only_values_count_as_unset() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"OPENAI_API_KEY": "   "})
    settings = Settings.from_env({"OPENAI_API_KEY": " sk-test ", "TWIN_MODEL": "  ", "PUSHOVER_USER": " "})
    assert settings.openai_api_key == "sk-test"
    assert settings.model == config.DEFAULT_MODEL
    assert settings.pushover_user is None


def test_knowledge_dir_expands_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test", "KNOWLEDGE_DIR": "~/kb"})
    assert settings.knowledge_dir == tmp_path / "kb"


def test_load_env_file_tolerates_missing_file(tmp_path: Path) -> None:
    load_env_file(tmp_path / "does-not-exist.env")


def test_errors_share_a_base() -> None:
    from twin.errors import TwinError
    from twin.knowledge import KnowledgeError

    assert issubclass(ConfigError, TwinError)
    assert issubclass(KnowledgeError, TwinError)
