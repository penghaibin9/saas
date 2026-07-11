# 13A · 学工中心 API 契约草案

> 文档性质：13A 学工中心全部后端接口契约草案（PC 管理端 + 学生小程序 + 教师移动端），供契约冻结（13A-P1 阶段）评审。
> 需求依据：`docs/03-业务模块设计/跨模块融合/_13-需求输入-V1.1.md` §2.x；实现依据：`docs/03-业务模块设计/跨模块融合/_13-现有系统集成事实速查.md`（响应/错误码/鉴权/Workflow/待办消息/导入导出管线全部复用既有实现）。
> 配套文档：`13A-学工中心状态机与权限矩阵.md`（状态机/权限点/数据范围为本册接口的行为依据）。
> 本文档不写代码、不改路由；路径与结构冻结前允许评审调整。
> 生成日期：2026-07-05

---

## 0. 统一说明（全部接口适用）

### 0.1 响应包络与错误码（沿用速查 §1，不得另造）

响应体：`{ code(数字), bizCode(字符串), message, data, traceId, timestamp }`；成功 `code=0 / bizCode=SUCCESS`。

| HTTP | code | bizCode | 学工中心典型场景 |
|---|---|---|---|
| 401 | 401001 | UNAUTHORIZED | 未登录/Token 失效/refreshToken 黑名单命中 |
| 403 | 403001 | NO_PERMISSION | 缺权限点；学生令牌访问 PC 接口（require_staff）；demo-school 只读锁写操作 |
| 403 | 403002 | NO_DATA_SCOPE | 有权限点但目标学生/班级/楼栋不在 scope 内（越权访问具体资源，写 PERMISSION_DENIED 审计） |
| 404 | 404001 | DATA_NOT_FOUND | 资源不存在或跨租户 ID（跨租户按不存在处理，不暴露存在性） |
| 409 | 409001 | DATA_CONFLICT / APPROVAL_VERSION_CONFLICT / IDEMPOTENCY_CONFLICT | 状态机非法转移；审批乐观锁冲突；重复提交（同 request_id 不同 payload / 业务唯一约束） |
| 422 | 422001 | VALIDATION_ERROR | 字段校验失败（details 给字段级行级原因） |
| 429 | 429001 | RATE_LIMITED | 导出限流（5 次/分）等 |
| 400 | 400001 | BAD_REQUEST | 参数格式错误 |

业务错误绝不 500；列表空数据返回成功 + 空 list；范围内无数据→空列表，越权访问具体资源→403002（判定标准见 docs/05-数据接口权限与安全/api/04 §三）。

### 0.2 鉴权与租户

- PC 管理端全部接口：`Authorization: Bearer <token>` + `require_staff`（学生令牌一律 403001）。
- 学生接口一律 `/api/v1/mobile/affairs/*`（token userType=STUDENT，student_id 恒从 token claims 取，路径/参数传他人 ID → 403002）。
- 教师移动端写操作走 `/api/v1/mobile/teacher/affairs/*` 包装（范围校验 + 审计 + 409）。
- 全部接口带租户上下文：tenant_id 从 token 解析（tid/tenantId claims），前端永不传；数据访问层统一 `WHERE tenant_id=:current`。demo-school 只读锁、到期租户只读中间件对本模块同样生效。
- 数据范围：统一走 `getStudentAffairsScope`（= resolve_teacher_scope + DORM_BUILDING/PSY_STUDENT/FUNDING_BIZ 扩展，见配套文档 §14），列表过滤与写校验共用同一解析。
- 写操作携带 `requestId`（幂等键）；审批类写操作携带 `version`（乐观锁）；驳回/退回 `reason` ≥5 字。
- 分页：`page/pageSize`（PC），`cursor/pageSize`（移动端滚动）；响应 `data={list,total,page,pageSize}`。

### 0.3 通用行为

- 审批动作落 `t_workflow_instance/t_workflow_task`，待办写 `t_unified_todo`，消息写 `t_unified_message`（8 种统一消息类型）。
- 审计：表中"审计动作"= `audit_log.record(action, resource, …)` 的 action 值；敏感读取另发 `SENSITIVE_VIEW`。
- 文件：上传走既有文件中心，业务只传 `fileIds[]`。
- ID 字符串化返回；时间 ISO8601 带时区；枚举返回英文码 + `xxxLabel`。

---

## 1. 学工首页（13A-01）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 1 | GET /api/v1/student-affairs/dashboard | 角色化学工首页 | semester(string,否)、dateRange(string,否)；角色/范围从 token+scope 解析 | summaryCards / todoList / riskStudents / workflowPending / classOverview / warningTrends / recentActivities | studentAffairs.dashboard.view | 无（读） |

**data 示例**：
```json
{
  "rolePreset": "COUNSELOR",
  "summaryCards": [{"key": "riskStudents", "label": "风险学生", "value": 6, "drill": "/admin/student-affairs/risk"}],
  "todoList": [{"todoId": "981", "todoType": "WORKFLOW_TODO", "title": "张某的请假待审批", "dueAt": "2026-07-06T12:00:00+08:00"}],
  "riskStudents": [{"studentId": "1024", "studentNo": "2024010203", "realName": "张*", "riskLevel": "HIGH", "profileUrl": "/admin/student-affairs/students/1024/profile"}],
  "workflowPending": {"leave": 3, "aid": 1, "funding": 0, "discipline": 1},
  "classOverview": [{"classId": "88", "className": "软件2401", "studentCount": 42, "riskCount": 2}],
  "warningTrends": [{"date": "2026-07-01", "count": 3}],
  "recentActivities": []
}
```
**错误码**：401001 未登录；403001 学生令牌；角色 preset 按 currentRoleCode 自动选择，无学工任何权限点时 403001。

---

## 2. 辅导员工作台（13A-02，counselor 四接口）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 2 | GET /api/v1/student-affairs/counselor/workbench | 工作台聚合（我的班级/待办/风险/预警/异常汇总） | 无 | myClasses / todayTodos / riskSummary / academicWarnings / pendingLeave / difficultStudents / employmentUnfilled / internshipExceptions / gdExceptions | studentAffairs.counselor.dashboard.view | 无 |
| 3 | GET /api/v1/student-affairs/counselor/students | 我的学生列表（快速搜索） | keyword(string,否)、classId(string,否)、riskLevel(enum,否)、page/pageSize | list[{studentId,studentNo,realName,className,riskLevel,tags[]}] | studentAffairs.counselor.student.view | 无 |
| 4 | GET /api/v1/student-affairs/counselor/todos | 今日/全部待办（读 t_unified_todo，scope 过滤） | status(enum,否)、todoType(enum,否)、page/pageSize | list[{todoId,todoType,sourceModule,studentId,title,dueAt,status}] | studentAffairs.counselor.todo.handle | 无 |
| 5 | GET /api/v1/student-affairs/counselor/risk-students | 风险学生列表 | riskLevel(enum,否)、source(enum,否)、status(enum,否)、page/pageSize | list[{riskId,studentId,realName,source,riskLevel,status,assignedAt}] | studentAffairs.counselor.risk.handle | 无 |

**workbench data 示例**：
```json
{
  "myClasses": [{"classId": "88", "className": "软件2401", "studentCount": 42, "riskCount": 2, "pendingLeave": 1}],
  "todayTodos": [{"todoId": "981", "todoType": "WORKFLOW_TODO", "sourceModule": "AFFAIRS_LEAVE", "title": "张某的请假待审批", "dueAt": "2026-07-06T12:00:00+08:00", "status": "PENDING"}],
  "riskSummary": {"total": 6, "high": 1, "processing": 3},
  "academicWarnings": {"total": 4, "unhandled": 2},
  "pendingLeave": 3,
  "difficultStudents": 8,
  "employmentUnfilled": 5,
  "internshipExceptions": 1,
  "gdExceptions": 0
}
```
**students data 示例**：
```json
{
  "list": [{"studentId": "1024", "studentNo": "2024010203", "realName": "张*", "className": "软件2401", "riskLevel": "MEDIUM", "tags": ["困难B级", "请假中"]}],
  "total": 42, "page": 1, "pageSize": 20
}
```
**错误码**：403001 非辅导员/班主任角色；scope 无任何 CLASS 行且非 ADMIN → 空列表（TENANT_FALLBACK 不放行，见配套文档 §14.5）；具体学生越权 → 403002。

---

## 3. 学生信息与画像（13A-03）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 6 | GET /api/v1/student-affairs/students/{studentId}/profile | 学工画像（读 t_student_profile + 各域沉淀） | 无 | baseInfo(脱敏) / statusInfo / leaveSummary / aidSummary / disciplineSummary(按权限) / psyFlag(仅"需关注") / talkSummary / dormInfo / activitySummary / moralScore / riskLevel | studentAffairs.student.view | 无 |
| 7 | GET /api/v1/student-affairs/students/{studentId}/timeline | 成长时间线（t_student_stage_event + affairs 事件） | eventType(enum,否)、page/pageSize | list[{eventId,eventType,module,title,occurredAt,refId}] | studentAffairs.student.view | 无 |
| 8 | POST /api/v1/student-affairs/students/{studentId}/sensitive/reveal | 查看完整隐私字段（联系方式/家庭/身份证） | field(enum,必)、reason(string,必,≥5字) | {field, fullValue} 一次性返回，不缓存 | studentAffairs.student.sensitiveView | SENSITIVE_VIEW（原因入 detail） |

