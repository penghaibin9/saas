# Teacher PC V2 四窗口生产迁移映射

> 状态：**DRAFT / BLOCKED BY PROTOTYPE FREEZE GATES**。本文件冻结并行施工边界，不代表现在允许修改生产前端。只有 `prototype-freeze-gates.md` G0–G7 全部 PASS、冻结 HEAD 已记录后，才生成并启用四条总控提示词。

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

第一轮四个窗口全部只读：

- `frontend/src/layouts/BasePortalLayout.vue`
- `frontend/src/config/navPlan.js`
- `frontend/src/config/adminMenu.js`
- `frontend/src/components/ui/**`
- `frontend/src/components/common/**`
- `frontend/src/components/business/**`
- 全局样式、Token、图标和构建配置

发现公共组件缺口只登记，不自行修改。公共层统一治理必须由单一负责人、单独批次处理。

## 窗口 A · 教务中心

### 建议分支

`refactor/teacher-pc-academic-affairs-v2`

### 独占范围

- 教务中心 29 个生产二级模块对应的前端页面、中心本地组件、中心本地样式和前端测试。
- 主要事实源：`frontend/src/modules/academicAffairs/**`。

### 冻结原型输入

- `academic-affairs/**`
- `manifest-parts/00`–`220`
- `component-reuse-matrix.md`
- `page-archetype-matrix.md`
- 教务相关 README 与 regression-report

### 当前工作区

**27 个**，包括新补的专业分流、排课管理和课堂考勤。

### 禁止越界

- 不修改学工、实习、毕设页面。
- 不修改学生主档、统一身份和后端教务服务。
- 不调整 29 个二级名称、顺序或权限投影。
- 不把统计、归档、成绩发布、专业分流确认或自动排课改成前端本地状态。

## 窗口 B · 学工中心

### 建议分支

`refactor/teacher-pc-student-affairs-v2`

### 独占范围

- 学工中心页面、中心本地组件、中心本地样式和前端测试。
- 学生主档页面只能按现有职责优化，不复制第二套学生数据模型。

### 冻结原型输入

- `student-affairs/**`
- `manifest-parts/300-student-affairs-key.json`
- `manifest-parts/330-student-affairs-extension.json`
- `shared/v2-student-affairs-workbench.css/js`
- `shared/v2-freeze-gap.css/js`
- 学工 README 与 regression-report

### 当前工作区

**15 个**：原有 11 个关键页，加数字迎新、班级与辅导员、谈心家校、活动二课与社团。

### 禁止越界

- 不修改统一学生主档表结构和身份接口。
- 不把无数据范围角色回退为全校。
- 不在普通页面展开心理、家庭经济、谈话原文和联系人明文。
- 不把风险、宿舍异常或心理关注直接定性为处分或诊断。
- 不修改教务、实习、毕设页面。

## 窗口 C · 岗位实习中心

### 建议分支

`refactor/teacher-pc-internship-v2`

### 独占范围

- 岗位实习中心页面、中心本地组件、中心本地样式和前端测试。
- 生产事实源：实习模块路由、Vue 页面、API、批次、状态机和权限。

### 冻结原型输入

- `internship/**`
- `manifest-parts/310-internship-key.json`
- `shared/v2-internship-key.css/js`
- `tools/check-internship-route-audit.mjs`
- 实习 README 与 regression-report

### 精确覆盖口径

- 12 个生产二级模块；
- 101 个三级叶子；
- 99 个唯一 URL；
- 2 个列表/详情共享 URL；
- 10 个关键 HTML owner。

### 禁止越界

- 不复制学生主档、企业主档或就业事实。
- 不跳过匹配冲突和三方协议确认。
- 不把批准请假显示为正常打卡。
- 不改变成绩权重、审核、发布和复核状态机。
- 不修改教务、学工、毕设页面。

## 窗口 D · 毕业设计中心

### 建议分支

`refactor/teacher-pc-graduation-v2`

### 独占范围

- 毕业设计 8 个工作区页面、中心本地组件、中心本地样式和前端测试。
- 生产事实源：`graduationWorkspaces.js`、毕设路由、Vue 页面、API、状态与权限。

### 冻结原型输入

- `graduation/**`
- `manifest-parts/320-graduation.json`
- `shared/v2-graduation-key.css/js`
- 毕设 README 与 regression-report

### 禁止越界

- 不复制学生、教师和课程事实源。
- 不跳过课题容量、导师上限、专业和重复分配冲突。
- 不覆盖材料、计划和成绩历史版本。
- 不把查重结果直接转为学术结论。
- 不在缺评分或缺材料时发布成绩或生成完整档案。
- 不修改教务、学工、实习页面。

## 四窗口统一提交纪律

每个窗口必须：

1. 从同一个冻结 HEAD 创建分支。
2. 开始前记录分支、HEAD、对应 Draft PR 和允许文件清单。
3. 使用精确暂存，不使用 `git add -A`。
4. 每批提交只包含本中心文件。
5. PR 保持 Draft，不合并 `main`。
6. 报告实际修改文件、路由覆盖、构建结果和未验证项。
7. 发现公共层需求只登记，不自行越界修改。

## 推荐合并顺序

1. 四个 Draft PR 完成后，先做公共层统一治理批次。
2. 教务中心。
3. 学工中心。
4. 岗位实习中心。
5. 毕业设计中心。
6. 最后跑教师 PC 全量路由、权限、构建、视觉和浏览器回归。

该顺序只用于减少共享样式和中心导航冲突，不代表业务优先级。

## 提示词启用条件

四条总控提示词只有在以下条件全部满足时输出：

- `prototype-freeze-gates.md` G0–G7 全部 PASS。
- 297 个业务切面、290 个 HTML、43 个共享文件和 60 个工作区通过程序化一致性检查。
- 岗位实习 101 叶子 / 99 URL 机器审计 0 error。
- 870 / 870 基础浏览器渲染 PASS，打印与特殊状态另行通过。
- README、PROGRESS、Manifest、route-coverage 和 PR 描述数字一致。
- 冻结 HEAD 已记录。
- 四窗口精确文件所有权清单已从冻结 HEAD 重新生成。

当前状态：**禁止据此立即开工生产前端。**
