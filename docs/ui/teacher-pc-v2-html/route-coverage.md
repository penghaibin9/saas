# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单或权限事实源。完整机器追溯见 `prototype-manifest.json` 与 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**261**
- 独立 HTML：**254**
- 共享 HTML 路由条目：**9**
- 共享设计文件：**35**
- 仓库截图：**0**
- 已记录本地历史渲染截图：**309**
- 已完成首轮工作区：**24**
- 一级中心完成：**0**

旧统计 175 / 169 / 17 / 15 已废止。旧总 manifest 只加载到 `120-exam.json`，没有聚合已经存在的 `130` 至 `180`；本轮已补齐聚合并新增 `190-quality.json`、`200-archive.json` 与 `210-stats.json`。

## 教务中心导航（已冻结）

- 左侧菜单按 `frontend/src/config/navPlan.js` 冻结顺序直接展示 **29 个真实二级模块**。
- 取消原型聚合分组；分组不得作为菜单、折叠层级、路由、页面或面包屑节点。
- 导航层级为：**顶部一级中心 → 左侧真实二级模块 → 内容区三级功能**。
- 共享壳支持二级菜单搜索、独立纵向滚动、展开 / 收起、当前模块高亮和严格三级面包屑。
- 权限继续以生产菜单投影和后端裁决为准，本 PR 不修改权限、角色或数据范围。

## 已进入首轮设计追踪的工作区

| 序号 | 工作区 | manifest | 独立 HTML | 当前口径 |
|---:|---|---|---:|---|
| 1 | 成绩管理 | 基线部分 | 已登记 | 首轮完成 |
| 2 | 成绩审核发布更正 | 基线部分 | 已登记 | 首轮完成 |
| 3 | 学籍管理 | 基线部分 | 已登记 | 首轮完成 |
| 4 | 注册管理 | `10-registration.json` | 已登记 | 首轮完成 |
| 5 | 学籍异动办理 | `20-status-changes.json` | 已登记 | 首轮完成 |
| 6 | 学院专业班级 | `40-org-console.json` | 已登记 | 首轮完成 |
| 7 | 学年学期 | `50-terms-calendar.json` | 已登记 | 首轮完成 |
| 8 | 校历节次 | `50-terms-calendar.json` | 已登记 | 首轮完成 |
| 9 | 课程库 | `60-courses.json` | 已登记 | 首轮完成 |
| 10 | 培养方案 | `70-programs.json` | 已登记 | 首轮完成 |
| 11 | 教学任务 | `80-teaching-tasks.json` | 已登记 | 首轮完成 |
| 12 | 课表管理 | `90-schedule.json` | 已登记 | 首轮完成 |
| 13 | 调停课 | `100-schedule-change.json` | 已登记 | 首轮完成 |
| 14 | 选课管理 | `110-selection.json` | 12 | 首轮完成 |
| 15 | 考务管理 | `120-exam.json` | 11 | 首轮完成 |
| 16 | 补考重修缓考免修 | `130-makeup.json` | 8 | 首轮完成 |
| 17 | 学业预警 | `140-warning.json` | 11 | 首轮完成 |
| 18 | 毕业资格审核 | `150-graduation.json` | 15 | 首轮完成 |
| 19 | 教材管理 | `160-textbook.json` | 7 | 首轮完成 |
| 20 | 教学资源 | `170-resource.json` | 9 | 首轮完成 |
| 21 | 教学评价 | `180-evaluation.json` | 8 | 首轮完成 |
| 22 | 教学质量 | `190-quality.json` | 8 | 首轮结构完成；浏览器回归待执行 |
| 23 | 教务归档 | `200-archive.json` | 4 | 首轮结构完成；浏览器回归待执行 |
| 24 | 教务统计 | `210-stats.json` | 15 新页 + 1 复用页 | 首轮结构完成；浏览器回归待执行 |

