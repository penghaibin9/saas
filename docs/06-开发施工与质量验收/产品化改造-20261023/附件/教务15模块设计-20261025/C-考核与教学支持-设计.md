# C组：考核与教学支持——内部流程与逐页设计

日期：2026-10-25。对应独立计划模块08考务、09成绩、11教材、13质量、14统计。本文件是设计交付，不是施工或业务验收通过证明。

## 1. 范围、证据与执行状态

- 依据本地已合并主分支 `ff7786877` 的实际路由/组件，保留文档1、文档3成果；旧 `saas-roles-r0` 候选仅纳入待组合清单，未覆盖主分支。
- 67条导航条目、65个不同地址，逐一打开并保存/查看首屏截图。两条统计隐藏映射复用同地址证据；不是67个独立页面。
- 浏览器使用现有5173服务、已有账号的学校管理员岗位；未保存、审核、发布、扫描、归档、导出、打印或创建沙箱业务。没有启动服务、改源码、提交或推送。
- 读取失败：挂科清单。岗位不适用：学校管理员打开重修免修申请显示无权。两者保留证据，不当作正常路径通过。加载中/错误落点截图已重拍；教师自评/评价统计初始渲染截图不作为稳定结果。
- 未验证：所有写入链、学生/教师本人角色办理、故障注入、全部深层弹窗、375/390/430宽度、微信端。截图为当前窗口首屏，不能替代完整交互验收。
- 截图原件位于 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/`，`manifest.json` 是65地址证据索引。截图含沙箱样例，仅本地保存，本文不转录个人信息。
- Product Design（产品设计）用于真实页面截图优先审计及设计；没有使用生成图冒充页面。以下为可施工的信息与交互设计，尚未生成完整高保真改版图，不宣称视觉设计最终冻结。

## 2. 五条内部流程与现行规则

| 模块 | 当前流程定位 | 保留的事实与设计出口 |
|---|---|---|
| 考务 | 批次→来源教学任务圈课→课程确认→时间/考场/座位/监巡考→就绪检查→发布→异常处理/结束归档；缓考按既有节点批准后合流 | 不把“安排完成”当“考试完成”；列表先选对象再显示动作；打印从批次课程考场选择进入；每一步保留真实状态及原权限 |
| 成绩 | 任课任务/名单与成绩构成→录入暂存→提交→学院审核→教务发布→查询；复查、更正、认定、重修免修各自保留原链 | 已发布版本不可覆盖；空分不是0；发布和预警扫描分别反馈；未知写结果必须恢复查询，不能删掉保护来简化 |
| 教材 | 目录版次→教学任务选用→学院来源审核备案→征订/累计到货→发放名单/签收→费用/库存 | 选用、订单、发放、费用是不同对象；页签不代表这些对象已完成前序。去掉默认首行概览；数量保持原库存和费用口径 |
| 质量 | 质量记录→确认→生成整改→跟进→提交复核→关闭归档；评价批次→生成任务→学生/自评/同行/督导提交→核算发布→申诉归档 | 质量记录与评价结果分开；事故登记不自动产生处罚；匿名评教不泄露评价者；不能固定页签进度冒充对象状态 |
| 统计 | 选择专题与筛选→查询→可解释指标→同口径明细→快照/报表 | 每个指标保留单位、分子分母和数据时间；缺失不是0；下钻不得扩大范围；原快照与实时查询不混称 |

本轮保持现行运行流程，不把文档2尚未实施的目标审批顺序当作当前事实。角色权限、成绩权重、评价权重、审核人数、清考资格、教材费用、数据保留均不自行改变。

## 3. 已确认问题与统一设计决策

| 编号 | 实际证据 | 已定设计 | 保留与验证 |
|---|---|---|---|
| C01 | 考务打印08-02；AaExamSeatingPrintView.vue:23、80、175 | 主流程改为批次→课程→考场选择；深链接仍接原roomId，内部编号仅诊断详情 | 只复用现有读取，不绕过已发布/名单锁定/座位一致性与打印审计；是否有足够级联读取由接口核对后落实 |
| C02 | 教材选用11-02、审核11-03；AaTextbookConsoleView.vue:58、240、291；AaTextbookStageRail.vue:5 | 列表页移除默认首行对象概览和按页签完成进度；真实选中对象显示状态，参考流程折叠且不打完成勾 | 不自行推算五步状态；有后台状态事实才显示进度 |
| C03 | 评价批次13-09；AaEvaluationConsoleView.vue:26、649 | 未选批次不显示已完成阶段；队列和主要动作上移，规则按需展开 | 选中归档批次后只读；任务、结果与申诉仍独立 |
| C04 | 统计14-01至14-14；AaStatsOverviewView.vue:553、563、575–576 | 分布图、指标图及明细共同取消摘要文字转数字回退；图表只用有明确数值与单位的统计数据，同单位才比较；明细保留原值及单位，更新时间单列 | 验证20:xx不变成20，百分比不丢百分号，数量不丢单位；明细不复用失真图表数据；没有可靠数值时不绘图、不以假数据补图 |
| C05 | 质量看板13-01；AaQualityDashboardView.vue:333–342 | “即将到期”改为“已逾期”，沿用实际overdue筛选；区分本人待办与授权范围待办 | 不引入新到期阈值；缺受理人依据不能伪称待我 |
| C06 | 教材目录11-01、成绩审计09-18、质量跟进13-07、统计多页 | 固定枚举映射中文；用户输入标题不全局替换。原始审计数据和快照哈希默认折叠为实施人员使用 | 未知值显示业务信息待核对并可查原值，不把未知动作称“待确认”业务状态 |
| C07 | 考务归档08-04，同一记录列表UTC文本与详情本地时间 | 使用现有公共日期格式，列表/详情一致；不改原时间值 | 空值与非法值明确；时区转换仅展示 |
| C08 | 09-14学院审核、09-16更正及评价空态 | 无队列时一处空态；有队列未选时才提示选择；成功空、失败、加载互斥 | 承接旧候选已验证修复而非重新实现；越界页保留回退分页 |
| C09 | 09-11重修免修申请，管理员无权仍见表单和空申请 | 无权主体显示清晰拒绝和返回，停止展示假空结果；不放宽权限 | 学生本人的正常表单另验，不能用管理员截图代替 |
| C10 | 13-02至13-05默认长表单遮住历史；模板64–91行 | 列表为默认，显式“新增”进入现有表单；表单顺序按对象→时间→事实→意见→是否整改 | 不新建重复业务路由；未保存提醒、状态校验和历史入口保留 |
| C11 | 11-05费用台账学生仅内部编号；AaTextbookConsoleView.vue:303 | 优先显示可信学生姓名/学号及发放来源；读取接口未返回时单列必要字段补齐，不猜名称 | 仍同租户和原范围，不能额外读取敏感字段 |
| C12 | 11-07统计的选用条数与征订册数并列比例图 | 分为“选用备案记录数”“征订到货册数”“费用金额”，不同单位不共用完成比例轴 | 现有到货率分母保留；无时间序列不造趋势 |

## 4. 统一页面结构与恢复要求

- 队列页：标题/主动作 → 一行筛选 → 本范围或本页必要摘要 → 列表。未选对象不展示默认第一行的责任和进度；点击行内“查看/办理”后显示对象详情。
- 办理页：对象名称与状态 → 依据/原值目标值 → 输入或办理动作 → 已发生历史。只有影响决策的警告常显；来源与实现自证折叠或删除。
- 记录表单：必填字段和错误紧邻；保留失败输入；主按钮使用业务动词；提交中禁重发，结果未知只给查询恢复，不能用重试按钮直接再写。
- 统计页：已应用筛选摘要 → 不同单位指标 → 有业务意义的分布 → 明细。空基数、未接入、无权限和失败分别显示；导出仍用已应用筛选。
- 复用 `academicFlowContext.js` 的身份隔离、迟到响应及返回上下文；复用 ModulePageShell（页面外壳）紧凑模式、AppSectionCard（分区卡）折叠及 DataTable（表格）横向滚动。不得新增一套缓存或组件体系。
- 文字长度不作为唯一验收：同一任务应更易找到对象、判断状态、完成动作、回到原队列。未经实测不宣称节省时间。
- 以下逐页卡均要求：从详情返回原学期/筛选/页码/选中对象；身份变化清旧数据；错误不清输入；列表加载不显示假完成；写操作范围和状态由后端继续独立校验。

## 5. 逐入口设计卡（67条，含关联映射）

### 08．考务管理

#### 08-01 考务安排

- **入口与归属：**`/admin/academic-affairs/exam`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**批次名称/学期/状态列表 → 所选批次课程 → 时间、考场、座位、监巡考及发布检查。
- **主次操作：**列表创建批次；选中后按真实状态圈课、编排、发布；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**未选批次隐藏六格责任摘要和完成进度；选中后仅保留名称、状态、实际阻断和下一动作。
- **验收场景：**选择两个批次后课程、考场不串；返回保留批次/页码；读取失败不显示可发布。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-01.png)；源码 `frontend/src/modules/academicAffairs/views/AaExamConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:160`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-02 考务打印

- **入口与归属：**`/admin/academic-affairs/exam/print/seating`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**已发布批次 → 课程 → 考场 → 考生座位预览 → 打印类型与原因。
- **主次操作：**载入打印预览；满足原条件后才可打印；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**取消要求用户手输考场内部编号的主流程；从考务详情携带考场，独立入口复用已有批次/课程/考场读取能力选择；未选对象不显示步骤1至3已完成。
- **验收场景：**无考场时给选择入口；未发布/名单未锁定拒绝；返回恢复原批次；本轮不调用打印。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-02.png)；源码 `frontend/src/modules/academicAffairs/views/AaExamSeatingPrintView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:185`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-03 缓考审批

- **入口与归属：**`/admin/academic-affairs/exam?tab=defer`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**状态筛选 → 学生/课程/申请时间/当前节点队列 → 原因与材料 → 当前可办动作。
- **主次操作：**查看申请；符合当前责任时审批或退回；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**流程说明默认折叠；不把已通过申请的历史节点作为当前待办；病因类别映射中文但保留用户原理由。
- **验收场景：**已通过记录只读；不同节点动作按后端返回；意见失败保留；学生/课程切换不串材料。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-03.png)；源码 `frontend/src/modules/academicAffairs/views/AaExamConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:160`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-04 考务归档

- **入口与归属：**`/admin/academic-affairs/exam?tab=archive`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期/批次筛选 → 已归档批次列表 → 课程确认/缺考违纪摘要 → 封存记录。
- **主次操作：**查看封存证据；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**列表和详情使用同一公共本地时间格式；批次名称为主，不用编号复述；取消无意义当前阶段条。
- **验收场景：**同一归档时间两处一致；未归档不混入；封存详情不提供改写动作。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-04.png)；源码 `frontend/src/modules/academicAffairs/views/AaExamConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:160`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-05 等级考试

- **入口与归属：**`/admin/academic-affairs/level-exams`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**考试批次名称/类型/报名期限/状态 → 报名与费用 → 成绩结果。
- **主次操作：**新建考试；选中考试后查看报名和成绩；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**考试类型中文显示；未选考试不预设创建阶段；报名、费用、成绩动作留在所选考试内。
- **验收场景：**切换考试清除旧名单；空报名与读取失败区分；不改报名费和成绩规则。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-05.png)；源码 `frontend/src/modules/academicAffairs/views/AaLevelExamView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:55`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-06 补考批次

- **入口与归属：**`/admin/academic-affairs/makeup?tab=makeup`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期/状态筛选 → 批次列表 → 原课程及不及格来源名单 → 安排/成绩结果。
- **主次操作：**新建批次；逐行打开名单/纳入；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**取消默认首条批次概览；选中对象后才展示真实阶段；保留来源成绩身份不可用时禁止纳入。
- **验收场景：**同学生不同课程不合并；成绩来源缺失拒绝；重复纳入保护不变；关闭详情返回原页。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-06.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:162`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-07 毕业清考

