# 13B-教务中心 · API 契约草案

> 文档性质：13B 教务中心全量接口契约草案（设计文档，不含代码；实现前以此为冻结基线评审）
> 需求来源：`docs/modules/_13-需求输入-V1.1.md` §3（全部接口覆盖并补齐）
> 集成对齐：`docs/modules/_13-现有系统集成事实速查.md`（包络/错误码/鉴权/租户/Workflow/导入导出全部沿用，禁止另造）
> 配套文档：`13B-教务中心状态机与权限矩阵.md`（状态机 SM-01～SM-14、权限点、数据范围，本文简称「矩阵文档」）
> 冲突盘点依据：后端实际路由 `backend/app/api/v1/academic.py`、`backend/app/api/v1/mobile.py`、`backend/app/api/v1/router.py`（2026-07-05 核对）
> 生成日期：2026-07-05

---

## 一、总则（沿用现有，速查 §1/§2，本节只引用不重定义）

1. **响应包络（冻结）**：`{ code(数字), bizCode(字符串), message, data, traceId, timestamp }`；成功 `code=0 / bizCode=SUCCESS`。
2. **错误码（冻结）**：401001 UNAUTHORIZED / 403001 NO_PERMISSION / 403002 NO_DATA_SCOPE / 404001 DATA_NOT_FOUND / 409001 DATA_CONFLICT·APPROVAL_VERSION_CONFLICT·IDEMPOTENCY_CONFLICT / 422001 VALIDATION_ERROR / 429001 RATE_LIMITED / 400001 BAD_REQUEST。业务错误绝不 500。
3. **鉴权**：真实登录 Token（claims：userId/userType/tid/tenantId/activeContextId/currentRoleCode，学生附 studentNo）；PC 一律 `require_staff`（学生令牌 403）；学生只走 `/api/v1/mobile/*`。tenant_id 前端永不传，后端从上下文解析并行级过滤。demo-school 只读锁、到期租户只读中间件对本域全部写操作生效。
4. **通用约定**：列表分页 `page/pageSize`，返回 `data.list/total/page/pageSize`；写操作带 `request_id` 幂等；审批带 `version` 乐观锁；驳回/退回 `reason≥5 字`；文件一律传 `file_id`；通知写 `t_unified_todo/t_unified_message`；审计走 `audit_log.record()` + 域级 `t_aa_audit_trail`；审批复用 `t_workflow_instance/t_workflow_task`（新增 workflow_code 清单见矩阵文档各 SM）。
5. **数据范围**：全部列表/详情/写操作经 `getAcademicScope(user)` / `canAccessAcademicStudent()` 裁定（矩阵文档 §17），看得见=能处理。

---

## 二、路径冲突盘点（必读，先于任何实现）

### 2.1 现有 `/api/v1/academic/*` 已占端点（以代码为准）

现有 academic 域 = **学业过程域**（过程性学业数据台账），实际路由如下：

| 既有端点 | 语义 | 与教务中心关系 |
|---|---|---|
| GET /academic/dashboard | 学业看板 | **冲突①**：教务中心首页同名诉求 |
| GET/POST/PUT /academic/students、POST /students/{sid}/void | 学业台账（过程性记录） | **冲突②**：与「学籍管理」易混淆 |
| GET/POST/PUT /academic/grades、POST /grades/{gid}/void | 过程性成绩流水（t_acad_grade） | **冲突③**：与教务中心「成绩管理」职责重叠 |
| GET /academic/credits | 学分修读聚合 | 无冲突，教务中心直接读用 |
| GET/POST /academic/makeups、PUT /makeups/{mid}/status | 补考台账骨架（t_acad_makeup，**复用既有 academic 学业过程模块**） | **冲突④**：13B 流程化走 `/academic-affairs/makeup/*`，终态回写 t_acad_makeup |
| GET /academic/retakes、PUT /retakes/{rid}/status | 重修台账骨架（t_acad_retake，**复用既有 academic 学业过程模块**） | **冲突④** 同上；13B 流程化走 `/academic-affairs/retake/*` |
| GET/POST /academic/warnings + {wid}/level·void·assign·remind·interventions·close·escalate | 学业预警（t_acad_warning，机制完整） | **非冲突**：13B 明确**复用扩展** |
| GET /academic/audit-logs | 学业域审计 | 无冲突，共用 |
| GET /api/v1/mobile/academic/my | 学生「我的学业过程」聚合 | 移动端共存，见 §五 |

### 2.2 共存方案（采纳速查 §10 建议）

**总原则：不迁移、不破坏既有学业过程端点；教务中心 13B 新建端点全部走 `/api/v1/academic-affairs/*`**（terms / calendar / enrollments / status-change / programs / courses / teaching-tasks / schedule / schedule-change / course-selection / exams / grade-tasks / grade-change / makeup / retake / exemption / graduation-audit / archive），与既有学业过程端点互补。仅 4 组冲突逐一裁定：

| # | 冲突 | 裁定 | 别名与迁移计划 |
|---|---|---|---|
| ① | dashboard | 既有 `GET /academic/dashboard`（**复用既有 academic 学业过程模块**）保留为**学业看板**；教务中心首页新开 `GET /academic-affairs/dashboard` | 物理隔离，零冲突；P3 起可为既有端点提供别名 `GET /academic/process-dashboard`（双路由同 handler，可选） |
| ② | students | 既有 `/academic/students`（**复用既有 academic 学业过程模块**）保留为**学业台账**；教务中心学籍管理不占该路径——学籍状态读学生主档，注册走 `/academic-affairs/enrollments`，异动走 `/academic-affairs/status-change` | 无需迁移；PC 菜单命名区分「学业过程-学业台账」与「教务中心-学籍管理」（路由 /admin/academic vs /admin/academic-affairs） |
| ③ | grades | 既有 `/academic/grades`（**复用既有 academic 学业过程模块**）保留为过程性成绩流水**读端点**；教务中心成绩管理走 `/academic-affairs/grade-tasks/*`（任务制录入-审核-发布）与 `/academic-affairs/grade-change`；**发布时回写 t_acad_grade**，既有 GET 语义不变 | 迁移计划：教务中心成绩流程上线（13B-P5）后，既有 POST/PUT /academic/grades 收敛为仅系统内部回写与补录特批（前端下线入口，接口加权限点收紧）；对外正式成绩以 grade-tasks 发布为准 |
| ④ | makeups/retakes | 既有台账端点（**复用既有 academic 学业过程模块**）保留为**查询与台账**；流程化走新 `/academic-affairs/makeup/*`、`/academic-affairs/retake/*`，终态回写 t_acad_makeup/t_acad_retake | 迁移计划：流程上线后 `PUT /makeups/{mid}/status`、`PUT /retakes/{rid}/status` 仅限教务处特批直改（收权限点+强制原因），P3 评估弃用 |

**预警（非冲突）**：13B 不新建任何 warnings 端点重复既有能力，只新增规则/扫描 3 个端点（§3.14），处置动作全部沿用既有 assign/remind/interventions/close/escalate/void。

**PC 路由与菜单**：教务中心前端为 `/admin/academic-affairs/*`，与现有 `/admin/academic`（学业过程）并列两个菜单；学业过程菜单保留“台账/流水”定位，教务中心为流程主战场，二者在成绩、预警页面互设跳转。

**新表命名**：教务中心新表一律 `t_aa_*`，与既有 `t_acad_*`（学业过程）映射关系在各接口「落表」栏注明。

### 2.3 盘点结论

- 教务中心 **13 组新子路径与既有零重叠**，可直接新增；
- **4 组命名冲突**（dashboard/students/grades/makeups+retakes）全部通过「新子路径 + 既有端点保留 + 回写联动 + 分期收敛」解决，**无需任何 breaking change**；
- 预警域**完全复用**既有 t_acad_warning 全部端点，仅扩展来源与规则；
- 移动端与既有 `GET /mobile/academic/my` 共存关系见 §五。

---

## 三、PC 端接口契约（前缀 `/api/v1`，均 require_staff）

> 表格列说明：参数只列业务关键项（分页/request_id/version 等通用项不重复）；「审计」✓ 表示写 t_security_audit_log（+域级 trail）；权限点全称前缀 `academicAffairs.` 省略。错误码场景只列本域特有情形，通用防护见矩阵文档 §0.2。

