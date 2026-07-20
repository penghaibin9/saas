# 小程序端 · 学生↔教师对接能力对照与缺口清单

> 日期：2026-07-17　类型：只读审计结论（可对照继续开发）
> 文件名用 ASCII（本会话工具对中文文件名会乱码，内容中文不受影响）
> 范围：微信小程序端（uni-app，`miniapp/`）学生端 ↔ 教师端 的业务对接闭环
> 事实源：`miniapp/src/pages.json`、`backend/app/api/v1/mobile.py`、`backend/app/services/mobile_teacher_service.py`、各业务 service、PC 端 `frontend/src/views/admin/**`

## 一、总体结论

**小程序端师生对接能力基本齐全，不存在“学生能发起但无人能处理”的断链。** 覆盖靠两层机制：

1. **统一审批引擎**：学生申请类写操作生成“统一待办”（WorkflowTask/UnifiedTodo），教师端 `/mobile/teacher/approvals` 聚合 `approval_service.list_tasks(PENDING)` → `approval_act(approve/reject)` 处理。
2. **各中心专用移动处理队列**：实习/毕设/教务/就业/迎新/心理/学工各自有教师专用移动端点。

真正的“移动端缺口”只有 2~3 项，且均为“PC 端能处理、手机端未移动化”，不是业务断链。

## 二、已闭环清单（学生小程序发起 → 教师小程序端可处理）

### 2.1 统一审批引擎覆盖（生成统一待办 → 教师 approvals 待办）
证据：以下 service 均创建统一待办（grep create_task/WorkflowTask/create_todo 命中）。

| 学生发起 | 后端 service | 教师处理 |
|---|---|---|
| 学工请假 | affairs_leave_service | teacher/approvals + affairs/leave/{id}/handle |
| 困难认定 | affairs_aid_service | teacher/affairs/aid/{id}/handle |
| 奖助申请 | affairs_funding_service | teacher/approvals（统一引擎）|
| 学籍异动 | academic_affairs_change_service | teacher/approvals（统一引擎）|
| 违纪/申诉 | affairs_discipline_service | teacher/approvals |
| 学业预警/风险 | academic_affairs_warning_service / affairs_risk_service | teacher/approvals + risk-students |
| 成绩/调课 | academic_affairs_grade_service / _schedule_change_service | teacher/approvals |

### 2.2 各中心专用移动处理队列（教师专用端点，均已建）
| 学生发起 | 教师移动端点（mobile.py / mobile_teacher_service） |
|---|---|
| 实习周报 | teacher/internship/weekly-reviews + weekly/{id}/review |
| 实习补卡 | makeup_pending + makeup_review |
| 实习请假 | leave_pending + review |
| 打卡异常 | exception_handle |
| 实习鉴定/自评 | student-evals + advisor-comment + review |
| 企业评价 | enterprise-evals + review |
| 实习保险 | insurances/pending + verify |
| 调岗退岗 | change-requests/pending + review |
| 实习成绩 | scores + compute + publish |
| 三方协议 | agreements/pending-school |
| 毕设开题 | graduation/proposal/{id}/review |
| 毕设论文 | graduation/final/{id}/review |
| 毕设中期 | graduation/midterm/queue + review |
| 毕设成绩 | graduation/grade/queue + submit |
| 成绩录入 | academic/grade-tasks + save |
| 课堂考勤 | attendance/sessions + save |
| 心理自评(超阈值) | mental/referrals + handle |
| 谈心谈话 | talk/{id}/complete |
| 就业 | employment/followup + add |
| 迎新现场报到 | orientation/today-checkins |

## 三、未闭环 / 移动端缺口（PC 有、小程序无 —— 待“干”）

> 均为“未移动化”，学生发起后 PC 端可处理，不影响业务闭环。补不补是产品选择。

| # | 缺口 | 现状 | 落地方式 | 优先级 |
|---|---|---|---|---|
| 1 | 迎新绿色通道审核（移动） | orientation 服务不进统一待办；PC 有 PaymentGreenChannelView 审核 | 新增教师移动端点（复用现有 PC 绿通审核 service，大概率不需新表）+ 教师小程序页 | 中 |
| 2 | 在校服务工单处理（移动） | campus_service 工单（CsWorkOrder）不进统一待办；PC 处理 | 新增教师移动端点（复用现有工单 service）+ 教师小程序页 | 中 |
| 3 | 毕设成绩申诉受理（移动） | 学生可申诉（graduation/grade/appeal），教师移动无专门受理页 | 待最终确认；若无 → 复用 PC 申诉 service 加移动端点 | 低 |

## 四、说明

- 本清单为只读审计结论；实际“干”（补移动端点/教师页）时须再核对目标 service 是否已存在、是否真需新表。
- 缺口 1/2/3 复用现有 PC service 的概率高 → 多为“零建表 / 加移动壳”，但会改到 backend/app/api/v1/mobile.py（近期在并行编辑，需注意合并冲突）与新增教师页。
- 学生端已完成三批修复：d54e469 实习假入口/plan 守卫、93feae4 申请/消息假按钮+崩溃、5ea63fb 个人数据导出（零建表）。
- 帮助反馈建表（t_feedback）代码就绪但迁移暂缓（检测到共享 dev 库有活跃 DDL），待库空闲执行。

## 五、下一步（对照开发）

按优先级：先做缺口 1「绿色通道审核移动化」→ 缺口 2「工单处理移动化」→ 缺口 3。每项：先核实现有 PC service → 加教师移动端点（避让 mobile.py 冲突，可用独立 router）→ 教师小程序页 → 双端 build + 提交。
