# 毕业设计中心：开发还原契约

> 本目录严格按生产 `frontend/src/modules/graduation/config/graduationWorkspaces.js` 的当前 8 个工作区一一对应。真实路由、权限、批次状态、字段、接口和数据范围仍以生产代码为准。

## 当前生产事实源

- 工作区：8
- 三级叶子：50
- 唯一 URL：48
- 显式共享 URL：2
- 独立 HTML：8
- 共享运行资源：`shared/v2-graduation-key.css/js`

两个共享入口：

1. `/admin/graduation/defense-scoring`：既从“我的工作台”进入，也从“答辩与成绩”进入；
2. `/admin/graduation/stats-report`：既从“我的工作台”进入，也从“风险与归档”进入。

它们是同一个生产页面的不同业务入口，不应重复制造页面或第二套数据。

## 8 个现行工作区

| 生产工作区 | HTML | 主入口 | 核心权限 |
|---|---|---|---|
| 我的工作台 `gd-workbench` | `overview.html` | `/admin/graduation` | `graduationDesign.dashboard.view` 及任务专项权限 |
| 批次与实施 `gd-batch-impl` | `batch-implementation.html` | `/admin/graduation/batches?panel=list` | `batch.view/update`、`student.view/manage`、`mentor.manage` |
| 题目与选题 `gd-topic-select` | `topic.html` | `/admin/graduation/topic-lib` | `topic.lib/manage/round/change` |
| 过程指导 `gd-process` | `process.html` | `/admin/graduation/process?panel=taskbook` | `graduationDesign.guidance.view` |
| 开题与成果 `gd-proposal-final` | `proposal-final.html` | `/admin/graduation/proposals` | `proposal.view`、`final.view`、`plagiarism.view`、`review.view`、`more.manage` |
| 答辩与成绩 `gd-defense` | `defense.html` | `/admin/graduation/defense` | `defense.view/score/scoreConfirm`、`grade.view`、`more.manage` |
| 风险与归档 `gd-risk-archive` | `risk-archive.html` | `/admin/graduation/risk-archive?panel=risk` | `riskArchive.manage`、`stats.view` |
| 模板与设置 `gd-templates` | `templates.html` | `/admin/graduation/templates` | `graduationDesign.template.manage` |

## 结构纠偏记录

原型早期错误地按“总览、选题、开题、过程、成果、答辩、成绩、归档统计”拆成 8 页。该拆法是生命周期概念分组，不是当前生产 `GRADUATION_WORKSPACES`。

2026-07-31 已纠正为上表现行 8 工作区：

- 删除旧 `artifact.html`、`proposal.html`、`grade.html`、`archive.html`；
- 新增 `batch-implementation.html`、`proposal-final.html`、`risk-archive.html`、`templates.html`；
- 保留并重定义 `overview.html`、`topic.html`、`process.html`、`defense.html`；
- 重建 `320-graduation.json`，为每个工作区补齐真实主路由、routeName、权限候选、叶子路由、字段、状态与边界；
- 重写共享 JavaScript 的菜单、页签、生产入口和工作区内容。

独立 HTML 总数仍为 8，没有用同一页面冒充多个工作区，也没有增加生产代码改动。

## 核心事实边界

1. 同一毕业设计批次上下文贯穿全部工作区，切换批次后摘要、列表、待办与动作必须一致。
2. 学生和教师身份来自统一身份及学生 / 教师主档，毕设中心不复制身份事实。
3. 工作台只聚合本人任务和授权范围，不建立第二套开题、成果、成绩或归档台账。
4. 批次时间轴、规则、模板和评分规则均需版本化；历史批次不得被新配置追溯改写。
5. 学生资格、导师准入、学生分配和冲突收口是独立事实。
6. 题目申报、审核、发布、学生志愿、匹配、确认、最终结果和题目调整互不替代。
7. 题目容量、导师上限、专业范围、重复分配和并发版本冲突必须阻断最终确认。
8. 任务书、指导计划、指导记录、导师评价和中期检查追加证据与历史。
9. 延期或整改不直接修改原截止时间与原结论。
10. 开题、初稿、定稿、查重证据、教师评阅和互查整改分别保留版本。
11. 查重结果只是证据，不自动生成学术合格或不合格结论。
12. 答辩发布前重新读取后端事实，核验答辩组、学生、评委、回避、时间、场地与容量。
13. 评委评分、秘书确认、成绩台账、优秀成果认定和更正申诉使用不同状态与权限。
14. 风险项保留来源、责任人、时限、证据、升级和关闭记录。
15. 档案包只收录最终有效版本和完整审计；缺材料时输出缺失清单，不制造假完整包。
16. 模板新版本只影响明确绑定的新任务或新批次，历史材料继续引用原模板版本。
17. 下载受权限、数据范围、用途、水印和审计约束。

## 公共组件映射

生产还原优先复用：

- `BasePortalLayout`
- `ModulePageShell`
- 毕设批次选择器与批次上下文
- 学生、导师、题目、答辩组和场地选择器
- `DataTable` 与服务端分页
- `AdvancedFilter`
- 状态、风险、缺失项和冲突组件
- 文件中心、版本历史和材料预览
- 确认弹层、步骤条与只读历史视图
- Excel 导入导出、统计下钻和档案包组件

原型共享 JavaScript 只用于离线展示，不进入生产 Vue 运行时。

## 开发 AI 读取顺序

1. 先读生产 `graduationWorkspaces.js`，确认 8 个工作区和 50 个三级叶子没有变化；
2. 阅读 `manifest-parts/320-graduation.json`；
3. 阅读对应 HTML 的 `workspaceKey`、`route`、`routeName`、`permissions`、`states` 和 `boundary`；
4. 阅读 `shared/v2-graduation-key.css/js`；
5. 回到生产 `routes.js`、真实 Vue 页面、API 和服务；
6. 先核对批次、权限、数据范围、状态机和版本链，再还原视觉与交互；
7. 不复制原型占位值，不把前端候选状态当作后端事实。

## 当前验证口径

- 8 个现行工作区、50 个三级叶子和 48 个唯一 URL 已完成静态映射重建；
- 共享 JavaScript 已在写入前通过 `node --check`；
- 重映射后的 8 页当前浏览器渲染次数仍为 0；
- 未执行三档分辨率、控制台、溢出、状态切换、键盘、焦点和页面跳转回归；
- 完成 8 × 3 = 24 次回归前，不得标记毕业设计中心冻结完成。