### 3.1 教务首页

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-001 | GET /academic-affairs/dashboard | 教务中心角色化首页（教务处/学院教务员/任课教师视图；学生视图走移动端） | semester、dateRange（角色/范围从上下文取） | dashboard.view | ✗ |

返回 `data` 示例（教务处视图，preset 按 currentRoleCode）：
```json
{
  "roleView": "ACADEMIC_ADMIN",
  "summaryCards": [
    {"key": "teachingTaskRate", "label": "教学任务完成率", "value": 0.92},
    {"key": "scheduleRate", "label": "排课完成率", "value": 0.88, "extra": {"conflicts": 3}},
    {"key": "selectionRate", "label": "选课进度", "value": 0.76},
    {"key": "gradeInputRate", "label": "成绩录入进度", "value": 0.41},
    {"key": "statusChangePending", "label": "学籍异动待审", "value": 12},
    {"key": "warningCount", "label": "学业预警数", "value": 57},
    {"key": "gradAbnormal", "label": "毕业资格异常数", "value": 9}
  ],
  "todoList": [{"todoId": 901, "todoType": "WORKFLOW_TODO", "title": "培养方案审核：软件技术2026", "dueAt": "2026-07-10"}],
  "workflowPending": {"statusChange": 12, "gradeReview": 5, "scheduleChange": 3},
  "drillLinks": {"warnings": "/admin/academic-affairs/warnings", "gradAudit": "/admin/academic-affairs/graduation-audit"}
}
```
错误码场景：无数据范围角色访问 → 403002（学生令牌进 PC → 403001）。

### 3.2 学年学期与校历（SM-01）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-002 | GET /academic-affairs/terms | 学期列表（状态/学年筛选） | schoolYear、status | term.view | ✗ |
| AC-003 | POST /academic-affairs/terms | 新建学年学期（DRAFT） | schoolYear、termNo、startDate、endDate | term.manage | ✓ |
| AC-004 | GET /academic-affairs/terms/{id} | 学期详情（含校历摘要） | — | term.view | ✗ |
| AC-005 | PUT /academic-affairs/terms/{id} | 编辑（仅 DRAFT 全量；PUBLISHED 仅微调字段） | 同 AC-003 + 微调字段 | term.manage | ✓ |
| AC-006 | POST /academic-affairs/terms/{id}/publish | 发布（完整性校验） | — | term.publish | ✓ |
| AC-007 | POST /academic-affairs/terms/{id}/freeze | 冻结 | reason≥5 字 | term.freeze | ✓ |
| AC-008 | POST /academic-affairs/terms/{id}/unfreeze | 解冻 | reason≥5 字 | term.freeze | ✓ |
| AC-009 | POST /academic-affairs/terms/{id}/archive | 归档 | — | term.archive | ✓ |
| AC-010 | GET /academic-affairs/terms/{id}/calendar | 校历明细（教学周/考试周/实习周/节假日/调休） | weekType | term.view | ✗ |
| AC-011 | PUT /academic-affairs/terms/{id}/calendar | 批量维护校历（DRAFT 全量 / PUBLISHED 仅节假日调休） | events[]（type/date/desc） | term.manage | ✓ |
| AC-012 | GET /academic-affairs/time-slots | 作息节次查询 | termId、campus | term.view | ✗ |
| AC-013 | PUT /academic-affairs/time-slots | 作息节次维护 | slots[]（no/start/end/campus） | term.manage | ✓ |

AC-006 返回 `data` 示例：
```json
{"termId": 11, "status": "PUBLISHED", "publishedAt": "2026-07-05T10:00:00+08:00", "notified": {"todoCount": 128, "channels": ["PUBLISHED_NOTICE"]}}
```
错误码场景：教学周有空洞发布 → 422001（返回行级 gaps）；已发布结构性修改 → 409001；存在 PUBLISHED 排课批次改节次 → 409001。

### 3.3 学籍注册（入学注册 / 学年注册，SM-02 受控入口）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-014 | GET /academic-affairs/enrollments/batches | 注册批次列表 | termId、batchType(ENTRANCE/ANNUAL)、status | enrollment.view | ✗ |
| AC-015 | POST /academic-affairs/enrollments/batches | 建注册批次（范围：年级/学院；截止时间） | batchType、termId、scope、deadline | enrollment.manage（教务处建） | ✓ |
| AC-016 | GET /academic-affairs/enrollments | 批次内学生注册名单（系统校验列：报到/缴费/材料） | batchId、collegeId、checkStatus | enrollment.view | ✗ |
| AC-017 | POST /academic-affairs/enrollments/confirm | 学院批量确认注册（核身份/专业/班级） | batchId、studentIds[]、remark | enrollment.manage | ✓ |
| AC-018 | POST /academic-affairs/enrollments/batches/{id}/submit | 学院提交名单至教务处 | — | enrollment.manage | ✓ |
| AC-019 | POST /academic-affairs/enrollments/batches/{id}/review | 教务处审核（通过→批量置 REGISTERED，联动 360/各域同步） | action(approve/return)、reason | enrollment.review | ✓ |
| AC-020 | GET /academic-affairs/enrollments/unregistered | 未注册清单（截止后定时生成，联动预警） | batchId、collegeId | enrollment.view | ✗ |

AC-019 通过返回 `data` 示例：
```json
{"batchId": 3, "approved": 1260, "statusChangedTo": "REGISTERED", "syncedModules": ["studentAffairs", "internship", "graduationDesign", "employment"], "stageEventsWritten": 1260}
```
错误码场景：名单含非 PENDING_REGISTER/ACTIVE 学生 → 422001 行级；跨学院确认 → 403002；批次已审再审 → 409001 APPROVAL_VERSION_CONFLICT。

### 3.4 学籍异动（SM-03，Workflow）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-021 | GET /academic-affairs/status-change | 异动单列表（按范围过滤） | changeType、status、collegeId、studentNo | statusChange.view | ✗ |
| AC-022 | GET /academic-affairs/status-change/{id} | 异动详情（原因全文按审批链/权限点控制，脱敏规则见矩阵 §16.1） | — | statusChange.view | ✓（看完整原因） |
| AC-023 | POST /academic-affairs/status-change | PC 代发起（学院代发退学等；学生自发走移动端 AC-134） | studentId、changeType、reason、fileIds[]、targetMajorId | statusChange.apply | ✓ |
| AC-024 | POST /academic-affairs/status-change/{id}/approve | 节点通过（辅导员/转出院/转入院/学院/教务处，节点由 workflow 裁定） | version、comment | statusChange.review | ✓ |
| AC-025 | POST /academic-affairs/status-change/{id}/reject | 节点驳回 | version、reason≥5 字 | statusChange.review | ✓ |
| AC-026 | POST /academic-affairs/status-change/{id}/return | 退回补材料 | version、reason≥5 字 | statusChange.review | ✓ |
| AC-027 | POST /academic-affairs/status-change/{id}/cancel | 撤销（终审前，本人或代发起学院） | reason | statusChange.apply | ✓ |

AC-024 终审通过返回 `data` 示例（转专业）：
```json
{
  "changeId": 77, "changeType": "TRANSFER_MAJOR", "status": "APPROVED",
  "effect": {"studentStatus": "TRANSFER_MAJOR", "newMajorId": 12, "newClassId": 305, "programVersionRebound": "2025-软件技术-v2"},
  "notified": ["STATUS_CHANGED:student", "STATUS_CHANGED:counselor"], "stageEventId": 8891
}
```
错误码场景：非 SUSPENDED 提复学 → 409001；在途同类异动重复提交 → 409001 IDEMPOTENCY_CONFLICT；窗口期外转专业 → 422001；审批人跨院操作 → 403002。