**profile data 示例**：
```json
{
  "baseInfo": {"studentId": "1024", "studentNo": "2024010203", "realName": "张三", "phoneMasked": "138****1234", "idCardMasked": "1101**********1234", "collegeName": "软件学院", "className": "软件2401", "counselorName": "李老师"},
  "statusInfo": {"currentStage": "ON_CAMPUS", "studentStatus": "NORMAL"},
  "leaveSummary": {"total": 3, "overdue": 0, "onLeave": false},
  "aidSummary": {"difficultLevel": "B", "identifiedAt": "2025-10-12", "fundingCount": 2},
  "disciplineSummary": {"activeCount": 0, "removedCount": 1},
  "psyFlag": {"needAttention": false},
  "talkSummary": {"total": 5, "lastTalkAt": "2026-06-20"},
  "dormInfo": {"building": "3号楼", "room": "302", "bed": "2"},
  "activitySummary": {"count": 8, "creditHours": 24, "moralScore": 86},
  "riskLevel": "LOW",
  "timelineUrl": "/api/v1/student-affairs/students/1024/timeline"
}
```
**错误码**：404001 学生不存在/跨租户；403002 学生不在 scope；403001 无 sensitiveView 权限点；422001 reason 不足 5 字。心理明细字段本接口不放行（走 §9 心理专用链路）。

**分角色视图差异**：宿管访问返回住宿视图子集（dormInfo+baseInfo 脱敏摘要）；资助老师返回资助视图子集（aidSummary/fundingSummary）；心理老师需 PSY_STUDENT 授权行方可访问，返回附 psyDetail 区块；班主任不含 disciplineSummary 之外的处分明细链接。字段裁剪由服务端按 scope 计算，前端不做视图判定。

---

## 4. 班级管理（13A-04）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 9 | GET /api/v1/student-affairs/classes | 班级列表 | collegeId/majorId/grade/keyword(均否)、page/pageSize | list[{classId,className,grade,majorName,collegeName,counselorName,headTeacherName,studentCount}] | studentAffairs.class.view | 无 |
| 10 | POST /api/v1/student-affairs/classes | 建班（绑定学院/专业/年级） | className(string,必)、majorId(string,必)、grade(string,必)、counselorId/headTeacherId(否) | {classId} | studentAffairs.class.create | AFFAIRS_CLASS_CREATE |
| 11 | GET /api/v1/student-affairs/classes/{classId} | 班级档案详情 | 无 | 班级档案 + 绑定信息 + 材料清单 | studentAffairs.class.view | 无 |
| 12 | PUT /api/v1/student-affairs/classes/{classId}/bindings | 调整辅导员/班主任绑定（同步写 scope 行） | counselorId(string,否)、headTeacherId(string,否)、version(必) | {classId, counselorName, headTeacherName} | studentAffairs.class.config | PERMISSION_CHANGE |
| 13 | GET /api/v1/student-affairs/classes/{classId}/students | 班级学生列表 | keyword/riskLevel(否)、page/pageSize | list[学生行(脱敏)] | studentAffairs.class.view | 无 |
| 14 | GET /api/v1/student-affairs/classes/{classId}/cadres | 班干部列表 | 无 | list[{cadreId,studentId,realName,position,startAt}] | studentAffairs.class.view | 无 |
| 15 | POST /api/v1/student-affairs/classes/{classId}/cadres | 设置/调整班干部 | studentId(必)、position(enum,必)、requestId | {cadreId} | studentAffairs.class.cadre.manage | AFFAIRS_CADRE_SET |
| 16 | GET /api/v1/student-affairs/classes/{classId}/profile | 班级画像（人数/男女/困难/风险/请假/处分/宿舍异常/学业预警/就业未填报/实习毕设异常） | semester(否) | metrics{} + trends[] | studentAffairs.class.view | 无 |

**错误码**：409001 同学院同名班级重复建班；403002 学院学工建他院班级/辅导员看非负责班级；422001 majorId 不存在于 t_major。

---

## 5. 请假/销假/续假（13A-05，全套）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 17 | GET /api/v1/student-affairs/leave | 请假单管理列表 | status/leaveType/classId/collegeId/keyword/dateRange(均否)、page/pageSize | list[{leaveId,studentNo,realName(脱敏),leaveType,startAt,endAt,days,status,statusLabel}] | studentAffairs.leave.view | 无 |
| 18 | GET /api/v1/student-affairs/leave/pending | 我的待审批列表 | page/pageSize | list[待审单 + workflowTaskId + version] | studentAffairs.leave.approve | 无 |
| 19 | GET /api/v1/student-affairs/leave/{leaveId} | 请假单详情（含审批链/附件/销假/续假记录） | 无 | detail + approvals[] + cancelRecord + extensions[] | studentAffairs.leave.view | 无（原因涉隐私时另发 SENSITIVE_VIEW） |
| 20 | POST /api/v1/student-affairs/leave/{leaveId}/approve | 审批通过（按天数自动流转下一节点或 APPROVED） | comment(string,否)、version(必)、requestId | {leaveId, status, nextNode} | studentAffairs.leave.approve | APPROVAL |
| 21 | POST /api/v1/student-affairs/leave/{leaveId}/reject | 驳回 | reason(string,必,≥5字)、version、requestId | {leaveId, status:"REJECTED"} | studentAffairs.leave.reject | APPROVAL |
| 22 | POST /api/v1/student-affairs/leave/{leaveId}/return | 退回补材料 | reason(必,≥5字)、version、requestId | {leaveId, status:"RETURNED"} | studentAffairs.leave.return | APPROVAL |
| 23 | POST /api/v1/student-affairs/leave/{leaveId}/cancel-leave/confirm | 销假确认/销假退回 | action(enum CONFIRM/RETURN,必)、actualReturnAt(CONFIRM必)、reason(RETURN必)、version、requestId | {leaveId, status:"CLOSED"或"APPROVED"} | studentAffairs.leave.cancelLeaveConfirm | AFFAIRS_LEAVE_CLOSE |
| 24 | POST /api/v1/student-affairs/leave/{leaveId}/extension/approve | 续假审批（通过/驳回） | action(enum,必)、reason(驳回必)、version、requestId | {leaveId, status:"APPROVED", newEndAt} | studentAffairs.leave.extension.approve | APPROVAL |
| 25 | POST /api/v1/student-affairs/leave/{leaveId}/overdue/handle | 逾期处置登记（联系记录/转家校/关闭） | handleType(enum CONTACT/TO_HOME_SCHOOL/CLOSE,必)、note(必)、requestId | {leaveId, status} | studentAffairs.leave.overdue.handle | AFFAIRS_LEAVE_OVERDUE_HANDLE |
| 26 | POST /api/v1/student-affairs/leave/{leaveId}/proxy-cancel-leave | 辅导员代登记销假 | actualReturnAt(必)、note(否)、requestId | {leaveId, status:"WAIT_CANCEL_LEAVE"} | studentAffairs.leave.cancelLeaveConfirm | AFFAIRS_LEAVE_PROXY |
| 27 | GET /api/v1/student-affairs/leave/stats | 请假统计（人数/天数/逾期未销，按学院/班级下钻） | groupBy(enum,必)、semester/dateRange(否) | metrics + breakdown[] | studentAffairs.stats.view | 无 |
| 28 | GET /api/v1/student-affairs/leave/rules | 查询请假规则（天数阈值/宽限期/材料要求） | 无 | rules{}（读平台规则中心） | studentAffairs.leave.config | 无 |
| 29 | PUT /api/v1/student-affairs/leave/rules | 修改请假规则（写平台规则中心 safe_rule） | rules(object,必)、requestId | rules{} | studentAffairs.leave.config | PERMISSION_CHANGE |

**审批通过 data 示例**：
```json
{"leaveId": "3301", "status": "COLLEGE_REVIEW", "statusLabel": "学院审核中", "nextNode": {"nodeCode": "COLLEGE_REVIEW", "assigneeRole": "COLLEGE_AFFAIRS"}, "version": 3}
```
**错误码**：409001 状态不允许（如审批已终态单）/APPROVAL_VERSION_CONFLICT 并发审批/重复审批；403002 审批非 scope 学生；422001 reason 不足 5 字/actualReturnAt 早于开始时间；404001 单不存在。学生发起/销假/续假接口见 §17 移动端。

---

