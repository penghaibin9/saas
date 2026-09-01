# O4 服务端报到资格 / 缴费 / 绿色通道 Authority 证据

- 阶段：O4
- 进入阶段 HEAD：`5b3f667d104363f77c452c447752e350b1e1053d`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_orientation_qualification_o4`
- parent：`20260901_dorm_checkout_d4`
- Fresh MySQL：本机隔离 MySQL 8.0.46，`saas_d4_fresh_local`
- 阶段结束前 `origin/main`：`de4d07d9053e902e7f4a9de18d30117a09f196db`，divergence 为 `11 9`

## Authority 与阶段边界

- 最终报到资格由后端 `orientation_qualification_service` 唯一计算和持久化；教师 PC、学生 PC、学生小程序、教师小程序只展示服务端 verdict，不在 Vue 中重算。
- 资格事实包含：真实学生/账号绑定、冻结流程版本、正式材料文件证据及扫描状态、缴费或已批准绿色通道、canonical 宿舍关系、开放异常和必办步骤。
- verdict 仅为 `QUALIFIED / NOT_QUALIFIED / MANUAL_REVIEW`；blockers、facts、规则版本和事实哈希同时持久化，便于解释与审计。
- 缴费以 `OrientationPaymentAccount` 作为校内投影，核验同步采用 expected-version CAS；O4 不伪造支付渠道回调。
- 绿色通道以 stable `student_id` 关联正式学生，学生提交使用 `client_request_id` 幂等，教师审批使用 expected-version CAS。
- 材料资格只认 `FileObject / FileAsset / FileVersion / FileBinding` 正式文件 Authority，不把文件名或 URL 当作证据。
- 宿舍事实只读取 canonical `DormStay / DormBed`，不把 `OrientationStudent.building/room/dorm_status` 投影提升为真值。

## Schema 与迁移

- 新增 `t_orientation_material_requirement`、`t_orientation_payment_account`、`t_orientation_qualification_decision`。
- `t_orientation_green_channel_application` 增加稳定 `student_id` 与 `client_request_id`，并建立租户内幂等唯一约束和状态约束。
- MySQL 非事务 DDL 前置校验覆盖目标表/列碰撞、缺失 batch/flow、非法租户/状态/支付事实和未知流程状态。
- D4 → O4、O4 → D4、D4 → O4 round-trip 均通过。
- 负向 preflight：注入一条缺失 batch/flow 的迎新学生后，升级在任何 O4 DDL 前失败；Alembic 仍停留 D4，3 张目标表和绿色通道新列均为 0。删除探针后重新升级成功。
- O4 目标表与绿色通道表的 programmatic `compare_metadata` 差异为 0；全仓历史 drift 仍按进入阶段前事实记录，未伪称全仓清零。
- 最终 Fresh DB 与仓库均为唯一 `20260901_orientation_qualification_o4 (head)`。

## API 与四端交付

- 教师端新增资格列表、详情、按当前事实重算、缴费核验同步 API；列表和详情均在服务端执行租户、权限和 Data Scope。
- 学生 PC 和学生小程序读取同一个资格详情与缴费投影，展示服务端阻断项和规则版本。
- 教师 PC 资格页不再拼装前端结论；缴费核验使用站内 `AppDrawer`，绿色通道审批带 expected-version。
- 学生绿色通道提交在 PC/小程序使用稳定 UUID 客户端请求号；网络重试不会创建第二张申请单。
- 教师小程序绿色通道审批使用同一 CAS 版本语义，不保留“看似成功”的本地降级。
- 关键动作已移除原生 `window.confirm`；真实 Chromium 中资格重算和缴费核验均打开站内角色对话框/抽屉，`getJsDialog()` 为空。

## Chromium REAL 验收

- 使用真实后端、真实 MySQL、真实账号登录；没有 mock API 或 seed fallback。
- 教师 PC 资格页读取一名 O4 学生，显示服务端结论“暂不具备报到资格”，阻断项为身份证、录取通知书、未缴费且无获批绿色通道，规则版本为 O4.1。
- 教师 PC 点击“按当前事实重算”打开站内对话框；点击“核验缴费”打开站内抽屉，均未出现截图所示的 `127.0.0.1` 原生弹窗。
- 学生 PC 真实登录后读取同一服务端 verdict、三项 blockers 和缴费投影 `应缴 6800 / 已缴 0`，四端没有各算一套资格。
- 验收专用用户、临时权限已删除，学生账号绑定已恢复为原 `D4S001`；未把浏览器测试账号留进阶段数据库。

## 自动化测试与构建

- O4 MySQL 目标测试：`backend/tests/test_orientation_o4_qualification.py::test_o4_server_verdict_green_idempotency_payment_cas_and_exception`，`1 passed`。
- 迎新兼容回归：`test_orientation.py::test_green_channel_closed_loop` 与 `test_portal_orientation.py::test_orientation_submit_without_record`，均通过。
- 教师 PC O4 合同：`frontend/tests/o4-orientation-qualification-contract.test.mjs`，`3/3 passed`。
- 教师 PC production build：通过（仅保留进入阶段前的 CSS import/chunk warning）。
- 学生 PC production build：通过。
- 小程序 H5 production build：通过；学生端与教师端 O4 页面使用真实 API service，mock=false。
- `py_compile`、`git diff --check`、迁移 round-trip、single-head 和 O4 target drift：通过。

## 负向用例

| 用例 | 结果 |
|---|---|
| 学生重复提交同一绿色通道请求 | 返回原申请，不创建重复记录 |
| 同一请求号改变业务参数 | 幂等冲突，拒绝覆盖原申请 |
| 绿色通道或缴费使用 stale version | 409，拒绝覆盖较新事实 |
| 缴费不足且无获批绿色通道 | 服务端 `NOT_QUALIFIED`，前端不得改判 |
| 正式材料缺失或文件扫描未通过 | 输出明确 blocker，不以文件名/URL 代替证据 |
| 开放异常或事实不可自动确认 | 服务端 `MANUAL_REVIEW`，不冒充具备资格 |
| 缺失 batch/flow 的历史迎新学生 | 迁移在 DDL 前失败，无部分建表/加列 |
| 跨租户、无权限或超出 Data Scope | 服务端 fail-closed |

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | O4 证据 |
|---|---|---|
| 服务端报到资格 Authority | REAL | 真实 MySQL 事实计算、持久化 verdict/blockers/hash，四端只读服务端结论 |
| 正式材料资格事实 | REAL | 复用文件 Authority 与扫描状态，缺失/不安全文件阻断 |
| 缴费投影与人工核验同步 | REAL | 真实表、API、CAS、教师 PC 站内抽屉和负向测试 |
| 绿色通道提交与审批 | REAL | stable student_id、客户端幂等号、expected-version、回归测试 |
| 教师 PC | REAL | 真实 Chromium 登录、资格重算与缴费抽屉，无原生弹窗 |
| 学生 PC | REAL | 真实 Chromium 登录读取同一 verdict、blockers 和缴费投影 |
| 学生小程序 | REAL | 真实 API contract + production H5 build，无 mock fallback |
| 教师小程序 | REAL | 真实 API contract + production H5 build，审批使用 CAS |
| 外部支付 Provider 自动回调 | DISABLED | O4 只提供可信校内投影/人工同步，不显示虚假“已支付” |
| signed check-in token 与正式报到落档 | NOT_APPLICABLE | 属于 O5；O4 不继续使用 admissionNo 冒充安全令牌 |
