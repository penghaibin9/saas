# B组：学生过程与业务保障——流程与逐页设计

日期：2026-10-25。归属独立《08-教务15模块-流程与页面设计-并行施工计划》，不是新的权限或业务授权。

## 1. 范围、证据和设计结论

本组覆盖学籍管理48条、日常教学13条、毕业管理15条、教学资源7条、教务归档6条，共89个源码入口。相同地址与隐藏别名保留逐项对应，不重复宣称独立页面。读取当前主目录教务源码，主分支基线 ff7786877；旧 saas-roles-r0 仅作候选对照。本轮仅保存设计文档和临时截图，没有改业务源码、提交推送、启停服务或写沙箱业务。

使用 Product Design（产品设计）的截图审计框架：先实际页面取证，再结合来源/责任/动作/结果制定设计。账号通过正常登录切到已有学校管理员身份；并未授予新权限。这里只能证明该身份的只读页面，不能证明学院教务、教师、学生均可办理。

**设计方向：**保留原办理链和页面归属，以批次/学生/课位/资源为中心压缩重复概览；真实状态替代固定设计步骤；主动作就近摆放；材料、不可逆操作、授权范围与未知结果恢复继续可见。现有教室资源页面结构合理，保留，不为统一外观重做。


**首屏证据更新：**B组原71个稳定地址，加总控补拍并经B组查看的8个地址，当前79个B组去重地址均已有稳定首屏证据；另由总控补拍带 `scope=roster&tab=statusChange` 的学籍统计入口，合计80个不同地址。统计组件设计归C组，参数入口不能用普通统计截图代替。原8张加载/过渡图保留历史，不再记为缺稳定截图。此覆盖不包含所有深层详情、弹窗、交互状态、写入流程或其他岗位，不能替代完整验收。

**统一复用：**`academicFlowContext.js` 负责可信身份、迟到响应和返回位置；`ModulePageShell` 紧凑模式、`AppSectionCard` 默认折叠、`DataTable` 内部横向滚动。只建议使用现有能力，不新造缓存、组件体系或导航。

## 2. 五条内部办理链和不可改变的规则

| 模块 | 内部流程 | 主要页面组织 | 必须保留 |
|---|---|---|---|
| 学籍管理 | 名册选学生→注册/分流/异动或身份更正→原节点审核→计划/实际生效→档案回查；成绩预警→责任人跟进→结果 | 列表负责选对象；详情负责核对；表单只展示当前类型必需字段；申请状态与生效状态分离 | 主档单一写入入口、未来生效、材料安全、敏感脱敏、同一学生跨批次区分、未知结果禁止重发 |
| 日常教学 | 正式课位→调停课申请/冲突预检→原审批链→课表生效/通知；课次→考勤→统计；资源节次→预约→审批 | 原/目标安排对照；审核队列先对象和证据再动作；统计不兼做管理 | 任课关系、原审批顺序、重新冲突核对、正式课堂与特殊补录分口径、占用未知不能当空闲 |
| 毕业管理 | 批次→预审→十一项证据核对→学院/教务原审核→毕业结业延毕结果→证书/归档 | 批次小栏贯穿页签；学生证据和责任入口在首屏；终审单独确认 | 系统预审不代替人工终审、费用原缺数据不阻断规则、不可逆终态、证书编号不可复用、历史结果不覆盖 |
| 教学资源 | 台账维护→排课/预约占用→冲突/维修→资源状态回查 | 台账是对象源，预约/课表是占用源；维修看板与资源状态双回查 | 可用≠时段空闲、实训室场地精确关联、多工单恢复条件、历史记录不因删除入口消失 |
| 教务归档 | 学期批次→十三域预检→定位缺项→复核→封存→物料/受控纠错 | 缺项先列、通过项折叠；按真实状态展示当前动作；已封存先历史查看 | 学院实时预检不能代学校封存、待处理不得封存、普通解冻关闭、独立责任复核和旧版本永久保留 |

上述是既有链路的界面承接，不将文档2未来审批目标擅自套到当前服务。真实事务和权限执行需后续隔离测试与正常账号办理验证。

## 3. 已确认的问题与可执行设计决定

| 问题 | 设计决定 | 回归验收重点 |
|---|---|---|
| 名册未选对象却有顶部“打开学生档案”，空队列也出现 | 取消默认首行入口，保留逐行姓名/档案和按状态的异动动作；承接既有候选 | 点击第二行必须进入第二个学生；空结果无误导入口；大整数标识不改值 |
| 学籍异动记录、复学结果、生效/归档有原始类型和时间；多个页面同一状态展示不一致 | 复用已存在中文映射和公共时间格式；未知值明确待核对，原值仅实施折叠区 | 同一单据列表/详情/统计名称一致；日期原值不改；时区显示一致 |
| 转专业列表前后都只显示“正常在籍” | 优先显示前专业→目标专业，状态作为独立列；接口缺名称先显示待核对并定位源字段 | 不靠状态推断转专业成功；名称缺失不猜；点击仍同一申请 |
| 更正和分流等页面固定阶段条占首屏并假定完成 | 未选对象只显示任务列表；选中后真实阶段才展开；参考流程默认折叠且不带完成态 | 已通过、已驳回、未选对象、已确认分流都不能展示同一个固定当前阶段 |
| 注册与未注册搜索只有本页能力，已有候选修复尚未整合 | 先对账候选前后端，再使用数据库过滤分页；不只改搜索文案 | 跨页命中、总数、清空、旧请求覆盖、批次范围、无权数据排除 |
| 审批六卡、毕业五栏概览与阶段图重复，操作被推后 | 保留一行对象/状态/责任/阻断；材料和前后对照靠近审核；技术版本说明折叠 | 关键阻断/材料状态仍可见；保留审核意见；换对象/批次不得串数据 |
| 空申请/空预警建议创建单据或改阈值 | 空态只说明当前范围无记录和可调整的查询条件；创建/扫描作为独立授权动作 | 不因为空数据鼓励退学、扫描或改政策；错误不能装空数据 |
| 调停课统计范围作为巨大数字卡、学期ID外露、长教师名截断 | 学期名称作筛选摘要，数字卡只放申请数/待办数/比例；名称有完整查看路径 | 同范围分母不变；C组入口与本页一致，返回保留学期 |
| 考勤场次用内部场次/班级编号识别 | 列顺序改课程、班级业务名、日期、类别、状态、人数；内部标识仅用于请求 | 不把相同课程不同课次合并；本人点名和未点名阻断保持 |
| 资源占用/冲突重复讲内部关联算法 | 技术来源折叠；未映射、缺场地、空结果非预约许可等业务风险常显 | 精确匹配、校历换算和权限不变；无数据不宣称可预约 |
| 维修记录恢复时间早于报修时间 | 保留既有异常警告，仅格式化显示，不修历史数据来消警告 | 原始数据不变；时间冲突仍提示；完成维修仍核对资源状态 |
| 已封存页面仍写“先检查完整性”，批量归档入口共用单学期页面 | 按真实状态生成下一步；已归档显示查阅/纠错；说明现有批量指本学期数据域 | 不新增跨学期批处理；已归档不能进入普通确认/解冻 |
| 预警看板/统计把含已关闭总数标成在办 | 标签统一为“预警总数（含已关闭）”，保留后端返回总数及来源/等级/处理状态分布；不改变查询默认值或擅自减去关闭项 | 同范围各状态之和等于总数；关闭记录仍可统计；另一个仅看在办统计接口不得共用错误标签 |


**补拍后的源码核对：**

- 预警：`AaWarningConsoleView.vue:32、187` 将 `summary.total` 标为在办；`warning_core_router.py:92–93` 调用 `warning_summary`；`academic_affairs_warning_service.py:572–589` 明确 `exclude_closed=False`，底层 `group_counts:547–568` 排除作废/删除但保留已关闭。因此本轮只更正上述展示标签，不改SQL默认条件，不新增不同口径指标。适用预警看板、预警统计及日常教学的旷课预警联动复用入口。
- 封存：`AaArchiveConsoleView.vue:68–73` 主动作说明固定写“先检查”，但按钮已按状态限制。设计只将说明随原状态变化：草稿/缺项提示检查和处理，待确认提示按原权限确认，已归档提示历史查阅/受控纠错，已取消提示只读历史；普通解冻关闭、不同人复核和旧版本保留不动。
- 课程达成：`AaGraduationAuditConsoleView.vue:121–155` 分开必修与选修结果；`academic_affairs_graduation_service.py:225–258` 中选修目标缺失或歧义返回未知，不是通过。补拍中的选修缺要求、系统异常、责任模块入口全部保留；不能为了压缩页面把未知改为零学分要求。

## 4. 全部89个入口的逐页设计卡

每行“信息与布局、主操作、状态/恢复”都是施工约束，结合本节末的共用状态要求执行。隐藏条目仅验证原入口归属，不另建路由。截图仅采纳本轮实际查看的稳定画面；加载截图和未打开状态明确保留缺口。

