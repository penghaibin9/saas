# AI 执行状态

> 回来先看这里，不用记流程、不用翻历史。

## 最新更新（2026-07-04）：MySQL 可部署演示（FAST-TRACK-MYSQL-ONLINE-SELLABLE-RUN）

只改 backend/ + frontend/src + miniapp + deploy/ + scripts/ + 本文件；未动 mock 数据、未动数据库冻结册、未 add/commit/push。密码只走 .env（本记录不含任何密码）。

1. MySQL 支持是否完成：是。config 新增 DB_DRIVER/DB_HOST/PORT/NAME/USER/PASSWORD + effective_database_url 组装（mysql+pymysql，charset=utf8mb4）；session 按方言配连接池；requirements 加 PyMySQL；保留 SQLite dev 不删。
2. MySQL 脚本是否完成：是。backend/scripts 新增 check_mysql_connection.py / init_mysql_db.py / reset_mysql_db.py（CONFIRM_RESET_MYSQL=YES 二次确认 + 生产词保护）/ seed_mysql_demo_data.py；种子逻辑抽到 _seed_core.py 单一来源（SQLite/MySQL 共用）。
3. MySQL 是否真实连接成功：本机沙箱无 root/无 MySQL 服务、PyPI 被墙，无法真连；改为离线证明——21 张表全部渲染为合法 MySQL DDL（BIGINT AUTO_INCREMENT / JSON / VARCHAR 带长度 / 索引≤128 utf8mb4 安全）。真连需用户在装了 MySQL 的机器上跑（见第 9 条）。
4. MySQL 种子是否成功：逻辑已验证——真实引擎 create_all 建 21 表通过；18 类 ORM 构造 + commit 通过；demo-school=5、主租户=100、admin/teacher/counselor/student_demo（演示账号已配置，密码只存 pbkdf2 hash，未公开展示）；新增 文件/导入批次/导出任务 测试数据。
5. 后端能否以 MySQL 模式启动：代码就绪（DB_ENABLED=true + DB_DRIVER=mysql 即走 MySQL）；沙箱缺 fastapi/pydantic 无法起 uvicorn，需在用户机验证。
6. PC build 是否通过：lint 通过；build 在本沙箱无法跑（node_modules 为 Windows 版，缺 Linux rollup/esbuild 原生二进制且 registry 被墙）——属环境限制非代码问题，请在 Windows 上 npm run build。
7. miniapp build 是否通过：同上，需在 Windows 上 npm run build:h5 / build:mp-weixin（env.js 已改为可配置 VITE_API_BASE_URL）。
8. 部署配置是否改成 MySQL 版：是。deploy/docker/docker-compose.mysql.yml（内置 mysql:8 utf8mb4，支持外部 MySQL）、deploy/nginx/nginx.mysql.conf（/ PC、/miniapp/ H5、/api/ 反代、安全头+gzip+history 兜底、uploads/exports 挂盘）、deploy/env/backend.mysql.env.example、scripts/deploy/mysql-init.ps1、scripts/deploy/deploy-server-check.ps1。前端 API 地址已可配置（同源生产默认走 /api/v1 经 nginx）。
9. 还缺什么服务器信息：① MySQL 密码（填 backend/.env 的 DB_PASSWORD，勿提交）；② 服务器公网 IP/域名（填前端 VITE_API_BASE_URL 或用同源 + nginx，填 CORS_ORIGINS）；③ 在用户机执行：check_mysql_connection→init_mysql_db→seed_mysql_demo_data，再 uvicorn 起后端、npm 构建两端。
10. git：未 add、未 commit、未 push。

---

## 上一轮更新（2026-07-04）：后端 P0 收口 · 统一为 FastAPI 基线（BACKEND-P0-FASTAPI-BASELINE-CLEANUP）

本轮只做 **backend/ 收口**，不碰 frontend/src、miniapp、docs/ui、数据库冻结文档、package.json（前端）、lock 文件。只修改了 `backend/` 与本文件。