### 3.5 培养方案（SM-04，版本化）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-028 | GET /academic-affairs/programs | 方案列表（专业/年级/状态/版本） | majorId、grade、status | program.view | ✗ |
| AC-029 | POST /academic-affairs/programs | 新建方案（DRAFT，v1） | majorId、grade、totalCredit、modules[]（课程/学分/学时/开课学期/性质）、graduationRequirements | program.edit | ✓ |
| AC-030 | GET /academic-affairs/programs/{id} | 方案详情（含模块树/学分汇总） | — | program.view | ✗ |
| AC-031 | PUT /academic-affairs/programs/{id} | 编辑（仅 DRAFT/RETURNED） | 同 AC-029 | program.edit | ✓ |
| AC-032 | GET /academic-affairs/programs/{id}/versions | 版本链（含各版本绑定学生数） | — | program.view | ✗ |
| AC-033 | POST /academic-affairs/programs/{id}/new-version | ENABLED 方案派生新版本（复制为 DRAFT，version+1） | changeNote≥10 字 | program.edit | ✓ |
| AC-034 | POST /academic-affairs/programs/{id}/submit | 提交学院审（合法性校验四条：不重复/学分达标/学期合法/课程库 ENABLED） | — | program.edit | ✓ |
| AC-035 | POST /academic-affairs/programs/{id}/review | 学院/教务处审核节点（node 由 workflow 裁定） | action(approve/return)、version、reason | program.collegeReview / program.academicReview | ✓ |
| AC-036 | POST /academic-affairs/programs/{id}/publish | 教务处发布（审核通过后） | — | program.publish | ✓ |
| AC-037 | POST /academic-affairs/programs/{id}/enable | 启用并绑定专业+年级学生（生成绑定关系，进 360） | bindScope（grade/classIds） | program.enable | ✓ |
| AC-038 | POST /academic-affairs/programs/{id}/freeze | 冻结 | reason≥5 字 | program.freeze | ✓ |
| AC-039 | POST /academic-affairs/programs/{id}/unfreeze | 解冻 | reason≥5 字 | program.freeze | ✓ |
| AC-040 | POST /academic-affairs/programs/{id}/disable | 停用（历史学生仍按本版审核） | reason≥5 字 | program.disable | ✓ |

AC-037 返回 `data` 示例：
```json
{"programId": 21, "version": 2, "status": "ENABLED", "bound": {"grade": "2026", "studentCount": 412}, "oldVersionPolicy": "已绑定学生保持 v1，不迁移"}
```
错误码场景：ENABLED 直接 PUT → 409001（提示 new-version）；引用非 ENABLED 课程提交 → 422001 行级；同（专业,年级）重复 ENABLED → 409001。

### 3.6 课程库（SM-05）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-041 | GET /academic-affairs/courses | 课程库检索（编号/名称/类别/性质/状态） | keyword、category、nature、status | course.view | ✗ |
| AC-042 | POST /academic-affairs/courses | 新增课程（DRAFT） | courseCode、courseName、category、nature、credit、hoursTheory、hoursPractice、applicableMajors[]、prerequisites[]、ownerId | course.edit | ✓ |
| AC-043 | GET /academic-affairs/courses/{id} | 课程详情（含被引用方案清单） | — | course.view | ✗ |
| AC-044 | PUT /academic-affairs/courses/{id} | 编辑（仅 DRAFT/RETURNED） | 同 AC-042 | course.edit | ✓ |
| AC-045 | POST /academic-affairs/courses/{id}/submit | 提交学院审 | — | course.edit | ✓ |
| AC-046 | POST /academic-affairs/courses/{id}/review | 学院/教务处审核（教务通过即 ENABLED） | action、version、reason | course.collegeReview / course.academicReview | ✓ |
| AC-047 | POST /academic-affairs/courses/{id}/disable | 停用（校验无 ENABLED 方案/在途任务引用） | reason≥5 字 | course.disable | ✓ |
| AC-048 | POST /academic-affairs/courses/{id}/new-version | ENABLED 课程派生新版本 | changeNote | course.edit | ✓ |

错误码场景：编号租户内重复 → 409001；先修课非库内 ENABLED → 422001；被引用停用 → 409001（data 返回引用清单）。

### 3.7 教学任务（SM-06）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-049 | GET /academic-affairs/teaching-tasks/batches | 学期任务批次列表 | termId、status | teachingTask.view | ✗ |
| AC-050 | POST /academic-affairs/teaching-tasks/batches | 建学期任务批次 | termId、deadline | teachingTask.manage | ✓ |
| AC-051 | POST /academic-affairs/teaching-tasks/batches/{id}/generate | 按 ENABLED 方案生成应开课程任务 | scope（collegeIds/grades） | teachingTask.manage | ✓ |
| AC-052 | GET /academic-affairs/teaching-tasks | 任务列表（按范围：学院/专业/本人） | batchId、status、courseCode、teacherId | teachingTask.view | ✗ |
| AC-053 | GET /academic-affairs/teaching-tasks/{id} | 任务详情（课程/教学班/人数/教师/状态轨迹） | — | teachingTask.view | ✗ |
| AC-054 | PUT /academic-affairs/teaching-tasks/{id} | 学院核对：调教学班/容量/分配教师（方案外课程必填说明） | classIds[]、capacity、teacherId、outOfProgramNote | teachingTask.assign | ✓ |
| AC-055 | POST /academic-affairs/teaching-tasks/{id}/leader-confirm | 专业负责人确认 | version | teachingTask.leaderConfirm | ✓ |
| AC-056 | POST /academic-affairs/teaching-tasks/{id}/teacher-confirm | 教师确认接受（移动端包装 AC-148） | version | teachingTask.teacherConfirm | ✓ |
| AC-057 | POST /academic-affairs/teaching-tasks/{id}/dispute | 教师异议退回学院 | reason≥5 字 | teachingTask.teacherConfirm | ✓ |
| AC-058 | POST /academic-affairs/teaching-tasks/batches/{id}/submit | 学院整批提交（校验：全确认、无缺教师） | collegeId | teachingTask.assign | ✓ |
| AC-059 | POST /academic-affairs/teaching-tasks/batches/{id}/review | 教务处审核（通过→批内任务 READY，写 COURSE scope） | action、version、reason | teachingTask.review | ✓ |

AC-059 通过返回 `data` 示例：
```json
{"batchId": 5, "collegeId": 2, "approvedTasks": 86, "taskStatus": "READY", "courseScopeWritten": 74, "warnings": [{"taskId": 512, "type": "CAPACITY_LT_CLASS", "note": "容量40<班级人数43，已留痕强制通过"}]}
```
错误码场景：缺教师提交 → 422001 行级；批内有未确认任务提交 → 409001；READY 后直改 → 409001；跨学院提交 → 403002。

### 3.8 排课与课表发布（SM-07）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-060 | GET /academic-affairs/schedule/batches | 排课批次列表 | termId、status | schedule.view | ✗ |
| AC-061 | POST /academic-affairs/schedule/batches | 建排课批次（前置校验：校历 PUBLISHED/作息已配） | termId、rules | schedule.manage | ✓ |
| AC-062 | POST /academic-affairs/schedule/batches/{id}/load-resources | 载入资源（READY 任务/教室/教学班/教师不可用时间） | — | schedule.manage | ✓ |
| AC-063 | GET /academic-affairs/schedule/items | 课位查询（排课工作台数据源） | batchId、collegeId、teacherId、roomId、classId | schedule.view / schedule.manage | ✗ |
| AC-064 | PUT /academic-affairs/schedule/items/{id} | 手动排课/调整课位（实时冲突检测，返回冲突明细） | dayOfWeek、slotNo、weeks[]、roomId | schedule.manage | ✓ |
| AC-065 | POST /academic-affairs/schedule/batches/{id}/conflict-check | 全量冲突检测（9 类：教师/班级/教室/时间/容量/类型/校区/不可用/周学时） | scope | schedule.manage | ✓ |
| AC-066 | GET /academic-affairs/schedule/batches/{id}/conflicts | 冲突报告（HARD/SOFT 分级，责任学院） | level、collegeId、resolved | schedule.view | ✗ |
| AC-067 | POST /academic-affairs/schedule/conflicts/{id}/resolve | 冲突处理登记（改课位或备注豁免） | action(adjust/waive)、note≥5 字 | schedule.conflictHandle | ✓ |
| AC-068 | POST /academic-affairs/schedule/batches/{id}/pre-publish | 预发布（校验 HARD=0；推教师确认待办、开学生预览） | — | schedule.prePublish | ✓ |
| AC-069 | POST /academic-affairs/schedule/batches/{id}/confirm | 教师确认本人课表 / 异议（移动可办） | action(confirm/dispute)、reason | schedule.teacherConfirm | ✓ |
| AC-070 | POST /academic-affairs/schedule/batches/{id}/publish | 正式发布（确认率阈值或强制，留痕） | force、forceReason | schedule.publish | ✓ |
| AC-071 | GET /academic-affairs/schedule/views | 课表视图（viewType=class/teacher/room/major，周/学期粒度） | viewType、refId、termId、week | schedule.view | ✗ |

