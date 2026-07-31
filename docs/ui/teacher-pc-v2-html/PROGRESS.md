# PROGRESS

## 当前状态

- 状态：**IN PROGRESS / NOT FROZEN**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 生产代码修改：**否**
- 允许目录外修改：**0**
- 当前阶段：**冻结缺口结构收口完成，等待真实程序化执行与浏览器回归**

## 当前统一统计

- Manifest 条目：**297**
- 独立 HTML：**290**
- 共享 HTML 路由条目：**9**
- shared 文件：**43**
- 首轮工作区：**60**
- 完整冻结一级中心：**0**
- 仓库截图：**0**
- 历史本地渲染截图记录：**309**

分布：

- 教务：27
- 学工：15
- 岗位实习：10 个关键工作台覆盖 12 个生产二级模块
- 毕业设计：8

## 本阶段实际完成

### 1. Manifest 与统计纠偏

总 Manifest 已聚合 `00`–`220`、`300`、`310`、`320`、`330`。README、PROGRESS、route-coverage、总 Manifest 和 PR 描述应统一使用 **297 / 290 / 43 / 60**。

### 2. 教务冻结缺口

新增独立原型与 `220-academic-freeze-gaps.json`：

- 专业分流：五态批次、容量、试分、调剂、确认写学籍；
- 排课管理：规则、教师可用时间、试排、漏排原因和冲突；
- 课堂考勤：PC 只统计移动端已提交场次并触发预警扫描。

### 3. 学工冻结缺口

新增独立原型与 `330-student-affairs-extension.json`：

- 数字迎新；
- 班级与辅导员；
- 谈心家校；
- 活动二课与社团。

继续执行 fail-closed 数据范围、学生主档单一事实源、敏感信息最小可见和用途审计。

### 4. 岗位实习 99 URL 契约重建

生产 `navPlan.js` 的岗位实习组实际为：

- 12 个二级模块；
- 101 个三级叶子；
- 99 个唯一 URL；
- 2 个显式共享 URL。

`310-internship-key.json` 已改为精确生产 URL，并为每个模块登记：

- `permissionCandidates`
- `fieldContract`
- `statusContract`
- `apiParameterContract`

旧的错误子路径与模糊 `coveredRoutes` 已废止。

### 5. 可重复执行工具

新增：

- `tools/check-prototype-consistency.mjs`
- `tools/check-internship-route-audit.mjs`
- `tools/run-browser-regression.mjs`
- `tools/README.md`

浏览器执行器从总 Manifest 动态读取 290 个唯一 HTML，并在三档分辨率下计划执行 **870 次渲染**。

## 已确认

- PR #27 继续保持 Open / Draft / 未合并。
- 所有本阶段修改仍在 `docs/ui/teacher-pc-v2-html/`。
- 生产路由、布局、公共组件、API、权限、后端和数据库均未修改。
- 新增 7 页带默认、加载、空、错误、403、只读和长数据状态。
- 新增共享弹层实现焦点进入、Tab 焦点陷阱、Escape 关闭与焦点归还。

## 尚未确认

- 一致性检查器在当前完整 HEAD 的真实执行结果；
- 岗位实习 101 叶子 / 99 URL 审计器的真实执行结果；
- 当前 290 个 HTML 的同一 HEAD 三档浏览器全量回归；
- 870 次渲染的控制台、资源、溢出、焦点与截图结果；
- 打印页和特殊业务状态人工复核；
- G0–G7 全部 PASS。

当前会话容器无法解析 GitHub 域名，不能克隆完整分支；现有 CI 只运行生产测试与构建，没有执行 docs 内冻结工具。工具已提交不等于检查通过。

## 下一步

1. 在能够完整检出该分支并安装 Chrome / Chromium 的执行环境运行一致性检查。
2. 修复检查报告中的缺失、重复、孤儿和相对资源问题。
3. 运行岗位实习路由审计并修到 0 error。
4. 先做 10 页冒烟，再执行 290 × 3 全量浏览器回归。
5. 修复所有失败后重跑，直到 870 / 870 PASS。
6. 完成人工打印、状态、键盘和业务红线复核。
7. G0–G7 全 PASS 后记录冻结 HEAD，再生成四条生产施工总控提示词。

## Git 纪律

- 保持 Draft PR #27
- 不合并 `main`
- 不创建新 PR
- 只修改 `docs/ui/teacher-pc-v2-html/`
- 生产代码只读
