# 高校 SaaS 公共组件商业化底座总控表

> **文档性质**：长期可维护的规划总控表（只规划，不写代码）  
> **创建日期**：2026-07-08  
> **适用对象**：产品 / 开发 / 交付 / 新手维护者  
> **强制原则**：优先复用已有组件，禁止重复造轮子；禁止重写已冻结底座，只允许增强规范与视觉统一。

---

## 0. 本表怎么用（新手必读）

把公共组件看成工厂流水线的 6 层「标准零件仓」。业务模块（学工 / 教务 / 毕设 / 实习）只允许从仓里取零件，不允许再各写一套。

| 列名 | 含义 |
|------|------|
| 组件名称 | 统一目标名（对外称呼） |
| 当前是否已有 | 仓库里是否已有可复用实现（可名称不同） |
| 当前成熟度 | `无` / `雏形` / `可用` / `成熟` / `冻结仅增强` |
| 是否需要新建 | 没有实现时标记「是」 |
| 是否只需增强 | 已有实现，只统一视觉/API/文档，不重写 |
| 是否禁止重写 | 硬规则：禁止拆掉重做 |
| 服务模块 | 主要服务哪些业务中心 |
| 影响试点 | 是否影响当前学校试点体验 |
| 影响正式上线 | 正式商业上线前是否必须达标 |
| 推荐开发阶段 | 第 0～6 阶段（见 §8） |
| 当前状态 | `planned` / `doing` / `implemented` / `partial` / `blocked` |
| 验收标准 | 做到什么才算完成 |
| commit 记录位 | 完成后回填 commit hash / 施工记录链接 |

**状态口径**：

- `implemented`：已有统一出口、可被多模块复用、有基本验收；
- `partial`：有实现但不统一 / 能力不全 / 名称不统一；
- `planned`：明确要做，尚未开工；
- `doing`：本阶段施工中；
- `blocked`：被依赖或工作区风险挡住。

**成熟度口径**：

- `无`：完全没有公共实现；
- `雏形`：局部/模块内有零散实现；
- `可用`：可复用，但规范或视觉未统一；
- `成熟`：可规模推广；
- `冻结仅增强`：已是底座，禁止重写，只增强。

---

## 1. 总原则与硬约束

1. **效果第一、交付第一**：优先做影响学校验收的权限、审计、脱敏、导出、附件展示。  
2. **不重写已有底座**：下列组件 **禁止重写，只增强规范与视觉统一**：
   - `DataTable`（目标名 AppDataTable）
   - `AdvancedFilter`（目标名 AppAdvancedFilter）
   - `AppDrawer`（目标名 AppDrawerLayout）
   - `AppConfirmDialog`
   - 公共日期组件族（`AppDatePicker` / `AppDateTimePicker` / `AppDateRangePicker` / `AppDeadlinePicker` / `AppDateDisplay` + `dateUtils`）
3. **已有组件禁止重复造轮子**：先 aliases / 文档统一 / 视觉对齐，再谈新建。  
4. **Excel 正式能力必须接公共底座**：`components/common/excel/` + `app/services/excel/`，不得再模块内私写 Excel 管道。  
5. **开发顺序 ≠ 层号顺序**：先做第 5 层交付能力，后做第 1 层视觉骨架与第 6 层体验增强。  
6. **本阶段暂停新业务功能扩散**：先打公共底座，再建下一业务模块。  
7. **对应 commit 记录位**：组件落地后在本表回填，并写进 `docs/施工记录/`。

### 已有关键实现路径（防重复）

| 目标名 | 现有路径 | 处理方式 |
|--------|----------|----------|
| AppDataTable | `frontend/src/components/business/DataTable.vue` | **禁止重写**，增强规范 |
| AppAdvancedFilter | `frontend/src/components/business/AdvancedFilter.vue` | **禁止重写**，增强规范 |
| AppDrawerLayout | `frontend/src/components/ui/AppDrawer.vue` | **禁止重写**，增强/别名 |
| AppConfirmDialog | `frontend/src/components/common/AppConfirmDialog.vue` | **禁止重写** |
| 公共日期组件 | `frontend/src/components/common/date/*` + `utils/dateUtils.js` | **禁止重写** |
| AppExcelImportWizard | `frontend/src/components/common/excel/AppExcelImportDrawer.vue` 等 | 增强包装，不重做管道 |
| AppExcelExportButton | `frontend/src/components/common/excel/AppExportButton.vue` | 增强 |
| AppExportConfirm | `frontend/src/components/common/AppExportConfirm.vue` | 增强 |
| AppSensitiveText | `frontend/src/components/common/AppSensitiveText.vue` | 增强权限/审计联动 |
| AppPageShell | `frontend/src/components/business/ModulePageShell.vue` | 统一命名 + 视觉 |
| AppModuleHero | `frontend/src/components/business/ModuleHero.vue` | 统一命名 + 视觉 |
| AppToolbar | `frontend/src/components/business/ModuleToolbar.vue` | 统一命名 + 视觉 |
| AppWatermark | `frontend/src/security/components/SecurityWatermark.vue` | 增强为公共出口 |
| AppAuditTrail | 各模块 `AuditTrailPanel.vue`（实习/就业/迎新） | **抽公共**，禁再复制 |

---

## 2. 六层总览统计

> **2026-07-08 盘点更新**：详见附录 C 与 `01-前端组件资产盘点报告.md`。

| 层 | 名称 | 组件数 | implemented | partial | page-only | duplicate | missing | blocked |
|----|------|--------|-------------|---------|-----------|-----------|---------|---------|
| 第 1 层 | 视觉与页面骨架 | 10 | 4 | 2 | 0 | 1 | 3 | 0 |
| 第 2 层 | 数据展示 | 15 | 7 | 4 | 1 | 2 | 1 | 0 |
| 第 3 层 | 数据录入 | 14 | 1 | 0 | 8 | 0 | 5 | 0 |
| 第 4 层 | 高校业务选择器 | 15 | 0 | 0 | 9 | 0 | 6 | 0 |
| 第 5 层 | 交付级业务组件 | 16 | 3 | 6 | 1 | 2 | 2 | 2 |
| 第 6 层 | 体验增强 | 12 | 1 | 2 | 0 | 0 | 8 | 1 |
| **合计** | — | **82** | **20** | **24** | **12** | **8** | **15** | **3** |