### 02 学籍管理（48项）

#### B-02-01 学籍名册

- 入口：`/admin/academic-affairs/roster`；代码：[AaRosterListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:38)。
- 信息：学生姓名/学号、班级、脱敏证件、学籍状态、是否在籍；当前状态筛选常显。
- 布局：姓名/学号与状态同排，查询后直接列表；删除默认首行档案入口。
- 操作：逐行查看档案；仅合适状态显示发起异动/办理复学。
- 状态与恢复：返回保持查询、页码与来源；休学/退学/保留学籍按原状态筛选，不改学生状态。
- 本轮证据：[B-01-roster.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-01-roster.png)：已查看，主列表；顶栏档案入口与对象选择需核对。

#### B-02-02 学籍档案（隐藏关联）

- 入口：`/admin/academic-affairs/roster`；代码：[AaRosterListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:38)。
- 信息：学生姓名/学号、班级、脱敏证件、学籍状态、是否在籍；当前状态筛选常显。
- 布局：姓名/学号与状态同排，查询后直接列表；删除默认首行档案入口。
- 操作：逐行查看档案；仅合适状态显示发起异动/办理复学。
- 状态与恢复：返回保持查询、页码与来源；休学/退学/保留学籍按原状态筛选，不改学生状态。
- 本轮证据：[B-01-roster.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-01-roster.png)：已查看，主列表；顶栏档案入口与对象选择需核对。

#### B-02-03 学籍状态

- 入口：`/admin/academic-affairs/roster/status`；代码：[AaRosterStatusView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterStatusView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:40)。
- 信息：总数、在籍/非在籍、近30天异动；状态分布。
- 布局：紧凑汇总→状态分布；实现函数、单一写入口等文字放实施说明。
- 操作：点击状态进入同范围名册。
- 状态与恢复：保留未知状态；状态分布相加与范围口径对账。
- 本轮证据：[B-02.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-02.png)：已查看；状态分布明确，change_student_status等实现说明移至实施说明。

#### B-02-04 学籍异动记录

- 入口：`/admin/academic-affairs/roster/changes`；代码：[AaRosterChangeRecordsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterChangeRecordsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:41)。
- 信息：学生、异动类型、前后状态、申请状态、生效时间。
- 布局：学生选择器替代内部学生编号；类型与状态复用共用中文映射，时间复用公共格式。
- 操作：查看申请；姓名进入同一学生档案。
- 状态与恢复：保留累计与筛选口径，映射缺失显示待核对，不把已生效映射成未知。
- 本轮证据：[B-03.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-03.png)：已查看；学生编号筛选、内部类型和原始时间外露。

#### B-02-05 学籍导入导出