AC-065 返回 `data` 示例：
```json
{"batchId": 8, "checkedItems": 2140, "conflicts": {"hard": 3, "soft": 11},
 "top": [{"conflictId": 91, "type": "TEACHER_TIME", "level": "HARD", "detail": "王某周三3-4节两教学班重叠", "ownerCollegeId": 2}]}
```
错误码场景：校历未发布建批次 → 409001；HARD>0 预发布 → 409001（data 带冲突清单）；PUBLISHED 后 PUT items → 409001（“请走调停课”）；学院改他院课位 → 403002。

### 3.9 调停课（SM-08，Workflow）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-072 | GET /academic-affairs/schedule-change | 调停课列表（范围过滤） | changeType(调/停/补)、status、teacherId | scheduleChange.view | ✗ |
| AC-073 | POST /academic-affairs/schedule-change | 教师发起（提交即目标冲突预检；移动端包装 AC-147） | scheduleItemId、changeType、reason≥5 字、targetTime、targetRoomId、makeupPlan | scheduleChange.apply | ✓ |
| AC-074 | POST /academic-affairs/schedule-change/{id}/approve | 学院/教务处节点通过（终审通过→系统 APPLIED 更新课表并通知师生） | version、comment | scheduleChange.collegeReview / academicReview | ✓ |
| AC-075 | POST /academic-affairs/schedule-change/{id}/reject | 驳回 | version、reason≥5 字 | 同上 | ✓ |
| AC-076 | POST /academic-affairs/schedule-change/{id}/cancel | 教师撤销（终审前） | reason | scheduleChange.apply | ✓ |

AC-074 终审通过返回 `data` 示例：
```json
{"changeId": 55, "status": "APPLIED", "scheduleUpdated": true, "originSlotKept": "历史留痕", "notified": {"students": 43, "teacher": 1, "channel": "STATUS_CHANGED"}}
```
错误码场景：目标课位冲突 → 409001（预检拒收）；非本人课程 → 403002（COURSE scope）；同课位在途重复申请 → 409001 IDEMPOTENCY_CONFLICT。

### 3.10 选课（SM-09；学生选/退课在移动端 §五）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-077 | GET /academic-affairs/course-selection/batches | 选课批次列表 | termId、status | courseSelection.view | ✗ |
| AC-078 | POST /academic-affairs/course-selection/batches | 建批次（时间窗/范围/课程容量/八条规则配置） | termId、window、scope、courses[]、rules | courseSelection.manage | ✓ |
| AC-079 | POST /academic-affairs/course-selection/batches/{id}/publish | 发布（学生可见；到时自动 OPEN） | — | courseSelection.publish | ✓ |
| AC-080 | POST /academic-affairs/course-selection/batches/{id}/lock | 锁定名单（生成教学班正式名单） | — | courseSelection.lock | ✓ |
| AC-081 | GET /academic-affairs/course-selection/records | 选课记录/名单查询（按课程/班级/学生） | batchId、courseCode、status | courseSelection.view | ✗ |
| AC-082 | POST /academic-affairs/course-selection/courses/{id}/cancel-course | 低于人数下限取消开课（联动学生记录/退额度/补选指引） | reason≥5 字 | courseSelection.manage | ✓ |

错误码场景：未 CLOSED 锁定 → 409001；锁定后取消课程 → 409001；OPEN 中修改容量只允许上调，下调 → 422001。

### 3.11 考务与缓考（SM-10；学生缓考申请在移动端 AC-139）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-083 | GET /academic-affairs/exams/batches | 考试批次列表 | termId、examType、status | exam.view | ✗ |
| AC-084 | POST /academic-affairs/exams/batches | 建考试批次（期末/期中/补考/缓考） | termId、examType、window | exam.manage | ✓ |
| AC-085 | POST /academic-affairs/exams/batches/{id}/generate-courses | 按教学任务+LOCKED 选课生成考试课程 | scope | exam.manage | ✓ |
| AC-086 | POST /academic-affairs/exams/batches/{id}/confirm-courses | 学院确认考试课程清单 | courseIds[]、version | exam.arrange | ✓ |
| AC-087 | POST /academic-affairs/exams/batches/{id}/arrange | 编排时间/考场/座位/监考（冲突校验三类） | arrangements[] | exam.arrange | ✓ |
| AC-088 | POST /academic-affairs/exams/batches/{id}/publish | 发布（考生+监考通知、准考名单生成） | — | exam.publish | ✓ |
| AC-089 | GET /academic-affairs/exams | 考试安排查询（课程/考场/监考/学生维度） | batchId、courseCode、roomId、invigilatorId | exam.view | ✗ |
| AC-090 | POST /academic-affairs/exams/{id}/record-abnormal | 考后登记缺考/违纪/缓考标记（违纪联动学工线索、缺考联动预警） | abnormalType、studentIds[]、note | exam.recordAbnormal | ✓ |
| AC-091 | GET /academic-affairs/exams/deferred | 缓考申请列表（审批工作台） | status、collegeId | deferredExam.review | ✗ |
| AC-092 | POST /academic-affairs/exams/deferred/{id}/approve | 节点通过（辅导员/教师确认/学院/教务处；终审→标记缓考入安排池） | version、comment | deferredExam.review | ✓ |
| AC-093 | POST /academic-affairs/exams/deferred/{id}/reject | 驳回 | version、reason≥5 字 | deferredExam.review | ✓ |

AC-087 冲突返回 `data` 示例（422 时置于 details）：
```json
{"arranged": 118, "failed": [{"courseCode": "C1024", "reason": "考场A203容量60<考生72"}, {"courseCode": "C1080", "reason": "学生李某同时段两门考试"}]}
```
错误码场景：批次未确认课程即编排 → 409001；考试开始后缓考审批通过 → 409001（转考后补办通道）；监考教师时段冲突 → 422001 行级。

### 3.12 成绩（SM-11，含更正）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-094 | GET /academic-affairs/grade-tasks | 录入任务列表（教师=本人；学院/教务=范围内进度） | termId、status、courseCode、teacherId | grade.view | ✗ |
| AC-095 | GET /academic-affairs/grade-tasks/{id} | 任务详情（名单+构成配置+当前分数） | — | grade.view / grade.input | ✗ |
| AC-096 | PUT /academic-affairs/grade-tasks/{id}/input | 批量录入/暂存（平时/期末/总评构成；范围与互斥校验） | items[]（studentNo/usual/final/mark）、composition | grade.input | ✓ |
| AC-097 | POST /academic-affairs/grade-tasks/{id}/submit | 教师提交（全员有值或标记） | version | grade.input | ✓ |
| AC-098 | POST /academic-affairs/grade-tasks/{id}/review | 学院审核（完整性/分布异常提示） | action(approve/return)、version、reason | grade.collegeReview | ✓ |
| AC-099 | POST /academic-affairs/grade-tasks/{id}/publish | 教务处发布（回写 t_acad_grade；触发预警扫描/360/学生通知） | version | grade.publish | ✓ |
| AC-100 | POST /academic-affairs/grade-tasks/{id}/return | 教务处退回教师 | version、reason≥5 字 | grade.return | ✓ |
| AC-101 | GET /academic-affairs/grade-change | 成绩更正单列表 | status、courseCode、collegeId | gradeChange.review / grade.view | ✗ |
| AC-102 | POST /academic-affairs/grade-change | 教师发起更正（原/新成绩+原因+材料） | gradeItemId、newScore、reason≥5 字、fileIds[] | gradeChange.apply | ✓ |
| AC-103 | POST /academic-affairs/grade-change/{id}/approve | 学院→教务处两级通过（终审：更新成绩、原值 append-only 留存、联动预警/毕业审核、通知学生） | version、comment | gradeChange.review | ✓ |
| AC-104 | POST /academic-affairs/grade-change/{id}/reject | 驳回（原值不变） | version、reason≥5 字 | gradeChange.review | ✓ |

AC-099 返回 `data` 示例：
```json
{"taskId": 301, "status": "PUBLISHED", "published": 43, "failCount": 5,
 "writeBack": {"table": "t_acad_grade", "rows": 43},
 "triggered": {"warningScanScheduled": true, "stageEvents": 43, "studentNotices": 43, "makeupCandidates": 5}}
```
错误码场景：构成比例合计≠100% → 422001；未全员有值提交 → 422001 行级；PUBLISHED 后 PUT input → 409001（“请走成绩更正”）；非本教学班录入 → 403002；ARCHIVED 后更正 → 409001。