| 层 | 名称 | 已有（含部分） | 需新建为主 | 正式上线前必须 |
|----|------|----------------|------------|----------------|
| 第 1 层 | 视觉与页面骨架 | 7 | 3 | 部分（壳/头/工具栏） |
| 第 2 层 | 数据展示 | 13 | 2 | 表/筛选/状态/空错载 |
| 第 3 层 | 数据录入 | 9（含 page-only 表单） | 5 | 表单与提交条统一 |
| 第 4 层 | 高校业务选择器 | 9（page-only 下拉） | 6 | 学工/教务/实习核心选型器 |
| 第 5 层 | 交付级业务组件 | 12 | 4 | **几乎全部** |
| 第 6 层 | 体验增强 | 3 | 9 | 水印必须；其余后置 |

分类快查：

| 分类 | 含义 | 处理策略 |
|------|------|----------|
| A 已有且冻结 | 禁止重写 | 只写规范、别名、视觉增强、使用文档 |
| B 已有需变漂亮/统一 | 有实现但不统一 | 增强 + 命名对齐，不推翻 |
| C 缺失但商业化必须 | 无实现且影响验收 | 优先排期新建 |
| D 正式上线前必须 | 不上线会卡验收/合规 | 进入第 1～3 阶段 |
| E 体验增强可后置 | 不影响闭环 | 第 6 阶段 |

---

## 3. 第 1 层：视觉与页面骨架组件（10）

> 目标：所有业务页看起来同属一个产品，而不是各写各的壳。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppPageShell | 是（ModulePageShell） | 可用 | 否 | 是 | 否（可别名） | 全模块 | 中 | 是 | 第 5 阶段 | partial | 统一页边距/背景/内容区；旧名兼容导出 | _待填_ |
| AppPageHeader | 是 | 可用 | 否 | 是 | 否 | 全模块 | 中 | 是 | 第 5 阶段 | partial | 标题/副标题/操作区插槽统一 | _待填_ |
| AppModuleHero | 是（ModuleHero） | 可用 | 否 | 是 | 否 | 看板类 | 低 | 否 | 第 5 阶段 | partial | 模块英雄区视觉统一 | _待填_ |
| AppSectionCard | 部分（AppCard） | 雏形 | 否 | 是 | 否 | 全模块 | 低 | 否 | 第 5 阶段 | partial | 卡片间距/标题区一致 | _待填_ |
| AppSectionHeader | 是（ui + dashboard 双份） | 可用 | 否 | 是 | 否 | 全模块 | 低 | 否 | 第 5 阶段 | partial | 合并双份出口，只保留一个规范 | _待填_ |
| AppToolbar | 是（ModuleToolbar） | 可用 | 否 | 是 | 否 | 列表页 | 中 | 是 | 第 5 阶段 | partial | 查询+操作条布局统一 | _待填_ |
| AppActionBar | 否 | 无 | 是 | 否 | 否 | 列表/详情 | 低 | 否 | 第 5 阶段 | planned | 主次按钮分区、危险操作右侧 | _待填_ |
| AppStickyFooter | 否 | 无 | 是 | 否 | 否 | 表单/审批 | 低 | 否 | 第 5 阶段 | planned | 吸底不遮内容、移动端安全区 | _待填_ |
| AppDrawerLayout | 是（AppDrawer） | 冻结仅增强 | 否 | 是 | **是** | 全模块 | 高 | 是 | 第 5 阶段 | implemented | 宽档/标题/footer 槽位文档化；禁止重写 | _待填_ |
| AppResponsiveGrid | 否 | 无 | 是 | 否 | 否 | 看板/表单 | 低 | 否 | 第 5 阶段 | planned | 12 栅格断点统一 | _待填_ |

**本层结论**：

- 已有优先：PageShell / PageHeader / ModuleHero / Toolbar / Drawer / SectionHeader。  
- 禁止重写：`AppDrawer`。  
- 正式上线前：至少统一 PageShell + PageHeader + Toolbar + Drawer。  
- 体验级（StickyFooter / ResponsiveGrid / ActionBar）可稍后。

---

## 4. 第 2 层：数据展示组件（15）

> 目标：列表、状态、空错载、指标在各中心一致。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppDataTable | 是（DataTable） | 冻结仅增强 | 否 | 是 | **是** | 全模块 | 高 | 是 | 第 2 阶段 | implemented | 列配置/选择/空态规范文档化；禁止重写 | _待填_ |
| AppColumnConfig | 否（列在 DataTable 内） | 雏形 | 是（配置层） | 是 | 否 | 全模块 | 中 | 是 | 第 2 阶段 | planned | 列显隐/排序持久化；不拆 DataTable 内核 | _待填_ |
| AppPagination | 部分（页内自写） | 雏形 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 2 阶段 | planned | 统一页码/每页条数/总数展示 | _待填_ |
| AppAdvancedFilter | 是（AdvancedFilter） | 冻结仅增强 | 否 | 是 | **是** | 全模块 | 高 | 是 | 第 2 阶段 | implemented | 字段类型含 date/daterange；禁止重写 | _待填_ |
| AppSearchBox | 部分 | 雏形 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 2 阶段 | planned | 防抖、清空、快捷键预留 | _待填_ |
| AppStatusTag | 是 | 成熟 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 2 阶段 | implemented | 统一状态色板与文案字典 | _待填_ |
| AppRiskTag | 是 | 成熟 | 否 | 是 | 否 | 学工/实习/毕设 | 高 | 是 | 第 2 阶段 | implemented | 风险等级色板统一 | _待填_ |
| AppProgressBar | 部分（DataQualityBar） | 雏形 | 是 | 否 | 否 | 看板 | 低 | 否 | 第 2 阶段 | planned | 百分比/阶段性进度统一 | _待填_ |
| AppMetricCard | 是 | 可用 | 否 | 是 | 否 | 看板 | 中 | 否 | 第 2 阶段 | partial | 视觉与数字格式统一 | _待填_ |
| AppChartCard | 否 | 无 | 是 | 否 | 否 | 驾驶舱/统计 | 低 | 否 | 第 2 阶段 | planned | 卡片壳 + 图表槽；图表引擎可后置 | _待填_ |
| AppTimeline | 是 | 可用 | 否 | 是 | 否 | 审批/过程 | 中 | 是 | 第 2 阶段 | partial | 节点状态色/时间格式统一 | _待填_ |
| AppDescriptionList | 否 | 无 | 是 | 否 | 否 | 详情页 | 中 | 是 | 第 2 阶段 | planned | 标签宽对齐、空值「未设置」 | _待填_ |
| AppEmptyState | 是（EmptyState） | 可用 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 2 阶段 | partial | 插图/文案/操作按钮槽统一 | _待填_ |
| AppErrorState | 是（ErrorState） | 可用 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 2 阶段 | partial | 可重试、错误码展示 | _待填_ |
| AppLoadingState | 是（LoadingState/GlobalState） | 可用 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 2 阶段 | partial | 表格骨架/整页 loading 统一 | _待填_ |