## 6. 困难认定（13A-06，aid 全套）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 30 | GET /api/v1/student-affairs/aid/batches | 认定批次列表 | schoolYear(否)、status(否)、page/pageSize | list[{batchId,batchName,schoolYear,applyStart,applyEnd,status}] | studentAffairs.aid.view | 无 |
| 31 | POST /api/v1/student-affairs/aid/batches | 建/发布认定批次 | batchName(必)、schoolYear(必)、applyStart/applyEnd(必)、levelConfig(object,必)、publish(bool,否) | {batchId, status} | studentAffairs.aid.batch.manage | AFFAIRS_AID_BATCH |
| 32 | GET /api/v1/student-affairs/aid/applications | 认定申请列表（家庭经济列默认脱敏） | batchId/status/collegeId/classId/level(否)、page/pageSize | list[{applyId,studentNo,realName(脱敏),status,suggestLevel,currentNode}] | studentAffairs.aid.view | 无 |
| 33 | GET /api/v1/student-affairs/aid/applications/{applyId} | 申请详情（家庭经济脱敏；完整值走 #8 reveal） | 无 | detail + reviews[] + materials[] | studentAffairs.aid.view | 无 |
| 34 | POST /api/v1/student-affairs/aid/applications/{applyId}/review | 各级评审（班级评议/初审/复审/终审，按当前节点鉴权） | action(enum APPROVE/REJECT/RETURN,必)、level(终审必,enum)、opinion(否)、reason(REJECT/RETURN必≥5字)、version、requestId | {applyId, status, nextNode} | studentAffairs.aid.approve/reject/return | APPROVAL |
| 35 | POST /api/v1/student-affairs/aid/applications/{applyId}/adjust | 发起动态调整（等级升降/移出） | targetLevel(enum,必)、reason(必)、fileIds(否)、requestId | {applyId, status:"ADJUST_REVIEW"} | studentAffairs.aid.adjust | AFFAIRS_AID_ADJUST |
| 36 | POST /api/v1/student-affairs/aid/batches/{batchId}/publicity | 公示操作（开启/异议登记/期满确认） | action(enum START/OBJECTION/CONFIRM,必)、objection(object,OBJECTION必)、requestId | {batchId, publicityStatus} | studentAffairs.funding.publicity.manage | AFFAIRS_AID_PUBLICITY |
| 37 | GET /api/v1/student-affairs/aid/difficult-students | 困难学生库（等级/年度，供助学金/绿通/临补引用） | level/collegeId/classId/schoolYear(否)、page/pageSize | list[{studentId,realName(脱敏),level,identifiedAt,batchName}] | studentAffairs.aid.view | 无 |

**申请详情 data 示例（家庭经济默认脱敏）**：
```json
{
  "applyId": "5501", "batchId": "12", "studentNo": "2024010203", "realName": "张三",
  "status": "COLLEGE_REVIEW", "statusLabel": "学院复审中", "suggestLevel": "B",
  "familyEconomy": {"annualIncomeRange": "2-4万", "memberCount": 4, "specialTags": ["单亲"], "detailMasked": true},
  "materials": [{"fileId": "f-889", "fileName": "低保证明.pdf", "uploadedAt": "2026-06-01T10:00:00+08:00"}],
  "reviews": [
    {"node": "CLASS_REVIEW", "result": "APPROVE", "opinion": "评议小组一致同意", "actedBy": "李老师", "actedAt": "2026-06-03T09:00:00+08:00"},
    {"node": "COUNSELOR_REVIEW", "result": "APPROVE", "opinion": "情况属实，建议B级", "actedBy": "李老师", "actedAt": "2026-06-05T15:00:00+08:00"}
  ],
  "version": 4
}
```
**错误码**：409001 批次未开放/已截止/同批次重复申请；403002 跨学院评审/非授权访问；403001 无 aid.sensitiveView 请求完整家庭经济；422001 等级配置非法。导出走 §16 domain=affairs_aid（水印+二次确认+SENSITIVE 审计）。

---

## 7. 奖助勤贷（13A-07，funding 全套，统一抽象）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 38 | GET /api/v1/student-affairs/funding/projects | 资助项目列表 | projectType(enum,否)、status(否)、page/pageSize | list[{projectId,projectType,projectName,amountRule,status}] | studentAffairs.funding.view | 无 |
| 39 | POST /api/v1/student-affairs/funding/projects | 建项目（类型 SCHOLARSHIP/GRANT/WORK_STUDY/LOAN/TUITION_REDUCTION/TEMPORARY_AID/GREEN_CHANNEL） | projectType(必)、projectName(必)、amountRule(object)、conditions(object) | {projectId} | studentAffairs.funding.project.manage | AFFAIRS_FUNDING_PROJECT |
| 40 | GET /api/v1/student-affairs/funding/batches | 批次列表 | projectId/status(否)、page/pageSize | list[批次行] | studentAffairs.funding.view | 无 |
| 41 | POST /api/v1/student-affairs/funding/batches | 建/发布批次（条件/名额/时间） | projectId(必)、quota(int)、applyStart/applyEnd(必)、conditions(object)、publish(bool) | {batchId, status} | studentAffairs.funding.batch.manage | AFFAIRS_FUNDING_BATCH |
| 42 | GET /api/v1/student-affairs/funding/batches/{batchId}/recommendations | 奖学金系统推荐名单（成绩/处分/学籍校验结果） | page/pageSize | list[{studentId,realName(脱敏),gpa,checkResult{disciplineOk,statusOk,gradeOk}}] | studentAffairs.funding.batch.manage | 无 |
| 43 | GET /api/v1/student-affairs/funding/applications | 资助申请列表 | batchId/projectType/status/collegeId/classId(否)、page/pageSize | list[{applicationId,projectType,studentNo,realName(脱敏),status,currentNode}] | studentAffairs.funding.view | 无 |
| 44 | GET /api/v1/student-affairs/funding/applications/{applicationId} | 申请详情 | 无 | detail + reviews[] + result（金额脱敏按角色） | studentAffairs.funding.view | 无 |
| 45 | POST /api/v1/student-affairs/funding/applications/{applicationId}/review | 各级评审（节点按项目类型差异表路由，见配套文档 §3.1） | action(enum,必)、reason(驳回/退回必)、version、requestId | {applicationId, status, nextNode} | studentAffairs.funding.approve/reject/return | APPROVAL |
| 46 | POST /api/v1/student-affairs/funding/batches/{batchId}/publicity | 公示（开启/异议/期满确认，勤贷可配跳过） | action(enum,必)、requestId | {batchId, publicityStatus} | studentAffairs.funding.publicity.manage | AFFAIRS_FUNDING_PUBLICITY |
| 47 | POST /api/v1/student-affairs/funding/batches/{batchId}/confirm | 名单确认（写 result，生成资助档案，进360） | requestId、version | {batchId, approvedCount} | studentAffairs.funding.batch.manage | AFFAIRS_FUNDING_CONFIRM |
| 48 | GET /api/v1/student-affairs/funding/work-study/posts | 勤工助学岗位列表 | deptKeyword/status(否)、page/pageSize | list[{postId,postName,dept,quota,enrolled,status}] | studentAffairs.funding.view | 无 |
| 49 | POST /api/v1/student-affairs/funding/work-study/posts | 部门发岗（资助老师代录） | postName(必)、dept(必)、quota(int,必)、salaryRule(object)、requestId | {postId} | studentAffairs.funding.project.manage | AFFAIRS_WORKSTUDY_POST |
| 50 | POST /api/v1/student-affairs/funding/work-study/{applicationId}/assessments | 月度考核+补贴记录 | month(string,必)、score(int,必)、subsidy(decimal,必)、note(否)、requestId | {assessmentId} | studentAffairs.funding.workstudy.assess | AFFAIRS_WORKSTUDY_ASSESS |
| 51 | POST /api/v1/student-affairs/funding/work-study/{applicationId}/terminate | 离岗/终止 | reason(必)、requestId、version | {applicationId, status:"TERMINATED"} | studentAffairs.funding.approve | AFFAIRS_WORKSTUDY_TERMINATE |
| 52 | GET /api/v1/student-affairs/funding/loans | 贷款登记列表 | schoolYear/status/collegeId(否)、page/pageSize | list[{loanId,studentNo,realName(脱敏),year,amount(脱敏),bank,status}] | studentAffairs.funding.view | 无 |
| 53 | POST /api/v1/student-affairs/funding/loans/{loanId}/verify | 回执核对/审核/学校确认（节点式） | action(enum,必)、reason(驳回必)、version、requestId | {loanId, status} | studentAffairs.funding.approve | APPROVAL |

**评审 data 示例**：
```json
{"applicationId": "7702", "projectType": "GRANT", "status": "SCHOOL_REVIEW", "nextNode": {"nodeCode": "SCHOOL_REVIEW", "assigneeRole": "FUNDING_TEACHER"}, "version": 2}
```
**错误码**：409001 资格硬校验失败（处分未解除/学籍异常/成绩不达标/同批次重复/非困难库申助学金/岗位时间冲突）；422001 材料缺失/字段非法；403002 资助老师 FUNDING_BIZ 范围外；409 非 WORK_STUDY 调用考核接口。

