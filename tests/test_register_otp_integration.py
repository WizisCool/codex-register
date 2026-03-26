import json
from types import SimpleNamespace

from src.core.register import RegistrationEngine


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []
        self.cookies = SimpleNamespace(get=lambda name: None)

    def get(self, url, **kwargs):
        self.get_calls.append({
            "url": url,
            "kwargs": kwargs,
        })
        return FakeResponse(status_code=200)

    def post(self, url, **kwargs):
        self.post_calls.append({
            "url": url,
            "kwargs": kwargs,
        })
        if url.endswith("/email-otp/validate"):
            code = json.loads(kwargs["data"])["code"]
            return FakeResponse(status_code=200 if code == "654321" else 401)
        return FakeResponse(status_code=200)


class FakeEmailService:
    def __init__(self):
        self.calls = []

    def get_verification_code(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return None
        return "654321"


def test_registration_engine_resend_flow_propagates_new_otp_timestamp_and_validates_code(monkeypatch):
    engine = RegistrationEngine.__new__(RegistrationEngine)
    engine.logs = []
    engine._log = lambda message, level="info": None
    engine.email = "tester@example.com"
    engine.email_info = {"service_id": "email-1"}
    engine.email_service = FakeEmailService()
    engine.session = FakeSession()
    engine._otp_sent_at = None

    issued_timestamps = iter([1000.0, 1005.0])
    monkeypatch.setattr("src.core.register.time.time", lambda: next(issued_timestamps))

    assert engine._send_verification_code() is True
    first_otp_sent_at = engine._otp_sent_at
    first_code = engine._get_verification_code()

    assert first_otp_sent_at == 1000.0
    assert first_code is None

    assert engine._send_verification_code() is True
    second_otp_sent_at = engine._otp_sent_at
    second_code = engine._get_verification_code()

    assert second_otp_sent_at == 1005.0
    assert second_code == "654321"
    assert engine._validate_verification_code(second_code) is True

    assert len(engine.email_service.calls) == 2
    assert engine.email_service.calls[0]["otp_sent_at"] == 1000.0
    assert engine.email_service.calls[1]["otp_sent_at"] == 1005.0
    assert engine.email_service.calls[0]["email_id"] == "email-1"
    assert engine.email_service.calls[1]["email_id"] == "email-1"

    validate_call = engine.session.post_calls[-1]
    assert validate_call["url"].endswith("/email-otp/validate")
    assert json.loads(validate_call["kwargs"]["data"]) == {"code": "654321"}
