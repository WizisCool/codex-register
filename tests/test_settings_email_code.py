import asyncio
from types import SimpleNamespace

from fastapi import HTTPException

from src.web.routes import settings as settings_routes


class DummySecret:
    def __init__(self, value: str = ""):
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def _build_settings(**overrides):
    data = {
        "proxy_enabled": False,
        "proxy_type": "http",
        "proxy_host": "127.0.0.1",
        "proxy_port": 7890,
        "proxy_username": "",
        "proxy_password": DummySecret(""),
        "proxy_dynamic_enabled": False,
        "proxy_dynamic_api_url": "",
        "proxy_dynamic_api_key_header": "Authorization",
        "proxy_dynamic_result_field": "data.proxy",
        "proxy_dynamic_api_key": DummySecret(""),
        "registration_max_retries": 3,
        "registration_timeout": 120,
        "registration_default_password_length": 12,
        "registration_sleep_min": 5,
        "registration_sleep_max": 30,
        "webui_host": "127.0.0.1",
        "webui_port": 15555,
        "debug": False,
        "webui_access_password": DummySecret(""),
        "tempmail_base_url": "https://mail.example.test",
        "tempmail_timeout": 30,
        "tempmail_max_retries": 3,
        "email_code_timeout": 120,
        "email_code_poll_interval": 3,
        "email_code_resend_max_retries": 2,
        "email_code_non_openai_sender_resend_max_retries": 1,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_get_all_settings_includes_non_openai_sender_resend_budget(monkeypatch):
    monkeypatch.setattr(
        settings_routes,
        "get_settings",
        lambda: _build_settings(email_code_non_openai_sender_resend_max_retries=4),
    )

    result = asyncio.run(settings_routes.get_all_settings())

    assert result["email_code"]["timeout"] == 120
    assert result["email_code"]["resend_max_retries"] == 2
    assert result["email_code"]["non_openai_sender_resend_max_retries"] == 4


def test_update_email_code_settings_persists_non_openai_sender_budget(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        settings_routes,
        "update_settings",
        lambda **kwargs: captured.update(kwargs),
    )

    response = asyncio.run(
        settings_routes.update_email_code_settings(
            settings_routes.EmailCodeSettings(
                timeout=180,
                poll_interval=5,
                resend_max_retries=3,
                non_openai_sender_resend_max_retries=2,
            )
        )
    )

    assert response["success"] is True
    assert captured == {
        "email_code_timeout": 180,
        "email_code_poll_interval": 5,
        "email_code_resend_max_retries": 3,
        "email_code_non_openai_sender_resend_max_retries": 2,
    }


def test_update_email_code_settings_rejects_invalid_non_openai_sender_budget():
    try:
        asyncio.run(
            settings_routes.update_email_code_settings(
                settings_routes.EmailCodeSettings(
                    timeout=120,
                    poll_interval=3,
                    resend_max_retries=2,
                    non_openai_sender_resend_max_retries=11,
                )
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "非 OpenAI 发件人重发次数必须在 0-10 之间"
        return

    raise AssertionError("expected HTTPException for invalid non_openai_sender_resend_max_retries")

