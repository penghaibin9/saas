# PROGRESS

## 当前状态

- 状态：**IN PROGRESS / NOT FROZEN**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 允许目录外修改：**0**
- 当前阶段：**浏览器累计 546 / 870；学工 15 页契约核对完成；岗位实习审计输入未变化；毕业设计现行 8 工作区及机器审计工具已落盘**

## 当前统一规模

- Manifest 条目：**297**
- 独立 HTML：**290**
- 共享 HTML 路由条目：**9**
- shared 文件：**43**
- 首轮工作区：**60**
- 完整冻结一级中心：**0**
- 仓库截图：**0**
- 历史本地渲染截图记录：**309**

工作区分布：

- 教务中心：27
- 学工中心：15
- 岗位实习中心：10 个关键工作台覆盖 12 个生产二级模块
- 毕业设计中心：8

## 当前浏览器回归

```text
546 / 870 PASS
324 / 870 待执行
182 / 290 页已完成
108 / 290 页待执行
```

早期 169 页 / 141 次等旧口径不再计入当前冻结累计。

最近完成并回填正式报告的页面族：

- 毕业资格审核：15 页，**45 / 45 PASS**；
- 教务归档：4 页，**12 / 12 PASS**；
- 教务统计：15 页，**45 / 45 PASS**。

上述页面族在最终候选 HEAD 仍需同源重跑；当前累计不能直接替代最终 870 次全量结果。

## 本阶段实际完成

### 1. Manifest 与统计纠偏

总 Manifest 聚合 `00`–`220`、`300`、`310`、`320`、`330`。README、route-coverage、总 Manifest 和各中心报告继续使用 **297 / 290 / 9 / 43 / 60** 统一口径。

### 2. 教务页面族收口

- 毕业资格审核：15 页 45 / 45 PASS；
- 教务归档：4 页 12 / 12 PASS；
- 教务统计：15 页 45 / 45 PASS；
- 教务统计 15 页真实 routeName 与权限元数据全部核准；
- 原型注释修正没有改变已通过页面族的 DOM、CSS、JavaScript 或运行参数。

### 3. 学工 15 页生产契约核对

学工共 15 个独立 HTML：

- 11 个关键工作台；
- 数字迎新、班级与辅导员、谈心家校、活动二课与社团 4 个冻结缺口页。

已完成 15 / 15 页生产 `routeName`、入口权限、动作权限、数据范围与敏感信息边界核对：

- **13 页契约一致**；
- **2 页存在生产菜单与路由守卫权限码冲突**。

明确阻断：

1. 数字迎新：菜单 `studentAffairs.orientation.view`，真实路由 `orientation.student.view`；
2. 班级管理：菜单 `studentAffairs.class.view`，真实主路由 `campus.record.view`。

`330-student-affairs-extension.json` 与对应 HTML 已分别登记菜单权限、路由权限和阻断状态，不把不同权限码静默当作别名。

4 个冻结缺口页此前已完成 **12 / 12** 三档回归；11 个关键工作台仍需执行 **33 次**回归。该 12 次已包含在全库 546 次累计中，不重复累加。

### 4. 岗位实习 101 叶子 / 99 URL 当前有效性

来源快照审计曾实际通过：

- 12 / 12 模块；
- 101 / 101 叶子；
- 99 / 99 唯一 URL；
- 2 / 2 显式别名；
- 99 / 99 唯一 owner。

本轮比较 `7031fc39...` 与当前生产、当前 PR 后确认：

- `frontend/src/config/navPlan.js` 未变化；
- `manifest-parts/310-internship-key.json` 未变化。

因此原机器审计仍适用于当前岗位实习契约，但这不是新的脚本运行，最终候选 HEAD 仍必须重跑。

### 5. 毕业设计结构纠偏

发现旧原型把生命周期概念“总览、选题、开题、过程、成果、答辩、成绩、归档统计”误写成生产 8 工作区，并在旧报告中错误宣称与 `GRADUATION_WORKSPACES` 一致。

现已按生产事实源重建为：

1. 我的工作台 `gd-workbench`
2. 批次与实施 `gd-batch-impl`
3. 题目与选题 `gd-topic-select`
4. 过程指导 `gd-process`
5. 开题与成果 `gd-proposal-final`
6. 答辩与成绩 `gd-defense`
7. 风险与归档 `gd-risk-archive`
8. 模板与设置 `gd-templates`