---

## 8. 违纪处分与解除（13A-08，discipline 全套）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 54 | GET /api/v1/student-affairs/discipline/cases | 处分案件列表 | status/level/collegeId/classId/keyword(否)、page/pageSize | list[{caseId,studentNo,realName(脱敏),level,status,registeredAt}] | studentAffairs.discipline.view | 无 |
| 55 | POST /api/v1/student-affairs/discipline/cases | 登记违纪（事实+材料） | studentId(必)、factDesc(string,必,≥20字)、level(enum,必)、occurredAt(必)、fileIds[](必)、requestId | {caseId, status:"REGISTERED"} | studentAffairs.discipline.create | AFFAIRS_DISCIPLINE_REGISTER |
| 56 | GET /api/v1/student-affairs/discipline/cases/{caseId} | 案件详情（明细按权限；资格校验方仅结论） | 无 | detail + materials[] + reviews[] + removeApplies[] | studentAffairs.discipline.view | 明细读取审计 |
| 57 | POST /api/v1/student-affairs/discipline/cases/{caseId}/submit | 提交学院初审 | version、requestId | {caseId, status:"COLLEGE_REVIEW"} | studentAffairs.discipline.create | APPROVAL |
| 58 | POST /api/v1/student-affairs/discipline/cases/{caseId}/review | 逐级审批（学院/学工处/校级，节点鉴权） | action(enum APPROVE/REJECT/RETURN,必)、reason(REJECT/RETURN必≥5字)、version、requestId | {caseId, status, nextNode} | studentAffairs.discipline.approve/reject/return | APPROVAL |
| 59 | POST /api/v1/student-affairs/discipline/cases/{caseId}/deliver | 送达回执登记 | deliveredAt(必)、receiptFileId(必)、requestId | {caseId, deliveredAt} | studentAffairs.discipline.view(辅导员范围) | AFFAIRS_DISCIPLINE_DELIVER |
| 60 | POST /api/v1/student-affairs/discipline/cases/{caseId}/cancel | 撤销登记（误登，EFFECTIVE 前） | reason(必≥5字)、version、requestId | {caseId, status:"CANCELLED"} | studentAffairs.discipline.create | AFFAIRS_DISCIPLINE_CANCEL |
| 61 | GET /api/v1/student-affairs/discipline/removals | 解除申请列表 | status/collegeId(否)、page/pageSize | list[{removeId,caseId,studentNo,realName(脱敏),status,currentNode}] | studentAffairs.discipline.view | 无 |
| 62 | POST /api/v1/student-affairs/discipline/removals | 发起解除申请（辅导员代发起） | caseId(必)、performanceDesc(必,≥20字)、fileIds[](必)、requestId | {removeId, status:"REMOVE_REVIEW"} | studentAffairs.discipline.remove.create | AFFAIRS_DISCIPLINE_REMOVE_APPLY |
| 63 | POST /api/v1/student-affairs/discipline/removals/{removeId}/review | 解除逐级审批（辅→院→学工处） | action(enum,必)、reason(驳回/退回必)、version、requestId | {removeId, status, nextNode}；终审通过 {caseStatus:"REMOVED"} | studentAffairs.discipline.remove.approve | APPROVAL |

**逐级审批 data 示例（学工处复核通过，严重处分流转校级）**：
```json
{
  "caseId": "6603", "status": "SCHOOL_REVIEW", "statusLabel": "学校审批中",
  "nextNode": {"nodeCode": "SCHOOL_REVIEW", "assigneeRole": "STUDENT_AFFAIRS_ADMIN"},
  "linkageHint": {"willFreezeFunding": true, "willAffectGraduationAudit": true},
  "version": 5
}
```
**错误码**：409001 EFFECTIVE 记录修改/未生效发起解除/未满最短期限（message 带最早可申请日）/在途解除重复提交；403002 跨学院登记审批；403001 心理老师/宿管/资助老师调用创建审批接口；404001 案件不存在。学生端仅回数量与文书状态（沿用 t_cs_discipline 约定），明细接口对学生令牌 403001。

**联动说明**：#58 审批至 EFFECTIVE 时服务端同步：① 写 t_cs_discipline 投影行（见 §18.2）；② 冻结奖助/评优资格标记（funding 资格校验读取）；③ 写 StageEvent 进 360；④ RISK_ALERT→辅导员。#63 终审 REMOVED 时反向解冻并保留历史。

---

## 9. 风险预警（13A-09，risk）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 64 | GET /api/v1/student-affairs/risk/records | 风险记录列表（心理来源明细自动收敛） | source/riskLevel/status/collegeId/classId(否)、page/pageSize | list[{riskId,studentNo,realName(脱敏),source,riskLevel,status,assignee,createdAt}] | studentAffairs.risk.view | 无 |
| 65 | POST /api/v1/student-affairs/risk/records | 人工标记风险 | studentId(必)、source(enum,必)、riskLevel(enum,必)、desc(必≥10字)、requestId | {riskId, status:"NEW"} | studentAffairs.risk.create | AFFAIRS_RISK_CREATE |
| 66 | GET /api/v1/student-affairs/risk/records/{riskId} | 风险详情（处置链/关联谈话/家校） | 无 | detail + handleRecords[] + transfers[] + linkedTalks[]（心理明细按 psyDetail.view） | studentAffairs.risk.view | 心理明细读取 SENSITIVE_VIEW |
| 67 | POST /api/v1/student-affairs/risk/records/{riskId}/assign | 分派/改派责任人 | assigneeId(必)、note(否)、requestId、version | {riskId, status:"ASSIGNED", assignee} | studentAffairs.risk.handle | AFFAIRS_RISK_ASSIGN |
| 68 | POST /api/v1/student-affairs/risk/records/{riskId}/handle | 处置记录（含转谈话/转家校联动） | handleType(enum,必)、content(必≥10字)、linkAction(enum TO_TALK/TO_HOME_SCHOOL,否)、requestId | {riskId, status:"PROCESSING", handleRecordId} | studentAffairs.risk.handle | AFFAIRS_RISK_HANDLE |
| 69 | POST /api/v1/student-affairs/risk/records/{riskId}/transfer | 转办 | targetAssigneeId(必)、reason(必≥5字)、requestId、version | {riskId, status:"ASSIGNED", assignee} | studentAffairs.risk.handle | AFFAIRS_RISK_TRANSFER |
| 70 | POST /api/v1/student-affairs/risk/records/{riskId}/escalate | 升级 | reason(必≥5字)、requestId、version | {riskId, status:"ESCALATED", riskLevel} | studentAffairs.risk.handle | AFFAIRS_RISK_ESCALATE |
| 71 | POST /api/v1/student-affairs/risk/records/{riskId}/close | 关闭（结论必填） | conclusion(必≥5字)、requestId、version | {riskId, status:"CLOSED"} | studentAffairs.risk.handle | AFFAIRS_RISK_CLOSE |
| 72 | POST /api/v1/student-affairs/risk/records/{riskId}/reopen | 重开 | reason(必≥5字)、requestId | {riskId, status:"REOPENED"} | studentAffairs.risk.handle | AFFAIRS_RISK_REOPEN |

**风险详情 data 示例（心理来源，请求者无 psyDetail.view）**：
```json
{
  "riskId": "9901", "studentNo": "2024010203", "realName": "张*",
  "source": "PSYCHOLOGY", "riskLevel": "HIGH", "status": "PROCESSING",
  "assignee": {"userId": "t-33", "realName": "王心理"},
  "psyDetail": null, "psyDetailHint": "心理明细需专项授权",
  "handleRecords": [{"handleId": "h-1", "handleType": "CONTACT", "contentSummary": "已首次联系", "actedBy": "王心理", "actedAt": "2026-07-01T10:00:00+08:00"}],
  "linkedTalks": [{"talkId": "t-88", "talkType": "PSYCHOLOGY", "status": "COMPLETED"}],
  "acadWarningRef": null,
  "version": 3
}
```
**错误码**：409001 无处置记录直接关闭/终态重复操作；403002 非责任人处置/转办后原责任人写操作；403001 无 psyDetail.view 取心理明细（普通教师仅见"需关注"）；来源=学业预警的记录引用 t_acad_warning，重复建单 409。导出 domain=affairs_risk 默认剔除心理明细。

---

