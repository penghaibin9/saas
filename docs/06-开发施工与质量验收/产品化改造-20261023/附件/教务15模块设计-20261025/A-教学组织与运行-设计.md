# A组：教学组织与运行——五模块流程与页面设计

> 设计版本：2026-10-25；依据主目录当前教务源码（main提交ff7786877对应教务目录无本地差异）。本文件是设计稿，不是已实施或业务验收报告。只写本文件及私有临时证据目录；未改业务代码、未提交推送、未启停服务、未写沙箱业务。

## 1. 覆盖与证据边界

A组负责教务基础27、培养与课程27、开课管理12、排课与课表22、选课管理7，共95个三级条目；地址去重86。隐含详情和抽屉另见第4节，不能用菜单条目数代替真实页面数。

本轮证据为A组23张＋总控R组65张，共88张（含2张课表/选课内容区补图）；95条入口按地址去重86个，已全部有本轮截图映射。这里的“覆盖”仅指所拍入口的正常首屏、初始选择空态、岗位拒绝或读取失败状态，不等于深层全状态审计通过，更不等于实际办理通过。班级调整批量记录正常态、学生本人选课正常态，以及选方案后模块/学分/实践/毕业要求等具体内容仍未核实。未实际提交、审核、发布、分配、生成或导出，手机宽度与写入恢复未全量实测。

使用Product Design（产品设计）的截图先行审计规则；真实看到的页面问题与仅由源码推导的设计建议分别标记。设计沿用ModulePageShell、AppSectionCard折叠、DataTable内部滚动和academicFlowContext返回/请求身份保护，不另建组件或缓存体系。

## 2. 共用页面与状态规范

- 队列页：标题及一个主要动作 → 学期/批次/状态/关键词筛选 → 列表及真实总数 → 分页。详情或办理区只在明确选择后出现。表格优先业务名称、版本、责任、状态，内部标识仅用于跳转。

- 编辑页：对象名称/版本/可编辑状态 → 业务字段分组 → 同屏字段错误 → 保存与取消。保留输入；已有未保存拦截必须保留，没有拦截的页面列为需补设计，不假定已有。结果未知时冻结原对象，只保留结果查询，不重复提交。

- 审核/发布页：待办队列 → 选中对象摘要 → 缺失/阻断证据 → 意见与唯一主要动作；空队列不要求选择不存在的对象。只按现有服务能力显示可办动作。

- 查询页：对象和时间范围固定；加载、失败、无权限、空结果分别展示。月份/周次切换不丢学期；列表进入详情后返回原筛选页码。跨模块走既有academicFlowContext，不自制地址缓存。

- 窄屏：筛选纵向满宽；关键按钮可触达；长表仅表格内部横滚、长名单限高滚动；不以裁切、隐藏关键字段解决溢出。375/390/430像素仍待实测。

- 无障碍：保留真实按钮/输入标签和错误关联，弹窗焦点回触发按钮，状态不只靠颜色；本轮不声明完整无障碍标准达标。

## 3. 五模块内部流程与逐入口设计卡

### A1 教务基础

**内部流程：**学期定义 → 当前学期治理 → 校历与节次 → 组织和班级核对 → 下游开课准备。

**保留边界：**当前激活沿既有两分支：统一治理学校走全校治理；非统一治理且服务明确允许直切、校级权限和读取状态均满足时保留原确认切换。不能删直切兼容能力，也不新增切换链；发布定义、当前学期、冻结、归档四种事实分开。

**统一布局：**学期/日期/周次/组织名称作为共同上下文；列表或月历为主体；重复权威来源和说明合入一处可展开帮助。

|条目|三级入口与地址|组件与证据|具体页面设计|本轮视觉证据|
|---|---|---|---|---|
|A1-01|学期管理<br>`/admin/academic-affairs/terms`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:23` → `AaTermListView.vue`|表格前置学期名称、起止日期、教学周数、定义状态和当前标记；主操作新建学期，行内打开详情；发布后统一激活入口只保留一处。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-02|学年管理<br>`/admin/academic-affairs/terms/years`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:32` → `AaAcademicYearView.vue`|按学年一行并列第一/第二学期、方案数与当前标记；缺学期显示未建立，主操作仍是新建学期，不另造学年编辑流程；隐藏状态后的内部编号。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\02.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-03|当前学期<br>`/admin/academic-affairs/terms/current`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:26` → `AaTermCurrentView.vue`|首屏显示当前学期、起止日期、周数和激活时间；保留两条既有路径：统一治理学校前往治理入口；非统一治理且服务明确返回 `canDirectSwitch=true`、校级维护权限具备、读取无错误时，对已发布候选保留“设为当前”及确认框。缺值、加载或失败不得放行；不新增其他切换路径。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\03.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-04|学期周次<br>`/admin/academic-affairs/terms/weeks`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:27` → `AaTermWeeksView.vue`|学期选择与月份切换同排，日历中显示日期和周次；主内容月历，配置入口为次操作；原周次来源与变更影响不重复占侧栏。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\04.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-05|教学周配置<br>`/admin/academic-affairs/terms/teaching-weeks`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:28` → `AaTeachingWeekConfigView.vue`|所选学期和锁定状态置顶；可编辑状态显示周数与影响预览，已发布状态只读且紧邻禁用按钮说明原因；不把解冻当恢复草稿。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\05.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-06|学期状态<br>`/admin/academic-affairs/terms/status`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:29` → `AaTermStatusView.vue`|直接呈现学期、定义状态、是否当前、课表引用、归档状态和当前可做动作；冻结/解冻原因放确认框，首屏删除重复权威说明卡。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\06.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-07|学期切换记录<br>`/admin/academic-affairs/terms/switch-log`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:33` → `AaTermSwitchLogView.vue`|按时间展示原学期→目标学期、操作岗位与原因，主动作查看目标学期；内部记录码默认折叠为实施详情，缺历史前序保留明确说明。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\07.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-08|学期归档<br>`/admin/academic-affairs/terms/archive-status`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:30` → `AaTermArchiveView.vue`|学期、封存状态、版本、封存时间、缺失域数作为主列；查看归档依据为行操作；批次编号与摘要移入详情，不新增封存按钮。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\08.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-09|校历管理<br>`/admin/academic-affairs/calendar`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|学期选择→简短锁定提示→事件月历和事件列表；主动作仅可编辑时新增事件；当前学期提示与发布限制合并，重复右栏说明默认折叠。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\09.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-10|作息时间<br>`/admin/academic-affairs/time-slots`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:36` → `AaTimeSlotView.vue`|列为节次、开始/结束、适用时间段、引用状态、启停状态、行操作；新增节次为主，模板导入折叠；引用阻断在变更确认处保持可见。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\10.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-11|节假日配置<br>`/admin/academic-affairs/calendar?tab=holiday`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|所选学期、起止日期、节假日名称为主信息；可编辑时新增假日，已发布仅查看；空态只说明本学期无记录，保留调休配对入口。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\11.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-12|补课日配置<br>`/admin/academic-affairs/calendar?tab=makeup`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|原教学日与补课日成对展示并标记未配对；主动作新增/修正配对，确认时重复显示两日期；不得把补课日普通事件化而丢掉配对。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\12.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-13|节次管理<br>`/admin/academic-affairs/time-slots`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:36` → `AaTimeSlotView.vue`|复用作息时间同页同数据；由入口身份恢复节次管理标题，高亮一致；不新增第二套节次维护。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\10.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-14|上课时间段<br>`/admin/academic-affairs/time-slots?tab=bands`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:36` → `AaTimeSlotView.vue`|先选节次，再显示校区、生效起止、开始结束时间及状态；新增/编辑只作用于所选节次；切节次关闭旧编辑并保护未保存输入。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\13.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-15|教学周日历<br>`/admin/academic-affairs/calendar?tab=weekCalendar`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|默认所选学期月历，突出日期对应教学周与调休日；跳到课表需携带学期和周次；无课表不等于无教学周。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\14.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-16|校历发布<br>`/admin/academic-affairs/calendar?tab=publish`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|所选学期摘要＋待处理项列表＋唯一发布入口；每项缺失可定位到节次/调休事件，发布前确认对象；原结果待确认锁定和查询恢复保留。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\15.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-17|校历归档<br>`/admin/academic-affairs/calendar?tab=archive`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:35` → `AaCalendarView.vue`|选择归档学期后显示其采用的事件、日期、版本；仅查看历史，跳回当前校历时保留原学期上下文，不允许编辑归档快照。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\16.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-18|学院管理<br>`/admin/academic-affairs/orgs?tab=college`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|学院名称/编码、负责人或秘书绑定、状态和行操作；新建/编辑抽屉复用；秘书绑定单独呈现人员、范围、有效期核对，不与学院表单混合提交。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\17.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-19|专业管理<br>`/admin/academic-affairs/orgs?tab=major`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|学院筛选置前；专业名称/代码、学制、培养层次、招生状态为主列；编辑保留学院归属；缺学院先明确阻断。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\18.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-20|年级管理<br>`/admin/academic-affairs/orgs?tab=grade`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|专业筛选→年级、预计毕业年度、专业数、班级数、学生数；长专业列表默认前两项加数量，可展开全部；保持派生年级来源，不另造创建流程。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\19.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-21|行政班管理<br>`/admin/academic-affairs/orgs?tab=class`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|专业、年级筛选→班级/人数/状态；查看学生、编辑、调整动作分层；已有关联学生或任务时保留删除阻断，不将删班作为常用操作。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\20.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-22|教学班管理<br>`/admin/academic-affairs/orgs?tab=teaching`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|按学期查询课程、教师、教学班、人数和来源任务；主动作查看名单/来源任务；教学安排维护回原任务，不能在此平行改派教师。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\21.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-23|组织核对<br>`/admin/academic-affairs/orgs?tab=tree`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|保留当前引用影响表，按组织/学院/名称筛选；列在籍学生、未归档任务、生效方案及核对结论；查看核对定位影响，未知与零数量区分。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\22.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-24|组织统计<br>`/admin/academic-affairs/orgs?tab=stats`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|按学院/专业展现组织与人数口径；保留统计时点及可见范围；下钻回对应已过滤列表，返回恢复原筛选。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\23.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-25|专业方向<br>`/admin/academic-affairs/orgs?tab=direction`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|先显示是否启用方向管理，再选专业维护方向名称/代码/状态；停用需展示已有引用影响；关闭能力时不假造空列表。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-26|班级学生<br>`/admin/academic-affairs/orgs?tab=students`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|必选行政班后显示姓名、学号与状态；行内查看档案/已有转班入口；选班变化清旧名单与旧抽屉，返回保留班级页码。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补02.png`；本轮所拍状态已查看；深层/写入状态另验|
|A1-27|班级调整<br>`/admin/academic-affairs/orgs?tab=adjust`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|单学生调整与班级层级调整分区呈现；保留源/目标班、人数、状态、预检及原确认。当前批量记录区实际读取失败，先保留错误与重试，不显示为空或正常结果；失败原因待接口链核对，不能按截图猜修。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补03.png`；读取失败已截图；正常批量列表未核实|


