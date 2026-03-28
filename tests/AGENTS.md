# TEST SUITE GUIDE

**Parent:** [../AGENTS.md](../AGENTS.md)

## OVERVIEW

pytest-based test suite with 27 Python unit tests and 3 CommonJS e2e tests. Tests cover email services, registration flow, upload modules, and task management.

## STRUCTURE

```
tests/
├── conftest.py                          # pytest fixtures
├── e2e/
│   └── runtime_functionality_check.py   # End-to-end tests
├── test_accounts_routes.py
├── test_codex_auth_routes.py
├── test_default_webui_port_config.py
├── test_duck_mail_service.py
├── test_email_service_backoff.py
├── test_email_service_cloudmail_routes.py
├── test_email_service_duckmail_routes.py
├── test_mail_code_reuse_guard.py
├── test_mail_latest_code_preference.py
├── test_newapi_service_routes.py
├── test_newapi_upload.py
├── test_register_otp_integration.py
├── test_register_protocol_baseline.py
├── test_registration_email_service_failover.py
├── test_registration_otp_phase.py
├── test_registration_proxy_failover.py
├── test_static_asset_versioning.py
├── test_task_manager_status_broadcast.py
├── test_task_recovery.py
├── test_tempmail_service.py
├── test_tempmail_timestamp_filter.py
└── [additional test files...]
```

## RUNNING TESTS

```bash
# All tests
pytest

# With verbose output
pytest -v

# Specific test file
pytest tests/test_registration_email_service_failover.py -v

# With coverage
pytest --cov=src --cov-report=html
```

## FIXTURES (conftest.py)

| Fixture | Purpose |
|---------|---------|
| `client` | FastAPI TestClient |
| `db_session` | Test database session |
| `test_settings` | Isolated settings |

## TEST CATEGORIES

| Category | Files |
|----------|-------|
| **Email services** | `test_*_mail_service.py`, `test_tempmail_*.py` |
| **Registration** | `test_registration_*.py`, `test_register_*.py` |
| **Routes/API** | `test_*_routes.py`, `test_accounts_*.py` |
| **Upload** | `test_newapi_upload.py` |
| **Task management** | `test_task_*.py` |
| **Utilities** | `test_static_asset_*.py`, `test_mail_*.py` |

## ANTI-PATTERNS

- Don't test against production services (use mocks)
- Don't skip test cleanup (database state)
- Never hardcode IDs — use fixtures
- Don't ignore async warnings — use `pytest-asyncio`
