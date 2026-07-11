# 施工卡 · 学工中心 · 宿舍与公寓（sa-dorm，B 包补强）

> 本文件是**施工任务卡（照着开发用）**，不是本轮实现记录，**只写文档、不改任何代码/navPlan/迁移**。
> 模块 key：`sa-dorm`（navPlan `mod('sa-dorm', '宿舍与公寓', …)`，见 `frontend/src/config/navPlan.js` L129-132）。
> 权限 moduleKey：`studentAffairs`；页面 menuKey 前缀：`studentAffairs.dorm.*`。
> 编写口径遵循 CLAUDE.md §0.0（市场验证优先与成熟商业系统复刻规则）、§40/§41（公共组件强制调用）、§38（Excel 正式导入导出）、§36（MySQL-only）、§6（敏感与审计）。
> **依据全部来自仓库现有文档与现有代码**，读不到的字段/规则一律标「需人工确认」，未凭空发明。关键依据文件与行号见 §13。

---

## 0. 核心事实核对（开工前必读，防止重复造轮子）

本模块**后端已大量落地，前端页面大部分为 planned**。开工不是从零，而是「补前端 + 硬化/校验已建后端 + 对齐三处文档口径分歧」。

| 事实 | 现状 | 证据 |
|---|---|---|
| 后端房源模型 | **已建**：`t_affairs_dorm_building / _room / _bed`（床位为占用事实源，乐观锁字段待确认） | `backend/app/models/affairs_dorm.py` L17-60 |
| 后端调宿模型 | **已建**：`t_affairs_dorm_transfer`（8 态） | `backend/app/models/affairs_dorm.py` L62-75 |
| 后端检查模型 | **已建**：`t_affairs_dorm_check_task / _check_record`（一房一记录，`student_ids_json` 存夜不归宿名单） | `backend/app/models/affairs_dorm.py` L77-110 |
| 复用旧表 | **已建**：`t_cs_dorm_record`（我的宿舍读链路）、`t_cs_dorm_exception`（异常/夜不归宿） | `backend/app/models/campus_service.py` L76-101 |
| 后端 API | **已建 ~15 个**：楼栋 CRUD/一键铺满/入住/退宿/入住率/自选开关/调宿提交/调宿审批/检查任务/检查记录 | `backend/app/api/v1/student_affairs.py` L799-883 |
| 后端 service | **已建**：`affairs_dorm_service.py`（含 checkin/checkout/transfer/review/check_record/occupancy/回写 t_cs_dorm_record） | `backend/app/services/affairs_dorm_service.py` |
| 迁移 | **已建**：`0008_13a_p6_dorm_archive.py` | `backend/alembic/versions/0008_13a_p6_dorm_archive.py` |
| 前端「入住管理」 | **已实现**：指向旧「宿舍服务」页 `/admin/campus-service/dormitory`（navPlan 标 I） | `frontend/src/config/navPlan.js` L131 |
| 前端 房源/调宿/检查/异常/统计 | **planned**：navPlan 用 `P(...)` 占位，未建真实页 | `frontend/src/config/navPlan.js` L130,L132 |

> **结论**：本卡 6 个三级页中 **1 个已实现（入住管理·旧页）**，其余 5 个页面前端待建，但**后端接口已就绪**（需逐条硬化：权限/数据范围/乐观锁/审计/脱敏是否真到位——见 §6/§7/§8 的「需人工确认」项）。**严禁新建平行 `t_dorm_*` 表**（§9），一律复用上表。

---

## 1. 模块定位与真实学校业务价值

**一句话**：把「学生住哪张床、能不能调宿、寝室查得怎么样、有没有夜不归宿、住宿率多少」变成可核查、可导出、可上报、可追责的「账」，并让夜不归宿自动进入风险中枢。

**真实学校谁用、解决什么**（依据总册 §3.11 ①角色四问 L577）：

| 角色 | 真实场景 | 本模块解决 |
|---|---|---|
| 宿管中心/宿管老师 | 维护楼层房床主数据、按楼查寝打分、登记夜不归宿、执行入住退宿 | 房源三级台账 + 移动查寝录入 + 异常登记 + 入退宿执行 |
| 辅导员 | 学生调宿初审、跟进本班宿舍异常、联系学生/家长 | 调宿初审待办 + 异常同步 + 一键转风险/家校 |
| 学生 | 查我的宿舍/室友、发起调宿、看检查结果 | 学生端「我的宿舍」只读 + 调宿申请 + 进度条（S-08） |
| 学院学工/学工处 | 看全校/本院住宿率、异常趋势、文明寝室、导出台账上报 | 宿舍统计 + 台账导出（水印+审计） |

**为什么不做成自嗨功能**：职校宿舍是学生安全与管理的高频刚需场景（夜不归宿=安全红线）；三家成熟学工产品普遍具备房源-入住-调宿-检查-夜不归宿-统计闭环（依据 §2 对标表）。本模块只补被市场验证的核心闭环，不发明花哨功能。**智能排宿/文明寝室/公寓纪律进补强能力池（§3 标 ☆），非本卡必做。**

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点）

> **对标性质说明**：主依据为仓库《13A-学工中心-商业化对标审计与补丁建议（第一轮）》，该文档已声明对标**正方、强智、青果**等经市场验证的成熟校园学工产品的「产品精华与业务成熟度」（角色分工/流程闭环/批量/台账/权限审计/参数配置/导入导出/打印归档/移动端），**不抄袭界面代码数据库商标**（依据该文件 L8 对标对象声明）。**本代理无联网，未做外部网页检索**；以下三家的「核心流程/字段/亮点/缺点」是**基于该审计文档提炼 + 行业通识归纳**，**具体到某产品的独家字段/独家流程细节标「需人工确认（未联网核证）」**，不编造某产品实际界面。

### ① 对标对象 A：正方（学工/公寓管理方向）
- **核心流程**：校区-楼栋-楼层-房间-床位主数据 → 批量导入分配 → 入住登记 → 调宿/退宿审批 → 查寝检查评分 → 违纪/夜不归宿登记 → 住宿统计报表。
- **角色**：公寓中心管理员、楼栋管理员（宿管）、辅导员、学生。
- **字段**：床位唯一编码、房间性别/容量/房型、入住日期、调宿原因、检查评分项、违规类型。
- **亮点**：与教务学籍库打通（学号→自动带班级/性别）；报表口径成熟、可上报。
- **缺点**：移动查寝早期偏弱；界面偏重管理端，学生端体验一般。
- **来源**：审计文档对标对象声明（L8）+ 行业通识；产品独家细节 **需人工确认（未联网核证）**。