1. **技术栈统一**：`backend/` 主技术栈确认并统一为 FastAPI + Pydantic + Uvicorn。原残留的 Node/Express5/MySQL 脚手架（`package.json`、`config/`、`middlewares/`、`utils/`）**未删除**，已整体归档到 `backend/_legacy_node_express/`，并写 README 说明现状与结论（不可运行、不作为主技术栈）。
2. **接口补齐**：新增 `app/api/v1/todo.py`、`message.py`、`file.py`、`import_export.py`，扩展 `audit.py`（新增 `simple_router`），更新 `router.py` 挂载。任务要求的 15 条接口路径（`/health`、`/api/v1/system/info`、`/api/v1/auth/*`、`/api/v1/tenant/brand`、`/api/v1/rbac/*`、`/api/v1/dashboard/summary`、`/api/v1/todos`、`/api/v1/messages`、`/api/v1/files/upload-placeholder`、`/api/v1/import/validate-placeholder`、`/api/v1/export/create-placeholder`、`/api/v1/audit/logs`）已全部在代码中挂好，均为 mock 数据，与原有正式契约路径（`/api/v1/admin/...`、分端 `/api/v1/{端}/todos` 等）并存，未删除任何既有实现。
3. **统一响应结构**：沿用既有 `code/message/data/traceId/timestamp` 结构（`code` 为字符串业务码，如 `SUCCESS`，对齐 `docs/api/00-API契约冻结总册`），**未改成任务描述里的数字 `0`**——改动会破坏已冻结的 API 契约对齐，本轮判断保留现状更安全，如确需数字码需单独决策。traceId 已保证每个响应都有。
4. **数据库仍是纯预留**：未接真实数据库；`app/models/`、`app/db/` 各加了一份 README 说明现状与 P1 计划，`__init__.py` 内容未动。
5. **测试补齐**：新增 `tests/test_health.py`、`test_openapi.py`、`test_mock_auth.py`、`test_rbac.py`；`requirements.txt` 增加 `pytest`、`httpx`。
6. **运行验证的真实情况（如实记录，不夸大）**：本次执行环境是隔离的 Linux 沙箱，且发现两个直接原因导致**无法在本次会话内实际跑通 `uvicorn`/`pytest`**：(a) 沙箱无法访问 PyPI（`pip install` 全部 403/超时），(b) `backend/.venv` 是此前在用户 Windows 机器上创建的 Windows 版本（`Scripts/python.exe`），Linux 沙箱无法执行。所有新增/修改代码已逐一做 AST 语法检查（全部通过，0 错误）并人工核对路由/依赖引用一致，但**尚未在真实可运行环境验证 `/health`、`/docs`、`pytest` 是否真正 200/通过**。请在本机按 `backend/README.md` 步骤实测，如报错请反馈以便继续修。
7. **下一步 P1**：接入 PostgreSQL + SQLAlchemy + Alembic，从学生主档第一张真实表开始建模。
8. 本次未提交 git、未 push。

## 2026-07-04：PC UI v2 最终验收与提交（PC-UI-V2-FINAL-ACCEPT）

本轮只做 **PC UI 最终验收 + 提交前整理**，不碰 miniapp / backend / deploy / scripts / 数据库文档。

1. **lint**：通过（eslint 0 错误 0 警告）。**build**：沙箱无法访问 npm registry（node_modules 为 Windows 版、缺 Linux 二进制），未能在沙箱执行；以本机 dev server 实测代替：12 个 /admin 页面全部打开正常，无白屏、无控制台红错、无横向滚动条。正式发布前建议本机跑一次 `npm run build` 复核。
2. 验收中修复 2 个小问题：`/admin` 裸路径无路由会白屏 → `router/index.js` 增加 `{ path: '/admin', redirect: '/' }`；工作台页脚残留「/dev/preview 旧产品体验页」入口 → 已从 `AdminWorkbenchView.vue` 移除（/dev/preview 存档路由本身保留）。
3. 前端展示文案无「职校」主名称残留（浏览器标题与门户品牌均为「高校学生全生命周期管理平台」；「演示职业技术学院」为租户名非产品名）。「产品体验中心」字样仅存于 /dev/preview 存档页内部，无对外入口。
4. 本次提交仅包含：`frontend/src/`、`docs/ui/pc-ui-v2/`、`AI执行状态.md`。miniapp / backend / deploy / scripts / 各类文档改动**未**纳入本次提交。未 push。
5. 备注：本文件此前一次写入被截断（下方 PROJECT-CONTRACT-QA-DEMO-DOCS 段仅存开头部分，`docs/backend-integration/` 及其后的 `docs/sales/`、`docs/qa/` 明细行丢失，完整清单以各目录 README 为准）。


## 2026-07-04：接口契约 / 权限 / 测试 / 演示 / 后端接入 / 销售 / 风险 七类交付文档（PROJECT-CONTRACT-QA-DEMO-DOCS）

本轮只补**交付类文档**，不碰任何业务代码、不碰数据库冻结册。只动了 `docs/api/`（仅新增，未改旧�
## 2026-07-04 · BACKEND-OVERNIGHT-FULL-FOUNDATION-AND-FIRST-REAL-API

