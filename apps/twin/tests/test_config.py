from pathlib import Path

import pytest

from twin import config
from twin.config import ConfigError, Settings, load_env_file

FULL_ENV = {
    "OPENAI_API_KEY": "sk-test",
    "TWIN_MODEL": "gpt-test",
    "KNOWLEDGE_DIR": "C:/somewhere/knowledge",
    "PUSHOVER_USER": "u-abc123",
    "PUSHOVER_TOKEN": "token",
}


def test_all_variables_present() -> None:
    settings = Settings.from_env(FULL_ENV)
    assert settings.openai_api_key == "sk-test"
    assert settings.model == "gpt-test"
    assert settings.knowledge_dir == Path("C:/somewhere/knowledge")
    assert settings.pushover_user == "u-abc123"
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
    assert "u-abc123" not in text
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
    env = {"OPENAI_API_KEY": " sk-test ", "TWIN_MODEL": "  ", "PUSHOVER_USER": " ", "TWIN_HOST": " "}
    settings = Settings.from_env(env)
    assert settings.openai_api_key == "sk-test"
    assert settings.model == config.DEFAULT_MODEL
    assert settings.pushover_user is None
    assert settings.host == "127.0.0.1"


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


def test_api_settings_have_defaults() -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test"})
    assert settings.allowed_origins == config.DEFAULT_ALLOWED_ORIGINS
    assert settings.site_url == config.DEFAULT_SITE_URL
    assert settings.trust_proxy is False
    assert settings.log_salt is None
    assert (settings.per_client_hourly, settings.per_client_burst) == (20, 5)
    assert settings.max_user_messages == 8
    assert settings.daily_call_limit == 500
    assert settings.pushover_hourly == 10
    assert settings.model_timeout_seconds == 60.0
    assert settings.port == 8080
    assert settings.host == "127.0.0.1"


def test_api_settings_are_parsed() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-test",
            "TWIN_ALLOWED_ORIGINS": "https://adambuilds.ai/, https://www.adambuilds.ai ,",
            "TWIN_SITE_URL": "https://example.test/",
            "TWIN_TRUST_PROXY": "true",
            "TWIN_LOG_SALT": "pepper",
            "TWIN_PER_CLIENT_HOURLY": "3",
            "TWIN_PER_CLIENT_BURST": "1",
            "TWIN_MAX_USER_MESSAGES": "2",
            "TWIN_DAILY_CALL_LIMIT": "9",
            "TWIN_PUSHOVER_HOURLY": "4",
            "TWIN_MODEL_TIMEOUT_SECONDS": "12.5",
            "PORT": "9000",
            "TWIN_HOST": "0.0.0.0",
        }
    )
    assert settings.allowed_origins == ("https://adambuilds.ai", "https://www.adambuilds.ai")
    assert settings.site_url == "https://example.test"
    assert settings.trust_proxy is True
    assert settings.log_salt == "pepper"
    assert (settings.per_client_hourly, settings.per_client_burst) == (3, 1)
    assert settings.max_user_messages == 2
    assert settings.daily_call_limit == 9
    assert settings.pushover_hourly == 4
    assert settings.model_timeout_seconds == 12.5
    assert settings.port == 9000
    assert settings.host == "0.0.0.0"
    assert "pepper" not in repr(settings)


def test_origins_are_normalised() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-test",
            "TWIN_ALLOWED_ORIGINS": "HTTPS://Adambuilds.AI/, https://www.adambuilds.ai:8443",
        }
    )
    assert settings.allowed_origins == ("https://adambuilds.ai", "https://www.adambuilds.ai:8443")


