# 施工卡 · 学工中心 · 心理关注（sa-mental / D 包第 10 步）

> 模块 key：`studentAffairs` · 二级 mod：`sa-mental`（心理关注）
> 当前状态：**planned（待施工）· 强敏感红线**。本卡为「照着开发」的施工输入，不是实现记录。
> navPlan 现状证据：`frontend/src/config/navPlan.js` L155–158 —— `mod('sa-mental','心理关注', null, P('心理关注名单','心理预警摘要','谈话转介与回访','危机升级','心理统计'))`，五个三级页面全部 `P()`（planned）。
> **口径纪律**：planned 页不臆造已实现字段/接口值；凡草案项标「草案」，凡无依据项标「需人工确认」。本卡不改任何代码、navPlan、迁移、配置，仅新增本文件。
> **联网声明**：本次未联网检索。按 CLAUDE.md §0.0「无法联网必须改搜仓库已有资料」，三家成熟系统对标全部引用仓库内已完成的《13A-学工中心-商业化对标审计与补丁建议（第一轮）》（已对标正方/强智/青果，含 15 条精华与缺口表）。凡外部产品结论，均标注来自该审计文档，未独立二次核实厂商官方手册者标「需人工确认」。

---

## 1. 模块定位与真实学校业务价值

**一句话定位**：心理关注是学工中心里**敏感级最高**的处置型业务，服务于「早发现—早关注—早干预—可追溯」的学生心理健康安全底线，**不做临床诊断，只做管理侧的关注、预警、转介、随访、危机升级留痕**。

**真实学校谁用、解决什么**（依据 权限总控 L268 心理老师角色、总册 §3.9）：

| 角色 | 真实场景 | 本模块解决 |
|---|---|---|
| 心理老师（心理中心） | 拿到授权关注名单，做关注等级维护、约谈、转介校外医院、危机上报 | 授权范围内心理明细的唯一可写方；转介/随访/危机升级闭环留痕 |
| 授权辅导员 | 班上有需重点关注学生，需知道「要不要跟、跟到什么程度」 | 仅对 `PSY_STUDENT` 授权学生看明细；其余仅见「需关注」标记 |
| 学院学工负责人 / 学工处 | 督办本院/全校心理关注与危机处置进度 | 看**脱敏摘要与进度**，不看咨询原文（权限总控 L262「看心理原始明细除非授权」为禁做项） |
| 校领导 | 校级心理健康态势汇总 | 只读脱敏统计，不下钻到人（施工图 L39「敏感权限先设计后施工」） |
| 普通教师 / 学生本人 / 家长 | —— | **不可见来源明细**；学生本人仅关怀提示（权限矩阵 L568），家长不可见 |

**为什么不能做成自嗨功能**（CLAUDE.md §0.0 / §6）：心理数据是全系统最高敏感级（权限矩阵 L568「最高敏感级」）。做浅了（无授权控制、无审计、把明细塞进普通风险详情）不是功能少，而是**合规事故**。成熟学工系统对心理模块的共识是「**宁可少字段，不可漏审计**」——本卡把安全红线放在功能之前。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点）

> **对标来源统一声明**：以下三家的流程/角色/字段/亮点/缺点，均转引自仓库《13A-学工中心-商业化对标审计与补丁建议（第一轮）》对正方/强智/青果的「产品精华与业务成熟度」提炼（该文 L6 明确对标口径为业务成熟度，不抄界面/代码/数据库）。**未独立联网核对三家官方手册，具体到某厂商的字段级细节标「需人工确认」。**

### ① 对标对象 A：正方（教务起家、学工一体化）
- 核心流程：心理普查/测评导入 → 建立心理档案 → 关注分级 → 约谈记录 → 预警名单 → 上报。
- 角色：心理中心教师、二级学院、辅导员、学生（测评作答）。
- 字段（需人工确认字段级）：关注等级、测评量表结果、约谈记录、预警级别、跟进人。
- 亮点：与学籍/成绩打通，异常联动学业预警；分级明确。
- 缺点：心理与普通学工权限边界偏粗，明细脱敏依赖实施配置。

### ② 对标对象 B：强智（教学 + 学工）
- 核心流程：心理测评计划 → 学生作答 → 结果解读（仅心理老师）→ 重点关注库 → 危机上报 → 归档。
- 角色：心理老师、学院、辅导员（仅结论）、学生。
- 字段（需人工确认）：测评批次、量表得分、风险结论、干预记录、随访。
- 亮点：测评—关注—干预链条完整；辅导员只见「需关注」结论，隐私控制较好。
- 缺点：危机干预 SOP 与校外转介偏弱，多靠线下。