- 入口：`/admin/academic-affairs/roster/import-export`；代码：[AaRosterImportExportView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:42)。
- 信息：导入任务、文件状态、校验结果、错误行；导出范围、用途、生成任务状态。
- 布局：导入、导出、任务记录三区；仅保留字段/安全扫描/部分失败等可行动说明，技术字段默认折叠。
- 操作：打开批量导入；申请导出；查看原任务结果。
- 状态与恢复：文件仍走安全扫描，任务版本/原任务恢复不删；未实际上传或导出。
- 本轮证据：[B补01.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补01.png)：总控已补拍稳定首屏，B组已查看；任务区已稳定显示0条；压缩实现说明，保留文件扫描/预检、范围和任务恢复限制。
- 历史证据：[B-04.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-04.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-06 休学学生

- 入口：`/admin/academic-affairs/roster?status=SUSPENDED`；代码：[AaRosterListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:38)。
- 信息：学生姓名/学号、班级、脱敏证件、学籍状态、是否在籍；当前状态筛选常显。
- 布局：姓名/学号与状态同排，查询后直接列表；删除默认首行档案入口。
- 操作：逐行查看档案；仅合适状态显示发起异动/办理复学。
- 状态与恢复：返回保持查询、页码与来源；休学/退学/保留学籍按原状态筛选，不改学生状态。
- 本轮证据：[B-05.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-05.png)：已查看；顶部档案动作与选中对象不一致，需取消默认首行入口。

#### B-02-07 复学学生

- 入口：`/admin/academic-affairs/roster/resumed-students`；代码：[AaRosterChangeResultListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterChangeResultListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:47)。
- 信息：学生/学号、前后状态或专业、结果、生效日期、原因。
- 布局：结果列表优先；一行说明这是结果查询，独立保留发起申请入口。
- 操作：查看档案、异动详情。
- 状态与恢复：复学和转专业查历史异动结果，不改用当前学生状态过滤；空态不提示造数据。
- 本轮证据：[B-06.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-06.png)：已查看；状态迁移含英文枚举，保留只读结果与申请入口区分。

#### B-02-08 退学学生

- 入口：`/admin/academic-affairs/roster?status=WITHDRAWN`；代码：[AaRosterListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:38)。
- 信息：学生姓名/学号、班级、脱敏证件、学籍状态、是否在籍；当前状态筛选常显。
- 布局：姓名/学号与状态同排，查询后直接列表；删除默认首行档案入口。
- 操作：逐行查看档案；仅合适状态显示发起异动/办理复学。
- 状态与恢复：返回保持查询、页码与来源；休学/退学/保留学籍按原状态筛选，不改学生状态。
- 本轮证据：[B-07.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-07.png)：已查看；空列表仍出现顶部档案按钮，需随对象禁用或移除。

#### B-02-09 转专业学生

- 入口：`/admin/academic-affairs/roster/transferred-major-students`；代码：[AaRosterChangeResultListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterChangeResultListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:48)。
- 信息：学生/学号、前后状态或专业、结果、生效日期、原因。
- 布局：结果列表优先；一行说明这是结果查询，独立保留发起申请入口。
- 操作：查看档案、异动详情。
- 状态与恢复：复学和转专业查历史异动结果，不改用当前学生状态过滤；空态不提示造数据。
- 本轮证据：[B-08.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-08.png)：已查看；空结果合理，说明可缩短并保留结果与申请区别。

#### B-02-10 保留学籍

- 入口：`/admin/academic-affairs/roster?status=PRESERVED`；代码：[AaRosterListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:38)。
- 信息：学生姓名/学号、班级、脱敏证件、学籍状态、是否在籍；当前状态筛选常显。
- 布局：姓名/学号与状态同排，查询后直接列表；删除默认首行档案入口。
- 操作：逐行查看档案；仅合适状态显示发起异动/办理复学。
- 状态与恢复：返回保持查询、页码与来源；休学/退学/保留学籍按原状态筛选，不改学生状态。
- 本轮证据：[B-09.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-09.png)：已查看；空列表顶部档案动作应移除或禁用。

#### B-02-11 学籍信息更正

- 入口：`/admin/academic-affairs/roster/corrections`；代码：[AaRosterCorrectionListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRosterCorrectionListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:49)。
- 信息：当前学生、申请字段、原值/新值、申请原因、材料、状态、审核意见。
- 布局：筛选→申请队列＋原新值对照→材料→审核区；删除固定完成阶段、来源自证和硬编码责任名。
- 操作：发起更正；按能力显示通过/驳回；查看档案。
- 状态与恢复：选中对象始终高亮；敏感值脱敏；更正不改学籍状态；返回保留原队列。
- 本轮证据：[B-10.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-10.png)：已查看；固定阶段误示当前进度，原值新值应前移，姓名等信息只保留必要位置。

#### B-02-12 学籍统计

- 入口：`/admin/academic-affairs/stats?scope=roster&tab=statusChange`；代码：[AaStatsOverviewView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatsOverviewView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:133)。
- 信息：已应用学期/学院范围、已生效异动数量、类型分布、查询更新时间；字段口径继承C组统计设计。
- 布局：从学籍模块带原范围进入统计，不另造页面；更新时间只作文本，不画成数量，类型按可信中文映射显示。
- 操作：按C组统计设计查看。
- 状态与恢复：返回必须回原学籍筛选，统计不扩大权限。
- 本轮证据：[学籍统计独立参数入口截图](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/02-12-学籍统计.png)：总控已补拍，B组已查看；保留 `scope=roster&tab=statusChange`。可见异动类型英文和更新时间被解析为柱图数值，按C组共用统计设计修复展示与直接消费者，不改变接口统计口径。

#### B-02-13 学籍归档

- 入口：`/admin/academic-affairs/archive?entry=studentStatus`；代码：[AaArchiveConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:178)。
- 信息：学期批次、真实状态、十三域结论、缺项、封存时间、纠错版本。
- 布局：批次队列→状态/范围紧凑摘要→当前可办动作→数据域→纠错；已归档不提示先检查。
- 操作：未封存：检查/按原条件确认；已封存：历史查看/独立纠错。
- 状态与恢复：批量入口仅现有单学期数据域，不能假定跨学期能力；不可解冻、双人纠错和原版本保存不变。
- 本轮证据：[B补02.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补02.png)：总控已补拍稳定首屏，B组已查看；学籍归档实际进入全教务归档共用页；已归档仍提示先检查完整性再确认归档，需按封存状态改主动作，纠错与历史保护保留。
- 历史证据：[B-11.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-11.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-14 注册批次

- 入口：`/admin/academic-affairs/registration`；代码：[AaRegistrationBatchListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationBatchListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:51)。
- 信息：批次名称、注册类型（注册批次入口锁定自身类型）、学期/年级、范围、人数、状态。
- 布局：流程参考默认折叠，紧凑计数→条件→批次列表；未知人数不填0；已存在全局搜索候选需前后端一起整合。
- 操作：注册名单为行内主操作；关闭/归档次级，仍用原确认及权限。
- 状态与恢复：保留类型 全部；输入词与已查询条件分开；返回恢复批次条件，不误选第一行。
- 本轮证据：[B-12.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-12.png)：已查看；固定参考流程占首屏，检索仅本页，候选已有后端修复待组合。

#### B-02-15 入学注册

- 入口：`/admin/academic-affairs/registration?type=ENROLL`；代码：[AaRegistrationBatchListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationBatchListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:51)。
- 信息：批次名称、注册类型（入学注册入口锁定自身类型）、学期/年级、范围、人数、状态。
- 布局：流程参考默认折叠，紧凑计数→条件→批次列表；未知人数不填0；已存在全局搜索候选需前后端一起整合。
- 操作：注册名单为行内主操作；关闭/归档次级，仍用原确认及权限。
- 状态与恢复：保留类型 ENROLL；输入词与已查询条件分开；返回恢复批次条件，不误选第一行。
- 本轮证据：[B-13.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-13.png)：已查看；入学类型筛选与列表加载完成。

#### B-02-16 学年注册

- 入口：`/admin/academic-affairs/registration?type=ANNUAL`；代码：[AaRegistrationBatchListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationBatchListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:51)。
- 信息：批次名称、注册类型（学年注册入口锁定自身类型）、学期/年级、范围、人数、状态。
- 布局：流程参考默认折叠，紧凑计数→条件→批次列表；未知人数不填0；已存在全局搜索候选需前后端一起整合。
- 操作：注册名单为行内主操作；关闭/归档次级，仍用原确认及权限。
- 状态与恢复：保留类型 ANNUAL；输入词与已查询条件分开；返回恢复批次条件，不误选第一行。
- 本轮证据：[B-14.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-14.png)：已查看；学年字段待核对，不可把缺数据当0；参考流程应默认折叠。

#### B-02-17 学期注册

- 入口：`/admin/academic-affairs/registration?type=SEMESTER`；代码：[AaRegistrationBatchListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationBatchListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:51)。
- 信息：批次名称、注册类型（学期注册入口锁定自身类型）、学期/年级、范围、人数、状态。
- 布局：流程参考默认折叠，紧凑计数→条件→批次列表；未知人数不填0；已存在全局搜索候选需前后端一起整合。
- 操作：注册名单为行内主操作；关闭/归档次级，仍用原确认及权限。
- 状态与恢复：保留类型 SEMESTER；输入词与已查询条件分开；返回恢复批次条件，不误选第一行。
- 本轮证据：[B-15.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-15.png)：已查看；学期注册固定参考流程占首屏，保留学期类型筛选。

#### B-02-18 注册资格核验

- 入口：`/admin/academic-affairs/registration/workbench?tab=eligibility`；代码：[AaRegistrationWorkbenchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:52)。
- 信息：学生/学号/班级、资格状态、名单/材料/核验时效。
- 布局：批次条件→候选队列＋四项核验依据→处理按钮；流程参考折叠。
- 操作：核验通过/标记不合格；查看注册名单。
- 状态与恢复：材料/版本/时效未知须保留；核验通过不等于完成注册。
- 本轮证据：[B-16.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-16.png)：已查看；未选择批次状态，未核验非空资格详情。

#### B-02-19 未注册学生

- 入口：`/admin/academic-affairs/registration/workbench?tab=unregistered`；代码：[AaRegistrationWorkbenchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:52)。
- 信息：学生、批次、资格、有效暂缓、责任人、记录类型。
- 布局：批次→检索→名单；扫描全校候选的影响提示保留；全局搜索候选需配套后端。
- 操作：查看原因；扫描与导出独立确认。
- 状态与恢复：同学生不同批次保留独立行；扫描范围与搜索范围不可混淆。
- 本轮证据：[B-17.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-17.png)：已查看；未注册队列与扫描范围提示，截图已重取。

#### B-02-20 暂缓注册

- 入口：`/admin/academic-affairs/registration/workbench?tab=deferral`；代码：[AaRegistrationWorkbenchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:52)。
- 信息：学生、原因、申请延后至、状态、审核意见。
- 布局：批次条件与列表前移；长原因不截断；期限用本地可读时间。
- 操作：申请暂缓；按当前状态/权限审核。
- 状态与恢复：原期限值不变；有效暂缓排除与后续注册关系不变。
- 本轮证据：[B补03.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补03.png)：总控已补拍稳定首屏，B组已查看；暂缓记录已读取，期限仍为原始时间、已选批次仍提示默认全部；承接旧候选时间格式和范围文案修复。
- 历史证据：[B-18.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-18.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-21 注册异常

- 入口：`/admin/academic-affairs/registration/workbench?tab=exception`；代码：[AaRegistrationWorkbenchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:52)。
- 信息：学生、异常类型、说明、状态、处理结果。
- 布局：批次条件→异常列表；长文本可换行/内横滚，技术术语不用作说明。
- 操作：标记异常；进入处理弹窗。
- 状态与恢复：创建与处理未知结果保留原对象恢复，不因换批次丢恢复入口。
- 本轮证据：[B补04.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补04.png)：总控已补拍稳定首屏，B组已查看；异常对象、类型、说明、状态和处理入口对应；范围说明按选中批次修正，长原因窄屏继续验证。
- 历史证据：[B-19.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-19.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-22 注册归档

- 入口：`/admin/academic-affairs/registration/workbench?tab=archive`；代码：[AaRegistrationWorkbenchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:52)。
- 信息：批次名称、类型、注册完成数/总数、归档时间。
- 布局：已归档列表优先；时间可读，名称不截断。
- 操作：查看名单；导出保持原权限与用途要求。
- 状态与恢复：已关闭不等于已归档；不新增归档动作或隐式导出。
- 本轮证据：[B补05.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补05.png)：总控已补拍稳定首屏，B组已查看；归档列表已稳定，日期原始格式待承接候选修复；保留名单与导出权限。
- 历史证据：[B-20.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-20.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-23 分流批次

- 入口：`/admin/academic-affairs/major-split`；代码：[AaMajorSplitView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaMajorSplitView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:54)。
- 信息：批次名称、年级、志愿上限、真实阶段；批次内专业容量/学生志愿/分配结果。
- 布局：未选批次只显示列表；参考流程折叠，选中后由真实状态生成步骤；志愿、分配、统计共用同批次。
- 操作：进入批次；按原状态显示分配/调剂/确认。
- 状态与恢复：不改志愿上限、分流规则或容量；确认前保留原新专业对照，结果写回另核实。
- 本轮证据：[B-21.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-21.png)：已查看；已确认分流批次仍固定显示创建步骤，需改按所选批次显示实际阶段。

#### B-02-24 分流志愿与录取（隐藏关联）

- 入口：`/admin/academic-affairs/major-split`；代码：[AaMajorSplitView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaMajorSplitView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:54)。
- 信息：批次名称、年级、志愿上限、真实阶段；批次内专业容量/学生志愿/分配结果。
- 布局：未选批次只显示列表；参考流程折叠，选中后由真实状态生成步骤；志愿、分配、统计共用同批次。
- 操作：进入批次；按原状态显示分配/调剂/确认。
- 状态与恢复：不改志愿上限、分流规则或容量；确认前保留原新专业对照，结果写回另核实。
- 本轮证据：[B-21.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-21.png)：已查看；已确认分流批次仍固定显示创建步骤，需改按所选批次显示实际阶段。

#### B-02-25 分流统计（隐藏关联）

- 入口：`/admin/academic-affairs/major-split`；代码：[AaMajorSplitView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaMajorSplitView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:54)。
- 信息：批次名称、年级、志愿上限、真实阶段；批次内专业容量/学生志愿/分配结果。
- 布局：未选批次只显示列表；参考流程折叠，选中后由真实状态生成步骤；志愿、分配、统计共用同批次。
- 操作：进入批次；按原状态显示分配/调剂/确认。
- 状态与恢复：不改志愿上限、分流规则或容量；确认前保留原新专业对照，结果写回另核实。
- 本轮证据：[B-21.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-21.png)：已查看；已确认分流批次仍固定显示创建步骤，需改按所选批次显示实际阶段。

#### B-02-26 异动台账

- 入口：`/admin/academic-affairs/status-changes`；代码：[AaStatusChangeListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:58)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-22.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-22.png)：已查看；重复说明与历史毕业类型外露，审批节点和计划生效保留。

#### B-02-27 发起异动

- 入口：`/admin/academic-affairs/status-changes/new`；代码：[AaStatusChangeFormView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeFormView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:59)。
- 信息：学生、异动类型、当前/目标组织状态、生效方式/日期、原因、材料。
- 布局：学生与前后对照优先，生效条件紧邻日期；参考流程折叠，右侧重复启动说明合并为阻断提示。
- 操作：提交申请；结果未知只保留查询原申请。
- 状态与恢复：理由仍为现有选填；计划日期不得提前改主档；上传隔离、安全状态和身份失效保护不删。
- 本轮证据：[B-23.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-23.png)：已查看；申请表单保留生效方式、选填原因和安全材料；流程参考与右侧重复说明收纳。

#### B-02-28 休学申请

- 入口：`/admin/academic-affairs/status-changes/suspend`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:61)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-24.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-24.png)：已查看；分类申请队列清楚，行按钮改为查看申请，保留本页统计口径。

#### B-02-29 复学申请

- 入口：`/admin/academic-affairs/status-changes/resume`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:62)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-25.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-25.png)：已查看；已生效与节点待核对分开，保留历史事实不改写。

