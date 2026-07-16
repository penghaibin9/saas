# 校园通小程序 · 全量设计交付与开发对照

> 目标读者：开发者 / Claude Code。本包含全部页面设计稿（`design/*.dc.html`）+ 逐页开发提示词 + 代码路径对照。
> 目标：在**现有 uni-app + Vue3 小程序工程**（`miniapp/`）中，用工程既有组件与令牌，1:1 复刻这些设计。

## 0. 怎么用这个包

1. 设计稿是 **HTML 参考稿**（浏览器/平台预览可看），**不是可直接上线的代码**。请在 `miniapp/` 里用 Vue3 + uni-app 重建。
2. 每屏给了一句「开发提示词」——可直接丢给 AI 编码助手，让它照着生成对应 `.vue` 页面。
3. 复用工程既有资产，**不要另造轮子**：
   - 组件：`miniapp/src/components/`（`MobileNavBar` `MobileStatusTag` `MobileTimeline` `MobileSafeAreaBar` `MobileTabBar` `MobileGlobalState` `MobileInlineAlert` `MobileSegmented` 等）
   - 设计令牌：`miniapp/src/styles/tokens.css`（颜色/字号/间距/圆角/阴影，**禁止硬编码**）
   - 数据：`miniapp/src/mock/*` + `miniapp/src/services/{studentApi,teacherApi}.js`
4. 学生端主色蓝（`--primary-600 #2563EB`），教师端强调青绿（`--teacher-600 #0D9488`）；卡片圆角 16px、卡片阴影统一。

## 1. 全局设计规范（所有页面统一）

- 顶部导航：学生蓝色渐变 `linear-gradient(162deg,#0e3a80,#1a56be,#2f76dd)`；教师青绿渐变 `linear-gradient(160deg,#0b5f57,#0d9488,#14b8a6)`。
- 卡片：`背景#fff / 圆角16px / 阴影 0 3px 14px -8px rgba(15,40,90,.14)`。
- 状态标签色：待办/进行中蓝、成功绿、警告琥珀、危险红、中性灰（对齐 tokens 语义色）。
- 底部 TabBar：学生「首页/服务/消息/我的」，教师「工作台/审批/消息/我的」。
- 列表页统一空/加载失败/无网络占位（见系统状态屏）。

## 2. 页面对照表 + 开发提示词

> 「代码路径」标注：`现有` = miniapp 已有页面，照设计重做 UI；`新建` = 需新增路由与页面。

### 2.1 登录与入口

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 校园通小程序登录 | 通用 | 现有 `pages/login/index.vue` | 微信小程序登录页：品牌区+四大功能图标+微信手机号快捷登录+验证码登录+协议勾选+授权手机号底部弹层。 |
| 迎新入口方案 · 登录页限时入口 | 新生 | 新建（登录页条件块） | 迎新批次开放期在登录页品牌区下方加橙色「新生报到通道」卡（含倒计时），凭录取通知书编号首次登录，批次结束隐藏。 |
| 迎新入口方案 · 未报到首页态 | 新生 | 新建（`pages/student/home` 状态分支） | 学生首页按报到状态渲染：未报到时首屏整块为迎新引导卡（进度环+倒计时+继续报到按钮+环节清单），完成后收起恢复普通首页。 |