def test_origins_drop_default_ports_but_keep_explicit_ones() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "sk-test",
            "TWIN_ALLOWED_ORIGINS": "https://adambuilds.ai:443, http://localhost:80, http://localhost:3000",
        }
    )
    assert settings.allowed_origins == ("https://adambuilds.ai", "http://localhost", "http://localhost:3000")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TWIN_PER_CLIENT_HOURLY", "many"),
        ("TWIN_DAILY_CALL_LIMIT", "-1"),
        ("PORT", "8.5"),
        ("PORT", "0"),
        ("PORT", "70000"),
        ("TWIN_TRUST_PROXY", "maybe"),
        ("TWIN_MODEL_TIMEOUT_SECONDS", "0"),
        ("TWIN_MODEL_TIMEOUT_SECONDS", "inf"),
        ("TWIN_MODEL_TIMEOUT_SECONDS", "nan"),
        ("TWIN_MODEL_TIMEOUT_SECONDS", "soon"),
        ("TWIN_ALLOWED_ORIGINS", " , , "),
        ("TWIN_ALLOWED_ORIGINS", "*"),
        ("TWIN_ALLOWED_ORIGINS", "https://adambuilds.ai/chat"),
        ("TWIN_SITE_URL", "adambuilds.ai"),
        ("TWIN_ALLOWED_ORIGINS", "https://u:p@adambuilds.ai"),
        ("TWIN_ALLOWED_ORIGINS", "https://adambuilds.ai?x=1"),
        ("TWIN_ALLOWED_ORIGINS", "ftp://adambuilds.ai"),
        ("TWIN_SITE_URL", "https://adambuilds.ai/site/"),
        ("TWIN_ALLOWED_ORIGINS", "https://adambuilds.ai:abc"),
        ("TWIN_ALLOWED_ORIGINS", "https://adambuilds.ai:"),
    ],
)
def test_bad_api_settings_name_the_variable(name: str, value: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({"OPENAI_API_KEY": "sk-test", name: value})
    assert name in str(excinfo.value)


def test_trust_proxy_requires_a_salt() -> None:
    with pytest.raises(ConfigError) as excinfo:
        Settings.from_env({"OPENAI_API_KEY": "sk-test", "TWIN_TRUST_PROXY": "1"})
    assert "TWIN_LOG_SALT" in str(excinfo.value)


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE"])
def test_trust_proxy_false_spellings_are_recognized(value: str) -> None:
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test", "TWIN_TRUST_PROXY": value})
    assert settings.trust_proxy is False


# Assumes no ancestor of tmp_path holds both apps/ and knowledge/.
def test_repo_root_walkup_falls_back_to_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "__file__", str(Path(tmp_path.anchor) / "config.py"))
    assert config._repo_root() == Path.cwd()


# Assumes no ancestor of tmp_path holds both apps/ and knowledge/.
def test_repo_root_ignores_site_packages_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_packages_twin = tmp_path / "app" / ".venv" / "lib" / "python3.13" / "site-packages" / "twin"
    site_packages_twin.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "__file__", str(site_packages_twin / "config.py"))
    assert config._repo_root() == Path.cwd()


def test_repo_root_finds_the_tree_above_a_venv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    site_packages_twin = (
        tmp_path / "app" / "apps" / "twin" / ".venv" / "lib" / "python3.13" / "site-packages" / "twin"
    )
    site_packages_twin.mkdir(parents=True)
    (tmp_path / "app" / "knowledge").mkdir(parents=True)
    monkeypatch.setattr(config, "__file__", str(site_packages_twin / "config.py"))
    assert config._repo_root() == (tmp_path / "app").resolve()


def test_repo_root_finds_the_source_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_tree = tmp_path / "repo" / "apps" / "twin" / "twin"
    source_tree.mkdir(parents=True)
    (tmp_path / "repo" / "knowledge").mkdir(parents=True)
    monkeypatch.setattr(config, "__file__", str(source_tree / "config.py"))
    assert config._repo_root() == (tmp_path / "repo").resolve()


def test_client_ip_header_defaults_blank_and_is_stripped() -> None:
    assert Settings.from_env({"OPENAI_API_KEY": "sk-test"}).client_ip_header == ""
    settings = Settings.from_env({"OPENAI_API_KEY": "sk-test", "TWIN_CLIENT_IP_HEADER": " Fly-Client-IP "})
    assert settings.client_ip_header == "Fly-Client-IP"
