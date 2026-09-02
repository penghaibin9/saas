# A0 — Orientation/Dorm 数据一致性只读检查计划

## 1. 适用范围与当前执行状态

本文件定义后续每个阶段在 MySQL 上必须执行的只读一致性检查、判定阈值和修复归属。A0 未获得生产/试点库连接目标，也不把机器上未知来源的现存容器当作 `origin/main @ 37e077cd…` 的权威数据集，因此本阶段实数计数为 **NOT_APPLICABLE**，没有对任何业务库执行写入、回填或“顺手修复”。

后续验证必须使用两类库：

1. 每个 Schema 包独占的 Fresh MySQL 8 数据库：只运行 Alembic chain，不先 `metadata.create_all()`。
2. 经用户明确指定的存量库只读副本：运行本计划并保存脱敏结果；任何修复另开 migration/repair 包。

所有 SQL 都必须绑定明确 `tenant_id`；禁止把缺少 tenant 条件的全库结果当作业务结论。

## 2. 统一判定

| 级别 | 条件 | Gate |
|---|---|---|
| GREEN | orphan/跨租户/一生多床/重复 active 记录均为 0，projection 漂移为 0 | 可进入下一阶段 |
| AMBER | 仅存在可解释的旧 projection 漂移，Authority 完整且有确定回填方案 | 阻断发布，不阻断编写修复 migration |
| RED | 跨租户、Authority orphan、一生多床、重复消费报到码、未知 scope 放大 | 立即停止后续 Schema 串行 |

输出不得包含姓名、身份证号、手机号、文件 URL、token。只保存 tenant、记录 ID、计数和 hash/掩码后的业务键。

## 3. Schema/Alembic 检查

每个 Schema 包必须保存：

```text
git rev-parse HEAD
alembic -c alembic.ini heads
alembic -c alembic.ini history --verbose
alembic -c alembic.ini upgrade head
alembic -c alembic.ini current
alembic -c alembic.ini downgrade <previous_revision>
alembic -c alembic.ini upgrade head
```

并比较：

- Fresh MySQL 纯迁移后的 `information_schema.columns/statistics/table_constraints` 快照。
- `Base.metadata` 预期快照。
- 升级前存量快照与升级后快照。
- 第二次运行升级/回填时 affected rows 必须为 0 或与显式幂等口径一致。

特别防线：`0001_init_core_tables` 使用当前 ORM metadata 活基线。任何新模型/列都必须有显式 revision；不能因为 Fresh upgrade 最终出现该列，就认定迁移完整。验证脚本必须证明目标列由本包 revision 创建/变更，并能从 previous revision 升级得到。

## 4. 全校 Authority 检查

### 4.1 租户边界

对所有 orientation/dorm 外键关系执行同租户反连接。示例：

```sql
SELECT COUNT(*) AS cross_tenant_student
FROM t_orientation_student o
JOIN t_student_profile s ON s.id = o.student_id
WHERE o.student_id IS NOT NULL
  AND o.tenant_id <> s.tenant_id;

SELECT COUNT(*) AS cross_tenant_bed_student
FROM t_affairs_dorm_bed b
JOIN t_student_profile s ON s.id = b.student_id
WHERE b.student_id IS NOT NULL
  AND b.tenant_id <> s.tenant_id;
```

期望均为 0。后续新增 batch/stay/allocation/token/waiver/file binding/workflow 外键时，同步加入同租户检查。

### 4.2 学生主档与账号

```sql
SELECT tenant_id, student_no, COUNT(*) c
FROM t_student_profile
WHERE is_deleted = 0
GROUP BY tenant_id, student_no
HAVING c > 1;

SELECT tenant_id, student_id, COUNT(*) c
FROM t_student_account_link
WHERE is_deleted = 0 AND status = 'ACTIVE'
GROUP BY tenant_id, student_id
HAVING c > 1;

SELECT tenant_id, user_id, COUNT(*) c
FROM t_student_account_link
WHERE is_deleted = 0 AND status = 'ACTIVE'
GROUP BY tenant_id, user_id
HAVING c > 1;
```

期望 0 行。禁止用姓名相等替代账号/学生链接。

### 4.3 组织稳定 ID

O1 迁移前统计：迎新记录能否通过租户内唯一组织 code/显式映射绑定；不得用模糊名称自动确认。

```sql
SELECT tenant_id, class_id, COUNT(*) c
FROM t_orientation_student
WHERE is_deleted = 0 AND class_id IS NOT NULL
GROUP BY tenant_id, class_id;
```

