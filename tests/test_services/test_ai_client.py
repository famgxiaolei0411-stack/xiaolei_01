import pytest

from services.ai_client import AIClient, AIConfigurationError, AIResponseParseError
from config import is_configured_api_key


def test_is_configured_api_key_rejects_placeholder_values() -> None:
    assert not is_configured_api_key("")
    assert not is_configured_api_key("sk-your-api-key-here")
    assert not is_configured_api_key(" sk-your-openai-key-here ")
    assert is_configured_api_key("sk-real-key")


def test_ai_client_rejects_placeholder_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.ai_client.AI_PROVIDER", "deepseek")
    monkeypatch.setitem(
        __import__("services.ai_client", fromlist=["_PROVIDER_CONFIG"])._PROVIDER_CONFIG["deepseek"],
        "api_key",
        "sk-your-api-key-here",
    )

    with pytest.raises(AIConfigurationError, match="DEEPSEEK_API_KEY"):
        AIClient()


def test_chat_json_raises_parse_error_for_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object.__new__(AIClient)
    monkeypatch.setattr(client, "chat", lambda **_: "not-json-at-all")

    with pytest.raises(AIResponseParseError, match="无法解析"):
        client.chat_json(system_prompt="sys", user_prompt="user")
