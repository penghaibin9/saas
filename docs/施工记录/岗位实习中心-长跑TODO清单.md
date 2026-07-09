# 岗位实习中心 · 长跑 TODO 清单（机器可执行）

> 落盘：2026-07-09 ｜ 配套 `岗位实习中心-长跑开发总控任务书.md`。每项含：改哪些文件 / 新增接口 / 新增表字段 / 补哪些测试 / 用哪些公共组件 / 验收命令 / commit 建议。
> 状态标记：`[x]`=已完成 `[~]`=partial `[ ]`=未开工。**进入每阶段前先重读 §2 前置协议并输出「本阶段施工计划」。**
> 通用验收命令（后端·MySQL 测试库）：`cd backend && .venv/Scripts/python.exe -m pytest tests/<file> -q`；前端：`cd frontend && npm run build && npm run lint`。
> 通用公共组件（除特别注明，新页一律用）：AppPageShell/AppSectionCard/AppToolbar、AppPermissionButton、AppStatusTag/AppRiskTag、AppSensitiveText、AppAuditTrail、AppExportButton/AppExportConfirm、AppDescriptionList、AppBatchActionBar、AppOperationResult、AppStudentPicker/AppTeacherPicker/AppCompanyPicker/AppPositionPicker/AppBatchPicker、AppFileList/AppFilePreview（附件预留）。

---

## P0 · 安全底座与可达性收口

### [x] P0-C 管理端 require_staff 门禁 ✅ 已完成（2026-07-09）
- 文件：`backend/app/api/v1/router.py`（+`_INTERN_DEP`，给 internship/internship_position/internship_agreement_template/internship_student/internship_match/employment 加门禁）
- 测试：`backend/tests/test_internship_staff_gate.py`（学生403/未登录401/教职工200）→ **3 passed**；回归 `test_internship.py` **9 passed**
- 验收：`pytest tests/test_internship_staff_gate.py tests/test_internship.py -q`
- commit 建议：`fix(internship): enforce require_staff on management routers`

### [x] P0-B 路由全局挂载 ✅ 已核实（无需改）
- `frontend/src/router/index.js:18,37` 已挂 `internshipRoutes`；11 子页刷新直达可达。建议后续删 `routes.js` 顶部过期注释。

### [x] P0-F 小程序 URL / useMock ✅ 已核实（无 bug）
- `miniapp/src/services/realApi.js` 写接口均正斜杠；`env.js useMock:true` 为 dev 开关。切真实：置 false + 起后端，手动验打卡/周报/批阅/异常真实落库。

### [ ] P0-D 管理端数据范围细分  ← **下一步优先**
- 改文件：`backend/app/services/internship_service.py`、`internship_student_service.py`、`employment_service.py`（在 list/detail/dashboard/weekly/exception/risk/match 的 tenant 过滤后叠加范围过滤）；复用 `resolve_teacher_scope`（毕设/学工同款）。
- 新增接口：无（不改入参/返回结构；仅收窄可见行）。
- 新增表/字段：无（用现有 advisor_name/counselor/college 关系；若缺关联，评估最小加列并记 alembic）。
- 补测试：`backend/tests/test_internship_scope.py`（教师A看不到教师B学生 / 学院负责人看本院 / 管理员看全校 / 学生管理接口403 / 跨租户不可见）。
- 公共组件：无（后端）。
- 验收：`pytest tests/test_internship_scope.py tests/test_internship_student.py -q`
- commit 建议：`feat(internship): apply data scope to management APIs`

### [ ] P0-E 实习学生 CSV→xlsx
- 改文件：`backend/app/api/v1/internship_student.py`（export→xlsx、import→xlsx 上传+dry-run+confirm+errors-xlsx+template）、`internship_student_service.py`；接 `backend/app/services/excel/`（ImportSpec/ExportSpec）；前端 `frontend/src/modules/internship/api/internship-student.api.js`、`InternshipStudentListView.vue`（导入导出按钮改 xlsx）。
- 新增接口：`POST /internship/intern-students/import/xlsx|errors-xlsx`、`GET /internship/intern-students/import/template`（export 已有→改 xlsx 输出）。
- 表/字段：无。
- 模板 15 列：学号/姓名/学院/专业/班级/指导教师/企业名称/岗位名称/实习批次/实习开始/实习结束/联系电话/实习状态/就业去向/备注。
- 补测试：`test_internship_student.py` 增 xlsx 模板+上传+错误行+导出脱敏用例。
- 公共组件：前端用 AppExportButton/AppExportConfirm；导入用公共 Excel 前端底座（`components/common/excel/`）。
- 验收：`pytest tests/test_internship_student.py -q` + 前端 build/lint。
- commit 建议：`feat(internship): replace student CSV with xlsx import/export`

