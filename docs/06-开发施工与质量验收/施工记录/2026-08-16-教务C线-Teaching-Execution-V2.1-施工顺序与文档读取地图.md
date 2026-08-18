# 教务 C 线 Teaching Execution V2.1 — 当前代码收口地图

> 固定分支：`agent/academic-c-teaching-execution`  
> PR：`#148`  
> Authority：`C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md`  
> 收口审计基线：`main@7fcf4f911e5ae8827c13e532e13c61676318b343`  
> 本次原子收口前 HEAD：`1949036b9e79b3d9ef037c692f1907d0caf65542`  
> 规则：本文件不再把“自身 commit SHA”写成永久 Gold。最终状态只认 PR 当前 exact HEAD 上的同头门禁；旧 run 仅保留为历史证据，禁止据此重复施工。

## 1. 当前结论

C 线的业务施工已经进入**合并前收口**，不是 W2/W3/W4 重做阶段。

| Wave | 当前代码事实 | 收口状态 |
|---|---|---|
| C-W0 Mature Chain Freeze | Attendance / Exam / Grade / EffectiveGrade / Correction-Recheck 成熟 Authority 均保留；本次修复 W0 Gate 的过期路径与迁移边界，并锁“考勤单一事务 Owner” | `IMPLEMENTED / SAME_HEAD_REVALIDATING` |
| C-W1 Published Occurrence + Attendance | 已消费 ScopeHead 正式课表、调停课 APPLIED 事实、TeachingRoster；ADMIN_SPECIAL 独立；考勤来源/课次/TeachingTask 已持久化 | `IMPLEMENTED / C-C1 FROZEN / SAME_HEAD_REVALIDATING` |
| C-W2 Teacher Today | 只读聚合今日课、正式名单、点名入口、调课变化、监考、成绩待办；PC/小程序复用正式事实 | `IMPLEMENTED` |
| C-W3 Exam | 正式名单/发布门禁不重写；正式打印、监考工作台、异常闭环、学生考试读取已接入 | `IMPLEMENTED` |
| C-W4 Grade | SQL 分页、deadline/延期/逾期、催录、退回重提、Path XLSX、工作量/教师关系 Authority 已落 | `IMPLEMENTED` |
| C-W5 C Gold | 可执行 E2E 资产已覆盖课表/调课、正式考勤 mark+submit、监考、录分、学院退回、教师重提、发布、PC/小程序成绩回读与登录隔离；本次把这些资产纳入 Final closure contract | `IMPLEMENTED / SAME_HEAD_REVALIDATING` |

**剩余不是继续加业务代码，而是：当前新 HEAD 的 W0、C-Final、Main required gate 同头跑绿后合并。**

## 2. 本次审计发现并关闭的重复施工根因

### 2.1 考勤存在两套 create_session 事务 — 已裁决为单一 Owner

旧状态：

- `academic_affairs_attendance_public_service.py` 自己维护一套完整 `create_session()`；
- `academic_affairs_attendance_teacher_relation_guard.py` 又维护一套更完整的 `create_session()`；
- 后者已经加入正式 `TeachingClassTeacher` 周次 Authority、课次去重、`teaching_task_id / occurrence_identity / source_type / source_reason / source_evidence`；
- 最新修复只落在 guard 时，public 的旧事务会自然漂移，形成“同一问题修两遍”的长期风险。

收口裁决：

- **唯一 command transaction owner**：
  `academic_affairs_attendance_teacher_relation_guard.py`
- **唯一 relation-aware list/stats owner**：
  `academic_affairs_attendance_teacher_relation_read_guard.py`
- `academic_affairs_attendance_public_service.py` 只保留稳定 facade、ADMIN_SPECIAL 共享辅助函数和正式课次 resolver 注入点；
- public 的 create/get/mark/submit/list/stats 全部显式委托最终 Owner；
- 新 `test_academic_c_closure_contract.py` 永久禁止 public 再出现第二个 `AaAttendanceSession(...)` 创建事务。

这不是删兼容 URL；只是把兼容入口统一到同一业务 Authority。

### 2.2 W0 Gate 已过期 — 已修成当前 C 最终合同