### 3.13 补考 / 重修 / 免修（SM-12；学生申请在移动端）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-105 | GET /academic-affairs/makeup/batches | 补考批次列表（含 PENDING 名单统计） | termId、status | makeup.manage / exam.view | ✗ |
| AC-106 | POST /academic-affairs/makeup/batches | 建补考批次并纳入名单、编排（复用考务编排结构） | termId、courseScope、arrangements | makeup.manage | ✓ |
| AC-107 | POST /academic-affairs/makeup/batches/{id}/publish | 发布补考安排 | — | makeup.manage | ✓ |
| AC-108 | PUT /academic-affairs/makeup/batches/{id}/scores | 补考成绩录入→审核→按规则更新最终成绩（回写 t_acad_makeup/t_acad_grade；计分规则读平台规则中心） | items[] | makeup.score | ✓ |
| AC-109 | GET /academic-affairs/retake/applications | 重修申请列表 | status、termId | retake.review | ✗ |
| AC-110 | POST /academic-affairs/retake/applications/{id}/review | 教务处审核（通过→纳入重修选课批次，回写 t_acad_retake） | action、version、reason | retake.review | ✓ |
| AC-111 | GET /academic-affairs/exemption/applications | 免修申请列表 | status、collegeId | exemption.review | ✗ |
| AC-112 | POST /academic-affairs/exemption/applications/{id}/review | 教师→学院→教务处逐级审核（终审→免修记录+学业进度标记） | action、version、reason | exemption.review | ✓ |

错误码场景：名单外学生编入补考 → 422001；重修同课程同学期重复申请 → 409001；免修已获成绩课程 → 422001。
> 既有 `GET /api/v1/academic/makeups`、`GET /api/v1/academic/retakes`（**复用既有 academic 学业过程模块**）保留为台账查询；13B 流程化走 `/api/v1/academic-affairs/makeup/*`、`/api/v1/academic-affairs/retake/*`；`PUT /{id}/status` 收敛计划见 §2.2-④。

### 3.14 学业预警（SM-13：复用为主，新增 3 端点）

**复用（不动）**：GET/POST /academic/warnings、GET /warnings/{wid}、PUT /warnings/{wid}/level、POST /warnings/{wid}/void、POST /warnings/assign、POST /warnings/remind、POST /warnings/{wid}/interventions、POST /warnings/{wid}/close、POST /warnings/{wid}/escalate（权限点映射至 warning.view/handle，数据范围按矩阵 §16）。

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-113 | GET /academic-affairs/warning-rules | 预警规则清单（九类来源阈值，接平台规则中心） | source、enabled | warning.rule.manage | ✗ |
| AC-114 | PUT /academic-affairs/warning-rules | 维护规则（阈值/等级/推送对象） | rules[] | warning.rule.manage | ✓ |
| AC-115 | POST /academic-affairs/warning-scan | 手动触发扫描（成绩发布后自动扫描的手动兜底；幂等：扫描批次号） | scope、sources[] | warning.rule.manage | ✓ |

AC-115 返回 `data` 示例：
```json
{"scanBatchNo": "WS20260705-01", "scanned": 5210, "generated": 37, "bySource": {"FAIL_COURSE": 21, "CREDIT_SHORT": 9, "UNREGISTERED": 7}, "pushed": {"counselors": 18, "collegeAcademic": 6, "studentNotices": 37}}
```
错误码场景：扫描进行中重复触发 → 409001 IDEMPOTENCY_CONFLICT；非教务处配规则 → 403001。

### 3.15 毕业资格审核（SM-14）

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-116 | GET /academic-affairs/graduation-audit/batches | 审核批次列表 | year、status | graduationAudit.view | ✗ |
| AC-117 | POST /academic-affairs/graduation-audit/batches | 建批次并生成应审学生（年级/学制；DELAYED 自动纳入） | year、scope | graduationAudit.manage | ✓ |
| AC-118 | POST /academic-affairs/graduation-audit/batches/{id}/run-precheck | 运行系统预审（九项条件，逐项判定留痕；幂等） | studentIds[]（可选增量） | graduationAudit.precheck | ✓ |
| AC-119 | GET /academic-affairs/graduation-audit/results | 审核结果列表（异常项筛选） | batchId、status、abnormalItem、collegeId | graduationAudit.view | ✗ |
| AC-120 | GET /academic-affairs/graduation-audit/results/{id} | 单人结果详情（九项判定明细+各模块供数快照） | — | graduationAudit.view | ✗ |
| AC-121 | POST /academic-affairs/graduation-audit/results/{id}/college-review | 学院初审（正常确认/异常处理意见） | action、version、comment | graduationAudit.collegeReview | ✓ |
| AC-122 | POST /academic-affairs/graduation-audit/results/{id}/academic-review | 教务处终审（conclusion=GRADUATED/COMPLETED/DELAYED/REJECTED；联动 SM-02） | conclusion、version、reason | graduationAudit.manage | ✓ |
| AC-123 | POST /academic-affairs/graduation-audit/batches/{id}/publish | 发布毕业/结业/延毕名单（学生端展示、360 归档；名单导出走 /export/domain） | — | graduationAudit.publish | ✓ |

AC-118 返回 `data` 示例：
```json
{"batchId": 2, "prechecked": 1380, "systemPassed": 1291, "systemAbnormal": 89,
 "abnormalTop": [{"item": "DISCIPLINE_UNREMOVED", "count": 4}, {"item": "CREDIT_SHORT", "count": 41}, {"item": "INTERNSHIP_UNFINISHED", "count": 17}],
 "riskAlertsPushed": 89}
```
错误码场景：预审运行中重复触发 → 409001；绕过学院初审直接终审 → 409001；学院审他院学生 → 403002；批次 ARCHIVED 后改结果 → 409001。

### 3.16 教务归档

| 编号 | 方法与路径 | 用途 | 关键参数 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-124 | GET /academic-affairs/archive/batches | 归档批次列表 | termId、status | archive.manage | ✗ |
| AC-125 | POST /academic-affairs/archive/batches | 建归档批次（方案/课表/成绩/考试材料/毕业审核/任务材料/审批记录） | termId、contentTypes[] | archive.manage | ✓ |
| AC-126 | POST /academic-affairs/archive/batches/{id}/execute | 执行归档（生成水印归档包、关联对象批量置 ARCHIVED、ARCHIVE_NOTICE） | version | archive.manage | ✓ |
| AC-127 | GET /academic-affairs/archive/packages | 归档包检索与下载登记（下载走导出管线留痕） | batchId、contentType | archive.manage | ✗ |

错误码场景：成绩/考试批次未全部终态执行归档 → 409001（data 返回未就绪清单）。

---

## 四、导入导出（零新增端点：注册 domain 接入既有管线，速查 §8）

导入沿用 `POST /api/v1/import/domain/{domain}/validate|confirm`（模板→dry-run 行级错误→整批事务，5000 行/20MB），导出沿用 `POST /api/v1/export/domain/{domain}`（用途≥5 字、脱敏列、首行水印、t_export_task 留痕、限流限行）。13B 注册 domain：

| domain | 方向 | 内容 | 权限点 | 敏感处理 |
|---|---|---|---|---|
| academic-roster | 导入 | 学籍导入（新生/批量维护） | import | 身份证列加密入库 |
| academic-course | 导入 | 课程库导入 | import | — |
| academic-program | 导入 | 培养方案（课程模块）导入 | import | — |
| academic-teaching-task | 导入 | 教学任务导入 | import | — |
| academic-grade | 导入 | 成绩模板导入（教师本人任务，行级校验构成） | import（教师限本人任务） | 成绩敏感，导入留痕 |
| academic-schedule | 导出 | 课表导出（班级/教师/教室） | export | 水印 |
| academic-selection | 导出 | 选课名单导出 | export | 水印 |
| academic-exam | 导出 | 考试安排/监考表导出 | export | 水印 |
| academic-transcript | 导出 | 学生成绩单导出 | export | 成绩敏感：二次确认+水印+审计 |
| academic-graduation | 导出 | 毕业/结业/延毕名单导出 | export | 身份证脱敏列+二次确认 |
| academic-status-change | 导出 | 异动台账导出（**默认不含原因全文**） | export | 脱敏+审计 |

---

## 五、移动端契约（学生小程序 + 教师移动端）

### 5.1 与既有 `/api/v1/mobile/academic/my` 的关系

