# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单或权限事实源。完整追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**152**
- 独立 HTML：**146**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**250**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理、调停课
- 一级中心完成：**0**

## 调停课（COMPLETE）

| 路由 / 切面 | 源组件 | HTML | 状态 |
|---|---|---|---|
| `/schedule-change` | `AaScheduleChangeLedgerView.vue` | `schedule-change/schedule-change-ledger.html` | COMPLETE |
| `/schedule-change/apply?type=ADJUST` | `AaScheduleChangeApplyView.vue` | `schedule-change/schedule-change-apply-adjust.html` | COMPLETE |
| `/schedule-change/apply?type=STOP` | 同上 | `schedule-change/schedule-change-apply-stop.html` | COMPLETE |
| 同申请路由冲突态 | 同上 | `schedule-change/schedule-change-apply-conflict.html` | COMPLETE |
| `/schedule-change/approval` | `AaScheduleChangeApprovalView.vue` | `schedule-change/schedule-change-approval.html` | COMPLETE |
| `/schedule-change/stats` | `AaScheduleChangeStatsView.vue` | `schedule-change/schedule-change-stats.html` | COMPLETE |
| `/schedule-change/archive` | `AaScheduleChangeArchiveView.vue` | `schedule-change/schedule-change-archive.html` | COMPLETE |
| 通知单 APPLIED / 未生效 | `AaScheduleChangeNoticePrintView.vue` | `schedule-change/schedule-change-notice-*.html` | COMPLETE |

完整权限、API、字段与状态登记在 `manifest-parts/100-schedule-change.json`。

## 重要事实

- 类型固定为 ADJUST / STOP / MAKEUP。
- 非停课必须提供目标星期与节次；停课必须填写补课计划。
- 冲突预检不落库，正式提交再次调用同一算法；冲突返回 409，单据不落库。
- 审批为学院→教务处两级，终审通过自动改写课表并进入 APPLIED。
- SUBMITTED / COLLEGE_REVIEW 可撤销，APPROVED 后撤销由后端阻断。
- 仅 APPLIED 可打印通知单。

## 尚未覆盖

- 教务中心：专业分流、选课、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