- **入口与归属：**`/admin/academic-affairs/makeup?tab=clearance`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**毕业年级/学期 → 清考批次 → 未通过课程名单 → 安排与正式结果。
- **主次操作：**新建清考批次；查看名单；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**无批次时用一处空态和已有创建入口；应届/课程范围限制置于创建表单，不重复整页。
- **验收场景：**年级缺失定位字段；圈定名单不在前端猜测；成绩更新后只提供重新预审入口，不代替毕业通过。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-07.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:162`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 08-08 缓考合流

- **入口与归属：**`/admin/academic-affairs/makeup?tab=deferred`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**已批准申请队列 → 原考试课程 → 可合入目标批次 → 合流结果。
- **主次操作：**逐行选择目标批次并确认；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**首屏以待安排学生和课程为主；申请编号进入详情；默认首条大进度不冒充选中项。
- **验收场景：**已合流显示目标批次并禁止重复；目标不可接收时明确原因；来源课程与学生保持不变。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/08-08.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:162`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

### 09．成绩管理

#### 09-01 成绩总览

- **入口与归属：**`/admin/academic-affairs/grade-overview`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期/状态/课程筛选 → 查询总数与本页摘要 → 课程/教学班/教师/状态/下一步。
- **主次操作：**查询任务；逐行查看进度或正式成绩；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**接回既有27页候选精简；责任信息主行仅当前责任，后续链折叠；保留本页与全量口径。
- **验收场景：**未开始、审核中、已发布入口不同；返回保留筛选；无教师关系不能误作可录入。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-01.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:113`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-02 成绩录入

- **入口与归属：**`/admin/academic-affairs/grade-entry`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**任务选择 → 当前课程/教学班/学期 → 成绩构成与名单 → 录入区 → 保存/提交。
- **主次操作：**暂存成绩；检查完整性后提交审核；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**任务队列补教学班区分同名课程；不让长队列挤走录分区；保留空分不计零、未保存提醒及未知结果查询。
- **验收场景：**选不同任务不串草稿；切身份旧响应无效；缺分/构成不完整定位问题；发布成绩只读。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-02.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:117`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-03 挂科清单