**本层结论**：

- **禁止重写**：DataTable、AdvancedFilter。  
- 正式上线前必须：分页、搜索框、空/错/载、描述列表、状态/风险标签统一。  
- ChartCard / ProgressBar 可降级为 partial，不阻断业务闭环。

---

## 5. 第 3 层：数据录入组件（14）

> 目标：表单控件与校验一套标准；日期已冻结。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppForm | 否（页面散写） | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 统一 label/校验/布局 | _待填_ |
| AppFormItem | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 必填星标、错误文案位 | _待填_ |
| AppTextInput | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 长度/禁用/只读态 | _待填_ |
| AppNumberInput | 否 | 无 | 是 | 否 | 否 | 全模块 | 低 | 是 | 第 4 阶段 | planned | 步进、精度、范围 | _待填_ |
| AppSelect | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 搜索、清空、异步 options | _待填_ |
| AppMultiSelect | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 最多选 N、已选标签 | _待填_ |
| AppRadioGroup | 否 | 无 | 是 | 否 | 否 | 全模块 | 低 | 否 | 第 4 阶段 | planned | 横向/纵向布局 | _待填_ |
| AppCheckboxGroup | 否 | 无 | 是 | 否 | 否 | 全模块 | 低 | 否 | 第 4 阶段 | planned | 半选、全选 | _待填_ |
| AppTextarea | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 字数统计、最大长度 | _待填_ |
| AppRichTextEditor | 否 | 无 | 是 | 否 | 否 | 通知/材料 | 低 | 否 | 第 4 阶段 | planned | 基础富文本；可先用受限方案 | _待填_ |
| AppFormSection | 否 | 无 | 是 | 否 | 否 | 复杂表单 | 低 | 否 | 第 4 阶段 | planned | 分区折叠标题 | _待填_ |
| AppFormValidator | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 4 阶段 | planned | 规则声明式、与后端错误码映射 | _待填_ |
| AppSubmitBar | 否 | 无 | 是 | 否 | 否 | 表单页 | 中 | 是 | 第 4 阶段 | planned | 提交/取消/二次确认钩子 | _待填_ |
| 公共日期组件（族） | 是 | 冻结仅增强 | 否 | 是 | **是** | 全模块 | 高 | 是 | 已完成底座 | implemented | 筛选默认不限；截止默认 23:59；空值「未设置」 | 公共日期底座已提交（回填具体 hash） |

**公共日期组件族明细（禁止重写）**：

- `AppDatePicker`
- `AppDateTimePicker`
- `AppDateRangePicker`
- `AppDeadlinePicker`
- `AppDateDisplay`
- `frontend/src/utils/dateUtils.js`

**本层结论**：

- 日期底座已完成，**禁止重写**。  
- 录入层整体偏空，按第 4 阶段建设；优先 Form / FormItem / Select / Textarea / SubmitBar。  
- RichText 正式上线前可用受限方案标 `partial`。

---

## 6. 第 4 层：高校业务选择器组件（15）

> 目标：学生 / 老师 / 院系专业班级 / 批次 / 企业岗位等选型器可跨模块复用，带数据范围与权限。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppStudentPicker | 否（页内自写） | 雏形 | 是 | 否 | 否 | 学工/教务/毕设/实习 | 高 | 是 | 第 3 阶段 | planned | 关键字搜、数据范围过滤、多选 | _待填_ |
| AppTeacherPicker | 否 | 雏形 | 是 | 否 | 否 | 教务/毕设/实习 | 高 | 是 | 第 3 阶段 | planned | 角色过滤、在职过滤 | _待填_ |
| AppClassPicker | 否 | 雏形 | 是 | 否 | 否 | 学工/教务 | 高 | 是 | 第 3 阶段 | planned | 学院→专业→班级联动可选 | _待填_ |
| AppMajorPicker | 否 | 雏形 | 是 | 否 | 否 | 教务/毕设 | 中 | 是 | 第 3 阶段 | planned | 按学院过滤 | _待填_ |
| AppCollegePicker | 否 | 雏形 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 3 阶段 | planned | 租户下学院列表 | _待填_ |
| AppOrgCascader | 否 | 无 | 是 | 否 | 否 | 系统/学工 | 中 | 是 | 第 3 阶段 | planned | 组织树懒加载 | _待填_ |
| AppAcademicYearPicker | 否 | 无 | 是 | 否 | 否 | 教务 | 中 | 是 | 第 3 阶段 | planned | 当前学年默认 | _待填_ |
| AppTermPicker | 否 | 无 | 是 | 否 | 否 | 教务 | 中 | 是 | 第 3 阶段 | planned | 学年学期联动 | _待填_ |
| AppBatchPicker | 否（页内自写） | 雏形 | 是 | 否 | 否 | 迎新/毕设/实习 | 高 | 是 | 第 3 阶段 | planned | 状态过滤（进行中优先） | _待填_ |
| AppRolePicker | 否 | 雏形 | 是 | 否 | 否 | 系统管理 | 中 | 是 | 第 3 阶段 | planned | 角色模板+自定义角色 | _待填_ |
| AppTenantPicker | 否 | 雏形 | 是 | 否 | 否 | 平台运营 | 低 | 是（平台） | 第 3 阶段 | planned | 仅平台侧可见 | _待填_ |
| AppCompanyPicker | 否 | 雏形 | 是 | 否 | 否 | 实习/就业 | 高 | 是 | 第 3 阶段 | planned | 企业库检索+状态 | _待填_ |
| AppPositionPicker | 否 | 雏形 | 是 | 否 | 否 | 实习 | 高 | 是 | 第 3 阶段 | planned | 企业下岗位过滤 | _待填_ |
| AppMentorPicker | 否 | 雏形 | 是 | 否 | 否 | 毕设/实习 | 高 | 是 | 第 3 阶段 | planned | 指导教师/企业导师区分 | _待填_ |
| AppCoursePicker | 否 | 无 | 是 | 否 | 否 | 教务 | 中 | 是 | 第 3 阶段 | planned | 课程库检索 | _待填_ |