### ③ 对标对象 C：青果（学工 / 迎新 / 资助见长）
- 核心流程：关注名单维护 → 谈话/咨询预约 → 咨询记录（强隐私）→ 转介 → 随访 → 结案。
- 角色：心理咨询师、辅导员、学工处、学生。
- 字段（需人工确认）：咨询预约、咨询记录、转介单、随访计划、结案结论。
- 亮点：咨询记录强隐私 + 审计；预约—记录—随访贴合心理中心真实动线。
- 缺点：与全校风险预警中枢的联动、领导侧脱敏驾驶舱较弱。

### ④ 三家共同具备的核心功能（= 本项目必须具备的基础能力）
1. **授权关注名单**（谁被谁授权关注，逐生授权，不按班级通配）。
2. **关注分级 + 预警摘要**（分级驱动待办与上报）。
3. **咨询/约谈/转介/随访记录**（强隐私、可追溯，不外泄）。
4. **危机上报/升级**（高危可即时上报到心理中心/学工处）。
5. **辅导员只见「需关注」结论、心理老师见明细**的分层可见。
6. **脱敏统计**（数量/分级/趋势，明细下钻需权限）。
7. **全链路审计**（查看/解锁/导出/转介/结案均留痕）。

### ⑤ 三家里最值得吸收的最佳做法
- **青果的「预约—咨询记录—随访」强隐私动线** + **强智的「辅导员只见结论」分层** + **正方的「异常联动风险/学业预警」**。三者合并即本项目的目标形态：**心理明细收敛在心理老师/授权辅导员，向风险中枢只输出「授权摘要/风险等级/待办」，绝不把原文写入普通风险详情**（与 D 包卡 §2「联动」红线一致）。

### ⑥ 本项目当前已有能力（证据）
- `t_cs_mental_record`（心理关注记录表）**已存在**：字段 `level / last_follow_time / next_follow_time / summary / counselor_note(涉密) / status`（`backend/app/models/campus_service.py` L132–141）。
- 心理来源风险已并入风险中枢 `t_affairs_risk_record`（`source=MENTAL`，`detail` 注释「MENTAL 来源明细仅授权角色可见」，`backend/app/models/affairs_discipline.py` L53–75）+ 处置留痕 `t_affairs_risk_handle_record`（L78–88）。
- 风险预警状态机 8 态、分派矩阵、心理明细收敛规则、导出排除，均已设计（总册 §3.9 L498–549；状态机 §6 L265–292）。
- 数据范围 `PSY_STUDENT`（逐生授权、防扩散、授权增删写 PERMISSION_CHANGE 审计）已定义（状态机 L602/L610；权限总控 L364/L375）。
- 权限点已在权限矩阵登记：`studentAffairs.risk.psyDetail.view`（强制审计）、`studentAffairs.risk.export`（默认不含心理明细）、`studentAffairs.archive.psySensitive`（状态机 L516/L517/L547）。

### ⑦ 缺失的生产级闭环（= 缺口）
- **心理专属 PC 页面 0 个**（navPlan 五页全 planned）；施工图 L39「未建完整 PC / 未确认完整 API」。
- **转介（referral）/随访（followup）/危机升级（crisis）三条记录链未落表未落接口**（总册 §3.9 缺口标注、审计文档第五步 §9「转介记录🔧 回访计划🔧 危机升级🔧」）。
- **心理测评量表集成**为 P2/P3（总册 §4.6），当前**只做接口位**，不做量表引擎。
- **心理脱敏统计页**未建（施工图 L192「心理统计-脱敏统计」）。

### ⑧ 本卡必须补齐（本轮范围）
五个 planned 三级页面的**设计闭环**（页面/流程/字段/权限/审计/API 草案/验收），使其达到「可照着开发、开发完即可标 partial→implemented」的粒度。**复用**现有 `t_cs_mental_record` 与风险中枢表，**不建平行心理表**（除非新增转介/随访子表，见 §9）。

