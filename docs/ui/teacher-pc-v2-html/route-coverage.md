# 路由覆盖

> 本文件是设计交付清单，不取代生产 router、模块 routes、`navPlan.js` 或权限事实源。完整追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**143**
- 独立 HTML：**137**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**231**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理
- 一级中心完成：**0**

## 课表管理（COMPLETE）

| 路由 / 切面 | 源组件 | HTML | 状态 |
|---|---|---|---|
| `/schedule` | `AaScheduleBatchListView.vue` | `schedule/schedule-batches.html` | COMPLETE |
| `/schedule?panel=archive` | 同上 | `schedule/schedule-archive.html` | COMPLETE |
| `/schedule/:batchId/edit` | `AaScheduleMaintainView.vue` | `schedule/schedule-maintain.html` | COMPLETE |
| 同路由 409 冲突态 | 同上 | `schedule/schedule-maintain-conflict.html` | COMPLETE |
| `/schedule/:batchId/views` 班级/教师/学生 | `AaScheduleViewsView.vue` | `schedule/schedule-views-*.html` | COMPLETE |
| 班级/教师/教室/学生/教学班独立课表 | 对应五个 View | `schedule/*-schedule.html` | COMPLETE |
| `/schedule/week` | `AaWeekScheduleView.vue` | `schedule/week-schedule.html` | COMPLETE |
| `/schedule/semester` | `AaSemesterScheduleView.vue` | `schedule/semester-schedule.html` | COMPLETE |
| `/schedule/publish` | `AaSchedulePublishView.vue` | `schedule/schedule-publish.html` | COMPLETE |
| `/schedule/adjustments` | `AaScheduleAdjustmentLogView.vue` | `schedule/schedule-adjustments.html` | COMPLETE |
| `/schedule/export` | `AaScheduleExportView.vue` | `schedule/schedule-export.html` | COMPLETE |
| 打印 class/teacher | `AaPrintScheduleView.vue` | `schedule/print-schedule-*.html` | COMPLETE |

完整权限、API、query 和状态登记在 `manifest-parts/90-schedule.json`。

## 重要事实

- 冲突由后端同一检测器裁决，覆盖教师、班级和教室。
- 发布后课表项不可直改；作废重发必须填写原因并保留发布记录。
- 学生课表合并行政班与本人锁定选课。
- 周/学期课表是五个既有查询端点的组合，不新增第二套后端能力。
- 调整记录只读读取审计流水，不混入独立“调停课”审批台账。
- XLSX 导出带水印和用途审计，范围仅 CLASS/TEACHER/ROOM。

## 尚未覆盖

- 教务中心：专业分流、调停课、选课、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
