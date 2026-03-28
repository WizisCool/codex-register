# TempMail Developer API (v2) 规范文档

## 1. 概览 (Overview)
TempMail 提供基于 HTTP 的临时邮件服务 API，支持自动化生成邮箱、接收邮件及自定义域名管理。

### 1.1 核心特性
* **认证机制**: 免费层级无需 API Key；Plus/Ultra 用户需使用 Bearer Token。
* **自定义能力**: 支持自定义域名 (Custom Domains) 与前缀 (Prefix)。
* **数据交互**: 所有 `POST` 请求必须包含 `Content-Type: application/json` 请求头。
* **基础 URL**: `https://api.tempmail.lol/v2/`

### 1.2 认证 (Authorization)
Plus 或 Ultra 用户须在 HTTP Header 中携带认证信息：
| Header | Value 示例 |
| :--- | :--- |
| `Authorization` | `Bearer tempmail.20250109.abcdefghijklmnopqrstuvwxyz` |

---

## 2. 数据模型 (Data Models)

### 2.1 邮件对象 (Email Object)
当检查收件箱时返回的邮件元数据。
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `from` | string | 发件人地址 |
| `to` | string | 收件人地址 (临时邮箱) |
| `subject` | string | 邮件主题 |
| `body` | string | 纯文本正文 (可能为空) |
| `html` | ?string | HTML 格式正文 (可能为 null) |
| `date` | number | 接收邮件的 Unix 时间戳 |

### 2.2 收件箱对象 (Inbox Object)
| 字段名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `address` | string | 生成的邮箱全称 |
| `token` | string | 用于访问该收件箱的唯一凭证 (Access Token) |

---

## 3. 生命周期管理 (Inbox Lifespan)
邮箱有效期取决于用户的订阅层级：
| 订阅层级 | 有效期 (Lifespan) |
| :--- | :--- |
| Free (无订阅) | 1 小时 |
| TempMail Plus | 10 小时 |
| TempMail Ultra | 30 小时 |

> **注**: 自定义域名邮箱可通过重复调用创建方法无限延长有效期。

---

## 4. 核心 API 端点 (Core Endpoints)

### 4.1 创建收件箱 (Create Inbox)
支持 `GET` (仅限兼容旧版) 和 `POST`。建议使用 `POST` 以获取完整功能。
* **Endpoint**: `POST /v2/inbox/create`
* **请求体 (Body)**:
    * `domain` (?string): 指定域名，缺省为随机。
    * `prefix` (?string): 指定邮箱前缀，缺省为随机。
* **响应 (201)**: 返回 `Inbox Object`。

### 4.2 获取邮件 (Fetch Emails)
* **Endpoint**: `GET /v2/inbox`
* **查询参数 (Query)**:
    * `token` (string): 必选，创建邮箱时获取的 Token。
* **响应 (200)**:
    * `emails` (Email[]): 邮件对象数组。
    * `expired` (boolean): 若邮箱已过期则为 `true`。

---

## 5. 自定义域名管理 (Custom Domain)
该功能仅限 **Plus** 及 **Ultra** 用户。

### 5.1 域名预备 (Prepare Custom Domain)
* **Endpoint**: `POST /v2/custom`
* **请求体 (Body)**: `domain` (string)。
* **响应 (200)**: 返回 `uuid` (string)。
* **DNS 配置**: 在域名服务商处添加记录：`[uuid].yourdomain.com`，值为 `tm-custom-domain-verification`。

### 5.2 创建自定义域名邮箱
* **Endpoint**: `POST /v2/inbox/create`
* **请求体 (Body)**:
    * `domain` (string): 已验证的自定义域名。
    * `prefix` (?string): 邮箱前缀。
* **注**: 若 Token 丢失，使用相同前缀再次请求即可找回并延长有效期。

---

## 6. Webhooks
仅限 **Ultra** 用户。

### 6.1 私有 Webhook (Private Webhooks)
针对特定域名的所有邮件转发。
* **Endpoint**: `POST /v2/private_webhook`
* **请求体**: `domain` (string), `url` (string)。
* **移除**: `DELETE /private_webhook?domain=[domain]`。

### 6.2 标准 Webhook (Standard Webhooks)
针对所有标准生成的邮件转发。
* **Endpoint**: `POST /v2/webhook`
* **请求体**: `url` (string)。
* **移除**: `DELETE /webhook`。