### [~] P0-G alembic 迁移（上线前必补，记账）
- 为 t_internship_batch/record/attendance_exception/weekly_report/risk_record/position、emp_company 实习附加列、t_internship_enterprise_contact、intern-student 附加列补 `backend/alembic/versions/00XX_*.py`；服务器迁移前备份。分类：上线前必补。

---

## P1 · 过程监管闭环（P0 通过后）

### [ ] P1-A 请假异常
- 文件：新 `backend/app/models/internship_leave.py`(t_internship_leave)、`schemas/internship_leave.py`、`services/internship_leave_service.py`、`api/v1/internship_leave.py`（+router.py 注册加 `_INTERN_DEP`）；前端新 `views/admin/internship/InternshipLeaveListView.vue`+detail、`modules/internship/api/leave.api.js`、`routes.js`、`navPlan.js`(in-leave 点亮)；小程序学生请假入口（若接）。
- 接口：list/detail/create/submit/approve/reject/withdraw/cancel(销假)/archive/export(xlsx)。
- 表字段：student_id/batch_id/leave_type/start/end/reason/status/approver/审计字段/file_id 预留；与 t_attendance_exception 联动（请假期间打卡缺卡不计异常）。
- 状态机：待提交→待审核→已通过/已驳回/已撤回→已销假→已归档（非法流转后端拒 + 审计）。
- 测试：`test_internship_leave.py`（状态机全链/越权/数据范围/xlsx/审计/与打卡联动）。
- 公共组件：AppApprovalPanel（审批）、AppStatusTag、通用清单。
- 验收：`pytest tests/test_internship_leave.py -q` + 前端 build/lint。
- commit：`feat(internship): add leave exception workflow`

### [ ] P1-B 指导记录
- 文件：新 model `t_internship_guidance`、schema、service、api（+注册门禁）；前端 `InternshipGuidanceListView.vue`+detail、api、routes、navPlan(in-guidance)；教师小程序入口（若接 `/mobile/teacher/internship/guidance`）。
- 接口：list/detail/create/update/void/export(xlsx)。
- 字段：指导教师/学生/企业/岗位/批次/指导方式(线上·电话·现场·企业导师反馈·视频)/主题/内容/问题类型/处理建议/下次跟进日期/是否形成风险/是否通知辅导员/file_id 预留/审计。
- 测试：`test_internship_guidance.py`（CRUD/数据范围/是否转风险/xlsx/审计）。
- 公共组件：AppFilePreview/AppFileList（附件）、AppTeacherPicker/AppStudentPicker、AppStatusTag。
- 验收：`pytest tests/test_internship_guidance.py -q` + build/lint。
- commit：`feat(internship): add guidance records workflow`

### [ ] P1-C 教师巡访（成熟商业对标项）
- 文件：新 model `t_internship_visit`、schema、service、api（+门禁）；前端页+api+routes+navPlan(in-visit)。
- 接口：list/detail/plan/create/update/rectify-followup/export(xlsx)。
- 字段：巡访计划/对象/企业/时间/方式/企业反馈/学生反馈/安全隐患/整改要求/整改截止/整改状态/巡访月报/file_id 预留/审计。
- 测试：`test_internship_visit.py`（整改状态机/数据范围/xlsx/审计）。
- 公共组件：同上 + AppWorkflowTimeline（整改跟进）。
- commit：`feat(internship): add teacher visit records`

### [ ] P1-D 风险处置全流程（现仅 list）
- 文件：`backend/app/services/internship_service.py`（补 risk create/handle/close/escalate/followup/复盘 + 状态机）、`api/v1/internship.py`（+ risk 动作端点）；前端 `InternshipRiskView.vue`（工具条 toast 占位改真实动作 + 权限按钮 + 数据范围）。
- 接口：`POST /internship/risks`、`/risks/{id}/handle|close|escalate|followup`、`GET /risks/{id}`、`POST /risks/export`(xlsx)。
- 表：复用 t_risk_record（已有 PENDING_HANDLE/PROCESSING/RESOLVED/CLOSED + owner/deadline 字段）。
- 状态机：待处理→处理中→已升级/已关闭→已归档。
- 测试：`test_internship_risk.py`（创建/自动风险/流转/关闭/升级/数据范围/xlsx/审计）。
- 公共组件：AppApprovalPanel/AppBatchActionBar/AppRiskTag/AppPermissionButton/AppAuditTrail。
- commit：`feat(internship): complete risk handling workflow`