#### B-02-30 退学申请

- 入口：`/admin/academic-affairs/status-changes/withdraw`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:63)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-26.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-26.png)：已查看；空态不应把创建退学作为默认下一步，改查询提示并保留独立申请入口。

#### B-02-31 转专业申请

- 入口：`/admin/academic-affairs/status-changes/transfer-major`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:64)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-27.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-27.png)：已查看；转专业列表应突出原专业→目标专业，不只显示相同学籍状态。

#### B-02-32 异动审批

- 入口：`/admin/academic-affairs/status-changes/approval`；代码：[AaStatusChangeApprovalView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeApprovalView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:71)。
- 信息：申请队列、学生、前后状态、材料、当前审批节点、意见、生效计划。
- 布局：两栏队列＋审核区；对象与状态单行摘要，材料与前后对照前移，决定版本归实施说明。
- 操作：通过/退回/驳回按节点能力显示；查看完整材料。
- 状态与恢复：材料未就绪/撤权/版本变化禁止提交；保留意见和原节点顺序。
- 本轮证据：[B-28.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-28.png)：已查看；审批核对6卡挤占操作，版本技术说明折叠，材料状态和审批条件保留。

#### B-02-33 异动生效

- 入口：`/admin/academic-affairs/status-changes/effective`；代码：[AaStatusChangeEffectiveView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeEffectiveView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:72)。
- 信息：学生、异动类型、前后组织/状态、计划日期、实际执行状态。
- 布局：已通过待生效/已生效双页签保留；学生筛选与类型日期同排，时间统一可读。
- 操作：异动详情、学籍档案。
- 状态与恢复：计划生效日期不是实际完成证据；不新增立即生效按钮。
- 本轮证据：[B-29.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-29.png)：已查看；日期和毕业类型原值外露；待生效与已生效分栏正确需保留。

#### B-02-34 异动统计

- 入口：`/admin/academic-affairs/status-changes/stats`；代码：[AaStatusChangeStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:73)。
- 信息：累计、在途待审、待生效、已生效、类型/状态分布。
- 布局：范围一行→紧凑四指标→图表与可点击明细；未知类型不删。
- 操作：按类型/状态查看同范围明细。
- 状态与恢复：无可靠学期归属不编造学期趋势；详情条件跟随图表且返回保留。
- 本轮证据：[B-30.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-30.png)：已查看；累计范围与未知类型区分合理；统计范围说明压成一行，保留同范围下钻。

#### B-02-35 转班申请

- 入口：`/admin/academic-affairs/status-changes/transfer-class`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:66)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-31.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-31.png)：已查看；空态避免鼓励造申请，保留同专业转班条件在表单。

#### B-02-36 保留学籍申请

- 入口：`/admin/academic-affairs/status-changes/preserve`；代码：[AaStatusChangeTypedListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeTypedListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:67)。
- 信息：学生/学号、异动类型、前后状态或专业班级、审批节点、申请状态、计划日期。
- 布局：筛选→本页统计→队列；移除重复台账标题；转专业/转班显示组织变化而非仅相同学籍状态。
- 操作：发起对应类型申请；行内查看申请。
- 状态与恢复：分类入口锁定原类型；保留学籍不改称留级；空态不引导为填列表创建申请。
- 本轮证据：[B-32.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-32.png)：已查看；当前节点明确，保留学籍与留级不得混称。

#### B-02-37 异动归档

- 入口：`/admin/academic-affairs/status-changes/archive`；代码：[AaStatusChangeArchiveView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaStatusChangeArchiveView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:74)。
- 信息：原申请结果、学生、类型、日期、封存状态、材料版本。
- 布局：标题下保留原记录回查与正式封存区别；日期中文化，缺封存证据显示待查询。
- 操作：原申请与材料；进入正式归档。
- 状态与恢复：已生效/已驳回不等于已归档；不依据列表终态虚构封存完成。
- 本轮证据：[B-33.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-33.png)：已查看；原记录回查与正式封存区别保留，原始时间转可读时间；不将已生效当已归档。

#### B-02-38 预警扫描与列表

- 入口：`/admin/academic-affairs/warnings`；代码：[AaWarningView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:125)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-34.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-34.png)：已查看；重复来源说明、级别标签挤压、原生按钮风格不一致；保留扫描与跟进分离。

#### B-02-39 预警看板

- 入口：`/admin/academic-affairs/warnings/console?tab=dashboard`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：预警总数（含已关闭）、来源、等级和处理状态分布；最近扫描/规则状态仅在真实返回时显示。
- 布局：统计范围摘要→紧凑指标→分类入口；重复来源解释收纳。
- 操作：进入分类预警或跟进；扫描独立确认。
- 状态与恢复：无记录不等于已扫描或没有风险；统计按同范围，不混累计与在办。
- 本轮证据：[B补06.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补06.png)：总控已补拍稳定首屏，B组已查看；看板在办总数标非已关闭，但与待处理加已关闭合计相等，需核对统计口径/标签；不擅改查询或忽略已关闭。
- 历史证据：[B-35.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-35.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-02-40 学分预警

- 入口：`/admin/academic-affairs/warnings/console?tab=credit`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-36.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-36.png)：已查看；筛选纵向过宽，空态不应建议调阈值制造结果，保留扫描权限。

#### B-02-41 挂科预警

- 入口：`/admin/academic-affairs/warnings/console?tab=fail`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-37.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-37.png)：已查看；列表主体清楚，压缩筛选区并统一风险级别名称，保留逐人跟进。

#### B-02-42 绩点预警

- 入口：`/admin/academic-affairs/warnings/console?tab=gpa`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-38.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-38.png)：已查看；无预警与未扫描需区分，阈值不变。

#### B-02-43 补考重修预警

- 入口：`/admin/academic-affairs/warnings/console?tab=retake`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-39.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-39.png)：已查看；空队列，保留补考重修来源与现有阈值。

#### B-02-44 毕业风险预警

- 入口：`/admin/academic-affairs/warnings/console?tab=graduation`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生/班级、预警来源与原因、等级、责任人、处理状态。
- 布局：条件横向紧凑→名单；扫描动作放表头右侧且保留作用范围；空态只提示查询条件。
- 操作：逐行进入该预警跟进；扫描按原能力控制。
- 状态与恢复：空态不能建议调整阈值制造数据；原学生范围、规则和扫描结果恢复不变。
- 本轮证据：[B-40.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-40.png)：已查看；空队列不代表毕业资格通过，保留与正式预审的区别。

#### B-02-45 预警规则

- 入口：`/admin/academic-affairs/warnings/console?tab=rules`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：规则名称、触发条件、单位、当前值、允许范围、生效时机。
- 布局：规则名说明与输入靠近；每条保存和校验就近显示，维护权限按真实能力提示。
- 操作：保存单条规则，保留扫描独立确认。
- 状态与恢复：不更改阈值/范围/默认值；无权限只读；变更后再扫描的规则保持。
- 本轮证据：[B-41.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-41.png)：已查看；规则单位/触发条件/范围完整保留，缩短标签到输入间距，权限提示按实际能力。

#### B-02-46 预警跟进

