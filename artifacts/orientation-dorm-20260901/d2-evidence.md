# D2 DormStay + Allocation Batch Schema 证据

- 阶段：D2
- 进入阶段 HEAD：`445b60c5c7826d2ed5148678fc863809809eb097`
- 同步核验 `origin/main`：`37e077cd452e3cbbbe7612cba4316d740cf871f6`，仍为当前分支祖先且无新公共 Schema 变更
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_dorm_stay_alloc_d2`
- parent：`20260901_orientation_batch_o1`
- Fresh MySQL：MySQL 8.0 / `saas_d2_fresh`

## 阶段边界

D2 只交付总册规定的第二个 Schema 包：`DormStay`、`DormAllocationBatch`、`DormAllocationItem`。保留 `DormBuilding / DormRoom / DormBed`、调宿工作流和 `CsDormRecord` 兼容投影，不提前实现 D3 的分配四端或 D4 的历史写入切换。

## Expand → Backfill → Validate → Switch → Contract

- Expand：新增 `t_affairs_dorm_stay`、`t_affairs_dorm_allocation_batch`、`t_affairs_dorm_allocation_item`，未改 frozen baseline、未删除旧表。
- Preflight：在 MySQL 非事务 DDL 前只读检查 OCCUPIED 床位的同租户学生/楼/房/床链和“一生最多一张当前床”；冲突在创建新表前失败，不猜测。
- Backfill：只从同租户稳定 `DormBed → DormRoom → DormBuilding → StudentProfile` 链生成 ACTIVE `DormStay`，来源固定为 `DORM_BED_BACKFILL + bed_id`。
- Validate：迁移内校验占用数等于回填数、住宿链无断裂、ACTIVE 学生和床位均无重复。
- Switch：ORM 注册三张 canonical 表；现有当前占用继续以 `DormBed.student_id` 为 Authority。D3/D4 前没有开放新表写 API。
- Contract：批次必须有 `open_at < close_at`；mode/status/item status 由 MySQL CHECK 约束；同租户批次号唯一、同批次同学生分配项唯一；来源住宿事实唯一。

## Fresh MySQL 迁移与回填

- 从真正空库执行完整不可变历史链到 O1：通过。
- 在 O1 插入一条稳定主键旧占用事实（学生、楼、房、床均为同租户），升级 D2 后生成且只生成一条 ACTIVE `DormStay`。
- 回填结果：`CURRENT_OCCUPANCY / DORM_BED_BACKFILL / source_biz_id=bed_id`，`checkin_at` 保留旧床位占用时间。
- D2 downgrade 到 O1：三张 D2 表移除，旧 OCCUPIED 床位仍存在；随后重新 upgrade 到 D2：通过。
- 降级保护：若已有 allocation batch/item 或非 backfill stay，迁移拒绝删除，避免静默丢失 D3/D4 业务数据。
- 最终 `alembic current` 与 `alembic heads`：唯一 `20260901_dorm_stay_alloc_d2 (head)`。

## Schema 反射

- 三张表均存在；tenant、业务复合索引和三个唯一约束均与 ORM 一致。
- CHECK：`ck_dorm_alloc_batch_window`、`ck_dorm_alloc_batch_mode`、`ck_dorm_alloc_batch_status`、`ck_dorm_alloc_item_status` 均存在。
- Fresh 数据一致性：`invalid_stay_chain=0`、`duplicate_active_student=0`、`duplicate_active_bed=0`。
- 全仓 `alembic check` 仍受进入 D2 前的历史 drift 影响而非零；按三张 D2 表、约束和索引过滤的自动生成差异为 0。

## 精准测试

- D2 模型、MySQL 约束、迁移单父链与安全降级：`3 passed`。
- D2 preflight 加固后模型/迁移静态复验：`2 passed`，Fresh downgrade/upgrade 再次通过。
- 既有宿舍权威/权限/Data Scope 回归：`10 passed`，覆盖占用与性别冲突、DORM_BUILDING 范围、跨楼写入拒绝、节点审批与真实宿管角色绑定。
- 教师 PC 宿舍相关契约：`26/26 passed`。
- 学生 PC 全量契约：`120/120 passed`。
- 学生端 + 教师端小程序全量契约：`239/239 passed`。

## 构建

- 教师 PC 生产构建：通过；官方站预渲染 21 条路由。既有 CSS `@import` 与大 chunk 警告不影响产物。
- 学生 PC 生产构建：通过。
- 微信小程序 release 构建：通过；预算通过，主包 494,972 bytes，总包 2,011,797 bytes。

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | D2 证据 |
|---|---|---|
| DormBed 当前占用 | REAL | 旧 Authority 保留；旧占用回归与 DORM_BUILDING Data Scope 通过 |
| DormStay Schema 与稳定回填 | REAL | Fresh MySQL 真实回填、反射、一致性和往返通过 |
| Allocation Batch Schema | REAL | 时间窗、模式、状态、唯一性均由 MySQL 约束 |
| Allocation API / 教师 PC | NOT_APPLICABLE | 总册规定在 D3 开放；D2 没有可点击但未接通的按钮 |
| 学生 PC / 学生小程序选床 | NOT_APPLICABLE | 总册规定在 D3 开放 |
| DormStay 入住/调宿/退宿实时历史写入 | NOT_APPLICABLE | 总册规定在 D4 切换，当前不会伪称已双写 |
| 名称/字符串住宿回填 | DISABLED | `CsDormRecord` 不参与 canonical 回填，不按楼名/房号猜稳定 ID |
| 私有审批/消息/文件框架 | DISABLED | 继续复用现有统一底座，不新增第二套引擎 |
| D2 Chromium 新页面 E2E | NOT_APPLICABLE | 本阶段无 UI 变更；相关四端契约和所有生产构建已通过 |
