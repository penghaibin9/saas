# O1 迎新批次 Authority 与组织主键落库证据

- 阶段：O1
- 进入阶段 HEAD：`306dabcdbc27fd8abd935fe2fb04a00dc5be16a0`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_orientation_batch_o1`
- parent：`20260831_iam_alias_backfill`
- 数据库：隔离的 Fresh MySQL 8.0（`saas_o1_fresh`、`saas_a1_test`）
- 口径：本文件只记录 O1 实现和可复验结果，不把种子或浏览器夹具当作 Golden Journey 业务证据。

## 权威模型

- `t_orientation_student.batch_id` 为非空稳定批次主键，且与记录租户一致。
- `college_id / major_id / class_id` 只接收同租户稳定主键；学院、专业、班级名称仅作快照展示，不参与自动猜测。
- `source_type + source_record_id` 标识批次内来源，`uk_ori_batch_source_record` 防止同批次重复来源。
- `identity_status` 只取 `UNLINKED / LINKED`，并严格按 `student_id` 是否存在判定。
- 旧字符串班级引用保留为只读 `class_ref_legacy`；无法唯一解析的行写入 `t_orientation_o1_backfill_issue`，不按名称猜测。
- 列表、创建、更新、领域导入与领域导出共用批次、组织主键、来源和 dataScope 约束。

## Fresh MySQL 迁移

- 从空库执行完整不可变 Alembic 链到 O1：通过。
- `alembic current`：`20260901_orientation_batch_o1 (head)`。
- `alembic heads`：唯一 head `20260901_orientation_batch_o1 (head)`。
- 在 `saas_o1_fresh` 和 `saas_a1_test` 上执行 O1 downgrade/upgrade 往返：通过。
- 反射确认新列类型、非空约束、注释、`ix_ori_student_batch_active`、`ix_ori_student_org_active`、`uk_ori_batch_source_record` 及 issue 表均存在。

## 旧数据回填演练

- 在 O1 前一版本构造同租户稳定组织链、可由 `StudentProfile` 唯一关联的旧迎新记录、以及无法解析的旧班级引用。
- 可解析行：回填稳定学院/专业/班级主键，保留旧引用，来源为 `LEGACY_BACKFILL`，身份为 `LINKED`。
- 不可解析行：组织主键保持空，旧引用保留，身份为 `UNLINKED`，issue 为 `CLASS_REF_UNRESOLVED`。
- 批次缺失、跨租户批次、跨租户/断裂组织链、来源缺失、来源重复、身份状态矛盾的最终校验计数：0。

## 测试与构建

- 后端 O1 精选 Fresh MySQL 复验：`9 passed`。
- A1 真实 XLSX 链复验：模板 → 文件 dry-run → confirm → list → 按批次导出 → 下载工作簿通过；无关宿舍角色返回 403。
- 创建/作废迎新记录回归：`1 passed`。
- 教师 PC 全量测试：`733/733 passed`；生产构建及 21 条官方路由预渲染通过。
- 学生 PC：`120/120 passed`；生产构建通过。
- 学生端 + 教师端小程序：`239/239 passed`；微信生产构建和分包预算检查通过（主包 0.47 MiB、总包 1.92 MiB）。
- O1/A1 定向前端契约：`9 passed`；变更范围 ESLint：通过。

## Chromium 页面验收

- 使用隔离 Fresh MySQL 临时账号完成真实密码登录；账号在验收后已删除，口令未写入仓库。
- 打开教师 PC `/admin/orientation/students`，真实请求 `/api/v1/orientation/batches` 与 `/api/v1/orientation/students?batchId=1` 均返回 200。
- ACTIVE 批次 `ORI-HOMONYM` 默认选中，列表按 `batchId=1` 查询并显示 1 条本租户记录。
- 在已选批次状态点击“导出报到台账”，成功打开审计确认对话框；对话框明确服务端按当前账号 dataScope 导出并写水印。
- 切换到“全部”后再次点击导出，页面不打开导出对话框，并提示“请先在筛选条件中选择一个迎新批次，再导出该批次台账”。

## 能力矩阵

| 面 | 状态 | O1 结论 |
|---|---|---|
| Backend / MySQL | REAL | 批次、稳定组织主键、来源、身份状态和迁移/回填校验均落库 |
| 教师 PC | REAL | 批次筛选、默认 ACTIVE 批次、单批次导出门禁已接真实 API |
| 学生 PC | N/A | O1 不新增学生端批次管理入口；既有端全量测试与构建通过 |
| 教师小程序 | N/A | O1 不新增移动端批次管理入口；既有端测试与生产构建通过 |
| 学生小程序 | N/A | O1 不新增移动端批次管理入口；既有端测试与生产构建通过 |
| 跨批次导出 | DISABLED | 未选择单一批次时前端和后端均拒绝 |
| 名称猜组织 | DISABLED | 运行链仅接受稳定 code/id 唯一解析；旧数据歧义进入 issue 表 |

## 已知仓库债务

全仓 `alembic check` 仍会报告 O1 进入前已存在的大量模型/历史迁移漂移。对自动生成差异按迎新表过滤后，O1 相关差异为 0；本阶段没有把全仓历史漂移误写进 O1 migration，也没有伪称全仓 drift 已清零。