当前 `class_id` 是字符串，以上仅用于盘点，不是稳定关联证明。O1 后必须以 bigint FK/稳定 ID 做 orphan 与跨租户检查；无法唯一映射的记录进入 staging error，不得静默猜测。

## 5. Orientation 一致性检查

### 5.1 名单唯一性与批次

```sql
SELECT tenant_id, admission_no, COUNT(*) c
FROM t_orientation_student
WHERE is_deleted = 0
GROUP BY tenant_id, admission_no
HAVING c > 1;
```

O1 后增加：

- active orientation row 必须有合法 `batch_id`。
- `batch_id` 与 orientation row 同 tenant。
- 锁定/发布批次不得再被普通名单写入。
- 同一批次+同一来源业务键幂等导入，不得生成第二个 StudentProfile。
- source/source_record_id 唯一且可审计；source 为人工时必须有 actor/audit。

### 5.2 主档链接

```sql
SELECT COUNT(*) orphan_profile
FROM t_orientation_student o
LEFT JOIN t_student_profile s
  ON s.id = o.student_id AND s.tenant_id = o.tenant_id AND s.is_deleted = 0
WHERE o.is_deleted = 0 AND o.student_id IS NOT NULL AND s.id IS NULL;
```

期望 0。无 `student_id` 的记录按批次/source 分类，不能以姓名自动补链。

### 5.3 资格、步骤与事实

当前 `steps_json` 不能直接用 SQL JSON 值认定业务完成。O2/O4 后建立逐项检查：

- MATERIAL DONE 必须存在有效、未删除、扫描通过且绑定正确 owner 的 FileBinding/材料记录。
- PAYMENT DONE 必须来自明确支付/绿色通道决策；“已申请”不等于“已通过”。
- DORM DONE 必须有同租户 current DormStay/Bed，而不是仅有 building/room 字符串。
- CHECKIN DONE 必须有成功 token consumption/checkin event。
- WAIVED 必须有 waiver actor、reason、evidence、timestamp；不得写成 DONE。
- overall verdict 必须可由以上事实重算，重算差异为 0。

### 5.4 报到码与并发

O3 后执行：

- token hash 唯一，明文不得落库。
- expired/revoked token 不得消费。
- 同 token 成功消费次数 ≤ 1；重复请求返回同一业务结果而不是第二条事件。
- 同 orientation/student 同批次最终 CHECKED_IN 事件仅一条 active/final。
- 100/500 并发消费测试后成功业务写入数为 1，其他为幂等成功或明确冲突。

### 5.5 导入/导出

- validate batch 与 confirm batch 同 tenant、同上传文件 hash、同 actor 权限上下文。
- confirm 后成功+失败+跳过=总行数。
- duplicate admission/source key 不得产生双记录。
- ExportTask 的 scope snapshot 与调用者 current-context 相符。
- 导出行集合必须是同一 scoped list query 的子集；不能用 tenant-only service 重查。
- xlsx 首行水印、公式转义、用途、审计记录和文件绑定齐全。

## 6. Dorm 一致性检查

### 6.1 当前一生一床

```sql
SELECT tenant_id, student_id, COUNT(*) c
FROM t_affairs_dorm_bed
WHERE is_deleted = 0 AND status = 'OCCUPIED' AND student_id IS NOT NULL
GROUP BY tenant_id, student_id
HAVING c > 1;

SELECT tenant_id, room_id, bed_no, COUNT(*) c
FROM t_affairs_dorm_bed
WHERE is_deleted = 0
GROUP BY tenant_id, room_id, bed_no
HAVING c > 1;
```

期望 0 行。还要检查 `status='OCCUPIED'` 必须有 student_id，`status='VACANT'` 必须没有 student_id；LOCKED 的允许组合由状态机显式定义。

### 6.2 房源层级同租户

```sql
SELECT COUNT(*) cross_tenant_room
FROM t_affairs_dorm_room r
JOIN t_affairs_dorm_building b ON b.id = r.building_id
WHERE r.tenant_id <> b.tenant_id;

SELECT COUNT(*) cross_tenant_bed
FROM t_affairs_dorm_bed d
JOIN t_affairs_dorm_room r ON r.id = d.room_id
JOIN t_affairs_dorm_building b ON b.id = d.building_id
WHERE d.tenant_id <> r.tenant_id
   OR d.tenant_id <> b.tenant_id
   OR r.building_id <> b.id;
```

期望均为 0。

### 6.3 DormStay（D2 后）

