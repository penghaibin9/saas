# O2 迎新流程版本与学生步骤 Authority 证据

- 阶段：O2
- 进入阶段 HEAD：`ed1a95111d9ef4ce154aa1f4d78a0ae0c7ebed1b`
- 同步核验 `origin/main`：`37e077cd452e3cbbbe7612cba4316d740cf871f6`，仍为当前分支祖先，divergence 为 `0 5`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_orientation_flow_o2`
- parent：`20260901_dorm_stay_alloc_d2`
- Fresh MySQL：MySQL 8.0 / `saas_o2_fresh`

## 阶段边界与权威切换

- 新增 `OrientationFlowVersion`、`OrientationFlowStep`、`OrientationStudentStep`；批次保存冻结的 `flow_version_id`。
- 流程草案 `t_orientation_flow_config` 仅用于未来批次发布新版本；与最新快照有差异时发布 V+1，不再决定已绑定批次/学生实例的运行步骤。
- `t_orientation_student_step` 是步骤状态唯一 Authority；允许状态严格为 `NOT_STARTED / IN_PROGRESS / BLOCKED / DONE / WAIVED / NOT_REQUIRED`。
- `steps_json` 仅由 Authority 派生为旧接口兼容投影。运行时读取若发现 Authority 缺失或版本链不一致会失败关闭，不回退读取 JSON。
- 新生创建、领域导入和所有正式种子在同一事务初始化 canonical 步骤；核验、绿色通道、材料、现场报到和入住按真实业务事实更新 canonical 行，再刷新投影。
- “人工已处理”不再直接写 `DONE`：必须有至少 5 字原因，写 `WAIVED`，并记录操作人、时间、审计行引用和来源业务引用。

## Expand → Backfill → Validate → Switch → Contract

- Preflight：在 MySQL 非事务 DDL 前校验批次租户链、旧流程配置和 `steps_json` 状态；未知状态或无证据旧 `WAIVED` 在任何 DDL 前失败。
- Expand：新增三张 O2 表和批次 `flow_version_id`，保留旧配置表与兼容 JSON 列。
- Backfill：每租户发布一个 `LEGACY_CONFIG_BACKFILL` 流程快照；显式映射 `TODO→NOT_STARTED`、`DOING→IN_PROGRESS`、`BLOCKED→BLOCKED`、`DONE→DONE`、`NOT_REQUIRED→NOT_REQUIRED`；停用且未开始步骤转 `NOT_REQUIRED`。
- Validate：批次/版本/流程步骤/学生步骤全链按稳定主键和租户校验，ACTIVE/CLOSED 批次不得缺流程版本，豁免不得缺操作人、原因和证据。
- Switch：管理端详情、进度、看板和学生移动端均只读 canonical 步骤；业务写入口只更新 canonical 后派生 JSON。
- Contract：MySQL CHECK 拒绝未知状态和无证据豁免；同一学生同一步骤唯一；已打开批次必须绑定流程版本。

## Fresh MySQL 迁移与演练

- 从真正空库执行完整不可变 Alembic 链到 D2，再升级 O2：通过。
- 在 D2 构造合法旧 ACTIVE 批次和旧学生投影：INFO/DONE 回填为 canonical DONE；停用 DORM/TODO 回填为 canonical NOT_REQUIRED。
- downgrade 到 D2 后三张 O2 表移除且旧学生仍存在；重新 upgrade O2：通过。
- 修复并复验降级顺序：先移除 ACTIVE 批次 CHECK，再清空/删除 `flow_version_id`，往返通过。
- 负向 preflight：把旧 INFO 状态改为 `MANUAL_DONE` 后升级在 DDL 前失败，O2 目标表数量仍为 0；恢复合法状态后升级成功。
- 最终 `alembic heads` 与 `alembic current` 均为唯一 `20260901_orientation_flow_o2 (head)`。
- Fresh 最终计数：flow version=1、flow step=2、student step=2、活动/已关闭批次缺版本=0、无证据豁免=0。

## Schema、漂移与回归

- O2 模型、MySQL 重复步骤/无证据豁免约束、迁移父链与安全回退：`3 passed`。
- 权威切换最终影响面：`70 passed`，覆盖 O2/O1/A1、迎新 CRUD 和业务闭环、真实 XLSX 导入导出、Data Scope、跨租户/同名隔离、宿舍初始化、学生影子回填与双读；最终重跑耗时 `690.16s`。
- 新增回归证明：canonical 初始化后即使直接篡改 `steps_json`，接口仍返回 canonical BLOCKED；人工豁免返回 WAIVED 且数据库存在完整审计证据。
- 冻结回归证明：草案停用 PAYMENT 后，旧 ACTIVE 批次仍绑定 V1 且 PAYMENT 保持启用；新批次启用时发布并绑定 V2，PAYMENT 按新草案停用。
- 全仓 `alembic check` 仍受进入本阶段前的历史 drift 影响而非零；对 O2 三张表、批次新增列、约束和索引过滤后的目标差异为 0。
- `py_compile` 与 `git diff --check`：通过。

## 跨端契约与构建

- 教师 PC 全量测试：`733/733 passed`；生产构建通过，3180 modules，官方站预渲染 21 条路由。
- 学生 PC 全量测试：`120/120 passed`；生产构建通过。
- 学生端 + 教师端小程序：`239/239 passed`；微信 release 构建通过，主包 483.4 KiB、总包 1.92 MiB、`budgetPass=true`。
- 上述前端在 O2 最终权威切换后没有源代码变化；最终后端 70 用例包含前端所依赖接口的响应契约。

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | O2 证据 |
|---|---|---|
| 流程版本与批次冻结 | REAL | 发布版、步骤快照、批次稳定主键绑定和 ACTIVE CHECK 均落 MySQL |
| 学生步骤 Authority | REAL | 运行读写只走 `t_orientation_student_step`；JSON 篡改回归通过 |
| 业务事实推进 | REAL | 核验、绿色通道、材料、报到、入住均更新 canonical 行 |
| 人工处理 | REAL | 仅允许带审计证据的 WAIVED，不可直接伪造 DONE |
| 旧 JSON 运行回退 | DISABLED | 权威不完整时 fail-closed，错误信息明确禁止回退 `steps_json` |
| 已打开批次改流程 | DISABLED | 批次冻结 `flow_version_id`；后续草案不改写已有实例 |
| O2 新页面 Chromium E2E | NOT_APPLICABLE | 本阶段无 UI 变更；O1 已完成相关页面真实浏览器验收，O2 跨端契约和构建均通过 |
| O4 材料资格/阻塞规则中心 | NOT_APPLICABLE | O2 只建立状态 Authority；复杂资格与规则解释按总册留到 O4 |
