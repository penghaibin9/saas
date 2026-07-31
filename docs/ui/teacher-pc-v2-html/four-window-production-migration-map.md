# Teacher PC V2 四窗口生产迁移映射

> 状态：**DRAFT / BLOCKED BY PROTOTYPE FREEZE GATES**。本文件先冻结并行施工边界，不代表现在允许修改生产前端。只有 `prototype-freeze-gates.md` 全部 PASS 后，才生成并启用四条总控提示词。

## 总原则

四个窗口只做各自中心的生产前端还原：

- 不改后端、数据库、状态机、权限码和 API 契约。
- 不重命名或删除生产路由。
- 不以原型 placeholder 替换真实数据。
- 不把前端隐藏按钮当权限控制。
- 不同时修改公共布局、全局导航、Token 和公共组件。
- 不使用 `git add -A`。
- 每个窗口独立分支、独立 Draft PR，禁止直接合并 `main`。

## 开工前公共层冻结

四窗口同时开启前，必须先在同一个基线提交中确认以下公共层保持不变：

- `frontend/src/layouts/BasePortalLayout.vue`
- `frontend/src/config/navPlan.js`
- `frontend/src/config/adminMenu.js`
- `frontend/src/components/ui/**`
- `frontend/src/components/common/**`
- `frontend/src/components/business/**`
- 全局样式、Token、图标和构建配置

第一轮四窗口全部把这些文件视为只读。发现公共组件 GAP 时，只在各自 PR 报告中登记，不自行修改。公共层统一治理另开后续单独批次，避免四个窗口互相覆盖。

## 窗口 A · 教务中心

### 建议分支

`refactor/teacher-pc-academic-affairs-v2`

### 独占业务范围

- 教务中心 29 个二级模块对应的前端页面与中心内组件。
- 生产模块主要事实源：`frontend/src/modules/academicAffairs/**`。
- 只允许修改明确属于教务中心的路由页面、中心本地组件、中心本地样式和前端测试。

### 原型输入

- `academic-affairs/**`
- `manifest-parts/00` 至 `210`
- `component-reuse-matrix.md`
- `page-archetype-matrix.md`
- 教务相关 README 与 regression-report

### 第一轮优先级

1. 教务公共页面壳与看板。
2. 24 个已完成首轮工作区按路由逐页还原。
3. 专业分流、排课管理、课堂考勤等缺口先补原型映射再施工。
4. 统一列表、详情、审批、复杂编排、打印和统计母版。

### 禁止越界

- 不修改学工、实习、毕设页面。
- 不修改学生主档、统一身份、后端教务服务。
- 不擅自调整 29 个二级名称、顺序或权限投影。
- 不把统计、归档、成绩发布等高风险操作改成前端本地状态。

## 窗口 B · 学工中心

### 建议分支

`refactor/teacher-pc-student-affairs-v2`

### 独占业务范围

- 学工中心页面、中心本地组件、中心本地样式和前端测试。
- 事实源包括 `frontend/src/modules/studentAffairs/**`、实际学工路由页面，以及被学工入口复用的明确业务页面。
- 学生主档页面只能按现有职责优化，不复制第二套学生数据模型。

### 原型输入

- `student-affairs/**`
- `manifest-parts/300-student-affairs-key.json`
- `shared/v2-student-affairs-workbench.css/js`
- 学工 README 与 regression-report

### 第一轮优先级

1. 学工总览与真实范围标签。
2. 学生列表 → 学生360授权聚合。
3. 请假、风险、宿舍异常、困难认定、奖助发放、处分、心理危机。
4. 统计驾驶舱和学生档案包。
5. 再处理数字迎新、班级辅导员、谈心家校、活动二课等未完整原型化模块。

### 禁止越界

- 不修改统一学生主档表结构和身份接口。
- 不把无数据范围角色回退为全校。
- 不在普通页面展开心理、家庭经济和联系人明文。
- 不把风险、宿舍异常和心理关注直接定性为处分或诊断。
- 不修改教务、实习、毕设页面。

## 窗口 C · 岗位实习中心

### 建议分支

`refactor/teacher-pc-internship-v2`

### 独占业务范围

- 岗位实习中心页面、中心本地组件、中心本地样式和前端测试。
- 生产事实源：实习模块路由、Vue 页面、API、批次、状态机和权限。

### 原型输入

- `internship/**`
- `manifest-parts/310-internship-key.json`
- `shared/v2-internship-key.css/js`
- 实习 README 与 regression-report

### 第一轮优先级

1. 总览、批次与规则版本。
2. 实习学生、企业与岗位。
3. 匹配、申请、三方协议、调岗退岗。
4. 打卡请假、周报任务、指导巡访。
5. 风险、评价成绩、就业转化、归档统计。

### 禁止越界

- 不复制学生主档、企业主档或就业事实。
- 不跳过匹配冲突和三方协议确认。
- 不把批准请假显示为正常打卡。
- 不改变成绩权重、审核、发布和复核状态机。
- 不修改教务、学工、毕设页面。

## 窗口 D · 毕业设计中心

### 建议分支

`refactor/teacher-pc-graduation-v2`

### 独占业务范围

- 毕业设计 8 个工作区页面、中心本地组件、中心本地样式和前端测试。
- 生产事实源：`graduationWorkspaces.js`、毕设路由、Vue 页面、API、状态与权限。

### 原型输入

- `graduation/**`
- `manifest-parts/320-graduation.json`
- `shared/v2-graduation-key.css/js`
- 毕设 README 与 regression-report

### 第一轮优先级

1. 总览与批次上下文。
2. 选题分配、开题、过程、成果。
3. 答辩组、回避、发布与应急调整。
4. 评分计算、审核发布与异议。
5. 归档包、统计、通知与预警。

### 禁止越界

- 不复制学生、教师和课程事实源。
- 不跳过课题容量、导师上限、专业和重复分配冲突。
- 不覆盖材料、计划和成绩历史版本。
- 不把查重结果直接转为学术结论。
- 不在缺评分或缺材料时发布成绩或生成完整档案。
- 不修改教务、学工、实习页面。

## 四窗口统一提交纪律

每个窗口必须：

1. 从同一个冻结基线创建分支。
2. 开始前记录分支、HEAD、对应 Draft PR 和允许文件清单。
3. 使用精确暂存，不使用 `git add -A`。
4. 每批提交只包含本中心文件。
5. PR 保持 Draft，不合并 `main`。
6. 报告实际修改文件、路由覆盖、构建结果和未验证项。
7. 发现公共层需求只登记，不自行越界修改。

## 推荐合并顺序

在四个 Draft PR 都完成后：

1. 先做公共层统一治理批次，并让四个分支同步最新基线。
2. 教务中心先合并，因为页面母版和公共组件使用面最广。
3. 学工中心第二。
4. 岗位实习第三。
5. 毕业设计第四。
6. 最后跑教师 PC 全量路由、权限、构建、视觉和浏览器回归。

合并顺序不是质量优先级，只是为了减少共享样式和中心导航冲突。

## 提示词启用条件

四条总控提示词只有在以下条件同时满足时输出：

- `prototype-freeze-gates.md` G0–G7 全部 PASS。
- PR #27 README、PROGRESS、manifest、route-coverage 和 PR 描述数字一致。
- 冻结 HEAD 已记录。
- 四窗口精确文件所有权清单已从生产仓库重新生成。
- 公共层在第一轮被明确设为只读。

当前状态：**禁止据此立即开工生产前端。**