## 10. 谈心谈话（13A-10，talks）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 73 | GET /api/v1/student-affairs/talks | 谈话列表（管理侧默认摘要） | talkType/status/classId/dateRange(否)、page/pageSize | list[{talkId,studentNo,realName(脱敏),talkType,status,scheduledAt,talkerName}] | studentAffairs.talk.view | 无 |
| 74 | POST /api/v1/student-affairs/talks | 建谈话计划（选学生+主题+类型） | studentIds[](必)、talkType(enum,必)、topic(必)、scheduledAt(否)、requestId | {talkIds[]} | studentAffairs.talk.create | AFFAIRS_TALK_PLAN |
| 75 | GET /api/v1/student-affairs/talks/{talkId} | 谈话详情（心理类全文按权限，否则摘要） | 无 | detail + followUps[] + linkedRisk | studentAffairs.talk.view | 心理类全文 SENSITIVE_VIEW |
| 76 | POST /api/v1/student-affairs/talks/{talkId}/record | 填写谈话记录（→COMPLETED） | content(必,≥20字)、result(enum,必)、needFollowUp(bool,必)、requestId、version | {talkId, status} | studentAffairs.talk.handle | AFFAIRS_TALK_RECORD |
| 77 | POST /api/v1/student-affairs/talks/{talkId}/follow-up | 跟进记录/办结/转风险/转家校 | action(enum FOLLOW/CLOSE/TO_RISK/TO_HOME_SCHOOL,必)、content(必)、requestId | {talkId, status, linkedRiskId?} | studentAffairs.talk.handle | AFFAIRS_TALK_FOLLOWUP |
| 78 | GET /api/v1/student-affairs/talks/stats | 谈话工作量统计（完成率进辅导员考评/Dashboard） | groupBy(enum COUNSELOR/CLASS/TYPE,必)、semester(否) | metrics + breakdown[] | studentAffairs.stats.view | 无 |

**错误码**：409001 未填记录直接办结/取消已完成谈话；403002 范围外学生建计划；心理类型记录人以外角色取全文 403001（授权辅导员除外）。

---

## 11. 宿舍与公寓（13A-11，dormitory）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 79 | GET /api/v1/student-affairs/dormitory/resources | 房源树/列表（楼→层→房→床，含占用状态） | buildingCode/status(否)、page/pageSize | list[{buildingCode,floor,roomNo,bedNo,gender,occupied,studentNo?}] | studentAffairs.dorm.view | 无 |
| 80 | POST /api/v1/student-affairs/dormitory/resources | 维护房源（新增/停用楼/房/床） | resourceType(enum,必)、payload(object,必)、requestId | {resourceId} | studentAffairs.dorm.resource.manage | AFFAIRS_DORM_RESOURCE |
| 81 | POST /api/v1/student-affairs/dormitory/allocation-plans | 生成排宿方案（规则：学院/专业/班级/性别/年级/特殊） | scopeConfig(object,必)、rules(object,必)、requestId | {planId, status:"DRAFT", conflictCount} | studentAffairs.dorm.allocation.manage | AFFAIRS_DORM_PLAN |
| 82 | POST /api/v1/student-affairs/dormitory/allocation-plans/{planId}/publish | 学院确认+发布（学生小程序可见，进360） | version、requestId | {planId, status:"PUBLISHED"} | studentAffairs.dorm.allocation.manage | AFFAIRS_DORM_PUBLISH |
| 83 | GET /api/v1/student-affairs/dormitory/transfers | 调宿单列表 | status/buildingCode/classId(否)、page/pageSize | list[{transferId,studentNo,realName(脱敏),fromBed,toBed,status,currentNode}] | studentAffairs.dorm.view | 无 |
| 84 | POST /api/v1/student-affairs/dormitory/transfers/{transferId}/review | 调宿审批（辅导员初审/宿管终审，含目标床位校验） | action(enum APPROVE/REJECT,必)、reason(REJECT必≥5字)、version、requestId | {transferId, status, nextNode} | studentAffairs.dorm.transfer.approve | APPROVAL |
| 85 | POST /api/v1/student-affairs/dormitory/transfers/{transferId}/execute | 执行迁移（原床释放+新床占用，原子） | requestId、version | {transferId, status:"COMPLETED"} | studentAffairs.dorm.transfer.approve | AFFAIRS_DORM_TRANSFER_EXEC |
| 86 | GET /api/v1/student-affairs/dormitory/inspections | 检查任务列表 | buildingCode/dateRange/status(否)、page/pageSize | list[{inspectionId,buildingCode,plannedAt,inspector,progress}] | studentAffairs.dorm.inspection.manage | 无 |
| 87 | POST /api/v1/student-affairs/dormitory/inspections | 建检查任务（按楼/房范围） | buildingCodes[](必)、plannedAt(必)、checkItems[](必)、requestId | {inspectionId} | studentAffairs.dorm.inspection.manage | AFFAIRS_DORM_INSPECT_CREATE |
| 88 | POST /api/v1/student-affairs/dormitory/inspections/{inspectionId}/records | 录检查记录（卫生/安全/违禁/夜不归宿，异常自动同步辅导员） | roomNo(必)、result(enum,必)、exceptionType(异常时必)、studentIds[](涉及人)、photoFileIds[](否)、requestId | {recordId, exceptionId?} | studentAffairs.dorm.inspection.manage | AFFAIRS_DORM_INSPECT_RECORD |
| 89 | GET /api/v1/student-affairs/dormitory/exceptions | 异常列表（扩展 t_cs_dorm_exception） | exceptionType/status/buildingCode/classId(否)、page/pageSize | list[{exceptionId,exceptionType,roomNo,studentNo,realName(脱敏),status,registeredAt}] | studentAffairs.dorm.view | 无 |
| 90 | POST /api/v1/student-affairs/dormitory/exceptions/{exceptionId}/handle | 异常处置（认领/留痕/升级转风险/关闭/误登撤销） | action(enum CLAIM/NOTE/ESCALATE/CLOSE/REVOKE,必)、content(必)、requestId、version | {exceptionId, status, linkedRiskId?} | studentAffairs.dorm.exception.handle | AFFAIRS_DORM_EXCEPTION_HANDLE |

**调宿审批 data 示例（宿管终审通过）**：
```json
{
  "transferId": "4402", "status": "APPROVED", "statusLabel": "已通过，待执行迁移",
  "fromBed": {"building": "3号楼", "room": "302", "bed": "2"},
  "toBed": {"building": "5号楼", "room": "108", "bed": "1", "reserved": true, "reserveExpireAt": "2026-07-12T00:00:00+08:00"},
  "nextAction": "EXECUTE", "version": 3
}
```
**检查记录 data 示例（登记出夜不归宿异常）**：
```json
{"recordId": "r-771", "exceptionId": "e-208", "exceptionType": "NIGHT_ABSENT", "syncedTo": {"counselorId": "t-12", "messageType": "STATUS_CHANGED"}, "autoRiskHint": "该生30天内第2次夜不归宿，第3次将自动升级风险"}
```
**错误码**：409001 目标床位被占（乐观锁）/在途调宿重复/ESCALATED 状态直接关闭；403002 宿管跨楼栋（DORM_BUILDING scope）；422001 性别楼栋规则不符/涉及学生不在住名单。宿舍分配导入、检查导入见 §16。

---

## 12. 学生活动（13A-12，activity，志愿复用）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 91 | GET /api/v1/student-affairs/activities | 活动列表 | activityType/status/scope(否)、page/pageSize | list[{activityId,title,activityType,startAt,quota,enrolled,status}] | studentAffairs.activity.view | 无 |
| 92 | POST /api/v1/student-affairs/activities | 建活动/志愿项目（范围/人数/时间/地点/学时积分规则） | title(必)、activityType(enum,必)、scopeConfig(object,必)、quota(int,必)、startAt/endAt(必)、creditRule(object,否)、requestId | {activityId, status:"DRAFT"} | studentAffairs.activity.create | AFFAIRS_ACTIVITY_CREATE |
| 93 | POST /api/v1/student-affairs/activities/{activityId}/publish | 发布/取消活动 | action(enum PUBLISH/CANCEL,必)、reason(CANCEL必≥5字)、version、requestId | {activityId, status} | studentAffairs.activity.publish | AFFAIRS_ACTIVITY_PUBLISH |
| 94 | GET /api/v1/student-affairs/activities/{activityId}/participants | 报名/签到名单 | status(否)、page/pageSize | list[{studentNo,realName(脱敏),enrolledAt,checkedIn,approved}] | studentAffairs.activity.view | 无 |
| 95 | POST /api/v1/student-affairs/activities/{activityId}/participants/review | 报名审核（志愿类开启时） | studentIds[](必)、action(enum,必)、requestId | {approvedCount} | studentAffairs.activity.confirm | AFFAIRS_ACTIVITY_ENROLL_REVIEW |
| 96 | POST /api/v1/student-affairs/activities/{activityId}/confirm | 确认名单+生成学时/积分/志愿时长（进360+第二课堂） | adjustments[](否)、version、requestId | {activityId, status:"CONFIRMED", creditIssued} | studentAffairs.activity.confirm | AFFAIRS_ACTIVITY_CONFIRM |

**错误码**：409001 非 PUBLISHED 报名/满员/重复报名/CONFIRMED 后改名单；403002 范围外学生报名/辅导员操作他班活动；422001 时间倒挂/名额非法。学生报名/签到见 §17 移动端。

---

