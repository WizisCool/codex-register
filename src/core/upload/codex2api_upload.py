"""
Codex2API 账号上传功能
将账号批量导入到 Codex2API 平台
"""

import logging
from typing import List, Tuple

from curl_cffi import requests as cffi_requests

from ...database.models import Account
from ...database.session import get_db

logger = logging.getLogger(__name__)


def upload_to_codex2api(
    account: Account,
    api_url: str,
    api_key: str,
    include_proxy_url: bool = True,
) -> Tuple[bool, str]:
    """
    上传单账号到 Codex2API（直连，不走代理）

    Args:
        account: 账号模型实例
        api_url: Codex2API URL，如 http://host
        api_key: Admin API Key（x-admin-key header）
        include_proxy_url: 是否上传 proxy_url 到 Codex2API

    Returns:
        (成功标志, 消息)
    """
    if not api_url:
        return False, "Codex2API URL 未配置"
    if not api_key:
        return False, "Codex2API API Key 未配置"
    if not account.refresh_token:
        return False, "账号缺少 refresh_token"

    url = api_url.rstrip("/") + "/api/admin/accounts"
    headers = {
        "x-admin-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "refresh_token": account.refresh_token or "",
    }
    if include_proxy_url:
        payload["proxy_url"] = account.proxy_used or ""

    try:
        resp = cffi_requests.post(
            url,
            headers=headers,
            json=payload,
            proxies=None,
            timeout=30,
            impersonate="chrome110",
        )
        if resp.status_code in (200, 201):
            return True, "上传成功"
        error_msg = f"上传失败: HTTP {resp.status_code}"
        try:
            detail = resp.json()
            if isinstance(detail, dict):
                error_msg = detail.get("message", error_msg)
        except Exception:
            error_msg = f"{error_msg} - {resp.text[:200]}"
        return False, error_msg
    except Exception as e:
        logger.error(f"Codex2API 上传异常: {e}")
        return False, f"上传异常: {str(e)}"


def batch_upload_to_codex2api(
    account_ids: List[int],
    api_url: str,
    api_key: str,
    include_proxy_url: bool = True,
) -> dict:
    """
    批量上传账号到 Codex2API

    Args:
        account_ids: 账号 ID 列表
        api_url: Codex2API URL
        api_key: Admin API Key
        include_proxy_url: 是否上传 proxy_url 到 Codex2API

    Returns:
        包含成功/失败统计和详情的字典
    """
    results = {
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "details": [],
    }

    with get_db() as db:
        for account_id in account_ids:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                results["failed_count"] += 1
                results["details"].append(
                    {
                        "id": account_id,
                        "email": None,
                        "success": False,
                        "error": "账号不存在",
                    }
                )
                continue
            if not account.refresh_token:
                results["skipped_count"] += 1
                results["details"].append(
                    {
                        "id": account_id,
                        "email": account.email,
                        "success": False,
                        "error": "缺少 refresh_token",
                    }
                )
                continue

            success, message = upload_to_codex2api(
                account, api_url, api_key, include_proxy_url
            )
            if success:
                results["success_count"] += 1
                results["details"].append(
                    {
                        "id": account_id,
                        "email": account.email,
                        "success": True,
                        "message": message,
                    }
                )
            else:
                results["failed_count"] += 1
                results["details"].append(
                    {
                        "id": account_id,
                        "email": account.email,
                        "success": False,
                        "error": message,
                    }
                )

    return results


def test_codex2api_connection(api_url: str, api_key: str) -> Tuple[bool, str]:
    """
    测试 Codex2API 连接（使用 GET 请求探测 /admin/accounts 端点）

    Returns:
        (成功标志, 消息)
    """
    if not api_url:
        return False, "API URL 不能为空"
    if not api_key:
        return False, "API Key 不能为空"

    url = api_url.rstrip("/") + "/api/admin/accounts"
    headers = {"x-admin-key": api_key}

    try:
        resp = cffi_requests.get(
            url,
            headers=headers,
            proxies=None,
            timeout=10,
            impersonate="chrome110",
        )
        if resp.status_code in (200, 201, 204):
            return True, "Codex2API 连接测试成功"
        if resp.status_code == 401:
            return False, "连接成功，但 API Key 无效"
        if resp.status_code == 403:
            return False, "连接成功，但权限不足"
        if resp.status_code == 404:
            return False, "未找到 /api/admin/accounts 接口，请检查 API URL"

        return False, f"服务器返回异常状态码: {resp.status_code}"
    except cffi_requests.exceptions.ConnectionError as e:
        return False, f"无法连接到服务器: {str(e)}"
    except cffi_requests.exceptions.Timeout:
        return False, "连接超时，请检查网络配置"
    except Exception as e:
        return False, f"连接测试失败: {str(e)}"
