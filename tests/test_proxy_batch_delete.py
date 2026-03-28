import asyncio
from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from src.database import crud
from src.database.session import DatabaseSessionManager
from src.web.routes import settings as settings_routes


def _build_fake_get_db(manager):
    @contextmanager
    def fake_get_db():
        with manager.session_scope() as session:
            yield session

    return fake_get_db


def _create_proxy_ids(manager, total: int) -> list[int]:
    created_ids = []
    with manager.session_scope() as session:
        for index in range(total):
            proxy = crud.create_proxy(
                session,
                name=f"proxy-{index}",
                type="http",
                host=f"127.0.0.{index + 1}",
                port=8000 + index,
            )
            created_ids.append(proxy.id)
    return created_ids


def test_batch_delete_proxies_removes_selected_ids(tmp_path, monkeypatch):
    manager = DatabaseSessionManager(f"sqlite:///{tmp_path}/proxy-batch-delete.db")
    manager.create_tables()
    manager.migrate_tables()
    monkeypatch.setattr(settings_routes, "get_db", _build_fake_get_db(manager))

    proxy_ids = _create_proxy_ids(manager, 3)

    result = asyncio.run(
        settings_routes.batch_delete_proxies(
            settings_routes.ProxyBatchDeleteRequest(ids=[proxy_ids[0], proxy_ids[2]])
        )
    )

    assert result["success"] is True
    assert result["requested_count"] == 2
    assert result["deleted_count"] == 2
    assert result["not_found_ids"] == []

    with manager.session_scope() as session:
        remaining_ids = [proxy.id for proxy in crud.get_proxies(session)]

    assert remaining_ids == [proxy_ids[1]]


def test_batch_delete_proxies_reports_missing_ids(tmp_path, monkeypatch):
    manager = DatabaseSessionManager(f"sqlite:///{tmp_path}/proxy-batch-delete-missing.db")
    manager.create_tables()
    manager.migrate_tables()
    monkeypatch.setattr(settings_routes, "get_db", _build_fake_get_db(manager))

    proxy_ids = _create_proxy_ids(manager, 1)

    result = asyncio.run(
        settings_routes.batch_delete_proxies(
            settings_routes.ProxyBatchDeleteRequest(ids=[proxy_ids[0], 99999, proxy_ids[0]])
        )
    )

    assert result["requested_count"] == 2
    assert result["deleted_count"] == 1
    assert result["not_found_ids"] == [99999]


def test_batch_delete_proxies_requires_non_empty_selection():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            settings_routes.batch_delete_proxies(
                settings_routes.ProxyBatchDeleteRequest(ids=[])
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "请至少选择一个代理"


def test_delete_disabled_proxy_items_only_removes_disabled_records(tmp_path, monkeypatch):
    manager = DatabaseSessionManager(f"sqlite:///{tmp_path}/proxy-delete-disabled.db")
    manager.create_tables()
    manager.migrate_tables()
    monkeypatch.setattr(settings_routes, "get_db", _build_fake_get_db(manager))

    with manager.session_scope() as session:
        enabled_proxy = crud.create_proxy(
            session,
            name="enabled-proxy",
            type="http",
            host="127.0.0.10",
            port=8010,
            enabled=True,
        )
        crud.create_proxy(
            session,
            name="disabled-proxy-1",
            type="http",
            host="127.0.0.11",
            port=8011,
            enabled=False,
        )
        crud.create_proxy(
            session,
            name="disabled-proxy-2",
            type="http",
            host="127.0.0.12",
            port=8012,
            enabled=False,
        )
        enabled_proxy_id = enabled_proxy.id

    result = asyncio.run(settings_routes.delete_disabled_proxy_items())

    assert result["success"] is True
    assert result["deleted_count"] == 2

    with manager.session_scope() as session:
        remaining = [(proxy.id, proxy.enabled) for proxy in crud.get_proxies(session)]

    assert remaining == [(enabled_proxy_id, True)]


def test_delete_disabled_proxy_items_is_noop_when_none_exist(tmp_path, monkeypatch):
    manager = DatabaseSessionManager(f"sqlite:///{tmp_path}/proxy-delete-disabled-empty.db")
    manager.create_tables()
    manager.migrate_tables()
    monkeypatch.setattr(settings_routes, "get_db", _build_fake_get_db(manager))

    _create_proxy_ids(manager, 2)

    result = asyncio.run(settings_routes.delete_disabled_proxy_items())

    assert result["success"] is True
    assert result["deleted_count"] == 0
    assert result["message"] == "已删除 0 个禁用代理"