### ⑨ 进 backlog（能力池，本卡不做实现）
- 心理测评量表引擎 / 第三方测评对接（总册 §4.6 P2/P3）——仅留 `source=PSY` 接口位。
- 行为大数据心理预警模型（总册 §3.9 ⑰ P2P3）。
- 家长端心理关怀推送（权限总控：家长不可见心理，§13）。
- 心理咨询排班/房间预约资源管理（如学校有独立心理中心系统则不重复建，需人工确认）。

### ⑩ 禁止做成假功能（红线）
- 禁止在页面写死「诊断结论」文本或 AI 生成诊断（D 包卡 §2 红线、总册 L704）。
- 禁止把心理明细塞进普通风险详情/普通画像段（默认段落整体不返回，见 §7）。
- 禁止导出携带咨询原文/量表明细/危机细节（D 包卡 §2 导出红线）。
- 禁止用 mock 数据冒充统计；禁止仅前端隐藏按钮代替后端鉴权（CLAUDE.md §3.4/§17）。

---

## 3. 三级页面清单与状态（对齐施工图）

navPlan `sa-mental` 下 5 个三级页面（现状 planned，进入公共规划占位页 `/admin/planned/...`，见 CLAUDE.md §42）：

| # | 三级页面 | 目标定位 | 状态 | 强敏感红线口径 |
|---|---|---|---|---|
| 1 | **心理关注名单** | 授权关注学生列表 + 关注等级 + 下次随访；心理老师维护 `t_cs_mental_record` | planned | 普通角色只见「需关注」标记；明细需 `psyDetail.view`+`PSY_STUDENT`，越权 403+审计；不写诊断 |
| 2 | **心理预警摘要** | 从风险中枢 `source=MENTAL` 汇聚的预警摘要卡 + 待办 | planned | 向风险页只输出「授权摘要/等级/待办」，明细不外泄；辅导员见等级不见原文 |
| 3 | **谈话转介与回访** | 心理约谈 → 校内/校外转介 → 随访计划 → 结案的记录链 | planned | 咨询/转介/随访原文强隐私加密；查看写 SENSITIVE_VIEW 审计 |
| 4 | **危机升级** | 高危（CRITICAL）即时上报心理中心/学工处的升级链 + 干预时间线 | planned | 危机细节最小可见；升级/接管/结案全链路审计；SOP 时限需人工确认 |
| 5 | **心理统计** | 脱敏统计：关注人数/分级分布/趋势/处置时长/随访完成率 | planned | 只出脱敏聚合，明细下钻需权限；导出剔除敏感原文（施工图 L192） |

> 说明：施工图 L179–192 列出更细的心理健康能力池 14 项（心理看板/测评/测评结果/重点关注/咨询预约/咨询记录/危机预警/危机干预/转介记录/回访记录/心理活动/心理档案/心理权限审计/心理统计）。**本卡以 navPlan 冻结的 5 页为交付单元**，把 14 项能力池收敛映射进 5 页；测评/测评结果/心理活动进 backlog（§2⑨），不在本卡一次交付。
> **测评属接口位**：任何测评相关入口本卡只留 `source=PSY` 数据位，不做量表作答/评分页（总册 §4.6）。

---

## 4. 业务流程与状态机

### 4.1 心理关注记录（`t_cs_mental_record`，已实现表 / 页面未建）
- **状态**（模型 `status` 默认 `PROCESSING`，现有枚举需人工确认收敛）：草案 `PROCESSING（关注中）/ FOLLOWING（随访中）/ CLOSED（结案）`。
- **关注等级** `level`（默认 `NORMAL`）：草案 `NORMAL / ATTENTION / KEY / CRISIS`（需与学校心理中心口径对齐，**需人工确认**）。
- 责任人：心理老师（唯一可写明细）；授权辅导员协同。

### 4.2 心理风险与升级（复用风险中枢，**已实现状态机**，不重复设计）
风险预警 8 态（状态机 §6 L267，**已实现**，本卡直接复用，禁止另造）：
`NEW → ASSIGNED → PROCESSING → FOLLOWING →（TRANSFERRED/ESCALATED 为流水事件）→ CLOSED →（同源再触发）REOPENED`
- 心理来源默认等级 `HIGH`；首责=心理老师，协同=授权辅导员（总册 L524 分派矩阵）。
- **危机升级**：`ESCALATED` 流水 + 通知学院学工/学工处 `RISK_ALERT`；`CRITICAL` 级超时自动升级（时限 **需人工确认**，总册 §3.9 ⑱、L508 示例 72h）。
- 非法转移 409；NEW/ASSIGNED 无处置记录直接关闭 409（状态机 L290）。