- 既有 `GET /api/v1/mobile/academic/my`（我的学业过程聚合）**保留不动**，继续作为学生端“学业”页聚合入口；教务中心上线后该聚合的成绩/预警节点改读发布后数据（t_acad_grade / t_acad_warning），入口语义不变。
- 教务中心学生端新增独立域前缀 **`/api/v1/mobile/academic-affairs/*`**（沿用 `{domain}/my` 命名风格，读接口 my-* 化），避免向既有 academic 聚合塞流程接口。
- 小程序页面侧：既有“我的学业”页保留；新增“教务服务”入口组（课表/选课/考试/成绩/学籍/毕业进度），请求层沿用 realFirst + createSubmitLock 防连点 + 401 单飞刷新；写操作全部带 request_id。

### 5.2 学生端 `/api/v1/mobile/academic-affairs/*`（token.studentNo 取本人，越权按 404 处理）

| 编号 | 方法与路径 | 用途 | 关键参数 / 返回要点 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-128 | GET …/my-schedule | 我的课表（周视图；调停课变更即时反映） | termId、week → items[]（课程/教师/教室/节次/变更标记） | schedule.view(SELF) | ✗ |
| AC-129 | GET …/my-courses | 我的课程（本学期修读+学分） | termId → courses[]、creditSummary | courseSelection.view(SELF) | ✗ |
| AC-130 | GET …/my-exams | 我的考试（安排/座位/准考信息；含补考缓考场次） | termId → exams[]（倒计时/考场/座位） | exam.view(SELF) | ✗ |
| AC-131 | GET …/my-grades | 我的成绩（**仅 PUBLISHED**；更正后展示更正标记） | termId → grades[]、gpa、failCount | grade.view(SELF) | ✗ |
| AC-132 | GET …/my-status | 我的学籍（状态/专业/班级/方案版本/注册记录） | → statusTimeline[]（StageEvent） | statusChange.view(SELF) | ✗ |
| AC-133 | GET …/status-change/my | 我的异动申请列表 | status → list[]（状态/当前节点） | statusChange.view(SELF) | ✗ |
| AC-134 | POST …/status-change | 发起异动申请（转专业/休学/复学/退学；防重复 409） | changeType、reason、fileIds[]、targetMajorId | statusChange.apply | ✓ |
| AC-135 | POST …/status-change/{id}/cancel | 撤销本人在途申请 | reason | statusChange.apply | ✓ |
| AC-136 | GET …/course-selection/batches | 可选课程（OPEN 批次+余量+规则提示） | batchId → courses[]（余量/冲突预判/先修满足） | courseSelection.view(SELF) | ✗ |
| AC-137 | POST …/course-selection/select | 选课（八条校验，容量原子扣减，防连点） | batchId、courseId | courseSelection.select | ✓ |
| AC-138 | POST …/course-selection/drop | 退课（OPEN 期内） | recordId | courseSelection.drop | ✓ |
| AC-139 | POST …/exams/deferred-apply | 缓考申请（材料必传；可带入已批请假单号） | examId、reason、fileIds[]、leaveId | deferredExam.apply | ✓ |
| AC-140 | GET …/my-warnings | 我的学业预警（等级/来源/处理进度/整改建议） | status → warnings[] | warning.view(SELF) | ✗ |
| AC-141 | GET …/graduation-progress | 毕业资格进度（九项条件逐项达成度；不含他人对比） | → items[]（passed/abnormal/说明）、conclusion | graduationAudit.view(SELF) | ✗ |

AC-137 失败示例（业务错误透出，不兜底）：
```json
{"code": 409001, "bizCode": "DATA_CONFLICT", "message": "课程容量已满，请选择其他课程", "data": null, "traceId": "req-a1b2", "timestamp": "2026-07-05T09:00:00+08:00"}
```
错误码场景：非 OPEN 时段 select/drop → 409001；SUSPENDED 学生选课 → 403001（文案“休学期间不可选课”）；422 校验（超学分上限/先修不满足）行级返回。

### 5.3 教师端 `/api/v1/mobile/teacher/academic-affairs/*`（沿用 mobile_teacher 包装：范围校验+审计+409）

| 编号 | 方法与路径 | 用途 | 关键参数 / 返回要点 | 权限点 | 审计 |
|---|---|---|---|---|---|
| AC-142 | GET …/today-courses | 今日课程（节次/教室/班级/调停课标记） | date → items[] | schedule.view(COURSE) | ✗ |
| AC-143 | GET …/my-schedule | 我的周课表 | termId、week | schedule.view(COURSE) | ✗ |
| AC-144 | GET …/class-roster | 授课班级学生名单（教学班维度，联系方式脱敏） | taskId → students[]（脱敏） | teachingTask.view(COURSE) | ✓（看完整联系方式另走授权） |
| AC-145 | GET …/grade-input-progress | 成绩录入进度（本人任务完成度；**录入操作回 PC**，移动端只读+提示） | termId → tasks[]（progress/deadline） | grade.view(COURSE) | ✗ |
| AC-146 | GET …/schedule-change/my | 我的调停课申请与结果 | status | scheduleChange.view(SELF) | ✗ |
| AC-147 | POST …/schedule-change | 移动发起调停课（包装 AC-073：范围校验+审计+防重复 409） | 同 AC-073 | scheduleChange.apply | ✓ |
| AC-148 | POST …/teaching-tasks/{id}/confirm | 移动确认教学任务（包装 AC-056/057，action=confirm/dispute） | action、reason | teachingTask.teacherConfirm | ✓ |
| AC-149 | GET …/invigilation | 我的监考任务（时间/考场/考生数；考后异常登记回 PC 或走 AC-090 包装（P2）） | termId → items[] | exam.view(SELF) | ✗ |
| AC-150 | GET …/warning-followups | 待跟进学业预警（被分配单+本人授课学生；处理动作**复用既有** /mobile/teacher 预警处理端点，不新增） | status → warnings[] | warning.view(COURSE) | ✗ |

> 教师移动端边界（与需求 §11 一致）：查看/确认/发起类移动可办；成绩录入、排课、考务编排、毕业审核一律回 PC。审批类（异动/缓考/成绩审核节点）走既有 `POST /api/v1/mobile/teacher/approvals/{id}/approve|reject` 通用包装，不为教务中心单独复制审批端点。

---

## 六、接口清单统计与实施顺序

| 分组 | 编号区间 | 条数 |
|---|---|---|
| PC：首页/校历/注册/异动 | AC-001 ～ AC-027 | 27 |
| PC：方案/课程库/教学任务 | AC-028 ～ AC-059 | 32 |
| PC：排课/调停课/选课 | AC-060 ～ AC-082 | 23 |
| PC：考务缓考/成绩/补重免 | AC-083 ～ AC-112 | 30 |
| PC：预警扩展/毕业审核/归档 | AC-113 ～ AC-127 | 15 |
| 移动端：学生 | AC-128 ～ AC-141 | 14 |
| 移动端：教师 | AC-142 ～ AC-150 | 9 |
| **合计（新增契约）** | AC-001 ～ AC-150 | **150** |
| 复用不新增 | 预警 9 端点 + 教师移动审批包装 + 导入导出管线 + /mobile/academic/my | — |

实施顺序对齐需求 §11 阶段：13B-P1 冻结本契约 → P2（AC-002~027）→ P3（AC-028~048）→ P4（AC-049~071，课表查看优先）→ P5（AC-094~104 查看链 + AC-113~115）→ P6（AC-116~123）→ P7（AC-128~150）→ P8 测试验收。自动排课、完整选课、完整考务、成绩全流程录审发为 P2/P3 期能力，本契约先冻结路径与包络，避免后续路径漂移。

---

## 七、workflow_code 与端点映射（审批全部落 t_workflow_instance/t_workflow_task）