### [ ] P1-E PC 打卡台账 + 补卡审批（成熟商业·防作弊字段）
- 文件：`services/internship_service.py`（打卡台账查询 over t_internship_checkin + 补卡状态机）、`api/v1/internship.py`（+ checkin 台账/补卡端点）；新 model 或复用 t_internship_checkin 补 makeup 字段；前端 `InternshipAttendanceLedgerView.vue`（明细/异常筛选/补卡审批）+ 打通移动端真实打卡数据。
- 接口：`GET /internship/checkins`(台账，多筛选)、`POST /internship/checkins/makeup`(补卡申请)、`/checkins/makeup/{id}/approve|reject`、`POST /internship/checkins/export`(xlsx)。
- 表字段（防作弊全集，缺对象存储/地图则字段预留+标 partial）：student/batch/enterprise/position/打卡时间/类型(上班·下班·外勤·补卡)/经纬度/地址/与企业距离/超范围/设备ID/is_mock/异常设备/重复打卡/风险等级/异常原因/处理状态/补卡关联/审计。
- 状态机：补卡 待审→通过/驳回。
- 测试：`test_internship_attendance.py`（台账筛选/补卡审批/防作弊字段/数据范围/xlsx/审计；不伪造定位照片）。
- 公共组件：AppStatusTag/AppRiskTag/AppBatchActionBar/AppExportButton/AppSensitiveText。
- commit：`feat(internship): add attendance ledger and makeup approval`

### [ ] P1-F 岗位申请五级审核 + 换岗/退岗（成熟商业·五级状态机）
- 文件：新 model `t_internship_application`(五级)、schema、service、api（+门禁）；换岗/退岗接 t_internship_record + t_internship_position(名额)；前端 `InternshipApplicationView.vue` + navPlan(in-apply/in-assign)；学生小程序申请入口预留。
- 接口：apply/submit/teacher-review/enterprise-confirm/school-confirm/hire/reject/withdraw、change-post/quit-post。
- 状态机：待学生提交→待指导教师审核→教师同意→待企业确认→企业已确认→学校已确认→已录用/已分配；旁支 已驳回/学生撤回/已换岗/已退岗/已归档。每态明确操作人/按钮/下一态/非法拒绝/审计/pytest。
- 测试：`test_internship_application.py`（五级流转 + 每态操作人 + 非法拒绝 + 换岗名额 + 数据范围）。
- 公共组件：AppApprovalPanel/AppWorkflowTimeline/AppStatusTag/AppPermissionButton。
- commit：`feat(internship): add multi-level job application workflow`

---

## P2 · 协议、评价、成绩闭环（P1 通过后）

### [ ] P2-A 三方协议签署实例（现仅模板库·双状态）
- 文件：新 model `t_internship_agreement`(实例，区别于 template)、schema、service、api（+门禁）；前端协议实例页 + navPlan(in-agreement 补 planned 叶子)。
- 接口：模板选择/实例生成/学生确认/企业确认/学校确认/上传(file_id)/查看/下载/作废/归档/export(xlsx)。
- 字段：template_id/student/enterprise/position/batch/学生确认状态/企业确认状态/学校确认状态/协议总状态/file_id 预留/审计。
- 状态机（总）：草稿→待学生确认→待企业确认→待学校确认→已生效→已驳回/已作废/已归档；无电子签章则「确认流+归档+电子签预留」标 partial。
- 测试：`test_internship_agreement.py`（双状态流转/非法拒绝/数据范围/xlsx/审计）。
- 公共组件：AppApprovalPanel/AppFileList/AppFilePreview/AppStatusTag。
- commit：`feat(internship): add agreement signing workflow`

### [ ] P2-B 企业评价（企业导师最小授权预留）
- 文件：新 model `t_internship_enterprise_eval`、schema、service、api；前端页；**企业导师门户权限预留**（只看授权学生/只填评价/操作审计，不做企业端页面也须权限+文档预留，禁学校老师代填假闭环）。
- 字段：企业导师/学生/岗位/批次/出勤·技能·态度·协作·安全纪律评价/综合评语/是否建议录用/提交状态/学校审核/审计。
- 测试：`test_internship_enterprise_eval.py`（提交/学校审核/授权边界/数据范围/导出）。
- 公共组件：AppApprovalPanel/AppStatusTag/AppSensitiveText。
- commit：`feat(internship): add enterprise evaluation`

