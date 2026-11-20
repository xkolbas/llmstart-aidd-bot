from pathlib import Path

import pytest

from bot.settings import Settings


@pytest.fixture
def configured_root(tmp_path, monkeypatch):
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_IMAGE_MODEL",
        "HISTORY_DIR",
        "HISTORY_MAX_EXCHANGES",
    ):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=123456:test-token\n"
        "OPENROUTER_API_KEY=test-key\n"
        "OPENROUTER_MODEL=test-model\n"
        "OPENROUTER_IMAGE_MODEL=image-model\n",
        encoding="utf-8",
    )
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts/system.txt").write_text("Тестовая роль\n", encoding="utf-8")
    (tmp_path / "prompts/image.txt").write_text("Анализ фото\n", encoding="utf-8")
    return tmp_path


def test_loads_dotenv_and_prompt_with_default_limit(configured_root):
    settings = Settings.load(configured_root)
    assert settings.telegram_bot_token == "123456:test-token"
    assert settings.openrouter_api_key == "test-key"
    assert settings.openrouter_model == "test-model"
    assert settings.openrouter_image_model == "image-model"
    assert settings.image_prompt == "Анализ фото"
    assert settings.history_max_exchanges == 10
    assert settings.system_prompt == "Тестовая роль"
    assert settings.history_dir == configured_root / "data/history"


def test_history_directory_can_be_absolute(configured_root, monkeypatch, tmp_path):
    target = tmp_path / "sessions"
    monkeypatch.setenv("HISTORY_DIR", str(target))
    assert Settings.load(configured_root).history_dir == target


def test_environment_overrides_dotenv(configured_root, monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "environment-model")
    monkeypatch.setenv("OPENROUTER_IMAGE_MODEL", "environment-image-model")
    monkeypatch.setenv("HISTORY_MAX_EXCHANGES", "5")
    settings = Settings.load(configured_root)
    assert settings.openrouter_model == "environment-model"
    assert settings.openrouter_image_model == "environment-image-model"
    assert settings.history_max_exchanges == 5


@pytest.mark.parametrize(
    "name",
    ["TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_IMAGE_MODEL"],
)
def test_rejects_missing_required_setting(configured_root, monkeypatch, name):
    monkeypatch.setenv(name, " ")
    with pytest.raises(ValueError, match=name):
        Settings.load(configured_root)


@pytest.mark.parametrize("limit", ["0", "-1", "abc", "1.5", ""])
def test_rejects_invalid_limit(configured_root, monkeypatch, limit):
    monkeypatch.setenv("HISTORY_MAX_EXCHANGES", limit)
    with pytest.raises(ValueError, match="HISTORY_MAX_EXCHANGES"):
        Settings.load(configured_root)


@pytest.mark.parametrize("content", ["", " \n "])
def test_rejects_empty_prompt(configured_root, content):
    (configured_root / "prompts/system.txt").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="не должен быть пустым"):
        Settings.load(configured_root)


def test_rejects_missing_prompt(configured_root):
    (configured_root / "prompts/system.txt").unlink()
    with pytest.raises(ValueError, match="Не удалось прочитать"):
        Settings.load(configured_root)


def test_missing_configuration_reports_names_without_secrets(configured_root: Path):
    (configured_root / ".env").write_text("", encoding="utf-8")
    with pytest.raises(ValueError) as error:
        Settings.load(configured_root)
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_IMAGE_MODEL",
    ):
        assert name in str(error.value)


@pytest.mark.parametrize("content", ["", " \n "])
def test_rejects_empty_image_prompt(configured_root, content):
    (configured_root / "prompts/image.txt").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="prompts/image.txt.*не должен быть пустым"):
        Settings.load(configured_root)


def test_rejects_missing_image_prompt(configured_root):
    (configured_root / "prompts/image.txt").unlink()
    with pytest.raises(ValueError, match="Не удалось прочитать.*prompts/image.txt"):
        Settings.load(configured_root)


@pytest.mark.parametrize("error", [PermissionError("private-path"), UnicodeError("private-data")])
def test_rejects_unreadable_image_prompt_without_leaking_details(
    configured_root, monkeypatch, error
):
    read_text = Path.read_text

    def failing_read(path, *args, **kwargs):
        if path == configured_root / "prompts/image.txt":
            raise error
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)
    with pytest.raises(ValueError, match="Не удалось прочитать.*prompts/image.txt") as result:
        Settings.load(configured_root)
    assert "private-" not in str(result.value)