## 13. 家校联系（13A-13，home-school）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 97 | GET /api/v1/student-affairs/home-school/students/{studentId}/guardians | 监护人/紧急联系人（号码脱敏 `_mask_phone`） | 无 | list[{guardianId,name,relation,phoneMasked}] | studentAffairs.homeSchool.view | 无 |
| 98 | POST /api/v1/student-affairs/home-school/guardians/{guardianId}/reveal | 查看完整号码（原因必填，进审计） | reason(必,≥5字)、requestId | {guardianId, phoneFull} | studentAffairs.homeSchool.contact.reveal | SENSITIVE_VIEW |
| 99 | GET /api/v1/student-affairs/home-school/records | 联系/家访记录列表 | studentId/contactType/dateRange(否)、page/pageSize | list[{recordId,studentNo,contactType,contactedAt,resultSummary,linkedRiskId}] | studentAffairs.homeSchool.view | 无 |
| 100 | POST /api/v1/student-affairs/home-school/records | 登记联系结果（可关联风险，进360） | studentId(必)、guardianId(必)、contactType(enum,必)、content(必≥10字)、result(enum,必)、linkedRiskId(否)、requestId | {recordId} | studentAffairs.homeSchool.record.create | AFFAIRS_HOME_SCHOOL_CONTACT |

**错误码**：403001 无 reveal 权限点取完整号码；422001 reason 不足 5 字；403002 范围外学生。

---

## 14. 学工归档（13A-14，archive）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 101 | GET /api/v1/student-affairs/archive/batches | 归档批次列表 | schoolYear/status(否)、page/pageSize | list[{batchId,batchName,schoolYear,status,packageCount,missingCount}] | studentAffairs.archive.view | 无 |
| 102 | POST /api/v1/student-affairs/archive/batches | 建批次+启动生成（学年/范围/内容清单） | batchName(必)、schoolYear(必)、scopeConfig(object,必)、contentTypes[](必)、requestId | {batchId, status:"GENERATING"} | studentAffairs.archive.batch.manage | AFFAIRS_ARCHIVE_BATCH |
| 103 | GET /api/v1/student-affairs/archive/batches/{batchId}/packages | 批次内档案包列表（含缺件清单） | classId/missing(bool,否)、page/pageSize | list[{packageId,studentNo,realName(脱敏),completeness,missingItems[]}] | studentAffairs.archive.view | 无 |
| 104 | POST /api/v1/student-affairs/archive/packages/{packageId}/supplement | 辅导员补缺（补传材料） | itemType(enum,必)、fileIds[](必)、requestId | {packageId, completeness} | studentAffairs.archive.supplement | AFFAIRS_ARCHIVE_SUPPLEMENT |
| 105 | POST /api/v1/student-affairs/archive/batches/{batchId}/review | 学院完整性审查（通过/退回） | action(enum APPROVE/RETURN,必)、reason(RETURN必≥5字)、version、requestId | {batchId, status} | studentAffairs.archive.review | APPROVAL |
| 106 | POST /api/v1/student-affairs/archive/batches/{batchId}/confirm | 学工处确认归档（生成水印归档包+t_export_task 留痕） | version、requestId | {batchId, status:"ARCHIVED"} | studentAffairs.archive.batch.manage | AFFAIRS_ARCHIVE_CONFIRM |
| 107 | POST /api/v1/student-affairs/archive/packages/{packageId}/download | 归档包下载（用途登记+水印+审计） | purpose(必,≥5字)、requestId | {downloadUrl(限时), exportTaskId} | studentAffairs.archive.download | EXPORT/DOWNLOAD |

**错误码**：409001 ARCHIVED 批次内写操作（归档冻结）/非 SUPPLEMENTING 状态补缺；403001 无 psySensitive 请求含心理明细专项包；429001 下载限流；403002 跨学院审查。

---

## 15. 学工统计（13A 各业务统计口径）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 108 | GET /api/v1/student-affairs/stats/overview | 学工总览（请假/困难/奖助覆盖率/处分/心理关注/风险/谈话完成率/宿舍异常/活动参与率/德育积分分布/辅导员完成率） | semester(否)、collegeId(否,按 scope 限) | metricGroups[]（每指标含口径 key/值/更新频率标记/可下钻 drill） | studentAffairs.stats.view | 无 |
| 109 | GET /api/v1/student-affairs/stats/{metricGroup} | 分组明细下钻（leave/aid/funding/discipline/risk/talk/dorm/activity/counselor-kpi） | groupBy(enum COLLEGE/CLASS/GRADE,必)、semester/dateRange(否)、page/pageSize | breakdown[] + trend[] | studentAffairs.stats.view | 无 |
| 110 | POST /api/v1/student-affairs/stats/{metricGroup}/export | 统计导出（转发导出管线） | purpose(必≥5字)、filters(object) | {exportTaskId} | studentAffairs.stats.export | EXPORT |

**overview data 示例（节选）**：
```json
{
  "metricGroups": [
    {"group": "leave", "metrics": [
      {"key": "leaveStudentCount", "label": "请假人数", "value": 120, "caliber": "学期内状态曾达 APPROVED 的去重学生数", "sourceTable": "t_cs_leave", "refresh": "实时", "drill": "/api/v1/student-affairs/stats/leave"},
      {"key": "overdueUncancelled", "label": "逾期未销", "value": 4, "caliber": "当前 status=OVERDUE", "refresh": "实时", "drill": "/api/v1/student-affairs/stats/leave"}
    ]},
    {"group": "counselor-kpi", "metrics": [
      {"key": "todoCompletionRate", "label": "辅导员待办完成率", "value": "92.5%", "caliber": "期限内完成待办/全部到期待办", "refresh": "每日", "drill": "/api/v1/student-affairs/stats/counselor-kpi"}
    ]}
  ]
}
```
每个指标响应体自带口径（caliber）/来源/更新频率/可下钻标记，满足需求输入 §8"每个指标必须定义口径"的要求；角色过滤与范围过滤由服务端按 scope 注入。

实现方式 = 扩展既有 `stats_service` 聚合（速查 §7），辅导员维度走 scope 过滤；接入 Dashboard 角色 preset。**错误码**：429001 导出限流；403002 请求超出 scope 的 collegeId。

---

## 16. 导入导出（注册 domain，复用既有管线）

复用 `/api/v1/import/domain/{domain}/validate|confirm`（模板→dry-run 行级错误→批次事务确认，5000 行/20MB）与 `/api/v1/export/domain/{domain}`（用途≥5字、脱敏列、水印、t_export_task、5 次/分、5000 行、下载审计）。**不新建端点，仅注册以下 domain 配置**：

| domain | 方向 | 内容 | 敏感处理 |
|---|---|---|---|
| affairs_leave | 导出 | 请假记录 | 原因列脱敏可配 |
| affairs_aid | 导出 | 困难名单/等级 | 家庭经济列强制剔除或区间化；导出需二次确认 |
| affairs_funding | 导出 | 奖助名单/结果 | 金额/银行卡脱敏 |
| affairs_discipline | 导出 | 处分记录 | 仅结论字段，明细不出 |
| affairs_risk | 导出 | 风险台账 | 心理明细默认剔除 |
| affairs_dorm_allocation | 导入 | 宿舍分配（排宿结果批量导入） | 行级校验床位存在/空闲/性别 |
| affairs_dorm_inspection | 导入 | 宿舍检查记录批量导入 | 行级校验房间/学生 |
| affairs_activity_participants | 导出 | 活动名单/学时 | 姓名脱敏可配 |
| affairs_class_students | 导入 | 班级学生导入（班级管理） | 行级校验学号在籍 |
| affairs_archive_package | 导出 | 归档包 | 整包水印，见 #107 |

（计入接口条数：validate/confirm/export 为既有端点复用，不重复计数。）

---

## 17. 移动端接口（独立章）

