# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单或权限事实源。完整追溯见 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**164**
- 独立 HTML：**158**
- 共享 HTML 路由条目：**8**
- 仓库截图：**0**
- 本地累计渲染截图：**276**
- 已完成首轮工作区：成绩管理、成绩审核发布更正、学籍管理、注册管理、学籍异动办理、学院专业班级、学年学期、校历节次、课程库、培养方案、教学任务、课表管理、调停课、选课管理
- 一级中心完成：**0**

## 选课管理（COMPLETE）

| 路由 / 切面 | 源组件 | HTML | 状态 |
|---|---|---|---|
| `/selection` | `AaSelectionConsoleView.vue` | `selection/selection-batches.html` | COMPLETE |
| 同路由 `DRAFT` | 同上 | `selection/selection-draft-config.html` | COMPLETE |
| 同路由轮次/抽签 | 同上 | `selection/selection-rounds.html` | COMPLETE |
| 同路由 `OPEN` | 同上 | `selection/selection-open-monitor.html` | COMPLETE |
| 同路由 `CLOSED` | 同上 | `selection/selection-closed-review.html` | COMPLETE |
| 同路由异常/冲突 | 同上 | `selection/selection-conflicts.html` | COMPLETE |
| 同路由 `LOCKED` | 同上 | `selection/selection-locked-roster.html` | COMPLETE |
| `/my-selection` | `AaSelectionStudentView.vue` | `selection/my-selection-open.html` | COMPLETE |
| 同路由满额态 | 同上 | `selection/my-selection-full.html` | COMPLETE |
| 同路由补选指引 | 同上 | `selection/my-selection-reselect.html` | COMPLETE |
| `/selection/archive` | `AaSelectionArchiveView.vue` | `selection/selection-archive.html` | COMPLETE |
| 同路由归档详情 | 同上 | `selection/selection-archive-detail.html` | COMPLETE |

完整权限、API、字段与状态登记在 `manifest-parts/110-selection.json`。

## 重要事实

- 批次状态为 `DRAFT → PUBLISHED → OPEN → CLOSED → LOCKED → ARCHIVED`。
- 不建轮次时全程先到先得；轮次支持 `FCFS / LOTTERY`。
- 轮次通过 `allowEnroll / allowDrop` 表达可选可退、只选和只退。
- 抽签轮次关闭后摇号，结果一次性，不提供重摇。
- 截止后可取消低人数课程，原记录进入 `COURSE_CANCELLED`，学生通过补选指引重新选择。
- 正式选课事实以锁定名单为准。
- 归档只查询 `ARCHIVED` 批次，导出 XLSX 前用途不少于 5 字。

## 尚未覆盖

- 教务中心：专业分流、考务、补考重修、预警、毕业审核、教材、教学资源、评价、质量、统计归档其余切面。
- 工作台其余页面及全局审批、消息、帮助、数据中心。
- 学工中心、岗位实习中心、毕业设计中心、系统管理。
- 登录、安全、其余打印/导出预览。

未覆盖项不得描述为完成。