### 4.3 谈话转介与回访（记录链，草案）
`约谈记录 →（需转介）建转介单 REFERRED →（校内/校外）→ 随访计划 FOLLOW_PLANNED → 随访记录 → 结案 CLOSED`
- 与谈心谈话模块联动：心理类谈话记录 `content_encrypted`，非授权仅显示「心理类谈话 N 次」（总册 §3.10 L561）。
- 转介/随访为 append-only 流水，责任人=心理老师；结案结论≥N 字（阈值草案，需人工确认）。

> 已实现项标注：风险 8 态状态机、心理明细收敛、导出排除、PSY_STUDENT 数据范围解析——**均已实现/已设计，本卡复用不重做**。缺口项：转介/随访/危机三条记录链的落表落接口（§9 新增子表）。

---

## 5. 表单字段与校验规则

> 逐字段列出。planned 页字段为**草案**，最终以现场确认与后端模型冻结为准；敏感级：S3=最高敏感（心理明细）、S2=脱敏可见摘要、S1=一般。

### 5.1 心理关注名单 · 关注记录表单（映射 `t_cs_mental_record`）
| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| 学生（cs_student_id） | 选择器 AppStudentPicker | 是 | 必在 `PSY_STUDENT` 授权范围内，否则 403 | S1 |
| 关注等级 level | 枚举 | 是 | NORMAL/ATTENTION/KEY/CRISIS（草案，需人工确认） | S2 |
| 关注摘要 summary | 文本 ≤500 | 否 | 长度≤500；不得含诊断结论文案（红线） | S2 |
| 咨询/辅导备注 counselor_note | 文本 ≤1000 | 否 | **涉密**：非授权角色整字段不返回（模型 L139 注释） | S3 |
| 上次随访 last_follow_time | 日期时间 | 否 | 公共日期组件；≤当前时间（CLAUDE.md §40） | S1 |
| 下次随访 next_follow_time | 日期时间 | 否 | 公共日期组件；≥当前时间；到期生成待办 | S1 |
| 状态 status | 枚举 | 是 | PROCESSING/FOLLOWING/CLOSED | S1 |

### 5.2 谈话转介与回访 · 转介单（草案，新增子表见 §9）
| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| 关联关注记录 mental_id | 隐藏引用 | 是 | 必属授权范围 | S1 |
| 转介类型 refer_type | 枚举 | 是 | INTERNAL(校内)/EXTERNAL(校外医院)（草案） | S2 |
| 转介去向 refer_to | 文本 ≤200 | 是 | —— | S3 |
| 转介原因 reason | 文本 ≤1000 | 是 | ≥N 字（草案）；不写诊断，只写关注事实 | S3 |
| 随访计划时间 followup_at | 日期时间 | 否 | 公共日期组件 | S1 |
| 随访记录 followup_note | 文本 ≤1000 | 否 | 查看写 SENSITIVE_VIEW 审计 | S3 |
| 结案结论 close_conclusion | 文本 | 结案时是 | ≥N 字（草案，需人工确认） | S3 |

### 5.3 危机升级（复用风险处置字段，已实现）
`handleType=ESCALATE`、`content(≥10字)`、`version`（乐观锁）、`requestId`（幂等）——沿用风险处置接口入参（API 契约 L280），不新增表单校验体系。

---

## 6. 权限矩阵与数据范围

> 引用权限总控 `docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md` L268/L364/L375、状态机 §权限矩阵 L512–580。

### 6.1 角色可见/可操作（心理域）
| 权限点 | 学工处 | 学院学工 | 辅导员 | 班主任 | 心理老师 | 宿管 | 资助 | 学生 |
|---|---|---|---|---|---|---|---|---|
| `studentAffairs.psy.view`（关注名单/明细段） | 限(授权) | ✗(仅"需关注") | 限(PSY_STUDENT) | ✗ | ✓(授权学生) | ✗ | ✗ | ✗ |
| `studentAffairs.psy.manage`（写关注记录/转介/随访）（草案） | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| `studentAffairs.risk.psyDetail.view`（心理来源明细，强制审计） | 限(授权) | ✗ | 限(授权) | ✗ | ✓ | ✗ | ✗ | ✗ |
| `studentAffairs.risk.escalate`（危机升级） | ✓ | 限 | 限(授权) | ✗ | ✓ | ✗ | ✗ | ✗ |
| `studentAffairs.psy.stats.view`（脱敏统计）（草案） | ✓ | 限(本院脱敏) | 限(本班脱敏) | ✗ | ✓ | ✗ | ✗ | ✗ |
| `studentAffairs.risk.export`（默认不含心理明细） | ✓ | 限 | ✗ | ✗ | 限(心理专项) | ✗ | ✗ | ✗ |