- **入口与归属：**`/admin/academic-affairs/grade-fail`；独立业务入口。 当前结论：已截图首屏；正常数据读取受阻。
- **信息顺序：**学期选择器 → 查询/重置 → 学生/课程/有效成绩/补重修状态列表。
- **主次操作：**查询；进入原课程成绩或后续办理；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**当前读取失败须作为独立问题保留；学期用现有选择器，不要求手输学期码；不以空表遮蔽失败。
- **验收场景：**读取失败可重试且保留条件；全校与本院范围由后端限定；关联补考定位同一成绩。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-03.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeFailListView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:114`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-04 学生成绩单

- **入口与归属：**`/admin/academic-affairs/transcript`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学生选择 → 学生摘要及范围 → 学期/课程成绩 → 查询件入口。
- **主次操作：**查看本人授权范围内学生成绩；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留先选学生的空态；显示名称学号而非内部身份；明细与导出范围写在同一位置。
- **验收场景：**换学生立即清旧成绩；无权限返回明确状态；未发布成绩不进入正式成绩单。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-04.png)；源码 `frontend/src/modules/academicAffairs/views/AaTranscriptView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:116`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-05 成绩导入

- **入口与归属：**`/admin/academic-affairs/grade-entry?action=import`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**选择可导入任务 → 模板说明 → 文件选择 → 校验结果 → 确认结果。
- **主次操作：**检查导入文件；通过后确认导入；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**独立导入入口按可编辑状态提示，不把已发布任务当可导入；校验问题定位行/列且保留文件和草稿。
- **验收场景：**模板与当前任务绑定；错误行可修正重试；不触发自动提交审核；未知导入结果先查询。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-05.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeEntryView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:117`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-06 成绩导出

- **入口与归属：**`/admin/academic-affairs/transcript?action=export`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学生/学期选择 → 将导出范围及用途 → 生成结果/下载状态。
- **主次操作：**申请查询件或导出文件；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留显式导出模式；不把当前屏幕条数等同完整导出；失败与下载待取分开。
- **验收场景：**缺学生或用途不能导出；后台超时保留结果查询；不显示无权字段。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-06.png)；源码 `frontend/src/modules/academicAffairs/views/AaTranscriptView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:116`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-07 成绩异常

- **入口与归属：**`/admin/academic-affairs/grade-exception`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期与异常类型 → 学生/课程/异常说明/任课关系 → 原任务入口。
- **主次操作：**查询；查看异常对应任务；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留任课关系不等于当前审核人的边界，缩成列说明；学期由选择器提供。
- **验收场景：**缺考/缓考/免修/作弊分别显示；空结果只在成功读取后出现；跳转精确任务。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-07.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeExceptionView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:115`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-08 成绩认定与替代

- **入口与归属：**`/admin/academic-affairs/grade-recognition`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**申请队列 → 学生、原课程与目标课程对照 → 证明材料 → 审批历史/动作。
- **主次操作：**查看申请；按现有权限代录或审核；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**对照信息优先于流程介绍；课程版本与正式认定结果分开；未选申请不显示既成状态。
- **验收场景：**目标/原课程不能混用；驳回意见可回看；重复认定与版本冲突拒绝且保留输入。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-08.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeRecognitionView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:57`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-09 重修审批