### 17.1 学生端 `/api/v1/mobile/affairs/*`（token userType=STUDENT，student_id 恒从 token 取）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 错误码要点 | 审计 |
|---|---|---|---|---|---|---|
| 111 | GET /api/v1/mobile/affairs/my-leave | 我的请假列表+状态 | status(否)、cursor/pageSize | list[{leaveId,leaveType,startAt,endAt,status,statusLabel,canCancel,canCancelLeave,canExtend}] | 401001 | 无 |
| 112 | POST /api/v1/mobile/affairs/apply-leave | 发起请假（类型/起止/原因/材料） | leaveType(enum,必)、startAt/endAt(必,开始≥当前,结束>开始)、reason(必,10-500字)、fileIds[](按类型必)、requestId(必) | {leaveId, status:"SUBMITTED", approvalChainPreview[]} | 422001 字段校验；409001 时间重叠在途单/重复提交 | AFFAIRS_LEAVE_APPLY |
| 113 | POST /api/v1/mobile/affairs/leave/{leaveId}/withdraw | 撤回申请（审批终态前） | requestId | {leaveId, status:"CANCELLED"} | 409001 已终态；403002 非本人 | AFFAIRS_LEAVE_WITHDRAW |
| 114 | POST /api/v1/mobile/affairs/leave/{leaveId}/cancel-leave | 销假（返校证明+实际返校时间） | actualReturnAt(必)、proofFileIds[](必)、requestId | {leaveId, status:"WAIT_CANCEL_LEAVE"} | 409001 非 APPROVED/OVERDUE | AFFAIRS_LEAVE_CANCEL_APPLY |
| 115 | POST /api/v1/mobile/affairs/leave/{leaveId}/extension | 续假申请 | newEndAt(必,>原endAt)、reason(必≥10字)、fileIds[](否)、requestId | {leaveId, status:"EXTENSION_REVIEW"} | 409001 非 APPROVED/在途续假 | AFFAIRS_LEAVE_EXTEND |
| 116 | GET /api/v1/mobile/affairs/my-aid | 我的困难认定+资助申请（含可申请批次） | cursor/pageSize | identifications[] + fundingApplications[] + openBatches[] | 401001 | 无 |
| 117 | POST /api/v1/mobile/affairs/aid/apply | 困难认定申请（家庭经济+材料） | batchId(必)、familyEconomy(object,必)、fileIds[](必)、requestId | {applyId, status:"SUBMITTED"} | 409001 批次外/重复；422001 | AFFAIRS_AID_APPLY |
| 118 | POST /api/v1/mobile/affairs/funding/apply | 资助申请（奖/助/勤/贷统一入口，按 projectType 校验） | batchId(必)、projectType(enum,必)、payload(object,必)、fileIds[]、requestId | {applicationId, status:"SUBMITTED"} | 409001 资格拦截（message 具体原因）；422001 | AFFAIRS_FUNDING_APPLY |
| 119 | GET /api/v1/mobile/affairs/my-dorm | 我的宿舍（床位/室友/检查结果/调宿单状态） | 无 | bedInfo + roommates[](脱敏) + inspectionResults[] + transferStatus | 401001 | 无 |
| 120 | POST /api/v1/mobile/affairs/dorm/transfer | 发起调宿 | reason(必≥10字)、preferBuilding/preferRoom(否)、requestId | {transferId, status:"SUBMITTED"} | 409001 在途单；422001 | AFFAIRS_DORM_TRANSFER_APPLY |
| 121 | GET /api/v1/mobile/affairs/my-activities | 可报名+已报名活动/志愿 | tab(enum OPEN/MINE,必)、cursor/pageSize | list[{activityId,title,startAt,quota,enrolled,myStatus}] | 401001 | 无 |
| 122 | POST /api/v1/mobile/affairs/activities/{activityId}/enroll | 报名/取消报名 | action(enum ENROLL/CANCEL,必)、requestId | {activityId, myStatus} | 409001 满员/重复/已截止；403002 范围外 | AFFAIRS_ACTIVITY_ENROLL |
| 123 | POST /api/v1/mobile/affairs/activities/{activityId}/checkin | 活动签到（扫码/定位） | checkinCode(必)、location(否)、requestId | {checkedIn: true, checkedAt} | 409001 非进行中/重复签到 | AFFAIRS_ACTIVITY_CHECKIN |
| 124 | GET /api/v1/mobile/affairs/my-talk-summary | 我的谈话摘要（仅"已谈话"事实，不含内容） | cursor/pageSize | list[{talkId,talkTypeLabel,talkedAt,talkerName}] | 401001 | 无 |
| 125 | GET /api/v1/mobile/affairs/my-discipline | 我的处分状态（数量+文书状态，无明细，沿用 t_cs_discipline 约定） | 无 | {activeCount, records[{level,status,effectiveAt,removable}]} | 401001 | 无 |
| 126 | POST /api/v1/mobile/affairs/discipline/{caseId}/remove-apply | 处分解除申请（本人） | performanceDesc(必≥20字)、fileIds[](必)、requestId | {removeId, status:"REMOVE_REVIEW"} | 409001 未满期限/在途 | AFFAIRS_DISCIPLINE_REMOVE_APPLY |
| 127 | GET /api/v1/mobile/affairs/my-profile-summary | 本人学工摘要（德育积分/活动学时/资助状态/宿舍） | 无 | summary{}（全部本人视角，脱敏规则不适用本人基础字段，家庭经济仍区间显示可配） | 401001 | 无 |

**apply-leave data 示例**：
```json
{
  "leaveId": "3305", "status": "SUBMITTED", "statusLabel": "已提交",
  "approvalChainPreview": [
    {"nodeCode": "COUNSELOR_REVIEW", "assigneeName": "李老师", "reason": "≤3天辅导员终审"}
  ],
  "cancelLeaveDeadline": "2026-07-10T18:00:00+08:00"
}
```
**my-leave data 示例**：
```json
{
  "list": [
    {"leaveId": "3305", "leaveType": "SICK", "leaveTypeLabel": "病假", "startAt": "2026-07-08T08:00:00+08:00", "endAt": "2026-07-10T18:00:00+08:00", "days": 3, "status": "APPROVED", "statusLabel": "已批准", "canCancel": false, "canCancelLeave": true, "canExtend": true}
  ],
  "nextCursor": null
}
```
前端约定：全部写接口配 createSubmitLock 防连点；401 单飞刷新失败跳登录；409/422 业务错误透出 message 不兜底（realFirst）；403 显示无权限态；成功后本地刷新列表并失效缓存。

**学生端四类错误处理基线**（每页统一）：401→单飞刷新→失败跳登录；403→"无权限查看"态（不重试）；409→safeToast 透出 message（如"存在时间重叠的请假单"）；422→表单字段标红（details 字段级原因）。网络失败→MobileGlobalState error 态+重试按钮。

### 17.2 教师端 `/api/v1/mobile/teacher/affairs/*`（包装层：范围校验+审计+409）

| # | 方法/路径 | 用途 | 关键请求参数 | 返回 data 要点 | 错误码要点 | 审计 |
|---|---|---|---|---|---|---|
| 128 | GET /api/v1/mobile/teacher/affairs/workbench | 移动工作台（辅导员高频入口聚合） | 无 | todos / pendingLeave / riskStudents / overdueLeave / dormExceptions | 403001 非教职工 | 无 |
| 129 | GET /api/v1/mobile/teacher/affairs/leave-approvals | 待审请假列表 | cursor/pageSize | list[{leaveId,studentName(脱敏),leaveType,days,submittedAt,version}] | 无数据空列表 | 无 |
| 130 | POST /api/v1/mobile/teacher/affairs/leave/{leaveId}/approve | 移动审批通过 | comment(否)、version(必)、requestId | {leaveId, status, nextNode} | 409001 版本冲突/已处理；403002 范围外 | APPROVAL |
| 131 | POST /api/v1/mobile/teacher/affairs/leave/{leaveId}/reject | 移动驳回 | reason(必≥5字)、version、requestId | {leaveId, status:"REJECTED"} | 422001 reason 不足 | APPROVAL |
| 132 | POST /api/v1/mobile/teacher/affairs/leave/{leaveId}/cancel-leave/confirm | 移动销假确认 | action(enum,必)、actualReturnAt(CONFIRM必)、version、requestId | {leaveId, status} | 409001 非 WAIT_CANCEL_LEAVE | AFFAIRS_LEAVE_CLOSE |
| 133 | GET /api/v1/mobile/teacher/affairs/risk-students | 移动风险学生列表 | riskLevel/status(否)、cursor/pageSize | list[风险行]（心理来源收敛） | 无 | 无 |
| 134 | POST /api/v1/mobile/teacher/affairs/risk/{riskId}/handle | 移动风险处置（快速留痕/关闭） | handleType(enum,必)、content(必≥10字)、requestId | {riskId, status} | 409001 非责任人→403002 | AFFAIRS_RISK_HANDLE |
| 135 | POST /api/v1/mobile/teacher/affairs/talks/quick-record | 移动快速谈话记录（现场谈完即录） | studentId(必)、talkType(enum,必)、content(必≥20字)、needFollowUp(bool,必)、requestId | {talkId, status:"COMPLETED"} | 403002 范围外学生 | AFFAIRS_TALK_RECORD |
| 136 | GET /api/v1/mobile/teacher/affairs/dorm-exceptions | 移动宿舍异常列表（辅导员认领入口） | status(否)、cursor/pageSize | list[异常行] | 无 | 无 |
| 137 | POST /api/v1/mobile/teacher/affairs/dorm-exceptions/{exceptionId}/handle | 移动异常处置 | action(enum,必)、content(必)、requestId、version | {exceptionId, status} | 409001 状态冲突 | AFFAIRS_DORM_EXCEPTION_HANDLE |

**teacher workbench data 示例**：
```json
{
  "todos": {"total": 7, "overdue": 1},
  "pendingLeave": [{"leaveId": "3308", "studentName": "王*", "leaveType": "PERSONAL", "days": 2, "submittedAt": "2026-07-05T09:00:00+08:00", "version": 1}],
  "riskStudents": {"total": 6, "high": 1},
  "overdueLeave": [{"leaveId": "3290", "studentName": "赵*", "overdueHours": 30}],
  "dormExceptions": {"unclaimed": 2}
}
```
移动端"必须回 PC"边界（对齐需求输入 §11 移动端设计）：请假移动端全流程（长假审批建议回 PC 看完整材料）；困难认定/资助申请移动端可发起，评审回 PC；处分登记与审批仅 PC；归档仅 PC；风险快速处置移动端可用，关闭需填结论建议 PC。

