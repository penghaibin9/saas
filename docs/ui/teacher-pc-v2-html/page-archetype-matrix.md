# Teacher PC V2 页面母版矩阵

> 目标从“每条路由复制一份 HTML”调整为：业务形态覆盖、特殊状态覆盖、高风险交互覆盖、真实路由追踪完整度和公共组件可实现性。

## 1. 审计口径

- 当前统计基于分支最新文件清单：**158 个独立 HTML**、**164 条 manifest 路由 / 业务切面**。
- HTML 数量不是完成度指标。相同布局和交互仅因标题、字段或查询参数不同，不应长期维护多份共享壳与重复脚本。
- 是否需要独立 HTML，主要由以下差异决定：
  1. 信息架构是否不同；
  2. 用户主要任务是否不同；
  3. 是否存在危险或不可逆动作；
  4. 状态机和权限边界是否不同；
  5. 是否需要特殊画布、打印、导入、审批或审计；
  6. 普通公共组件组合是否足以实现。
- 即使复用同一个 HTML 母版，每条真实路由仍必须在 manifest 中登记字段、操作、权限、状态、API 和参数差异。

## 2. 页面母版矩阵

| 母版名称 | 适用页面 / 当前实例 | 对应真实路由示例 | 对应 Vue 页面 / 组件 | 公共组件组合 | 独特交互 | 必须覆盖的状态 | 是否需要独立 HTML | 复用理由 |
|---|---|---|---|---|---|---|---|---|
| 1. 工作台 / 驾驶舱 | 教务看板、我的工作台、中心总览 | `/admin/academic-affairs`、`/` | `AaDashboardView.vue` 等 | `ModulePageShell`、`AppMetricCard`、待办卡、图表、状态组件 | 指标下钻、待办跳转、风险提醒、按角色投影 | 默认、加载、局部失败、无权限、无当前学期、长数据 | **是** | 首屏任务、指标口径和角色差异大，不能降级成标准列表 |
| 2. 标准筛选＋表格列表 | 学期列表、课程列表、注册批次、学籍名册、归档列表 | `/terms`、`/courses`、`/registration`、`/roster` | 对应列表 View | `AppPageHeader`、`AdvancedFilter`、`DataTable`、`AppPagination` | 筛选、排序口径、行操作、批量操作 | 默认、加载、空、错误、403、搜索无结果、长表格 | **通常否** | 结构相同，应共享一个标准列表母版；字段和权限差异放 manifest |
| 3. 列表＋详情双栏 | 选课批次与详情、课程控制台、部分组织控制台 | `/selection`、`/courses/console`、`/orgs` | Console 类 View | `AppCard`、列表菜单、详情卡、抽屉、状态标签 | 左侧选择上下文、右侧局部刷新、状态驱动操作 | 未选中、加载、空、错误、详情失效、只读 | **按工作区独立** | 双栏结构可共享，但右侧任务与状态机差异较大，不能只换文案 |
| 4. 独立详情页 | 学籍档案、课程详情、教学任务详情、教学班详情 | `/roster/:id`、`/courses/:id`、`/teaching-tasks/:id` | Detail View | `ModulePageShell`、`AppDescriptionList`、状态、时间线、审计 | 关联信息切换、返回上下文、只读与操作权限 | 加载、404、403、已归档、关联数据失败、长文本 | **主体类型独立** | 主体模型和关联关系不同；同一主体的状态变体可复用同页 |
| 5. 新建 / 编辑表单 | 新增课程、编辑课程、发起异动、规则编辑 | `/courses/new`、`/courses/:id/edit`、`/status-changes/new` | Form View | `AppForm` 组件族、picker、`AppSubmitBar`、确认弹窗 | 实时校验、草稿、未保存离开提醒、重复提交防护 | 初始、校验失败、保存中、保存失败、只读、数据已变化 | **按字段模型独立** | 字段模型差异真实存在，但表单容器、提交和错误处理必须共享 |
| 6. 多步骤表单 | 培养方案编制、复杂批次配置、导入流程 | `/programs/:id` 等 | Editor / Wizard View | `AppStepBar`、`AppForm`、`AppStickyFooter`、结果组件 | 跨步校验、草稿恢复、步骤锁定、最终提交 | 草稿、步骤错误、保存中、过期版本、只读、提交冲突 | **是** | 跨步骤依赖和版本治理不能由多个普通表单页面拼接 |
| 7. 审批与状态流转 | 学籍异动审批、成绩审核发布、调停课审批、毕业终审 | `/status-changes/approval`、`/grade-college-review`、`/grade-publish`、`/schedule-change/approval` | Approval View | `AppApprovalPanel`、流程时间线、材料、确认、审计 | 通过、退回、原因必填、影响说明、状态刷新 | 待办为空、无权审批、已被他人处理、提交中、失败、终态只读 | **是** | 高风险动作、节点和影响范围不同，必须高保真验证 |
| 8. 配置控制台 | 学年学期、校历、课程分类、组织、选课规则 | `/terms`、`/calendar`、`/courses/console`、`/orgs`、`/selection?tab=rule` | Console View | 页签、表格、抽屉、确认、状态标签 | 新增/编辑配置、启停、发布后锁定、版本切换 | 无配置、部分配置、校验失败、已发布锁定、403、并发变更 | **按配置域独立** | 视觉母版可共享，但锁定条件和依赖关系必须分别登记 |
| 9. 统计分析 | 成绩统计、组织统计、任务统计、选课统计、教务总览 | `/stats?tab=*`、各模块 stats | Stats View | 指标卡、图表卡、筛选、下钻表、导出 | 维度切换、图表下钻、口径说明、导出用途 | 加载、无数据、部分指标失败、数据延迟、权限裁剪 | **大型统计独立；普通统计共享** | 同一统计总览的 Tab 可共享；特殊驾驶舱需独立布局 |
| 10. 日历 / 课表 | 校历、教学周、班级/教师/学生/教室课表 | `/calendar`、`/schedule/class`、`/schedule/teacher` 等 | Calendar / Schedule View | 日期组件、筛选、状态、打印 | 周切换、视角切换、时间网格、冲突标记 | 无当前学期、未发布、空课表、冲突、打印态、长名称 | **是** | 二维时间网格与标准表格不同，且三档分辨率风险高 |
| 11. 排课 / 排考复杂工作台 | 自动排课、人工排课、冲突处理、考务编排 | `/scheduling`、`/schedule`、`/exam` | Workbench View | 页面壳、筛选、专用网格、抽屉、确认、审计 | 资源分配、冲突定位、批量生成、撤销、发布前核验 | 未配置、计算中、部分成功、冲突、发布锁定、数据已变化 | **是** | 核心是二维资源编排，必须独立高保真，不可复用普通列表 HTML |
| 12. 批量操作 | 批量确认、教师分配、班级调整、锁定名单 | `/teaching-tasks/confirm`、`/orgs?tab=adjust`、选课锁定 | Batch View | `DataTable`、批量条、抽屉/表单、确认、结果 | 全选/跨页选择、预检、部分成功、失败重试 | 未选择、权限混合、预检阻断、提交中、部分成功、重复提交 | **高风险批量独立** | 单纯批量导出可共享；改变业务状态或关系的批量操作需独立 |
| 13. 导入导出 | 学籍导入导出、成绩导入、课表导出、归档导出 | `/roster/import-export`、`grade-entry?action=import`、`/schedule/export` | Import / Export View | Excel 流程、文件列表、操作结果、确认 | 模板下载、上传预检、错误行、部分成功、用途审计 | 文件错误、字段错误、重复数据、部分成功、导出失败 | **导入流程独立；普通导出共享** | 导入风险高且步骤多；导出应统一复用公共确认组件 |
| 14. 打印页面 | 异动通知/审批表、班级/教师课表、座位表、准考证、门贴 | `/print/*`、`/exam/print/seating` | Print View | 独立打印壳、`AppPrintButton` | A4 分页、打印预览、禁打原因、签章位 | 数据未生效、无权限、打印数据缺失、长名单、多页 | **是** | 打印版式与后台工作台完全不同，必须独立路由和 CSS |
| 15. 复杂编辑器 | 培养方案课程模块、学分要求、标准映射、版本比较 | `/programs/:id`、`/programs/console?tab=*` | Program Editor | 树/表格、表单、步骤、校验摘要、版本 diff | 拖放/排序、规则校验、版本切换、发布前检查 | 草稿、校验阻断、并发版本、已发布只读、变更待审 | **是** | 编辑对象存在层级、约束和版本，普通 CRUD 页面无法表达 |
| 16. 归档与审计 | 学期归档、课程历史、异动归档、成绩操作审计、组织变更审计 | `/archive`、各模块 archive/audit | Archive / Audit View | 表格、完整性检查、状态、审计、导出确认 | 完整性核验、封存、用途审计、前后值查看 | 缺失数据、阻断、归档中、已封存、只读、导出失败 | **归档控制台和审计详情独立** | 归档与普通列表最大差异是不可逆风险和完整性前置条件 |
| 17. 只读查询页面 | 学年聚合、已发布锁定、归档详情、历史版本、名单查询 | `/terms/years`、archive detail、locked views | Readonly View | 标题、说明、筛选、表格/描述列表、状态 | 查询、下钻、导出（若有权限），不提供写操作 | 空、错误、403、数据延迟、已封存、长数据 | **通常否** | 可共享只读查询母版，关键是明确无写权限和数据范围 |

