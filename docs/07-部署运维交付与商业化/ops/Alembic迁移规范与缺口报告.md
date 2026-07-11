# Alembic 迁移规范与缺口报告（P13-E）

> 本报告只做**检查与规范**，未改动任何现有迁移、未删除 `create_all`、未重写历史 migration。
> 生成方式：`backend` 目录运行 `python ../scripts/check/check-migration-coverage.py`。

## 一、检查结论（实测）

| 指标 | 数值 |
|---|---|
| ORM 模型注册表总数 | **71** |
| Alembic 迁移已覆盖（含 `create_table`）的表 | **0** |
| 未纳入迁移（疑似靠 `metadata.create_all` 建） | **71（全部）** |

**现状**：`backend/alembic/versions/` 下仅 `0001_init_core_tables.py` 一个迁移，且未以 `op.create_table('t_xxx')` 逐表声明；实际建表依赖启动时 `Base.metadata.create_all`。这意味着**生产环境改表没有版本化、无法安全回滚**——是本项目上生产前的**高优先级工程债**。

## 二、缺口清单（应纳入下一版迁移的表）

全部 71 张业务表当前均未版本化。重点新增/近期表（本轮 P13 引入）：
- `t_notification_template` / `t_notification_task` / `t_notification_log`（P13-B 通知中心）
- `t_teacher_student_scope`（教师数据范围）

其余覆盖六域、组织、RBAC、审批、文件、审计、平台等既有表（详见脚本输出）。

## 三、生产改表标准流程（建议落地，本轮不执行）

1. **切换为迁移驱动**：新环境初始化用 `alembic upgrade head`，逐步淘汰 `create_all`（先并存：`create_all` 仅兜底缺失表，正式改表一律走迁移）。
2. 生成基线迁移：对当前 71 表用 `alembic revision --autogenerate -m "baseline_all_tables"` 产出一版**基线**，人工核对后作为 head（注意：autogenerate 需连到与生产同构的库）。
3. 每次模型变更：`alembic revision --autogenerate -m "变更说明"` → **人工审阅生成的 upgrade/downgrade** → 提交。
4. 发布顺序：先备份库 → `alembic upgrade head` → 启动新版后端 → 冒烟检查。
5. 严禁在生产直接 `create_all` 或手改表结构。

## 四、回滚策略

- **优先数据备份回滚**：改表前必做全量备份（见《备份恢复演练手册》）；出问题优先恢复备份，而非 `downgrade`。
- **迁移级回滚**：仅对"纯结构、无数据破坏"的变更用 `alembic downgrade -1`；涉及删列/改类型的变更，downgrade 往往丢数据，须谨慎并先备份。
- 每个 migration 必须写**可用的 downgrade**；不可逆变更要在 PR 注释里显式标注"不可回滚，仅靠备份"。
- 发布前在**测试库**演练一次 upgrade + downgrade。

## 五、多租户表迁移注意事项

1. 本项目一期为**共享库 + 行级隔离**（`tenant_id`），迁移是**全租户同时生效**——一次 DDL 影响所有学校，务必先在测试库验证。
2. 加索引优先带 `tenant_id` 前缀（多租户查询几乎都带租户过滤），避免全表扫描。
3. 大表加列/加索引在生产要考虑**锁表时间**（MySQL 大表 online DDL / 低峰执行）。
4. 新增租户级表必须带 `tenant_id` 且建索引，遵循 `TenantMixin`。
5. 私有化（PRIVATE）部署将来可能一校一库，迁移需支持"对每个库分别 upgrade"——脚本化遍历，勿手工逐库。

## 六、下一步（排期建议）

- P13 之后单开一轮"**迁移基线化**"：产出 baseline 迁移 + 切换初始化流程 + 补 downgrade + 测试库演练。**此项属结构性改造，需独立分支 + 充分测试，不与业务改动混提。**