> 证据：状态机 L516/L517/L568；权限总控 L268（心理老师禁「输出诊断结论、明细外泄」）、L262（学工处禁「看心理原始明细除非授权」）。`studentAffairs.psy.manage` / `.stats.view` 为本卡草案权限点，命名遵循 CLAUDE.md §10.3 `module.domain.action`，**冻结前需人工确认**。

### 6.2 数据范围（来自真实业务关系，非角色名）
- **心理老师** → `scope_type=PSY_STUDENT`：逐生授权清单，**不支持班级/学院通配**（防心理数据扩散，状态机 L610）；授权/回收由学工处操作并写 `PERMISSION_CHANGE` 审计。
- **授权辅导员** → 本班 `CLASS/ADVISOR` 数据范围 **且** 命中 `PSY_STUDENT` 授权行，方可见明细；未授权仅「需关注」。
- **学院学工/学工处** → 本院/全校**脱敏摘要与进度**，明细仍需专项授权。
- **canAccessAffairsStudent** 七路判定含「心理授权」路（状态机 L619），列表过滤与写校验共用同一函数，越权 403+审计（状态机 L31「看得见=能处理」）。
- **学生本人** → 仅关怀提示，不见记录（权限矩阵 L568）；**家长不可见**（权限总控 §13）。

---

## 7. 敏感字段脱敏与审计（§6 红线落地）

依据 CLAUDE.md §6、状态机 L568/L580、D 包卡 §2：

1. **最小授权**：心理明细（`counselor_note`、转介原文、随访原文、危机细节）默认**段落整体不返回**（非返回空值，防试探，总册 L263）。
2. **查看原因 + 二次确认**：解锁 S3 明细须填 reason（阈值≥N 字，草案）；每次读取写 `SENSITIVE_VIEW` 审计（状态机 L580）。
3. **水印**：任何心理明细页/导出带租户+用户+时间水印（复用 AppWatermark，CLAUDE.md §41）。
4. **审计留痕**：查看/解锁/导出/转介/升级/结案/授权增删（`PERMISSION_CHANGE`）全部落 `t_cs_audit_trail`（模型 L144–154，append-only）或统一审计表；平台方不可删改学校审计（权限总控 L163）。
5. **导出排除**：导出列配置硬编码排除心理明细（状态机 L532）；专项含明细导出走 `archive.psySensitive` 权限点 + 二次确认 + `SENSITIVE_VIEW`（状态机 L547）。
6. **不写诊断**：系统不生成、不展示诊断结论（红线，总册 L704）。

> **组件安全红线**（CLAUDE.md §40.4）：敏感字段一律 `AppSensitiveText`；审计展示一律 `AppAuditTrail`（只读后端真实审计，不伪造）；`AppPermissionButton` 只做前端体验，越权拦截由后端 `authz` 裁定。

---

## 8. API 契约草案

> **复用（已实现，直接调用，不新建）** —— 风险中枢链路（API 契约 §9 L269–292）：
> - `GET /api/v1/student-affairs/risk/records?source=MENTAL&...`（心理来源明细自动收敛）
> - `GET /risk/records/{riskId}`（心理明细按 `psyDetail.view`，读取 `SENSITIVE_VIEW` 审计）
> - `POST /risk/records/{riskId}/escalate`（危机升级，`reason≥5字`+`version`）
> - `POST /risk/records/{riskId}/handle | /close | /reopen`
> 错误码沿用：401 未登录 / 403001 无权限 / 403002 不在 scope / 404001 记录不存在/跨租户 / 409001 非法状态转移 / 422001 参数校验失败。

**新增草案端点**（planned，命名遵循现有 `/api/v1/student-affairs/...` 前缀；入参/出参为草案，冻结前需人工确认）：