### 2.2 一级 Tab 页（`校园通-一级页面重新设计` 为最新统一版）

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 一级页面重新设计 · 学生首页 | 学生 | 现有 `pages/student/home/index.vue` | 蓝色渐变头部（问候+学分绩点/学分/出勤率）+通知条+常用服务9宫格+学业全周期步进条+待办列表。 |
| 一级页面重新设计 · 教师工作台 | 教师 | 现有 `pages/teacher/workbench/index.vue` | 头部（我的学生/待审批/待批阅）+教学管理9宫格+班级全周期概览+待我审批列表+顶部当前身份切换。 |
| 一级页面重新设计 · 学生服务大厅 | 学生 | 现有 `pages/student/campus-service/index.vue` | 按教务/实习/毕设/学工分中心卡片，每卡渐变图标九宫格；管理模式可增删服务项（配置驱动）。 |
| 一级页面重新设计 · 教师审批中心 | 教师 | 现有 `pages/teacher/approval/index.vue` | 待审批/已审批/我发起的子Tab+分类chip，卡片含学生信息、字段详情、审批流时间轴、退回/驳回/通过操作。 |
| 一级页面重新设计 · 消息（双角色） | 通用 | 现有 `pages/student/messages`、`pages/teacher/messages` | 顶部快捷分类入口（带未读角标）+最近消息列表+全部已读；教师端多「待办审批」聚合项。 |
| 一级页面重新设计 · 我的（双角色） | 通用 | 现有 `pages/student/me`、`pages/teacher/me` | 蓝色渐变个人头部+分组设置列表+退出登录二次确认弹层；教师端头部含身份切换。 |
| 一级页面重新设计 · 身份切换 | 教师 | 现有 `pages/role-switch/index.vue` | 底部弹层列出教师多身份（辅导员/毕设导师/实习导师/就业/教务/学院管理员），选中按该身份数据范围刷新。 |

### 2.3 岗位实习中心

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 二级页方向 · 实习周报 | 学生 | 现有 `pages/student/weekly-report/index.vue` | 顶部周次切换；当前周为可填表单（工作内容/收获/问题/工时+存草稿/提交），历史周只读+导师批阅。 |
| 二级页方向 · 实习打卡 | 学生 | 新建 `pages/student/internship/checkin` | 定位地图卡+大圆形打卡按钮（点击采集定位签到，成功变绿显示时间）+本周打卡记录（正常/迟到/缺卡）。 |
| 二级页方向 · 教师待审批 | 教师 | 现有 `pages/teacher/approval/index.vue` | 审批卡：学生信息+字段+审批流时间轴+退回/驳回/通过，操作后即时切换结果态。 |
| 三级模块二级页 · 申请与协议 | 学生 | 新建 `pages/student/internship/agreement` | 三方协议进度时间线+协议文件下载+实习保险状态三张卡。 |
| 三级模块二级页 · 指导巡访 | 教师 | 现有 `pages/teacher/internship-review` 扩展 | 本月巡访计划学生列表，每人「记录巡访」按钮点击后置为已巡访。 |
| 三级模块二级页 · 就业跟进 | 教师 | 现有 `pages/teacher/employment-follow/index.vue` | 就业统计KPI+未就业/跟进中/待核验/已落实Tab+学生列表带跟进动作。 |
| 入口补齐 · 企业岗位库 | 学生 | 新建 `pages/student/internship/enterprises` | 城市筛选chip+企业岗位卡列表（公司/岗位/薪资/城市/招聘人数）。 |

### 2.4 毕业设计中心

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 二级页方向 · 毕设中心 | 学生 | 现有 `pages/student/graduation/index.vue` | 课题头部+突出「提交中期」主行动卡+9节点竖向里程碑时间轴+指导记录。 |
| 三级模块二级页 · 毕设选题 | 学生 | 新建 `pages/student/graduation/topics` | 题目列表（名额/导师）+「选择该题目」单选，选定后顶部提示等待导师确认。 |
| 三级模块二级页 · 任务书 | 学生 | 新建 `pages/student/graduation/taskbook` | 任务书状态+研究内容+进度安排竖向时间线+参考文献，只读展示。 |
| 三级模块二级页 · 答辩安排 | 学生 | 新建 `pages/student/graduation/defense` | 答辩时间/地点/顺序/组长信息卡+同组答辩学生时段列表。 |