旧 W0 workflow 仍停留在最初成熟链：

- 没监听后来真正接管考勤执行的 relation guard / read guard / occurrence consumer；
- compile 也没覆盖这些最终 Owner；
- 将任何 Alembic revision 都视为 C 越界。

但当前 C-W4 已合法拥有并通过 Final Gate 的两个成绩 deadline revision：

- `20260818_aa_grade_task_deadline.py`
- `20260818_merge_prog_grade_deadline.py`

收口后：

- 共享 `route_registration / permissions / permission_catalog / services/__init__ / academic_affairs_registry / data-exchange` 仍绝对禁止；
- migration 改为**精确 allowlist**，只允许上述两个 C 已验收 revision，任何第三个 revision 仍失败；
- W0 编译/回归加入正式课次、teacher relation、relation-aware read 与 single-owner closure contract；
- W0 因而可以对当前最终 C HEAD 做真实复验，不再因为历史规则自相矛盾而永远无法 Gold。

## 3. C-W0 成熟链 KEEP 矩阵

### Attendance

唯一写链：

`public facade → attendance_teacher_relation_guard → PublishedOccurrence + TeachingClassTeacher + TeachingRoster snapshot → AttendanceSession`

硬事实：

- 普通考勤必须绑定当前学期可执行 TeachingTask；
- 当前正式课次由 ScopeHead active batch + calendar + schedule change 解析；
- `ADJUST/STOP/MAKEUP` 只消费已经 APPLIED 的正式变化；
- 普通教师权限来自正式 `TeachingClassTeacher`，按 occurrence teaching week 裁决；
- 未投影 TeachingClass 的历史任务才允许 TeachingTask migration fallback；
- 正式场次冻结 `ATTENDANCE_SESSION` RosterConsumerSnapshot；
- 同一 formal occurrence 重复创建 fail-closed；
- ADMIN_SPECIAL 只允许管理员且必须 reason + evidence；
- 正式场次持久化 TeachingTask、occurrence identity、source provenance；
- 台账/统计按 relation week 读取，ADMIN_SPECIAL 不污染默认课堂统计。

### Exam

保持 `academic_affairs_exam_facade.py` 为成熟 Authority：

- formal term；
- TeachingTask；
- `EXAM_COURSE` roster snapshot；
- 名单、容量、座位、监考完整后才可发布；
- 发布后变更显式留痕。

本轮不重建 Exam。

### Grade / EffectiveGrade

保持正式 Grade 主链：

- GradeTask 绑定稳定 course identity；
- 正式名单来自 TeachingRoster；
- submit 冻结 `GRADE_TASK` snapshot；
- publish 要求 snapshot current；
- EffectiveGrade 按稳定课程身份 + 冻结 policy；
- Correction/Recheck 追加正式版本，不原地覆盖。

W4 已关闭原规模欠账：

- task list SQL `COUNT + ORDER BY + OFFSET/LIMIT`；
- deadline/延期/逾期 + DB trigger；
- reminder/digest/outbox；
- XLSX Path 安全读取；
- teacher relation + workload 对账。

## 4. C-W1 Published Occurrence / Attendance

早期地图中的 `B-C1_NOT_FROZEN` 已过期，不能继续当施工阻断。

当前 C 已有正式 consumer：

- `academic_affairs_attendance_occurrence_consumer.py`
- ScopeHead active batch；
- `AaScheduleItem` recurrence；
- HOLIDAY / SWAP；
- APPLIED schedule change；
- expected `scheduleItemId`；
- occurrence concurrency / duplicate fail-closed。

现有合同：

- `test_aa_attendance_published_occurrence_contract.py`
- `test_aa_attendance_applied_change_contract.py`
- `test_aa_attendance_expected_schedule_item_contract.py`
- `test_aa_attendance_occurrence_concurrency.py`
- `test_aa_attendance_class_options_formal_schedule.py`

C-C1 不再定义第二套 Schedule Authority，只消费正式事实。

## 5. C-W2 Teacher Today

当前 Authority：

- `academic_affairs_teacher_today_service.py`
- `academic_affairs_teacher_today_execution_state_service.py`
- `academic_affairs_teacher_today_grade_todo_guard.py`
- 教师 PC / miniapp consumer。