| # | 端点 | 方法 | 入参(草案) | 出参(草案) | 权限点 | 审计 |
|---|---|---|---|---|---|---|
| M1 | `/psy/mental-records` | GET | level/status/keyword/page/pageSize；范围由 PSY_STUDENT 解析 | list[{id,studentNo,realName(脱敏),level,status,nextFollowAt}] | `studentAffairs.psy.view` | 无(列表读) |
| M2 | `/psy/mental-records` | POST | studentId/level/summary/counselorNote/nextFollowAt/requestId | {id,status} | `studentAffairs.psy.manage` | AFFAIRS_PSY_CREATE + SENSITIVE_VIEW(note) |
| M3 | `/psy/mental-records/{id}` | GET | reason(解锁明细时必填≥N字) | detail（无权限时 counselorNote 段不返回） | `studentAffairs.psy.view` / 明细 `.risk.psyDetail.view` | SENSITIVE_VIEW |
| M4 | `/psy/mental-records/{id}` | PATCH | level/summary/counselorNote/status/version/requestId | {id,status} | `studentAffairs.psy.manage` | AFFAIRS_PSY_UPDATE |
| M5 | `/psy/referrals` | POST | mentalId/referType/referTo/reason/followupAt/requestId | {referralId,status:"REFERRED"} | `studentAffairs.psy.manage` | AFFAIRS_PSY_REFER |
| M6 | `/psy/referrals/{id}/followup` | POST | followupNote/nextFollowAt/version/requestId | {referralId,status:"FOLLOW_PLANNED"} | `studentAffairs.psy.manage` | AFFAIRS_PSY_FOLLOWUP |
| M7 | `/psy/referrals/{id}/close` | POST | closeConclusion(≥N字)/version/requestId | {referralId,status:"CLOSED"} | `studentAffairs.psy.manage` | AFFAIRS_PSY_CLOSE |
| M8 | `/psy/stats` | GET | dim(college/class)/dateRange/level | {counts,levelDist,trend,avgHandle,followupRate}（脱敏聚合） | `studentAffairs.psy.stats.view` | 无(明细下钻另计) |

> 错误码统一：401/403001/403002/404001/409001/422001（同上）。M2/M4/M5/M6/M7 均要求 `requestId` 幂等 + `version` 乐观锁（防并发，CLAUDE.md §18）。**所有写操作不得 mock 成功**（§38.9）。

---

## 9. 数据表与迁移（MySQL utf8mb4 + tenant_id + 软删除/审计）

> 原则：**优先复用现有表，不建平行心理表**（状态机 L139「13A V1 不建心理新表」；L196「不新建心理表/预警表」）。

### 9.1 复用（已存在，不新增）
| 表 | 用途 | 证据 |
|---|---|---|
| `t_cs_mental_record` | 心理关注记录（等级/摘要/涉密备注/随访/状态） | 模型 `campus_service.py` L132–141 |
| `t_affairs_risk_record` | 心理来源风险（source=MENTAL，明细收敛，8态，唯一防重） | `affairs_discipline.py` L53–75 |
| `t_affairs_risk_handle_record` | 危机升级/处置留痕（append-only） | 同上 L78–88 |
| `t_cs_audit_trail` / 统一审计 | 敏感查看/导出/授权审计 | 模型 L144–154 |
| `t_teacher_student_scope`（scope_type=PSY_STUDENT） | 逐生心理授权 | 状态机 L602/L610 |

### 9.2 新增（仅转介/随访链路，草案，需人工确认后再落 Alembic）
- `t_affairs_psy_referral`（转介随访单）：`id / tenant_id / mental_id / student_id / refer_type / refer_to / reason(加密) / followup_at / followup_note(加密) / status / close_conclusion` + `CommonMixin`（`created_at/updated_at/created_by/updated_by/is_deleted/version`，base.py L37–41）。
- 建表须：`utf8mb4_unicode_ci`；`tenant_id` 行级隔离 + 索引；软删除 `is_deleted`；敏感文本列考虑应用层加密（对齐谈话 `content_encrypted` 做法，总册 L566）。
- **必须走 Alembic migration，可重复执行**（CLAUDE.md §36），禁止 `create_all` 长期替代；建表前确认连接 MySQL（非 SQLite）。
- 是否真需要独立 `psy_referral` 表 vs 复用 `t_affairs_risk_handle_record` 扩 `action` 枚举 —— **需人工确认**（倾向新子表，因转介有独立生命周期与结案结论）。

---

## 10. Excel 导入导出（接公共底座）

依据 CLAUDE.md §38、审计文档，接 `app/services/excel/` 公共管道，**不自造解析/校验/错误行逻辑**：