### ② 对标对象 B：强智（学工/公寓管理方向）
- **核心流程**：房源建模 → 智能/手动分配 → 入住 → 调宿退宿工作流 → 卫生检查评比 → 文明寝室评定 → 统计。
- **角色**：宿管中心、楼管员、辅导员、学生、二级学院。
- **字段**：楼栋性别规则、检查评分明细、文明寝室评比批次与累计分、缴费/绿通（与迎新联动）。
- **亮点**：文明寝室评比链路完整（基于检查分累计）；分配支持批量与规则约束。
- **缺点**：调宿并发床位冲突、跨校区规则等边界处理依实施而定；配置项多、实施重。
- **来源**：审计文档（L8、缺口表 L123/L162 提「文明寝室/公寓纪律」）+ 行业通识；独家细节 **需人工确认（未联网核证）**。

### ③ 对标对象 C：青果（学工方向）
- **核心流程**：住宿信息维护 → 入住/调宿 → 查寝记录 → 异常（夜不归宿）预警 → 与辅导员工作/风险联动 → 统计。
- **角色**：学工处、辅导员、宿管、学生。
- **字段**：住宿档案、异常类型（夜不归宿/违规电器等）、处理记录、与学生画像联动的住宿段。
- **亮点**：异常与辅导员日常工作、学生画像联动紧密（学工一体化）。
- **缺点**：公寓侧主数据精细度（床位级）弱于专业公寓系统；移动录入依版本。
- **来源**：审计文档（L8）+ 行业通识；独家细节 **需人工确认（未联网核证）**。

### ④ 三家共同具备的核心功能（=本项目必须具备的基础能力）
1. 房源三级+床位主数据（床位唯一编码、性别/容量规则）；
2. 入住 / 退宿 / 调宿闭环（调宿走审批 + 床位冲突校验）；
3. 宿舍检查（评分项 + 记录 + 异常）；
4. 夜不归宿/违规登记 → 预警/风险联动；
5. 住宿率/异常/检查覆盖率统计与台账导出；
6. 数据范围隔离（宿管按楼栋、辅导员按班、学生本人）。

### ⑤ 三家里最值得吸收的最佳做法
1. **床位为唯一占用事实源 + 唯一编码**（正方口径）——本项目 `t_affairs_dorm_bed` 已按此建（L45-60），最佳做法已落地。
2. **调宿审批「二次校验目标床位仍空」+ 乐观锁防超占**（并发安全）——总册 §3.11 ③-3 已设计，需核验代码是否真加乐观锁（§9 需人工确认）。
3. **夜不归宿→异常→风险自动链路 + 30 天内≥3 次自动升级**（安全闭环）——状态机 §9.2 L389 已设计。
4. **移动端查寝逐房录入**（宿管高频，弱网草稿）——移动端 T-07；对标最强销售项（审计 精华原则 10）。
5. **迎新分宿数据对齐**（building/room 文本→bed_id 映射字典，对不上进人工对账不阻塞上线）——总册 §3.11 ③-1，避免存量数据割裂。

### ⑥ 本项目当前已有能力
见 §0 核对表：后端房源/入住/退宿/调宿/检查/入住率/回写 t_cs_dorm_record 已建；旧「入住管理」页已实现；调宿状态机 8 态、检查异常状态机 5 态已设计（状态机文档 §8/§9）；DORM_BUILDING 数据范围已定义（§14）。

### ⑦ 本项目缺失的生产级闭环（缺口，依据审计 L162-163「宿舍」行）
- 文明寝室评比 / 公寓纪律（标 ☆ 补强包，非本卡必做）；
- 检查移动端录入（标 P2，本卡列为应补，因是宿管最高频移动场景）；
- **宿舍台账导出**（检查导入已列，台账导出未成体系——审计明确核心缺口）；
- 前端 5 个页面（房源/调宿退宿/检查/异常/统计）尚未建真实页。

### ⑧ 本卡必须补齐
1. 前端 5 页：房源管理、调宿与退宿、宿舍检查、宿舍异常（含夜不归宿）、宿舍统计（复用已建后端）；
2. 后端硬化核验：调宿乐观锁/二次校验、DORM_BUILDING 数据范围强校验、审计留痕、检查照片脱敏（§6/§7/§8）；
3. **宿舍台账 Excel 导出**（住宿花名册/检查台账/异常台账，脱敏+水印+审计，接公共底座 §10）；
4. 学生端「我的宿舍 + 调宿」(S-08) 对接（§11）。

### ⑨ 暂进 backlog（补强能力池，本卡不做）
- 11-9 智能排宿（☆，算法接口位 `POST /dorm/allocation/suggest`，无算法人工排宿可跑通——总册 §4.1 L333-336）；
- 11-10 公寓纪律（☆）、11-11 文明寝室评比（☆）；
- 水电/门禁对接、批量迁移向导（DISABLED 房维修）。

### ⑩ 禁止做成假功能（红线）
- 不做「假入住按钮点了不写库」——写操作必须落 MySQL（§36）；
- 不做「假导出弹成功不出文件」——导出走后端真实管线 + t_export_task 留痕（§38、§40 安全红线）；
- 不做「前端隐藏菜单当权限」——DORM_BUILDING 越栋必须后端 403（§6/§18）；
- 检查照片（寝室内景/学生个人物品）**不得**因宿管有普通菜单权限就对无关角色展示（§6）；
- planned 的 ☆ 页（智能排宿/公寓纪律/文明寝室）**不建空页**，走公共规划占位页（CLAUDE.md §42）。

---

## 3. 三级页面清单与状态（对齐施工图 + navPlan + 页面树）

navPlan 现状：`mod('sa-dorm','宿舍与公寓')` 下 = 房源管理(P) + 入住管理(I·旧页) + 调宿与退宿(P) + 宿舍检查(P) + 宿舍异常(P) + 宿舍统计(P)（`navPlan.js` L129-132）。页面树 §3.9（L282-296）给出更细的 11-x 页码。

