# PROJECT KNOWLEDGE BASE

**Generated:** 2025-03-28  
**Commit:** b751d65  
**Branch:** master

## OVERVIEW

OpenAI/Codex CLI 自动注册系统 v2 - FastAPI Web UI for batch account registration, token management, and multi-service upload (CPA/Sub2API/Team Manager).

## STRUCTURE

```
./
├── webui.py              # CLI entry point
├── src/                  # Main source code
│   ├── config/          # Settings + constants
│   ├── core/            # Business logic (register, oauth, upload)
│   ├── database/        # SQLAlchemy models + CRUD
│   ├── services/        # Email service providers (plugin arch)
│   └── web/             # FastAPI app + routes + WebSocket
├── tests/               # pytest suite
├── templates/           # Jinja2 HTML
├── static/              # CSS/JS assets
├── docker-compose.yml   # Docker deployment
└── pyproject.toml       # Project config
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add email service | `src/services/` | Extend `BaseEmailService`, register in `__init__.py` |
| Add API endpoint | `src/web/routes/` | Add to existing or new module, import in `app.py` |
| Database schema | `src/database/models.py` | SQLAlchemy ORM definitions |
| DB operations | `src/database/crud.py` | All CRUD functions |
| Registration logic | `src/core/register.py` | `RegistrationEngine` class |
| Config/settings | `src/config/settings.py` | `get_settings()` singleton |
| Task/WebSocket | `src/web/task_manager.py` | Global task manager |
| Constants | `src/config/constants.py` | Enums, API endpoints, defaults |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `app` | FastAPI | `src/web/app.py:226` | Global app instance |
| `create_app()` | function | `src/web/app.py:56` | App factory |
| `RegistrationEngine` | class | `src/core/register.py` | Core registration |
| `BaseEmailService` | class | `src/services/base.py` | Email service base |
| `EmailServiceFactory` | class | `src/services/base.py` | Service factory |
| `get_settings()` | function | `src/config/settings.py` | Config singleton |
| `task_manager` | instance | `src/web/task_manager.py` | Task + WebSocket mgr |
| `Account` | model | `src/database/models.py:31` | Main account table |
| `get_db()` | contextmgr | `src/database/session.py` | DB session ctx |

## CONVENTIONS

### Naming
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/vars**: `snake_case`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Private**: `_prefixed`
- **Enum members**: `SCREAMING_SNAKE_CASE`

### Docstrings
```python
"""
模块描述
"""
```

### Section Dividers (in constants.py)
```python
# ============================================================================
# 枚举类型
# ============================================================================
```

## ANTI-PATTERNS (THIS PROJECT)

- **Never commit `.env`** — in .gitignore
- **Never store passwords in code** — use database settings
- **Never skip SSL verification** in production
- **No type suppression** — don't use `as any` or `@ts-ignore`

## UNIQUE STYLES

- **Chinese comments** for user-facing documentation
- **Dot-notation settings keys**: `app.name`, `webui.port`, `database.url`
- **Plugin architecture**: Email services via `EmailServiceFactory.register()`
- **Circuit breaker**: Email service backoff with `EmailProviderBackoffState`
- **Database-backed config**: All settings in DB, not env vars (except startup)

## COMMANDS

```bash
# Development
python webui.py --debug
python webui.py --port 8080 --access-password mypass

# Dependencies
uv sync                    # recommended
pip install -r requirements.txt

# Tests
pytest tests/ -v

# Docker
docker-compose up -d
docker-compose logs -f

# Packaging
build.bat                  # Windows
bash build.sh              # Linux/macOS
```

## NOTES

- **Default port**: 15555 (config in 4 places: webui.py, constants.py, docker-compose.yml, Dockerfile)
- **Entry point**: `webui.py` → `start_webui()` → uvicorn
- **PyInstaller support**: Frozen mode detection via `getattr(sys, 'frozen', False)`
- **Database**: SQLite default (`data/database.db`), PostgreSQL supported
- **Proxy priority**: Dynamic proxy > Proxy list (random/default) > Direct
- **Upload services**: Always direct, no proxy (CPA/Sub2API/TM)
- **WebSocket**: Real-time logs at `ws://host/api/ws/logs/{uuid}`
- **Concurrency**: ThreadPoolExecutor (50 workers), max 50 concurrent registrations