## 3. 当前 158 个 HTML 的归类结论

### 应继续保留独立高保真 HTML

以下现有页面具有明显不同的任务、布局或风险，保留独立 HTML 是合理的：

- 工作台与教务看板：`workbench/my-workbench/index.html`、`academic-affairs/dashboard/index.html`
- 学籍主体详情：`roster/roster-detail.html`
- 成绩录入、审核、发布、更正、审计：`grades/grade-entry.html`、`grade-college-review.html`、`grade-publish.html`、`grade-change.html`、`grade-audit.html`
- 学籍异动表单、审批、生效、打印：`status-changes/status-change-form*.html`、`status-change-approval.html`、`status-change-effective.html`、`status-change-print.html`
- 培养方案编辑与校验：`programs/program-editor-*.html`、`program-course-modules.html`、`program-credit-requirements.html`、`program-review.html`、`program-publish.html`
- 教学任务工作台与高风险批量：`teaching-tasks/task-workbench.html`、`task-generate.html`、`teacher-assign.html`、`batch-confirm.html`、`merge-split.html`
- 多视角课表、维护、发布、打印：`schedule/schedule-maintain*.html`、`schedule-views-*.html`、`print-schedule-*.html`
- 调停课申请、冲突、审批、通知：`schedule-change/schedule-change-apply-*.html`、`schedule-change-approval.html`、`schedule-change-notice-*.html`
- 选课开放监控、抽签、冲突、锁定、学生满额/补选：`selection/selection-open-monitor.html`、`selection-rounds.html`、`selection-conflicts.html`、`selection-locked-roster.html`、`my-selection-*.html`
- 归档、审计和打印页面。