“首轮完成”不等于生产施工完成，也不等于当前 HEAD 的全量浏览器回归通过。

## 教学评价

8 个入口 HTML、README、回归记录、共享资源与 `180-evaluation.json` 已完整落盘。匿名、最小样本、回避、结果版本、申诉和归档边界已追踪。

## 教学质量

8 个生产入口均有独立 HTML；监控信号不直接定责，事故、整改、复查与归档边界见 `190-quality.json`。

## 教务归档

4 个生产入口均有独立 HTML；一学期一批次、6 状态、语义门禁、强制归档、封存写保护、解冻和导出审计见 `200-archive.json`。

## 教务统计（本轮补齐）

| 生产路由 | HTML | 权限 | 复用关系 |
|---|---|---|---|
| `/admin/academic-affairs/stats` | `stats/stats-overview.html` | `academicAffairs.stats.view` | 统计总览母版 |
| `?tab=statusChange` | `stats/stats-status-change.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=registration` | `stats/stats-registration.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=course` | `stats/stats-course.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=teachingTask` | `stats/stats-teaching-task.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=schedule` | `stats/stats-schedule.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `/schedule-change/stats` | `schedule-change/schedule-change-stats.html` | `academicAffairs.scheduleChange.view` | 复用既有独立页 |
| `?tab=courseSelection` | `stats/stats-selection.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=exam` | `stats/stats-exam.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=grade` | `stats/stats-grade.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=warning` | `stats/stats-warning.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=graduation` | `stats/stats-graduation.html` | `academicAffairs.stats.view` | 共享统计母版 |
| `?tab=workload` | `stats/stats-workload.html` | `academicAffairs.stats.view` | 工作量独立切面 |
| `?tab=resource` | `stats/stats-resource.html` | `academicAffairs.stats.view` | 学校级资源切面 |
| `/admin/academic-affairs/workload-review` | `stats/workload-review.html` | `academicAffairs.stats.view` | 独立审核页 |
| `?tab=export` | `stats/stats-export.html` | `academicAffairs.stats.export` | 正式导出页 |

### 教务统计事实边界

- 百分比保留分子分母、口径、范围、更新时间与下钻来源。
- 摘要和明细使用相同筛选与后端数据范围。
- 未配置学院范围时 fail-closed。
- 零值、空数据、未启用、无范围和请求失败分别展示。
- 调停课统计复用独立业务页，不在聚合页重复造入口。
- 教学资源统计为学校级资产，不添加学期 / 学院筛选。
- 教师工作量仅供教务参考，不承担薪酬核算。
- 工作量审核只有 `SUBMITTED / APPROVED / REJECTED`，驳回原因至少 5 字。
- 导出为同步 XLSX，用途至少 5 字；无虚假异步历史列表。

完整字段、下钻、权限与口径见 `210-stats.json` 和统计 README。

## 下一批：专业分流

必须先核对真实生产三级入口、Vue、API、权限与状态，再区分批次、规则、志愿、资格、自动分配、人工调整、结果发布、异议和归档；不得复制第二套专业、班级或学生主档。

## 尚未覆盖或未收口

### 教务中心

- 专业分流
- 教学计划独立映射说明
- 排课管理复杂工作台
- 课堂考勤
- 教务看板与部分入口的统一回归

### 其他一级中心

- 工作台其余页面和全局审批、消息、帮助、数据中心
- 学工中心
- 岗位实习中心
- 毕业设计中心
- 系统管理
- 登录、安全与其余打印 / 导出预览

## 尚未完成的验证

- 当前 **254 个 HTML** 尚未在同一最新 HEAD 下完成一次全量浏览器回归。
- 教学质量 8 页、教务归档 4 页和教务统计 15 页尚未完成三档分辨率、控制台、溢出、键盘和焦点回归。
- 仓库截图和打印 PDF 均为 0。

未覆盖或未验证项不得描述为完成，PR 必须继续保持 Draft。