- **入口与归属：**`/admin/academic-affairs/makeup?tab=retake`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**状态/学期 → 学生课程申请 → 来源成绩和版本证据 → 审核与编班结果。
- **主次操作：**当前节点审核；通过后进入现有编班；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**内部申请编号不作主标题；数据缺失提示改为来源成绩暂不可核对并给查询入口，不删除版本限制。
- **验收场景：**缺来源成绩版本不能审核/编班；批准与已编入分开；换申请不串意见。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-09.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:162`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-10 免修审批

- **入口与归属：**`/admin/academic-affairs/makeup?tab=exemption`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学生课程申请 → 材料有效性 → 申请理由 → 原审批结论 → 正式认定。
- **主次操作：**审核或查看驳回结果；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留材料失效/缺失警告，收起实现说明；审核结果与学分认定区分。
- **验收场景：**无有效材料拒绝办理；退回理由保留；不同学生材料不串；归档不改变结论。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-10.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:162`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-11 重修免修申请

- **入口与归属：**`/admin/academic-affairs/my-makeup`；独立业务入口。 当前结论：已截图无权状态；学生本人流程待验。
- **信息顺序：**本人身份检查 → 选择本人课程或挂科成绩 → 理由/材料 → 提交结果。
- **主次操作：**学生本人提交申请；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**管理员当前被拒时只呈现无权说明和返回，隐藏无效表单与虚假暂无申请；不得放宽权限。
- **验收场景：**管理员仍拒绝；学生仅本人课程；失败不同时显示空申请；切页保留明确草稿策略。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-11.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupStudentView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:163`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-12 统计分析

- **入口与归属：**`/admin/academic-affairs/makeup/stats`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期/学院/明细维度 → 四类业务各自数量与口径 → 对应明细。
- **主次操作：**查询；查看同范围明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**补考分数比例与重修免修审批比例不可混称通过率；明细与聚合采用同一已应用条件。
- **验收场景：**改筛选未查询时不改旧结果口径；零基数显示暂无基数；导出与筛选一致。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-12.png)；源码 `frontend/src/modules/academicAffairs/views/AaMakeupStatsView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:165`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-13 材料归档

- **入口与归属：**`/admin/academic-affairs/exemption/archive`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期/归档状态 → 学生课程申请 → 审批结论、材料有效性、归档状态。
- **主次操作：**核对材料；原条件满足后归档；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**学生名称和课程业务编码主显，内部编号折叠；已驳回与已归档是独立状态，不把归档当通过。
- **验收场景：**失效材料不能伪装有效；归档不改变审批结论；查询失败保持筛选。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-13.png)；源码 `frontend/src/modules/academicAffairs/views/AaExemptionArchiveView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:166`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-14 学院成绩审核

- **入口与归属：**`/admin/academic-affairs/grade-college-review`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**待审核任务队列 → 当前课程/教学班 → 名单和构成检查 → 意见/动作。
- **主次操作：**审核通过或退回；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**承接候选空态修复：无任务不出现右侧选择提示和无效分页；有任务才显示核对区。
- **验收场景：**缺审核依据拒绝；越界分页仍可返回；退回字数和撤权恢复保护保留。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-14.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:118`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-15 成绩发布

- **入口与归属：**`/admin/academic-affairs/grade-publish`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**待终审/已发布 → 当前任务 → 两列核对信息 → 发布结果与预警扫描。
- **主次操作：**发布；已发布任务查看/查询扫描结果；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**承接候选两列核对；页签不暗示人人有归档权；发布与预警扫描分别确认。
- **验收场景：**发布成功但扫描失败分别提示；缺名单/构成/任课关系不能发布；已发布不再重复发布。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-15.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradePublishView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:119`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-16 成绩更正

- **入口与归属：**`/admin/academic-affairs/grade-change`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**我发起/待办理/授权范围 → 状态 → 申请队列 → 原值新值、理由、当前节点、审批历史。
- **主次操作：**发起更正或办理当前节点；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**承接候选空态互斥；保留原值与新值同屏，删除实现自证说明；表单关闭不丢未知结果。
- **验收场景：**旧版本冲突保留意见；未确认结果禁重发；失败不显示暂无申请；发布后历史不可覆盖。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-16.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeChangeView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:120`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-17 成绩复查