**本模块验收场景：**同对象正常读取；筛选无匹配；接口失败不报空；无权限不露办理动作；切换学期/批次旧响应不覆盖；进入详情再返回原筛选。涉及写操作的页面另验证必填、重复提交、结果未知恢复、版本冲突保留输入，测试不得修改现行业务规则。

### A2 培养与课程

> 2026-10-27 专项复审：[真实页面审计与简化设计](../培养与课程真实页面审计-20261027/审计与简化设计.md)。新增本轮 13 张页面与交互证据，确认发布/变更阶段误导、绑定动作命名、搜索空态和未修改离开提示；提出同方案集中办理与入口收拢方案。该附件为待实施设计，不表示既有页面已完成改造或业务验收。

**内部流程：**课程版本维护 → 方案编制 → 质量校验 → 原学院/教务审核 → 适用年级绑定与发布 → 开课引用。

**保留边界：**现有版本和审核节点不改；课程停用及删除引用保护不改；成绩构成设置不与课程考核方式混同。

**统一布局：**选中方案/课程名称与版本固定在内容头，主体为结构或证据，阻断项紧邻操作；摘要不重复内部编号。

|条目|三级入口与地址|组件与证据|具体页面设计|本轮视觉证据|
|---|---|---|---|---|
|A2-01|方案列表<br>`/admin/academic-affairs/programs`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:83` → `AaProgramListView.vue`|突出名称、专业年级、版本、状态和质量阻断；主操作新建方案，导入次要；行内打开原方案，不用内部编号表达身份。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补04.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-02|方案制定<br>`/admin/academic-affairs/programs/console?tab=authoring`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|本轮草稿列表和继续编制入口简洁，保留主要结构；只压缩空工具容器或重复说明。选定方案后进入现有编辑器，保留退回原因与对象上下文。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补05.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-03|方案版本<br>`/admin/academic-affairs/programs/console?tab=versions`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|同专业年级按版本排序，标明当前启用/历史状态；查看版本为常用动作，新版本为次要确认动作；保留原版本只读。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补06.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-04|课程模块<br>`/admin/academic-affairs/programs/console?tab=courseModules`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|选方案后列课程名称/版本、模块、学期、学分与学时；添加和编辑聚焦行，合计位于表尾；课程身份必须来自课程库。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补07.png`；选方案前空态已截图；具体条目未核实|
|A2-05|学分要求<br>`/admin/academic-affairs/programs/console?tab=creditRequirements`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|按模块列目标学分、已编学分和差额；编辑后只有一个保存结构入口，未保存提示留在本区；零值与未设置区别展示。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补08.png`；选方案前空态已截图；具体条目未核实|
|A2-06|实践环节<br>`/admin/academic-affairs/programs/console?tab=practiceSegments`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|列环节名称、学期、周数/学分、关联要求；新增/编辑用同一抽屉；实践课程与实践环节关系说明仅在相关字段旁显示。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补09.png`；选方案前空态已截图；具体条目未核实|
|A2-07|毕业要求<br>`/admin/academic-affairs/programs/console?tab=graduationRequirements`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|按要求类别列阈值/内容、引用与校验状态；编辑以现有规则字段为准，禁止自行补默认毕业门槛；保存失败保留整条输入。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补10.png`；选方案前空态已截图；具体条目未核实|
|A2-08|方案审核<br>`/admin/academic-affairs/programs/console?tab=review`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|待审队列＋选中方案证据＋意见区；通过/退回只对当前可受理节点显示；阻断项点击定位原方案，返回保留队列筛选。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补11.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-09|方案发布<br>`/admin/academic-affairs/programs/console?tab=publish`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|已启用对象不再因所在页签而固定显示当前发布阶段；根据真实版本状态、绑定范围和既有可执行条件决定主动作及文案。保留合法的新范围绑定/发布，不仅凭已启用就禁用全部能力；先核实专业年级范围，避免重复发布同一事实。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补12.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-10|方案变更<br>`/admin/academic-affairs/programs/console?tab=changeStatus`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|先选已发布版本，再输入原因并确认新旧版本关系；历史不直接编辑；结果显示新版本并提供继续编制入口。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补13.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-11|方案归档<br>`/admin/academic-affairs/programs/console?tab=archive`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|列表突出版本、启用范围、归档状态与只读查看；不展示无权限操作；历史版本不得回到可编辑表单。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补14.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-12|课程列表<br>`/admin/academic-affairs/courses`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:77` → `AaCourseListView.vue`|课程名称/业务代码/版本/性质/学分学时/状态为主列；新建为主、导入次要；课程档案返回保持名称搜索和页码。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补15.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-13|新增课程<br>`/admin/academic-affairs/courses/new`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:78` → `AaCourseFormView.vue`|字段分基本信息、学分学时、负责人范围、材料四组；顶部和底部各一主保存入口，底部不出现重复保存按钮；编码、学时和权限校验保持。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补16.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-14|课程分类<br>`/admin/academic-affairs/courses/console?tab=category`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|按分类过滤课程，显示当前分类及版本；调整类别抽屉锁定所选课程；已启用版本采用原版本变更约束。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补17.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-15|课程性质<br>`/admin/academic-affairs/courses/console?tab=nature`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|按必修/选修等业务性质过滤；调整后显示新性质并保留课程版本；未知值显示待确认，不暴露枚举。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补18.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-16|学分学时<br>`/admin/academic-affairs/courses/console?tab=credit`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|课程行显示总学分、总学时、理论/实践等分项；抽屉实时显示分项合计；原合计校验失败定位字段并保留输入。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补19.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-17|课程大纲<br>`/admin/academic-affairs/courses/console?tab=outline`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|列表保留课程版本与管理大纲入口；目前列表不能判断齐全程度。仅已有可信材料状态来源时补“已登记/待补齐”等准确状态，缺来源标为依赖，不按无返回推断无材料，不逐行额外请求形成大量查询。查看/上传/安全流程保持。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补20.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-18|考核方式<br>`/admin/academic-affairs/courses/console?tab=assessment`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|显示课程当前考核方式及版本，修改抽屉只编辑该维度；不能把考核方式与成绩构成权重混为同一设置。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补21.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-19|课程负责人<br>`/admin/academic-affairs/courses/console?tab=owner`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|课程与所属学院、当前负责人同排；指定/更换先核对人和范围；未分配突出为待办理，不显示无用身份编号。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补22.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-20|课程材料<br>`/admin/academic-affairs/courses/console?tab=material`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|列表保留课程与管理材料入口；齐全状态必须有可信材料规则与返回依据才补，缺来源不造默认完成标记。详情仍按类型列文件/时间/状态，新增登记、上传、作废分开，原安全和历史保留机制不变。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补23.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-21|课程停用<br>`/admin/academic-affairs/courses/console?tab=disable`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|列表展示启用状态与引用情况；停用前看被哪些方案使用，原后端引用阻断不变；停用成功回当前过滤队列。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补24.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-22|历史课程（已停用/旧版本）<br>`/admin/academic-affairs/courses/console?tab=archive`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:80` → `AaCourseConsoleView.vue`|按课程代码及完整版本关系判定历史，保留当前版/停用区别。历史筛选0条时显示“暂无历史或停用版本”，不能说课程库为空或引导新建；筛选无匹配、整个课程库空、读取失败分别显示。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补25.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-23|专业教学计划（关联）<br>`/admin/academic-affairs/programs`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:83` → `AaProgramListView.vue`|原方案列表的关联入口；保留来源标题与筛选，结果返回同一方案，不创建平行计划数据。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补04.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-24|实践教学计划<br>`/admin/academic-affairs/programs/console?tab=practicePlan`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|方案下只显示实践课程、目标实践学分与差额；添加课程进入原方案结构；不能另存一份实践课程副本。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补26.png`；选方案前空态已截图；具体条目未核实|
|A2-25|计划审核（关联）<br>`/admin/academic-affairs/programs/console?tab=review`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|复用方案审核页；入口标题与来源保持，权限和受理节点与方案审核一致。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补11.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-26|计划发布（关联）<br>`/admin/academic-affairs/programs/console?tab=publish`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|复用方案发布页并采用同一真实动作判断；已启用对象不固定处于待发布阶段，同版本同绑定不重复发布，仍保留现有合法新范围绑定能力。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补12.png`；本轮所拍状态已查看；深层/写入状态另验|
|A2-27|计划变更<br>`/admin/academic-affairs/programs/console?tab=planChange`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:85` → `AaProgramConsoleView.vue`|按方案版本展示变更原因与历史，进入原版本变更流程；不新增独立计划状态机。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补27.png`；本轮所拍状态已查看；深层/写入状态另验|


**本模块验收场景：**同对象正常读取；筛选无匹配；接口失败不报空；无权限不露办理动作；切换学期/批次旧响应不覆盖；进入详情再返回原筛选。涉及写操作的页面另验证必填、重复提交、结果未知恢复、版本冲突保留输入，测试不得修改现行业务规则。

### A3 开课管理

**内部流程：**已发布方案 → 生成任务 → 分配教师 → 教师本人确认 → 学院核对 → 教务终审 → 可排课。

**保留边界：**以上为当前代码链：AaTaskDetailView:412、424和AaTeacherTaskConfirmView:30等。文档2目标顺序如有差异只登记，不擅自迁移状态。

**统一布局：**队列优先、选中后显示详情；批次进度基于真实工作区，主操作由当前状态和责任决定；不把列表首条当选中对象。

|条目|三级入口与地址|组件与证据|具体页面设计|本轮视觉证据|
|---|---|---|---|---|
|A3-01|教学任务批次<br>`/admin/academic-affairs/teaching-tasks`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:88` → `AaTaskBatchListView.vue`|学期/状态/名称筛选一排，表格列批次、任务数、分配与确认进度、阻断、下一步；摘要仅保留总数及当前页口径。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补28.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-02|教学任务生成<br>`/admin/academic-affairs/teaching-tasks?open=generate`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:88` → `AaTaskBatchListView.vue`|从批次页打开原生成面板；先学期、方案/范围，再显示可生成性与重复任务阻断；只保留一次确认生成，不默认跨范围。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补29.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-03|任课教师分配<br>`/admin/academic-affairs/teaching-tasks/assign`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:89` → `AaTeacherAssignConsoleView.vue`|按批次/状态列课程、教学班、教师、周学时、人数；操作贴近任务行；去掉默认首行概览，确认框锁定原任务和教师。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补30.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-04|教学班生成<br>`/admin/academic-affairs/orgs?tab=teaching`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:136` → `AaOrgConsole.vue`|复用组织控制台的教学班管理，显示来自任务的班级；实际生成入口追到原任务流程，不新增第二个生成人工入口。|A组截图 `C:\Users\10850\AppData\Local\Temp\academic-design15-20261025\A\21.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-05|合班拆班<br>`/admin/academic-affairs/teaching-tasks/merge-split`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:90` → `AaTaskMergeSplitView.vue`|选择区显示同批次同版本、教师确认前条件；已选课程/班级/人数在确认框对照；不同对象不混选，拆班恢复原任务事实。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补31.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-06|教学任务确认<br>`/admin/academic-affairs/teaching-tasks/confirm`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:91` → `AaTaskConfirmView.vue`|先显示批次及真实状态，选中后才显示任务工作区和可办动作；未选批次不显示固定学院阶段。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补32.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-07|教师任务确认<br>`/admin/academic-affairs/teaching-tasks/teacher-confirm`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:92` → `AaTeacherTaskConfirmView.vue`|默认本人当前学期待确认任务，已确认/退回/就绪作为筛选；确认前核对课程班级周次人数；管理身份不能代替任课教师。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补33.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-08|教学任务调整<br>`/admin/academic-affairs/teaching-tasks/adjust`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:94` → `AaTaskAdjustView.vue`|列表先于说明；规则折叠但更换教师须本人确认、已审核须重办等限制不丢；确认框突出调整前后差异与原因。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补34.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-09|教学任务统计<br>`/admin/academic-affairs/teaching-tasks/stats`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:95` → `AaTaskStatsView.vue`|学期/学院范围与任务状态分布同屏，已分配与本人确认分别计数；下钻回对应任务筛选，不把两个完成率混用。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补35.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-10|学期开课计划（关联）<br>`/admin/academic-affairs/teaching-tasks`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:88` → `AaTaskBatchListView.vue`|复用教学任务批次，保留原查询身份；已发布方案对应的开课结果可追溯，不增加另一套计划录入。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补28.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-11|计划执行进度（关联）<br>`/admin/academic-affairs/teaching-tasks/stats`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:95` → `AaTaskStatsView.vue`|复用任务统计，按原口径显示分配/确认/审核；阶段来源为真实任务状态，不用固定进度条。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补35.png`；本轮所拍状态已查看；深层/写入状态另验|
|A3-12|工作量申报审核<br>`/admin/academic-affairs/workload-review`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:134` → `AaWorkloadReviewView.vue`|先展示学期/状态筛选和申报审核台账，去掉固定统计步骤与重复对象说明；保留教师、申报量、状态、原审核责任与意见，未知量不填0。通过仍仅表示申报审核结果，不暗示授课关系、名单或薪酬已核验。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补36.png`；本轮所拍状态已查看；深层/写入状态另验|