### 阶段 0 · 现状扫描（只读）
- 技术栈痕迹：backend 已是 FastAPI + Pydantic-settings + Uvicorn（Python 3.12 .venv 已存在，fastapi/uvicorn 已装）；Node/Express 残留**已在早前归档**至 backend/_legacy_node_express/（含 package.json/config/middlewares/utils + README）。
- FastAPI：存在（app/main.py + api/v1 15 个路由文件 + core 响应/异常/上下文/安全 + mock services + 4 个测试）。
- 真实数据库连接：无（DB_ENABLED=False，DATABASE_URL 空）。ORM 模型：无（models/ 空占位）。Alembic：无。测试：4 个（health/openapi/mock_auth/rbac）。
- 最大问题：无 SQLAlchemy/Alembic/pytest 依赖与模型层；缺 students/approvals API；响应码为冻结契约字符串码而任务要求数字码（决定：双码兼容 code=数字 + bizCode=字符串，见阶段4）。
- 冻结册已读：表统一 t_ 前缀；公共字段 §1.2；审计表 append-only；组织=t_college/t_major/t_class；待办=t_unified_todo；审批=t_workflow_instance/task；无 t_menu 表（菜单来自 RBAC 配置，不造表）。

### 阶段 1–22 · 执行结果（最终）
1. 后端已统一为 FastAPI（+Pydantic+SQLAlchemy 2.x+Alembic+Uvicorn+Pytest）；Node 残留此前已归档 backend/_legacy_node_express/，本轮未移动 FastAPI 文件。
2. /health /docs /openapi.json：Windows 本机实测全部 200（清掉旧 8000 端口进程后用新代码复验，/health 返回 code=0/bizCode=SUCCESS/dbEnabled=false）。
3. pytest：**27 passed**（修 1 次：audit_log.record 参数签名不匹配）。compileall app/tests/alembic 通过。
4. Alembic 新增：alembic.ini + env.py + script.py.mako + versions/0001_init_core_tables.py（不自动执行）。
5. 第一批 ORM 19 模型（t_ 前缀按冻结册；冻结册无 t_org/t_menu → 组织用 t_college/t_major/t_class，菜单不建表）：t_tenant、t_tenant_brand_config、t_college、t_major、t_class、t_user、t_role、t_permission、t_user_role、t_role_permission、t_student_profile、t_student_contact、t_student_stage_event、t_student_import_batch、t_workflow_instance、t_workflow_task、t_unified_todo、t_unified_message、t_security_audit_log、t_export_task（20 张，含导入批次即 import_log）。
6. 学生主档 API：7 接口全部可用（列表筛选/详情360/新增/更新/逻辑作废/时间线/风险摘要），DB_ENABLED=true 骨架已留（TODO P3）。
7. 审批 API：7 接口可用（待办/详情/通过/驳回≥5字/转办/已办/抄送），操作全部写审计。
8. 审计：内存队列 + /audit/logs 查询 + mock-record；重启丢失已在 README 声明；模型 t_security_audit_log 就绪。
9. 统一响应改为双码：code=数字（0/400001/401001/403001/403002/404001/409001/422001/500001）+ bizCode=冻结契约字符串码（兼容 docs/api/00 契约，旧测试已同步更新）。
10. 当前连接真实生产数据库：否（DB_ENABLED 默认 false，不连不建不删）。
11. 下一步建议：backend P3 —— 真实 PostgreSQL 初始化 + 学生主档真实 CRUD 联调（见 docs/backend-integration/后端下一阶段任务清单.md）。
12. PC UI / miniapp / frontend/src 是否被修改：否。forbidden 路径零改动。
13. 插曲记录：app/api/v1/router.py 发现同步截断损坏（文件在 include make_todos_router 处截断），已按其自身结构重建并补挂 students/approvals/audit/tenant/rbac/dashboard 等前缀；验证以 Windows 本机 pytest+uvicorn 实测为准。

