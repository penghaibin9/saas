# 05 · 岗位实习 API

> 第一主攻可卖模块（P3）。风险密度最高、角色最多（含企业导师）。学生小程序打卡/周报高频，教师端批阅，PC 管理端监管。
> 通用规则见 [00 总册](00-API契约冻结总册.md)。前缀：管理端 `/api/v1/admin/internship`；学生 `/api/v1/student-pc|student-mini/internship`；教师 `/api/v1/teacher-mobile/internship`；企业 `/api/v1/enterprise-portal/*`。
> DB 依据：DB 冻结册 §4.9（t_intern_* / t_assignment / t_checkin / t_agreement…）。深化：06 中心 §17（provider 契约）。

---

## 模块一览

| # | 接口 | 方法 | 路径 | 端 | 一期 |
|---|---|---|---|---|---|
| 5.1 | 实习首页/工作台 | GET | /admin/internship/workbench | PC/教师 | P3 |
| 5.2 | 我的实习（学生） | GET | /student-pc/internship/my | 学生 | P3 |
| 5.3 | 实习学生列表 | GET | /admin/internship/students | PC/教师 | P3 |
| 5.4 | 企业岗位信息 | GET | /admin/internship/positions | PC/学生 | P3 |
| 5.5 | 实习申请（提交/审核） | POST | /*/internship/applications[/{id}/review] | 全端 | P3 |
| 5.6 | 打卡 | POST | /student-mini/internship/checkins | 学生 | P3 |
| 5.7 | 打卡异常列表 | GET | /*/internship/checkin-exceptions | 教师/PC | P3 |
| 5.8 | 补卡申请/审核 | POST | /*/internship/checkins/{id}/makeup[/review] | 学生/教师 | P3 |
| 5.9 | 周报列表 | GET | /*/internship/reports | 全端 | P3 |
| 5.10 | 周报提交 | POST | /student-pc/internship/reports | 学生 | P3 |
| 5.11 | 周报批阅 | POST | /*/internship/reports/{id}/review | 教师 | P3 |
| 5.12 | 请假申请 | POST | /student-mini/internship/leaves | 学生 | P3 |
| 5.13 | 请假审批 | POST | /*/internship/leaves/{id}/approve|reject | 教师 | P3 |
| 5.14 | 巡访记录 | GET/POST | /teacher-mobile/internship/visits | 教师 | P3 |
| 5.15 | 实习风险 | GET/POST | /*/internship/risks[/{id}/handle] | 全端 | P3 |
| 5.16 | 企业评价 | POST | /enterprise-portal/evaluations | 企业 | P3 |
| 5.17 | 实习成绩 | GET/POST | /admin/internship/scores | PC | P3 |
| 5.18 | 实习归档 | POST | /admin/internship/filings | PC | P3 |

> provider 方法名（前端对齐）：`fetchInternWorkbench、fetchApplications、reviewApplication、fetchMyInternship、submitCheckin、reviewMakeup、fetchReports、submitReport、reviewReport、reviewLeave、submitEnterpriseEval、calcFinalScore、publishScore、fetchRisks、handleRisk、fetchFiling`。

---

### 5.1 实习首页/工作台
- **方法/路径**：`GET /api/v1/admin/internship/workbench`（教师端 `/teacher-mobile/workbench` 聚合含实习）
- **用途**：概览指标 + 今日待办 + 风险摘要 + 完成率。
- **响应字段**：`{ metrics:[{id,title,value,trendType,trendQuality}], todos:[...], risks:[...], onboardCount }`。
- **权限**：`intern:workbench:view`。**数据范围**：按身份（INTERN_STUDENTS/COLLEGE/SCHOOL）。**审计**：否。**mock**：是。**表**：t_assignment、t_checkin、t_intern_report、t_complaint（聚合）。**一期**：P3。指标禁硬编码（trendQuality 由聚合层返回）。

### 5.2 我的实习（学生）
- `GET /api/v1/student-pc/internship/my`。用途：学生 S6 实习主入口。响应 `{ status, enterprise, position, schoolTeacher, enterpriseMentor, todayTask, returnedAlert }`。权限 SELF。表 t_assignment、t_intern_application。一期 P3。

### 5.3 实习学生列表
- `GET /api/v1/admin/internship/students?keyword=&stage=&riskLevel=&page=`。教师 T17 我的实习学生。响应含在岗状态/打卡异常/周报状态。权限 `intern:student:view`。数据范围 按身份。分页 是。表 t_assignment、t_student_profile。一期 P3。

### 5.4 企业岗位信息
- `GET /api/v1/admin/internship/positions?enterpriseId=&status=`。响应岗位/企业/打卡范围。权限 `intern:position:view`。表 t_position、t_enterprise、t_checkin_point。一期 P3。

### 5.5 实习申请（五级审核）
- **提交**：`POST /api/v1/student-pc/internship/applications`，体 `{ positionId, choiceOrder, requestId }` → status `PENDING`。
- **审核**：`POST /api/v1/admin/internship/applications/{id}/review`，体 `{ action:"TEACHER_AGREE|TEACHER_REJECT|COLLEGE_PASS|COLLEGE_REJECT|HIRE|NOT_HIRE", comment, rejectReason?, version, requestId }`。
- **用途**：五级审核流（学生→教师一审→院校二审→企业录用）。列表须显示"卡在哪一方"。
- **权限**：学生 `intern:application:create`；审核 `intern:application:review`。**审计**：是。**乐观锁/幂等**：是。**SoD**：是。**表**：t_intern_application。**一期**：P3。状态枚举见 DB 冻结 §5.5。

### 5.6 打卡（核心）
- **方法/路径**：`POST /api/v1/student-mini/internship/checkins`
- **用途**：学生定位打卡（防作弊）。**只在主动点击时采集定位**（骨架冻结）。
- **使用页面**：学生端打卡（tabBar 高频）。
- **请求体**：`{ latitude, longitude, accuracy, isMock, deviceId, photoFileId, slot, clientDraftId }`。
- **响应字段**：`{ checkinId, withinRange, distance, result:"NORMAL|ABNORMAL", riskTriggered }`。
- **权限**：SELF + `intern:checkin:create`。**数据范围**：SELF。**审计**：是。**幂等**：clientDraftId（弱网防重）。**依赖定位**：是（无定位 `LOCATION_PERMISSION_REQUIRED`）。**mock**：是。**表**：t_checkin、t_checkin_point、t_mini_draft、t_complaint（异常触发）。**一期**：P3。
- **红线**：**禁止代打卡**——operator 必须为学生本人，违反写 t_security_audit。`withinRange/isMock` 服务端复算，超范围不直接定性作弊、允许说明。

### 5.7 打卡异常列表
- `GET /api/v1/teacher-mobile/internship/checkin-exceptions`。教师 T18。响应 `items[] { studentName, enterprise, checkinTime, location, distance, exceptionType, studentNote, handleStatus }`。权限 `intern:checkin:handle`。表 t_checkin。一期 P3。

### 5.8 补卡申请/审核
- 申请 `POST /student-mini/internship/checkins/{id}/makeup`；审核 `POST /teacher-mobile/internship/checkins/{id}/makeup/review`（体含 action/comment/version）。状态 makeup PENDING/APPROVED/REJECTED。审计 是。一期 P3。

### 5.9 周报列表
- `GET /api/v1/{端}/internship/reports?studentId=&reportType=weekly&status=&page=`。响应版本列表。权限 `intern:report:view`。分页 是。表 t_intern_report。一期 P3。

### 5.10 周报提交
- **方法/路径**：`POST /api/v1/student-pc/internship/reports`（长文走 PC；小程序可草稿）
- **请求体**：`{ reportType:"weekly|monthly", weekNo, content, attachmentFileIds, clientDraftId, requestId }`。
- **权限**：SELF + `intern:report:create`。**审计**：是。**幂等**：clientDraftId/requestId。**表**：t_intern_report、t_mini_draft。**一期**：P3。状态 DRAFT→SUBMITTED。

### 5.11 周报批阅
- **方法/路径**：`POST /api/v1/teacher-mobile/internship/reports/{id}/review`
- **请求体**：`{ action:"APPROVE|RETURN", comment, rejectReason?, version, requestId }`。
- **用途**：教师 T20 周报批阅（移动/PC）。
- **权限**：`intern:report:review`。**数据范围**：INTERN_STUDENTS（只批本人指导学生）。**审计**：是。**乐观锁/幂等**：是。**校验**：RETURN 时 rejectReason ≥5字。**表**：t_intern_report；退回生成学生待办+消息+不可关闭 InlineAlert。**一期**：P3。状态 APPROVED/RETURNED。

### 5.12 请假申请
- `POST /api/v1/student-mini/internship/leaves`，体 `{ leaveType, startAt, endAt, reason, proofFileId, clientDraftId }`。SELF。表 t_leave。一期 P3。旁路态 LEAVE_PENDING。

### 5.13 请假审批
- `POST /api/v1/teacher-mobile/internship/leaves/{id}/approve|reject`，体 `{ comment, rejectReason?, version, requestId }`。权限 `intern:leave:review`。审计 是。表 t_leave。一期 P3。通过后联动打卡状态。

### 5.14 巡访记录
- `GET/POST /api/v1/teacher-mobile/internship/visits`。POST 体 `{ studentId, visitDate, summary, requestId }`。权限 `intern:visit:create`。表 t_teacher_visit。一期 P3。

### 5.15 实习风险
- `GET /*/internship/risks`；处理 `POST /*/internship/risks/{id}/handle`，体 `{ action:"ACCEPT|PROCESS|CLOSE|ESCALATE", measure, evidenceFileId, version, requestId }`。风险闭环 PENDING→PROCESSING→HANDLED→CLOSED/ESCALATED。审计 是。CLOSE/ESCALATE 二次确认。表 t_complaint。一期 P3。

### 5.16 企业评价
- **方法/路径**：`POST /api/v1/enterprise-portal/evaluations`（企业端；P3 移动入口 `/teacher-mobile/enterprise/evaluations`）
- **请求体**：`{ studentId, itemScores:{...}, total, hireIntention, comment, version, requestId }`。
- **权限**：`enterprise:evaluation:submit`。**数据范围**：ENTERPRISE_AUTH_STUDENTS（仅授权学生）。**审计**：是。**表**：t_enterprise_eval。**一期**：P3。
- **红线**：企业导师**不可**看学生家庭/心理/处分/毕设成果、不可批量导出；评价提交后不可直接改（需审批）。

### 5.17 实习成绩
- 权重配置 + 核算 + 发布：`GET/POST /api/v1/admin/internship/scores`；核算 `.../calc`；发布 `.../publish`（体 version/requestId）。五项权重+及格线+incomplete。状态 PENDING_CALC→PENDING_REVIEW→PUBLISHED→WITHDRAWN。审计 是。发布二次确认。表 t_intern_score_config、t_intern_final_score。一期 P3。

### 5.18 实习归档
- `POST /api/v1/admin/internship/filings`（生成/催补/核验/归档，体 action/version）。归档五态。权限 `intern:archive`。审计 是。表 t_filing_record（biz_module=INTERNSHIP）。一期 P3。

---

## 一期范围小结（本文档）
全部 P3（岗位实习为第一主攻）。P6-1 首批 3 页闭环优先：我的实习(5.2)/周报(5.9-5.11)/周报批阅——对齐 P5.5 拍板。其余按 06 中心 §17 顺序推进。
