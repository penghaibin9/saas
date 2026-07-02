# 部署模式：私有化 与 SaaS（同一套代码两用）

本平台支持两种交付模式，由环境变量 `TENANCY_MODE` 切换，**业务代码完全一致**。

| | 私有化部署 (single) | SaaS (multi) |
|---|---|---|
| 适用 | 单所职院独立采购、内网/等保 | 一套平台服务多所学校 |
| 隔离 | 单库 | **每校一个独立数据库**（DB-per-tenant，物理隔离） |
| 切换 | `TENANCY_MODE=single`（默认） | `TENANCY_MODE=multi` |
| 租户识别 | 无需 | 子域名 `<code>.域名` 或请求头 `X-Tenant: <code>` |

## 原理（为什么改造成本极低）

- 全项目 87 处以 `require('../config/db')` 使用同一连接池。改造后该模块导出一个**租户感知代理**：每次访问按"当前请求所属租户"解析到对应库（`config/tenancy.js` + `AsyncLocalStorage`）。
- **40 个数据模型一行未改**；事务（`getConnection`）也自动落在同一租户库。
- `single` 模式恒为默认库 → 行为与改造前完全一致（已回归验证：E2E 25/25、smoke 39/0、前端 120+ 页 0 缺陷）。

## 私有化部署（默认）

```bash
# .env
TENANCY_MODE=single
DB_NAME=internship_management
npm run migrate:all && npm run seed   # 建库 + 管理员
npm start
```

## SaaS：开通一所学校

```bash
# .env
TENANCY_MODE=multi
MASTER_DB_NAME=internship_management   # 租户注册表所在库（建议单独 master 库）

# 开通：建独立库 + 建表 + 种管理员 + 登记映射
npm run provision <code> "<学校名称>" [adminUser] [adminPass]
# 例：
npm run provision hnyz "湖南某职业学院" admin Admin@123
```

开通后该校访问方式：
- 子域名：`hnyz.your-domain.com`（Nginx 泛解析 + 转发到同一后端）
- 或前端登录时带请求头 `X-Tenant: hnyz`

## 安全

- 登录令牌内嵌 `tid`（租户标识）；后续请求即使不带子域名/头，也据此路由到该校库。
- 跨租户令牌复用被拒绝：令牌 `tid` 与请求解析出的租户不一致时返回 `403 TENANT_MISMATCH`。
- 已验证隔离：A 校创建的数据 B 校物理不可见（`scripts/test-tenant-isolation.js`，7/7 通过）。

## 单校导出 → 转私有化（销售卖点）

SaaS 中某校要转独立部署时，直接 `mysqldump internship_<code>` 整库导出，导入到该校私有服务器，`TENANCY_MODE=single` + `DB_NAME=internship_<code>` 即可，数据零丢失、零改造。

## 相关脚本

- `scripts/provision-tenant.js` —— 开通学校（建库/建表/种管理员/登记）
- `scripts/test-tenant-isolation.js` —— 隔离验证
- `scripts/ui-walkthrough.js` / `ui-walkthrough-m.js` —— 全页面浏览器实走回归