| workflow_code | 业务 | 节点序列（node_code） | 发起端点 | 审批端点 |
|---|---|---|---|---|
| AC_ENROLL_REVIEW | 注册批次审核 | COLLEGE_SUBMIT → ACADEMIC_REVIEW | AC-018 | AC-019 |
| AC_SC_TRANSFER | 转专业 | COUNSELOR → OUT_COLLEGE → IN_COLLEGE → ACADEMIC | AC-023 / AC-134 | AC-024/025/026 |
| AC_SC_SUSPEND | 休学 | COUNSELOR → COLLEGE → ACADEMIC | AC-023 / AC-134 | 同上 |
| AC_SC_RESUME | 复学 | COUNSELOR → COLLEGE(定班) → ACADEMIC | AC-134 | 同上 |
| AC_SC_WITHDRAW | 退学 | COUNSELOR → COLLEGE → ACADEMIC | AC-023 / AC-134 | 同上 |
| AC_PROGRAM_REVIEW | 培养方案 | COLLEGE_REVIEW → ACADEMIC_REVIEW | AC-034 | AC-035 |
| AC_COURSE_REVIEW | 课程库 | COLLEGE_REVIEW → ACADEMIC_REVIEW | AC-045 | AC-046 |
| AC_TASK_REVIEW | 教学任务批次 | ACADEMIC_REVIEW（前段确认链走统一待办） | AC-058 | AC-059 |
| AC_SCHEDULE_CHANGE | 调停课 | COLLEGE_REVIEW → ACADEMIC_REVIEW | AC-073 / AC-147 | AC-074/075 |
| AC_DEFERRED_EXAM | 缓考 | COUNSELOR → TEACHER_CONFIRM → COLLEGE → ACADEMIC | AC-139 | AC-092/093 |
| AC_GRADE_REVIEW | 成绩审核发布 | COLLEGE_REVIEW → ACADEMIC_PUBLISH | AC-097 | AC-098/099/100 |
| AC_GRADE_CHANGE | 成绩更正 | COLLEGE_REVIEW → ACADEMIC_REVIEW | AC-102 | AC-103/104 |
| AC_RETAKE | 重修 | ACADEMIC_REVIEW | 移动端报名 | AC-110 |
| AC_EXEMPTION | 免修 | TEACHER → COLLEGE → ACADEMIC | 移动端申请 | AC-112 |
| AC_GRAD_AUDIT | 毕业审核 | COLLEGE_REVIEW → ACADEMIC_REVIEW | AC-118（预审后进入） | AC-121/122 |

> 待办统一进 t_unified_todo（todo_type=WORKFLOW_TODO，source_module=academic-affairs）；教师移动审批走既有 `POST /api/v1/mobile/teacher/approvals/{id}/approve|reject` 通用包装；已处理再审一律 409 APPROVAL_VERSION_CONFLICT。

## 八、补充返回示例（高频读接口 data 形态冻结）

AC-071 课表视图（viewType=class）：
```json
{
  "viewType": "class", "refId": 305, "termId": 11, "week": 3,
  "items": [
    {"itemId": 9001, "courseCode": "C1024", "courseName": "Java程序设计", "teacherName": "王某",
     "roomName": "A203", "dayOfWeek": 3, "slots": [3, 4], "weeks": "1-16", "changeFlag": null},
    {"itemId": 9002, "courseCode": "C1080", "courseName": "数据库原理", "teacherName": "李某",
     "roomName": "B102", "dayOfWeek": 4, "slots": [1, 2], "weeks": "1-8,10-17", "changeFlag": "CHANGED"}
  ]
}
```

AC-131 我的成绩（学生端，仅 PUBLISHED）：
```json
{
  "termId": 11, "gpa": 3.12, "failCount": 1, "creditEarned": 24.5,
  "grades": [
    {"courseCode": "C1024", "courseName": "Java程序设计", "credit": 4, "usual": 85, "final": 78,
     "total": 81, "passStatus": "PASS", "corrected": false},
    {"courseCode": "C1080", "courseName": "数据库原理", "credit": 3, "usual": 70, "final": 52,
     "total": 58, "passStatus": "FAIL", "corrected": false, "makeupHint": "已进入补考名单，安排待发布"}
  ]
}
```

AC-141 毕业资格进度（学生端）：
```json
{
  "batchId": 2, "status": "SYSTEM_ABNORMAL", "conclusion": null,
  "items": [
    {"item": "STATUS_NORMAL", "label": "学籍正常", "passed": true},
    {"item": "CREDIT_TOTAL", "label": "方案学分达标", "passed": false, "detail": "已获118/应修126"},
    {"item": "REQUIRED_COURSES", "label": "必修课程通过", "passed": true},
    {"item": "INTERNSHIP", "label": "岗位实习完成", "passed": true},
    {"item": "GRADUATION_DESIGN", "label": "毕业设计通过", "passed": true},
    {"item": "DISCIPLINE", "label": "无未解除严重处分", "passed": true},
    {"item": "FEE_MATERIAL", "label": "费用与材料", "passed": true},
    {"item": "EMPLOYMENT_REPORT", "label": "就业去向填报", "passed": false, "detail": "未填报"},
    {"item": "ARCHIVE", "label": "档案归档", "passed": true}
  ],
  "suggestion": "请完成学分修读与就业去向填报，可联系辅导员"
}
```

AC-016 注册名单（学院核对视图，身份证脱敏）：
```json
{
  "list": [
    {"studentNo": "2026010001", "realName": "张某", "idCardMasked": "3701**********1234",
     "collegeName": "软件学院", "majorName": "软件技术", "className": "软件2601",
     "checks": {"reported": true, "paid": false, "materials": true}, "confirmable": false, "blockReason": "学费未缴清"}
  ],
  "total": 1260, "page": 1, "pageSize": 20,
  "summary": {"confirmable": 1180, "blocked": 80}
}
```

## 九、核心链路验收用例（每链路 ≥4 条，必含重复提交与越权）

**链路一：学生休学申请（AC-134 → AC-024 → SM-02 联动）**
1. 学生提交休学（材料齐）→ 生成异动单 SUBMITTED，辅导员收 WORKFLOW_TODO，学生端「我的异动」显示待审。
2. 辅导员→学院→教务处逐级通过 → 到休学起始日 student_status=SUSPENDED，学生收 STATUS_CHANGED，360 时间线出现异动事件。
3. 同一学生连点两次提交（同 request_id 或在途同类）→ 仅一条单据，第二次 409 IDEMPOTENCY_CONFLICT。
4. 学生 A 用 AC-133/AC-135 访问学生 B 的异动单 → 404（按不存在处理）；PC 端他院教务员审批 → 403 NO_DATA_SCOPE + 审计。
5. SUSPENDED 学生调 AC-137 选课 → 403，文案“休学期间不可选课”。

**链路二：成绩录入-发布-预警（AC-096→097→098→099 → SM-13）**
1. 教师录入全员成绩提交 → 任务 SUBMITTED，学院收待办；构成比例 90% 提交 → 422 行级。
2. 学院通过、教务处发布 → 回写 t_acad_grade，学生端 AC-131 可查，5 名不及格进补考名单并当晚生成 FAIL_COURSE 预警推辅导员。
3. 发布后教师再 PUT AC-096 → 409（提示走成绩更正 AC-102）；更正终审通过 → 原值留存、学生收“成绩已更正”。
4. 教师对非本人教学班任务调 AC-096 → 403 NO_DATA_SCOPE（COURSE scope 判定）+ 审计。
5. 学院对已审任务重复 AC-098 → 409 APPROVAL_VERSION_CONFLICT。

**链路三：选课并发（AC-137/AC-138）**
1. 批次 OPEN 内选课成功 → SELECTED，余量减 1，学生端回执。
2. 余量 1 时两学生并发选 → 恰一人成功，另一人 409 “课程容量已满”，无超卖。
3. 非 OPEN 时段（PUBLISHED/CLOSED）select/drop → 409 “不在选课时间内”。
4. 已修过该课程再选 → 422 行级（校验规则命中）；退课后重选 → 新记录 SELECTED。

**链路四：调停课（AC-147 → AC-074 → APPLIED）**
1. 教师移动端发起调课（目标无冲突）→ SUBMITTED，学院收待办。
2. 学院、教务处通过 → APPLIED，课表更新，受影响 43 名学生收 STATUS_CHANGED，AC-128 课表出现 changeFlag。
3. 目标课位教室被占 → 提交即 409，不落单。
4. 教师对他人课程课位发起 → 403 NO_DATA_SCOPE；APPROVED 后撤销 → 409。

**链路五：毕业预审（AC-118 → AC-141）**
1. 建批次 run-precheck → 1291 SYSTEM_PASSED / 89 SYSTEM_ABNORMAL，异常者辅导员收 RISK_ALERT，学生端 AC-141 显示逐项达成度。
2. 学生补修学分+填报就业后夜间自动重跑 → 该生转 SYSTEM_PASSED。
3. 预审运行中再次触发 AC-118 → 409 IDEMPOTENCY_CONFLICT。
4. 学院教务员初审他院学生结果 → 403 NO_DATA_SCOPE；绕过初审直接终审 → 409。

