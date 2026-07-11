# 施工卡 · 学工中心 D 包 —— 统计与档案（sa-archive-stats）

> 模块代号：`sa-archive-stats`（学工中心 D 包「统计与档案」收口件）
> 覆盖三级页面：**学工归档（归档批次）· 学生档案包 · 学工统计（统计驾驶舱）**
> 文档性质：**施工卡（供照着开发），不是实现记录**。本卡只写文档，未改任何代码 / navPlan / 配置 / 迁移。
> 证据规则：每条关键结论标来源文件 + 章节/行号；读不到依据一律标「需人工确认」，不臆造字段 / 接口 / 流程。
> 对标口径：严格执行 CLAUDE.md §0.0「市场验证优先与成熟商业系统复刻规则」——先输出三家成熟系统对标表，再落本项目实现。
> planned 状态说明：本三页在施工图中标 **P2 / D 包 / 待施工**（见 `13A-学工中心全量规划施工图.md` L49–50、L299–325）。本卡为「照着开发」的输入，**不改变 planned 状态，不得据此标 implemented / partial**；真实施工完成并验收后方可在 navPlan 由 `P()` 改 `I()`。

---

## 1. 模块定位与真实学校业务价值

### 1.1 真实学校谁用、解决什么

| 角色 | 真实场景 | 本模块解决什么 |
|---|---|---|
| 学工处管理员 | 学年末要向学校/上级交「学工工作档案」，要在年度考核、评估、审计、迎评创建时拿出台账与统计 | 一键按学年/范围生成学生学工档案包、汇总全域指标出报表，替代「各科室手工翻单据、Excel 东拼西凑」 |
| 学院学工负责人 | 对本院学生档案完整性负责，要审核缺件、看本院各项分布与排行 | 本院档案完整性审查、本院口径统计与下钻 |
| 辅导员 | 带班学生档案缺什么材料要补齐；关心自己带班的各项数据 | 收到缺件待办→补传材料；看本班切片统计 |
| 校领导 | 只看汇总趋势、学院对比，不看个人明细 | 校级驾驶舱（数量/趋势/学院对比），下钻二次鉴权 |

**一句话业务价值**：学工归档是「学校验收 / 迎评 / 审计时能拿得出的账」，学工统计是「领导决策与投标响应里的数字」。二者是学工中心的**收口件**——B/C 包产生业务数据，D 包把它变成**可核查的档案**与**可上报的统计**。

依据：`13A-学工中心D包-上线补强与商业增强施工卡.md` §1（L10–11「学工归档/学工统计 P0，形成学生学工档案包、指标库/报表/校级统计」）、`13A-学工中心-商业化对标审计与补丁建议（第一轮）.md`（下称《对标审计》）第三步原则 2「所有业务必须有台账」、原则 9「所有统计必须能从汇总钻取到明细」、原则 15「所有模块都要能形成销售话术和投标响应」。