**本层结论**：

- 目前几乎都是「页面内临时下拉」，统一选型器是商业化交付刚需。  
- 试点已受影响的：Student / Teacher / Batch / Company / Position / Mentor。  
- **全部属于「缺失且商业化必须」**，安排在第 3 阶段，先做高频 6 个。

---

## 7. 第 5 层：交付级业务组件（16）

> 目标：学校能验收的「真交付能力」——权限、审计、脱敏、导入导出、附件、确认、待办。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppExcelImportWizard | 是（ExcelImportDrawer 族） | 可用 | 否 | 是 | 否（禁重做管道） | 全模块 | 高 | 是 | 第 1 阶段 | partial | 向导步骤文案统一；复用底座管道 | Excel 底座 V1.1 |
| AppExcelExportButton | 是 | 可用 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | implemented | 权限+审计+文件名规范 | Excel 底座 V1.1 |
| AppExportConfirm | 是 | 可用 | 否 | 是 | **建议禁重写** | 全模块 | 高 | 是 | 第 1 阶段 | implemented | 导出原因/敏感提示 | _待填_ |
| AppImportResultPanel | 部分（ErrorSummary/Preview） | 可用 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | partial | 成功/失败汇总面板统一 | _待填_ |
| AppFileUpload | 否 | 雏形 | 是 | 否 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | planned | 类型/大小限制、进度、失败重试 | _待填_ |
| AppFilePreview | 是 | 可用 | 否 | 是 | 否 | 全模块 | 中 | 是 | 第 1 阶段 | partial | 图片/PDF/Office 策略清晰 | _待填_ |
| AppFileList | 否 | 无 | 是 | 否 | 否 | 全模块 | 中 | 是 | 第 1 阶段 | planned | 下载/删除权限、空列表 | _待填_ |
| AppAuditTrail | 部分（模块内 Panel） | 雏形 | 是（抽公共） | 是 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | partial | 统一时间线+操作人+动作；删除模块副本 | _待填_ |
| AppSensitiveText | 是 | 成熟 | 否 | 是 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | implemented | 脱敏+揭示审计强制 | _待填_ |
| AppPermissionButton | 否 | 无 | 是 | 否 | 否 | 全模块 | 高 | 是 | 第 1 阶段 | planned | 按钮级 permissionCode；无权限隐藏/禁用可配 | _待填_ |
| AppConfirmDialog | 是 | 冻结仅增强 | 否 | 是 | **是** | 全模块 | 高 | 是 | 第 1 阶段 | implemented | 危险操作样式；禁止重写 | _待填_ |
| AppBatchActionBar | 部分（DataTable batch 槽） | 雏形 | 是 | 否 | 否 | 列表页 | 中 | 是 | 第 1 阶段 | planned | 批量操作确认+权限+审计 | _待填_ |
| AppWorkflowTimeline | 部分（Timeline） | 雏形 | 是 | 否 | 否 | 审批/过程 | 中 | 是 | 第 1 阶段 | planned | 流程节点/驳回原因展示 | _待填_ |
| AppApprovalPanel | 否 | 无 | 是 | 否 | 否 | 工作台/审批 | 高 | 是 | 第 1 阶段 | planned | 通过/驳回/转办标准面板 | _待填_ |
| AppTodoPanel | 部分（TodoCard/TaskWorkbench） | 雏形 | 是 | 否 | 否 | 工作台 | 高 | 是 | 第 1 阶段 | planned | 待办列表统一入口样式 | _待填_ |
| AppNotificationPanel | 否 | 无 | 是 | 否 | 否 | 工作台 | 中 | 是 | 第 1 阶段 | planned | 消息已读/跳转 | _待填_ |

**本层结论（第一优先级）**：

- **第一阶段先做**：`AppPermissionButton`、`AppAuditTrail`（抽公共）、`AppSensitiveText`（增强联动）、`AppFileUpload`、`AppFileList`、`AppFilePreview`（增强）、`AppExcelImportWizard`/`Export`/`ImportResult`（增强统一）、`AppBatchActionBar`、`AppApprovalPanel`/`AppTodoPanel`（至少可用版）。  
- **禁止重写**：`AppConfirmDialog`；Excel 管道不重做；ExportConfirm 只增强。  
- 全部影响正式上线。

---

## 8. 第 6 层：体验增强组件（12）

> 目标：体验更好，但不阻塞业务闭环与正式上线主链路（水印除外）。