- 入口：`/admin/academic-affairs/warnings/console?tab=followup`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生、来源、级别、跟进人、状态；详情含原因、历史、处理意见。
- 布局：条件横向紧凑→队列→详情抽屉；未分配明确写未指派；跟进记录优先于解释。
- 操作：新增跟进为主；指派/提醒/升级/关闭/误报作废为明确次级动作。
- 状态与恢复：关闭、升级、误报原因及审计保留；已关闭不能继续写；提醒确为发送而非查看。
- 本轮证据：[B-42.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-42.png)：已查看；跟进人空值应明确未指派，表格保留来源级别状态和处理入口。

#### B-02-47 预警统计

- 入口：`/admin/academic-affairs/warnings/console?tab=stats`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：预警总数（含已关闭）、来源、等级和处理状态分布；最近扫描/规则状态仅在真实返回时显示。
- 布局：统计范围摘要→紧凑指标→分类入口；重复来源解释收纳。
- 操作：进入分类预警或跟进；扫描独立确认。
- 状态与恢复：无记录不等于已扫描或没有风险；统计按同范围，不混累计与在办。
- 本轮证据：[B-43.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-43.png)：已查看；当前页面标签写在办，但后端包含已关闭；改为预警总数（含已关闭），分布口径常显，提供已有分类页跳转。

#### B-02-48 预警通知

- 入口：`/admin/academic-affairs/warnings/console?tab=notify`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：学生、预警来源、级别、接收对象、标题、触发场景、已读状态、发送时间。
- 布局：紧凑计数→通知列表；触发机制放折叠说明；时间统一格式。
- 操作：仅查看，不新加群发或补发。
- 状态与恢复：通知数不等于学生数；未读事实保留，查看不得改变接收人状态。
- 本轮证据：[B-44.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-44.png)：已查看；通知时间原始格式需统一，累计通知与未读状态保留，说明收纳。

### 07 日常教学（13项）

#### B-07-01 调停课台账

- 入口：`/admin/academic-affairs/schedule-change`；代码：[AaScheduleChangeLedgerView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeLedgerView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:149)。
- 信息：学期、课程/班级/教师、类型、原→目标、状态。
- 布局：学期类型状态同排→列表；原目标对照保留；台账说明压缩。
- 操作：详情、通知单；发起申请/审批工作台。
- 状态与恢复：只能按原状态撤销；已生效不可通过本页删除安排，返回保持范围。
- 本轮证据：[B-45.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-45.png)：已查看；列表原课位→目标清楚，顶部重复台账说明可缩短，通知单与状态保留。

#### B-07-02 调停课申请

- 入口：`/admin/academic-affairs/schedule-change/apply`；代码：[AaScheduleChangeApplyView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeApplyView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:150)。
- 信息：原课程/教学班/教师、时间周次教室；目标课位、原因、冲突结果。
- 布局：未选课位只留一个主选择动作；选后原/目标并排，冲突紧邻提交；参考步骤折叠。
- 操作：从正式课位选择；预检后提交；结果未知去原台账查询。
- 状态与恢复：本人成立关系及学院协助候选先对账；不改审批顺序、不让用户输入内部编号。
- 本轮证据：[B-46.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-46.png)：已查看；原课位未选时保留一个主选择入口，流程可折叠，技术编号解释移除；学院协助候选待基线整合。

#### B-07-03 调停课审批

- 入口：`/admin/academic-affairs/schedule-change/approval`；代码：[AaScheduleChangeApprovalView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeApprovalView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:151)。
- 信息：课程、班级教师、类型、原→目标、当前节点、材料与意见。
- 布局：筛选→待审队列→单据对照/证据→审核动作；删除分页实现说明。
- 操作：查看证据与办理；原通过/驳回确认。
- 状态与恢复：通过时重新核对冲突/责任/版本；学院通过与最终课表生效分开。
- 本轮证据：[B-47.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-47.png)：已查看；待审节点与原目标对照清楚；页内分页实现说明删除，保留证据后办理。

#### B-07-04 调停课通知（隐藏关联）

- 入口：`/admin/academic-affairs/schedule-change`；代码：[AaScheduleChangeLedgerView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeLedgerView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:149)。
- 信息：学期、课程/班级/教师、类型、原→目标、状态。
- 布局：学期类型状态同排→列表；原目标对照保留；台账说明压缩。
- 操作：详情、通知单；发起申请/审批工作台。
- 状态与恢复：只能按原状态撤销；已生效不可通过本页删除安排，返回保持范围。
- 本轮证据：[B-45.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-45.png)：已查看；列表原课位→目标清楚，顶部重复台账说明可缩短，通知单与状态保留。

#### B-07-05 调停课冲突检测（隐藏关联）

- 入口：`/admin/academic-affairs/schedule-change/apply`；代码：[AaScheduleChangeApplyView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeApplyView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:150)。
- 信息：原课程/教学班/教师、时间周次教室；目标课位、原因、冲突结果。
- 布局：未选课位只留一个主选择动作；选后原/目标并排，冲突紧邻提交；参考步骤折叠。
- 操作：从正式课位选择；预检后提交；结果未知去原台账查询。
- 状态与恢复：本人成立关系及学院协助候选先对账；不改审批顺序、不让用户输入内部编号。
- 本轮证据：[B-46.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-46.png)：已查看；原课位未选时保留一个主选择入口，流程可折叠，技术编号解释移除；学院协助候选待基线整合。

#### B-07-06 调停课统计

- 入口：`/admin/academic-affairs/schedule-change/stats`；代码：[AaScheduleChangeStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:153)。
- 信息：学期范围、申请数、待办数、完成比例、学院分布、教师频次。
- 布局：范围移出数字卡改筛选摘要；三指标横排；教师长名称可完整查看，学期ID改学期。
- 操作：进入关联台账并携带学期；返回保留筛选。
- 状态与恢复：次数不作绩效结论；分母及状态口径保留；C组统计入口共享此页。
- 本轮证据：[B-48.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-48.png)：已查看；学期ID改学期，范围移到筛选摘要不作大数字卡，长教师名应可完整查看。

#### B-07-07 调停课归档

- 入口：`/admin/academic-affairs/schedule-change/archive`；代码：[AaScheduleChangeArchiveView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaScheduleChangeArchiveView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:154)。
- 信息：课程、原/目标、终态、发起时间、通知单。
- 布局：去掉与对象无关的固定归档阶段；学期主键输入改已有学期选择器；时间可读。
- 操作：查看详情/通知单；返回台账。
- 状态与恢复：终态记录不是正式封存证明；历史课表、审核与更正保护保留。
- 本轮证据：[B-49.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-49.png)：已查看；固定归档阶段与终态列表混淆，学期主键输入改现有学期选择器，发起时间统一格式。

#### B-07-08 课堂考勤

- 入口：`/admin/academic-affairs/attendance-stats`；代码：[AaAttendanceStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaAttendanceStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:124)。
- 信息：学期、班级、点名类别；场次视图课程/班级名称/日期/状态；汇总视图出勤迟到旷课请假。
- 布局：同一筛选栏切场次/汇总；压缩两处相同口径提示；场次与班级内部编号改业务名称。
- 操作：查看课次名单；本人任课关系允许时点名提交；扫描独立。
- 状态与恢复：正式课堂与特殊补录分开；提交前未点名人数保留；迟到响应不串场次。
- 本轮证据：[B-50.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-50.png)：已查看；正式课堂与补录范围说明重复，合为筛选摘要；考勤汇总及扫描权限保留。

#### B-07-09 考勤场次查询

- 入口：`/admin/academic-affairs/attendance-stats?panel=sessions`；代码：[AaAttendanceStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaAttendanceStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:124)。
- 信息：学期、班级、点名类别；场次视图课程/班级名称/日期/状态；汇总视图出勤迟到旷课请假。
- 布局：同一筛选栏切场次/汇总；压缩两处相同口径提示；场次与班级内部编号改业务名称。
- 操作：查看课次名单；本人任课关系允许时点名提交；扫描独立。
- 状态与恢复：正式课堂与特殊补录分开；提交前未点名人数保留；迟到响应不串场次。
- 本轮证据：[B-51.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-51.png)：已查看；场次ID/班级ID外露，改课程日期班级业务名称；任课关系与提交检查保留。

#### B-07-10 按点名类别统计（隐藏关联）

- 入口：`/admin/academic-affairs/attendance-stats`；代码：[AaAttendanceStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaAttendanceStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:124)。
- 信息：学期、班级、点名类别；场次视图课程/班级名称/日期/状态；汇总视图出勤迟到旷课请假。
- 布局：同一筛选栏切场次/汇总；压缩两处相同口径提示；场次与班级内部编号改业务名称。
- 操作：查看课次名单；本人任课关系允许时点名提交；扫描独立。
- 状态与恢复：正式课堂与特殊补录分开；提交前未点名人数保留；迟到响应不串场次。
- 本轮证据：[B-50.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-50.png)：已查看；正式课堂与补录范围说明重复，合为筛选摘要；考勤汇总及扫描权限保留。

#### B-07-11 旷课预警联动