**本模块验收场景：**同对象正常读取；筛选无匹配；接口失败不报空；无权限不露办理动作；切换学期/批次旧响应不覆盖；进入详情再返回原筛选。涉及写操作的页面另验证必填、重复提交、结果未知恢复、版本冲突保留输入，测试不得修改现行业务规则。

### A4 排课与课表

**内部流程：**已就绪任务＋校历/节次/资源 → 选择批次 → 检查约束 → 手工/自动编排 → 冲突处理 → 预发布/发布 → 多视图查询 → 纠错/归档。

**保留边界：**保护原草稿/预发布/正式版本及纠错规则；条件检查与正式写入分开；资源占用为空不等于承诺可用。

**统一布局：**全程保留学期、批次、版本、范围；待排任务与课位为主体，冲突项可定位；流程说明仅保留当前阻断与下一步。

|条目|三级入口与地址|组件与证据|具体页面设计|本轮视觉证据|
|---|---|---|---|---|
|A4-01|课表批次<br>`/admin/academic-affairs/schedule`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:97` → `AaScheduleBatchListView.vue`|学期/学院/状态筛选后列批次、版本、覆盖与阻断；草稿进入编排，已发布查看版本；创建、作废重发与归档不要混作主操作。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-02|班级课表<br>`/admin/academic-affairs/schedule/class`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:101` → `AaClassScheduleView.vue`|学期＋行政班＋周次为最小筛选；课程格显示课程/教师/教室和调停标记；无发布课表独立空态。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-02.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-03|教师课表<br>`/admin/academic-affairs/schedule/teacher`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:102` → `AaTeacherScheduleView.vue`|默认本人或明确选择教师，显示课程/班级/教室；切教师清除旧课表，请求迟到不能覆盖新选择。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-03.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-04|学生课表<br>`/admin/academic-affairs/schedule/student`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:105` → `AaStudentScheduleView.vue`|先选授权学生，按已发布安排显示课程/教师/教室；学号姓名用于确认对象，不展示他人范围；无学生不默认首条。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-04.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-05|教室课表<br>`/admin/academic-affairs/schedule/room`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:103` → `AaRoomScheduleView.vue`|校区/教室/周次筛选，课程格显示课程教师班级；占用与可预约不混为可用承诺。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-05.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-06|教学班课表<br>`/admin/academic-affairs/schedule/teaching-class`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:106` → `AaTeachingClassScheduleView.vue`|选教学班而非行政班，显示跨班组班安排；返回来源任务时保留学期/批次。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-06.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-07|周课表<br>`/admin/academic-affairs/schedule/week`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:107` → `AaWeekScheduleView.vue`|学期、周次置顶，周次前后切换有界；日期与教学周一致，异常/调停信息就近展示。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-07.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-08|学期课表<br>`/admin/academic-affairs/schedule/semester`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:108` → `AaSemesterScheduleView.vue`|学期与对象筛选明确，长周期按周次范围展示；不将整学期所有格子硬挤到单屏，保留原筛选查询。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-08.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-09|课表发布<br>`/admin/academic-affairs/schedule/publish`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:109` → `AaSchedulePublishView.vue`|候选批次队列＋发布条件＋所选版本摘要；队列没有选中对象时不显示固定发布阶段；选中后按真实版本状态显示预发布/正式发布，未知结果只查原结果。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-09.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-10|课表调整记录<br>`/admin/academic-affairs/schedule/adjustments`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:110` → `AaScheduleAdjustmentLogView.vue`|按日期显示原课位→新课位、原因、操作人和版本；查看记录回对应批次；内部命令码默认折叠。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-10.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-11|课表导出<br>`/admin/academic-affairs/schedule/export`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:111` → `AaScheduleExportView.vue`|先显示学期、版本、对象和范围选择；未选择时不呈现发布阶段或责任占位；按钮文案随范围，保留原授权，不扩大教师/学生数据。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-11.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-12|排课规则<br>`/admin/academic-affairs/scheduling?tab=rules`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|保留学期级规则无需先选批次；显示可信业务名称、作用范围、当前值、版本/状态。名称从已有返回或同键规则目录取得，值按真实类型和单位显示；未返回与未设置分开，不猜默认值。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-12.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-13|教师可用时间<br>`/admin/academic-affairs/scheduling?tab=availability`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|先选学期和教师，显示日期/节次及申报审核状态；移除无批次的固定第2阶段和责任占位；保留采纳状态/原因，未申报不视为全天可用。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-13.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-14|自动排课<br>`/admin/academic-affairs/scheduling?tab=auto`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|批次选择前置，只保留一个检查条件入口；未选批次不显示固定第3阶段；取得工作区后按真实条件检查→方案/冲突→确认落地，检查不直接执行。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-14.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-15|冲突报告<br>`/admin/academic-affairs/scheduling?tab=conflict`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|先选批次，读取后按教师/班级/教室/时间分类显示双方；统一只读动作名为查询冲突，处理入口贴近具体冲突；不预设第4阶段，失败不显示0冲突。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-15.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-16|手工排课（关联）<br>`/admin/academic-affairs/schedule`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:97` → `AaScheduleBatchListView.vue`|复用课表批次入口并进入具体草稿编辑；先明确批次版本，布局以课位与待排任务为主，重复状态说明折叠。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-17|排课约束<br>`/admin/academic-affairs/scheduling?tab=constraint`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|复用规则组件，标题区分约束；作用范围、优先级、版本一致，不能维护两套相互覆盖规则。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-17.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-18|教室可用时间<br>`/admin/academic-affairs/scheduling?tab=room`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|内嵌资源占用使用紧凑内容，保留单一页面标题；资源显示可信场地名称，无名显示信息待核对而非内部编号；缺场地关联警告和最终冲突检查完整保留，无记录不承诺空闲。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-18.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-19|自动排课预留<br>`/admin/academic-affairs/scheduling?tab=import`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|实际地址为导入，目标标题统一为“排课结果导入”；保留选批次→上传预校验→确认，未选对象不显示固定冲突阶段；总控同步标题/导航契约，不冒充自动排课或新增入口。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-19.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-20|排课结果<br>`/admin/academic-affairs/scheduling?tab=result`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|仅选定批次并读取后显示版本、覆盖与真实状态；未选时只保留选择提示，删除固定处理冲突阶段和重复指定批次标题；未发布不标正式。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-20.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-21|排课调整<br>`/admin/academic-affairs/scheduling?tab=adjust`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:172` → `AaSchedulingConsoleView.vue`|未选批次仅展示选择器；选定后按草稿/已发布/允许纠错显示动作，不固定处理冲突进度。草稿进入编排，已发布走有原因的纠错草稿，不直接改正式课表。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-21.png`；本轮所拍状态已查看；深层/写入状态另验|
|A4-22|排课归档<br>`/admin/academic-affairs/schedule?panel=archive`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:97` → `AaScheduleBatchListView.vue`|`panel=archive` 仅显示已归档批次，保留只读查看和版本信息；不加入可归档批次。可归档动作仍在普通课表批次列表，继续按既有条件及确认执行。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-22.png`；本轮所拍状态已查看；深层/写入状态另验|


