# PROGRESS

## 当前状态

- 状态：**IN PROGRESS**
- 基线：`main@b0af2244e1c8d466fe8afbd7b2bc0ab067d68489`
- 分支：`codex/teacher-pc-v2-html-library`
- Draft PR：`#27`
- 共享设计系统：`teacher-pc-v2 / 0.5.0`
- 生产代码修改：**否**
- 允许目录外修改：**0**

## 本轮收尾完成

### 学院专业班级

真实 `AaOrgConsole.vue` 的 11 个 Tab 已全部进入 manifest：

1. 学院
2. 专业
3. 行政班
4. 年级
5. 教学班
6. 专业方向
7. 班级学生
8. 班级调整
9. 组织树
10. 组织统计
11. 变更审计

同时覆盖新建/编辑抽屉、教学秘书绑定、逻辑删除、班级学生抽屉、个体转班、专业方向总开关、批量班级调整、前置核验、阻断结果和执行确认。

### 学年学期

- 学期管理
- 新建学期
- 学年管理
- 当前学期设置
- 学期周次
- 教学周配置
- 教学周配置非草稿锁定态
- 学期状态及冻结/解冻
- 学期切换记录
- 学期归档只读总览

### 校历节次

- 校历管理
- 校历发布后锁定态
- 节假日配置
- 补课日配置
- 教学周日历
- 校历发布
- 校历归档只读总览
- 节次管理
- 上课时间段

`time-slots.html` 与 `time-bands.html` 的提交 `722a67a74b2dbad5f27ddb7459ac3ce8ee5e2feb` 已快进接入当前分支和 Draft PR #27。

## 累计数量

- manifest 条目：**82**
- 独立 HTML：**76**
- 共享路由条目：**8**
- shared 文件：**10**
- 仓库截图：**0**
- 本地累计渲染截图：**118**
- 已完成首轮工作区：**8**
- 完成一级中心：**0**

## 本批验证

### 学院专业班级

- 页面：**11**
- 1440 × 1000：11 页全部渲染
- 1280 × 900：5 个关键页额外渲染
- 1920 × 1080：5 个关键页额外渲染
- 本批渲染：**21 次**

### 学年学期与校历节次

- 页面：**19**
- 1440 × 1000：19 页全部渲染
- 1280 × 900：7 个关键页额外渲染
- 1920 × 1080：7 个关键页额外渲染
- 本批渲染：**33 次**

### 结果

- 页面级横向溢出：**0**
- 控制台明显错误：**0**
- 相对资源缺失：**0**
- 默认态、加载态、空态、错误态、无权限态、长数据态及关键抽屉/弹窗均完成静态检查
- 学期周次示例日期已按 `2026-09-01` 起连续日期计算，不存在无效月份
- 截图只保存在执行环境，**未提交 GitHub 仓库**

执行环境说明：容器 Chromium 对 `file://` 和 `localhost` 直接导航返回 `ERR_BLOCKED_BY_ADMINISTRATOR`。采用“HTML + 本地 CSS/JS/SVG 完全内联后渲染”检查布局与交互，并独立检查原始 HTML 相对资源路径。

## 已完成首轮工作区

1. 成绩管理
2. 成绩审核发布更正
3. 学籍管理
4. 注册管理
5. 学籍异动办理
6. 学院专业班级
7. 学年学期
8. 校历节次

“首轮完成”不代表教务中心或教师 PC 全量完成。

## 已确认差异 / 疑问

1. `navPlan.js` 使用 `PRESERVED`，`AaRosterListView.vue` 使用 `RETAINED`。继续记录，不修改生产代码。
2. `PRESERVE` 是保留学籍，`RETAIN` 是留级，不能合并。
3. `/status-changes/retain` 仅为旧路由重定向，不生成原型。
4. 异动记录 `term_code` 当前无可靠回填，不在异动归档原型中虚构学期筛选。
5. 学期和校历归档实际动作统一进入“教务归档”，本原型只做真实只读联动，不造第二套归档写入口。
6. 校历发布后事件锁定；教学周总数与考试周起始周次仅 `DRAFT` 学期可改。

## 下一批精确起点

按真实业务依赖，下一批从 **课程库** 开始：

1. `/admin/academic-affairs/courses` 课程列表
2. `/admin/academic-affairs/courses/new` 新建课程
3. `/admin/academic-affairs/courses/:id` 课程详情及审核态
4. `/admin/academic-affairs/courses/:id/edit` 编辑课程
5. `/admin/academic-affairs/courses/console?tab=category` 课程分类
6. `?tab=nature` 课程性质
7. `?tab=credit` 学分学时
8. `?tab=outline` 课程大纲
9. `?tab=assessment` 考核方式
10. `?tab=owner` 课程负责人
11. `?tab=material` 课程材料
12. `?tab=disable` 课程停用
13. `?tab=archive` 历史课程
14. 分类/性质/考核方式抽屉、学分学时抽屉、负责人抽屉、材料上传与作废确认、启停状态

课程库完成后继续 **培养方案**，仍以真实 `AaProgramListView.vue`、`AaProgramEditorView.vue`、`AaProgramConsoleView.vue` 的路由、Tab、状态机和字段为准。

## Git 状态

- 保持 Draft PR #27
- 不合并 main
- 不创建新 PR
- 每批只修改 `docs/ui/teacher-pc-v2-html/`
- 当前收尾完成后，下一会话从课程库直接续工
