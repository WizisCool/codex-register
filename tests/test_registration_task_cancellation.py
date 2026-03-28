import asyncio
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from src.core.register import ERROR_TASK_CANCELLED, RegistrationResult
from src.database.models import Base, RegistrationTask
from src.database.session import DatabaseSessionManager
from src.services import EmailServiceType
from src.services.base import BaseEmailService, EmailServiceCancelledError
from src.web.routes import registration as registration_routes


class FakeTaskManager:
    def __init__(self):
        self.cancelled = set()
        self.status_updates = []
        self.logs = {}
        self.batch_status = {}

    def is_cancelled(self, task_uuid):
        return task_uuid in self.cancelled

    def cancel_task(self, task_uuid):
        self.cancelled.add(task_uuid)

    def update_status(self, task_uuid, status, **kwargs):
        self.status_updates.append((task_uuid, status, kwargs))

    def create_log_callback(self, task_uuid, prefix="", batch_id=""):
        def callback(message):
            full_message = f"{prefix} {message}" if prefix else message
            self.logs.setdefault(task_uuid, []).append(full_message)
        return callback

    def create_check_cancelled_callback(self, task_uuid):
        return lambda: self.is_cancelled(task_uuid)

    def get_batch_status(self, batch_id):
        snapshot = self.batch_status.get(batch_id)
        return dict(snapshot) if snapshot else None

    def cancel_batch(self, batch_id):
        snapshot = self.batch_status.setdefault(batch_id, {})
        snapshot["cancelled"] = True
        snapshot["status"] = "cancelling"

    def update_batch_status(self, batch_id, **kwargs):
        snapshot = self.batch_status.setdefault(batch_id, {})
        snapshot.update(kwargs)


class DummySettings:
    proxy_dynamic_enabled = False
    proxy_dynamic_api_url = ""
    email_code_timeout = 10
    email_code_poll_interval = 1
    email_code_resend_max_retries = 0
    email_code_non_openai_sender_resend_max_retries = 0
    openai_client_id = "client-id"
    openai_auth_url = "https://auth.example.test"
    openai_token_url = "https://token.example.test"
    openai_redirect_uri = "https://callback.example.test"
    openai_scope = "openid profile email"

    def get_proxy_url(self):
        return None


def _build_fake_get_db(manager):
    @contextmanager
    def fake_get_db():
        with manager.session_scope() as session:
            yield session

    return fake_get_db


class FakeRegistrationEngine:
    started_event = None

    def __init__(self, email_service, proxy_url=None, callback_logger=None, status_callback=None, task_uuid=None):
        self.email_service = email_service
        self.phase_history = []
        self.check_cancelled = None
        self.callback_logger = callback_logger or (lambda _msg: None)
        self.task_uuid = task_uuid

    def run(self):
        if self.started_event is not None:
            self.started_event.set()
        while True:
            if callable(self.check_cancelled) and self.check_cancelled():
                return RegistrationResult(
                    success=False,
                    error_message="任务已取消",
                    error_code=ERROR_TASK_CANCELLED,
                    logs=[],
                )
            time.sleep(0.01)

    def save_to_database(self, result):
        return False

    def close(self):
        return None


class FakePollingEmailService(BaseEmailService):
    def __init__(self, started_event=None):
        super().__init__(EmailServiceType.TEMPMAIL, "fake-polling-email")
        self.started_event = started_event

    def create_email(self, config=None):
        return {"email": "poll@example.test", "service_id": "poll-service"}

    def get_verification_code(self, email: str, email_id: str = None, timeout: int = 120, pattern: str = r"(?<!\d)(\d{6})(?!\d)", otp_sent_at=None):
        if self.started_event is not None:
            self.started_event.set()
        while True:
            self._raise_if_cancelled("任务已取消")
            self._sleep_with_cancel(0.05)

    def list_emails(self, **kwargs):
        return []

    def delete_email(self, email_id: str):
        return True

    def check_health(self):
        return True


class FakeEmailPollingRegistrationEngine:
    def __init__(self, email_service, proxy_url=None, callback_logger=None, status_callback=None, task_uuid=None):
        self.email_service = email_service
        self.phase_history = []
        self.check_cancelled = None
        self.callback_logger = callback_logger or (lambda _msg: None)
        self.task_uuid = task_uuid

    def run(self):
        try:
            self.email_service.get_verification_code("poll@example.test", timeout=60)
        except EmailServiceCancelledError as exc:
            return RegistrationResult(
                success=False,
                error_message=str(exc),
                error_code=ERROR_TASK_CANCELLED,
                logs=[],
            )

        return RegistrationResult(success=False, error_message="邮箱轮询未被取消", logs=[])

    def save_to_database(self, result):
        return False

    def close(self):
        return None


def test_cancel_task_route_marks_task_manager_and_db_cancelled(monkeypatch):
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / "registration_cancel_route.db"
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)

    task_uuid = "task-cancel-route"
    with manager.session_scope() as session:
        session.add(RegistrationTask(task_uuid=task_uuid, status="running"))

    fake_task_manager = FakeTaskManager()
    monkeypatch.setattr(registration_routes, "get_db", _build_fake_get_db(manager))
    monkeypatch.setattr(registration_routes, "task_manager", fake_task_manager)

    response = asyncio.run(registration_routes.cancel_task(task_uuid))

    assert response == {"success": True, "message": "任务已取消"}
    assert task_uuid in fake_task_manager.cancelled

    with manager.session_scope() as session:
        task = session.query(RegistrationTask).filter(RegistrationTask.task_uuid == task_uuid).first()
        assert task.status == "cancelled"
        assert task.error_message == "任务已取消"


