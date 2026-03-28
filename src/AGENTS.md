# SOURCE CODE GUIDE

**Parent:** [../AGENTS.md](../AGENTS.md)

## OVERVIEW

Main source code directory with clean architecture: config → database → services → core → web.

## STRUCTURE

```
src/
├── config/          # Configuration management
│   ├── constants.py    # Enums, API endpoints, defaults
│   ├── settings.py     # Pydantic Settings + DB-backed config
│   └── __init__.py
├── core/            # Business logic
│   ├── openai/         # OAuth, token refresh, payment
│   ├── upload/         # CPA/Sub2API/TM/NewAPI upload
│   ├── register.py     # RegistrationEngine (main)
│   ├── codex_auth.py   # Codex CLI auth
│   ├── login.py        # Account login
│   ├── http_client.py  # curl_cffi wrapper
│   ├── dynamic_proxy.py # Proxy fetching
│   └── utils.py        # Shared utilities
├── database/        # Data layer
│   ├── models.py       # SQLAlchemy ORM
│   ├── crud.py         # All CRUD operations
│   ├── session.py      # DB engine + get_db()
│   └── init_db.py      # Migration/init
├── services/        # Email service providers **[SEE services/AGENTS.md]**
└── web/             # Web layer
    ├── app.py          # FastAPI factory
    ├── task_manager.py # Task + WebSocket mgr
    └── routes/         # API endpoints
        ├── accounts.py
        ├── email.py
        ├── payment.py
        ├── registration.py
        ├── settings.py
        ├── websocket.py
        └── upload/       # Service mgmt routes
```

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add email provider | `services/` + `services/__init__.py` |
| Change registration flow | `core/register.py` |
| Add upload target | `core/upload/` + `database/models.py` |
| Add API route | `web/routes/` + `web/app.py` |
| Modify DB schema | `database/models.py` + `database/crud.py` |
| Change config logic | `config/settings.py` |

## IMPORT HIERARCHY

```
config/          # No internal deps (bottom)
database/        # Depends on config/
services/        # Depends on config/, database/
core/            # Depends on all below
web/             # Depends on all (top)
```

## KEY PATTERNS

### Database Session
```python
from ..database.session import get_db

with get_db() as db:
    account = crud.get_account(db, id)
```

### Settings Access
```python
from ..config.settings import get_settings

settings = get_settings()
timeout = settings.registration_timeout
```

### HTTP Client
```python
from ..core.http_client import HTTPClient, RequestConfig

async with HTTPClient() as client:
    response = await client.get(url, proxy=proxy)
```

## ANTI-PATTERNS

- Don't import web/ from core/ (circular)
- Don't import routes directly, use `api_router` in `app.py`
- Never modify `task_manager` loop directly, use `set_loop()`