- 每生最多一条 `is_current=1`/ACTIVE stay，数据库唯一约束和并发测试同时证明。
- current stay 的 bed 必须 OCCUPIED 且 student_id 相同。
- 非 current stay 必须有 end_at/end_reason；时间区间不得重叠。
- 调宿必须在同一事务终结旧 stay、创建新 stay、切换床位；任意失败全部回滚。
- 退宿必须终结 stay、释放床位并产生审计/生命周期事件。

### 6.4 Allocation Batch（D2/D3 后）

- batch/item/rule 同 tenant；item 的 student/bed 同 tenant。
- 同批次同学生最多一条有效分配，同床最多一条有效分配。
- 发布前可重算，发布后版本锁定；撤回必须有规则和审计。
- 性别、楼栋限制、学院/班级/特殊需求规则由服务端验证。
- 100/500 并发发布/抢床后不超容量、不双床、不跨租户。

### 6.5 调宿与退宿

- 同学生进行中调宿最多一条。
- transfer.from_bed/to_bed 与学生/tenant 一致。
- 到达宿管节点时目标楼栋必须在 assignee 的 DORM_BUILDING 范围。
- 审批期间目标床被占：明确 409，不释放旧床，不写 EXECUTED。
- 学生提交/撤回永远不得直接释放旧床。
- WorkflowInstance/Task、UnifiedTodo 与 transfer 当前节点一致，孤儿数为 0。

### 6.6 检查、异常与风险

- check task/record/room/building 同 tenant。
- 夜不归宿/晚归事件必须绑定真实 student_id；禁止 student_id=0。
- provider status=UNAVAILABLE/ERROR 只能记录供应商不可用，不能生成“未归”事实。
- exception 关联 risk 时 tenant/student/source_ref 全部一致。
- 宿管只能读取/处理负责楼栋；无法解析范围必须 403/空，而不是 tenant 全量。

### 6.7 旧 projection 漂移

当前 `t_cs_dorm_record` 是兼容 projection。D2 后以 DormStay+DormBed 重建并比较：

- IN 记录必须对应 current stay 和 occupied bed。
- building/room/bed 字符串必须等于当前房源名称/编号。
- 已退宿不得仍为 IN。
- 漂移报告只列 ID/计数；修复通过可重放 projection job，不反写 Authority。

迎新宿舍 projection 同理：`OrientationStudent` 的 building/room/dorm_status 必须来自 current stay/正式分配，不得由普通 update 独立写入。

## 7. 权限与 Data Scope 数据检查

- permission code 统一后，检查 active RolePermission 不再依赖未注册的 legacy code。
- 每个宿管 active UserRole 必须有稳定 DORM_BUILDING scope 或稳定 manager user_id 关联；不允许只靠姓名。
- 重复 active scope、跨租户 ref_id、指向删除楼栋/班级/学生的 scope 均为 0。
- SCHOOL/COLLEGE/MAJOR/CLASS/STUDENT/DORM_BUILDING 每种范围分别做 allow/deny 对照；未知类型必须 deny。
- 导出、统计、搜索、详情和写动作使用同一范围边界，不能“列表收敛但详情/导出越权”。

## 8. 每阶段必须留存的脱敏证据

```text
exact-head.txt
alembic-heads.txt
fresh-mysql-upgrade.log
schema-snapshot-before.json
schema-snapshot-after.json
migration-drift.txt
consistency-counts.csv
tenant-scope-deny-cases.json
concurrency-summary.json
four-end-action-matrix.csv
test-results.txt
build-results.txt
```

其中 `consistency-counts.csv` 至少包含：check_id、tenant_id、count、expected、result、query_version、head；不得包含个人敏感字段。

## 9. A0 基线状态

| 检查 | 当前状态 | 说明 |
|---|---|---|
| exact head | GREEN | `37e077cd452e3cbbbe7612cba4316d740cf871f6` |
| Alembic head count | GREEN | 1 个：`20260831_iam_alias_backfill` |
| static Authority map | GREEN | 已完成，见 authority audit/matrix |
| Fresh MySQL data counts | NOT_APPLICABLE | A0 不改 Schema，未指定独占数据集 |
| production/clone consistency counts | NOT_APPLICABLE | 未提供经授权目标 |
| orientation Golden Journey | RED/DEFERRED | 当前测试不覆盖，从 O1—O5 修复 |
| dorm Golden Journey | RED/DEFERRED | 当前测试不覆盖，从 D1—D6 修复 |

A0 之后任何阶段若不能给出相应 GREEN 证据，不得用文档声称“生产级完成”。
