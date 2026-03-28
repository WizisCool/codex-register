# EMAIL SERVICES GUIDE

**Parent:** [../AGENTS.md](../AGENTS.md)

## OVERVIEW

Plugin architecture for email service providers. 8 implementations with automatic failover and circuit breaker pattern.

## STRUCTURE

```
services/
├── __init__.py              # Factory registration
├── base.py                  # Abstract base + factory + backoff
├── tempmail.py              # Tempmail.lol API
├── temp_mail.py             # CF Worker temp mail
├── moe_mail.py              # MoeMail REST API
├── duck_mail.py             # DuckMail API
├── freemail.py              # FreeMail service
├── imap_mail.py             # Generic IMAP
├── cloud_mail.py            # Cloud mail service
├── outlook_legacy_mail.py   # Old Outlook IMAP
└── outlook/                 # Modern Outlook (multi-provider)
    ├── __init__.py
    ├── service.py           # Main Outlook service
    ├── base.py              # Outlook base
    ├── account.py           # Account model
    ├── token_manager.py     # OAuth token mgmt
    ├── email_parser.py      # OTP extraction
    ├── health_checker.py    # Provider health
    └── providers/           # Provider implementations
        ├── __init__.py
        ├── base.py
        ├── imap_new.py      # New IMAP
        ├── imap_old.py      # Legacy IMAP
        └── graph_api.py     # MS Graph API
```

## ADDING NEW EMAIL SERVICE

1. **Create file**: `services/my_service.py`
2. **Extend base**:
```python
from .base import BaseEmailService, EmailServiceType

class MyServiceEmailService(BaseEmailService):
    def __init__(self, service_id: int, config: dict):
        super().__init__(service_id, config)
        self.service_type = EmailServiceType.MY_SERVICE
    
    async def create_email(self) -> str:
        # Implementation
        pass
    
    async def get_verification_code(
        self, 
        email: str, 
        timeout: int = 120
    ) -> Optional[str]:
        # Implementation
        pass
```
3. **Register in `__init__.py`**:
```python
from .my_service import MyServiceEmailService

EmailServiceFactory.register(
    EmailServiceType.MY_SERVICE, 
    MyServiceEmailService
)
```
4. **Add to constants.py**:
```python
class EmailServiceType(str, Enum):
    # ... existing
    MY_SERVICE = "my_service"
```

## KEY CLASSES

| Class | Purpose |
|-------|---------|
| `BaseEmailService` | Abstract base - extend this |
| `EmailServiceFactory` | Factory pattern for instantiation |
| `EmailProviderBackoffState` | Circuit breaker state |
| `EmailServiceType` | Enum of all service types |

## CONVENTIONS

- Service class name: `{Type}EmailService`
- File name: `snake_case.py`
- Must implement: `create_email()`, `get_verification_code()`
- Optional: `health_check()`, `cleanup()`

## ANTI-PATTERNS

- Don't call `create_email()` twice without cleanup
- Don't block in `get_verification_code()` — use async
- Never store credentials in logs
- Don't modify backoff state directly — use methods