| 组件名称 | 当前是否已有 | 成熟度 | 新建 | 仅增强 | 禁止重写 | 服务模块 | 影响试点 | 影响正式上线 | 推荐阶段 | 状态 | 验收标准 | commit 记录位 |
|----------|--------------|--------|------|--------|----------|----------|----------|--------------|----------|------|----------|---------------|
| AppWatermark | 是（SecurityWatermark） | 可用 | 否 | 是 | 否 | 全模块 | 中 | **是** | 第 6 阶段（可提前） | partial | 导出/打印/敏感页强制水印 | _待填_ |
| AppCopyableText | 否 | 无 | 是 | 否 | 否 | 全模块 | 低 | 否 | 第 6 阶段 | planned | 一键复制反馈 | _待填_ |
| AppHelpTooltip | 否 | 无 | 是 | 否 | 否 | 全模块 | 低 | 否 | 第 6 阶段 | planned | 字段帮助气泡 | _待填_ |
| AppFieldHint | 否 | 无 | 是 | 否 | 否 | 表单 | 低 | 否 | 第 6 阶段 | planned | 表单项下方提示 | _待填_ |
| AppQuickFilterChips | 否 | 无 | 是 | 否 | 否 | 列表 | 低 | 否 | 第 6 阶段 | planned | 快捷筛选芯片 | _待填_ |
| AppKeyboardShortcut | 否 | 无 | 是 | 否 | 否 | 管理端 | 低 | 否 | 第 6 阶段 | planned | 常用快捷键说明 | _待填_ |
| AppPrintButton | 否 | 无 | 是 | 否 | 否 | 台账/证明 | 低 | 是（部分场景） | 第 6 阶段 | planned | 打印样式+水印+审计 | _待填_ |
| AppQRCode | 否 | 无 | 是 | 否 | 否 | 迎新/实习 | 低 | 否 | 第 6 阶段 | planned | 二维码生成展示 | _待填_ |
| AppBadge | 是 | 可用 | 否 | 是 | 否 | 全模块 | 低 | 否 | 第 6 阶段 | implemented | 视觉对齐 | _待填_ |
| AppAvatarGroup | 否 | 无 | 是 | 否 | 否 | 协作页 | 低 | 否 | 第 6 阶段 | planned | 重叠头像+溢出数 | _待填_ |
| AppStepGuide | 部分（AppStepBar） | 雏形 | 是 | 否 | 否 | 向导页 | 低 | 否 | 第 6 阶段 | planned | 新手步骤引导 | _待填_ |
| AppOperationResult | 否 | 无 | 是 | 否 | 否 | 提交结果 | 低 | 否 | 第 6 阶段 | planned | 成功/失败结果页模板 | _待填_ |

**本层结论**：

- 除 **水印、打印（部分验收项）** 外，均可后置。  
- 属「体验增强，后面再做」。

---

## 9. 推荐开发顺序（不等于层号）

> 优先做最影响商业交付与学校验收的组件。

### 第 0 阶段：工作区清理与基线确认

目标：

1. 确认公共日期底座、Excel 底座、毕设 PC 试点已入库可引用；
2. 清理或登记无关工作区改动，避免公共组件施工被噪音淹没；
3. 盘点本表「已有路径」，冻结禁止重写清单；
4. 输出基线 commit / 分支约定（由人工确认后执行）。

产出：基线确认纪要 + 本表状态从 planned 调为可开工。

### 第 1 阶段：第 5 层交付级 · 权限 / 审计 / 脱敏 / 导出 / 附件

**建议先做清单（第一阶段核心）**：

1. `AppPermissionButton`（新建）
2. `AppAuditTrail`（从模块副本抽公共）
3. `AppSensitiveText`（增强：权限门闩 + 审计钩子规范）
4. `AppFileUpload` + `AppFileList` + `AppFilePreview`（新建/增强）
5. `AppExcelImportWizard` / `AppImportResultPanel` / `AppExcelExportButton` / `AppExportConfirm`（增强统一，不重做管道）
6. `AppBatchActionBar`（新建，复用 DataTable 选择态）
7. `AppConfirmDialog`（**只增强规范，禁止重写**）
8. `AppApprovalPanel` / `AppTodoPanel`（可用版；Notification 可并行或紧随）

验收：任意业务页可接「有权限才显示按钮 / 敏感揭示写审计 / 附件可上传预览 / 导出有确认与审计」。

### 第 2 阶段：第 2 层数据展示补强

优先：

1. `AppPagination`、`AppSearchBox`、`AppDescriptionList`
2. `AppEmptyState` / `AppErrorState` / `AppLoadingState` 视觉与 API 统一
3. `AppColumnConfig`（不拆 DataTable，做配置层）
4. `AppStatusTag` / `AppRiskTag` / `AppMetricCard` / `AppTimeline` 增强
5. `AppDataTable` / `AppAdvancedFilter`：**只增强，禁止重写**

### 第 3 阶段：第 4 层高校业务选择器

优先 6 个（试点高频）：

1. AppStudentPicker  
2. AppTeacherPicker  
3. AppBatchPicker  
4. AppCompanyPicker  
5. AppPositionPicker  
6. AppMentorPicker  

随后：College / Major / Class / OrgCascader / AcademicYear / Term / Course / Role / Tenant。

### 第 4 阶段：第 3 层数据录入

优先：AppForm / AppFormItem / AppTextInput / AppSelect / AppMultiSelect / AppTextarea / AppFormValidator / AppSubmitBar。  
日期组件：**禁止重写，只推广接入**。  
RichText / Radio / Checkbox 可后。

### 第 5 阶段：第 1 层视觉与页面骨架统一

统一：PageShell / PageHeader / Toolbar / ModuleHero / SectionHeader / Drawer 文档。  
新建：ActionBar / StickyFooter / ResponsiveGrid。  
Drawer：**禁止重写**。

### 第 6 阶段：第 6 层体验增强

水印与打印优先提档到「上线前必检」。  
其余 Copyable / Tooltip / Chips / Shortcut / QR / Avatar / Guide / Result 按体验包推进。

---

## 10. 分类总表（给新手一眼看懂）

### 10.1 禁止重写（只增强）

| 组件 | 现名/路径 | 说明 |
|------|-----------|------|
| AppDataTable | `business/DataTable.vue` | 列表内核冻结 |
| AppAdvancedFilter | `business/AdvancedFilter.vue` | 筛选内核冻结 |
| AppDrawerLayout | `ui/AppDrawer.vue` | 抽屉内核冻结 |
| AppConfirmDialog | `common/AppConfirmDialog.vue` | 确认框冻结 |
| 公共日期组件族 | `common/date/*` + `dateUtils` | 日期底座冻结 |
| Excel 管道 | `services/excel/*` + `common/excel/*` | 禁止各模块重写管道 |

### 10.2 已有但需要变漂亮 / 变统一（B 类）

AppPageShell、AppPageHeader、AppModuleHero、AppToolbar、AppSectionHeader、AppSectionCard、AppStatusTag、AppRiskTag、AppMetricCard、AppTimeline、AppEmpty/Error/Loading、AppExcelImportWizard、AppImportResultPanel、AppFilePreview、AppExportConfirm、AppSensitiveText、AppWatermark、AppBadge、AppTodoPanel（从现有卡片提升）、AppAuditTrail（从模块副本抽公共）。

### 10.3 缺失且商业化必须（C 类）