### BACKEND-DB · SQLite 真实数据层（本轮）
- dev.db：scripts/reset_dev_db.py / init_dev_db.py（20 表）/ seed_demo_data.py（租户+品牌+组织+2用户+6学生+3审批+4待办+3消息+1审计）全部跑通，幂等。
- 五域真实走库（backend/.env DB_ENABLED=true + sqlite dev.db）：students（列表/详情360/新增/更新/逻辑作废/时间线/风险）、approvals（待办/详情/通过/驳回≥5字/转办/已办）、todos（列表/汇总/完成）、messages（列表/已读）、audit（record 双写内存+t_security_audit_log，query 走库）。统一 tenant_id 过滤 + is_deleted=false；手机号存 contact_value_encrypted（演示占位明文，真实环境为密文）响应恒脱敏。
- 已知 TODO：riskLevel 暂借 StudentProfile.remark 存演示值（P4 接风险信号表）；utcnow Deprecation 待批量换 timezone-aware。
- pytest：**32 passed**（27 mock + 5 DB 模式端到端，临时 SQLite 独立夹具，互不污染）。
- 实测（Windows .venv + uvicorn + dev.db）：health code=0 dbEnabled=True；docs/openapi 200；students=6；approvals=3 PENDING；todos=4；messages=3；audit=2（含落库）。
- 修改范围仅 backend/ 与本文件；未写任何新文档；未提交。

### P1-BACKEND-REAL-DB-RUN（短状态）
- dev.db 迁至 backend/data/dev.db（gitignored）；reset/init/seed 三脚本可重复跑。
- 种子达标：1租户+1品牌+8角色+20用户+100学生(含电话/阶段事件)+20审批+30待办+20消息+50审计。
- 全接口实测通过（uvicorn+dev.db）：students 100/详情/新增(101)/PUT 更新 v=1/void 逻辑删除；approvals 20：approve/reject无reason被422拦截/reject/transfer；todos PENDING=24→done；messages 20→read；audit 50→52（业务操作双写落库，含 mock_audit_service 通道补齐）。
- health code=0 dbEnabled=True；docs/openapi 200；pytest 32 passed。未连生产 PG；只改 backend/ 与本文件；未提交。

### P2-PC-CONNECT-BACKEND-REAL-API（短状态）
- 新增 frontend/src/services/http/（config/client/adapters/index）：API_BASE_URL 默认 http://localhost:8000（VITE_API_BASE_URL 可覆盖），统一解析 code/bizCode/message/data/traceId/timestamp，自动 mock-login 取 token，4s 超时 + 15s 离线冷却 + toast 提示，后端挂了自动回退 mock 不白屏；localStorage.useRealApi='false' 可整体关闭真实接口。
- 已接主链（真实接口，失败回退 mock）：tenant/brand + rbac/current-context + todos/summary（合入 student/approval 两模块 getContext：品牌/currentRole/dataScope/pendingCount，产品名=高校学生全生命周期管理平台）；students 列表/详情/新增/更新/作废；approvals 待办列表/详情/通过/退回(reject) + getTodoSummary；audit/logs（系统管理·审计查询）。字段适配在 services/http/adapters.js（DTO 对齐 mock 契约，UI 零改动）。
- mock 全量保留（原方法改名 _mockXxx，桥接失败即回退）；权限矩阵/字典/availableRoles 仍来自 mock（后端第一批未覆盖）。
- lint ✅ 0 错误；build ✅ 3.49s。后端 uvicorn(8000) 与 vite dev(5173) 均已启动供人工点验 /admin/student/list（真实库 100 名学生）。屏幕使用中，未做页面截图。
- 未动 miniapp / docs/ui / 路由结构 / UI 风格；未提交。

### P3-MINIAPP-CONNECT-BACKEND-REAL-API（短状态）
- miniapp 真实后端优先接入（http://localhost:8000，ENV.useMock=true 可整体回退纯 mock）：新增 services/realApi.js（字段适配层）；request.js 实现 realRequest（统一响应解析/token/4s超时/15s离线冷却+toast，不白屏）与 realFirst 兜底。
- 登录/角色切换：session.login/switchRole 同步后端 mock-login（角色→账号映射：student01/counselor01/teacher01/employment01/academic01/college_admin01），token 存 uni storage；本地角色配置与学生/教师端入口全保留。
- 学生端已接：首页(阶段+待办计数 enrich)、我的档案(真实学生合入)、消息中心(真实消息合入 tabs/groups)。教师端已接：我的学生/风险学生(真实 100 学生)、学生360(数字 id 走真实)、审批列表+通过/驳回/退回(数字 id 调真实接口，mock 编号保持演示)、移动待办、消息。其余页面仍 mock。
- build:h5 ✅ / build:mp-weixin ✅（DONE Build complete）。未动 frontend/src 与 UI 风格；未提交。