### [ ] P2-C 学生鉴定 / 学生评价
- 文件：新 model `t_internship_student_eval`、schema、service、api；前端页。
- 字段：学生自评/实习总结/收获/问题/企业导师意见/指导教师意见/学校审核/审计/归档。
- 测试：`test_internship_student_eval.py`。
- commit：`feat(internship): add student self-appraisal`

### [ ] P2-D 实习成绩（五项权重·成熟商业核心）
- 文件：新 model `t_internship_score_config`(权重) + `t_internship_final_score`、schema、service(核算)、api；前端成绩页。
- 字段：打卡/周报/月报总结/企业评价/学校评价权重 + 指导教师评分 + pass_line + 五项分 + total + incomplete + 状态。
- 状态机：待核算→待复核→已发布→已撤回→已归档。
- 测试：`test_internship_score.py`（**权重和=100 / 缺项不能发布 / 计算正确 / 复核留痕 / 非法发布拒 / 数据范围隔离**）。
- 公共组件：AppDescriptionList/AppMetricCard/AppStatusTag/AppApprovalPanel。
- commit：`feat(internship): add internship grade calculation`

---

## P3 · 归档统计与商业 UI 统一（P2 通过后）

### [ ] P3-A 实习归档中心
- 文件：新 service/api 归档聚合（按学生/批次/企业 + 材料完整性检查 + 缺失提醒 + 归档包 file_id 预留）；前端归档中心页 + navPlan(in-archive)。
- 接口：archive-by-student/batch/enterprise、check-completeness、export(xlsx)。
- 测试：`test_internship_archive.py`（完整性检查/缺失提醒/无 file_id 不宣称完成/审计）。
- 公共组件：AppFileList/AppOperationResult/AppStatusTag。
- commit：`feat(internship): add archive center`

### [ ] P3-B 实习统计中心
- 文件：新 stats service/api（实习覆盖率/岗位匹配率/打卡异常率/周报提交率/风险学生数/协议签署率/成绩分布/就业转化率/企业合作质量 + 学院·专业·班级筛选）；前端统计中心页 + navPlan(in-stats)。
- 测试：`test_internship_stats.py`（各指标口径/维度筛选/数据范围）。
- 公共组件：AppMetricCard/AppChartCard(partial 未接图表库则外壳)/AppDescriptionList。
- commit：`feat(internship): add statistics center`

### [ ] P3-C 公共组件全面接入（低风险改造既有 16 页）
- 文件：`frontend/src/views/admin/internship/*`（手写权限按钮→AppPermissionButton、状态→AppStatusTag/AppRiskTag、脱敏 maskNo()→AppSensitiveText、AuditTrailPanel→AppAuditTrail、导出→AppExportButton/AppExportConfirm、附件→AppFileList、审核区→AppApprovalPanel、批量→AppBatchActionBar、骨架→AppPageShell/AppSectionCard/AppToolbar）。
- 约束：不改业务流程/接口/状态机；不重写 DataTable/AdvancedFilter/AppDrawer。
- 验收：build/lint + `/dev/components` 对照 + 无 console error + 页面 smoke test。
- commit：`refactor(internship): adopt shared SaaS components`

---

## P4 · 最终全量验收

### [ ] P4 生产级长跑报告 + 《成熟商业岗位实习系统对标达成表》
- 输出报告 25 项（阶段/commit hash/文件/接口/表字段/迁移/前端页/小程序/测试/权限结果/数据范围结果/xlsx 结果/审计结果/build/lint/pytest/implemented/partial/blocked/不能上线项/PC 试点/学生小程序/教师小程序/是否打 tag/剩余混杂说明/是否 push=否）。
- 《对标达成表》列：能力项 / 成熟系统应有 / 本项目是否实现 / 状态 / 页面 / 接口 / 表 / 测试 / 是否可试点 / 是否可上线 / 未完成原因。覆盖 28 能力项（实习计划…小程序教师端）。
- 全量验收：`cd backend && .venv/Scripts/python.exe -m pytest tests/test_internship*.py tests/test_employment.py -q`（MySQL 并发 DDL 报错则单文件跑并说明）；`cd frontend && npm run build && npm run lint`。