AppPermissionButton、AppFileUpload、AppFileList、AppBatchActionBar、AppApprovalPanel、AppNotificationPanel、AppPagination、AppSearchBox、AppDescriptionList、AppColumnConfig、几乎全部第 4 层选择器、AppForm 全家桶（除日期）。

### 10.4 正式上线前必须（D 类）

- 第 5 层绝大部分；
- DataTable / AdvancedFilter / 空错载 / 分页 / 搜索；
- Student/Teacher/Batch/Company/Position/Mentor Picker；
- Form 基础能力；
- PageShell + PageHeader + Toolbar + Drawer；
- Watermark（敏感/导出场景）。

### 10.5 体验增强后置（E 类）

第 6 层除水印/打印外的多数组件；ActionBar/StickyFooter/ResponsiveGrid/ChartCard/RichText 等可标 partial 后置。

---

## 11. 与业务模块关系（简图）

```text
工作台 ─────────── 待办 / 审批 / 通知 / 水印
学工中心 ───────── 学生选择器 / 批次 / 敏感字段 / Excel / 附件
教务中心 ───────── 学年学期 / 课程 / 班级专业 / 表单 / 表格筛选
毕业设计中心 ───── 导师选择器 / 批次 / 过程时间线 / Excel / 日期
岗位实习中心 ───── 企业岗位选择器 / 打卡日期 / Excel / 附件 / 审计
系统管理 ───────── 角色 / 租户选择器 / 权限按钮 / 审计轨
```

六层是横贯所有中心的底座；业务模块只「接线」不「造引擎」。

---

## 12. 施工与回填规则

每完成一个组件，必须：

1. 在本表把状态改为 `doing` → `implemented` / `partial`；  
2. 回填「commit 记录位」；  
3. 在 `docs/施工记录/` 追加施工记录；  
4. 若能力不足但可交付，写进 `docs/施工记录/历史欠账.md`；  
5. **禁止**未验收就把 `planned` 标成 `implemented`。

---

## 13. 本轮文档交付说明

| 项 | 内容 |
|----|------|
| 最新动作（2026-07-08） | 只读盘点 + 更新附录 C + 新增 `01-前端组件资产盘点报告.md` |
| 规划文档 | `docs/公共组件/00-高校SaaS公共组件商业化底座总控表.md` |
| 盘点报告 | `docs/公共组件/01-前端组件资产盘点报告.md` |
| 六层组件总数 | **82** |
| 背景假设 | 公共日期底座 `431c389`；毕设 PC 试点 `graduation-pc-trial-v1`；公共组件冲刺在干净 worktree `components-foundation-sprint` |
| 未改 | 业务代码、后端、数据库、路由；未提交 git |

---

## 附录 A：快速答案卡（给用户直接看）

1. **六层组件总数**：82  
2. **已有可直接复用（implemented）**：20 个  
3. **只需增强（partial）**：24 个  
4. **页面散落待抽（page-only）**：12 个  
5. **多份重复待合并（duplicate）**：8 个  
6. **完全缺失（missing）**：15 个  
7. **平台阻塞（blocked）**：3 个（FileUpload、PrintButton 等）  
8. **第一阶段先做**：PermissionButton、AuditTrail 抽公共、SensitiveText 推广、Excel 导出入口统一、ConfirmDialog 扫尾  
9. **禁止重写**：DataTable、AdvancedFilter、AppDrawer、AppConfirmDialog、公共日期组件族（及 Excel 管道）  
10. **开发顺序提醒**：第 0 清理 → 第 1 交付级 → 第 2 展示 → 第 3 选择器 → 第 4 录入 → 第 5 骨架 → 第 6 体验  
11. **详细盘点**：见 `01-前端组件资产盘点报告.md` 与附录 C  

---

## 附录 B：命名对齐建议（实施时用，本轮不改代码）

| 目标公共名 | 现有实现名 | 建议 |
|------------|------------|------|
| AppPageShell | ModulePageShell | 保留旧导出 + 新名别名 |
| AppModuleHero | ModuleHero | 同上 |
| AppToolbar | ModuleToolbar | 同上 |
| AppDataTable | DataTable | 同上，内核不动 |
| AppAdvancedFilter | AdvancedFilter | 同上，内核不动 |
| AppDrawerLayout | AppDrawer | 文档用 Layout 名，代码可保留 AppDrawer |
| AppExcelImportWizard | AppExcelImportDrawer | Drawer 作为 Wizard 实现载体，或包一层步骤壳 |
| AppEmptyState 等 | EmptyState 等 | business 导出别名到 App* |
| AppWatermark | SecurityWatermark | 公共出口 re-export |

**原则**：别名与文档优先，文件搬迁最后做，避免大爆炸重构。

---

## 附录 C：2026-07-08 前端组件资产盘点结果（82 项全表）

> 盘点方式：只读扫描 `frontend/src/components/`、`modules/*/components/`、`security/components/`、`utils/`。  
> 详细说明见：`docs/公共组件/01-前端组件资产盘点报告.md`  
> **成熟度口径**：`implemented` / `partial` / `page-only` / `duplicate` / `missing` / `blocked`  
> **视觉口径**：`商业级` / `可用但普通` / `粗糙` / `不统一` / `缺失`  
> **处理建议**：`禁止重写，只增强` / `增强现有组件` / `抽成公共组件` / `新建公共组件` / `暂缓` / `正式上线前必须做`

