# 教务 C 线 Teaching Execution V2.1 — 当前代码收口地图

> 固定施工分支：`agent/academic-c-teaching-execution`  
> PR：`#148`  
> Authority：`C_教务Teaching_Execution_当前代码精确施工总册_V2.1_20260816.md`  
> 当前 main 基线：`7fcf4f911e5ae8827c13e532e13c61676318b343`  
> 本轮审计原则：代码事实 > 历史日志；只认当前 PR exact HEAD 的同头门禁；禁止用旧失败重复施工。

## 1. 当前 Wave 结论

| Wave | 当前代码事实 | 状态 |
|---|---|---|
| C-W0 Mature Chain Freeze | Attendance / Exam / Grade / EffectiveGrade / Correction-Recheck 成熟 Authority 保留；W0 已改成 PR exact-head Gate | `IMPLEMENTED / SAME_HEAD_REVALIDATING` |
| C-W1 Published Occurrence + Attendance | ScopeHead 正式课表、APPLIED 调停课、TeachingRoster、正式教师关系、ADMIN_SPECIAL 均已接入 | `IMPLEMENTED / C-C1 FROZEN / SAME_HEAD_REVALIDATING` |
| C-W2 Teacher Today | 只读聚合今日课、点名入口、调课变化、监考、成绩待办；不建第二 Task/Todo | `IMPLEMENTED` |
| C-W3 Exam | 正式名单/发布门禁保留；打印、监考、异常闭环、学生考试读取已接入 | `IMPLEMENTED` |
| C-W4 Grade | SQL 分页、deadline/延期/逾期、催录、退回重提、Path XLSX、工作量/教师关系 Authority 已落 | `IMPLEMENTED` |
| C-W5 C Gold | 可执行资产覆盖课表/调课、正式考勤 mark+submit、监考、录分、学院退回、教师重提、发布、跨端回读与登录隔离 | `IMPLEMENTED / SAME_HEAD_REVALIDATING` |

剩余工作不是继续扩业务，而是把当前 exact HEAD 的 W0、C-W2、C-Final、Playwright、Main required gate 跑成同头 Gold。

## 2. 本轮重复代码审计

### 2.1 考勤 command/read Owner 已收成一套

历史上同时存在旧 service、public service、relation-aware command/read guard 和启动期 monkey-patch。最终裁决：

- 唯一 command transaction owner：`academic_affairs_attendance_teacher_relation_guard.py`
- 唯一 relation-aware read owner：`academic_affairs_attendance_teacher_relation_read_guard.py`
- 稳定 public facade / 测试注入 seam：`academic_affairs_attendance_public_service.py`
- 历史 import path：`academic_affairs_attendance_service.py` 仅做 compatibility export，不再保存第二套事务
- Router 不再重复 monkey-patch command/read；移动端 picker 只显式绑定 relation-first Teacher Today 投影

`backend/tests/test_academic_c_closure_contract.py` 永久禁止旧业务实现重新长回来。

### 2.2 W0 真红纠错：禁止虚构 AttendanceSession 列

当前 ORM `AaAttendanceSession` 没有 `teaching_task_id / occurrence_identity / source_type / source_reason / source_evidence`。把这些参数直接塞进构造器属于真实生产 bug，不是测试问题。

C 线不抢共享模型/迁移 Owner。最终持久化策略只用现有事实：

- TeachingTask + TeachingRoster identity：既有 `RosterConsumerSnapshot`
- 正式 occurrence：`occurrenceIdentity / scheduleItem / activeBatch / scope` 写 `AffairsAuditTrail.detail`
- ADMIN_SPECIAL：`session_type=ADMIN_SPECIAL`，reason + evidence 写 `AffairsAuditTrail.detail`
- 正式 occurrence 重复创建继续按 tenant + class + date + slot + 非 ADMIN_SPECIAL 行锁 fail-closed
- 创建响应返回 `occurrenceEvidence`，但不伪装不存在的 ORM 列

W0/C-Final source contract 同步锁住这条规则。

## 3. C-W0 KEEP Matrix

Attendance：`public facade → relation-aware command → ScopeHead occurrence → TeachingClassTeacher → versioned TeachingRoster → RosterConsumerSnapshot → AttendanceSession + AuditTrail`。普通教师必须当前学期可执行 TeachingTask；正式课次来自 active ScopeHead；调停课只消费 APPLIED；正式教师按 occurrence week 裁决；正式名单冻结 snapshot；ADMIN_SPECIAL 强制 reason+evidence；默认课堂统计排除特殊补录。

Exam：继续 KEEP formal term / TeachingTask / EXAM_COURSE roster snapshot / 名单容量座位监考完整发布 / 发布后显式变更。

Grade / EffectiveGrade：继续 KEEP stable course identity、TeachingRoster、GRADE_TASK snapshot、publish current check、EffectiveGrade policy、Correction/Recheck 追加版本。W4 已完成 SQL pagination、deadline/延期/逾期、reminder/digest/outbox、Path XLSX、teacher relation/workload reconciliation。

## 4. C-W1 Published Occurrence / Attendance

早期 `B-C1_NOT_FROZEN` 已过期。当前 consumer 已覆盖 ScopeHead active batch、AaScheduleItem recurrence、HOLIDAY/SWAP、APPLIED schedule change、expected scheduleItemId、occurrence concurrency/duplicate fail-closed。C-C1 只消费正式 Schedule Authority，不再造第二套课次。

## 5. C-W2 Teacher Today

read projection only；不新建第二 Task/Todo；成绩待办回链 live GradeTask + formal teacher authority；正式课次批量投影；移动点名 picker 只展示当前正式、本人关系覆盖且 attendanceExecutable=true 的课次；历史/非 active schedule task 不伪装成可点名选项。

## 6. C-W3 Exam

formal print / issue、invigilation workbench + scope、exam incident closure、publish delivery guard、student exam safe read / defer fail-closed、PC/miniapp 正式消费者均已实现；禁止重写成熟 Exam/roster/publish Authority。

## 7. C-W4 Grade

Grade task DB pagination、deadline/extension/overdue、scheduler reminder/digest、MySQL deadline trigger、teacher relation live authority、legacy/mobile grade entry 统一、Path XLSX、message event、workload reconciliation、PC allowedActions/逾期状态均已实现。

## 8. C-W5 C Gold

总册定义：`课表 → 点名 → 调课 → 考试/监考 → 录成绩 → 审核退回 → 再提交 → 发布`。

现有可执行资产：`backend/scripts/e2e_academic_affairs_live_flow.py` 依次执行 chain3/chain4/chain5，覆盖 schedule publish/change、exam invigilator、grade draft/submit/college return/resubmit/approve/publish/transcript、多登录与 logout；`backend/scripts/e2e_academic_affairs_round3.py` 覆盖正式 ScopeHead occurrence → create → mark → submit。`test_academic_c_closure_contract.py` 锁定这些资产不能静默退化。

## 9. 前端影响

本轮只收后端 Owner、合同、Gate、文档；不改教师 PC/miniapp 页面、公共路由、权限、主 DTO、Attendance/Exam/Grade schema 或状态机。前端只需同头重新通过 production build、source contract、Playwright，不另做重复 UI 施工。

## 10. 唯一 Exit Gate

只认当前 exact HEAD：W0 success → C-W2 success → C-Final success → 小程序 Gate success → Playwright success → required `Main / canonical release gate` success → review threads=0 → mergeable=true → HEAD/main 不漂后合并 #148。旧 SHA 的 failure/cancelled 日志不得生成新待办。
