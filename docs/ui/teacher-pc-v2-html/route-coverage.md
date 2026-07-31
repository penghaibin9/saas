# 路由覆盖

> 本文件是设计交付清单，不取代生产路由、菜单或权限事实源。完整机器追溯见 `prototype-manifest.json` 与 `manifest-parts/*.json`。

## 当前统计

- manifest 条目：**245**
- 独立 HTML：**239**
- 共享 HTML 路由条目：**8**
- 共享设计文件：**33**
- 仓库截图：**0**
- 已记录本地历史渲染截图：**309**
- 已完成首轮工作区：**23**
- 一级中心完成：**0**

旧统计 175 / 169 / 17 / 15 已废止。旧总 manifest 只加载到 `120-exam.json`，没有聚合已经存在的 `130` 至 `180`；本轮已补齐聚合并新增 `190-quality.json` 与 `200-archive.json`。

## 教务中心导航（已冻结）

- 左侧菜单按 `frontend/src/config/navPlan.js` 冻结顺序直接展示 **29 个真实二级模块**。
- 取消原型聚合分组；分组不得作为菜单、折叠层级、路由、页面或面包屑节点。
- 导航层级为：**顶部一级中心 → 左侧真实二级模块 → 内容区三级功能**。
- 共享壳支持二级菜单搜索、独立纵向滚动、展开/收起、当前模块高亮和严格三级面包屑。
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

“首轮完成”不等于生产施工完成，也不等于当前 HEAD 的全量浏览器回归通过。

## 教学评价（结构完整）

| 生产入口 | HTML | 状态 |
|---|---|---|
| 评教批次（结果分级） | `evaluation/evaluation-batches.html` | COMPLETE |
| 申诉审核 | `evaluation/evaluation-appeals.html` | COMPLETE |
| 学生评教（小程序治理入口） | `evaluation/evaluation-student.html` | COMPLETE |
| 教师自评 | `evaluation/evaluation-self.html` | COMPLETE |
| 同行评价 | `evaluation/evaluation-peer.html` | COMPLETE |
| 督导评价 | `evaluation/evaluation-supervisor.html` | COMPLETE |
| 评价统计 | `evaluation/evaluation-stats.html` | COMPLETE |
| 评价归档 | `evaluation/evaluation-archive.html` | COMPLETE |

完整匿名、最小样本、角色回避、结果版本、申诉与归档边界见 `180-evaluation.json` 和评价 README。

## 教学质量（本轮补齐）

| 生产路由 | HTML | 权限 | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/quality` | `quality/quality-monitor.html` | `academicAffairs.quality.dashboard.view` | STATIC COMPLETE |
| `?tab=supervision` | `quality/quality-supervision.html` | `academicAffairs.quality.record.view` | STATIC COMPLETE |
| `?tab=patrol` | `quality/quality-patrol.html` | `academicAffairs.quality.record.view` | STATIC COMPLETE |
| `?tab=inspection` | `quality/quality-inspection.html` | `academicAffairs.quality.record.view` | STATIC COMPLETE |
| `?tab=incident` | `quality/quality-incident.html` | `academicAffairs.quality.record.view` | STATIC COMPLETE |
| `?tab=rectify` | `quality/quality-rectify.html` | `academicAffairs.quality.rectification.view` | STATIC COMPLETE |
| `?tab=followUp` | `quality/quality-followup.html` | `academicAffairs.quality.rectification.view` | STATIC COMPLETE |
| `?tab=archive` | `quality/quality-archive.html` | `academicAffairs.quality.archive.view` | STATIC COMPLETE |

教学质量监控信号不直接定责；事故、整改、复查与归档边界见 `190-quality.json`。

## 教务归档（本轮补齐）

| 生产路由 | HTML | 权限 | 状态 |
|---|---|---|---|
| `/admin/academic-affairs/archive` | `archive/archive-batches.html` | `academicAffairs.archive.view / manage` | STATIC COMPLETE |
| `/admin/academic-affairs/archive/precheck` | `archive/archive-precheck.html` | `academicAffairs.archive.view` | STATIC COMPLETE |
| `/admin/academic-affairs/archive?entry=batch` | `archive/archive-batch-workbench.html` | `academicAffairs.archive.view / manage` | STATIC COMPLETE |
| `/admin/academic-affairs/archive/export` | `archive/archive-export.html` | `academicAffairs.archive.export` | STATIC COMPLETE |

### 教务归档事实边界

- 一学期一个归档批次。
- 状态为 `DRAFT / CHECKING / READY / MISSING_ITEMS / ARCHIVED / CANCELLED`。
- 语义预检不能用记录数量替代业务完成结论。
- “批量归档”是单学期批次内多域集中处理，不是跨学期一键封存。
- 普通确认只允许 `READY`；缺失批次只能修复或明确强制归档。
- 强制归档必须保留缺失、原因和风险审计。
- 归档后学期封存，核心写入口返回 `409 TERM_ARCHIVED`。
- 特批解冻仅学校管理员，原归档历史不可删除。
- 正式导出仅限已归档批次，下载要求用途、水印、权限和审计。

详细开发契约见 `academic-affairs/archive/README.md` 与 `200-archive.json`。

## 下一批：教务统计

生产入口包括教务总览及注册、异动、成绩、预警、质量等统计与导出。下一批必须先核对真实统计页面、11 项指标、筛选口径、下钻和导出 API，再决定驾驶舱、明细与正式导出的独立切面。

## 尚未覆盖或未收口

### 教务中心

- 专业分流
- 教学计划独立映射说明
- 排课管理复杂工作台
- 课堂考勤
- 教务统计
- 教务看板与部分入口的统一回归

### 其他一级中心

- 工作台其余页面和全局审批、消息、帮助、数据中心
- 学工中心
- 岗位实习中心
- 毕业设计中心
- 系统管理
- 登录、安全与其余打印 / 导出预览

## 尚未完成的验证

- 当前 **239 个 HTML** 尚未在同一最新 HEAD 下完成一次全量浏览器回归。
- 教学质量 8 页与教务归档 4 页尚未完成三档分辨率、控制台、溢出、键盘和焦点回归。
- 仓库截图和打印 PDF 均为 0。

未覆盖或未验证项不得描述为完成，PR 必须继续保持 Draft。