**与既有移动端接口的关系**：

| 既有接口 | 关系 | 说明 |
|---|---|---|
| POST /api/v1/mobile/teacher/approvals/{id}/approve\|reject | **复用（底座）** | 13A 审批任务同样落 t_workflow_task，通用审批中心继续可审全部学工任务；`/mobile/teacher/affairs/leave/*` 是带请假上下文（附件/天数/销假）的**业务包装**，二者操作同一任务，乐观锁保证不双审（后到者 409） |
| GET /api/v1/mobile/teacher/student/{id}（学生360聚合） | **复用+扩展** | 聚合端点扩展读取 affairs 域记录与 StageEvent，学工不另建学生详情端点 |
| /api/v1/mobile/campus-service/apply（在校服务请假提交） | **别名过渡→废弃** | 见 §18 迁移策略：M1 起该路径内部转写新 affairs_leave 模型（双写别名），M3 小程序切至 /mobile/affairs/apply-leave，M4 起旧路径返回 410 前先经一个版本的 301 语义提示（响应 message 引导），最终下线 |
| t_unified_todo / t_unified_message 既有"标已读"等端点 | **复用** | 学工待办与消息不建新端点 |

---

## 18. 与既有路径/模型冲突盘点

### 18.1 campus-service 请假（t_cs_leave）与新 leave API 的共存/迁移（重点）

**现状**：campus-service 已有 `t_cs_leave`（状态仅 PENDING_REVIEW/APPROVED/RETURNED，approve/return API + 批量），移动端学生提交（防重复 409）。

**决策：扩展 t_cs_leave + 必要子表**（与 C3 §3.1、融合设计 §5.1 一致），理由：需求输入 §1 业务域边界 + 速查 §6 不得平行再建 + t_cs_leave 已有 409/审批/pytest 覆盖。

| 阶段 | 内容 |
|---|---|
| M0 契约冻结 | 冻结本册 leave API；主单 = **t_cs_leave 加列**（affairs_status 等）；子表 = cancel_record / extension；附件 = t_file_object |
| M1 兼容上线 | 新 API 上线；`/mobile/campus-service/apply` 保留为**别名**，内部写同一 t_cs_leave 行（状态双列投影：affairs_status 权威，旧 status 兼容只读视图） |
| M2 存量补齐 | 存量 t_cs_leave **无需迁新主表**：Alembic 加列 + affairs_status 回填脚本（PENDING_REVIEW→COUNSELOR_REVIEW 等）+ 对账报告（行数+sha256） |
| M3 前端切换 | 小程序请假页切 `/mobile/affairs/*`；PC 在校服务请假菜单指向 /admin/student-affairs/leave（旧列表可读，写走新端点） |
| M4 收敛 | 别名路径加 Deprecation header；旧 approve/return 写操作引导新端点；**t_cs_leave 始终为唯一主单**，不下线 |

**冲突规则**：同一学生同时段重复提交 → 以 t_cs_leave 时间重叠校验拦截（409001 IDEMPOTENCY_CONFLICT）；别名端点与新端点共用同一校验与同一主表。

### 18.2 其余冲突项

| 冲突点 | 现状 | 策略 |
|---|---|---|
| t_cs_discipline | 处分骨架（record_status ACTIVE，学生端只回数量） | 新 `t_affairs_discipline_case/decision/material/remove_apply/review` 为流程主表；t_cs_discipline 保留为**结论投影表**（生效/解除时同步写入），既有读端点不动；归属关系：affairs 为源，cs 为投影 |
| t_cs_mental_record | 心理骨架（强权限） | 13A 不建新心理记录表，风险/谈话以外键引用之；心理明细读取全部走其既有权限约束 + PSY_STUDENT scope |
| t_cs_dorm_record / t_cs_dorm_exception + orientation 分宿 | 宿舍骨架 | 房源/排宿/调宿新表 `t_affairs_dorm_*`；入住结果继续写 t_cs_dorm_record（投影），异常扩展 t_cs_dorm_exception（加 status/handle 字段而非建新表）；迎新分宿（orientation building/room/dorm_status）作为排宿初始数据源导入 |
| /api/v1/stats/* | 已有 overview/lifecycle/risk/workbench | 学工统计不占用 /api/v1/stats/*，走 /api/v1/student-affairs/stats/*，实现层复用 stats_service |
| /api/v1/mobile/teacher/approvals | 通用审批中心 | 复用为底座（见 §17.2），学工业务包装端点不与其重名 |
| t_acad_warning（学业预警） | academic 域已实现 | 学工风险"学业来源"记录引用其 ID，不复制不新建预警表；状态双向同步（其 CLOSED → 风险源侧提示可关闭） |
| PC 路由 /admin/student-affairs/* | 未占用 | 新模块目录 frontend/src/modules/student-affairs/，与现有模块无冲突；与 /admin/campus-service 请假菜单关系见 M3 |
| 权限点前缀 studentAffairs.* | 未占用 | 与既有权限码（如 student.profile.view）无重叠；counselor 四接口权限点按需求书命名保留 studentAffairs.counselor.* |
| 平台规则中心 | 已存在 /admin/platform + safe_rule | 长假天数阈值、销假宽限期、公示天数、处分最短解除期限、活动自动确认开关等全部注册为 safe_rule 项，不新建管理端 |

---

## 19. 核心链路验收用例（契约级，每链路 ≥4 条，含重复提交与越权）

**链路 A：学生请假移动端全流程**
1. 学生提交普通请假（#112）→ 生成单据 SUBMITTED→COUNSELOR_REVIEW；辅导员 #128 工作台与 t_unified_todo 出现待办；学生 #111 见"待审批"。
2. 辅导员 #130 审批通过 → 状态 APPROVED；学生收 WORKFLOW_RESULT；360 时间线（#7）出现请假记录。
3. 学生重复提交时间重叠请假（#112 二次调用）→ 仅存在一条单据，第二次返回 409/409001，message 说明重叠单号。
4. 学生 A 以 A 的 token 请求 B 的请假详情/销假 → 403/403002（student_id 从 token 取，路径 ID 不可信），写 PERMISSION_DENIED 审计。
5. 到期未销假 → 定时任务转 OVERDUE，生成风险记录（#64 可见，source=LEAVE_ABNORMAL），辅导员收 RISK_ALERT。

**链路 B：辅导员移动审批并发**
1. 同一请假任务 PC（#20）与移动端（#130）同时提交审批 → 先到成功，后到 409 APPROVAL_VERSION_CONFLICT。
2. 辅导员审批非负责班级学生（伪造 leaveId）→ 403002 + 审计。
3. 驳回不填原因或原因 <5 字 → 422001，任务状态不变。
4. demo-school 租户审批 → 403001（只读锁），响应引导 sandbox。

**链路 C：困难认定到助学金联动**
1. 批次开放→学生 #117 申请→逐级 #34 评审→公示期满→APPROVED 入困难库（#37 可查）。
2. 非困难库学生 #118 申请助学金 → 409001（资格拦截）。
3. 班主任查看认定名单不含家庭经济明细；请求完整值无 sensitiveView → 403001。
4. 资助老师导出困难名单 → 用途必填、水印、t_export_task 留痕、SENSITIVE 二次确认。

**链路 D：处分生效到毕业联动**
1. 登记→逐级审批→EFFECTIVE：学生 #125 可见状态；奖学金推荐名单（#42）checkResult.disciplineOk=false。
2. 未满最短期限发起解除（#126）→ 409001 带最早可申请日期。
3. 解除终审 REMOVED → 资格解冻；360 保留处分历史与解除记录双事件。
4. 学生请求处分明细接口 → 403001（仅回数量与文书状态）。

---

## 20. 接口清单汇总

- PC 管理端（require_staff）：#1–#110，共 **110** 条（其中 §16 导入导出为既有端点注册 domain，不计新增端点数）。
- 学生小程序 `/api/v1/mobile/affairs/*`：#111–#127，共 **17** 条。
- 教师移动端 `/api/v1/mobile/teacher/affairs/*`：#128–#137，共 **10** 条。
- **合计 137 条接口契约**；另有复用不新增的既有端点 5 组（approvals、mobile/teacher/approvals、import/export domain、unified todo/message、mobile teacher student/{id} 聚合）。
- 覆盖需求输入 §2.1–§2.14 全部列名接口（dashboard、counselor 四接口、classes、leave 全套、aid 全套、funding 全套、discipline 全套、risk、talks、dormitory、activity、home-school、archive、统计、导入导出 domain），并补齐需求未列明的缺口（销假确认、逾期处置、规则配置、公示、勤工考核、贷款核对、归档下载、移动端全链路）。
