# D3 宿舍分配计划与学生首次选床证据

- 阶段：D3
- 进入阶段 HEAD：`df7f6660bff136ff1b09c221a8e01955c3e37ea8`
- 同步核验 `origin/main`：`37e077cd452e3cbbbe7612cba4316d740cf871f6`，仍为当前分支祖先，进入提交前 divergence 为 `0 6`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_dorm_allocation_d3`
- parent：`20260901_orientation_flow_o2`
- Fresh MySQL：MySQL 8.0 / `saas_d3_fresh`

## 阶段边界与 Authority

- D3 复用 D2 的 `DormAllocationBatch / DormAllocationItem / DormStay` 和既有 `DormBuilding / DormRoom / DormBed`；没有新建学生、组织、审批、消息或文件 Authority。
- 分配模式为 `ADMIN_AUTO / ADMIN_MANUAL / STUDENT_SELECT / POST_CHECKIN_PUBLISH`。批次创建时冻结学生稳定主键和床位稳定主键；发布后只能读取冻结的 `resolvedBedIds`，后来在同房间新增床位不会扩大资源池。
- 强规则在服务端统一执行：性别兼容、房态可用、一生一床、同批次一床唯一、时间窗不重叠；民族、籍贯、宗教等敏感规则被显式拒绝。
- Dry Run 是发布前强制步骤。软规则真正参与排名：同班、同专业、同学院亲和，尽量减少空床并平衡楼层；冲突不会被伪装为成功。
- 自动分配、人工分配和学生自选均在事务内锁学生/床位并重查已有 ACTIVE/RESERVED `DormStay` 与占用床位。成功只写 `DormStay=RESERVED`、`DormBed=LOCKED`，不提前写正式入住或学生当前床位指针。
- 首次选床成功后同步 O2 `DORM` 步骤业务引用；正式入住、历史切换和退宿仍按总册留给 D4。
- `CsDormRecord` 与迎新住宿字符串继续只作兼容投影；旧全局 `selfSelectEnabled` 开关已从运行 Authority 退役。

## Expand → Validate → Switch → Contract

- Preflight：在 MySQL 非事务 DDL 前拒绝同批次重复床位提案和 `PUBLISHED` 但无 `published_at` 的批次。
- Expand：在既有 D2 表上增加发布时点 CHECK 和 `(tenant_id, allocation_batch_id, bed_id)` 唯一约束；不修改 frozen baseline。
- Backfill：D2 表在进入 D3 前尚无生产写入口，合法旧数据无需推断式回填；preflight 先证明可安全收紧。
- Validate：批次发布时重新验证冻结学生、冻结床位、批次模式、规则、Dry Run、冲突和真实学生链接；缺失迎新学生链接归类为 `DATA_MISSING`。
- Switch：教师 PC、教师小程序摘要、学生 PC、学生小程序均读取同一 D3 服务；旧全局开关不再决定自选资格。
- Contract：数据库唯一约束兜底同床冲突；服务事务与行锁负责一生多床、同床并发和资格重查；发布批次要求真实发布时间。

## Fresh MySQL 迁移与演练

- 从真正空库执行完整不可变 Alembic 链至 `20260901_dorm_allocation_d3 (head)`：通过。
- D3 → O2 → D3 downgrade/upgrade：通过；downgrade 会在存在 D3 运行数据时阻止不安全回退。
- 负向 preflight：在 O2 注入同批次同床的两条提案后，D3 upgrade 在 DDL 前以 `duplicate bed proposals` 拒绝；清理测试行后可重新升级。
- 最终 `alembic heads` 与 `alembic current` 均为唯一 `20260901_dorm_allocation_d3 (head)`。
- 目标约束存在：`ck_dorm_alloc_batch_publish_time`（CHECK）、`uk_dorm_alloc_item_bed`（UNIQUE）。
- Fresh 最终异常计数：同批次重复床位组=0，已发布但无发布时间=0。

## 后端、权限、并发与 XLSX

- 隔离 MySQL 回归：`12 passed, 39327 warnings in 293.76s`。
- 覆盖：Dry Run 强制、自动预留与 O2 联动、普通冲突和 `DATA_MISSING` XLSX、后续批次拒绝已预留学生、发布后精确床位冻结、学生访问管理列表 403、同床并发严格一成一败、报到前隐藏/报到后可见、旧全局开关失效，以及 D2/O2 约束回归。
- 权限与 Data Scope：管理 API 使用 `studentAffairs.dorm.allocation.manage`；教师摘要按既有组织/楼栋范围收敛；学生只解析本人稳定 `student_id`；无权限管理列表返回 403。
- 冲突导出是真实 XLSX，包含普通分配冲突和未链接迎新学生的 `DATA_MISSING` 行；响应设置 `no-store`、`nosniff` 和 UTF-8 文件名，并记录审计。
- `py_compile` 与 `git diff --check`：通过。Ruff 未安装（`No module named ruff`），不是产品运行或测试失败。

## 四端契约、构建与 Chromium

- 教师 PC 全量测试：`735/735 passed`；生产构建通过（3182 modules，仅既有 CSS import/chunk warning）。
- 学生 PC 全量测试：`122/122 passed`；生产构建通过。
- 学生端 + 教师端小程序：`241/241 passed`；微信 release/budget 构建通过。
- 教师 PC Chromium：临时 Fresh-schema 鉴权库、`MOCK_LOGIN_ENABLED=false`、真实 `/auth/browser-login`；进入 `/admin/student-affairs/dorm/allocation`，真实显示“分配计划”、Dry Run 说明、发布前强校验、“新建分配批次”和空批次状态。
- 学生 PC Chromium：真实 STUDENT 账号和 ACTIVE `StudentAccountLink` 登录；进入 `/portal/campus-service?tab=dorm`，真实返回“当前没有可用的学生自选住宿批次，请按学校安排等待分配”，没有虚构可选床位或成功态。
- Chromium 临时库仅创建租户/用户/角色模板/学生身份绑定；验证前 `t_affairs_dorm_allocation_batch=0`，未直接插入任何分配业务中间结果。验证完成后开发服务已停止，临时库 `saas_d3_e2e` 已删除；Fresh 验收库 `saas_d3_fresh` 保留。

## Migration drift

- 全仓 `alembic check` 仍受进入 D3 前的历史 comment/index 命名 drift 影响而非零。
- 对 D3 目标表、约束和索引过滤后的自动生成差异为 `D3_TARGET_DRIFT_MATCHES=0`；本阶段没有通过改历史 migration 或 merge revision 掩盖 drift。

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | D3 证据 |
|---|---|---|
| 教师创建/查看分配批次 | REAL | 管理 API、教师 PC 页面、权限门禁、空态 Chromium 均通过 |
| Dry Run 与强/软规则 | REAL | 发布强制先预检；敏感规则拒绝；排序和冲突回归通过 |
| 管理员自动/人工预留 | REAL | 事务锁、RESERVED stay、LOCKED bed、O2 步骤联动均由 MySQL 回归证明 |
| 学生首次选床 | REAL | 学生 PC/小程序共用真实 API；同床并发一成一败；无批次明确禁用 |
| 发布后资源冻结 | REAL | 只认冻结 `resolvedBedIds`；同房间后来新增床位不可见 |
| 报到前隐藏/报到后展示 | REAL | `POST_CHECKIN_PUBLISH` 正反向接口测试通过 |
| 冲突 XLSX | REAL | 普通冲突 + `DATA_MISSING`、审计、安全响应头测试通过 |
| 旧全局学生自选开关 | DISABLED | 教师 PC 已移除；旧 API 写入返回明确 400；移动端不再读取其 Authority |
| 无发布批次时首次选床 | DISABLED | 真实学生 Chromium 明确提示等待学校安排，不展示假床位或假成功 |
| 正式入住、历史写入和退宿 | NOT_APPLICABLE | D3 只形成预留；按施工总册在 D4 切换 canonical `DormStay` 历史 Authority |
| 归寝 Provider 与晚归联动 | NOT_APPLICABLE | 按施工总册留到 D5/D6，不生成任何假门禁事件 |