**本模块验收场景：**同对象正常读取；筛选无匹配；接口失败不报空；无权限不露办理动作；切换学期/批次旧响应不覆盖；进入详情再返回原筛选。涉及写操作的页面另验证必填、重复提交、结果未知恢复、版本冲突保留输入，测试不得修改现行业务规则。

### A5 选课管理

**内部流程：**批次草稿 → 配置课程/规则/轮次 → 发布 → 开选 → 截止 → 低人数处置/补选 → 锁定名单 → 归档。

**保留边界：**沿既有状态表和_NEXT；抽签报名/中签/未中签/锁定分开，批次时间处理是写命令，不在只读审计中执行。

**统一布局：**当前批次与窗口常驻；课程余量和不可办原因贴近动作；管理员配置与学生选退记录分开，结果未知提供查询恢复。

|条目|三级入口与地址|组件与证据|具体页面设计|本轮视觉证据|
|---|---|---|---|---|
|A5-01|选课批次<br>`/admin/academic-affairs/selection`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:156` → `AaSelectionConsoleView.vue`|5张批次大卡改为紧凑队列/选择器，选中摘要只保留学期/窗口/批次状态/下一步，课程供给和名单前置。窗口截止与批次待收口分别显示；批量开选/截止保留明确范围确认，不自动运行。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A5-02|本人选课<br>`/admin/academic-affairs/my-selection`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:157` → `AaSelectionStudentView.vue`|管理员收到明确拒绝时显示“当前岗位不适用，请使用本人学生入口”，不标读取失败、不扩大权限。学生正常态按批次展示课程教师学分时间余量和原因，选退预检/确认保留；学生态本轮未实测。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-02.png`；管理员岗位拒绝已截图；学生正常态未核实|
|A5-03|选课规则<br>`/admin/academic-affairs/selection?tab=rule`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:156` → `AaSelectionConsoleView.vue`|所选批次和真实规则版本置顶；草稿可编辑时保留原输入，开选后显示静态“累计选课学分上限”及值，替代全宽禁用步进器和无意义保存按钮。0仍表示不设批次级上限，系统校验及正式变更规则保留。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-03.png`；本轮所拍状态已查看；深层/写入状态另验|
|A5-04|补选管理<br>`/admin/academic-affairs/selection?tab=reselect`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:156` → `AaSelectionConsoleView.vue`|压缩批次卡与重复流程；仅批次正式状态为 `CLOSED` 时读取补选指引。窗口到期但批次未截止时，保留阻断和原批次收口入口，不自动收口。原记录与替代记录只有正式关联存在才显示前后课程及完成结论；缺关联明确待核对，不按余量或另选课程推断，不新增管理员代选/调整命令。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-04.png`；本轮所拍状态已查看；深层/写入状态另验|
|A5-05|冲突检测<br>`/admin/academic-affairs/selection?tab=conflict`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:156` → `AaSelectionConsoleView.vue`|当前查询完成且0条时只显示一处简明空态，不再同时显示空明细表与第1页分页；有记录显示课程/时间/原因和分页；越界页保留返回前页。失败与未查询不显示无冲突，最终提交仍重新校验。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-05.png`；本轮所拍状态已查看；深层/写入状态另验|
|A5-06|选课结果<br>`/admin/academic-affairs/schedule`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:97` → `AaScheduleBatchListView.vue`|当前入口复用课表批次，需设计为先明确“查看已发布课表/选课名单”的业务目的；不新增无后端结果的页面，核对来源批次到对应课表关系。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-01.png`；本轮所拍状态已查看；深层/写入状态另验|
|A5-07|选课归档<br>`/admin/academic-affairs/selection/archive`|`frontend/src/modules/academicAffairs/academic-affairs.routes.js:158` → `AaSelectionArchiveView.vue`|按批次名称、可信学期名称、格式化锁定时间、人数和归档状态显示；移除学期编号回退，缺名明示不可用，不改原时间值。选中行与详情同步高亮；保留封存只读和导出用途/权限限制。|总控R截图 `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-07.png`；本轮所拍状态已查看；深层/写入状态另验|


**本模块验收场景：**同对象正常读取；筛选无匹配；接口失败不报空；无权限不露办理动作；切换学期/批次旧响应不覆盖；进入详情再返回原筛选。涉及写操作的页面另验证必填、重复提交、结果未知恢复、版本冲突保留输入，测试不得修改现行业务规则。


## 4. 关联详情、抽屉和直接消费者

|归属|必须补查的表面|具体设计与保留要求|源码证据|
|---|---|---|---|
|教务基础|学期新建/详情/周次影响预览；冻结确认、解冻抽屉；归档证据抽屉|学期不可变身份与草稿编辑范围清楚；预览不等于执行；冻结/解冻显示对象及原因|AaTermCurrentView.vue:209；AaTeachingWeekConfigView.vue:194；AaTermStatusView.vue:70；AaTermArchiveView.vue:45|
|教务基础|校历新增编辑、删除确认、发布确认；节次/时间段新增编辑删除|日期或时段对照；发布条件缺项可定位；结果未知不能重发|AaCalendarView.vue:69、199、226、729；AaTimeSlotView.vue:29、173、190、206|
|教务基础|组织新建编辑、秘书绑定、班级学生、转班、方向、班级调整预检与结果|对象和范围固定；人员绑定与组织编辑独立；预检→执行顺序保留，部分完成逐项展示|AaOrgConsole.vue:323、356、388、410、455、480、506|
|培养与课程|方案编辑器四业务区；新建方案、添加课程/模块学分/实践/毕业要求、绑定、变更记录|对象头只保留名称年级版本；方案校验位置可定位；未通过不开放后续动作；不清用户输入|AaProgramConsoleView.vue:224、239、255、269、285、299、310、329；AaProgramEditorView.vue|
|培养与课程|课程档案/编辑；维度、学分学时、负责人、材料抽屉与作废确认|同一课程版本贯穿；材料上传/登记/作废分别显示，引用阻断与历史保持|AaCourseConsoleView.vue:88、109、127、142、185；AaCourseDetailView.vue；AaCourseFormView.vue|
|开课管理|任务批次详情、派师确认、合拆班确认、调整确认、教师本人确认和退回|冻结原批次/任务；教师姓名工号作对照；权限和责任取现有服务动作；主流程以当前代码为准|AaTaskDetailView.vue:370、398、412、424；AaTeacherAssignConsoleView.vue:193；AaTeacherTaskConfirmView.vue:30|
|排课与课表|具体批次编辑/三视图、规则版本编辑、导入预校验、自动排课检查/确认、纠错原因、发布门禁和作废重发|区分检查和写入；显示原版本与候选；保留精确查询旧结果、草稿可编辑及正式只读规则|AaSchedulingConsoleView.vue:434、754、881、980；AaSchedulePublishView.vue:324、377、422；AaScheduleMaintainView.vue|
|选课管理|批次/课程/轮次新增、课程名单、生命周期确认、学生选退预检与确认、归档详情|同批次锁定；实时容量及冲突再次读取；报名不等于名额；名单锁定后不显示开放选退|AaSelectionConsoleView.vue:211、239、269、288、299；AaSelectionStudentView.vue:52、141、175；AaSelectionArchiveView.vue:141|


## 5. 请求与业务链定位

|业务|前端真实消费者|接口适配证据|施工前必须保护|
|---|---|---|---|
|学期/周次|学期各视图|academic-affairs.api.js:109、112、129、146；academic-affairs-term-detail.api.js:27、30、33|当前学期按既有治理/明确许可直切分支决定；影响预览与写入分开|
|组织/班级|AaOrgConsole|academic-affairs.api.js:999；AaOrgConsole.vue:817、890、1069、1371|查询范围、学生转班原子性、引用删除限制|
|方案/课程|方案和课程控制台|academic-affairs.api.js:374、425、431、483；AaProgramConsoleView.vue:1004、1023|审核节点、绑定、发布版本不可编辑|
|任务|批次/详情/教师确认|academic-affairs.api.js:516、519；AaTaskDetailView.vue:398、412、424|本人确认和学院/学校当前责任，状态与版本检查|
|课表|批次/排课/发布|academic-affairs.api.js:592、598、617；AaSchedulePublishView.vue:324、422|冲突、范围、正式版本、精确结果恢复|
|选课|批次/本人/归档|academic-affairs.api.js:1065；AaSelectionConsoleView.vue:509；AaSelectionStudentView.vue:158|容量与资格、抽签状态、锁定名单、重复命令恢复|

正式路由装配已核：`backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py:138` 挂载课程/方案/任务路由，142行起挂载课表主链，146行起挂载排课操作；课程/方案/任务正式文件为 `course_program_task_router.py`，培养方案提交/审核/绑定入口分别在144/149/154行。后续扩展路由仍在同一build_router末段装配，不能直接改旧入口认定生效。

以上是源代码定位，不声称已穷尽每个后端最终安装函数。本轮不变更接口/数据结构，后续若需改接口必须继续追到最终服务并列文件清单。


## 6. 本轮截图发现与改版优先顺序

- `01.png` 学期管理：主流程入口明确；卡片标题重复正式学期定义，当前权威列与上方说明重复；保留发布后统一激活的业务限制。

- `02.png` 学年管理：学年自动汇总及第一/第二学期关系清楚；学期状态后的数字编号无业务含义，建议去掉。

- `03.png` 当前学期：当前学期、权威来源、激活方式和关系表重复展示；改为一行当前学期摘要＋唯一治理入口，操作边界折叠。

- `04.png` 学期周次：月历与周次可读；右栏多为通用说明，默认折叠，保留更改周次会影响引用的提醒。

- `05.png` 教学周配置：已发布周次锁定提示有效；主按钮禁用但原因应紧邻按钮；不放宽锁定。

- `06.png` 学期状态：状态与归档关系表有效；首屏重复说明过多，聚焦学期行与可执行动作，冻结/归档区分保留。

- `07.png` 学期切换记录：历史链路与目标入口清楚；记录内部码外露，应移入实施详情；无前序记录如实保留。

- `08.png` 学期归档：归档版本与缺失状态可读；摘要哈希和批次数字移入证据详情，保留封存不可普通解冻提示。

- `09.png` 校历管理：日期和校历标签明确；蓝黄两条提示加右侧说明重复，合并成所选学期只读原因，教学事件优先显示。

- `10.png` 节次管理：节次时间、引用状态和行操作有效；长侧栏说明折叠，变更涉及已有引用时在确认处保留阻断。

- `11.png` 节假日配置：节假日空态真实；两条学期提示重复，保留已发布不可改的原因并缩短空态。

- `12.png` 补课日配置：补课日页面突出月历但未配对信息应紧贴事件列表；当前月无补课记录不能推断整学期无记录。保留所选学期锁定。

- `13.png` 上课时间段：先选节次的对象边界正确；整块空态和重复标题可压缩为选择器下的短提示，不默认选择首节。

- `14.png` 教学周日历：周日历与学期周次共用月历表现一致；通用来源说明过多，合并折叠。日期周次未发现视觉错位，未核后台周次算法。

- `15.png` 校历发布：已发布对象仍显示固定校验发布阶段，可能误解为待发布；设计改为依据真实状态展示已发布/不可重发。学期选择器、对象卡、左队列重复身份；合并，核验依据前置，保留已发布禁用。

- `16.png` 校历归档：归档页真实区分未封存、无发布流水与未建归档批次；保留三项缺口，移除反复证明文字和学期内部编号。

- `17.png` 学院管理：学院表和组织树并排重复名称，树占据主要工作宽度；设计保留列表优先，组织树在组织核对页展开或本页折叠。顶部说明含ID技术词，移入编辑字段帮助。

- `18.png` 专业管理：专业筛选与列表字段有效；左树与专业列表重复；停招保留历史规则应放在编辑/停用动作旁，行内删除不作为高频主操作。

- `19.png` 年级管理：年级表关联专业直接铺满长段文字，淹没班级/学生数量；设计默认显示专业数量与前两项，点击展开完整清单，保留全部名称和原统计口径。

- `20.png` 行政班管理：行政班列表名称、专业、年级、人数与状态有效；左树占宽，行内删除与常用查看并列易误触，改低频更多操作但保留后端保护。

- `21.png` 教学班生成：教学班保留正式名单版本和查看教学任务入口正确；代码和长学期在窄内容区反复折行，折叠左树后扩大主表；不得在此新增另一套派师或名单写入。

- `22.png` 组织核对：组织核对实际是引用影响表而非组织树，学生/未归档任务/生效方案证据清楚；保留该结构，只缩短重复核对说明，查看详情继续定位引用。

- `23.png` 组织统计：组织统计数字、分布与规模表清楚；不为凑改动重排图表。补充当前可见范围/统计时点（仅接口真实提供时显示），不凭截图认定数值准确。


### 总控课表/选课补充证据与已确定设计

下列来源为总控本轮实际截图与逐张观察；A组复看了规则、规则只读配置、冲突空态三张关键图，并追到对应组件，不把它们标成A组独立浏览器实测。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-01.png` 课表批次：列表直接显示批次和状态，未出现默认首行概览；多行显示版本待核对，需保留缺失提示。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-02.png` 班级课表：查询学期、周次与班级，选择后加载；未选对象不伪造课表。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-03.png` 教师课表：初始教师选择；查询范围说明和空态重复，可合并。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-04.png` 学生课表：姓名/学号选择保留；未选对象时责任大栏与空态重复。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-05.png` 教室课表：资源身份、学期周次均在筛选；未选对象时重复查询范围与空态需合并。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-06.png` 教学班课表：空态提示选择已排课教学班，可用搜索；大块范围摘要与空态重复。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-07.png` 周课表：实际默认当前学期第8周并显示日期范围；未选班级空态与顶部范围说明重复，可合并。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-08.png` 学期课表：检查学期与对象选择、状态和返回入口。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-09.png` 课表发布：队列有多种状态，顶部却统一显示发布阶段；应移除队列固定完成进度，保留每行实际状态和发布条件。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-10.png` 课表调整记录：读取调整记录与筛选，不操作调课。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-11.png` 课表导出：仅核对导出范围和状态，未创建导出任务。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-12.png` 排课规则：未选批次却有固定阶段与责任占位；规则表业务参数空白、当前配置未设置但已启用，说明含内部配置键。需补可信规则名称/值映射，不能猜默认值。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-13.png` 教师可用时间：教师时段表可读，首屏重复学期编号、责任占位及固定第2阶段；保留采纳状态与原因，压缩无对象流程栏。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-14.png` 自动排课：未选批次即显示固定第3阶段，检查条件按钮上下重复；将批次选择提前，阶段只在取得对象状态后呈现。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-15.png` 冲突报告：未选对象已有固定第4阶段；“处理当前冲突”和“生成冲突报告”语义需统一为当前真实动作，先选批次。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-17.png` 排课约束：核对约束入口实际落点。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-18.png` 教室可用时间：嵌套资源占用页出现双标题和多层来源说明，表格仍露资源内部编号；缺场地关联警告必须保留，不能把无记录当空闲。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-19.png` 自动排课预留入口：侧栏“自动排课预留”实际打开“导入排课结果”；应按实际功能统一名称，保留批次选择及上传前校验。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-20.png` 排课结果：结果入口未选批次却固定为处理冲突阶段，重复指定批次标题；应先选择对象再显示结果状态。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-21.png` 排课调整：调整页未选对象仍显示固定处理冲突进度；先选批次，再呈现已发布/草稿/纠错的实际能力。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/05-22.png` 排课归档：读取已归档批次列表，未归档数据。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-01.png` 选课批次：5个批次卡片和对象概览占首屏，具体办理区在下方；窗口已截止但批次待收口的区别必须保留，批量开选不自动执行。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-02.png` 本人选课：管理员进入学生自助页被拒绝，显示为加载失败；设计应区分岗位不适用与读取失败，不放宽授权。学生正常态未验证。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-03.png` 选课规则：只查看规则页和所选批次，未保存。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-04.png` 补选管理：实际窗口截止但批次未执行截止，补选指引被阻断；应把这条原因与可办下一步靠近主体，压缩上方卡片与重复阶段。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-05.png` 选课冲突检测：只读查看冲突内容，未提交选课。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-07.png` 选课归档：归档表显示学期内部编号和原始日期；已有选中归档对象时应同步高亮对应行，保留只读封存和导出用途限制。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-05-detail.png` 选课冲突检测内容：内容区按学号查询冲突；0条时既有大型空态又有空明细表和分页，应合并为一处，保留查询结果不等于提交保证。

- `C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/06-03-detail.png` 选课规则配置区：开选后规则只读，当前使用全宽禁用步进器；设计改静态值并保留0含义与变更限制，不能放开修改。


**规则可信展示：**`AaSchedulingConsoleView.vue:342、350、565` 当前分别直读ruleLabel/valueSummary及按键建立规则目录。设计优先用真实返回名称，缺失时用同键目录名称；值按目录类型/单位解释真实ruleValue。缺值显示“配置值未返回”，不能凭备注或默认值反推当前值，不能用“未设置”掩盖已启用规则展示异常。未识别规则的技术键只放实施详情，保存前必须准确读取，禁止覆盖成猜测默认值。


**阶段条适用条件：**无选定批次、查询失败或工作区状态缺失时不显示已完成/当前阶段和责任占位；学期级规则和教师时段仍可按学期查看，不强制选择无关批次。明确选中批次且服务返回状态后再显示真实阶段，保留预发布、发布和纠错区别。


**规则只读与冲突空态：**`components/parallel-a/AaSelectionSpecialWorkspace.vue:24–31` 的只读规则用静态值代替禁用步进器，0的含义和原变更限制不变；96–101行的空态与DataTable改为按成功空结果/非空互斥设计，并保留越界分页恢复，不改规则值或查询范围。


**归档名称与时间：**`AaSelectionArchiveView.vue:25–26` 当前使用termId回退和原始lockedAt。设计使用可信名称与现有日期格式化，缺名显示学期信息不可用，保留原值；不新增臆测名称，不把无名当无学期关联。


截图根目录：`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/A/`。原图可能含沙箱显示数据，未复制进仓库，不作为公开材料。


## 7. 具体状态与衔接验收卡

|场景|正常路径|拒绝/恢复路径|验收对象|
|---|---|---|---|
|学期定义与当前治理|定义发布后可查；统一治理学校取治理结果，明确允许直切的非治理学校保留原确认切换|未激活不误标当前；直切许可缺失/false、加载失败或无校级权限均拒绝；已归档不能普通解冻|学期列表、当前学期、状态、上下游选择器|
|周次/校历变更|草稿修改先预览影响并能定位日期|已发布只读；预览失败不开放提交；调休不成对阻断|周配置、校历6页签、课表日期|
|节次与校区时段|所选节次读取正确校区和生效区间|切节次旧请求不覆盖；已有引用不能删改身份|作息两页签、编辑与删除确认|
|班级与学生调整|源/目标班及预检学生一致，成功结果可查|关闭/失败不清输入；已有学生任务限制保持；部分完成分项列出|组织控制台、学生抽屉、调整申请/结果|
|方案版本与引用|当前版本和绑定年级一致，新版本可继续编制|旧版本只读；审核阻断可定位；同一原因不重复创建|方案列表、编制、审核、发布、变更|
|课程详情返回|列表筛选→课程详情→编辑→返回保持原列表范围|读取失效不显示上一课程；取消不丢上下文|AaCourseFormView.vue:225目前直接回详情/列表路径，需复核筛选恢复|
|派师与教师确认|所选任务正确分配，本人确认后管理队列更新|跨学院/他人任务拒绝；改派后旧确认按既有规则失效|任务详情、分配、教师确认、调整|
|排课与发布|批次条件可查，冲突可定位，发布后同一版本多视图一致|未知结果只能查询；已发布不可直接编辑，纠错走草稿|排课控制台、发布、各课表视图|
|选课与名单|同批次资格与容量检查后形成选课记录，锁定名单可查|报名未中签不算取得名额；窗口关闭与名单锁定拒绝选退；迟到响应不串批次|选课控制台、本人选课、归档|
|课程全量与历史判断|当前实现按全部课程版本判定旧版|不得删成只读首页再误判当前版；将来优化必须由服务提供可信版本关系并分页，耗时/内存本轮未测|AaCourseConsoleView.vue:376–405|


## 8. 设计收口和实施顺序

先锁定所有入口与内部流程 → 本轮截图补齐 → 每页设计卡核对 → 与B/C组核对组织、资源、统计、归档引用 → 总控统一设计结论 → 才允许业务代码施工。

实施时先共享状态/返回/错误规范，再基础配置、课程方案、任务、课表、选课；原有27页候选按主分支差异复用，不整文件覆盖。自动排课预留入口实为导入、选课结果复用课表批次等标题与真实目的差异优先交总控定稿；不自行增加菜单或业务能力。

**未完成证据：**86个入口地址已有首屏/受阻状态截图，但选定业务对象后的全部详情、关键弹窗、错误恢复、岗位正反向、375/390/430宽度、后端最终链逐接口及真实办理仍未穷尽。班级调整批量列表读取失败、学生本人选课岗位正常态、选方案前空态后的具体数据均单列待核实；不能据首屏覆盖标记五模块已验收。

## 9. 交叉复核修订（2026-10-25）

- 当前学期：核对 `AaTermCurrentView.vue:66、134–138、209`，统一治理与明确允许直切两路径都保留；直切只对已发布候选，仍需原确认框。
- 排课归档：核对 `AaScheduleBatchListView.vue:153–173`，`panel=archive` 只看已归档，可归档留普通批次列表；不扩大本入口结果集。
- 补选：核对 `components/parallel-a/AaSelectionSpecialWorkspace.vue:38、60、197–211`，只读取已截止批次指引，完成结论需原记录与替代记录正式关联；缺关联待核对，不新增代选或调整流程。
- 95条入口表及其他表格的内部空行已清除，标题段落留空；本次不改已有截图覆盖数，不修改业务代码。

## 10. 总控补拍A组前三模块（2026-10-25）

以下36张均由总控保存并实际查看；按精确path补充95条入口表。只引用A补和05-/06-证据，不计入B组后续补图。相同地址别名共享证据，但来源入口高亮、全部深层状态仍需单独验证。

|编号|入口/所拍状态|证据|设计结论与边界|
|---|---|---|---|
|A补01|专业方向<br>`/admin/academic-affairs/orgs?tab=direction`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补01.png`|专业方向未启用，保留学校政策决定和显式开关，不为审计启用。|
|A补02|班级学生<br>`/admin/academic-affairs/orgs?tab=students`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补02.png`|行政班与姓名学号查询清楚，初始需选班；批量调整入口提示可改成有权限的直接入口并保留范围。|
|A补03|班级调整<br>`/admin/academic-affairs/orgs?tab=adjust`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补03.png`|单学生调整与班级层级调整并置，正文有内部对象ID和版本解释；批量记录区实际读取失败，正常列表未核实。|
|A补04|专业教学计划<br>`/admin/academic-affairs/programs`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补04.png`|方案名称/版本/阻断可见，仍有正式来源记录与方案内部编号；旧候选已精简的部分可承接，不重复实现。|
|A补05|方案制定<br>`/admin/academic-affairs/programs/console?tab=authoring`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补05.png`|制定页草稿列表与继续编制入口简洁，可保留；新建与相关工作区不重复展开。|
|A补06|方案版本<br>`/admin/academic-affairs/programs/console?tab=versions`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补06.png`|版本列表可读，但顶部无动作时留有空白工具条；保留版本与新建版本权限，压缩空容器。|
|A补07|课程模块<br>`/admin/academic-affairs/programs/console?tab=courseModules`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补07.png`|未选方案空态与选择器重复提示；应优先显示方案选择，选中后再展开课程模块；未查看具体方案模块。|
|A补08|学分要求<br>`/admin/academic-affairs/programs/console?tab=creditRequirements`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补08.png`|学分要求初始未选方案，未取具体标准；设计应从方案详情保留选中对象进入，避免再次选择。|
|A补09|实践环节<br>`/admin/academic-affairs/programs/console?tab=practiceSegments`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补09.png`|实践环节初始未选方案，需从同一方案连续进入而非重复选取；具体实践条目未读取。|
|A补10|毕业要求<br>`/admin/academic-affairs/programs/console?tab=graduationRequirements`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补10.png`|毕业要求需选方案，当前未读具体条目；保持方案上下文后再展示达成指标，不能填默认要求。|
|A补11|计划审核<br>`/admin/academic-affairs/programs/console?tab=review`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补11.png`|审核选中对象与证据卡已对应；可压缩重复对象概览和“设计视角/正式来源”解释，保留阻断卡与完整方案入口。|
|A补12|计划发布<br>`/admin/academic-affairs/programs/console?tab=publish`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补12.png`|发布页已启用对象仍显示当前发布阶段与校验并发布主按钮；设计须依据实际状态/服务允许动作决定标签与可用性，不能仅按页签。|
|A补13|方案变更<br>`/admin/academic-affairs/programs/console?tab=changeStatus`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补13.png`|变更对象已启用但显示课程编制固定阶段；版本链空态说明保留，重复对象责任说明可收拢。|
|A补14|方案归档<br>`/admin/academic-affairs/programs/console?tab=archive`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补14.png`|归档页实际含被新版本替代的旧版本，旧状态可为已启用；需分清原版本状态与历史替代原因，空工具条可移除。|
|A补15|课程列表<br>`/admin/academic-affairs/courses`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补15.png`|课程列表仍显示稳定身份、正式课程编号；承接既有候选精简，保留业务代码、名称、版本、学分学时。|
|A补16|新增课程<br>`/admin/academic-affairs/courses/new`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补16.png`|新建表单启动条件和前后业务重复顶部流程；字段必填与编码规则保留，按旧候选精简。|
|A补17|课程分类<br>`/admin/academic-affairs/courses/console?tab=category`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补17.png`|分类筛选、数量、课程与调整入口清楚，保留主要结构；总量与分类需保持同一统计口径。|
|A补18|课程性质<br>`/admin/academic-affairs/courses/console?tab=nature`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补18.png`|课程性质标签和行内操作简明，首屏结构可保留；调整权限/新版本规则按原逻辑。|
|A补19|学分学时<br>`/admin/academic-affairs/courses/console?tab=credit`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补19.png`|学分与理论/实践学时集中可读；0与缺值显示应维持区别，不补造数值。|
|A补20|课程大纲<br>`/admin/academic-affairs/courses/console?tab=outline`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补20.png`|大纲列表仅课程名与管理入口，不能直接判断大纲是否齐全；设计需以真实材料状态提供可读标记，缺来源另列依赖，不猜有无。|
|A补21|考核方式<br>`/admin/academic-affairs/courses/console?tab=assessment`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补21.png`|考核方式中文分类和状态明确，保留结构，不改考试/考查规则。|
|A补22|课程负责人<br>`/admin/academic-affairs/courses/console?tab=owner`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补22.png`|已指定/未指定责任人分类可读，保留姓名与逐行操作；未进入人员选择弹窗。|
|A补23|课程材料<br>`/admin/academic-affairs/courses/console?tab=material`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补23.png`|材料列表无法直接判断材料是否齐全；设计保留原安全上传流程，并仅用真实材料状态补充列表，不造完成标记。|
|A补24|课程停用<br>`/admin/academic-affairs/courses/console?tab=disable`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补24.png`|停用列表按状态显示可操作对象，保留引用检查与停用确认；本轮未验证确认弹窗。|
|A补25|历史课程（已停用/旧版本）<br>`/admin/academic-affairs/courses/console?tab=archive`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补25.png`|历史课程0条却提示课程库为空并引导新建，与实际756课程不符；改成暂无历史/停用版本，不造数据。|
|A补26|实践教学计划<br>`/admin/academic-affairs/programs/console?tab=practicePlan`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补26.png`|实践计划未选方案初始页，选中后字段和异常状态未实测；设计复用同一方案上下文。|
|A补27|计划变更<br>`/admin/academic-affairs/programs/console?tab=planChange`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补27.png`|已启用方案的计划变更列表可读；顶部空工具栏应移除，发起变更仍走原版本流程。|
|A补28|学期开课计划<br>`/admin/academic-affairs/teaching-tasks`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补28.png`|批次状态、阻断和下一步集中展示，可保留；摘要解释可精简但本页统计口径保留。|
|A补29|教学任务生成<br>`/admin/academic-affairs/teaching-tasks?open=generate`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补29.png`|任务生成表单已出现，批次统计与历史列表占较多位置；表单优先，但一个批次一个责任学院/行政班筛选不改变方案与校历前置必须保留。|
|A补30|任课教师分配<br>`/admin/academic-affairs/teaching-tasks/assign`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补30.png`|首行已就绪任务被顶部默认当当前对象，固定分配阶段与状态冲突；承接旧候选去除首行概览，保留逐行分配和确认边界。|
|A补31|合班拆班<br>`/admin/academic-affairs/teaching-tasks/merge-split`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补31.png`|合拆班队列为空仍固定分配阶段、两个大空态，已有旧候选可压缩；同批次同版本与教师确认前条件保留。|
|A补32|教学任务确认<br>`/admin/academic-affairs/teaching-tasks/confirm`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补32.png`|未选批次却固定学院校对阶段，且列表多为已通过；采用旧候选去固定阶段，选中后显示真实状态。|
|A补33|教师任务确认<br>`/admin/academic-affairs/teaching-tasks/teacher-confirm`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补33.png`|本人待确认0条仍有固定第3阶段和重复0卡片/页签；缩短空态，保留本人确认与历史入口，非空确认未验证。|
|A补34|教学任务调整<br>`/admin/academic-affairs/teaching-tasks/adjust`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补34.png`|调整页默认首行概览、固定分配阶段和长规则挤压列表；承接旧候选折叠规则，保留换教师需本人确认和重新审核约束。|
|A补35|计划执行进度<br>`/admin/academic-affairs/teaching-tasks/stats`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补35.png`|批次与任务数量、分配率/确认率分开显示，单位清楚；单一状态的大柱图可简化展示，不能更改分母。|
|A补36|工作量申报审核<br>`/admin/academic-affairs/workload-review`|`C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/A补36.png`|工作量已通过记录仍固定统计口径阶段，顶部首行概览重复台账；保留学期、类别、课时、意见与状态，按真实对象定位。|