### 登录页试用咨询入口 + 演示账号收敛（短状态）
- PC 新增 /login 登录页（母版登录屏风格）：账号密码走 POST /api/v1/auth/login（真实校验），「进入演示环境」按钮保留原工作台入口；试用咨询区块（想为学校开通正式试用？请联系平台服务顾问：13549666867，复制手机号 + tel: 拨打）。
- miniapp 登录页：演示按钮统一为「进入演示环境」；新增账号密码登录（走 /auth/login，成功按角色进入学生端/教师端）；底部试用咨询卡（13549666867，复制 + 拨打，H5/mp 双端）；移除"不接后端"旧口径文案。
- 后端：POST /api/v1/auth/login（t_user + pbkdf2_sha256 校验）；seed 新增 demo-school 租户（演示职业技术学院）+ 4 个演示账号，**密码仅以 pbkdf2 哈希入库，仓库与页面均不含明文（演示账号已配置，密码未公开展示）**；令牌携带 tenantId，租户绑定移至中间件 async 上下文（修复 contextvar 传播），实测隔离：demo 账号仅见 demo-school 5 名学生，主租户 100 名不可见；错误密码 401。
- 验证：pytest 32 passed；PC lint/build ✅（3.39s）；miniapp build:h5 / build:mp-weixin ✅；后端已重启运行于 8000。

### P3.5-FIX-DEMO-PASSWORD-SIMPLE（短状态）
- demo-school 四个演示账号（admin/teacher/counselor/student_demo）密码已统一简化并隐藏展示：种子脚本仅存新 pbkdf2_sha256 哈希，仓库/页面/本文件均无明文；旧密码已失效（实测 REJECTED）。
- 四账号新密码登录实测均 code=0 且角色正确；pytest 32 passed；PC build ✅；miniapp build:h5 / build:mp-weixin ✅。登录页未改结构，仍只显示试用电话 13549666867。后端已重启（8000）。

### P4-文件上传/导入导出/审计（短状态）
- 文件上传（真实）：POST /api/v1/files/upload（白名单+黑名单校验、50MB 上限、sha256、UPLOAD_DIR 落盘、t_file_object 登记、审计）+ GET /files/meta/{id}；新增 models/file.py（t_file_object，冻结册表卡）。
- 学生导入（真实两步）：/import/students/validate（JSON 行）与 /validate-file（xlsx/csv，openpyxl 解析）Dry-Run 写 t_student_import_batch，行级错误（必填/文件内重复/库内重复）；/import/students/confirm 整批一个事务失败回滚，插入含联系方式加密列。
- 学生导出（真实 xlsx）：/export/students 用途≥5字必填 → openpyxl 生成（首行水印：平台名/导出人/时间/用途/脱敏声明；手机号恒脱敏）→ t_export_task(file_hash) + 审计；/export/tasks/{id}/download 下载（写 DOWNLOAD 审计）。占位接口全部保留。
- 审计增强：中间件补 ip/userAgent/method/path 请求元（仅新增行，租户绑定逻辑未动）；t_security_audit_log 落库带全字段；/audit/logs 支持 action/operator/dateFrom/dateTo 过滤。
- PC：学生主档导出入口接真实（createExport 真实优先→自动打开下载链接，mock 校验流保留为回退）；审计日志真实接口沿用 P2 桥接自动获得新字段。导入入口暂保留 mock（页面无真实文件控件，后端 validate-file 已就绪）。miniapp 本轮未动。
- 回归门槛通过：demo-school=5 / 主租户=100 / demo 登录 code=0；P3.5 保护文件仅 middleware/context.py 增加请求元 3 行（兼容性增量）。pytest **36 passed**（新增 4 个 P4 用例：上传/导入两步/导出下载/审计过滤）；PC lint ✅ build ✅（3.59s）；后端已重启（8000）。

### P4.1-PC-REAL-STUDENT-IMPORT-FIX（短状态）
- PC 学生主档导入接真实：导入页新增隐藏文件控件（xlsx/csv）→ multipart 上传 /import/students/validate-file → 展示 totalRows/validRows/errorRows + 错误表（行号/字段/原始值/错误说明，后端错误行补 rowIndex/field/rawValue 增量键）→ 真实批次校验失败禁 confirm（后端 400 双保险实测 BLOCKED）→ /import/students/confirm 成功后跳转学生列表刷新。mock 演示流完整保留（离线自动回退，"跳过错误行"仅 mock 流显示）。
- client.js 新增 requestUpload（FormData multipart，15s 超时，离线冷却复用）。
- 联调实测：坏文件 DRY_RUN_FAILED(err0: rowIndex=3/field=studentNo/rawValue 有值) → 好文件 PASSED → confirm inserted=1 → 列表可查(手机号脱敏)。回归：demo 登录 OK、demo-school=5。pytest 36 passed；PC lint ✅ build ✅(3.54s)。临时验证文件已清理，后端运行于 8000。

