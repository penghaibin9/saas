# 学工中心关键原型：开发还原契约

> 本目录不是学工中心全菜单逐页复制，而是覆盖最高频、最高风险和跨域最多的 11 个关键工作区。生产路由、权限、状态、数据范围和敏感字段仍以真实代码与后端为准。

## 关键页面

| 原型 | 生产入口 / 覆盖范围 | 主要权限 |
|---|---|---|
| `dashboard.html` | `/admin/student-affairs/dashboard` | `studentAffairs.dashboard.view` |
| `student-360.html` | `/admin/student/list` → 隐藏详情 `/admin/student-affairs/profile` | `student.profile.view` 或 `studentAffairs.student.view` |
| `leave-workbench.html` | 请假审批、销假续假、台账、统计 | `studentAffairs.leave.view` |
| `dorm-exception.html` | `/admin/student-affairs/dorm/exception` | `studentAffairs.dorm.view` |
| `risk-workbench.html` | `/admin/student-affairs/risk` | `studentAffairs.risk.view` / `handle` |
| `difficulty-workbench.html` | 困难认定批次、审核、公示、台账、学生库、统计、异议 | `studentAffairs.aid.view` |
| `funding-workbench.html` | 项目、批次、评审、公示申诉、发放、统计及扩展资助 | `studentAffairs.funding.view` |
| `discipline-workbench.html` | 处分工作台、送达申诉、台账、统计 | `studentAffairs.discipline.view` |
| `mental-crisis.html` | 心理名单、摘要、转介、危机、统计 | `studentAffairs.risk.view` + 高敏明细权限 |
| `stats-cockpit.html` | 学工统计、统计驾驶舱 | `studentAffairs.stats.view` |
| `archive-packages.html` | 学工归档、学生档案包 | `studentAffairs.archive.view` |

数字迎新、班级与辅导员、谈心家校、活动二课与社团等已有真实页面与独立业务结构，后续生产施工仍按 `navPlan.js` 全量核对；本关键包不把它们伪装成已完成原型覆盖。

## 统一安全上下文

学工中心必须复用真实 `StudentAffairsSecurityContext`，数据范围可能为：

- 全校
- 本院
- 本人负责班级
- 点名学生范围
- 授权宿舍楼栋
- 本人
- 无范围

页面只展示用户可理解的 `scopeLabel`，不把内部范围码暴露给老师。

### fail-closed 红线

- 非管理角色没有配置范围时，不能回退全校。
- 列表可以为空态；详情、修改、批量、导出应按后端返回 `403002 NO_DATA_SCOPE`。
- 菜单可见、路由守卫和后端权限必须同口径。
- 前端隐藏按钮不是权限控制。

## 页面事实边界

### 学工总览

只显示真实、可下钻且与当前范围一致的指标。当前可信卡片包括范围内学生、班级、本人待办、待审请假、逾期未销假、困难认定、奖助、处分和风险学生。没有可信范围聚合的宿舍指标不进入首页，不造假。

### 学生360

学生主档仍是唯一基础身份事实源。360只做授权业务聚合：班级、真实宿舍入住、请假、困难认定、奖助、处分、风险、谈话、家庭联系摘要和生命周期时间线。心理明细、经济材料和联系人明文另走敏感权限、用途和审计。

### 请假销假

申请、多级审批、续假、返校、销假确认和逾期扫描形成追加式历史。不同天数按学校规则进入不同节点；只有当前审批节点可操作。扫描操作幂等，不能重复生成提醒。

### 宿舍异常

宿管按楼栋、辅导员按负责学生、学工人员按授权范围查看。夜不归宿等异常先核验请假、门禁、现场与学生说明，只记录客观事实，再决定转维修、风险、家校或违纪流程。

### 风险处置

支持建单、分派、处置、跟进、转派、升级、接管、关闭和重开。心理来源普通角色只见摘要；超时扫描仅学工或校级管理角色执行。风险等级不是处分结论。

### 困难认定与奖助发放

困难认定区分批次、申请审核、公示、异议、有效学生库和台账；普通列表不展开受保护申请材料。资助区分项目、批次、评审、公示申诉和发放，评审通过不等于已到账，失败、重试、部分成功与凭证均留痕。

### 违纪处分

先事实与证据，后审批定性。送达、陈述申辩、生效、申诉、解除和归档是独立节点。学生360、处分台账和学生状态投影需要对账，但不能绕过状态机直接改主档。

### 心理危机

实行最小可见、点名授权和敏感访问双向审计。查看高敏明细需要原因；成功和拒绝都记录。系统负责流程与留痕，不自动生成医疗诊断。

### 统计与档案

统计继承后端范围，敏感域遵守最小样本和聚合粒度。档案包只收录已办结或可归档版本，原始附件、结论、撤回和重开历史不可覆盖；下载受权限、脱敏、用途、水印与审计约束。

## 公共组件映射

生产还原优先使用：

- `BasePortalLayout`
- `ModulePageShell`
- `DataTable`
- `AdvancedFilter`
- `AppPermissionButton`
- `AppDrawer` / `AppConfirmDialog`
- 加载、空、错误和无权限状态组件
- 学生选择、学院班级选择、文件中心、Excel 导出组件
- 风险、状态和敏感访问提示组件

原型共享 JS 只用于离线展示，不进入生产 Vue 运行时。

## 开发 AI 读取顺序

1. 阅读 11 个 HTML 的 route、permission、states 和 boundary。
2. 阅读 `manifest-parts/300-student-affairs-key.json`。
3. 阅读 `shared/v2-student-affairs-workbench.css/js`。
4. 回到生产 `navPlan.js`、学工路由、真实 Vue 页面、API 与服务。
5. 先核对权限与数据范围，再还原视觉和交互。
6. 不复制 placeholder 数据、候选状态或前端权限判断。

## 当前验证口径

- 11 个 HTML、共享 CSS/JS、README 和 manifest 已落盘。
- 关键入口、权限与安全边界已按生产菜单、API 和安全上下文静态核对。
- 本批真实浏览器渲染次数为 0，不能宣称控制台、溢出、键盘、焦点或三档分辨率回归通过。
