from pathlib import Path

path = Path("docs/06-开发施工与质量验收/施工记录/2026-08-16-教务C线-CW1-INT迁移与数据治理交接.md")
text = path.read_text(encoding="utf-8")

old = '''## 2. Published Occurrence 依赖\n\nC 不自行定义正式课次 Authority。\n\n最终 occurrence identity 必须消费 B-C1 Published Schedule Contract（B-W2 冻结后）：\n\n`term + ScopeHead active batch + TeachingTask + effective ScheduleItem + ScheduleChange + calendar/week/parity`\n\nB-C1 未冻结时，INT/C 都不得用课程名、行政班、日期+节次自由拼接成“正式课次”。\n'''
new = '''## 2. Published Occurrence 依赖\n\nC 不自行定义正式课次 Authority。B-C1 Published Schedule Contract 已冻结并被 C-W1 正式消费。\n\n当前普通课堂 occurrence 解析固定为：\n\n`term + ScopeHead active batch + TeachingTask + EFFECTIVE ScheduleItem + APPLIED ScheduleChange + calendar/week/parity`\n\nC-W1 已落实以下 fail-closed 语义：\n\n- 只认当前 `ScopeHead.active_batch_id` 指向的 `PUBLISHED` 批次，不回退历史 EFFECTIVE 行；\n- SCHOOL / COLLEGE ScopeHead 指向同一 active batch 时按同一 Authority 去重；同一 TeachingTask 同时落入不同 current active batch 时视为冲突；\n- 只认 `EFFECTIVE ScheduleItem`；调课旧 `CHANGED` occurrence 拒绝；\n- 带 `change_id` 的新课次必须回链同租户 `AaScheduleChange(status=APPLIED)`，且 `new_item_id / task_id / batch_id` 一致；\n- `HOLIDAY` 拒绝普通点名；`SWAP` 原停课日拒绝，补课日映射到原教学日计算 week/weekday；\n- `ODD / EVEN / ALL` 周次规则在服务端实时判定；\n- 客户端可携带 `scheduleItemId` 作为 optimistic occurrence identity；实时 resolver 命中不同 item 时返回 409，不静默漂移。\n\n任何历史治理/迁移都不得用课程名、行政班、教师名或裸 `日期+节次` 自由拼接替代上述正式课次 Authority。\n'''
if text.count(old) != 1:
    raise SystemExit(f"published occurrence section anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''6. 普通课堂唯一性：同租户 + canonical occurrence identity 只能有一个有效考勤场次；并发重复创建只能单赢家或幂等命中同一事实。\n7. 归档/软删语义必须与现有 archive guard 一致，禁止通过删除旧行再重建来绕唯一性历史。\n'''
new = '''6. 普通课堂唯一性：同租户 + canonical occurrence identity 只能有一个有效考勤场次；并发重复创建只能单赢家或幂等命中同一事实。当前 C-W1 应用层已在持有正式课次 Authority 锁后，对 `tenant + class + teacher + actual sessionDate + slot` 做 current locking read，MySQL 并发合同已证明单赢家；这只是 DB UNIQUE 落地前的应用层保护，**不得替代最终数据库约束**。\n7. occurrence 冻结建议同时保存/可追溯以下证据：`scheduleItemId`、`teachingTaskId`、`activeBatchId`、`scopeType/scopeId/scopeHeadVersion`、actual `sessionDate`、calendar logical date、`calendarSource/calendarEventId`、`weekNo/weekday/slotNo/weekParity`、`changeId/changeType/changeAppliedAt`。\n8. 归档/软删语义必须与现有 archive guard 一致，禁止通过删除旧行再重建来绕唯一性历史。\n'''
if text.count(old) != 1:
    raise SystemExit(f"migration uniqueness section anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''## 5. 并发与 MySQL Gate\n\nB-C1 到位后，C/INT 联合 MySQL 必须覆盖：\n\n- 两个教师/管理员并发为同 occurrence 创建普通场次 → 单一正式事实；\n- occurrence 正在因调停课换版时创建 → stale occurrence 409，不能冻结旧课次；\n- Roster 换版与场次创建并发 → 继续沿现有 TeachingClass → current RosterVersion 锁序；\n- ADMIN_SPECIAL 不得占用/冲突正式 occurrence identity；\n- duplicate retry 明确幂等还是 409，不能随机 500/IntegrityError 泄漏。\n'''
new = '''## 5. 并发与 MySQL Gate\n\nC-W1 已完成的应用层/MySQL 证据：\n\n- 同一正式 occurrence 双事务并发创建 → current locking read 单赢家，另一请求 409；\n- 调停课新 occurrence 必须 `APPLIED` 且 change→item 回链一致；旧 `CHANGED` occurrence 不可继续创建；\n- stale `scheduleItemId` 与实时 resolver 命中不一致 → 409，并返回 expected/resolved item evidence；\n- ADMIN_SPECIAL 仍是独立审计来源，不占用正式 occurrence duplicate guard；\n- Roster 继续消费 versioned TeachingRoster 并冻结 `RosterConsumerSnapshot`。\n\nINT 落数据库约束时仍必须补齐/重放：\n\n- canonical `occurrence_identity` 的 tenant-scoped UNIQUE / active-fact 约束；\n- duplicate retry 明确选择幂等命中还是稳定 409，不能泄漏随机 500/IntegrityError；\n- 与 Roster 换版、Schedule publish/change finalizer 的锁序/死锁回归；\n- dirty-data/backfill 后再收紧 NOT NULL/CHECK/UNIQUE，禁止迁移脚本静默删重。\n'''
if text.count(old) != 1:
    raise SystemExit(f"mysql gate section anchor count={text.count(old)}")
text = text.replace(old, new, 1)

old = '''- B-C1 Published Schedule Contract = FROZEN；\n- C-C1 Attendance Consumer Contract 至少进入可实现状态；\n'''
new = '''- B-C1 Published Schedule Contract = FROZEN（当前已满足）；\n- C-C1 Attendance Consumer Contract = FROZEN 后再由 INT 接手 schema 落地；\n'''
if text.count(old) != 1:
    raise SystemExit(f"INT receive condition anchor count={text.count(old)}")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