- **入口与归属：**`/admin/academic-affairs/grade-recheck`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**状态筛选 → 学生课程申请与申请时间 → 原成绩、理由、处理结论。
- **主次操作：**查看申请并按权限处理；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**同学生同课程多条申请加时间和申请状态区分，不靠内部编号；未选对象不预设审核结果。
- **验收场景：**不同申请切换不串记录；维持原成绩与进入更正分开；已结案只读。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-17.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeRecheckView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:122`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 09-18 成绩操作审计

- **入口与归属：**`/admin/academic-affairs/grade-audit`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**对象类型/时间筛选 → 时间、中文动作、操作人/岗位 → 变更前后。
- **主次操作：**查看操作证据；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**岗位码映射中文；未知动作显示动作信息待核对而不是待确认业务状态；原始数据折叠为实施人员使用。
- **验收场景：**原审计文本不改写；变更前后值保留原义；未知事件不伪造状态；页码切换身份隔离。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/09-18.png)；源码 `frontend/src/modules/academicAffairs/views/AaGradeAuditView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:123`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

### 11．教材管理

#### 11-01 教材目录

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=catalog`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**名称/书号检索 → 教材名称/版次/出版社/课程分类/定价/状态。
- **主次操作：**新建或打开目录；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**类别枚举映射为中文，列名依当前数据改为课程分类；不谎称具体适用课程；主表不重复内部目录编号。
- **验收场景：**类别映射不改变原值；同名不同版次能区分；已引用目录仍受原停用保护。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-01.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-02 教材选用

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=selection`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期与状态 → 任务、课程教学班、教材版本、需求人数、状态 → 申报详情。
- **主次操作：**从教学任务申报；逐行修改或查看来源；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**去掉默认第一行对象概览和按页签固定的步骤1；列表直接办理，选中后只显示该记录真实状态。
- **验收场景：**已征订不标正在申报；需求人数按原规则；提交失败保留选用；返列表保留页码。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-02.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-03 审核备案

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=review`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**待办/历史 → 来源学院与批次 → 选用明细/审核证据 → 当前节点动作。
- **主次操作：**创建审核批次或办理已有批次；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**“审核选用申报”若实际创建批次应改为创建审核批次；已备案不显示当前仍在审核；责任缺失如实提示。
- **验收场景：**来源学院一致；备案不能自动跳征订；退回理由保持；未选对象无默认当前记录。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-03.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-04 征订到货

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=order`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**征订单/状态 → 征订明细与累计到货 → 发放名单入口。
- **主次操作：**生成征订；逐单登记到货或进入发放；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留到货前检查；列表无数量时明确查看明细，不虚构汇总；生成发放名单是打开表单，不暗中生成。
- **验收场景：**累计量更新保留防重；部分到货不冒充全到；从征订单到发放单保持关联。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-04.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-05 费用台账

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=fee`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学生/教材/发放来源 → 原应收、已收、减免、剩余与状态 → 收款记录。
- **主次操作：**核对记录；按原权限登记部分收款或减免；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**当前学生列是内部编号：有可信姓名学号则主显；接口未提供时列出补充读取依赖，禁止猜名；不改财务口径。
- **验收场景：**减免不计应收的原逻辑保留；重复收款拒绝；失败保留金额和原因；敏感范围不扩大。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-05.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-06 教材库存

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=stock`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**教材与版次 → 到货、待签收占用、已签收、可用库存 → 原流水。
- **主次操作：**刷新；查看对应流水；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留四种数量及负库存冲突警告；缩短重复来源说明，不用已签收代替已发放。
- **验收场景：**可用数仍按原口径；冲突值不归零伪装修复；跨教材查看不串流水。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-06.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 11-07 教材统计

- **入口与归属：**`/admin/academic-affairs/textbooks?tab=stats`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**本校范围/时间 → 选用审核记录数、征订到货册数、费用金额分组 → 明细入口。
- **主次操作：**查看对应业务明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**按单位拆开图表，不能把768条选用与40400册征订放同一完成比例图；无周趋势保留简明提示。
- **验收场景：**不同单位不混算；到货率分母分子可核对；下钻承接同范围；未提供趋势不造线图。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/11-07.png)；源码 `frontend/src/modules/academicAffairs/views/AaTextbookConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:168`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

### 13．教学质量

#### 13-01 质量看板

- **入口与归属：**`/admin/academic-affairs/quality`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**待处理/已逾期摘要 → 按期限排序的质量事项 → 指标与历史导出。
- **主次操作：**继续办理选中质量事项；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**即将到期当前实际统计已逾期，标题改为已逾期并保留原筛选；待我与范围内待办区分，不能仅凭管理员可见就称待我。
- **验收场景：**已逾期与将到期不同；无负责人显示待指定；指标失败与队列失败分别提示。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-01.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-02 督导听课

- **入口与归属：**`/admin/academic-affairs/quality?tab=supervision`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**记录列表及课程教师筛选 → 新增听课 → 课程、教师、听课时间、观察、结论、是否整改。
- **主次操作：**新增或查看听课记录；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**历史列表优先，新增表单按动作打开；折叠启动条件自证，保留必要字段；未选对象不显示已完成阶段。
- **验收场景：**课程教师关系由原校验控制；草稿切换提醒；从记录发起整改携带同一问题。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-02.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-03 巡课记录

- **入口与归属：**`/admin/academic-affairs/quality?tab=patrol`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**巡课记录列表 → 巡查人/日期/课次/地点 → 问题与建议 → 是否整改。
- **主次操作：**新增巡课；查看原记录；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**将完整表单默认展开改为显式新建状态，避免查历史须先滚过长表单；不删历史记录入口。
- **验收场景：**取消新建不清已有历史筛选；必填问题定位；不能把巡课记录当督导评价。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-03.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-04 教学检查

- **入口与归属：**`/admin/academic-affairs/quality?tab=inspection`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**检查记录 → 责任单位/时间/范围/项目 → 发现与结论 → 整改关联。
- **主次操作：**登记检查；从已确认问题发起整改；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**列表、筛选优先；新建与当前选中历史状态分开；技术启动条件收起。
- **验收场景：**记录确认和关闭按原状态；不同学院范围不扩大；退回保留意见。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-04.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-05 教学事故

- **入口与归属：**`/admin/academic-affairs/quality?tab=incident`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**事故记录列表 → 课程/教师/时间/摘要 → 情况材料/等级/处理意见 → 后续状态。
- **主次操作：**登记情况；查看与处理已有记录；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留不自动处罚的业务边界；新增表单显式打开；不自行提供事故等级默认值。
- **验收场景：**事故登记不等于处分决定；必填说明保留；关闭/取消不删除历史。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-05.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-06 质量整改

- **入口与归属：**`/admin/academic-affairs/quality?tab=rectify`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**状态筛选 → 待处理/处理中/已关闭看板 → 来源、责任、期限、下一动作。
- **主次操作：**从已确认问题生成整改；进入具体任务；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**来源类型用中文单独展示，不整段替换用户标题；无任务列用小空态，避免大返回框撑高看板。
- **验收场景：**新整改只能来自合法问题；逾期不改变审批状态；已关闭仍可查看复核证据。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-06.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-07 整改跟进

- **入口与归属：**`/admin/academic-affairs/quality?tab=followUp`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**未关闭任务队列 → 当前问题/责任/期限 → 中文进度时间线 → 提交复核。
- **主次操作：**追加进度；提交复核；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**时间线动作由原代码映射为领取/更新进度等；不要裸露RECEIVE/UPDATE；提交复核不等于关闭提示保留。
- **验收场景：**切任务不串进度；已关闭无写动作；复核退回后仍能继续；失败保留填写内容。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-07.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-08 质量归档

- **入口与归属：**`/admin/academic-affairs/quality?tab=archive`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期 → 已关闭问题/整改记录 → 来源、结论、关闭时间 → 封存证据。
- **主次操作：**查看封存证据；有权时导出；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**保留只读；类型标签中文化，原始标题不全局替换；两个导出入口明确对象避免重复含混。
- **验收场景：**未关闭不显示归档完成；不同数据类型不混计；历史字段原值可追溯。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-08.png)；源码 `frontend/src/modules/academicAffairs/views/AaQualityDashboardView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:176`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-09 评价批次

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=batches`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**批次名称/学期/状态 → 所选批次应评任务、评价窗口、结果 → 原生命周期动作。
- **主次操作：**创建批次；选中后生成任务/开放/核算/发布；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**取消未选批次固定处于步骤3的进度；将说明、摘要压缩，批次队列和待办优先。
- **验收场景：**未选择批次不声称前两步完成；已归档只读；任务来源与评价人校验保持。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-09.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-10 申诉审核

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=appeals`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**待办/历史队列 → 原评价结果、申诉理由 → 原节点处理意见 → 新结论。
- **主次操作：**办理当前申诉节点；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**无申诉时一处空态；原结果与意见分开展示；不把申诉结案直接覆盖旧结果。
- **验收场景：**原发布结果可追溯；撤权/版本冲突保留意见；不同申请不串材料。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-10.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-11 学生评教

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=studentEval`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**批次选择 → 课程/被评教师 → 应评数、已评数及任务状态。
- **主次操作：**查看完成情况；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**管理端只查完成情况，不显示评价者身份；保留一句匿名说明，删重复实现解释。
- **验收场景：**选批次不泄露学生身份；匿名小样本保护仍由原服务裁定；不提供代填入口。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-11.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-12 教师自评

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=selfEval`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**本人任务队列 → 课程/学期/被评对象 → 原问卷与证据 → 提交状态。
- **主次操作：**本人填写并提交自评；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**空任务一处提示；问卷未提交值在失败后保留；管理员无任务不当作教师流程验证。
- **验收场景：**只接受本人任务；切任务处理未保存输入；已提交不重复提交；评分项和权重不改。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-12.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-13 同行评价

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=peerEval`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**被分配的同行任务 → 课程/教师/听课依据 → 评价内容 → 提交结果。
- **主次操作：**办理本人被分配任务；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**与自评保持结构一致但明确被评教师；无任务不要求选择；不替代被评人自评。
- **验收场景：**未被分配仍拒绝；本人自评与同行任务不混用；错误保留证据。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-13.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-14 督导评价

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=supervisorEval`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**督导任务 → 教学对象及观察依据 → 问卷/意见 → 提交结果。
- **主次操作：**提交评价；需整改时导航到独立质量流程；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**评价与整改分开，提交评价不能显示整改已生成；保留现有任务分配范围。
- **验收场景：**未分配对象不能评价；已提交不重发；整改跳转携带明确来源且不自动写入。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-14.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-15 评价统计

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=evalStats`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**批次 → 参评口径/各来源完成率 → 等级分布与授权结果明细。
- **主次操作：**查询批次统计；查看同口径结果；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**参评率按评价类型拆开，等级与分数口径注明；不默认选择首条批次。
- **验收场景：**小样本隐藏不伪装0分；未发布结果不冒充正式成绩；列表总数与明细口径一致。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-15.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 13-16 评价归档