### P5-部署准备（短状态）
- 范围：与 P4/P4.1 并行执行，只做部署准备，不改业务逻辑。本轮只新增/修改了
  `deploy/`、`scripts/deploy/`、`backend/Dockerfile`、本文件，未碰 `backend/app`、
  `backend/scripts/seed_demo_data.py`、`frontend/src`、`miniapp`、`docs`、
  `00-今天新设计文档`、`99-老毕业设计系统-只参考不要照抄`、根 package.json、任何 lock 文件。
- 新增 `backend/Dockerfile`：python:3.12-slim，白名单方式 COPY（app/、alembic/、alembic.ini、
  requirements.txt、scripts/），不打包 `.venv`/`.env`/`data`/`uploads`/`_legacy_node_express`/`tests`；
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`（不带 --reload）；HEALTHCHECK 探 `/health`。
- 新增 `deploy/docker/docker-compose.local.yml`：backend + postgres(16-alpine，真实服务) +
  redis(7-alpine，预留占位，backend 当前未接入真实缓存逻辑) + nginx(1.27-alpine)。
  端口规划：80(nginx·PC)、8080(nginx·miniapp H5)、8000(backend)、5432(postgres)、6379(redis)。
  数据用具名 volume（pgdata/backend-data/backend-uploads/redisdata），不绑定挂载到仓库目录，
  与本机非 Docker 的 SQLite 开发流（`backend/data/dev.db`）互不干扰。
- 新增 `deploy/nginx/nginx.conf`：单个完整配置（供整体挂载替换官方 nginx 镜像默认配置），
  两个 server 块（:80 PC / :8080 miniapp H5），均含 try_files 前端路由兜底、index.html 不缓存、
  静态资源长缓存、gzip（http 层全局）、4 条基础安全响应头、`/api/` 反代 `http://backend:8000`。
  与仓库既有的 `deploy/nginx/pc-frontend.conf.example`、`miniapp-h5.conf.example`（传统宿主机
  Nginx + conf.d 模式）并存、不冲突、不是同一部署形态，均未改动旧文件。
- 更新 `deploy/env/backend.env.example`：DATABASE_URL 指向 compose 里的 postgres 服务名；
  如实注明 Postgres 首次是空库，需手动 `alembic upgrade head` 建表才能真正读写，不迁移也不会
  报错崩溃（会退回 DB_ENABLED=false 的 mock 行为）；REDIS_URL 标注"预留，backend 未接入"。
- 新增 `deploy/env/frontend.env.example`（任务要求的新文件名，与既有 `pc-frontend.env.example`
  内容等价、变量一致，互不冲突，二选一使用）；更新 `deploy/env/miniapp.env.example` 的
  `MINIAPP_API_BASE_URL` 说明为经本地 nginx（8080）或直连 backend(8000) 两种可选值。
- 新增 4 个 `scripts/deploy/*.ps1`（沿用 `scripts/dev/`、`scripts/check/` 现有风格：UTF-8 BOM、
  Write-Host 彩色输出、`$PSScriptRoot` 定位根目录、失败非 0 退出码、`Read-Host` 收尾防止窗口秒关）：
  `build-pc.ps1`（frontend npm run build → 校验 dist/index.html）、
  `build-miniapp.ps1`（miniapp build:h5 必须过 + build:mp-weixin 尽量过，两者独立汇总）、
  `start-backend.ps1`（docker compose up backend，自动带 postgres/redis 依赖，`-All` 可选连 nginx，
  首次自动从 `.example` 复制 `backend.env`，轮询 `/health` 但不影响退出码）、
  `check-deploy.ps1`（纯只读：10 个部署文件是否齐全 + `docker compose config` 语法 +
  临时容器 `nginx -t` 语法 + 5 个规划端口占用情况汇总，全程不启动/不停止任何服务）。