- 入口：`/admin/academic-affairs/warnings/console?tab=dashboard`；代码：[AaWarningConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaWarningConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:127)。
- 信息：预警总数（含已关闭）、来源、等级和处理状态分布；最近扫描/规则状态仅在真实返回时显示。
- 布局：统计范围摘要→紧凑指标→分类入口；重复来源解释收纳。
- 操作：进入分类预警或跟进；扫描独立确认。
- 状态与恢复：无记录不等于已扫描或没有风险；统计按同范围，不混累计与在办。
- 本轮证据：[B补06.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补06.png)：总控已补拍稳定首屏，B组已查看；看板在办总数标非已关闭，但与待处理加已关闭合计相等，需核对统计口径/标签；不擅改查询或忽略已关闭。
- 历史证据：[B-35.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-35.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-07-12 教室预约

- 入口：`/admin/academic-affairs/classroom-bookings`；代码：[AaClassroomBookingView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaClassroomBookingView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:139)。
- 信息：日期、资源名称/容量、节次占用、已批准/待核对；当日申请状态。
- 布局：日期→占用矩阵→预约记录；保留未映射风险，技术说明折叠；编号默认不露。
- 操作：选择具体资源节次申请；按权限审批/驳回/取消。
- 状态与恢复：未发现占用不是可用许可；维修、借用规则、场地关联和重新校验均保留。
- 本轮证据：[B-52.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-52.png)：已查看；占用网格保留，资源编号及三处技术说明收纳；待核对不能当空闲。

#### B-07-13 实训室预约

- 入口：`/admin/academic-affairs/resources/lab-bookings`；代码：[AaLabBookingView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaLabBookingView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:143)。
- 信息：日期、资源名称/容量、节次占用、已批准/待核对；当日申请状态。
- 布局：日期→占用矩阵→预约记录；保留未映射风险，技术说明折叠；编号默认不露。
- 操作：选择具体资源节次申请；按权限审批/驳回/取消。
- 状态与恢复：未发现占用不是可用许可；维修、借用规则、场地关联和重新校验均保留。
- 本轮证据：[B-53.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-53.png)：已查看；实训室缺场地映射警告保留；申请仍需审核，不把待核对显示空闲。

### 10 毕业管理（15项）

#### B-10-01 毕业预审

- 入口：`/admin/academic-affairs/graduation`；代码：[AaGraduationBatchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationBatchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:128)。
- 信息：批次名称、年级、学期、学生数、预审结论、当前阶段。
- 布局：批次列表优先，审核批次页四指标紧凑化；缺历史学期显示待核对。
- 操作：继续预审、查看结果；按状态进入归档结果。
- 状态与恢复：不伪造学期；新批次需原前置条件，系统预审不代替学院/终审。
- 本轮证据：[B-54.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-54.png)：已查看；预审批次列表简洁，历史学期缺失如实保留，继续预审与查看结果需清楚区分。

#### B-10-02 审核批次

- 入口：`/admin/academic-affairs/graduation?tab=batches`；代码：[AaGraduationBatchView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationBatchView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:128)。
- 信息：批次名称、年级、学期、学生数、预审结论、当前阶段。
- 布局：批次列表优先，审核批次页四指标紧凑化；缺历史学期显示待核对。
- 操作：继续预审、查看结果；按状态进入归档结果。
- 状态与恢复：不伪造学期；新批次需原前置条件，系统预审不代替学院/终审。
- 本轮证据：[B-55.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-55.png)：已查看；当前页人数口径保留，压缩四卡让批次队列前移。

#### B-10-03 毕业学生名单

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=roster`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：毕业/结业/延毕三类名单；学号姓名、学院专业班级。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-56.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-56.png)：已查看；批次摘要、阶段条和页签占半屏，合并为紧凑批次栏；毕业/结业/延毕分类保留。

#### B-10-04 学分达成审核

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=credit`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：已得学分/要求学分、判断结果、供数责任。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-57.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-57.png)：已查看；学生证据区被重复总览推后，压缩顶部；学分当前值/要求值及来源责任保留。

#### B-10-05 课程达成审核

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=course`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：必修通过与选修学分两类证据，各自分页；选修要求缺失显示缺数据，保留系统异常和来源责任入口，不视作零要求或通过。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B补07.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补07.png)：总控已补拍稳定首屏，B组已查看；课程达成有真实系统异常及选修要求缺数据，应保留阻断与来源入口；批次总览/步骤条/队列信息层叠可压缩。
- 历史证据：[B-58.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-58.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-10-06 实践环节审核

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=practice`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：实践环节要求、实际完成、缺证据原因。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-59.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-59.png)：已查看；缺实践学分依据明确，保留责任模块入口；顶部信息应压缩。

#### B-10-07 毕设状态联动

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=thesis`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：毕设台账状态、来源对象、缺失原因。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-60.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-60.png)：已查看；毕设台账缺失与不通过区别保留；缺台账引导只能指向有权岗位。

#### B-10-08 实习状态联动

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=internship`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：实习台账、成绩归档与有效合规材料、来源对象。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-61.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-61.png)：已查看；实习证据不通过与责任名称需核对来源；不得把缺证据改通过。

#### B-10-09 费用结清（待接入）

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=fee`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：费用核验状态、人工核验结果、未对接边界。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-62.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-62.png)：已查看；未接入财务显示缺数据且本项不阻断，保留原规则和人工标记边界。

#### B-10-10 处分状态联动

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=discipline`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：处分台账与结果，缺台账不能当无处分。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-63.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-63.png)：已查看；无台账导致不能核验，不能显示无处分；来源模块入口保留。

#### B-10-11 毕业资格终审

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=final`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：学生、十一项证据、学院初审、终审结论和确认。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-64.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-64.png)：已查看；无待终审名单合理，终审不可逆和学院初审前置警告必须常显。

#### B-10-12 不通过原因

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=reason`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：系统异常、学院驳回、延毕原因分别统计与分页。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-65.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-65.png)：已查看；系统异常、人工驳回、延毕分类需独立计数，不合并成同一不通过状态。