| 施工图三级页 | 对应页面树页码 | 建议路由 | 状态 | 后端就绪 | 本卡动作 |
|---|---|---|---|---|---|
| 房源管理（楼栋/房间/床位） | 11-1 房源 + 11-2 入住分配 | `/admin/student-affairs/dorm/buildings`、`.../allocation` | **planned·前端待建** | ✅ 已建 | 建前端页，接已建 API |
| 入住管理（现有·宿舍服务） | 承接旧页 | `/admin/campus-service/dormitory` | **已实现（旧页）** | ✅ | 保留兼容；评估是否迁并入 11-2（§14 风险） |
| 调宿与退宿 | 11-3 调宿列表 + 11-4 调宿审批 | `/admin/student-affairs/dorm/transfers`、`.../transfers/:id/approve` | **planned·前端待建** | ✅ 已建 | 建列表+审批双栏页 |
| 宿舍检查 | 11-5 检查任务 + 11-6 记录录入 | `/admin/student-affairs/dorm/inspections`、`.../inspections/:taskId/records` | **planned·前端待建** | ✅ 已建 | 建任务页 + 逐房录入页（移动优先） |
| 宿舍异常（含夜不归宿） | 11-7 异常 | `/admin/student-affairs/dorm/exceptions` | **planned·前端待建** | ✅ 复用 t_cs_dorm_exception | 建异常处置页 |
| 宿舍统计 | 11-8 统计 | `/admin/student-affairs/dorm/stats` | **planned·前端待建** | ✅ `/dorm/occupancy` 已建（其余指标需补） | 建统计页 + 补指标 API |
| （补强）智能排宿 ☆ | 11-9 | `/dorm/smart-allocation` | **planned·占位页** | 接口位 | **不做**，走规划占位页 |
| （补强）公寓纪律 ☆ | 11-10 | `/dorm/rules` | **planned·占位页** | 无 | **不做** |
| （补强）文明寝室 ☆ | 11-11 | `/dorm/civilized` | **planned·占位页** | 无 | **不做** |

> **6 个三级页中 1 已实现（入住管理旧页），5 前端待建、后端已就绪**。路由前缀建议统一到 `/admin/student-affairs/dorm/*`（旧 `/dorm/*`、`/admin/campus-service/dormitory` 保留 redirect/alias 不 404——CLAUDE.md §9.1）。**最终路由前缀需人工确认**（页面树 §3.9 写 `/dorm/*` 简写，实际部署前缀以路由文件为准）。

---

## 4. 业务流程与状态机

> 已实现项标「已实现/已建」，不重复设计；本节汇总权威口径并**标注三处文档 vs 代码的分歧（需人工确认后统一）**。

### 4.1 房源主数据（无审批，直接操作+审计）
- 楼栋 → 楼层 → 房间 → 床位；床位唯一编码；一键铺满（层×每层房数×每间床位）。**已建**（service `create_building/generate_layout` L67-129）。
- 床位状态：`VACANT / OCCUPIED / LOCKED`（代码 L58）。注意：总册用 `VACANT/OCCUPIED/DISABLED`（L618），代码用 `LOCKED`——**枚举分歧，需人工确认统一为 DISABLED 还是 LOCKED**。
- 房间状态：`ENABLED / DISABLED / MAINTAIN`（代码 L40）。

### 4.2 入住 / 退宿（无审批，事务内翻转床位 + 回写 t_cs_dorm_record）
- 入住：`checkin(bed_id, student_id)` → 床位置 OCCUPIED + 写 t_cs_dorm_record（回链 `cs_dorm_record_id`）。**已建**（service L223-251）。
- 退宿：`checkout(bed_id)` → 释放床位。**已建**（L289-309）。
- 学生自选入住：需学校开关放开（`/dorm/config/self-select`），否则 403。**已建**（L282-288）。

### 4.3 调宿状态机（走审批 AFFAIRS_DORM_TRANSFER）
**⚠ 三处口径分歧（必须人工确认后统一，建议以已实现代码为准）：**