生产覆盖量：

- 8 个工作区；
- 50 个三级叶子；
- 48 个唯一 URL；
- 2 个显式共享 URL：`defense-scoring`、`stats-report`。

实际施工：

- 删除旧 `artifact.html`、`proposal.html`、`grade.html`、`archive.html`；
- 新增 `batch-implementation.html`、`proposal-final.html`、`risk-archive.html`、`templates.html`；
- 重定义其余 4 个 HTML；
- 重建 `320-graduation.json`；
- 重写共享 `v2-graduation-key.js` 和流程样式；
- JavaScript 写入前通过 `node --check`；
- 独立 HTML 总数仍保持 8，全库仍为 290；
- 当前重映射后浏览器回归：**0 / 24**。

### 6. 毕业设计机器审计

新增：

- `tools/check-graduation-workspace-audit.mjs`
- `graduation/workspace-audit-report.md`

工具直接比较生产 `graduationWorkspaces.js` 与 `320-graduation.json`，检查：

- 8 工作区、50 叶子、48 唯一 URL、2 共享 URL；
- workspace key、名称、主入口和全部 `coveredRoutes`；
- 权限候选覆盖；
- 8 个 HTML 的存在性和唯一 owner；
- 字段、状态与业务边界；
- 漏项、过时项和共享 owner 偏差。

已完成：

- 工具 JavaScript 语法检查 PASS；
- 隔离同构夹具运行 8 / 50 / 48 / 2、8 HTML、0 error PASS。

尚未完成：当前真实完整 PR 分支上的脚本执行。隔离夹具 PASS 不能写成最终 HEAD 审计通过。

### 7. 可重复执行工具

- `tools/check-prototype-consistency.mjs`
- `tools/check-internship-route-audit.mjs`
- `tools/check-graduation-workspace-audit.mjs`
- `tools/run-browser-regression.mjs`
- `tools/README.md`

## 已确认

- PR #27 保持 Open / Draft / 未合并；
- 所有修改均位于 `docs/ui/teacher-pc-v2-html/`；
- 生产路由、布局、公共组件、API、权限实现、后端和数据库均未修改；
- 原型继续执行 fail-closed、学生主档单一事实源、敏感数据最小可见、用途与审计；
- 学工生产权限冲突已如实登记，没有在原型层伪造一致性；
- 毕业设计旧工作区错误已撤销，没有继续对错误结构执行无效回归；
- 毕业设计机器审计的能力和结论边界已写入总 Manifest 与专项报告。

## 尚未确认

- 当前完整最终候选 HEAD 的一致性检查器 PASS；
- 剩余 108 页、324 次浏览器回归；
- 学工 11 个关键工作台的 33 次浏览器回归；
- 毕业设计现行 8 工作区的 24 次浏览器回归；
- 最终冻结 HEAD 的岗位实习 101 / 99 审计；
- 毕业设计最终 HEAD 的 8 / 50 / 48 / 2 真实分支审计；
- 打印、键盘、焦点、Escape、焦点归还和高风险业务人工复核；
- 数字迎新与班级管理生产权限冲突的最终裁决；
- G0–G7 全部 PASS。

当前执行容器不能解析 GitHub 域名，无法直接克隆或下载完整分支；GitHub 连接器可以读取和维护仓库，但现有生产 CI 不执行 docs 内冻结工具。工具落盘不等于最终 HEAD 已经通过。

## 下一步

1. 在可材料化完整分支快照的环境中运行一致性检查和毕业设计机器审计，重点确认旧 4 页无残留引用、新 4 页无孤儿或断链；
2. 执行学工 11 页 `11 × 3 = 33` 次回归；
3. 执行毕业设计现行 8 页 `8 × 3 = 24` 次回归；
4. 推进剩余页面族，直到累计 870 / 870；
5. 最终候选 HEAD 全量重跑一致性、浏览器、岗位实习路由审计和毕业设计工作区投影核对；
6. 完成人工打印、敏感业务、键盘与焦点验收；
7. G0–G7 全 PASS 后记录冻结 HEAD，再生成四条生产施工总控提示词。

## Git 纪律

- 保持 Draft PR #27
- 不合并 `main`
- 不创建新 PR
- 只修改 `docs/ui/teacher-pc-v2-html/`
- 生产代码只读