### 2.5 教务中心

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 三级模块二级页 · 我的课表 | 学生 | 新建 `pages/student/academic/schedule` | 周一~周五日期切换+当天课程列表（时间/课名/教师/教室）。 |
| 三级模块二级页 · 课程成绩 | 学生 | 现有 `pages/student/academic` 扩展 | GPA/排名/学分头部+课程列表（分数或进行中标签）。 |
| 三级模块二级页 · 学分修读 | 学生 | 新建 `pages/student/academic/credits` | 总学分进度条+按公共/专业核心/选修/实践分类的已修/应修。 |
| 三级模块二级页 · 学业预警 | 学生 | 新建 `pages/student/academic/warning` | 预警科目卡（风险说明）+无其他预警的正向提示。 |
| 三级模块二级页 · 补考重修 | 学生 | 新建 `pages/student/academic/makeup` | 需补考科目（分数+补考时间地点）+已重修通过科目列表。 |
| 三级模块二级页 · 网上选课 | 学生 | 新建 `pages/student/academic/selection` | 必修/选修Tab+课程列表（学分/已选人数/容量）+选课/已选切换按钮。 |
| 入口补齐 · 成绩录入 | 教师 | 新建 `pages/teacher/academic/grade-entry` | 课程班级下的学生名单+分数输入框+底部提交（提交后置为教务审核中）。 |
| 入口补齐 · 考勤管理 | 教师 | 新建 `pages/teacher/academic/attendance` | 课次应到/实到/迟到/缺勤统计+学生列表，点行循环切换出勤状态。 |

### 2.6 学工中心

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 二级页方向 · 请假销假 | 学生 | 现有 `pages/student/affairs/leave.vue` 扩展 | 类型切换（病/事/外出）+起止时间+事由+附件上传+提交；下方我的请假记录带状态标签。 |
| 二级页方向 · 校园服务办理 | 学生 | 现有 `pages/student/campus-service` | 分类chip筛选+服务项列表（图标/部门/说明/可办状态）。 |
| 三级模块二级页 · 我的宿舍 | 学生 | 新建 `pages/student/affairs/dorm`（现有 dorm.vue 可复用） | 宿舍信息（楼栋/房间/床位）+室友列表+最近检查结果。 |
| 三级模块二级页 · 奖助申请 | 学生 | 新建 `pages/student/affairs/funding` | 奖助项目列表（金额/说明）+申请/已申请切换按钮。 |
| 三级模块二级页 · 活动与二课 | 学生 | 新建 `pages/student/affairs/activity` | 第二课堂学分进度+近期活动列表+报名/已报名切换。 |
| 三级模块二级页 · 谈心谈话 | 教师 | 新建 `pages/teacher/affairs/talk` | 顶部新增记录（学生+内容表单）+历史谈话记录列表。 |
| 三级模块二级页 · 违纪处分 | 学生 | 新建 `pages/student/affairs/discipline` | 本人违纪记录；无记录时正向空状态「请继续保持」。 |
| 三级模块二级页 · 心理关注 | 教师 | 新建 `pages/teacher/affairs/mental`（强敏感） | 仅辅导员可见的关注名单，脱敏（只显关注提醒+跟进状态，不显诊断隐私），顶部保密提示。 |

### 2.7 就业中心

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 二级页方向 · 毕业与就业中心 | 学生 | 现有 `pages/student/employment/index.vue` | 就业意向卡+5步就业流程竖向时间线+智能岗位推荐（匹配度）。 |

### 2.8 教师端 · 学生与工作

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 三级模块二级页 · 我的学生列表 | 教师 | 现有 `pages/teacher/*`（学生库） | 阶段筛选chip+学生列表（姓名/阶段/待办/风险标签），点入学生详情。 |
| 三级模块二级页 · 风险学生列表 | 教师 | 现有 `pages/teacher/risk-students/index.vue` | 风险等级筛选+按风险排序学生列表（最近风险事件+等级标签）。 |
| 二级页方向 · 学生详情（风险画像） | 教师 | 现有 `pages/teacher/student-detail/index.vue` | 学生档案头+高风险横幅+实习信息+动态时间线+待处理事项（催交/处理/记录）。 |
| 入口补齐 · 通知发布 | 教师 | 新建 `pages/teacher/notice/publish` | 接收范围chip（全体/本班/实习生）+标题+内容表单+发布。 |
| 入口补齐 · 数据看板 | 教师/管理员 | 现有 `admin/data-center` 移动版 | KPI四宫格（在册/风险/待处理预警/就业率）+生命周期漏斗条形+学院风险分布。 |
| 拓展页面 · 我的课程 | 教师 | 新建 `pages/teacher/courses` | 本学期任教课程列表（课名/班级/时间地点/人数）。 |
| 拓展页面 · 我的班级 | 教师 | 新建 `pages/teacher/classes` | 管理班级列表（人数/风险数）+班级全周期概览。 |
| 拓展页面 · 移动催办 | 学院管理员 | 现有 `pages/teacher/todos` 扩展 | 全院待处理事项列表（可勾选+即将超时标签）+一键批量催办。 |