- **导入**（心理关注名单初始化，谨慎）：下载 Excel 模板 → 上传 xlsx → 字段校验/必填/格式/文件内重复/库内重复 → 错误行预览 → 下载错误行 Excel → 确认导入 → 导入记录 + 审计。**导入仅限心理老师，且导入学生须在其 PSY_STUDENT 授权范围**，越权行判错。**counselor_note 涉密列默认不在批量导入模板中**（避免明文批量流转，需人工确认）。
- **导出**：按当前筛选 + 权限裁剪 + **默认剔除心理明细/咨询原文/量表/危机细节**（D 包卡 §2）；文件名含模块名+租户+时间；导出写审计；含明细专项导出走 `archive.psySensitive` 二次授权。
- 统计导出：`AppExportButton + AppExportConfirm`，脱敏聚合，写导出台账（§40.4）。

---

## 11. 移动端入口

依据总册 §3.9 ⑮「学生小程序=无（对学生不可见）」、移动端设计：

| 端 | 入口 | 口径 |
|---|---|---|
| 学生端 | **无心理明细入口** | 仅「谈话邀约」时间地点可见（总册 L553），不见任何心理记录；家长端不可见 |
| 教师端（心理老师/授权辅导员） | 工作台「风险学生」→ 心理来源处置页（填流水/升级/关闭） | 移动端可写处置流水；复杂转介/统计回 PC（D 包卡 §小程序教师端「复杂配置回 PC」） |
| 敏感缓存红线 | 心理明细**不落本地缓存**（审计文档第五步 §19 缺口，统一红线） | 弱网草稿不缓存 S3 字段 |

> 移动端只做高频只读+轻处置，**心理关注名单维护、转介、统计不在移动端做**（最小暴露原则）。

---

## 12. 验收标准（页面级用例）

对每个 planned 页，开发完成后须逐项过：

| 用例 | 判据 |
|---|---|
| 进入 | 5 页可从 `sa-mental` 二级进入，施工完成前进公共规划占位页（§42），完成一页 navPlan 改 `I(label,path)` 让位 |
| 旧路由兼容 | 若映射旧 `/admin/campus-service/*` 心理入口，redirect 不 404（CLAUDE.md §9.1） |
| 权限 | 未授权访问明细 403001；不在 scope 403002；普通教师仅见「需关注」标记 |
| 数据范围 | 心理老师仅见 PSY_STUDENT 授权学生；授权回收后立即不可见；辅导员仅授权学生见明细 |
| 脱敏 | `counselor_note`/转介原文/随访原文无权限时**整段不返回**；列表姓名脱敏 |
| 审计 | 查看明细/解锁/导出/转介/升级/结案/授权增删均写审计，可追溯到人+时间+原因 |
| 三态 | loading / empty / error / no-permission / network-error / validation-error 全覆盖（CLAUDE.md §17） |
| 导出 | 默认导出无敏感原文；带水印；写导出台账；含明细需二次授权 |
| 不写诊断 | 页面无「诊断结论」字段/文案；无 AI 诊断 |
| 无假按钮 | 无 mock 成功；写操作走真实后端 + MySQL；危机升级全链路可追溯（D 包卡 §2 验收） |
| build | `npm run build` 通过；后端 pytest（MySQL 测试库）覆盖越权 403 / 非法转移 409 |

---

## 13. 依据文档索引（逐条标来源）

