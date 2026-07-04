# backend/ · 高校学生全生命周期管理平台 后端

## 技术栈（唯一主线）

**FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + Uvicorn + Pytest**（Python 3.12）。
Node/Express/MySQL 残留已归档 `backend/_legacy_node_express/`（不参与运行，勿引用，确认无用后可删）。

## 快速启动（新手照做即可）

```bash
cd backend
python -m venv .venv                 # 已有 .venv 可跳过
.venv\Scripts\activate               # Windows；Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

验收地址：
- http://localhost:8000/health （统一响应：code=0 / bizCode=SUCCESS / traceId / timestamp）
- http://localhost:8000/docs （Swagger）
- http://localhost:8000/openapi.json

## 测试

```bash
.venv\Scripts\python.exe -m pytest -q     # 默认 DB_ENABLED=false（mock 模式），当前 27 passed
```

## 统一响应与错误码（双码）

`code` 数字码：0 成功 / 400001 参数错误 / 401001 未登录 / 403001 无权限 / 403002 数据范围越权 /
404001 不存在 / 409001 冲突 / 422001 校验失败 / 500001 系统异常。
`bizCode` 字符串码：兼容 docs/api/00-API契约冻结总册（SUCCESS / NO_PERMISSION / ...）。

## 数据库（默认关闭）

- 默认 `DB_ENABLED=false`：**不连库、不建表、不删表**，全部接口返回 mock。
- 启用：复制 `.env.example` 为 `.env`，设 `DB_ENABLED=true` 与
  `DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/student_lifecycle`。
- PostgreSQL 准备：建空库 `student_lifecycle` 即可，建表走 Alembic（下节），禁止手工建表。
- 测试库：`TEST_DATABASE_URL=sqlite+pysqlite:///:memory:`。

## Alembic

```bash
cd backend
alembic upgrade head                                  # 执行第一版迁移（0001_init_core_tables，19 张核心表）
alembic revision --autogenerate -m "your message"     # 模型变更后生成新迁移（需可连库）
```
说明：0001 以 app.models metadata 建表（与模型单一事实来源）；P3 接真实 PG 后改用 autogenerate 精确差量。
不自动执行迁移、不自动 drop。

## 当前真实完成 / 仍是 mock

已真实完成：统一响应+traceId+全局异常；mock 登录（8 演示账号：student01/counselor01/teacher01/
employment01/academic01/college_admin01/school_admin01/platform_admin01，密码任意非空）；
/auth/me、switch-role、logout；租户品牌（产品名=高校学生全生命周期管理平台）；RBAC 菜单/权限/数据范围/
角色目录/current-context；学生主档 7 接口；审批任务 7 接口；看板/待办/消息；文件上传与导入导出占位；
审计日志（内存队列，**服务重启即丢失**，DB_ENABLED=true 后写 t_security_audit_log）；
SQLAlchemy 第一批 19 模型 + Alembic 0001；pytest 27 用例。

仍是 mock/TODO：真实登录与密码哈希（P1/P2）；DB_ENABLED=true 的真实 CRUD（P3）；流程引擎；
对象存储（MinIO/OSS）；Excel 解析生成；消息渠道下发；国密与字段加密（见 docs/security/03）。

## 后续开发顺序

P3：真实 PostgreSQL 初始化 + 学生主档真实 CRUD 联调 → 审批接流程引擎 → RBAC 真实权限表 →
文件接 MinIO → 导入导出接 Excel → 审计落库。详见 docs/backend-integration/后端下一阶段任务清单.md。