### 1.2 边界（不做卖不出去的自嗨功能）
- 统计**只读聚合，不反写业务主表**（D 包施工卡 §4「读取聚合表和业务表，不反写业务主表」L72）。
- 归档**只汇聚已有业务摘要**，不在归档模块新造业务数据；心理原文 / 资助敏感 / 处分证据**默认不入包**（D 包施工卡 §3 L61、§11.2 L142）。
- 统计指标**复用既有 `stats_service`**，不另起一套口径（API 契约 L417「实现方式 = 扩展既有 stats_service」、L552「学工统计不占用 /api/v1/stats/*，走 /student-affairs/stats/*，实现层复用 stats_service」）。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点）

> 联网说明：本次运行**无法确认可用联网检索**，故对标主依据取仓库内《对标审计》（已对标正方 / 强智 / 青果，含 15 条精华原则与缺口表，见该文件 L6、L73–103、L128–129、L170–172）。以下每条结论标来源；三家产品的具体私有字段/界面**不抄袭**，只吸收其经市场验证的业务成熟度。三家产品各自「档案/统计」专有细节，仓库未逐条列举处标「需人工确认」。

**① 对标对象 A —— 正方（教务/学工一体化，市场保有量大）**
- 核心流程：业务数据 → 期末批量归档 → 按学籍号生成学生档案 → 导出/打印台账。统计以「教务口径为主，学工为辅」的报表中心呈现。
- 角色：校级管理员、学院、辅导员/班主任。
- 字段：学年学期、归档范围、材料清单、完整度、导出用途。
- 亮点：**归档与学籍主数据强绑定，档案按学生聚合**，台账导出稳定，实施交付成熟。
- 缺点：学工侧敏感数据分级较弱，心理/资助明细与普通材料混装的历史包袱（依据：《对标审计》原则 5 指出「敏感分级脱敏」是本项目相对优势，反衬同类产品此项偏弱）。「需人工确认」正方最新版本的具体脱敏策略。

**② 对标对象 B —— 强智（教务强、学工模块完整）**
- 核心流程：指标库 → 报表模板 → 按角色出不同视图 → 导出。归档以「材料库 + 完整性检查」呈现。
- 角色：处 / 院 / 辅 / 领导驾驶舱。
- 字段：指标口径、统计维度（校/院/专业/班）、报表 code、导出范围。
- 亮点：**报表模板化 + 多维下钻**，领导驾驶舱成熟（对应《对标审计》原则 1「分角色看板」、原则 9「汇总钻取到明细」）。
- 缺点：模块多导致口径分散、易出现「两套数」；配置门槛偏高。「需人工确认」强智驾驶舱的具体指标清单。

**③ 对标对象 C —— 青果（学工/学生工作管理见长）**
- 核心流程：学工业务 → 工作台/台账 → 归档 → 统计上报。强调辅导员工作量与学工台账。
- 角色：学工处、学院、辅导员、宿管、资助、心理。
- 字段：学工业务台账、辅导员工作量、归档缺件、导出审计。
- 亮点：**学工台账体系完整、辅导员工作量沉淀**（对应《对标审计》原则 2「所有业务必须有台账」、原则 11「围绕画像与待办聚合」）。
- 缺点：统计与教务口径打通较弱；跨学院数据范围控制需现场配置。「需人工确认」青果的归档封存/版本机制细节。

**④ 三家共同具备的核心功能（默认即本项目必备基础能力）**
1. 按学年/范围**批量生成学生档案包**，含材料清单与完整度。
2. 归档**完整性检查 + 缺件补传**闭环。
3. 归档包/报表**导出带用途登记、水印、下载审计**。
4. 统计**指标库化 + 多维下钻（校/院/专业/班）+ 分角色视图**。
5. **领导驾驶舱**（数量/趋势/对比）与**明细钻取**联动，且「汇总-明细对账一致」。
6. 导出**按数据范围裁剪、敏感字段脱敏**。

依据：《对标审计》第四步缺口表 #17 学工归档、#18 学工统计（L128–129），第三步原则 1/2/5/8/9（L75/77/83/89/91）。

**⑤ 三家里最值得吸收的最佳做法**
- 正方：**档案按学生聚合 + 与学籍主数据绑定**（本项目已具备：`t_affairs_archive_package` 每生一行、回链 student_id，见数据表草案 L170）。
- 强智：**报表模板化 + 多维下钻 + 领导驾驶舱**（本项目已有 stats overview 自带 caliber/drill，见 API 契约 L397–415）。
- 青果：**学工台账完整 + 辅导员工作量沉淀**（本项目辅导员完成率/工作量摘要已定义，见状态机 L452、《对标审计》补丁 P-01 L196）。
- 三家共性最佳做法：**「汇总数字必须能下钻到人，且首页-列表对账 0 差异」**（本项目已作硬门禁，见 `13A-13B-V1范围冻结表.md` §8 / 状态机与页面树承诺）。

**⑥ 本项目当前已有能力（有证据）**
- 归档状态机已设计：`DRAFT/GENERATING/SUPPLEMENTING/COLLEGE_REVIEW/AFFAIRS_CONFIRM/ARCHIVED`，含补缺/审查/退回/确认/下载全链路（状态机 §11，L426–453）。
- 归档 API 契约 7 端点已定义（#101–107，API 契约 L377–389）。
- 归档表已定名：`t_affairs_archive_batch`、`t_affairs_archive_package`，复用 `t_export_task`/`t_file_object`，**不建归档文件表**（数据表草案 §3.9，L167–170）。
- 统计 API 契约 3 端点已定义（#108–110，API 契约 L393–417），指标自带口径/来源/更新频率/下钻。
- 权限点已定义：`studentAffairs.archive.*`、`studentAffairs.stats.*`（状态机 §12，L541–550）。
- 各业务终态「批次收编归档 → ARCHIVED 只读」已在 11 个业务状态机统一约定（状态机 §说明 L24、各业务表尾行）。
- 页面树已列 15-1~15-5、16-1（页面树 §3.11，L319–328）。

**⑦ 缺失的生产级闭环（缺口）**
- 归档：三家有的「**按班级/业务/学年多维归档**」本项目现只按学生+批次；「**缺失项自动催办**」有补缺流程但催办未任务化（《对标审计》#17 缺口 L128、第五步 17 项 L170）。
- 统计：三家有的「**独立统计分析页的五维交叉 + 通用排行榜**」本项目 overview 偏角色 preset，专业维/通用排行未成（《对标审计》#18/#29 缺口 L129/L172）。
- 校级/学院**驾驶舱**页（`/dashboard/college`、`/dashboard/school`）在 D 包施工卡 §11.3 列出（L153–154），但 API 契约未见独立驾驶舱端点——**需人工确认**是否复用 overview + Dashboard preset，还是新增端点。

**⑧ 本卡必须补齐（本轮交付目标）**
1. 学工归档三级页 15-1~15-4（批次列表/创建/档案包详情/完整性审核确认）真实闭环，接已定 7 端点与两表。
2. 学生档案包详情页（15-3）——目录树 + 完整度 + 缺件清单 + 补传 + 水印下载。
3. 学工统计驾驶舱（16-1 统计总览 + 15-5 归档统计）——指标卡 + 口径 + 多维下钻 + 导出，接已定 3 端点。
4. 全链路脱敏 + 用途登记 + 水印 + 下载/导出审计。

**⑨ 进 backlog（能力池，本卡不一次性交付，标 planned）**
- 按班级/业务/学年**多维归档**、缺件**自动催办**（《对标审计》#17）。
- 独立统计分析页**五维交叉 + 通用排行榜**、**学院对比分析**（施工图 L324）。
- 校级/学院**独立驾驶舱页**（若确认新增）。
- 含心理明细的**专项归档**（需 `studentAffairs.archive.psySensitive` 专项授权，状态机 L447）。

**⑩ 禁止做成假功能（红线）**
- 禁止统计页写死 mock 数据（D 包施工卡 §4「不用假数据」L26）。
- 禁止归档包绕过导出管线直接下载（状态机 §11.1 L446「绕过 → 403」）。
- 禁止把敏感原文（心理/资助/处分证据）打进归档包默认导出（D 包施工卡 §11.2 L142、状态机 L447）。
- 禁止「有菜单无闭环」的占位统计/归档页冒充完成。

---

## 3. 三级页面清单与状态（对齐施工图）

> 本模块在导航中挂 **学工中心 → 学工归档 / 学工统计** 两个二级。下列页面对齐 `13A-学工中心页面树与路由设计.md` §3.11（L319–328）与 D 包施工卡 §3/§4。当前状态 **planned（待施工）**，真实完成后逐叶改 `I()`。

### 3.1 学工归档（二级 · 路由前缀 `/archive`）

| 页面号 | 页面名 | 路由 | 主用角色 | 状态 | 依据 |
|---|---|---|---|---|---|
| 15-1 | 归档批次列表 | `/admin/student-affairs/archive/batches` | 处/院（辅见涉己补缺） | planned | 页面树 L323、L165 |
| 15-2 | 创建归档批次 | `/admin/student-affairs/archive/batches/create` | 处 | planned | 页面树 L324、L166 |
| 15-3 | **批次详情（学生档案包）** | `/admin/student-affairs/archive/batches/:batchId` | 处/院/辅（范围内） | planned | 页面树 L325、L167 |
| 15-4 | 完整性审核与确认 | `/admin/student-affairs/archive/batches/:batchId/review` | 院（完整性）→处（确认） | planned | 页面树 L326、L168 |
| 15-5 | 归档统计 | `/admin/student-affairs/archive/stats` | 处/院（归档率） | planned | 页面树 L327、L169 |

> 静态段路由（`create`/`stats`/`review`）**必须注册在 `:batchId` 动态段之前**，避免被吞（页面树 §路由约定 L28）。

### 3.2 学工统计（二级 · 路由前缀 `/stats`）

| 页面号 | 页面名 | 路由 | 主用角色 | 状态 | 依据 |
|---|---|---|---|---|---|
| 16-1 | **统计总览（驾驶舱）** | `/admin/student-affairs/stats` | 处/院（辅见本班切片） | planned | 页面树 L328、L172 |
| （能力池） | 学院/校级独立驾驶舱 | `/dashboard/college`、`/dashboard/school` | 院/处/校领导 | backlog | D 包施工卡 §11.3 L153–154，**需人工确认**是否独立端点 |

### 3.3 三个三级收口件的对应关系（对齐任务口径）
- **归档批次**（15-1/15-2/15-4）= 归档流程的批次编排与审核确认。
- **学生档案包**（15-3）= 批次内每生一个档案包，是学校验收/迎评时的「学生学工档案」实体。
- **统计驾驶舱**（16-1，+15-5 归档率）= 全域指标汇总 + 下钻 + 导出的领导/管理视图。

> 三者是学工中心**验收收口件**：B/C 包各业务产生数据 → 归档收编为只读档案 → 统计出账。

---

## 4. 业务流程与状态机

### 4.1 归档批次状态机（13A-14，**已设计，照抄不重设计**）

状态枚举 **[推导枚举，需现场确认]**（状态机 §11 L428）：
`DRAFT → GENERATING → SUPPLEMENTING → COLLEGE_REVIEW → AFFAIRS_CONFIRM → ARCHIVED`

> 注意：数据表草案 §3.9（L169）批次枚举写作 `DRAFT/COLLECTING/COLLEGE_REVIEW/SA_CONFIRM/ARCHIVED`，与状态机 §11 的 `GENERATING/SUPPLEMENTING/AFFAIRS_CONFIRM` **命名不完全一致**。**需人工确认统一一套枚举**（建议以状态机 §11 为准，数据表 COLLECTING≈GENERATING+SUPPLEMENTING、SA_CONFIRM≈AFFAIRS_CONFIRM），冻结前必须对齐，否则前后端枚举撞车。

| 当前状态 | 操作 | 执行角色 | 目标状态 | Workflow | 通知 | 审计 | 依据 |
|---|---|---|---|---|---|---|---|
| DRAFT | 建归档批次（学年/范围/内容清单） | 处 | DRAFT | 否 | 无 | 是 | 状态机 L433 |
| DRAFT | 启动生成（按学生生成档案包） | 处 | GENERATING | 否 | 无 | 是 | L434 |
| GENERATING | 生成完成（含缺件清单） | 系统 | SUPPLEMENTING | 否 | WORKFLOW_TODO→辅导员 | 是 | L435 |
| SUPPLEMENTING | 辅导员补缺（逐生补传） | 辅 | SUPPLEMENTING（留痕） | 否 | 无 | 是 | L436 |
| SUPPLEMENTING | 提交完整性审查 | 辅/院 | COLLEGE_REVIEW | 是 | WORKFLOW_TODO→学院学工 | 是 | L437 |
| COLLEGE_REVIEW | 完整性通过 | 院 | AFFAIRS_CONFIRM | 是 | WORKFLOW_TODO→学工处 | 是 | L438 |
| COLLEGE_REVIEW | 退回补缺 | 院 | SUPPLEMENTING | 是 | RETURNED_NOTICE→辅导员 | 是 | L439 |
| AFFAIRS_CONFIRM | 确认归档（生成水印包+写 t_export_task） | 处 | ARCHIVED | 是 | ARCHIVE_NOTICE→院+辅 | 是（归档事件进360） | L440 |
| AFFAIRS_CONFIRM | 退回 | 处 | SUPPLEMENTING | 是 | RETURNED_NOTICE→辅导员 | 是 | L441 |
| ARCHIVED | 下载归档包（水印+用途登记） | 处/院（范围内） | ARCHIVED | 否 | 无 | 是(EXPORT/DOWNLOAD) | L442 |

**责任人 / 超期升级**（状态机 §11.2 L450–453）：
- SUPPLEMENTING 停留 ≥14 天 → `DEADLINE_REMINDER`→辅导员+学院学工（附缺件清单）；归档率纳入辅导员完成率统计。
- GENERATING 超 2h 未完成 → 告警学工处（任务失败**可重跑，幂等**）。

**非法转移防护**（状态机 §11.1 L446–448）：
- ARCHIVED 批次内任何业务记录写操作 → **409**（归档冻结）；非 SUPPLEMENTING 状态补缺 → 409。
- 下载绕过导出管线（无用途≥5字/无水印/无 t_export_task）→ **403**。
- 含心理明细专项归档需 `studentAffairs.archive.psySensitive` + 二次确认 + SENSITIVE_VIEW 审计。
- 跨学院提交/审查 → **403** NO_DATA_SCOPE。

### 4.2 学生档案包（批次内子对象）状态机

数据表草案 §3.9（L170）：`t_affairs_archive_package` 状态 `PENDING_GEN / PENDING_SUPPLEMENT / SUBMITTED / ARCHIVED / RETURNED`，随批次流转（回链 batch_id）。**需人工确认**包级枚举与批次级枚举的联动映射（建议：批次 GENERATING→包 PENDING_GEN；批次 SUPPLEMENTING→包 PENDING_SUPPLEMENT/SUBMITTED；批次 ARCHIVED→包 ARCHIVED）。

### 4.3 统计（无状态机 —— 只读聚合）
统计为只读查询，无状态流转。数据实时或按日刷新，口径随各指标 `refresh` 标记（API 契约 L406–410：请假实时、辅导员完成率每日）。**归档率**指标由归档批次完成度回流（状态机 L452）。

---

## 5. 表单字段与校验规则

> 归档为「配置 + 审核」型，无学生填报长表单。逐字段列关键写入项；敏感级按融合设计脱敏矩阵与 CLAUDE.md §6。

### 5.1 创建归档批次（15-2，对应 API #102）

| 字段 | 类型 | 必填 | 校验 | 敏感级 | 依据 |
|---|---|---|---|---|---|
| batchName 批次名称 | string | 是 | 1–50 字，同租户+学年内不重复 | 普通 | API #102 L382 |
| schoolYear 学年 | string(枚举) | 是 | 取自学年学期字典，格式如 `2025-2026` | 普通 | API #102；公共日期族按 §40 |
| scopeConfig 归档范围 | object | 是 | 至少含一种范围（学院/专业/班级/年级）；后端按操作人 scope 二次校验，越权 → 403 | 普通 | API #102；状态机数据范围 §13 |
| contentTypes[] 内容清单 | array(枚举) | 是 | 取值 ∈ {请假,奖助,困难,处分,解除,谈话,心理风险,宿舍,活动,家校,风险处置,辅导员日志,班级材料}，至少 1 项 | 普通 | 状态机 L429、D 包施工卡 §3 L60 |
| includePsySensitive 含心理明细 | bool | 否 | 默认 false；置 true 需 `studentAffairs.archive.psySensitive` + 二次确认 | **敏感** | 状态机 L447 |
| requestId 幂等键 | string | 是 | 幂等去重，重复提交返回同结果 | 普通 | API 契约幂等约定 |

### 5.2 完整性审核与确认（15-4，对应 API #105/#106）

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| action 动作 | enum(APPROVE/RETURN) | 是 | 学院审查用；RETURN 时 reason 必填 | 普通 |
| reason 退回原因 | string | RETURN 必填 | ≥5 字（API #105 L385） | 普通 |
| version 乐观锁版本 | int | 是 | 与当前不一致 → 409 状态冲突 | 普通 |

### 5.3 补缺（15-3 内动作，对应 API #104）

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| itemType 缺件类型 | enum | 是 | ∈ contentTypes；非 SUPPLEMENTING 状态提交 → 409 | 普通 |
| fileIds[] 补传文件 | array | 是 | 只存 file_id（走文件中心，§40 红线 6），至少 1 个 | 视材料而定 |

### 5.4 归档包下载 / 统计导出（15-3 / 16-1，对应 API #107/#110）

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| purpose 用途登记 | string | 是 | **≥5 字**（API #107 L387、#110 L399），写审计 | 普通（内容留痕） |
| filters 导出过滤 | object | 否 | 统计导出按当前筛选；后端按 scope 裁剪 | 普通 |

---

## 6. 权限矩阵与数据范围

> 权限点命名遵循 CLAUDE.md §10（`module.domain.action`）；数据范围来自真实业务关系（`t_teacher_student_scope` + `resolve_teacher_scope`，封装 `getStudentAffairsScope`），引用权限总控 `00-系统管理中心-权限角色模块授权与权责边界设计.md` §3.3/§16。

### 6.1 权限点（状态机 §12，L541–550，照抄）

| 权限点 | 处 | 院 | 辅 | 心 | 说明 |
|---|---|---|---|---|---|
| `studentAffairs.archive.view` | ✓ | 限本院 | 限（缺件清单） | ✗ | 归档查看 |
| `studentAffairs.archive.batch.manage`（建批次/生成/确认） | ✓ | ✗ | ✗ | ✗ | 仅学工处 |
| `studentAffairs.archive.supplement`（补缺） | ✗ | 限 | 限（本班） | ✗ | 辅导员/学院补传 |
| `studentAffairs.archive.review`（完整性审查） | ✓ | 限本院 | ✗ | ✗ | 学院审查 |
| `studentAffairs.archive.download`（水印下载） | ✓ | 限本院 | ✗ | ✗ | 下载全量审计 |
| `studentAffairs.archive.psySensitive`（含心理明细专项） | 限（专项授权） | ✗ | ✗ | 限 | 二次确认+SENSITIVE_VIEW |
| `studentAffairs.stats.view` | ✓ | 限本院 | 限本班切片 | 限（心理类） | 统计查看 |
| `studentAffairs.stats.export` | ✓ | 限本院 | ✗ | ✗ | 统计导出 |

### 6.2 数据范围（状态机 §13 归档行 L573）

| 角色 | 归档可见范围 | 特殊规则 |
|---|---|---|
| 学工处 | 全校 | 归档包整体水印；下载全量审计 |
| 学院学工 | 本学院 | 跨院提交/审查 → 403 |
| 辅导员/班主任 | 负责班级的**缺件清单**（补传） | 不可下载整包（仅处/院可下载） |
| 心理/宿管/资助 | 不可见（普通归档） | 心理明细专项包另需 psySensitive |

- 数据范围来源：辅导员看哪些学生 = 辅导员-班级绑定（权限总控 §3.3；`t_teacher_student_scope`，状态机 §13 L590）。
- 角色默认模板：**学工处管理员 = 全校学生 + 全学工业务+批次/公示/归档**（权限总控 L262）；**不可看心理原始明细（除非授权）、不可删审计**（同 L262）。
- 后端四层裁定：当前激活角色 → 权限点 → 数据范围 → 敏感权限 →（归档审查节点）（权限总控 §主流程 L70）。**前端隐藏 ≠ 有权限，后端必须独立校验**。

---

## 7. 敏感字段脱敏与审计（CLAUDE.md §6 红线）

| 红线项 | 本模块落法 | 依据 |
|---|---|---|
| 最小授权 | 归档默认剔除心理原文/资助敏感/处分证据；专项含心理明细需 psySensitive 专项授权 | D 包施工卡 §11.2 L142、状态机 L447 |
| 二次确认 | 建含心理明细批次、下载归档包、统计导出均走 `AppExportConfirm` 二次确认 | D 包施工卡 §11.1 表6 L132、§40 公共组件 |
| 填写查看原因 | 下载/导出 `purpose` **≥5 字**，写审计 | API #107 L387、#110 L399 |
| 水印 | 归档包整包水印；统计报表导出水印 xlsx | 状态机 L440/L573、D 包施工卡 §11.3 L151 |
| 审计留痕 | 确认归档 `AFFAIRS_ARCHIVE_CONFIRM`、下载 `EXPORT/DOWNLOAD`、统计导出 `EXPORT`；敏感查看 `SENSITIVE_VIEW`；写入 `t_security_audit_log`（`record()`）与域 `audit_trail` | API #106/#107/#110、权限总控 §复用事实 L5 |
| 可追溯到人 | 每次谁归档/谁下载/谁导出均留痕（学年-范围-操作人-用途-时间-sha256） | 状态机 L442、数据表 L169「t_export_task(sha256)」 |
| 脱敏展示 | 档案包列表 `realName` 脱敏（API #103 L383）；统计只出聚合数，下钻明细按 scope | API #103、状态机 §13 |

> 面板一律用 `AppSensitiveText`（脱敏）、`AppExportConfirm`（导出二次确认）、`AppAuditTrail`（展示后端真实审计，不伪造）——CLAUDE.md §40 安全红线。

---

## 8. API 契约草案（照抄已定契约，未定处标确认）

> 全部端点已在 `13A-学工中心API契约草案.md` §14/§15 定义（L377–417）。统一前缀 `/api/v1/student-affairs/`。错误码统一：401 未登录 / 403 无权限或越 scope / 404 不存在 / 409 状态冲突或归档冻结 / 422 校验失败。

### 8.1 学工归档（API §14，L381–389）

| # | 方法/路径 | 用途 | 关键入参 | 出参要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 101 | `GET /archive/batches` | 批次列表 | schoolYear/status(否)、page/pageSize | list[{batchId,batchName,schoolYear,status,packageCount,missingCount}] | archive.view | 无 |
| 102 | `POST /archive/batches` | 建批次+启动生成 | batchName、schoolYear、scopeConfig、contentTypes[]、requestId | {batchId,status:"GENERATING"} | archive.batch.manage | AFFAIRS_ARCHIVE_BATCH |
| 103 | `GET /archive/batches/{batchId}/packages` | 档案包列表（含缺件） | classId/missing(否)、page/pageSize | list[{packageId,studentNo,realName(脱敏),completeness,missingItems[]}] | archive.view | 无 |
| 104 | `POST /archive/packages/{packageId}/supplement` | 辅导员补缺 | itemType、fileIds[]、requestId | {packageId,completeness} | archive.supplement | AFFAIRS_ARCHIVE_SUPPLEMENT |
| 105 | `POST /archive/batches/{batchId}/review` | 学院完整性审查 | action(APPROVE/RETURN)、reason(RETURN≥5)、version、requestId | {batchId,status} | archive.review | APPROVAL |
| 106 | `POST /archive/batches/{batchId}/confirm` | 学工处确认归档 | version、requestId | {batchId,status:"ARCHIVED"} | archive.batch.manage | AFFAIRS_ARCHIVE_CONFIRM |
| 107 | `POST /archive/packages/{packageId}/download` | 归档包下载 | purpose(≥5)、requestId | {downloadUrl(限时),exportTaskId} | archive.download | EXPORT/DOWNLOAD |

**归档错误码**（API L389）：`409001` ARCHIVED 批次内写/非 SUPPLEMENTING 补缺；`403001` 无 psySensitive 请求含心理明细专项包；`429001` 下载限流；`403002` 跨学院审查。

### 8.2 学工统计（API §15，L397–417）

| # | 方法/路径 | 用途 | 关键入参 | 出参要点 | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| 108 | `GET /stats/overview` | 学工总览（请假/困难/奖助覆盖/处分/心理关注/风险/谈话完成率/宿舍异常/活动参与/德育积分/辅导员完成率） | semester(否)、collegeId(否,按 scope 限) | metricGroups[]（每指标含 key/value/caliber/sourceTable/refresh/drill） | stats.view | 无 |
| 109 | `GET /stats/{metricGroup}` | 分组下钻（leave/aid/funding/discipline/risk/talk/dorm/activity/counselor-kpi） | groupBy(COLLEGE/CLASS/GRADE,必)、semester/dateRange(否)、page/pageSize | breakdown[] + trend[] | stats.view | 无 |
| 110 | `POST /stats/{metricGroup}/export` | 统计导出（转发导出管线） | purpose(≥5)、filters | {exportTaskId} | stats.export | EXPORT |

**统计错误码**（API L417）：`429001` 导出限流；`403002` 请求超出 scope 的 collegeId。
**归档率入统计**：15-5 归档统计 / overview 的归档指标由 `t_affairs_archive_batch` 完成度回流。**需人工确认**归档率是否新增 `stats/{metricGroup}=archive` 分组（现枚举未显式列 archive，L398 枚举为 leave/aid/funding/discipline/risk/talk/dorm/activity/counselor-kpi）。

### 8.3 校级/学院驾驶舱端点 —— **需人工确认**
D 包施工卡 §11.3 列 `/dashboard/college`、`/dashboard/school`（L153–154），但 API 契约未定独立端点。建议**复用 #108 overview + collegeId + Dashboard 角色 preset**（API L417「接入 Dashboard 角色 preset」），不新增端点；若甲方要独立驾驶舱聚合端点，需补契约并人工确认。

---

## 9. 数据表与迁移（MySQL utf8mb4，优先复用）

> 遵循 CLAUDE.md §36（MySQL-only、utf8mb4、tenant_id、软删除+审计字段、Alembic 迁移）。归档表已在数据表草案 §3.9 定名，**优先复用，不建平行表**。

| 表名 | 复用/新增 | 业务含义 | 核心字段 | 状态枚举 | 备注 | 依据 |
|---|---|---|---|---|---|---|
| `t_affairs_archive_batch` | **新建** | 学工归档批次 | batch_name/year_code/scope_json/confirm_by/confirm_at/workflow_instance_id | DRAFT/COLLECTING/COLLEGE_REVIEW/SA_CONFIRM/ARCHIVED（**与状态机 §11 枚举待对齐，见 §4.1**） | 水印包走 export 管线并落 t_export_task(sha256)，**不建归档文件表** | 数据表 §3.9 L169 |
| `t_affairs_archive_package` | **新建** | 学生档案包（批次内每生一行，缺项清单） | batch_id/student_id/missing_items_json/package_file_id/export_task_id | PENDING_GEN/PENDING_SUPPLEMENT/SUBMITTED/ARCHIVED/RETURNED | 回链 batch_id；包文件 file_id→t_file_object；导出留痕 export_task_id→t_export_task | 数据表 §3.9 L170 |
| `t_export_task` | **复用** | 导出/归档包留痕（sha256、水印、用途） | 既有 | — | 归档包与统计导出共用，不新建 | 数据表 §3.9 L169、API L436 |
| `t_file_object` | **复用** | 文件对象（补传材料、包文件） | 既有 | — | 只存 file_id（§40 红线6） | 数据表 L170 |
| `t_security_audit_log` / 域 `audit_trail` | **复用** | 审计 | 既有 `record()` | — | 归档/下载/导出/敏感查看 | 权限总控 §复用事实 L5 |
| （统计）**无新表** | **复用** | 统计聚合 | 走 `stats_service` 读业务表/聚合表 | — | **不反写业务主表** | API L417/L552、D 包施工卡 §4 L72 |
| `t_affairs_stat_snapshot` | **需人工确认** | 统计快照 | — | — | D 包施工卡 §11.3 L152 提到 `t_affairs_stat_snapshot`，数据表草案未见此表定义——**确认是否新建快照表或纯实时聚合** | D 包施工卡 L152 |

**迁移策略**：
- 两归档表为纯新增（不改存量结构），Alembic 单 revision 可重复执行；含 `tenant_id`、创建/更新时间、软删除、审计字段（CLAUDE.md §36-5）。
- 各业务终态「ARCHIVED 只读」已在既有各业务表以 `affairs_status` / `is_archived` 标记（风险域 L285「风险枚举本身无 ARCHIVED，以 is_archived 标记」），**不改业务表结构**。
- 统计无迁移（只读）。
- **需人工确认**：`t_affairs_stat_snapshot` 是否落表；归档批次枚举命名统一。

---

## 10. Excel 导入导出（接公共底座，CLAUDE.md §38）

> 归档模块本身**无导入**（数据来自业务，不导入学生）；**导出**为核心。统一接 `app/services/excel/`（后端）+ `components/common/excel/`（前端），复用 `AppExportButton`+`AppExportConfirm`（§40）。

| 场景 | 类型 | 做法 | 依据 |
|---|---|---|---|
| 归档包下载 | 导出（打包） | 走导出管线 #107，整包水印 + 用途登记 + t_export_task + 下载审计；**非 xlsx，是归档包文件** | API #107、数据表 L169 |
| 归档批次台账导出 | 导出 Excel | 批次列表/档案包完整度按当前筛选导出 xlsx，文件名含「学工归档-租户-学年-时间」，脱敏+水印+导出台账 | CLAUDE.md §38-8、D 包施工卡 §11.2 |
| 统计报表导出 | 导出 Excel | #110 转发导出管线，按 scope 裁剪 + 脱敏 + 水印 xlsx + 导出台账；导出字段与页面一致 | API #110、D 包施工卡 §4 L73「按范围裁剪、带水印、写导出台账」、§11.3 L151「水印 xlsx」 |
| 错误行下载 | N/A | 本模块无导入，不涉及错误行 | — |

红线：导出必须**按当前筛选 + 权限控制 + 敏感脱敏 + 导出审计**（CLAUDE.md §38-8）；**不 mock 导出成功**（§40 红线）。验收：导出字段与页面一致（D 包施工卡 §4 L75）。

---

## 11. 移动端入口

| 端 | 归档 | 统计 |
|---|---|---|
| 学生端 | **不涉及**（归档是管理动作） | 不涉及 |
| 教师端（辅导员） | **缺件补传待办**可在移动端**接收提醒并跳转**；但「归档仅 PC」——完整补传/审核/下载回 PC | 不涉及（统计非高频移动场景） |
| 校领导 | — | 校级驾驶舱**只读**汇总可作移动领导视图（**需人工确认**是否纳入本卡） |

依据：API 契约 §移动端边界 L514「**归档仅 PC**；风险快速处置移动端可用，关闭需填结论建议 PC」。故本模块**移动端仅承接归档缺件待办提醒 + 跳 PC**，归档实操与统计导出**PC-only**。校领导移动驾驶舱只读口径**需人工确认**（移动端设计文档未见归档/统计学生端页，`13A-学工中心移动端入口设计.md` 学生 11 页 + 教师 8 页不含归档/统计）。

---

## 12. 验收标准（页面级用例）

### 12.1 通用（每页）
- 进入：菜单点击进入正确页，面包屑「学工中心 / 学工归档（或学工统计）/ 具体页」，一/二/三级高亮正确（CLAUDE.md §9.4 唯一 leafKey）。
- 旧路由兼容：旧 `/admin/student/archive*`（若存在）redirect 不 404；planned 期间点击进公共占位页（CLAUDE.md §42），真实上线后 leaf 改 `I()`。
- 三态：loading / empty（空数据显示 0，不显示 Invalid Date/undefined，§40 日期规则）/ error / no-permission(403) / network-error 均有明确提示。
- 无假按钮、无假数据、无 mock 成功（D 包施工卡 §4 L26、§10 L119）。
- 无控制台错误；`npm run build` 通过。

### 12.2 学工归档
- 建批次：非学工处角色 → 403；scopeConfig 越 scope → 403；含心理明细未授权 → 403001。
- 生成：GENERATING 超 2h 未完成 → 告警学工处，任务**可重跑幂等**（同 requestId 不重复生成）。
- 补缺：非 SUPPLEMENTING 状态补缺 → 409;辅导员只能补本班（跨班 → 403）。
- 审查：学院退回必填 reason≥5 字（缺则 422）；跨院审查 → 403002；version 不符 → 409。
- 确认归档：确认后批次内任何业务记录写 → 409（归档冻结）；生成水印包并落 t_export_task。
- 下载：purpose<5 字被拒并不产生下载；下载写 EXPORT/DOWNLOAD 审计 + 水印；绕过导出管线 → 403；限流 → 429001。
- 完整性：档案包 `realName` 脱敏展示；缺件清单准确；补齐后 completeness 更新。

### 12.3 学工统计
- overview 每指标自带 caliber/sourceTable/refresh/drill；**首页-列表对账 0 差异**（冻结表 §8 门禁）。
- 下钻：groupBy 必填（缺 422）；下钻数字与明细列表一致；辅导员只见本班切片；越 scope 的 collegeId → 403002。
- 导出：按当前筛选 + scope 裁剪 + 脱敏 + 水印 xlsx + 导出台账；导出字段与页面一致；限流 → 429001。
- 跨学院不可见（学院角色看本院；D 包施工卡 §4 L75「跨学院不可见」）。
- 心理类统计**只出脱敏聚合**，不出个人明细（权限总控 §6、状态机 stats.view 心=限心理类 L549）。

---

## 13. 依据文档索引（每条标来源 + 章节/行号）

| 主题 | 来源文件 | 章节/行号 |
|---|---|---|
| §0.0 对标规则 | `CLAUDE.md` | §0.0 市场验证优先与成熟商业系统复刻规则 |
| 三家对标（正方/强智/青果）+15 原则+缺口 | `13A-学工中心-商业化对标审计与补丁建议（第一轮）.md` | L6、L73–103、#17/#18 缺口 L128–129、第五步 17/18 项 L170/L172 |
| 归档状态机（枚举/流转/责任人/超期/防护） | `13A-学工中心状态机与权限矩阵.md` | §11 L426–453、§11.1 L444–448、§11.2 L450–453 |
| 归档/统计权限点 | 同上 | §12 L541–550 |
| 归档数据范围 | 同上 | §13 归档行 L573、scope 表 L590 |
| 归档 API 7 端点 + 错误码 | `13A-学工中心API契约草案.md` | §14 L377–389 |
| 统计 API 3 端点 + overview 示例 + 实现方式 | 同上 | §15 L393–417、L552 |
| 移动端「归档仅 PC」边界 | 同上 | L514 |
| 归档两表 + 复用 t_export_task/t_file_object | `跨模块融合/13A-13B-数据表与迁移策略草案.md` | §3.9 L167–170 |
| 页面树 15-1~15-5 / 16-1 + 路由约定 | `13A-学工中心页面树与路由设计.md` | §3.11 L319–328、L164–172、路由约定 L28、L409–418 |
| D 包范围/施工卡/生产级红线/驾驶舱 | `13A-学工中心D包-上线补强与商业增强施工卡.md` | §1 L10–16、§3 L53–63、§4 L65–75、§11.2 L138–145、§11.3 L147–154 |
| 施工图 planned/P2/D + 三级清单 | `13A-学工中心全量规划施工图.md` | L49–50、L299–325 |
| 角色模板（学工处=全校+归档）/四层裁定/数据范围机制 | `系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md` | L5、L70、L262、§3.3 |
| MySQL-only / Excel 底座 / 公共组件 / 日期 | `CLAUDE.md` | §36、§38、§40、§42 |
| 文档关联索引（统计/导入导出落点） | `docs/03-业务模块设计/学工中心/文档关联索引.md` | L21、L23 |

**需人工确认清单（读不到确定依据处）**：
1. 归档批次枚举命名统一（状态机 §11 `GENERATING/SUPPLEMENTING/AFFAIRS_CONFIRM` vs 数据表 §3.9 `COLLECTING/SA_CONFIRM`）——冻结前必须对齐。
2. `t_affairs_stat_snapshot` 是否落表（D 包施工卡 §11.3 L152 提及，数据表草案未定义）。
3. 校级/学院独立驾驶舱端点（复用 overview 还是新增）。
4. 归档率是否新增 `stats/{metricGroup}=archive` 分组。
5. 档案包级枚举与批次级枚举联动映射。
6. 校领导移动端只读驾驶舱是否纳入本卡。
7. 三家产品「档案封存/多维统计」私有细节（无联网，未逐条核验）。

---

## 14. 施工顺序与依赖

### 14.1 前置依赖
- **上游数据**：归档汇聚 B 包（请假/宿舍）、C 包（困难/奖助/处分/审批）、各业务谈话/风险/家校数据。归档「有效性」依赖上游业务已产生真实数据（施工图 L49「等 B/C 产生材料后汇总」）。
- **复用底座**：`t_export_task`（导出/水印/sha256）、`t_file_object`（文件中心）、`stats_service`（统计聚合）、`t_security_audit_log`+`audit_trail`（审计）、`resolve_teacher_scope`/`getStudentAffairsScope`（数据范围）、Workflow 引擎（`affairs_archive_review`，状态机 L646）。
- **公共组件**：`AppExportButton`/`AppExportConfirm`、`AppSensitiveText`、`AppAuditTrail`、`AppFileList`/`AppFilePreview`、`AppMetricCard`/`AppChartCard`、`AppDateRangePicker`（施工图 L49–50 列出）、`AppWorkflowTimeline`（归档审批链）。

### 14.2 建议施工顺序（一次做深，先归档后统计）
1. **迁移**：新增 `t_affairs_archive_batch`、`t_affairs_archive_package`（Alembic，MySQL utf8mb4，含 tenant_id/审计/软删除）；确认统计快照表口径（§9 待确认项）。先解决 §13 待确认 1/2/5（枚举与快照）。
2. **后端归档**：model → service（生成/补缺/审查/确认/下载，接 Workflow + export 管线）→ API #101–107 → pytest（MySQL 测试库）。含状态机防护（409/403）与超期任务（GENERATING 2h、SUPPLEMENTING 14 天）。
3. **后端统计**：扩展 `stats_service` 聚合 → API #108–110（scope 注入、caliber、drill、export）→ pytest。归档率指标回流。
4. **前端归档**：15-1 列表 → 15-2 创建 → 15-3 档案包详情（目录树/完整度/缺件/补传/水印下载）→ 15-4 审核确认。用公共组件，不自造。
5. **前端统计**：16-1 驾驶舱（指标卡 + 口径 tooltip + 多维下钻 + 导出）+ 15-5 归档率。
6. **navPlan 收口**：真实完成的 leaf 由 `P()` 改 `I(label, path)`，占位路径让位（CLAUDE.md §42-5）；侧栏实测高亮（§9.4）。
7. **验收 + 施工记录**：按 §12 逐页用例；写入 `docs/施工记录/历史欠账.md`（关闭/新增欠账）。

### 14.3 风险点
- **枚举撞车**（状态机 vs 数据表）——最高风险，前后端开工前必须统一（§13 确认项 1）。
- **口径两套数**——统计必须复用 `stats_service`，与各业务 stats 端点（05-7/06-8/07-12/…）同源，否则违反「汇总-明细对账 0 差异」门禁。
- **敏感泄漏**——归档包默认含敏感原文是红线事故；默认剔除，专项授权才含。
- **归档包绕过导出管线**——必须走 t_export_task + 水印 + 审计。
- **数据范围放大**——学院/辅导员越 scope 必须后端 403，不能只靠前端隐藏。

### 14.4 建议 commit 粒度
- `feat(sa-archive): archive batch/package tables + migration`
- `feat(sa-archive): archive service & api (#101-107) + workflow + export pipeline`
- `feat(sa-stats): student-affairs stats service & api (#108-110)`
- `feat(sa-archive): PC pages 15-1~15-4 archive batch & student package`
- `feat(sa-stats): PC page 16-1 dashboard + 15-5 archive-rate`
- `chore(nav): flip archive/stats leaves P()->I() after acceptance`
- `docs(record): update 历史欠账 for sa-archive-stats`

> 每个 commit 附「实际改了什么 / 未改禁止文件 / 检查命令 / `git status --short` / 是否需人工确认」（CLAUDE.md §1.2、§23）。

---

> 本卡为文档输入，未改任何代码 / navPlan / 迁移。开工前请先解决 §13「需人工确认」7 项（尤其枚举统一），再按 §14 顺序施工。