### 可逐步收敛为共享 HTML 母版

以下页面若最终确认仅字段、筛选项和操作列不同，不应长期保留完整重复结构：

- 单纯的分类、性质、负责人、考核方式等“筛选＋表格＋抽屉”配置页。
- 学期、课程、注册、组织等无特殊交互的标准列表状态变体。
- 只读归档列表、历史列表和普通统计明细。
- 同一真实路由下仅 query 参数改变默认筛选、且没有独立状态机或权限差异的页面。

收敛方法不是立即删除文件，而是：

1. 先在 manifest 为每条路由补齐 `archetype`、`templateHtml` 和差异字段；
2. 将共享壳、筛选、表格、状态和弹层迁入统一脚本；
3. 完成路径引用与截图回归后，再删除真正重复的 HTML；
4. 保留所有真实路由追踪，不以删除追踪记录换取文件数下降。

## 4. 独立 HTML 判断规则

满足任一条件，应保留独立 HTML：

- 主体详情、复杂编辑、审批或状态流转；
- 发布、锁定、归档、终审、批量变更等危险或不可逆操作；
- 排课、排考、座位、课表、日历等特殊画布；
- 导入预检、错误处理、部分成功；
- 打印版式；
- 权限边界、状态机或角色任务与普通页面有实质差异；
- 三档分辨率下具有独立布局风险。

仅有以下差异时，优先复用母版：

- 标题与说明；
- 表格列和筛选字段；
- 默认 query；
- 普通按钮文案；
- 相同状态机内的只读过滤视图；
- 相同公共组件组合，没有特殊交互。

## 5. Manifest 后续字段建议

每条真实路由或业务切面建议至少登记：

```json
{
  "route": "/admin/academic-affairs/example",
  "archetype": "standard-filter-table",
  "templateHtml": "shared/archetypes/standard-filter-table.html",
  "independentHtml": false,
  "fieldDiff": [],
  "actionDiff": [],
  "permissionDiff": [],
  "stateDiff": [],
  "apiDiff": [],
  "routeParamDiff": []
}
```

本 PR 当前不强制一次性重写全部 164 条记录，但后续新增工作区必须按该口径登记，避免继续用“新增 HTML 数量”代替设计覆盖质量。