### 2.9 数字迎新（核心卖点，完整报到旅程）

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 拓展页面 · 迎新报到（总览） | 新生 | 现有 `pages/student/orientation/index.vue` | 报到状态+报到码+8环节报到流程时间线+联系人。 |
| 拓展页面 · 预报到信息采集 | 新生 | 新建 `pages/student/orientation/collect` | 基础信息+家庭信息表单，分步保存。 |
| 拓展页面 · 电子报到码 | 新生 | 新建 `pages/student/orientation/code` | 大号二维码+报到码编号+身份信息，核验后失效提示。 |
| 拓展页面 · 绿色通道申请 | 新生 | 新建 `pages/student/orientation/green-channel` | 困难类型选择+缓缴金额+证明材料上传+提交。 |
| 拓展页面 · 现场报到核验 | 迎新老师 | 新建 `pages/teacher/orientation/verify` | 扫描报到码大按钮+今日已核验学生列表。 |
| 拓展页面 · 迎新看板 | 迎新老师 | 现有 `admin/orientation` 移动版 | 报到KPI（计划/已报到/报到率/异常）+报到进度条+未报到学生列表。 |

### 2.10 账号与系统状态

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 三级模块二级页 · 搜索结果 | 学生 | 新建 `pages/common/search` | 搜索框+分类Tab（全部/服务/消息/我的申请）+分组结果列表。 |
| 三级模块二级页 · 账号与安全 | 通用 | 新建 `pages/me/security` | 手机号/微信绑定/实名认证/修改密码列表+注销账号入口。 |
| 三级模块二级页 · 修改密码 | 通用 | 新建 `pages/me/password` | 原密码/新密码/确认新密码表单+提交后需重新登录提示。 |
| 三级模块二级页 · 消息通知设置 | 通用 | 新建 `pages/me/notify-settings` | 教务/实习/审批/系统通知开关列表（iOS 风格 switch）。 |
| 三级模块二级页 · 心理健康问卷 | 学生 | 新建 `pages/student/campus-service/mental-survey` | 单选题问卷（3题）+提交，注明结果仅心理中心可见。 |
| 三级模块二级页 · 系统状态占位 | 通用 | 组件 `MobileGlobalState` | 空数据/加载失败(重试)/网络异常(检查网络) 三种统一占位，供所有列表页复用。 |

### 2.11 内容详情

| 设计文件 · 屏 | 角色 | 代码路径 | 一句话开发提示词 |
| --- | --- | --- | --- |
| 三级模块二级页 · 消息详情 | 学生 | 新建 `pages/student/messages/detail` | 发送方+时间+正文+处理状态+底部行动按钮（如去提交周报）。 |
| 三级模块二级页 · 通知公告详情 | 学生 | 新建 `pages/common/notice/detail` | 分类标签+标题+发布部门时间+正文长文。 |

## 3. 数据来源对照（复刻时对齐字段）

- 学生：`mock/student/{home,academic,internship,graduation,employment,orientation,campusService,applications,messages,profile}.js`
- 教师：`mock/teacher/{workbench,students,approval,internshipReview,graduationGuide,employmentFollow,todos,messages}.js`
- 角色/品牌：`config/roles.config.js`、`config/brand.config.js`
- 数据看板口径：`frontend/src/mocks/dataCenter/dataCenter.mock.js`（在册 4520 / 风险 114 / 待处理预警 47 / 就业落实率 70.8%）

## 4. 附：迎新方案文档

见同目录 `迎新入口与告知方案.md`（多渠道告知 + 登录页限时入口 + 登录后状态驱动首页的完整方案）。