约束：

- read projection only；
- 不新建第二 Task/Todo；
- 成绩待办必须回链 live GradeTask + formal teacher authority；
- 调课后消费正式 occurrence truth；
- 首页 deep-link 进入点名/监考/成绩。

最近同头历史证据：
`1949036b...` 上 `Academic C W2 Teacher Today Targeted` run `32128879965` 为 success。新收口 commit 后必须重新只认新 SHA。

## 6. C-W3 Exam

当前实现已包含：

- formal print / issue；
- invigilation workbench + scope；
- exam incident closure；
- publish delivery guard；
- student exam safe read / defer fail-closed；
- PC/miniapp 正式消费者。

C-Final 已对 Exam targeted MySQL + frontend source contracts 做验收。本次不再重写成熟 Exam。

## 7. C-W4 Grade

当前实现已包含：

- Grade task DB pagination；
- deadline / extension / overdue；
- scheduler milestone reminder + overdue digest；
- MySQL deadline trigger；
- teacher relation live authority；
- mobile legacy grade entry 统一到同一 live owner；
- Path XLSX 安全读取；
- reminder message event；
- workload relation-first reconciliation；
- PC 成绩状态和 `allowedActions`。

旧地图“`.all()` 后 Python slice”“截止/催录待施工”等文字全部作废。

## 8. C-W5 C Gold

总册定义：

`课表 → 点名 → 调课 → 考试/监考 → 录成绩 → 审核退回 → 再提交 → 发布`

当前可执行证据资产不是空白：

### Broad live flow

`backend/scripts/e2e_academic_affairs_live_flow.py`

按同一 runner 顺序执行：

1. `chain3_schedule_attendance()`
2. `chain4_selection_exam()`
3. `chain5_grades_warning()`

其中已有：

- `C3.schedule_publish`
- `C3.schedule_four_end_read`
- `C3.schedule_change_apply`
- `C4.exam_invigilator`
- `C5.grade_draft`
- `C5.grade_submit`
- `C5.grade_college_return`
- RETURN 后再次保存/submit
- college approve
- `C5.grade_publish`
- `C5.transcript_four_end`
- `C0.multi_login`
- `C0.logout_invalidates_token`

### Strict attendance flow

`backend/scripts/e2e_academic_affairs_round3.py`

正式 ScopeHead occurrence 候选 → create → mark → submit：

- `R3.att_submit`
- 找不到正式 occurrence 时明确失败，不把 400/409 当 Gold。

### Closure contract

`backend/tests/test_academic_c_closure_contract.py` 锁定：

- 考勤只有一个 command transaction owner；
- W5 上述可执行 E2E 资产不能被静默删掉或退化；
- grade RETURN 与 publish 之间必须存在真实 resubmit/approve。

因此 W5 的**实现资产已齐**；最终 Gold 仍必须是当前 exact HEAD 的门禁 + interaction evidence，不能复用旧 SHA。

## 9. 前端影响审计

本次去重只改后端公开 facade / Gate / contract / 文档：

- 不改教师 PC Vue 页面；
- 不改 miniapp 页面；
- 不改路由；
- 不改权限；
- 不改 DTO；
- 不改数据库 schema；
- 不改 Grade/Exam 状态机。

当前 C-Final 和小程序 Gate 已在上一 HEAD 证明生产构建可用；新 HEAD 仍必须自动重跑相关门禁后才签字。

## 10. 合并前唯一 Exit Gate

后续禁止再从旧日志发散施工，只做以下顺序：

1. PR exact HEAD 不漂；
2. `Academic C W0 Mature Chain Freeze`：success；
3. `Academic C W2 Teacher Today Targeted`：success（若当前 diff 触发/需要）；
4. `Academic C W3 W4 W5 PR Final`：success；
5. 小程序/Playwright 受影响门禁保持 success；
6. required `Main / canonical release gate`：success；
7. review threads = 0，mergeable=true；
8. 再合并 #148。

任何旧 SHA 的 failure / cancelled job 只作历史，不允许拿来生成新修复待办。