- 验证方式的真实情况（如实记录，不夸大）：本次执行环境是隔离 Linux 沙箱，**没有 docker、
  没有 nginx 二进制、没有 pwsh，也无法联网装（apt/pip 均被拒绝/断网）**，因此未能真正跑
  `docker compose config`、`nginx -t`、PowerShell 解析器做终极语法验证。已做的替代验证：
  (a) `docker-compose.local.yml` 用 Python `yaml.safe_load` 解析通过，并额外用自定义
      Loader 排查过无重复 key；services/networks/volumes 结构、端口、depends_on 均核对与设计一致；
  (b) `nginx.conf` 用逐字符括号计数确认 `{`/`}` 配对且深度归零，两处跨行指令（log_format、
      gzip_types）人工确认以 `;` 收尾；`root`/`proxy_pass` 目标与 compose 里的 volume 挂载路径、
      服务名逐一核对一致；
  (c) 4 个 `.ps1` 脚本用 Python 做括号/引号计数（排除注释行后）确认 `{}()[]` 全部配对、
      单引号数量为偶数；UTF-8 BOM（`EF BB BF`）与仓库既有脚本逐字节比对一致；
  (d) Dockerfile / env 示例文件人工逐行核对，未做自动化工具验证。
  **请在本机装好 Docker Desktop 后，实际跑一次 `scripts\deploy\check-deploy.ps1` 和
  `docker compose -f deploy\docker\docker-compose.local.yml config` 复核，如报错请反馈。**
- 未真实起任何容器、未连服务器；只做本地部署预演配置准备。
- 是否修改 `backend/app`：否。是否修改 `frontend/src`：否。是否修改 `miniapp`：否。
- 本次未 `git add`、未 `commit`、未 `push`、未执行任何 `git stash/reset/checkout`。

### P5.5A-BACKEND-SECURITY-HARDENING（短状态）
- 新增 core/token_store.py（内存态基础版，生产迁 Redis 只换此模块）：refreshToken 签发/一次性轮换/按用户吊销；access jti 黑名单；登录失败 5 次锁 15 分钟；滑动窗口限流。
- JWT：access 带 jti；密钥走 settings.jwt_secret（环境变量 JWT_SECRET_KEY/JWT_SECRET）；assert_secret_safe 生产默认弱密钥拒启；get_current_user 校验 jti 黑名单。
- /auth/refresh（轮换，旧 refresh 复用返回 401001）；/auth/logout 真失效（jti 黑名单 + 吊销该用户全部 refresh，实测登出后 me=401）；mock-login 与 /auth/login 均签发真实 refreshToken。
- 锁定：/auth/login 错 5 次锁 15 分钟（审计 LOGIN_FAIL/LOGIN_LOCKED，锁定态 401 提示剩余分钟）。
- 限流：登录 10 次/IP/分（429001+审计 RATE_LIMITED）、上传 20 次/用户/分、导出 5 次/用户/分；403/越权与限流统一在异常处理器写审计 PERMISSION_DENIED/RATE_LIMITED。
- PC client：存 refreshToken，401 自动刷新一次重试，新增 logoutRemote()；miniapp request：refresh 存储 + 401 刷新重试（uni storage）。登录页/试用电话/演示账号隐藏逻辑零改动；P4 导入导出接口零改动（仅导出加限流守卫）。
- 回归：demo-school=5 / 主租户=100（重灌后精确恢复，此前 101 为 P4.1 联调导入的合法数据）/ demo 登录 code=0 + refresh code=0 + 登出后 401。pytest **41 passed**（新增 5 个安全用例；conftest 每用例重置内存安全态，db_mode 夹具上移共享）；PC lint ✅ build ✅；miniapp h5/mp-weixin ✅。deploy/nginx/Dockerfile 未触碰。后端运行于 8000。

### FINAL-INTEGRATION-CHECK-NO-COMMIT（终检结论）
- 危险文件：无「演示账号密码.txt」；backend/.env、data/dev.db、uploads/ 均已 gitignore 未被追踪；git ls-files 中的 uploads 匹配仅为 docs/ui 与 99-老系统的历史设计资产（非运行时数据，未动）；补 backend/.dockerignore（.venv/.env/db/uploads/缓存），Dockerfile 本就只 COPY requirements/app/alembic/alembic.ini/scripts。
- 后端全矩阵实测：health/docs/openapi=200；demo 登录 0 / 错密码 401001 / 无 token 401001；跨租户访问被拒(404001 不泄露存在性)；students 详情/审批 20/待办 30/消息 20；上传 0 且 evil.exe 被拒 400001；validate-file=DRY_RUN_PASSED→confirm=SUCCESS+1；export=SUCCESS→download=200→审计 EXPORT 命中；pytest 41 passed。终态已 reseed 恢复基线：demo-school=5 / 主租户=100。
- 构建：PC lint 0 错误 + build ✅；miniapp build:h5 / mp-weixin ✅。产物级校验：两端登录页 chunk 均含 13549666867，全产物+源码 grep 无任何明文密码。
- 部署：10 个部署文件齐全；nginx.conf 含 PC/miniapp 双站点 root、/api/ 代理、try_files history fallback、gzip、X-Frame-Options/X-Content-Type-Options。
- 本轮修复仅 2 处小项：backend/.dockerignore（新增）；无其他代码改动。页面级人工点验（/login、学生列表、导入导出、审批、审计、断网 fallback）此前各阶段均已实测通过，本轮以接口矩阵+产物校验复核，未重复占用用户屏幕。
- 建议提交分组见终检输出；未 add/commit/push。


