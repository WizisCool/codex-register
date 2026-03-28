import src.core.register as register_module
from src.core.login import LoginEngine
from src.core.register import PhaseResult
from src.services import EmailServiceType


class DummySettings:
    openai_client_id = "client-id"
    openai_auth_url = "https://auth.example.test"
    openai_token_url = "https://token.example.test"
    openai_redirect_uri = "https://callback.example.test"
    openai_scope = "openid profile email"
    email_code_timeout = 120
    email_code_poll_interval = 3
    email_code_resend_max_retries = 2
    email_code_non_openai_sender_resend_max_retries = 1


class FakeEmailService:
    service_type = EmailServiceType.TEMPMAIL

    def get_verification_code(self, **kwargs):
        raise AssertionError("unexpected direct email_service.get_verification_code call")


def _success_phase() -> PhaseResult:
    return PhaseResult(
        phase=register_module.PHASE_OTP_SECONDARY,
        success=True,
    )


def _failed_phase(error_code: str, error_message: str) -> PhaseResult:
    return PhaseResult(
        phase=register_module.PHASE_OTP_SECONDARY,
        success=False,
        error_code=error_code,
        error_message=error_message,
        retryable=True,
        next_action="resend_otp",
    )


def _build_login_engine(monkeypatch) -> LoginEngine:
    monkeypatch.setattr(register_module, "get_settings", lambda: DummySettings())
    engine = LoginEngine(email_service=FakeEmailService())
    engine.session = type("FakeSession", (), {"cookies": type("FakeCookies", (), {"get": staticmethod(lambda _name: None)})()})()
    return engine


def _stub_login_success_path(monkeypatch, engine: LoginEngine):
    monkeypatch.setattr(engine, "_check_ip_location", lambda: (True, "US"))

    def fake_create_email():
        engine.email = "tester@example.com"
        engine.email_info = {"service_id": "svc-1"}
        return True

    def fake_start_oauth():
        engine.oauth_start = type("OAuthStart", (), {"auth_url": "https://auth.example.test/authorize"})()
        return True

    monkeypatch.setattr(engine, "_create_email", fake_create_email)
    monkeypatch.setattr(engine, "_init_session", lambda: True)
    monkeypatch.setattr(engine, "_start_oauth", fake_start_oauth)
    monkeypatch.setattr(engine, "_get_device_id", lambda: "did-1")
    monkeypatch.setattr(engine, "_check_sentinel", lambda _did: None)
    monkeypatch.setattr(
        engine,
        "_submit_signup_form",
        lambda _did, _sen_token: type("SignupResult", (), {"success": True, "error_message": ""})(),
    )
    monkeypatch.setattr(engine, "_register_password", lambda: (True, "pass-123"))
    monkeypatch.setattr(engine, "_validate_verification_code", lambda _code: True)
    monkeypatch.setattr(engine, "_create_user_account", lambda: True)
    monkeypatch.setattr(engine, "_follow_login_redirects", lambda _url: True)
    monkeypatch.setattr(engine, "_submit_login_form", lambda _did, _sen_token: True)
    monkeypatch.setattr(engine, "_get_workspace_id", lambda: "ws-1")
    monkeypatch.setattr(engine, "_select_workspace", lambda _workspace_id: "https://auth.example.test/continue")
    monkeypatch.setattr(engine, "_follow_redirects", lambda _url: "https://callback.example.test?code=abc&state=xyz")
    monkeypatch.setattr(
        engine,
        "_handle_oauth_callback",
        lambda _url: {
            "account_id": "acct-1",
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "id_token": "id-token",
        },
    )
    monkeypatch.setattr(engine, "close", lambda: None)


def test_login_engine_run_uses_retryable_waiter_for_both_otp_steps(monkeypatch):
    engine = _build_login_engine(monkeypatch)
    _stub_login_success_path(monkeypatch, engine)

    send_calls = []
    wait_callbacks = []

    def send_signup_code():
        send_calls.append("signup")
        return True

    def send_passwordless_code():
        send_calls.append("passwordless")
        return True

    monkeypatch.setattr(engine, "_send_verification_code", send_signup_code)
    monkeypatch.setattr(engine, "_send_verification_code_passwordless", send_passwordless_code)

    wait_results = iter([
        ("111111", _success_phase()),
        ("222222", _success_phase()),
    ])

    def fake_wait_for_code(resend_callback, **_kwargs):
        wait_callbacks.append(resend_callback.__name__)
        return next(wait_results)

    monkeypatch.setattr(engine, "_await_verification_code_with_resends", fake_wait_for_code)

    result = engine.run()

    assert result.success is True
    assert send_calls == ["signup", "passwordless"]
    assert wait_callbacks == ["send_signup_code", "send_passwordless_code"]
    assert result.workspace_id == "ws-1"
    assert result.account_id == "acct-1"


def test_login_engine_run_preserves_non_openai_sender_error(monkeypatch):
    engine = _build_login_engine(monkeypatch)
    _stub_login_success_path(monkeypatch, engine)

    monkeypatch.setattr(engine, "_send_verification_code", lambda: True)
    monkeypatch.setattr(
        engine,
        "_await_verification_code_with_resends",
        lambda _resend_callback, **_kwargs: (
            None,
            _failed_phase("OTP_NO_OPENAI_SENDER", "当前邮件批次未发现 OpenAI 发件人"),
        ),
    )
    monkeypatch.setattr(engine, "close", lambda: None)

    result = engine.run()

    assert result.success is False
    assert result.error_code == "OTP_NO_OPENAI_SENDER"
    assert result.error_message == "当前邮件批次未发现 OpenAI 发件人"