- **入口与归属：**`/admin/academic-affairs/evaluation?tab=archive`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**已归档批次 → 原结果及发布时间 → 申诉结束依据 → 历史查看。
- **主次操作：**查看归档批次和结果；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**去掉重复流程说明；保留原结果只读和受控纠错去向；编号仅在实施详情。
- **验收场景：**未发布草稿不归档；在途申诉不伪称已收口；历史结果不被新计算覆盖。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/13-16.png)；源码 `frontend/src/modules/academicAffairs/views/AaEvaluationConsoleView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:174`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

### 14．教务统计

#### 14-01 统计总览

- **入口与归属：**`/admin/academic-affairs/stats`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**总体指标、各业务分组、当前范围、更新时间。
- **主次操作：**指标明细与同口径下钻；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**没有连续快照不画趋势；指标名字可直接进入对应业务。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-01.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-02 学籍统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=statusChange`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**已生效异动数、异动类型、学院/学期。
- **主次操作：**已生效异动明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**毕业/入学/休学等类型中文映射；不把未生效申请混入。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-02.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-03 学籍与注册

- **入口与归属：**`/admin/academic-affairs/stats?tab=registration`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**应注册、已注册、未注册、完成率及分母。
- **主次操作：**未注册名单；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**人数/批次人次口径按服务返回说明，不能与学籍人数混称。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-17.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-04 开课与教学运行

- **入口与归属：**`/admin/academic-affairs/stats?tab=course`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**启用课程、分类、开课学院。
- **主次操作：**课程明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**分类筛选用业务选项；课程数、学院数不放同一比较坐标。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-04.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-05 教学任务统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=teachingTask`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**任务总数、未确认、确认率。
- **主次操作：**未确认任务明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**批次与单条任务口径区分；点击未确认继续到同任务。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-05.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-06 课表统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=schedule`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**课表批次、未解决冲突、发布覆盖。
- **主次操作：**冲突明细与课表批次；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**冲突条数与批次数不可画为同一构成；点击冲突定位安排。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-06.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-07 调停课统计

- **入口与归属：**`/admin/academic-affairs/schedule-change/stats`；独立业务入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**学期 → 调停课申请数量、完成比例 → 学院和教师分布。
- **主次操作：**查看同范围关联办理；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**页面归B组：C仅核对统计入口和返回条件；学期内部字段名及卡片挤压已反馈B组。
- **验收场景：**统计跳转后保留范围，返回恢复专题；不把调课频次当绩效结论。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-07.png)；源码 `frontend/src/modules/academicAffairs/views/AaScheduleChangeStatsView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:153`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-08 选课统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=courseSelection`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**批次容量、已选、低人数课程与填充比例。
- **主次操作：**选课明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**分子分母已有但比例缺失时核对字段契约，不擅自推定新口径。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-08.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-09 考试与成绩