---

## 十、附录：按 13A 学工 B 包深度补齐的 13B 教务中心施工卡（API 命名规则、B0–B8 分组与缺口清单）

> 口径说明：上文 §三（3.1–3.16）已按 14 个业务域给出完整端点契约，本节不重复罗列端点，只补三样 13A B 包标准要求但上文缺少的东西：①统一命名规则、②把已有端点按 B0–B8 施工顺序重新分组（方便新手按包施工时知道该看哪几节）、③表/字段建议索引、④xlsx 接口清单、⑤接口缺口清单、⑥与既有 `/admin/academic` 模块的融合边界重申。

### 十.1 API 命名规则

- **路径**：`/api/v1/academic-affairs/<domain>[/:id][/<action>]`，domain 用英文小写 kebab-case（如 `status-change`、`teaching-tasks`、`grade-tasks`）；移动端固定 `/api/v1/mobile/academic-affairs/*`（学生）与 `/api/v1/mobile/teacher/academic-affairs/*`（教师）。
- **动作型端点**：状态流转类统一 `POST /<domain>/:id/<verb>`（`approve`/`publish`/`reject`/`rollback`/`cancel`），禁止用 `PUT` 承担状态机跳转。
- **权限点**：`academicAffairs.<biz>.<action>`（与 §15 权限点矩阵一致，例如 `academicAffairs.grade.publish`）。
- **导入导出**：统一走 `/api/v1/excel/import|export`，`domain` 参数注册对应 13B 业务域，禁止每个业务域另起一套导入导出端点（复用 `app/services/excel/`）。
- **统计**：统一 `/api/v1/stats/*`，多维参数化，不为每个统计维度单开端点。

### 十.2 B0–B8 API 分组（映射到 §三已有端点，与 Opus 入口文档 §16 同一顺序）

| 分包 | 涉及业务域（对应 §三小节） | 端点前缀 |
|---|---|---|
| B0 | 无新端点，契约冻结 | — |
| B1 | 教务首页（3.1）、学年学期与校历（3.2） | `/dashboard`、`/terms` |
| B2 | 培养方案（3.5）、课程库（3.6）、教学任务（3.7） | `/programs`、`/courses`、`/teaching-tasks` |
| B3 | 教学任务分配子集（3.7）、选课（3.10，承接） | `/teaching-tasks/:id/check`、`/enrollment` |
| B4 | 排课与课表发布（3.8）、调停课（3.9） | `/schedule`、`/course-adjustments` |
| B5 | 考务与缓考（3.11） | `/exam`、`/exam/deferral` |
| B6 | 成绩（3.12） | `/grade-tasks`、`/grades`、`/grade-correction` |
| B7 | 补考/重修/免修（3.13）、学业预警（3.14） | `/makeup`、`/retake`、`/exemption`、`/warnings` |
| B8 | 毕业资格审核（3.15）、教务归档（3.16）、导入导出（四）、移动端（五）、统计（六接口清单统计） | `/graduation-audit`、`/archive`、`/excel/*`、`/mobile/academic-affairs/*`、`/stats/*` |
| 桥接 | 学籍注册/异动（3.3/3.4）——学籍主档在学生中心，教务只做受控写入口 | `/roll/registration`、`/status-change` |

### 十.3 表/字段建议索引（详见 `13A-13B-数据表与迁移策略草案.md` §4，本节只做索引不重复列字段）

| 表分组 | 归属分包 | 状态 |
|---|---|---|
| §4.1 学年学期与校历组 | B1 | V1 新建，已有 Alembic 0009 |
| §4.2 学籍组（异动新表+student_status 受控扩展） | B1/B3 | V1 新建，已有 Alembic 0010 |
| §4.3 课程库与培养方案组 | B2 | V1 新建，已有 Alembic 0011 |
| §4.4 教学任务与课表组 | B2/B3/B4 | V1 新建，已有 Alembic 0011/0012 |
| §4.5 成绩与预警组（成绩权威=t_acad_grade，预警复用 t_acad_warning） | B6/B7 | V1 新建，已有 Alembic 0013 |
| §4.6 毕业资格预审组 | B8 | V1 新建，已有 Alembic 0014 |
| §4.7 审计组 | 全程 | 复用既有 `t_security_audit_log`/`t_export_task`，不新建 |
| §4.8 13B P2 预留表（教材/教学资源/教室/评价/质量/归档批次/等级考试/国家平台上报） | B8 | 仅锁名，本轮不建 |

### 十.4 xlsx 导入导出接口（详见 `13A-13B-打印导出归档模板设计.md` §2.1–2.10，本节只做接口清单）

| domain 注册名 | 用途 | 模板 | 归属分包 | 状态 |
|---|---|---|---|---|
| `aa_status_change` | 学籍异动申请表导出 | §2.1 | B3 | 契约已冻结，前端未接 |
| `aa_grades` | 成绩单 PDF+xlsx | §2.2 | B6 | 契约已冻结，前端未接 |
| `aa_makeup_list` | 补考名单 | §2.3 | B7 | 契约已冻结，前端未接 |
| `aa_retake_list` | 重修名单 | §2.4 | B7 | 契约已冻结，前端未接 |
| `aa_schedule` | 课表（班级/教师/教室三视图） | §2.5 | B4 | 契约已冻结，前端未接 |
| `aa_exam_schedule` | 考试安排 | §2.6 | B5 | 契约先冻结，功能随考务 P2 启用 |
| `aa_graduation_audit` | 毕业资格审核表 | §2.7 | B8 | 契约已冻结，前端未接 |
| `aa_graduation_lists` | 毕业/结业/延毕名单三变体 | §2.8–2.10 | B8 | 契约已冻结，前端未接 |
| 错误行下载 | 全部导入 domain 通用能力（复用 `AppImportErrorSummary`） | — | B2/B3/B6 | 后端管线已支持，前端未接 |
| 导出台账 | 全部导出 domain 通用能力（`t_export_task` 已记录） | — | 全程 | 后端已支持，前端展示未接 |

### 十.5 接口缺口清单

| 缺口 | 现状 | 阻断PC | 阻断上线 |
|---|---|---|---|
| 前端零调用 | 全部 §三 端点已在 `academic_affairs.py`（569 行，10 个 service）实现并有 11 个 `test_aa_*.py` 覆盖，`frontend/src` 内 0 处 `request('/academic-affairs/...')` 调用 | 是 | 是 |
| dashboard 聚合接口 | §3.1 教务首页端点契约已给，后端待确认是否已实现（需 B0 核对） | 是 | 是 |
| stats 多维统计接口 | §六接口清单统计与实施顺序未见 `/api/v1/stats/*` 教务维度实现确认 | 否 | 是 |
| 算法排课/排考/抽签选课接口位 | `suggest` 系列端点为接口位设计，未启用时需返回明确"未启用"而非报错 | 否 | 否（P2/P3） |
| 移动端端点前端接入 | 契约已给（§五），`miniapp/src/pages/student/academic-affairs/*` 现有页面读取的是 t_acad_ 而非 t_aa_，需 B8 核对切换或双轨过渡方案 | 否 | 是 |

### 十.6 与既有 `/admin/academic`（t_acad_）模块的融合边界（重申 §2 结论）

- `t_acad_*`（现有"学业过程"模块）与 `t_aa_*`（本模块）**并存不合并**：`t_acad_*` 保留为学生个人学业过程视图（成绩/学分/补考重修/预警的学生侧只读呈现），`t_aa_*` 是教务处的业务权威源（培养方案/课程/教学任务/排课/考试/成绩录入审核发布的管理侧闭环）。
- 成绩权威表为 `t_acad_grade`：B6 成绩发布/更正**原子回写** `t_acad_grade`，不新建平行成绩表；学业预警权威表为 `t_acad_warning`，B7 只做扩展 `source` 字段，不新建平行预警表。
- 现有 `/api/v1/academic/*` 端点（students/grades/credits/makeups/retakes/warnings/audit-logs）及 `/api/v1/mobile/academic/my` **零改动、零重复注册**，CI 路由重复检查覆盖。
- 前端菜单层面：`navPlan.js` 中"教务中心"分组 `aa-dashboard` 等少数条目当前复用 `/admin/academic` 路由，B1 起需按 §十.2 分组逐条切到 `/admin/academic-affairs/*` 真实路由，替换过程中旧路由保持 redirect 兼容，不破坏在用页面。

（完）