### C.1 第 1 层：视觉与页面骨架（10）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppPageShell | 是 | `business/ModulePageShell.vue` | implemented | 可用但普通 | 否 | 是 | 否 | 第5阶段 | partial | 禁止重写，只增强 |
| AppPageHeader | 是 | `common/AppPageHeader.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第5阶段 | partial | 增强现有组件 |
| AppModuleHero | 是 | `business/ModuleHero.vue` | implemented | 可用但普通 | 否 | 是 | 否 | 第5阶段 | partial | 禁止重写，只增强 |
| AppSectionCard | 部分 | `ui/AppCard.vue` | partial | 不统一 | 否 | 是 | 否 | 第5阶段 | partial | 增强现有组件 |
| AppSectionHeader | 是 | `ui/AppSectionHeader.vue` + `dashboard/AppSectionHeader.vue` | duplicate | 不统一 | 否 | 是 | 否 | 第5阶段 | partial | 抽成公共组件 |
| AppToolbar | 是 | `business/ModuleToolbar.vue` | implemented | 可用但普通 | 否 | 是 | 否 | 第5阶段 | partial | 禁止重写，只增强 |
| AppActionBar | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第5阶段 | planned | 新建公共组件 |
| AppStickyFooter | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第5阶段 | planned | 暂缓 |
| AppDrawerLayout | 是 | `ui/AppDrawer.vue` | implemented | 可用但普通 | 否 | 是 | **是** | 第5阶段 | implemented | **禁止重写，只增强** |
| AppResponsiveGrid | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第5阶段 | planned | 暂缓 |

### C.2 第 2 层：数据展示（15）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppDataTable | 是 | `business/DataTable.vue` | implemented | 可用但普通 | 否 | 是 | **是** | 第2阶段 | implemented | **禁止重写，只增强** |
| AppColumnConfig | 部分 | 各模块 `ColumnSettings*.vue` | duplicate | 不统一 | 是 | 是 | 否 | 第2阶段 | partial | 抽成公共组件 |
| AppPagination | 部分 | `DataTable.vue` 内嵌 pager | partial | 不统一 | 是 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |
| AppAdvancedFilter | 是 | `business/AdvancedFilter.vue` | implemented | 可用但普通 | 否 | 是 | **是** | 第2阶段 | implemented | **禁止重写，只增强** |
| AppSearchBox | 部分 | `StudentSearchBar.vue` + 筛选 keyword | duplicate | 不统一 | 是 | 否 | 否 | 第2阶段 | partial | 抽成公共组件 |
| AppStatusTag | 是 | `common/AppStatusTag.vue` | implemented | 商业级 | 否 | 是 | 否 | 第2阶段 | implemented | 增强现有组件 |
| AppRiskTag | 是 | `common/AppRiskTag.vue` | implemented | 商业级 | 否 | 是 | 否 | 第2阶段 | implemented | 增强现有组件 |
| AppProgressBar | 部分 | `dashboard/DataQualityBar.vue` | partial | 粗糙 | 是 | 否 | 否 | 第2阶段 | planned | 暂缓 |
| AppMetricCard | 是 | `common/AppMetricCard.vue` + `dashboard/MetricCard.vue` | duplicate | 不统一 | 否 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |
| AppChartCard | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第2阶段 | planned | 暂缓 |
| AppTimeline | 是 | `common/AppTimeline.vue` + `dashboard/LifecycleTimeline.vue` | partial | 不统一 | 否 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |
| AppDescriptionList | 页内 | 各详情页 `mp-kv` 样式 | page-only | 粗糙 | 是 | 否 | 否 | 第2阶段 | planned | 新建公共组件 |
| AppEmptyState | 是 | `business/EmptyState.vue` → `AppGlobalState` | implemented | 可用但普通 | 否 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |
| AppErrorState | 是 | `business/ErrorState.vue` → `AppGlobalState` | implemented | 可用但普通 | 否 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |
| AppLoadingState | 是 | `business/LoadingState.vue` → `AppGlobalState` | implemented | 可用但普通 | 否 | 是 | 否 | 第2阶段 | partial | 增强现有组件 |

### C.3 第 3 层：数据录入（14）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppForm | 页内 | 各页 `ie-fld` 散写 | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppFormItem | 页内 | 各页 label 散写 | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppTextInput | 页内 | `ie-in` class | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppNumberInput | 页内 | 原生 number input | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 暂缓 |
| AppSelect | 页内 | 原生 `<select>` | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppMultiSelect | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppRadioGroup | 页内 | 原生 radio | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 暂缓 |
| AppCheckboxGroup | 页内 | 原生 checkbox | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 暂缓 |
| AppTextarea | 页内 | 原生 textarea | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppRichTextEditor | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第4阶段 | planned | 暂缓 |
| AppFormSection | 页内 | `mp-card` 分区 | page-only | 粗糙 | 是 | 否 | 否 | 第4阶段 | planned | 暂缓 |
| AppFormValidator | 否 | 局部校验散落 | missing | 缺失 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| AppSubmitBar | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第4阶段 | planned | 新建公共组件 |
| 公共日期组件族 | 是 | `common/date/*` + `dateUtils.js` | implemented | 商业级 | 否 | 是 | **是** | 已完成 | implemented | **禁止重写，只增强** |

### C.4 第 4 层：高校业务选择器（15）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppStudentPicker | 页内 | 列表关键字/建档 select | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppTeacherPicker | 页内 | 导师分配输入/下拉 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppClassPicker | 页内 | AdvancedFilter class 字段 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppMajorPicker | 页内 | AdvancedFilter major 字段 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppCollegePicker | 页内 | AdvancedFilter college 字段 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppOrgCascader | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppAcademicYearPicker | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppTermPicker | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppBatchPicker | 页内 | 毕设/迎新/实习批次 `<select>` | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppRolePicker | 页内 | 系统角色页局部 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppTenantPicker | 页内 | 平台租户页局部 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 暂缓 |
| AppCompanyPicker | 页内 | 实习企业搜索/下拉 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppPositionPicker | 页内 | 实习岗位搜索/下拉 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppMentorPicker | 页内 | 毕设导师分配 | page-only | 粗糙 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |
| AppCoursePicker | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第3阶段 | planned | 新建公共组件 |

### C.5 第 5 层：交付级业务组件（16）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppExcelImportWizard | 是 | `common/excel/AppExcelImportDrawer.vue` 等 | partial | 可用但普通 | 否 | 是 | 否（禁重做管道） | 第1阶段 | partial | 增强现有组件 |
| AppExcelExportButton | 是 | `common/excel/AppExportButton.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppExportConfirm | 是 | `common/AppExportConfirm.vue` | implemented | 商业级 | 否 | 是 | 建议禁重写 | 第1阶段 | implemented | 禁止重写，只增强 |
| AppImportResultPanel | 部分 | `excel/AppImportErrorSummary.vue` 等 | partial | 可用但普通 | 否 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppFileUpload | 否 | 平台 `/api/v1/files` 占位 | blocked | 缺失 | 是 | 否 | 否 | 第1阶段 | blocked | 正式上线前必须做 |
| AppFilePreview | 是 | `common/AppFilePreview.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppFileList | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第1阶段 | planned | 正式上线前必须做 |
| AppAuditTrail | 副本×3 | `modules/*/AuditTrailPanel.vue` | duplicate | 不统一 | 是 | 是 | 否 | 第1阶段 | partial | 抽成公共组件 |
| AppSensitiveText | 是 | `common/AppSensitiveText.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppPermissionButton | 页内 | `permissionActions` map 散落 | page-only | 不统一 | 是 | 否 | 否 | 第1阶段 | planned | 新建公共组件 |
| AppConfirmDialog | 是 | `common/AppConfirmDialog.vue` | implemented | 商业级 | 否 | 是 | **是** | 第1阶段 | implemented | **禁止重写，只增强** |
| AppBatchActionBar | 副本×2 | `orientation/employment/BatchActionBar.vue` | duplicate | 不统一 | 是 | 否 | 否 | 第1阶段 | partial | 抽成公共组件 |
| AppWorkflowTimeline | 部分 | `common/AppTimeline` + workflow 组件 | partial | 不统一 | 否 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppApprovalPanel | 部分 | `workflow/ApprovalTaskDetailPanel.vue` 等 | partial | 可用但普通 | 是 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppTodoPanel | 部分 | `common/AppTodoCard` + `dashboard/TaskWorkbenchPanel` | partial | 不统一 | 是 | 是 | 否 | 第1阶段 | partial | 增强现有组件 |
| AppNotificationPanel | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第1阶段 | planned | 暂缓 |