| 来源 | 状态枚举 | 中间审核节点名 | 终态 |
|---|---|---|---|
| 总册 §3.11 ⑥ L611 | SUBMITTED/COUNSELOR_REVIEW/**DORM_ADMIN_REVIEW**/APPROVED/RETURNED/REJECTED/CANCELLED | DORM_ADMIN_REVIEW | APPROVED（事务换床） |
| 状态机文档 §8 L337 | SUBMITTED/COUNSELOR_REVIEW/**DORM_REVIEW**/APPROVED/REJECTED/CANCELLED/**COMPLETED**/ARCHIVED | DORM_REVIEW | COMPLETED→ARCHIVED |
| **代码 model L72** | SUBMITTED/COUNSELOR_REVIEW/**DORM_MANAGER_REVIEW**/APPROVED/REJECTED/RETURNED/CANCELLED/**EXECUTED** | DORM_MANAGER_REVIEW | EXECUTED |

- **推荐**：以代码 `DORM_MANAGER_REVIEW / EXECUTED / RETURNED` 为准（已实现、已迁移），把两份文档对齐到代码；**是否对齐、终态命名需人工确认**。
- 流转（权威流程，三处一致部分）：学生发起 → 系统受理（在住校验+在途单拦截，创建流程）→ COUNSELOR_REVIEW（辅导员初审）→ DORM_MANAGER_REVIEW（宿管审，**二次校验目标床位仍 VACANT**，被占退回改选）→ APPROVED → 事务（原床释放+新床占用+更新 t_cs_dorm_record）→ EXECUTED → 360 事件。
- 责任人：辅导员（初审，本班）；宿管（终审，**目标楼栋 DORM_BUILDING**）。
- 超期升级（状态机 §8.2 L360）：DORM_REVIEW 停留 ≥48h → DEADLINE_REMINDER→宿管；APPROVED 后 7 天未执行 → 自动 CANCELLED 释放预留。**是否已实现定时任务，需人工确认**。
- 非法转移防护（§8.1 L353-356）：目标床位并发被占 → 409 DATA_CONFLICT（乐观锁 version，回审核重选）；在途单再发 → 409；越栋审批 → 403 NO_DATA_SCOPE；性别/楼栋不符 → 422。

### 4.4 宿舍检查异常状态机（不走审批，时效优先，全动作留痕）
- 检查任务本身：`DRAFT / RUNNING / DONE / CANCELLED`（代码 task L79；总册用 PLANNED/IN_PROGRESS/DONE——**枚举分歧需人工确认**）。任务=计划+记录，不设审批。
- 检查记录：一房一条（代码 `t_affairs_dorm_check_record`，`result=NORMAL/ABNORMAL`，`student_ids_json` 存夜不归宿名单）。**已建**（service `submit_check_record` L404-450）。
  - ⚠ 分歧：总册 §3.11 ③-4 设计的是 `t_affairs_dorm_inspection` + `_item`（一房多项打分）；**代码实现为单表 check_record（issue_type 一项）**，粒度更粗。是否补 `_item` 明细/多评分项（卫生+安全+违禁+夜不归宿分开），**需人工确认**（影响 §5 表单字段能否逐项打分）。
- 异常（落 t_cs_dorm_exception）状态机（状态机 §9 L364）：`REGISTERED → PROCESSING → (ESCALATED) → CLOSED → ARCHIVED`。
  - 责任人：宿管登记（本楼）→ 辅导员认领处理（本班）→ 严重升级转风险（辅/宿/院）。
  - 自动升级（§9.2 L388-389）：REGISTERED ≥24h 无人认领 → 提醒辅导员；≥48h 自动 ESCALATED 生成风险；**夜不归宿同生 30 天内 ≥3 次 → 自动生成风险 + 升级**。**定时任务是否已实现，需人工确认**。

### 4.5 夜不归宿 → 异常 → 风险自动链路
检查录入或单独登记（type=NIGHT_ABSENT/NIGHT_OUT——代码 `exc_type` 默认 `NIGHT_OUT`，总册用 `NIGHT_ABSENT`，**需人工确认统一**）→ 写 t_cs_dorm_exception → 自动建风险（source_type=DORM_EXCEPTION/DORM，分派宿管+辅导员，见 §3.9 风险）→ 辅导员联系学生/家长 → 风险闭环。**service 已含生成风险逻辑**（model 注释 L91「生成风险 source=DORM」，需核验实际代码 §8）。

---

## 5. 表单字段与校验规则

> 逐字段。**发起端表单（调宿/检查记录）以表单字段文档 §3.13/§3.14 为权威**（含 422 场景）；管理端表单（楼栋/房间/床位）以代码字段为准。敏感级：普通 / 敏感(SEC) / 强敏感(SEC+)。

### 5.1 楼栋 building（管理端·无审批）
| 字段 | 类型 | 必填 | 校验/枚举 | 敏感级 | 来源 |
|---|---|---|---|---|---|
| building_name 楼栋名 | text | 是 | ≤100 字 | 普通 | model L21 |
| building_code 楼栋编码 | text | 否 | ≤50，DORM_BUILDING scope 的 ref 对象（唯一性建议校验） | 普通 | model L22 |
| gender_limit 性别规则 | select | 是 | MALE/FEMALE/MIXED（男寝/女寝/混合） | 普通 | model L23 |
| manager_teacher_key 宿管 | select | 否 | 教师 key（绑定 DORM_BUILDING） | 普通 | model L25 |
| floor_count 层数 | number | 否 | 生成器用，正整数 | 普通 | model L26 |
| status 状态 | select | 是 | ENABLED/DISABLED | 普通 | model L27 |

### 5.2 房间 room / 床位 bed（管理端）
| 字段 | 类型 | 必填 | 校验/枚举 | 来源 |
|---|---|---|---|---|
| room: floor_no 层 | number | 是 | 正整数 | model L34 |
| room: room_no 房号 | text | 是 | 楼栋内唯一（uk_dorm_room_building_no） | model L35,L43 |
| room: capacity 床位数 | number | 是 | 默认 4，正整数 | model L36 |
| room: room_type 房型 | select | 否 | STANDARD/…（枚举需人工确认） | model L37 |
| room: status | select | 是 | ENABLED/DISABLED/MAINTAIN | model L38 |
| bed: bed_no 床号 | text | 是 | 房间内唯一（uk_dorm_bed_room_no），如 512-1 | model L49,L57 |
| bed: status | 系统 | — | VACANT/OCCUPIED/LOCKED（占用由入退宿/调宿翻转，不手改） | model L58 |
| bed: student_id | 系统 | — | 空=空床；由 checkin 写入 | model L50 |

### 5.3 调宿申请 transfer（发起端·表单文档 §3.13 L355 权威）
| 字段 | 类型 | 必填 | 枚举/校验 | 敏感级 | 422 场景 |
|---|---|---|---|---|---|
| current_bed 原床位 | 只读自动带出 | 自动 | 引用 t_cs_dorm_record 当前分配 | 普通 | 无床位记录→422001 current_bed |
| target_building 目标楼栋 | select 三级联动1 | 是 | 按学生性别过滤可选楼栋 | 普通 | 性别不匹配→422001 target_building |
| target_room 目标房间 | select 联动2 | 是 | 所选楼栋下有空床房间 | 普通 | 房间不属楼栋→422001 target_room |
| target_bed 目标床位 | select 联动3 | 是 | 仅列空床 | 普通 | 提交时被占→422001 target_bed；审批时被占→**409001** |
| transfer_reason 原因 | select | 是 | HEALTH/CONFLICT/MAJOR_TRANSFER/SPECIAL_NEED/OTHER | 普通 | 枚举外→422001 |
| reason_detail 说明 | textarea | 是 | L1 10–500 字 | HEALTH 涉病情按敏感，宿管端收敛 | 字数不符→422001 |
| attachments 佐证 | 文件 | HEALTH 必传 | PDF/JPG/PNG ≤10MB ≤3 个，医疗材料预览水印 | 敏感 | HEALTH 未传→422001 |
- 防重复：同学生同时仅一条进行中调宿 → 409001。草稿：不支持。

### 5.4 宿舍检查记录 inspection record（发起端·表单文档 §3.14 L372 权威）
| 字段 | 类型 | 必填 | 枚举/校验 | 敏感级 | 422 场景 |
|---|---|---|---|---|---|
| task_id 检查任务 | 隐藏带入 | 是 | 进行中任务 | 普通 | 任务已关闭→422001 |
| building_id 楼栋 | select | 是 | 本人负责楼栋（DORM_BUILDING） | 普通 | 非负责→403002；不在任务范围→422001 |
| room_id 房间 | select 联动 | 是 | 楼栋下房间，已录标「已检查」 | 普通 | 不属楼栋→422001 |
| hygiene_score 卫生分 | number 0–100 | 是 | 整数区间 | 普通 | 越界→422001 |
| safety_score 安全分 | number 0–100 | 是 | 整数区间 | 普通 | 越界→422001 |
| contraband 违禁品 | radio+说明 | 是 | NONE/FOUND（FOUND 需明细 5–200 字+照片） | 普通 | FOUND 未填明细→422001 |
| absent_students 夜不归宿名单 | 学生多选 | 否 | 仅可选该房间在住学生；联系方式脱敏展示 | **敏感** | 学生不在该房间→422001 |
| photos 照片 | 图片上传 | 异常时必传 | JPG/PNG ≤10MB ≤5 张 | **敏感（寝室内景/个人物品，仅检查链路可见）** | 异常未传→422001 |
| abnormal_level 异常等级 | select | 是 | NORMAL/MINOR/MAJOR/SEVERE（有夜不归宿/FOUND 不可选 NORMAL） | 普通 | 夜不归宿仍选 NORMAL→422001 |
| remark 备注 | textarea | 否 | 0–200 字 | 普通 | 超长→422001 |
- 草稿：不支持（逐房提交）。防重复：同任务+同房间唯一 → 409001。
- 提交后：abnormal_level ≥ MINOR 自动生成异常(11-7)+辅导员待办；SEVERE 或夜不归宿自动生成风险(source=宿舍异常)；进统计与 360。
- ⚠ 代码单表 check_record 是否支持上述「卫生+安全分开打分/多项」需人工确认（§4.4 分歧）。

### 5.5 通用校验（表单文档 §开头 L25/L50）
- L1 文本类 10–500 字；后端幂等：同学生同业务时间区间重叠/在途唯一 → 409001「已存在相同申请」。

---

## 6. 权限矩阵与数据范围

> 引用权限总控《00-系统管理中心-权限角色模块授权与权责边界设计》L266/L365/L421/L463 + 状态机文档 §13 权限矩阵 L522-530 + §14 数据范围 L603-618。**前端负责展示，后端为最终裁定（§18）。**

### 6.1 权限点（menuKey/permissionCode，命名遵循 CLAUDE.md §10）
| permissionCode | 含义 | 处 | 院 | 辅 | 班 | 心 | 宿 | 资 | 生 |
|---|---|---|---|---|---|---|---|---|---|
| studentAffairs.dorm.view（房源/入住） | 查看房源/入住 | ✓ | 限本院 | 限本班 | 限本班 | ✗ | 限本楼 | ✗ | 限本人床位 |
| studentAffairs.dorm.resource.manage | 楼/房/床维护 | ✓ | ✗ | ✗ | ✗ | ✗ | 限本楼 | ✗ | ✗ |
| studentAffairs.dorm.allocation.manage | 排宿/发布/入退宿 | ✓ | 限确认 | ✗ | ✗ | ✗ | 限本楼 | ✗ | ✗ |
| studentAffairs.dorm.transfer.create | 调宿发起 | ✗ | ✗ | 限代发起 | ✗ | ✗ | ✗ | ✗ | 限本人 |
| studentAffairs.dorm.transfer.approve | 调宿审批 | ✓ | 限 | 限初审(本班) | ✗ | ✗ | 限终审(本楼) | ✗ | ✗ |
| studentAffairs.dorm.inspection.manage | 检查任务/记录 | ✓ | 限 | ✗ | ✗ | ✗ | 限本楼 | ✗ | ✗ |
| studentAffairs.dorm.inspection.input | 检查录入 | ✓ | ✗ | ✗ | ✗ | ✗ | 限本楼 | ✗ | ✗ |
| studentAffairs.dorm.exception.handle | 异常处理 | ✓ | 限 | 限本班 | ✗ | ✗ | 限登记/撤销 | ✗ | ✗ |
| studentAffairs.dorm.import / export | 分配导入/检查导入/台账导出 | ✓ | 限 | ✗ | ✗ | ✗ | 限检查导入 | ✗ | ✗ |

（处=学工处管理员，院=学院学工，辅=辅导员，班=班主任，心=心理老师，宿=宿管，资=资助，生=学生。来源：状态机 §13 L522-530。**buttonCode 建议**：`dorm.building.create / bed.checkin / transfer.approve / inspection.record / exception.escalate / dorm.export`。）

### 6.2 数据范围（来自真实业务关系，非角色名）
| 角色 | scopeType | ref | 可见学生 = |
|---|---|---|---|
| 宿管 | **DORM_BUILDING** | 楼栋编码 | 当前在住床位属该楼栋集合的学生（t_cs_dorm_record/床位反查）；跨楼栋 → 403 NO_DATA_SCOPE |
| 辅导员/班主任 | CLASS/ADVISOR | 班级 | 本班学生住宿+异常 |
| 学院学工 | COLLEGE | 学院 | 本院汇总 |
| 学工处 | SCHOOL | 全校 | 全校 |
| 学生 | SELF | 本人 | 本人床位+本寝检查结果 |

- 解析入口：`getStudentAffairsScope(user)` 输出含 `dormBuildings[]`（状态机 §14 L609/L618）。
- **宿管不自动拥有学生完整画像/学业/心理/困难明细**（权限总控 L266/L421 明确）。
- **需人工确认**：DORM_BUILDING 的解析扩展 `resolve_teacher_scope` 是否已在代码落地并对 §4 所有写接口强校验（§0 核对表未确认到 scope 强校验代码）。

---

## 7. 敏感字段脱敏与审计（CLAUDE.md §6 红线）

| 敏感对象 | 处理 | 依据 |
|---|---|---|
| 检查照片（寝室内景/学生个人物品） | 仅登记人/辅导员/学院可见；导出打水印；无关角色不可见 | 状态机 §13 备注 L571 |
| 夜不归宿名单里学生联系方式 | 脱敏展示（MobileSensitiveText）；查看完整号码填原因+审计 | 表单 §3.14 absent_students；移动 S-08 L182 |
| 调宿 HEALTH 原因说明/医疗材料 | 附件加密存储，仅审批链路可见，宿管端收敛；预览水印 | 表单 §4 L447 |
| 学生住宿档案进画像 | 宿舍段仅当前床位+异常计数，不越权带其他敏感段 | 总册 §3.11 ⑬ L618 |

**审计留痕（必写 audit_log）**：房源变更、入退宿、调宿审批各节点、检查提交、异常登记/处置/升级、导入、导出、查看完整手机号（含 ip/ua/traceId/原因）。依据总册 §3.11 ⑪ L618 + service `_audit` L32。
**最小授权 + 二次确认 + 水印 + 导出留痕（t_export_task）**：适用一切导出/打印/批量/查看完整敏感值（§40 安全红线：脱敏一律 AppSensitiveText，查看明文由调用方写审计）。

---

## 8. API 契约草案

> **已建端点以代码为权威**（`student_affairs.py` L799-883），下表标「已建」；缺口端点标「需补」。统一响应 `success(...)`；错误码全模块统一：401 未登录 / 403 无权限(NO_DATA_SCOPE 越栋) / 404 不存在 / 409 状态或床位冲突(DATA_CONFLICT/IDEMPOTENCY_CONFLICT) / 422 校验失败(422001+字段) / 500。**路由前缀以路由文件为准（见 §3 需人工确认）。**

### 8.1 房源（已建）
| 方法 路径 | 说明 | 入参 | 出参 | 状态 |
|---|---|---|---|---|
| POST /dorm/buildings | 新建楼栋（可带层/房/床一键铺满） | BuildingCreate | 楼栋 | ✅ L799 |
| GET /dorm/buildings | 楼栋列表（gender 过滤，带空床/总床） | gender,page,pageSize | items,total | ✅ L804 |
| POST /dorm/buildings/{id}/generate | 铺房+床 | floors,roomsPerFloor,bedsPerRoom | 结果 | ✅ L811 |
| GET /dorm/buildings/{id}/rooms | 房间列表（floor 过滤，带空床数） | floor,page | items | ✅ L817 |
| GET /dorm/rooms/{id}/beds | 床位列表（标空/已住） | — | items | ✅ L824 |
| GET /dorm/occupancy | 入住率统计 | — | 统计 | ✅ L829 |

### 8.2 入住/退宿/自选（已建）
| POST /dorm/beds/{bedId}/checkin | 入住（回写我的宿舍） | studentId | — | ✅ L834 |
| POST /dorm/beds/{bedId}/checkout | 退宿（释放床位） | — | — | ✅ L839 |
| GET /dorm/config | 分配模式（自选开关） | — | config | ✅ L848 |
| PUT /dorm/config/self-select | 开/关学生自选 | enabled | — | ✅ L853 |
| POST /dorm/beds/{bedId}/self-select | 学生自选入住（未放开→403） | studentId | — | ✅ L859 |

### 8.3 调宿（已建）
| POST /dorm/transfers | 发起调宿 | studentId,toBedId,reason | — | ✅ L864 |
| POST /dorm/transfers/{id}/review | 调宿审批（辅→宿→执行） | action,reason | — | ✅ L870 |

### 8.4 检查（已建）
| POST /dorm/check-tasks | 建检查任务 | CheckTaskCreate | — | ✅ L876 |
| POST /dorm/check-tasks/{taskId}/records | 录检查结果（异常→风险） | CheckRecordBody | — | ✅ L881 |

### 8.5 需补端点（前端 5 页所需，需人工确认是否已在别处实现）
| 方法 路径 | 说明 | 备注 |
|---|---|---|
| GET /dorm/transfers | 调宿申请列表（11-3，按 scope/状态筛选） | **需补**（当前仅提交/审批，无列表查询） |
| GET /dorm/transfers/{id} | 调宿详情（进度条+审批链） | **需补** |
| GET /dorm/check-tasks | 检查任务列表（11-5） | **需补** |
| GET /dorm/check-tasks/{taskId}/records | 某任务检查记录列表（11-6） | **需补** |
| GET /dorm/exceptions | 宿舍异常列表（11-7，含夜不归宿，按 scope） | **需补**（异常处置端点） |
| POST /dorm/exceptions/{id}/handle|escalate|close | 异常认领/升级/关闭 | **需补**（状态机 §9 动作） |
| GET /dorm/stats | 宿舍统计（入住率/异常数/夜不归宿趋势/检查覆盖率/调宿时长） | 部分（occupancy 已建），**其余指标需补** |
| POST /dorm/export | 台账导出（花名册/检查/异常，脱敏+水印+审计） | **需补**（§10） |
| POST /dorm/import | 房源/床位分配/检查导入（Excel） | **需补**（§10） |

> ⚠ **调宿 review 的 action 枚举需与 §4.3 最终状态机对齐**（approve/reject/return/execute），且宿管节点必须做「目标床位二次校验 + 乐观锁」——**需核验代码 `review_transfer` L343 是否已实现乐观锁与二次校验**，否则并发超占是阻断上线的 D 级欠账。

---

## 9. 数据表与迁移（MySQL utf8mb4 + tenant_id + 软删除/审计字段）

> **强制复用已建表，严禁建平行 t_dorm_* 表**（CLAUDE.md §9/§37）。全部继承 `PKMixin + TenantMixin + CommonMixin`（含 tenant_id/软删除/审计时间字段）。

| 表 | 复用/新增 | 用途 | 关键字段 | 证据 |
|---|---|---|---|---|
| t_affairs_dorm_building | **复用（已建）** | 楼栋 | building_name/code/gender_limit/manager_teacher_key/status | model L19 |
| t_affairs_dorm_room | **复用（已建）** | 房间 | building_id/floor_no/room_no/capacity/room_type/status（uk 楼栋+房号） | model L32 |
| t_affairs_dorm_bed | **复用（已建）** | 床位(占用事实源) | room_id/bed_no/student_id/status/cs_dorm_record_id（uk 房间+床号） | model L47 |
| t_affairs_dorm_transfer | **复用（已建）** | 调宿 | student_id/from_bed_id/to_bed_id/reason/status/current_node/workflow_instance_id/return_reason | model L64 |
| t_affairs_dorm_check_task | **复用（已建）** | 检查任务 | task_name/building_id/check_type/checker_key/planned_at/status | model L79 |
| t_affairs_dorm_check_record | **复用（已建）** | 检查记录 | task_id/room_id/result/issue_type/detail/related_exception_id/related_risk_id/student_ids_json/status | model L92 |
| t_cs_dorm_record | **复用（旧表）** | 我的宿舍读链路 | cs_student_id/building/room/bed/checkin_date/status | campus_service L76 |
| t_cs_dorm_exception | **复用（旧表）** | 异常/夜不归宿 | cs_student_id/exc_type/happen_time/detail/status/handler/handle_note | campus_service L87 |

**可能需要的字段级迁移（先评估，改前走 §19：先输出必要性/影响/回滚）：**
1. **床位乐观锁**：`t_affairs_dorm_bed` 若无 `version` 列，需加（防调宿并发超占，§8.5 D 级风险）——**需人工确认代码是否已有乐观锁机制**。
2. **检查多评分项**：若确认要卫生/安全分开打分（§4.4 分歧），可给 check_record 加 `hygiene_score/safety_score/abnormal_level` 列，或补 `_item` 明细表——**需人工确认，不确认前不动表**。
3. **调宿状态枚举统一**（§4.3）——仅注释/校验层对齐，**不需要改表结构**（status 是 String）。

> 迁移原则（§36）：新增列走 Alembic migration，可重复执行；utf8mb4/utf8mb4_unicode_ci；不删旧列、不批量改历史数据。**本卡默认不新增表**——若最终无需字段迁移，则本模块「零迁移」，纯前端 + 后端补查询/导出接口。

---

## 10. Excel 导入导出（接公共底座 `app/services/excel/`，CLAUDE.md §38）

> 公共 Excel 底座已存在：`backend/app/services/excel/{spec.py, validators.py, pipeline.py, job_service.py}`（§0 已确认）；前端用 `AppExportButton + AppExportConfirm`（§40）。**禁止本模块另写一套解析/校验/错误行/导入记录/导出审计。**

### 10.1 导入（Excel/xlsx，页面文案：下载 Excel 模板/上传 Excel/导入 Excel）
| domain | 用途 | 关键列 | 校验 |
|---|---|---|---|
| dorm_resource | 楼栋/房间/床位批量建 | 楼栋/性别/层/房号/容量/床号 | 必填+房号床号唯一+性别枚举 |
| dorm_allocation | 床位分配（学号→床位） | 学号/楼栋/房间/床位 | 学生存在+床位空+性别匹配+文件内/库内重复 |
| dorm_inspection | 检查结果批量导入 | 楼栋/房间/卫生分/安全分/违禁/异常等级 | 分数区间+异常等级枚举 |

流程（§38 完整链）：下载模板 → 上传 xlsx → 字段/必填/格式/业务规则/文件内重复/库内重复校验 → 错误行预览 → **下载错误行 Excel** → 确认导入 → 导入记录 + 操作审计。

### 10.2 导出（Excel 台账，按当前筛选+权限+脱敏+审计）
| 台账 | 内容 | 脱敏 | 文件名 |
|---|---|---|---|
| 住宿花名册 | 楼栋/房间/床位/学号/姓名/班级/入住日期 | 联系方式脱敏 | 宿舍花名册_{租户}_{时间}.xlsx |
| 检查台账 | 任务/楼栋/房间/评分/异常/整改 | 照片不入表（或水印链接） | 宿舍检查台账_… |
| 异常台账 | 学生/类型/时间/状态/处置人/结论 | 夜不归宿名单联系方式脱敏 | 宿舍异常台账_… |

- 导出走后端真实管线（不 mock 成功），敏感字段脱敏，**t_export_task 留痕 + 水印 + 用途≥5 字**（§40 安全红线、§7）。

---

## 11. 移动端入口（依据移动端设计 S-08 L174 / T-07）

| 端 | 入口 | 口径 | 页面路径 |
|---|---|---|---|
| 学生端 | 服务大厅「我的宿舍」宫格 | **只读**宿舍信息（楼/层/房/床、室友仅姓名、宿管电话脱敏）+ 检查结果页签 + **可写**调宿申请 | `pages/student/affairs/dorm/my`、`.../dorm/transfer` |
| 教师端·宿管 | 检查任务 | **可写**：逐房检查录入（高频移动场景，弱网草稿）、夜不归宿登记 | T-07 移动录入（标 P2 但本卡列应补） |
| 教师端·辅导员 | 待办 | **可写**：宿舍异常认领/处置、一键联系学生（脱敏+审计） | 随工作台待办 todo_type |

学生端调宿要点（S-08 L185-188）：createSubmitLock 防重复；在途单→409001「已有调宿申请在审批中」；404→「暂无分配宿舍」渲染 empty（新生未排宿，非错误）；提交成功→信息页顶部「调宿审批中」状态条 + 待办生成 + 通过后床位字段更新。**目标床位校验在审批节点（不在学生端），保持后端裁定。**

---

## 12. 验收标准（页面级用例）

对 5 个待建页 + 学生端逐一验收（对齐 CLAUDE.md §20）：

**通用（每页必过）**
- 进入：菜单点入正确、面包屑「学工中心 / 宿舍与公寓 / X」、刷新高亮不丢（唯一 leafKey，§9.4）。
- 旧路由兼容：`/admin/campus-service/dormitory`、旧 `/dorm/*` 刷新不 404（redirect/alias）。
- 权限：无 `studentAffairs.dorm.*` 权限不显示入口；后端越权直接 403（前端隐藏≠权限）。
- 数据范围：宿管仅见本楼栋（越栋 403 NO_DATA_SCOPE）；辅导员仅本班；学生仅本人；处/院按 scope 汇总，数字与下钻 0 差异。
- 脱敏：联系方式/检查照片/HEALTH 材料按 §7 脱敏；查看完整值填原因+审计。
- 三态：loading 骨架 / empty（如新生未排宿）/ error（单卡失败不塌整页）；网络错误可重试。
- 导出：Excel 带水印、脱敏、t_export_task 留痕；无「假导出」。
- 无假按钮/假数据/无 console error。

**页面专项**
- 房源管理：楼→房→床三级树完整；一键铺满数量正确；床位状态与入退宿联动准确。
- 调宿：三级联动仅列空床；提交防重复 409；审批二次校验床位+并发被占 409 引导改选；通过后原床释放新床占用一致、t_cs_dorm_record 更新、学生端刷新。
- 宿舍检查：逐房录入落 check_record；abnormal≥MINOR 生成异常+辅导员待办；SEVERE/夜不归宿生成风险；同任务同房重复 409。
- 宿舍异常：夜不归宿→异常→风险单自动生成；30 天≥3 次自动升级；认领/升级/关闭状态流转正确、留痕。
- 宿舍统计：入住率/异常数/夜不归宿趋势/检查覆盖率/调宿时长口径与业务表 0 差异，可下钻。

---

## 13. 依据文档索引（关键结论 → 来源 + 行号）

| 结论 | 来源文件 | 章节/行号 |
|---|---|---|
| 对标正方/强智/青果（不抄袭）+ 宿舍缺口 | 13A-学工中心-商业化对标审计与补丁建议（第一轮）.md | L8、L123、L162-163 |
| 宿舍全流程（角色/前置/主流程/状态机/权限/字段/统计/入口） | 13A-学工中心全业务流程设计总册.md | §3.11 L577-620 |
| 调宿状态机 8 态 + 检查异常状态机 5 态 + 超时升级 | 13A-学工中心状态机与权限矩阵.md | §8 L335-361、§9 L364-389 |
| 权限矩阵（宿舍 9 权限点）+ 数据范围 DORM_BUILDING | 同上 | §13 L522-530、§14 L603-618 |
| 调宿/检查表单字段与 422 校验 | 13A-学工中心表单字段与校验规则.md | §3.13 L355、§3.14 L372 |
| 页面树 11-1~11-11 + 承接现状表 | 13A-学工中心页面树与路由设计.md | §3.9 L282-296、L478-484 |
| 学生端我的宿舍/调宿 S-08 | 13A-学工中心移动端入口设计.md | S-08 L174-188 |
| 宿管楼栋绑定/不给完整画像 | 系统管理中心-权限角色模块授权与权责边界设计.md | L266、L365、L421、L463 |
| 智能排宿人工可跑通/接口位 | 13A-学工中心-商业化对标审计…第一轮.md | L333-336、L484 |
| 后端房源/调宿/检查模型 | backend/app/models/affairs_dorm.py | L17-110 |
| 复用旧 t_cs_dorm_record/exception | backend/app/models/campus_service.py | L76-101 |
| 已建 ~15 个 dorm API | backend/app/api/v1/student_affairs.py | L799-883 |
| service（checkin/transfer/check/回写/审计） | backend/app/services/affairs_dorm_service.py | L27-451 |
| 已建迁移 | backend/alembic/versions/0008_13a_p6_dorm_archive.py | 全 |
| navPlan sa-dorm 6 三级页状态 | frontend/src/config/navPlan.js | L129-132 |
| 施工图卡指令 | frontend/src/config/constructionMap.js | L65-69 |
| Excel 公共底座 | backend/app/services/excel/ | spec/validators/pipeline/job_service |

**需人工确认清单（不得当确定结论）**：
1. 三处调宿状态枚举分歧（DORM_ADMIN_REVIEW / DORM_REVIEW / DORM_MANAGER_REVIEW；APPROVED/COMPLETED/EXECUTED）——统一口径。
2. 床位状态 LOCKED vs DISABLED、检查任务 DRAFT/RUNNING vs PLANNED/IN_PROGRESS 枚举分歧。
3. 夜不归宿类型 NIGHT_OUT vs NIGHT_ABSENT。
4. 检查记录单表 vs `_item` 多评分项（能否卫生/安全分开打分）。
5. Workflow 名 AFFAIRS_DORM_CHANGE vs AFFAIRS_DORM_TRANSFER。
6. 床位乐观锁 version 是否已实现（并发超占防护，D 级风险）。
7. DORM_BUILDING scope 是否已对所有写接口强校验。
8. 超时自动升级/自动 CANCELLED 定时任务是否已实现。
9. 路由最终前缀（`/admin/student-affairs/dorm/*`）。
10. 三家产品的独家字段/流程细节（本代理未联网，未核证具体产品界面）。
11. 房型 room_type 枚举取值。
12. 旧「入住管理」页是否迁并入 11-2（§14 风险）。

---

## 14. 施工顺序与依赖

**前置模块（必须先在）**
- 班级管理（辅导员 scope 载体）、风险预警（夜不归宿转风险的接收方）、Workflow 引擎（调宿审批 AFFAIRS_DORM_TRANSFER）、公共组件底座（§40/§41）、Excel 底座（§10）、导出管线 t_export_task。

**复用表（不新建）**：见 §9 全部标「复用」。

**建议施工顺序（照做）**
1. **对齐口径**（0.5 天，纯确认）：把 §13 需人工确认 1-8 项与甲方/代码确认，锁定枚举与乐观锁现状，产出对齐结论（不改代码文档时先记欠账）。
2. **后端硬化 + 补查询/导出接口**（构成一次提交）：补 §8.5 列表/详情/异常处置/统计/导入导出端点；核验乐观锁、DORM_BUILDING 强校验、审计、脱敏。若需字段迁移（乐观锁/多评分项），先走 §19 评估再 Alembic。`commit: feat(student-affairs): harden dorm backend + list/export apis`
3. **房源管理 + 调宿退宿前端**（连续处理=列表+详情双栏，复杂详情独立页）：`commit: feat(student-affairs): dorm resource & transfer pages`
4. **宿舍检查 + 宿舍异常前端**（检查录入移动优先）：`commit: feat(student-affairs): dorm inspection & exception pages`
5. **宿舍统计 + Excel 导入导出接入**：`commit: feat(student-affairs): dorm stats & excel pipeline`
6. **学生端我的宿舍/调宿（S-08）对接**：`commit: feat(student-affairs): student dorm mobile pages`
7. **☆ 补强页**（智能排宿/公寓纪律/文明寝室）走公共规划占位页，**不建空页**（§42），保持 planned。

**风险点**
- **调宿并发超占**（无乐观锁→双人抢同床）：D 级，上线前必须核验/补齐，否则不得标 implemented。
- **DORM_BUILDING 越栋泄露**：宿管看到非本楼学生=数据范围红线，后端强校验必须真到位。
- **检查照片脱敏**：寝室内景/个人物品泄露=隐私红线（§7）。
- **旧「入住管理」页与新 11-2 并存**：避免双入口干扰用户；迁并需 §37 安全下线流程（先 redirect，确认无引用再清理），**不在本卡擅自删旧页**。
- **文档 vs 代码枚举分歧未对齐就开发**：会产生前后端状态字符串不一致的隐性 bug。

**提交粒度**：每个功能段 1 个 commit，精确 `git add` 本模块文件（禁止 `git add -A`），不 push/不 tag（§15）；完成后更新 `docs/06-开发施工与质量验收/施工记录/` 与 `历史欠账.md`（§35），navPlan 把已完成叶子从 `P(...)` 改 `I(label, path)`（§42「做完一个亮一个」）。

---

> 本卡为**施工指导文档**，不含任何代码改动；所有「已建/已实现」均引代码行号，所有分歧与未证实项均标「需人工确认」。开工严格遵循 CLAUDE.md 六步阅读顺序与 §0.0 市场验证优先原则。