def test_run_sync_registration_task_stops_after_cancel_request(monkeypatch):
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / "registration_cancel_runtime.db"
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)

    task_uuid = "task-cancel-runtime"
    with manager.session_scope() as session:
        session.add(RegistrationTask(task_uuid=task_uuid, status="pending"))

    fake_task_manager = FakeTaskManager()
    start_event = threading.Event()
    FakeRegistrationEngine.started_event = start_event

    monkeypatch.setattr(registration_routes, "get_db", _build_fake_get_db(manager))
    monkeypatch.setattr(registration_routes, "task_manager", fake_task_manager)
    monkeypatch.setattr(registration_routes, "get_settings", lambda: DummySettings())
    monkeypatch.setattr(registration_routes, "RegistrationEngine", FakeRegistrationEngine)
    monkeypatch.setattr(
        registration_routes,
        "_build_email_service_candidates",
        lambda db, service_type, actual_proxy_url, email_service_id, email_service_config: [
            {
                "service_type": EmailServiceType.TEMPMAIL,
                "config": {"proxy_url": actual_proxy_url},
                "db_service": None,
            }
        ],
    )
    monkeypatch.setattr(
        registration_routes.EmailServiceFactory,
        "create",
        lambda service_type, config, name=None: SimpleNamespace(
            service_type=service_type,
            name=name or service_type.value,
            config=config,
        ),
    )

    worker = threading.Thread(
        target=registration_routes._run_sync_registration_task,
        kwargs={
            "task_uuid": task_uuid,
            "email_service_type": EmailServiceType.TEMPMAIL.value,
            "proxy": None,
            "email_service_config": {},
        },
    )
    worker.start()
    assert start_event.wait(timeout=1.0), "registration engine did not start in time"

    response = asyncio.run(registration_routes.cancel_task(task_uuid))
    assert response == {"success": True, "message": "任务已取消"}

    worker.join(timeout=2.0)
    assert not worker.is_alive(), "registration worker should stop after cancellation"

    with manager.session_scope() as session:
        task = session.query(RegistrationTask).filter(RegistrationTask.task_uuid == task_uuid).first()
        assert task.status == "cancelled"
        assert task.error_message == "任务已取消"

    statuses = [status for current_uuid, status, _kwargs in fake_task_manager.status_updates if current_uuid == task_uuid]
    assert "cancelled" in statuses


def test_cancel_batch_propagates_to_member_tasks(monkeypatch):
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / "registration_cancel_batch.db"
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)

    task_uuids = ["batch-cancel-1", "batch-cancel-2"]
    with manager.session_scope() as session:
        session.add_all([
            RegistrationTask(task_uuid=task_uuids[0], status="running"),
            RegistrationTask(task_uuid=task_uuids[1], status="pending"),
        ])

    fake_task_manager = FakeTaskManager()
    fake_task_manager.batch_status["batch-1"] = {
        "finished": False,
        "cancelled": False,
        "task_uuids": task_uuids,
    }

    monkeypatch.setattr(registration_routes, "get_db", _build_fake_get_db(manager))
    monkeypatch.setattr(registration_routes, "task_manager", fake_task_manager)

    response = asyncio.run(registration_routes.cancel_batch("batch-1"))

    assert response["success"] is True
    assert fake_task_manager.batch_status["batch-1"]["cancelled"] is True
    assert fake_task_manager.cancelled == set(task_uuids)

    with manager.session_scope() as session:
        tasks = session.query(RegistrationTask).order_by(RegistrationTask.task_uuid.asc()).all()
        assert [task.status for task in tasks] == ["cancelled", "cancelled"]


def test_run_sync_registration_task_stops_while_email_service_polling(monkeypatch):
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / "registration_cancel_email_polling.db"
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)

    task_uuid = "task-cancel-email-polling"
    with manager.session_scope() as session:
        session.add(RegistrationTask(task_uuid=task_uuid, status="pending"))

    fake_task_manager = FakeTaskManager()
    start_event = threading.Event()

    monkeypatch.setattr(registration_routes, "get_db", _build_fake_get_db(manager))
    monkeypatch.setattr(registration_routes, "task_manager", fake_task_manager)
    monkeypatch.setattr(registration_routes, "get_settings", lambda: DummySettings())
    monkeypatch.setattr(registration_routes, "RegistrationEngine", FakeEmailPollingRegistrationEngine)
    monkeypatch.setattr(
        registration_routes,
        "_build_email_service_candidates",
        lambda db, service_type, actual_proxy_url, email_service_id, email_service_config: [
            {
                "service_type": EmailServiceType.TEMPMAIL,
                "config": {"proxy_url": actual_proxy_url},
                "db_service": None,
            }
        ],
    )
    monkeypatch.setattr(
        registration_routes.EmailServiceFactory,
        "create",
        lambda service_type, config, name=None: FakePollingEmailService(start_event),
    )

    worker = threading.Thread(
        target=registration_routes._run_sync_registration_task,
        kwargs={
            "task_uuid": task_uuid,
            "email_service_type": EmailServiceType.TEMPMAIL.value,
            "proxy": None,
            "email_service_config": {},
        },
    )
    worker.start()
    assert start_event.wait(timeout=1.0), "email polling did not start in time"

    response = asyncio.run(registration_routes.cancel_task(task_uuid))
    assert response == {"success": True, "message": "任务已取消"}

    worker.join(timeout=2.0)
    assert not worker.is_alive(), "registration worker should stop while email service is polling"

    with manager.session_scope() as session:
        task = session.query(RegistrationTask).filter(RegistrationTask.task_uuid == task_uuid).first()
        assert task.status == "cancelled"
        assert task.error_message == "任务已取消"