- **入口与归属：**`/admin/academic-affairs/stats?tab=exam`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**应考课程、已编排、异常条数。
- **主次操作：**考务明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**编排完成不等于考试完成；异常进入对应考试课程。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-09.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-10 成绩统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=grade`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**有效成绩记录数、不及格成绩记录数、任务发布比例。
- **主次操作：**授权不及格明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**不及格按成绩记录计数，不称去重学生人数；保留原查询口径和任务发布率的独立分母。依据 `academic_affairs_stats_scale_guard.py:136–137` 按成绩记录计数、`academic_affairs_stats_service.py:1104–1105` 原样返回；同一学生两门不及格计2条，不能写2人。去重人数另列需求，不擅自改查询。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-18.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-11 学业与毕业

- **入口与归属：**`/admin/academic-affairs/stats?tab=warning`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**未关闭预警、风险等级、来源分布。
- **主次操作：**预警明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**预警条数不等于学生人数；返回保留等级/来源条件。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-11.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-12 毕业资格统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=graduation`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**预审批次、应审、待核或异常、通过比例。
- **主次操作：**资格异常明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**毕设/实习等异常项中文化；通过人数与异常项数量分开展示。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-12.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-13 师资与资源

- **入口与归属：**`/admin/academic-affairs/stats?tab=workload`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**授课教师、任务数、计划学时。
- **主次操作：**单教师授课明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**计划学时保留非绩效结算说明；不重复画无业务含义的构成图。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-13.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-14 教学资源统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=resource`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**资源类型、可用状态、待审预约。
- **主次操作：**资源明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**资源不随学期筛选；范围卡不能继续显示原学期范围；状态中文化。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-14.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-15 报表与快照

- **入口与归属：**`/admin/academic-affairs/stats?tab=export`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**导出维度、学期学院、实际范围与用途。
- **主次操作：**生成文件及结果查询；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**只说明本次真实导出范围；无已选对象功能时不放三种范围说明卡；不改用途字数与权限。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-15.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-16 统计快照

- **入口与归属：**`/admin/academic-affairs/stats?tab=snapshot`；同组件不同业务参数，必须保留本参数入口。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**快照类型、学期范围、冻结时间、完整性与查看入口。
- **主次操作：**查看详情/校验；权限允许时冻结；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**去掉重复标题和说明；摘要哈希放默认折叠实施详情；冻结动作需明确当前查询范围。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-16.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-17 注册统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=registration`；隐藏关联条目，与同地址页面共用设计和截图；不新增页面。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**应注册、已注册、未注册、完成率及分母。
- **主次操作：**未注册名单；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**人数/批次人次口径按服务返回说明，不能与学籍人数混称。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-17.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

#### 14-18 成绩统计

- **入口与归属：**`/admin/academic-affairs/stats?tab=grade`；隐藏关联条目，与同地址页面共用设计和截图；不新增页面。 当前结论：已截图首屏；设计待总控评审。
- **信息顺序：**有效成绩记录数、不及格成绩记录数、任务发布比例。
- **主次操作：**授权不及格明细；刷新、规则说明及历史查询作为次操作，危险操作按原权限和二次确认保留。
- **确定设计：**不及格按成绩记录计数，不称去重学生人数；保留原查询口径和任务发布率的独立分母。依据 `academic_affairs_stats_scale_guard.py:136–137` 按成绩记录计数、`academic_affairs_stats_service.py:1104–1105` 原样返回；同一学生两门不及格计2条，不能写2人。去重人数另列需求，不擅自改查询。
- **验收场景：**已应用筛选不被草稿筛选覆盖；同指标分子分母可回到原明细；跨角色不扩大返回范围；技术时间与不同单位不被转成同一图表数值。
- **证据：**[本轮页面截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/C/14-18.png)；源码 `frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1`；正式前端路由 `frontend/src/modules/academicAffairs/academic-affairs.routes.js:133`。深层状态与写入办理未验证，不能仅凭本截图宣布完成。

## 6. 关联详情、表单、弹窗与关键契约

以下是逐三级入口之外必须实施/复验的直接界面，已经按源码纳入设计；本轮没有冒充全部打开过。