### P6-PLATFORM-OWNER-CONFIG-AND-RULE-CENTER（平台老板总控台）
- 后端配置中枢：新增 t_platform_config（KV：tenant_id=0 全局默认，租户行覆盖；PACKAGE/FEATURES/RULES/WORKFLOWS/DICT/BRAND/SECURITY/SETTINGS/TENANT_META 九类）+ t_order + t_platform_notice 三张表；三级合并生效（平台默认 ← 套餐 ← 租户覆盖）。
- 强校验：/api/v1/platform/*（约 45 个端点）全部经 require_platform_super_admin 后端依赖校验；SCHOOL_ADMIN/TEACHER/STUDENT 一律 403 NO_PERMISSION 且写审计 PERMISSION_DENIED；未登录 401。
- 租户全托管：列表/详情/新建（tenantCode 唯一 409）/启停/延试用/试用转正式/标记到期/变更套餐/容量覆盖/用量/重置演示数据（仅 demo-school，恢复 5 人基线）。停用租户全员登录被拒（403+审计）；到期租户可登录可查看、所有写操作 403 MODULE_EXPIRED_READONLY（中间件级，续费提示含 13549666867）。
- 规则中心真生效（不是摆设）：审批驳回原因最小字数、导出用途必填+最小字数、单次导入最大行数、上传大小上限均实时读取规则中心（改完立即按新值校验，已有用例证明）；5 档套餐（trial/basic/standard/professional/private）价格/时长/容量/功能可改；19 个功能开关关闭后业务接口 403 MODULE_NOT_AUTHORIZED；8 类审批流开关/时限可配；12 类字典可改；品牌（顶栏名/水印/主色/咨询电话）可配；安全参数带合法边界（越界拒绝保存，不允许不设防）；订单标记支付自动开通/续期；公告草稿→发布→下线；跨租户审计查询（tenantId/action/operator/日期过滤）。
- 账号控制：为任意学校创建管理员/停用/启用/重置密码；初始密码与新密码仅响应一次性返回，不落任何日志与文档。
- 种子扩展（幂等，基线不动）：平台运营中心租户 + 平台超管账号（platform_owner，密码只存 pbkdf2 哈希，未公开展示）+ trial-school（试用中）/expired-school（已到期只读）/disabled-school（已停用禁登录）三个演示租户（各 1 管理员 + 2 学生，密码同样只存哈希）+ 2 订单 + 2 公告；主/演示租户补 TENANT_META（professional/standard，远期到期）。重灌链路（_seed_core.run）已挂接平台种子；也可对既有库单独执行 scripts/seed_platform_data.py。
- PC 平台总控：新增 10 个真实接口页面（views/admin/platform/control/：总控台总览/租户管控[开通抽屉+行操作]/租户配置中心[运营容量/功能开关/规则/审批流/品牌/账号 六页签]/套餐/字典/订单/公告/安全/全平台审计/系统参数），platformControl.api.js 真实优先+演示兜底不白屏；platform.routes.js 新增 overview、tenants/create、features、rules、workflows、brands、users、dictionaries、notices、security、audit、settings 路由并将 tenants/:tenantId、packages、orders 指向真实页；AdminPlatformLayout 侧栏与 adminMenu 平台组同步扩充（platformOnly）。
- 回归与验收：pytest **57 passed**（新增 16 个平台用例：403 强校验/租户生命周期/停用禁登/到期只读/开关 403/规则动态生效/安全边界/订单开通/公告/一次性密码/拒绝审计落库）；live smoke 全过（总览 6 租户 111 学生、demo 管理员平台接口 403 且学生仍=5、disabled 登录 403、expired 写 403 读 200）；PC lint 0 错误 + build ✅（516 modules）；基线终态 demo-school=5 / 主租户=100。
- 未 git add、未 commit、未 push；未触碰 miniapp/、deploy/、.env、dev.db 基线数据。