### 补拍后的明确决策

- **历史课程空态**：`AaCourseConsoleView.vue:46` 对过滤后的空结果使用了课程库为空通用提示，且历史集合由295行派生。设计按加载失败、源库确为空、当前筛选无匹配、无历史/停用版本分别显示；本轮课程库有756条不是新建课程的理由。
- **材料完成状态**：同文件66/69行仅提供管理入口，484行在选定课程后读取材料；不能从列表没返回材料推断未完成。优先复用已有可信汇总来源；无来源时登记接口依赖，保留查看入口，不新增逐行材料请求、不编完成百分比。
- **方案发布阶段**：`AaProgramConsoleView.vue:12、484–496` 有按页签组织动作/阶段的结构。设计将“在哪个功能页”与“当前对象完成到哪一步”分开，已启用对象按实际允许的绑定/发布能力显示动作；不得自行扩大或收回后端原能力。
- **工作量审核**：`AaWorkloadReviewView.vue:21` 固定第3阶段与32行起台账重复，删除固定阶段表达，保留原审核动作、结果查询和65行有关依据缺失/非薪酬结论的业务限制。
- **本轮结论**：入口展示设计95条均有具体决定和本轮截图映射；关联详情/弹窗及全部异常状态尚未穷尽，不将“设计覆盖”写成“完整业务流程通过”。