| 关联界面 | 固定设计 | 源码定位 |
|---|---|---|
| 考务创建批次、批量圈课预览确认、课程安排、考场/座位、监考、巡考、异常和缓考意见 | 对象与范围摘要置顶；预览与确认分步；缺项定位具体课程/考场；批次换页不残留旧对象；发布后调整走原唯一入口 | AaExamConsoleView.vue:819、869、904、913、948、1022、1029、1087；academic-affairs.api.js:1152 |
| 考务打印已载入预览与重复打印原因 | 显示考试、场地、时间、名单人数和文书类型；只有原服务授权的正式数据能打印；重复打印保留原因与审计 | AaExamSeatingPrintView.vue:158、175、196、218 |
| 固定/动态成绩构成、录入任务、导入错误、成绩审核确认、发布结果 | 构成编辑与录分权限分离；错误定位到学生/分项；草稿、暂存、正式发布明确；不删回执恢复 | AaGradeEntryView.vue:470、481、717、749；academic-affairs.api.js:690–775；academic-affairs-r10.api.js:21–44；academic-file-exchange.api.js；grade-identity.api.js |
| 更正申请/审批详情、复查详情、认定原目标课程/材料 | 原结果与拟改结果对照；文件访问失败和材料无效分开；审批意见、版本和当前节点同时出现；未知写结果先核对 | AaGradeChangeView.vue、AaGradeRecheckView.vue、AaGradeRecognitionView.vue 的实际处理方法 |
| 补考批次、清考名单、来源成绩选择、缓考合流、重修编班、免修证据 | 所有对象从已有选择器选；禁止手工推造来源成绩；退出弹窗不丢待确认命令；原成绩身份及来源版本缺失则阻断 | AaMakeupConsoleView.vue:134、146、157、171、456、628、668、759 |
| 教材目录编辑、选用申报、审核批次、到货登记、部分收款、减免原因 | 表单清楚区分创建/编辑；累计到货数量与新增量口径沿原实现；金额和原因保留失败输入；默认首行不得作为隐藏写对象 | AaTextbookConsoleView.vue:165–216、425、426、445、564–576 |
| 教材发放名单生成、发放签收详情 | 必须从实际订单携带来源；候选名单→预览→确认；签收与费用状态分别展示，结果未知查询原命令 | academic-affairs.routes.js:169–170；AaTextbookDistributionGenerateView.vue；AaTextbookDistributionDetailView.vue |
| 质量记录详情、确认/撤销、来源问题选择、整改详情/时间线、进度/复核表单 | 已确认问题才能生成整改；责任和期限同屏；复核前后状态保留；历史只读不改原值；来源为空给可操作修复入口 | AaQualityDashboardView.vue:64–180及pendingWrite/verifyPendingWrite链 |
| 评价批次创建/任务生成、问卷、结果、申诉意见、归档详情 | 分清评价来源、评价人和被评对象；评分项与权重不变；匿名学生只显示汇总；已发布与修订结果分开 | AaEvaluationConsoleView.vue:424–502、597、664–760及对应写命令 |
| 统计下钻、导出结果、快照详情和完整性校验 | 下钻始终采用已应用条件；快照哈希等默认折叠“实施人员使用”；生成与下载结果分开；无权接口仍拒绝 | AaStatsOverviewView.vue:631–689、737、822、877；stats_core_router.py、stats_snapshot_router.py |

## 7. 前后端实际读取链与测试交接

| 业务 | 前端消费者与接口源 | 后端正式入口依据 | 后续验证重点 |
|---|---|---|---|
| 考务 | academic-affairs.api.js:1152；exam-convenience.api.js；AaExamConsole/SeatingPrint | academic_affairs_bundle.py:158先挂exam_core_router；exam_core_router.py:63–420；扩展异常收口另核对 | 发布前就绪、考场容量、座位与名单、监巡考冲突、缓考不同节点、只读打印条件 |
| 成绩/补重修 | academic-affairs.api.js:690–800、1197；academic-affairs-r10.api.js:21–44；parallel-c恢复工具 | bundle.py:24动态成绩扩展；现有成绩核心与读守卫安装链须在实施前按方法确认，不能把旧同名函数当正式入口 | 本人课程/本院范围、版本、未知结果恢复、导入原子性、发布更正不可变历史 |
| 教材 | academic-affairs.api.js:1245；textbook-p0.api.js | bundle.py:171–172教材核心；textbook_closure_router提供发放闭环扩展 | 任务来源、版本、到货/库存/发放数量关系、费用防重和部分成功 |
| 评价 | academic-affairs.api.js:1369 | bundle.py:169–170 evaluation_core_router；学生评教扩展独立挂载 | 本人/被分配对象、匿名小样本、权重、申诉与归档状态 |
| 质量 | academic-affairs.api.js:1401 | bundle.py:177起保留基础路由；routers/academic_affairs.py:4809、4901、4942等质量路由调用academic_affairs_quality_service（同文件49行导入）；program_quality_router是培养方案治理，不是教学质量入口 | 记录/整改来源、责任范围、版本、逾期展示与关闭复核 |
| 统计 | AaStatsOverviewView.vue；academic-affairs.api.js统计调用 | bundle.py:175–176 stats_core_router；stats_snapshot_router | 参数、单位、分子分母、缺失与零、个人明细边界、冻结范围、导出恢复 |

已定位可复用前端检查：`academic-pc-parallel-b-exam.test.mjs`、`academic-exam-design-workspace-contract.test.mjs`、`academic-exam-formal-print-source-contract.test.mjs`、`academic-grade-publish-receipt.test.mjs`、`academic-grade-action-receipt-contract.test.mjs`、`academic-pc-parallel-b-textbook.test.mjs`、`academic-pc-parallel-b-quality.test.mjs`、`academic-pc-evaluation-module.test.mjs`、`academic-stats-workspace-behavior.test.mjs`、`academic-stats-snapshot-behavior.test.mjs`。本轮不运行测试，不把定位到测试文件算通过。

## 8. 跨组归属、接口依赖与剩余证据

- C拥有考务/成绩共用的补重修控制台、教学评价/质量视图及统计共用页；B拥有调停课统计，C仅核对入口和口径。B学籍统计借用C统计页，必须保留原scope/来源返回条件。
- A提供教学任务、课程版本、学期/组织选择的现行字段与链接；C不得重新造教学任务或修改其确认状态。考试/成绩下钻返回A时带同一任务与来源。
- B提供有效注册/学籍对象、预警与毕业结果接收关系；C成绩发布不直接把学生改为毕业或关闭预警。评价有整改需求只导航原质量流程，不自动新建记录。
- 教材费用学生名称、考务打印级联选择、未知审计动作等若现有读取不能满足，列为精确字段/映射依赖；在接口契约核清前不写“已有”或绕过范围取数。
- 需要补充真实界面证据：挂科清单正常读取；学生本人重修免修申请；上述关联详情/弹窗的完整状态；教师/学院等岗位；手机指定宽度；候选设计图与修改后复验。
- 本次提交的是五模块内部流程、67入口的具体设计卡与真实首屏证据。不能将“首屏已看”称为所有业务状态审计完成，也不能称五模块已通过真实办理验收。总控应在全部15模块共同评审后决定设计冻结，再进入代码阶段。