| 结论 | 来源文件 · 章节/行号 |
|---|---|
| §0.0 对标十点结构、无法联网改搜仓库 | `CLAUDE.md` §0.0 |
| 三家（正方/强智/青果）对标、15 精华、缺口表 | `docs/03-业务模块设计/学工中心/13A-学工中心-商业化对标审计与补丁建议（第一轮）.md` L6、L71–174（第三/四/五步）、L154（心理缺口：转介/回访/危机升级） |
| 心理关注+风险预警业务流程/分派矩阵/状态机 | `13A-学工中心全业务流程设计总册.md` §3.9 L498–549 |
| 谈话转介/随访/心理类加密 | 同上 §3.10 L551–575 |
| 心理测评深度集成 P2/P3（接口位，不做引擎） | 同上 §4.6 L699–701 |
| 风险 8 态状态机、心理明细收敛、导出排除、超时升级 | `13A-学工中心状态机与权限矩阵.md` §6 L265–292；敏感字段矩阵 L568/L580 |
| PSY_STUDENT 逐生授权、防扩散、授权审计 | 同上 L602/L610；`00-系统管理中心-权限角色模块授权与权责边界设计.md` L364/L375 |
| 心理老师角色权责与禁做项 | `00-系统管理中心...权责边界设计.md` L268；学工处禁看原始明细 L262 |
| 家长不可见心理 | 同上 §13（家长/监护人边界） |
| 风险 API（escalate/handle/close/reopen/psyDetail） | `13A-学工中心API契约草案.md` §9 L269–292 |
| navPlan 5 页 planned 现状 | `frontend/src/config/navPlan.js` L155–158 |
| `t_cs_mental_record` 字段 | `backend/app/models/campus_service.py` L132–141 |
| `t_affairs_risk_record` / `t_affairs_risk_handle_record` 字段 | `backend/app/models/affairs_discipline.py` L53–88 |
| 公共字段/软删除/审计 append-only 约定 | `backend/app/models/base.py` L5–41 |
| D 包心理健康安全施工卡（页面/红线/状态机/联动/验收） | `13A-学工中心D包-上线补强与商业增强施工卡.md` §2 |
| 心理健康能力池 14 项、心理统计脱敏 | `13A-学工中心全量规划施工图.md` L39、L179–192 |
| 公共组件强制复用、日期组件 | `CLAUDE.md` §40/§41/§40(日期) |
| 规划占位页规则 | `CLAUDE.md` §42 |
| **需人工确认项** | 关注等级/状态枚举收敛、CRISIS 升级时限、结案结论字数阈值、`psy_referral` 是否独立建表、导入模板是否含涉密列、草案权限点 `psy.manage`/`psy.stats.view` 命名、心理明细可见角色终表（总册 §3.9 ⑱ / §3.3 ⑱ 现场确认） |

---

## 14. 施工顺序与依赖

**前置模块（必须先在，均已实现）**：风险预警中枢（B 包，`t_affairs_risk_record` 处置闭环）、学生画像 360（psyFlag「需关注」段）、系统管理数据范围（PSY_STUDENT 授权 UI）、公共组件底座（AppSensitiveText/AppAuditTrail/AppRiskTag/AppWatermark/AppExportConfirm）、公共 Excel 底座、公共日期组件。

**建议施工波次与 commit 粒度**：
1. `feat(sa-mental): 心理关注名单页 + M1/M2/M3/M4 接口 + PSY_STUDENT 越权 403 用例` —— 先打通「看得见=能处理」与明细收敛/审计红线（复用 `t_cs_mental_record`，不建表）。
2. `feat(sa-mental): 心理预警摘要页（复用 risk source=MENTAL）` —— 纯前端聚合 + 复用已实现 risk 接口，不新增后端。
3. `feat(sa-mental): 危机升级链（复用 risk escalate/handle/close）+ 干预时间线` —— 复用已实现状态机，前端时间线 + 审计区。
4. `feat(sa-mental): 谈话转介与回访 + t_affairs_psy_referral 迁移 + M5/M6/M7` —— **唯一涉及新表**，先出 Alembic + pytest 再接前端（需人工确认建表后再动）。
5. `feat(sa-mental): 心理统计脱敏页 + M8` —— 聚合只读 + 导出剔除敏感 + 台账。
6. 每波完成：navPlan 对应叶子 `P→I(label,path)`（让位占位页）、写 `docs/施工记录/历史欠账.md`、`npm run build` + 后端 pytest（MySQL）绿。

**风险点**：
- **最高风险=敏感越权**：任何一页漏 `psyDetail.view` 校验或漏 `SENSITIVE_VIEW` 审计即为上线阻断（§35 E 级），必须后端校验，不能只前端隐藏。
- 枚举/时限/字数阈值未确认前，先按草案落库并标 partial + 记欠账，**不得标 implemented**（CLAUDE.md §0.0 第 10 条、§35.5）。
- 测评引擎 backlog，务必只留接口位，勿被需求牵引临时造量表页（自嗨风险）。
- MySQL 争用/测试库连接须确认（历史欠账中教务已有相关阻断记录，参见 `docs/施工记录/历史欠账.md`）。

**复用表清单**：`t_cs_mental_record` / `t_affairs_risk_record` / `t_affairs_risk_handle_record` / `t_cs_audit_trail` / `t_teacher_student_scope(PSY_STUDENT)`。**新增仅** `t_affairs_psy_referral`（草案，待确认）。