### C.6 第 6 层：体验增强（12）

| 组件名称 | 已有 | 已有路径 | 成熟度 | 视觉 | 新建 | 仅增强 | 禁止重写 | 阶段 | 状态 | 处理建议 |
|----------|------|----------|--------|------|------|--------|----------|------|------|----------|
| AppWatermark | 是 | `security/SecurityWatermark.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第6阶段 | partial | 正式上线前必须做 |
| AppCopyableText | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppHelpTooltip | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppFieldHint | 页内 | `ie-hint` class | page-only | 粗糙 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppQuickFilterChips | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppKeyboardShortcut | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppPrintButton | 否 | — | blocked | 缺失 | 是 | 否 | 否 | 第6阶段 | blocked | 正式上线前必须做 |
| AppQRCode | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppBadge | 是 | `ui/AppBadge.vue` | implemented | 商业级 | 否 | 是 | 否 | 第6阶段 | implemented | 增强现有组件 |
| AppAvatarGroup | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |
| AppStepGuide | 部分 | `common/AppStepBar.vue` | partial | 可用但普通 | 否 | 是 | 否 | 第6阶段 | partial | 暂缓 |
| AppOperationResult | 否 | — | missing | 缺失 | 是 | 否 | 否 | 第6阶段 | planned | 暂缓 |

### C.7 盘点结论速查

| 统计项 | 数量 |
|--------|------|
| 总组件数 | 82 |
| implemented（可直接复用） | 20 |
| partial（需增强） | 24 |
| page-only（页面散落待抽） | 12 |
| duplicate（多份待合并） | 8 |
| missing（完全缺失） | 15 |
| blocked（平台依赖） | 3 |
| 禁止重写清单 | DataTable、AdvancedFilter、AppDrawer、AppConfirmDialog、公共日期族、Excel 管道 |
| 第一阶段优先 5 项 | PermissionButton、AuditTrail、SensitiveText、Excel 导出入口、ConfirmDialog 扫尾 |

---

## 附录：第一/二阶段交付级公共组件落地状态（2026-07-09）

> 本轮已按「交付级公共组件底座」施工完成 20 个组件；统一出口 `@/components/common`（UI 基元在 `@/components/ui`）。
> 在线预览：`/dev/components`。使用手册：`docs/公共组件/02-第一阶段交付级公共组件使用指南.md`。
> commit：待用户确认后提交（本轮不 commit、不 push）。

### 第一阶段（12 个）

| 组件 | 类型 | 状态 | 备注 |
|------|------|------|------|
| AppPermissionButton | 新建 | implemented | 仅前端体验，越权拦截由后端 |
| AppAuditTrail | 新建 | implemented | 只展示后端真实审计 |
| AppFileList | 新建 | partial | 展示态完成；上传/存储依赖文件中心 |
| AppBatchActionBar | 新建 | implemented | 列表多选浮出操作条 |
| AppApprovalPanel | 新建 | implemented | 驳回/退回强制意见+校验 |
| AppExportButton | 增强·统一出口 | implemented | 不伪造导出成功，走后端 |
| AppExportConfirm | 复用 | implemented | 必填导出用途写审计 |
| AppConfirmDialog | 增强 | implemented | 新增 content/danger/loading 别名 |
| AppStatusTag | 增强 | implemented | 状态映射扩到 40+、新增 size |
| AppRiskTag | 增强 | implemented | 支持别名、新增 size |
| AppSensitiveText | 复用 | implemented | 默认脱敏，@reveal 写审计 |
| AppFilePreview | 复用 | implemented | 只展示与派发事件 |

### 第二阶段（8 个）

| 组件 | 类型 | 状态 | 备注 |
|------|------|------|------|
| AppMetricCard | 增强 | implemented | 新增 loading 骨架 |
| AppWorkflowTimeline | 新建 | implemented | 审批流/流转时间线 |
| AppTodoPanel | 新建 | implemented | 工作台待办 |
| AppNotificationPanel | 新建 | implemented | 消息通知面板 |
| AppCopyableText | 新建 | implemented | 敏感字段仍用 AppSensitiveText |
| AppHelpTooltip | 新建 | implemented | 口径/填写帮助气泡 |
| AppFieldHint | 新建 | implemented | 表单字段提示 |
| AppBadge | 增强 | implemented | 新增计数/红点，兼容原胶囊 |

**验收口径**：统一出口可被多模块 `import`；`/dev/components` 真实渲染并可交互；`npm run build` 通过；无 console 报错。
**未覆盖（随业务模块对接）**：后端真实数据、导出接口、审批引擎联调；文件中心上传/对象存储（AppFileList/AppFilePreview 上传态）。