#### B-10-13 审核结果

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=results`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：系统预审、当前审核状态、终审结论和详情。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-66.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-66.png)：已查看；系统预审/学院退回/终审结论区分正确，合并重复总览让结果先出现。

#### B-10-14 毕业证书管理

- 入口：`/admin/academic-affairs/certificates`；代码：[AaCertificateView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaCertificateView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:56)。
- 信息：学生/学号、证书业务编号、类型、生成/发放/作废状态、来源批次。
- 布局：筛选与证书表前移；去掉全页固定完成阶段；保留一行状态汇总和必要不可逆提示。
- 操作：按正式终审生成、登记发放、作废；查询原操作结果。
- 状态与恢复：证书编号/电子注册号为业务标识保留；作废不删除、不复用编号；结果未知禁止重复生成。
- 本轮证据：[B-67.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-67.png)：已查看；证书列表被三层摘要推后，状态汇总压缩；正式终审来源、作废不可复用及回执保留。

#### B-10-15 审核归档

- 入口：`/admin/academic-affairs/graduation/audit-console?tab=archive`；代码：[AaGraduationAuditConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:131)。
- 信息：可归档正式结论、已归档结果、排除的延毕/退回项。
- 布局：批次选择+学期/状态紧凑一栏→本页对象队列/表格→对应证据或动作；阶段图默认折叠，重复责任摘要合并。
- 操作：按本页现有能力查看证据/责任模块；终审和归档保留确认与不可逆警告。
- 状态与恢复：切页签保留批次；切批次清旧学生证据；待处理/缺证据不等于不通过；费用原不阻断规则不改。
- 本轮证据：[B-68.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-68.png)：已查看；无可归档结果时归档动作仍显，设计按现有资格禁用并说明原因，保留延毕不归本批边界。

### 12 教学资源（7项）

#### B-12-01 教室资源

- 入口：`/admin/academic-affairs/classrooms`；代码：[AaClassroomListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaClassroomListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:138)。
- 信息：楼栋楼层、教室名称编号、类型、教学/考试容量、状态和用途限制。
- 布局：保留楼栋目录＋教室卡片/台账切换；仅压缩重复引导，已有合理布局不重做。
- 操作：新建楼栋/单间、导入；详情中编辑/课表/维修。
- 状态与恢复：教室可用不等于当时段空闲；容量、唯一编号、楼栋历史归并保护不改。
- 本轮证据：[B-69.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-69.png)：已查看；楼栋/状态/容量/卡片结构可保留；资源可用不等于时段空闲的提示必须保留。

#### B-12-02 实训室资源

- 入口：`/admin/academic-affairs/resources/labs`；代码：[AaLabResourceListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaLabResourceListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:141)。
- 信息：资源业务编号、名称、类型/位置、容量或数量、责任人、状态。
- 布局：筛选同排→资源表；编辑为主、状态/删除归更多；未知历史类型只显示待核对，原码归实施说明。
- 操作：编辑/关联场地或位置；按现有能力维护状态。
- 状态与恢复：不猜历史类型、不改真实编号；缺场地映射不能直接批准预约；维修联动保持。
- 本轮证据：[B-70.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-70.png)：已查看；筛选区过高、历史类型露原码，状态动作集中到更多；未知历史类型不猜映射。

#### B-12-03 设备资源

- 入口：`/admin/academic-affairs/resources/equipment`；代码：[AaEquipmentListView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaEquipmentListView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:142)。
- 信息：资源业务编号、名称、类型/位置、容量或数量、责任人、状态。
- 布局：筛选同排→资源表；编辑为主、状态/删除归更多；未知历史类型只显示待核对，原码归实施说明。
- 操作：编辑/关联场地或位置；按现有能力维护状态。
- 状态与恢复：不猜历史类型、不改真实编号；缺场地映射不能直接批准预约；维修联动保持。
- 本轮证据：[B-71.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-71.png)：已查看；资产编号为业务编号保留，筛选压缩、状态动作归更多；未分配位置规则保留。

#### B-12-04 资源占用

- 入口：`/admin/academic-affairs/resources/occupancy`；代码：[AaResourceOccupancyView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaResourceOccupancyView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:144)。
- 信息：日期、资源、节次、预约/正式课表来源、对象、精确匹配状态。
- 布局：筛选→未映射警告→结果表；技术来源卡默认折叠，内部编号不常显。
- 操作：核对正式课位，按原身份返回来源位置。
- 状态与恢复：同正式场地+日期+节次才匹配；空结果不构成预约许可；不新增改课或批准入口。
- 本轮证据：[B-72.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-72.png)：已查看；技术来源三卡与底注重复，保留未映射警告并让占用表前移；内部编号默认不显示。

#### B-12-05 资源冲突

- 入口：`/admin/academic-affairs/resources/conflicts`；代码：[AaResourceConflictView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaResourceConflictView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:145)。
- 信息：日期、资源、节次、预约/正式课表来源、对象、精确匹配状态。
- 布局：筛选→未映射警告→结果表；技术来源卡默认折叠，内部编号不常显。
- 操作：核对正式课位，按原身份返回来源位置。
- 状态与恢复：同正式场地+日期+节次才匹配；空结果不构成预约许可；不新增改课或批准入口。
- 本轮证据：[B-73.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-73.png)：已查看；来源技术卡可折叠，未映射风险不可折叠，空结果不得显示可预约。

#### B-12-06 资源维修

- 入口：`/admin/academic-affairs/resources/repairs`；代码：[AaResourceRepairView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaResourceRepairView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:146)。
- 信息：资源名称、故障、报修人/时间、维修状态、记录与恢复时间。
- 布局：筛选紧凑→待领取/处理中/已关闭看板；责任解释简化；时间可读且保留异常警告。
- 操作：登记报修、领取、完成、取消；查询原结果。
- 状态与恢复：多未结工单影响资源恢复的规则不变；异常历史日期不改写；写入结果同时核对资源状态。
- 本轮证据：[B-74.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-74.png)：已查看；恢复早于报修的警告应保留；时间可读化，责任说明卡压缩；不改异常历史数据。

#### B-12-07 资源统计

- 入口：`/admin/academic-affairs/resources/stats`；代码：[AaResourceStatsView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaResourceStatsView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:147)。
- 信息：资源数量/可用率、预约与维修数量、状态分布、统计范围。
- 布局：范围与口径合一行，六项指标紧凑分组→状态明细；不制造无来源趋势。
- 操作：进入资源目录/占用/维修台账。
- 状态与恢复：资源数量不是单件设备数量的任意转换；可用率不称空闲率；缺返回值不填0。
- 本轮证据：[B-75.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-75.png)：已查看；数量/比例口径保留，六卡紧凑排列减少留白，资源可用率不叫空闲率。

### 15 教务归档（6项）

#### B-15-01 归档与封存

- 入口：`/admin/academic-affairs/archive`；代码：[AaArchiveConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:178)。
- 信息：学期批次、真实状态、十三域结论、缺项、封存时间、纠错版本。
- 布局：批次队列→状态/范围紧凑摘要→当前可办动作→数据域→纠错；已归档不提示先检查。
- 操作：未封存：检查/按原条件确认；已封存：历史查看/独立纠错。
- 状态与恢复：批量入口仅现有单学期数据域，不能假定跨学期能力；不可解冻、双人纠错和原版本保存不变。
- 本轮证据：[B-76.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-76.png)：已查看；已归档仍提示先检查，须按当前状态显示下一步；不可解冻和独立纠错保护保留。

#### B-15-02 归档缺失提醒

- 入口：`/admin/academic-affairs/archive/precheck`；代码：[ArchivePrecheckView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/ArchivePrecheckView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:179)。
- 信息：学期、十三域结论、阻断/待处理/通过/不适用、责任与去处理入口。
- 布局：学期筛选→结论摘要→阻断/待处理优先→通过项折叠；不展示两块相同结论。
- 操作：去处理对应业务并保留学期；重新检查。
- 状态与恢复：待处理和缺映射不能通过；学院仅实时预检，不代学校封存。
- 本轮证据：[B补08.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/R/B补08.png)：总控已补拍稳定首屏，B组已查看；缺失提醒有真实多域阻断，保留首要处理入口；大摘要/重复计数可压缩，待处理不改成已通过。
- 历史证据：[B-77.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-77.png)：原加载/过渡画面保留追溯，不作为稳定页；该缺口已由上述补拍关闭。

#### B-15-03 批量归档

- 入口：`/admin/academic-affairs/archive?entry=batch`；代码：[AaArchiveConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:178)。
- 信息：学期批次、真实状态、十三域结论、缺项、封存时间、纠错版本。
- 布局：批次队列→状态/范围紧凑摘要→当前可办动作→数据域→纠错；已归档不提示先检查。
- 操作：未封存：检查/按原条件确认；已封存：历史查看/独立纠错。
- 状态与恢复：批量入口仅现有单学期数据域，不能假定跨学期能力；不可解冻、双人纠错和原版本保存不变。
- 本轮证据：[B-78.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-78.png)：已查看；批量入口复用单学期归档，设计明确批量指该学期数据域，不新增跨学期批处理。

#### B-15-04 归档导出

- 入口：`/admin/academic-affairs/archive/export`；代码：[ArchiveExportView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/ArchiveExportView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:180)。
- 信息：已封存批次、范围/类别、用途、物料、下载历史与结果。
- 布局：批次选择→范围用途→申请动作→物料/历史；三种范围说明默认折叠。
- 操作：申请完整导出或单域下载；查询原结果。
- 状态与恢复：用途必填、水印、审计、权限和冻结物料保持；未知结果不重复生成。
- 本轮证据：[B-79.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-79.png)：已查看；导出范围与用途保留；三种范围长说明按需展开，未执行导出。

#### B-15-05 计划归档（隐藏关联）

- 入口：`/admin/academic-affairs/archive`；代码：[AaArchiveConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:178)。
- 信息：学期批次、真实状态、十三域结论、缺项、封存时间、纠错版本。
- 布局：批次队列→状态/范围紧凑摘要→当前可办动作→数据域→纠错；已归档不提示先检查。
- 操作：未封存：检查/按原条件确认；已封存：历史查看/独立纠错。
- 状态与恢复：批量入口仅现有单学期数据域，不能假定跨学期能力；不可解冻、双人纠错和原版本保存不变。
- 本轮证据：[B-76.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-76.png)：已查看；已归档仍提示先检查，须按当前状态显示下一步；不可解冻和独立纠错保护保留。

#### B-15-06 教学任务归档（隐藏关联）

- 入口：`/admin/academic-affairs/archive`；代码：[AaArchiveConsoleView.vue](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/views/AaArchiveConsoleView.vue:1)；路由 [academic-affairs.routes.js](C:/Users/10850/Desktop/职校学生全生命周期系统/frontend/src/modules/academicAffairs/academic-affairs.routes.js:178)。
- 信息：学期批次、真实状态、十三域结论、缺项、封存时间、纠错版本。
- 布局：批次队列→状态/范围紧凑摘要→当前可办动作→数据域→纠错；已归档不提示先检查。
- 操作：未封存：检查/按原条件确认；已封存：历史查看/独立纠错。
- 状态与恢复：批量入口仅现有单学期数据域，不能假定跨学期能力；不可解冻、双人纠错和原版本保存不变。
- 本轮证据：[B-76.png](C:/Users/10850/AppData/Local/Temp/academic-design15-20261025/B/B-76.png)：已查看；已归档仍提示先检查，须按当前状态显示下一步；不可解冻和独立纠错保护保留。

### 共用状态与返回规范

- 读取中显示单一加载区；读取失败保留筛选并给重试；成功空结果才能显示暂无记录。页面换对象立即清掉旧详情，失败不得借旧数据填满。
- 表单校验在字段附近说明原因；提交中禁用重复操作；版本冲突和拒绝保留输入；结果未知锁定原对象并提供“查询办理结果”，不自动重发。
- 返回使用现有来源令牌/路由状态，携带批次、学期、筛选和页码；失效返回本模块合法列表，不根据任意网址跳转。
- 列表行必须以业务对象的真实字符串标识绑定；学生跨批次记录用复合身份，不改变原后端范围。
- 电脑表格保留必要宽度并内部横向滚动；窄屏条件换行，摘要压缩，操作不覆盖正文。375/390/430像素仍待实际复验，不凭源码媒体查询算通过。
- 当前选中对象的突出样式与按钮对象必须一致。允许明确高亮首项作为队列默认选择，但不能在没有选择语义的全列表顶部假称“当前对象”。

## 5. 三级菜单之外必须连带审计的详情/表单/弹窗

| 对象 | 组件/入口 | 设计与验证 |
|---|---|---|
| 学籍档案 | AaRosterDetailView.vue；roster/:studentId | 当前身份、组织和状态→历史时间线→注册/异动入口；证件默认脱敏，不能为审计揭示完整证件 |
| 注册名单 | AaRegistrationDetailView.vue、AaRegistrationBulkPanel.vue | 当前批次名称→候选学生→预览结果→确认；保留100人上限、失败名单与原结果恢复；不实际注册 |
| 注册批次创建/关闭/归档 | AaRegistrationBatchListView.vue抽屉/确认框 | 类型入口保持锁定；确认框有批次、人数影响和状态；未知结果先查询 |
| 更正发起/审核 | AaRosterCorrectionListView.vue抽屉 | 学生→字段原新值→原因材料；敏感字段不明文扩散；审核材料检查和版本一致 |
| 分流批次详情 | AaMajorSplitView.vue内详情 | 批次摘要→专业容量→志愿/分配→确认结果；不可将已确认批次显示为创建中 |
| 异动详情与材料 | AaStatusChangeDetailView.vue、StatusChangeReview.vue、打印路由 | 原/目标对照→当前节点→材料→处理历史→正式结果；未来生效单独展示；打印不绕过权限 |
| 预警跟进抽屉 | AaWarningConsoleView.vue | 学生/风险原因→责任人→跟进历史→新增记录；升级、关闭、误报独立确认；提醒不能伪装只读 |
| 调停课详情/通知单 | components/parallel-b/ScheduleChangeEvidence.vue（台账内详情）及打印路由 | 原目标、审批记录、结果和通知状态同对象核对；不重新发消息 |
| 考勤场次名单 | AaAttendanceStatsView.vue内详情 | 课程日期教学班→名单点名状态→未点名计数→提交；不得用管理员模拟任课关系 |
| 预约申请/审核 | ResourceBookingWorkspace.vue抽屉 | 资源、日期、节次、用途和结果；缺场地/维修/冲突提示就近，结果未知恢复 |
| 毕业结果详情/终审 | AaGraduationResultView.vue及AuditConsole弹窗 | 十一项证据→学院意见→终审结论确认；源数据链接保持同学生，取消不清空待填意见 |
| 证书生成/发放/作废 | AaCertificateView.vue抽屉/确认 | 正式终审批次→证书范围→确认；证书号是业务编号不得删除；作废原因不少于原限制 |
| 资源编辑/场地绑定 | 教室、实训室、设备表单与详情 | 表单分对象身份、容量/用途、位置/责任、状态；保留业务编码、精确场地绑定及既有占用保护 |
| 维修报修/完成/取消 | AaResourceRepairView.vue | 资源及故障、处理意见、恢复结果；多个未结工单不能被一个完成动作覆盖 |
| 归档批次/纠错/下载 | AaArchiveConsoleView.vue、AaArchiveCorrectionWorkspace.vue、ArchiveExportView.vue | 原封存版本只读；纠错独立记录、不同操作人复核；导出用途与回执保留 |

以上关联页已完成源码定位和设计约束，未逐一进入所有具体对象/弹窗；不计为全部页面状态浏览器验收完成。

## 6. 实际请求链和共享归属

后端正式挂载证据为 `backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py`：117–135行挂载名册注册、便利性和异动；153–174行挂载调停课、毕业、预警、归档。本文不依据遗留大路由函数名断言最终实现。

| 业务 | 已核真实入口/请求 | 保持的责任边界 |
|---|---|---|
| 名册与注册 | 前端academic-affairs.api.js:212–350；roster_registration_router.py:55、104、135；注册便利性路由独立挂载 | 核验/暂缓/异常/注册不能合为一个“完成”动作；批量确认复用既有正式注册写入 |
| 学籍异动 | status_change_router.py:32、37、52、57；便利性/计划生效独立router | 列表、详情、审批复用change_service；计划生效与即时生效保持同一正式状态写入约束 |
| 调停课 | schedule_change_router.py；前端academic-schedule-change.api.js与ScheduleChangeEvidence.vue | B组拥有台账/申请/审批/统计，C组只维护统计目录跳入与返回，不改这组页面 |
| 预警 | warning_core_router.py:11；AaWarningConsoleView.vue、AaWarningView.vue | B组拥有预警；成绩/考勤只提供来源关系，不能各造规则和跟进页面 |
| 毕业 | graduation_core_router.py:12；academic-affairs.api.js:872–909 | 证据由各正式业务供给，B组不修对方数据为“通过”；费用等业务默认值保持 |
| 资源与预约 | teaching_resource_router.py:17–35；ResourceBookingWorkspace.vue:58 | 台账/预约/维修复用资源服务与场地绑定，A组课表只提出返回与占用需求 |
| 教务归档 | archive_core_router.py:39–87；AaArchiveConsoleView.vue:243以后 | B组拥有共用归档；A组计划和任务归档入口只引用原能力，不重建已退役门面 |

共享导航/权限/公共样式由总控持有。B组默认不新增接口、不改结构或权限；名称等确需后端补齐的缺口按正式对象查询最小补充，不以页面样例数据替代。

## 7. 待施工的验证矩阵（本轮未运行）

| 设计包 | 正向验证 | 反向/恢复验证 | 复用现有测试方向 |
|---|---|---|---|
| 学籍名册与结果 | 第二行姓名进入同一学生，状态分类正确，原新值业务名称可读 | 空列表无首行动作；未映射类型不误判；时间原值不改 | academic-affairs-status-change-supporting-surfaces-contract、future-effective-display |
| 注册 | 全局检索及批次返回正确，预览结果和正式回读一致 | 跨批次同学生不丢；迟到响应不覆盖；有效暂缓排除；撤权拒绝 | academic-registration-context/concurrency/eligibility-runtime/other-queues及候选MySQL专项 |
| 异动与更正 | 材料、前后状态、审批、生效与档案一致 | 未来未到期不生效；材料未安全/版本冲突拒绝；保留意见；未知结果不重发 | academic-status-change-decision-version、materials-contract、parallel-c-status-change |
| 预警 | 分类进入同预警，跟进人和记录回读 | 空态不建议改规则；无处理权无动作；关闭后不可新增；扫描未知结果恢复 | academic-pc-parallel-c-warning-scan、warning-graduation-action-receipt |
| 调停课与考勤 | 同课位对照/审批记录；同课次名单与统计衔接 | 非任课关系拒绝；冲突拒绝；提交中不可切对象；未知结果锁定 | 现有调停课与正式考勤相关前后端检查 |
| 毕业与证书 | 同批次同学生证据→当前状态→终审结论→证书 | 缺证据不通过；财务缺失仍按原政策；终审防重复；作废编号不复用 | academic-graduation-evidence-behavior/upstream-navigation；test_aa_graduation* |
| 资源 | 业务名称、占用来源、维修结果与可用状态一致 | 未映射不是空闲；维修时间异常保留；多个未结工单不能提前恢复 | 教学资源正式路由/范围/预约与并发相关检查 |
| 归档 | 十三域检查、缺项跳转、封存物料及日志一致 | 待处理不封存；已封存不能普通解冻；双人纠错；导出未知恢复 | academic-archive-confirm-action-v5/correction/v5-scope；test_aa_archive* |

源码/文档检查无需数据库。本轮没有运行上述测试；后续由总控按已授权隔离库串行执行，不能三组同时跑pytest。

## 8. 收口边界

本文件已为89条入口确定流程承接、页面信息顺序、主要操作、状态和恢复要求，并补列关联详情/表单。它不宣称所有真实状态和岗位已经验收，也不宣称改版图已实现。

本轮证据仅为学校管理员只读首屏。未执行保存、注册、审批、扫描、通知、归档、导出；未验证指定窄屏、键盘全流程、教师/学院教务/学生身份、全部详情和弹窗。视觉结构调整仍需在总控统一设计图中结合这些真实截图表达，之后才能进入代码施工。
