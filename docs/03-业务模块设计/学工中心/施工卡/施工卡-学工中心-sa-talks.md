# 施工卡 · 学工中心 · 谈心家校（C 包 · sa-talks）

> 模块键：`sa-talks`　｜　施工顺序：C 包 · 第 9 步　｜　当前状态：**全部三级页 planned（待施工）**
> 依据口径：本卡为**开发前施工卡**，不是实现记录；所有页面按「规划占位页规则（CLAUDE §42）」目前进占位页，真实施工完成后 navPlan 中该叶子改 `I(label, 真实path)`。
> 证据规则：每条关键结论在第 13 节标注来源文件 + 章节/行号；读不到依据处一律标「**需人工确认**」，不臆造字段/接口/流程。
> 对标口径（CLAUDE §0.0）：优先复刻经市场验证的成熟学工产品的**业务成熟度与流程闭环**（角色分工、台账、批量、权限审计、脱敏、导入导出、移动端高频体验），不抄袭其界面/代码/数据库/商标。
> 本卡范围严格等于施工图 C 包第 9 步的 6 个三级页：**谈话计划、谈话记录、重点学生跟进、家校联系人、家校联系记录、谈心统计**（`frontend/src/config/navPlan.js` L152–154；`constructionMap.js` L101–105；页面树 §施工图 L518）。

---

## 1. 模块定位与真实学校业务价值

**一句话定位**：谈心家校是「辅导员与学生一对一沟通 + 家校协同」的记录、跟进与工作量沉淀中枢，是**风险预警 / 请假逾期 / 违纪 / 心理关注 / 宿舍异常等业务的落地出口**（谈完、联系完家长才算处置闭环），也是辅导员考评的工作量来源之一。

**真实学校里谁在用、解决什么**（依据：总册 §3.10 ①角色四问 L553、§4.7 家校 L709；权限总控 L264/L657）：

| 角色 | 真实动线 | 本模块解决的痛点 |
|---|---|---|
| 辅导员 / 班主任 | 每周谈心谈话、给重点学生定期跟进、联系家长 | 谈话「谈了没有、谈了什么、要不要跟进」无处沉淀；家长「联系了没、联系结果」无台账，年终考评无法举证 |
| 心理老师 | 心理类谈话记录（强敏感） | 心理谈话内容需与普通谈话隔离、分级可见、不外泄 |
| 学院学工负责人 / 学工处 | 看本院/全校谈话完成率、重点学生跟进覆盖、家校联系工作量 | 领导要「账」和「排行」，不是流程截图 |
| 学生（小程序） | 收到「谈话邀约」（时间地点），确认/改约 | 学生只看邀约事实，**看不到谈话记录内容**（隐私红线） |
| 家长（外部身份，暂不登录） | 接收通知、被联系 | 家长默认不是后台角色，只接收；渠道开关控制（CLAUDE §13） |

**为什么是刚需（不是自嗨功能）**：谈心谈话是教育部对辅导员的明确工作要求（谈心谈话制度、重点学生台账），家校联系是请假逾期/风险/违纪处置绕不开的一步；成熟学工产品普遍把「谈话记录 + 重点学生跟进 + 家校联系台账」作为辅导员日常与考评的标配（依据：审计文档第三步精华原则 2「所有业务必须有台账」、原则 11「围绕画像和今日待办聚合」）。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE §0.0 十点）

> **诚实声明**：仓库唯一的对标依据是 `13A-学工中心-商业化对标审计与补丁建议（第一轮）.md`，该文档对标对象为**正方 / 强智 / 青果**三家，但其对谈心谈话/家校的处理是**三家合并式精华提炼（15 条原则 + 缺口表）**，未逐家拆分「谈话模块」的字段级差异。本会话**无联网**，无法实时核验各家谈话/家校模块的界面级细节。故下表：① 三家「共同核心」「最佳做法」「本项目现状/缺口/必做」严格依据仓库审计文档（可追溯行号）；② 标注为「〔厂商精华·未逐条核验〕」的单元格来自成熟校园学工产品的通行做法认知，**未在仓库逐条印证，属需人工确认项**，不得当成确定结论写入对甲方承诺。

**① 对标对象 A：正方学工（Zfsoft 学工）**
- 核心流程〔厂商精华·未逐条核验〕：谈话计划 → 邀约学生 → 谈话记录（分类型）→ 需跟进则挂重点学生 → 与请假/预警/资助联动 → 完成率进考评。
- 角色〔未核验〕：辅导员、学院学工、学工处、学生端。
- 字段〔未核验〕：谈话类型、时间地点、内容纪要、学生状态、是否跟进、关联事项。
- 亮点〔未核验〕：与教务学籍/成绩预警打通，谈话可从学业预警直接发起。
- 缺点〔未核验〕：家校联系相对薄弱，多为电话记录文本，台账化弱。

**② 对标对象 B：强智学工（Kingosoft 学工）**
- 核心流程〔未核验〕：重点关注学生库 → 定期谈话任务下发 → 谈话记录 → 家校联系 → 台账导出上报。
- 角色〔未核验〕：辅导员、二级学院、学生处、宿管协同。
- 字段〔未核验〕：重点学生分类（学业/经济/心理/违纪/就业困难）、跟进频次、联系方式。
- 亮点〔未核验〕：「重点学生台账 + 定期跟进提醒」成熟，契合本卡「重点学生跟进」页。
- 缺点〔未核验〕：移动端速记与弱网体验偏弱。

**③ 对标对象 C：青果学工（Qingguo 学工）**
- 核心流程〔未核验〕：谈话记录 + 家访/家校联系单 + 辅导员工作日志/工作量统计一体。
- 角色〔未核验〕：辅导员、班主任、学院、学工处。
- 字段〔未核验〕：家校联系原因、联系结果、家长反馈、下次跟进时间。
- 亮点〔未核验〕：家校联系单结构化 + 工作量沉淀到辅导员考评做得较完整。
- 缺点〔未核验〕：心理类谈话与普通谈话的分级脱敏控制偏弱。

**④ 三家共同具备的核心功能**（依据审计文档精华原则 2/6/7/11 + 缺口表 L122/L125/L158/L160）：
1. 谈话计划 + 谈话记录（按类型分类）；2. 重点学生台账与定期跟进提醒；3. 谈话与风险/预警/请假/违纪/心理/宿舍等业务联动（一键发起、回写）；4. 家校联系记录（含完整号码脱敏与查看留痕）；5. 辅导员谈话/家校工作量统计，进考评与领导视图。

**⑤ 三家里最值得吸收的最佳做法**：
- 「**重点学生库 + 定期跟进任务 + 逾期提醒**」（强智式）——直接落为本卡「重点学生跟进」页与状态机 FOLLOW_UP + 超时提醒（依据：状态机 §7.2 L330–331）。
- 「**家校联系单结构化 + 去重提示 + 台账导出**」（青果式）——直接落为审计补丁 P-08（家校联系单结构化，依据 L386–411）。
- 「**心理类谈话强敏感分级**」——本项目已达标且更严（心理类 content_encrypted + PSY_STUDENT 逐生授权，依据 §7.1 L324、权限总控 L268/L536）。

**⑥ 本项目当前已有能力**（底座已设计，均有行号）：谈话计划/记录/跟进链/风险联动/工作量统计（总册 §3.10 L556–571）、谈话状态机 7 态（状态机 §7 L305–331）、谈话表单与类型/结果枚举（表单 §3.12 L333–353）、谈话 API 6 支（API 契约 L300–311）、家校联系记录 + 完整号码 reveal 审计（API L364–371、权限总控 L537–540）、家校数据表 t_affairs_family_contact_log 已锁名预留（总册 L141）。

**⑦ 本卡必须补齐的生产级闭环**：
1. 6 个三级页的真实前端（列表+详情/抽屉，非空壳）；2. 谈话/家校后端接口 + MySQL 建表迁移；3. 「重点学生跟进」聚合页（见 §3 映射，属新聚合口径）；4. 家校联系单结构化（原因/结果/下次跟进/去重提示，补丁 P-08）；5. 谈心统计页（完成率/工作量/家校台账，脱敏导出）；6. 敏感字段脱敏 + 审计 + 心理类分级全链路；7. 移动端谈话邀约（学生只读）+ 教师速记。

**⑧ 进 backlog（能力池，本卡不做真代码，仅接口位/人工流程）**：谈话模板库、语音转文字速记、家长短信通知渠道（未配渠道强制置灰）、家访 GPS 打卡、AI 谈话摘要（依据总册 §3.10 ⑰ P2P3 L574、审计补丁 P-08 渠道开关 L397、补丁 P-10 语音 P2）。

**⑨ 禁止做成假功能的内容**（CLAUDE §17/§39 红线）：
- 家长短信「通知成功」不得 mock：未配渠道时置灰，不能假成功（依据 P-08 L397、参数 #7）。
- 心理类谈话内容不得对无权限角色返回明文，也不得「前端隐藏、接口仍返回」——**整段不返回**（依据权限总控 L536、状态机 §7.1 L324）。
- 谈话记录、家校联系记录写操作不得 mock，必须真写 MySQL + 审计。
- 「谈心统计」数字必须与谈话/家校真实记录同源（首页-列表对账 0 差异，冻结表 §8）。

---

## 3. 三级页面清单与状态（对齐施工图）

来源：`navPlan.js` L152–154（`mod('sa-talks', '谈心家校', null, P(...))`，`P()`=planned）；`constructionMap.js` L101–105；页面树 §施工图 L518。**6 页当前全部 planned（待施工），本卡完成后按真实施工进度逐页转 implemented。**

| # | 三级页（施工图名） | 建议路由 | 映射到既有设计 | 状态 | 说明 |
|---|---|---|---|---|---|
| 1 | 谈话计划 | `/admin/student-affairs/talks/plans` | 页面树 10-1 `/talk/plans`（L123/L276） | planned | 建计划、约定时间地点、邀约学生、计划台账 |
| 2 | 谈话记录 | `/admin/student-affairs/talks/records`（列表）+ `/records/create`（新增）+ `/records/:id`（详情） | 页面树 10-2/10-3/10-4（L124–127） | planned | 列表+新增+详情三视图归入「谈话记录」一个三级页（连续处理=列表+详情双栏，复杂详情独立页，CLAUDE §9.3 冻结形态） |
| 3 | 重点学生跟进 | `/admin/student-affairs/talks/follow-ups` | **无 1:1 既有页**；最接近=状态机 FOLLOW_UP 跟进链（§7 L316/L318）+ 工作台 `overdueFollowStudents` 卡（补丁 P-01 L197） | planned | **口径需人工确认**：本页为「需跟进/待回访/长期未跟进」重点学生聚合台账，非新流程，聚合既有谈话 FOLLOW_UP + 风险跟进；跟进频次/重点分类枚举需现场确认 |
| 4 | 家校联系人 | `/admin/student-affairs/home-school/guardians` | 页面树 12-1 `/family/contacts`（L143/L302） | planned | 监护人**复用 `t_student_contact`，不新建联系人表**（总册 L141）；号码脱敏，看完整填原因+审计 |
| 5 | 家校联系记录 | `/admin/student-affairs/home-school/records` | 页面树 12-2 `/family/records`（L144/L303） | planned | 结构化联系单（原因/方式/结果/下次跟进/关联单），append-only；家访记录（12-3）并入本页或作 tab |
| 6 | 谈心统计 | `/admin/student-affairs/talks/stats` | 页面树 10-5 `/talk/stats`（L128/L280）+ 家校台账 | planned | 谈话完成率/工作量/类型分布 + 家校联系台账；脱敏导出；进辅导员考评与首页卡 |

**路由兼容说明**：既有页面树用 `/talk/*`、`/family/*` 短路径；建议新页统一挂 `/admin/student-affairs/talks/*`、`/admin/student-affairs/home-school/*`（与 API 前缀 `/api/v1/student-affairs/talks|home-school` 一致，API 契约 L304/L369）。旧短路径若已注册须 redirect/alias 兼容，不 404（CLAUDE §9.1）。**是否已存在旧 `/talk/*` 路由：需人工确认**（本卡不查前端路由表，避免越界改代码）。

---

## 4. 业务流程与状态机

### 4.1 谈话状态机（13A-10）

**已实现/已设计，本卡不重新发明**。状态枚举（依据状态机 §7 L307，**标注为「推导枚举，需现场确认」**）：
`PLANNED → SCHEDULED → COMPLETED → FOLLOW_UP → CLOSED`，旁支 `CANCELLED`、终态 `ARCHIVED`。

| 当前状态 | 操作 | 执行角色 | 目标状态 | 审批 | 通知 | 审计 | 进 360 |
|---|---|---|---|---|---|---|---|
| （新建） | 建计划（选学生+主题） | 辅/班/心/院 | PLANNED | 否 | 无 | 是 | 否 |
| PLANNED | 约定时间地点 | 发起人 | SCHEDULED | 否 | STATUS_CHANGED→学生（邀约） | 是 | 否 |
| PLANNED/SCHEDULED | 取消 | 发起人 | CANCELLED | 否 | STATUS_CHANGED→学生 | 是 | 否 |
| SCHEDULED | 填谈话记录 | 发起人 | COMPLETED | 否 | 无 | 是 | 是（学生仅见"已谈话"摘要） |
| COMPLETED | 判定需跟进 | 发起人 | FOLLOW_UP | 否 | 无 | 是 | 否 |
| COMPLETED | 转风险 / 转家校 | 发起人 | COMPLETED（联动留痕） | 否 | RISK_ALERT→风险责任人 | 是 | 是 |
| FOLLOW_UP | 跟进/再约谈（链式新单） | 发起人 | FOLLOW_UP（留痕） | 否 | 无 | 是 | 否 |
| COMPLETED/FOLLOW_UP | 办结 | 发起人 | CLOSED | 否 | 无 | 是 | 是 |
| CLOSED/CANCELLED | 批次收编归档 | 处/院 | ARCHIVED | 否 | ARCHIVE_NOTICE | 是 | 否 |

来源：状态机 §7 L310–320。**谈话不走 Workflow 审批**（处置类，时效优先，与风险同理 §6）。

**非法转移防护**（§7.1 L322–326）：① 未填记录直接办结（SCHEDULED→CLOSED）→ **409**；② 对范围外学生建计划 → **403 NO_DATA_SCOPE**；③ 心理类记录取全文，非授权 → 403 或 SENSITIVE_VIEW 审计后放行。
**超时自动转移**（§7.2 L328–331）：SCHEDULED 过约定 24h 未填记录 → DEADLINE_REMINDER→发起人；7 天未填 → 自动 CANCELLED（计入完成率）；FOLLOW_UP ≥14 天无跟进 → DEADLINE_REMINDER→发起人。

> **⚠ 枚举冲突（需人工确认，写入 §13）**：状态机 §7 用 `PLANNED/SCHEDULED/COMPLETED/FOLLOW_UP/CLOSED/CANCELLED/ARCHIVED`；总册 §3.10 L556–557 用 `PLANNED/DONE/MISSED`。API 契约 L307 用 `→COMPLETED`。**三处不一致，冻结前必须由甲方拍板统一**，建议以状态机 §7 为准（最细、已标推导待确认）。开发时以确认后的唯一枚举落库，禁止两套并存。

### 4.2 家校联系流程

家校联系**无审批流程态，为 append-only 联系单**（依据审计补丁 P-08 L394、交互矩阵 L477「联系单 append(无流程态)」）。主流程（总册 §4.7 L710、补丁 P-08）：
从 360/风险/请假逾期/违纪/心理/宿舍异常一键发起 → 查看脱敏号码（完整号码填原因≥5 字+审计）→ 电话/家访 → 填联系单（对象/原因/方式/结果/家长反馈/下次跟进/关联单 ref）→ 关联风险处置流水 → 重点学生定期联系提醒（DEADLINE_REMINDER）。

**跨模块联动（已设计，本卡复用不重造）**：
- 风险处置「转家校」：handle_type=FAMILY_CONTACT（表单 §3.11 L319/L484；API 68 linkAction=TO_HOME_SCHOOL L277）。
- 谈话「转家校」：talk result=TRANSFER_FAMILY（表单 §3.12 L345/L497；API 77 action=TO_HOME_SCHOOL L308）。
- 请假逾期「转家校」：leave overdue handleType=TO_HOME_SCHOOL（API 25 L165）。

---

## 5. 表单字段与校验规则

### 5.1 谈话计划（页 1）— `t_affairs_talk_plan`
依据总册 §3.10 ⑨ L566、API 74 L305。

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| 谈话对象 student_ids[] | 多选（学生 Picker，可多选） | 是 | 每个 student 必在发起人 scope 内，否则 403 NO_DATA_SCOPE | 普通 |
| 谈话主题类型 topic_type/talk_type | select | 是 | 枚举见下 5.3；心理类触发强敏感提示 | 心理类=强敏感 |
| 谈话主题 topic | input | 是 | L3 规则 2–50 字（表单 L27/L343） | 普通 |
| 约定时间 plan_time/scheduledAt | 日期时间（公共日期组件） | 否（建计划可空，约定时填） | 不早于当前（约定态）；空日期显"未设置"（CLAUDE §40） | 普通 |
| 约定地点 place | input | 否 | 2–50 字 | 普通 |
| 关联风险单 related_risk_id | select（从风险转入自动带） | 否 | 须本人负责的风险单，否则 422001 | 普通 |

### 5.2 谈话记录（页 2）— `t_affairs_talk_record`
依据表单 §3.12 L333–353（**这是最完整的既有字段定义，直接复刻**）。**心理类（PSYCHOLOGICAL）为强敏感记录，content 加密存储 `talk_content_encrypted`。**

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| 关联计划 plan_id | 隐藏/带入 | 否 | 空=临时补录 | 普通 |
| 谈话类型 talk_type | select | 是 | 枚举见 5.3；选 PSYCHOLOGICAL 弹强敏感提示 | 心理类强敏感 |
| 谈话时间 talk_time | 日期时间 | 是 | **不晚于当前**（事后记录，T5）；晚于当前→422001 | 普通 |
| 谈话地点 location | input | 是 | 2–50 字 | 普通 |
| 谈话主题 topic | input | 是 | 2–50 字 | 普通 |
| 内容纪要 content | 长文本 | 是 | **20–2000 字**（表单 L28）；心理类落 `content_encrypted` | 心理类=加密 |
| 学生状态评估 student_state_eval | select/文本 | 否 | — | 普通 |
| 谈话结果 result | select | 是 | NORMAL/NEED_FOLLOW/TRANSFER_RISK/TRANSFER_FAMILY；NEED_FOLLOW 时跟进计划必填 | 普通 |
| 跟进计划 follow_plan | 文本/日期 | 条件必填 | result=NEED_FOLLOW 时必填，否则 422001 follow_plan | 普通 |
| 关联风险单号 risk_id | select | 否 | 本人负责风险单；从 09-3 转入自动带 | 普通 |

**防重复**：`createSubmitLock` + 后端「同记录人+同学生+同谈话时间（精确到分钟）」唯一 → **409001**（表单 L351）。
**提交后**：直接生效（无审批）；写学生 360 时间线；result=TRANSFER_RISK 自动生成风险记录（NEW）；TRANSFER_FAMILY 生成家校联系待办；带 risk_id 回写风险跟进（表单 L352）。

### 5.3 谈话类型 / 结果枚举（表单 §3.12 L489–497，冻结）
- talk_type：`DAILY 日常 / ACADEMIC 学业 / PSYCHOLOGICAL 心理（强敏感）/ DISCIPLINE 违纪 / EMPLOYMENT 就业 / INTERNSHIP 实习 / AID_SUPPORT 困难帮扶 / DORM_ABNORMAL 宿舍异常`
- result：`NORMAL 情况正常 / NEED_FOLLOW 需跟进 / TRANSFER_RISK 转风险 / TRANSFER_FAMILY 转家校`

### 5.4 重点学生跟进（页 3）
**字段口径需人工确认**（无既有页 1:1 定义）。建议聚合字段（只读为主 + 跟进动作）：学生、重点分类（学业/经济/心理/违纪/就业困难——可复用风险 source_type 或困难库分类）、最近一次谈话时间、下次应跟进时间、逾期天数、责任辅导员、跟进动作（建谈话计划/记录跟进）。**重点分类枚举、跟进频次阈值必须现场确认**，参数化落 `studentAffairs.counselor.followGapDays`（默认 14，补丁 P-01 L197/L206）。

### 5.5 家校联系人（页 4）— 复用 `t_student_contact`（不新建联系人表）
依据总册 L141、API 98 L369。字段：关系（父/母/祖父母/兄弟姐妹/其他）、姓名、**联系电话（脱敏展示 `138****1234`，看完整走 reveal+审计）**、是否监护人。号码为强敏感字段（表单 §L442、权限总控 L536）。

### 5.6 家校联系记录（页 5）— `t_affairs_family_contact_log`
依据 API 100 L371、审计补丁 P-08 L395。

| 字段 | 类型 | 必填 | 校验 | 敏感级 |
|---|---|---|---|---|
| 学生 student_id | Picker | 是 | 在 scope 内，否则 403 | 普通 |
| 联系人 guardian_id | select（来自 t_student_contact） | 是 | — | 关联脱敏号码 |
| 联系原因 contact_reason | select | 是 | LEAVE_OVERDUE/RISK/DISCIPLINE/PSY/DORM/OTHER（P-08 L395，**枚举需人工确认**） | 普通 |
| 联系方式 contact_type | select | 是 | PHONE 电话 / VISIT 家访 / OTHER 其它 | 普通 |
| 联系结果摘要 content/result_summary | 长文本 | 是 | ≥10 字（API 100 L371 content≥10） | 普通 |
| 家长反馈 parent_feedback | 文本 | 否 | — | 普通 |
| 下次跟进时间 next_follow_at | 日期 | 否 | 公共日期组件；空显"未设置" | 普通 |
| 关联业务单 linked_ref / linked_risk_id | 隐藏/带入 | 否 | 从风险/请假/谈话转入自动带 | 普通 |

**去重提示**（P-08 L398）：同一学生 N 天内已联系则新建时提示「N 天前已联系过」（N=`studentAffairs.family.repeatGapDays`），**不强制阻断**。
**结果枚举 result**（若与 API 一致需确认）：API 100 有 `result(enum,必)` 但未列枚举值 → **枚举值需人工确认**。

---

## 6. 权限矩阵与数据范围

**权限点**（谈话）：`studentAffairs.talk.view / .create / .handle / .stats.view / .psyContent.view`
> 命名不一致提示：总册 §3.10 L564 列 `.plan/.record/.view/.psyContent.view/.stats.view`；状态机 L519–521 列 `.view/.create/.handle/.export`；API 契约 L305–308 用 `.create/.handle/.view` + `.stats.view`。**以 CLAUDE §10 命名规范 `module.domain.action` 收敛为唯一集，冻结前需人工确认**，建议：`studentAffairs.talk.view/.create/.handle/.stats.view/.psyContent.view`。

**权限点**（家校）：`studentAffairs.homeSchool.view / .record.create / .contact.reveal`（状态机 L538–540、API L369–371）。

**数据范围（核心，来自真实业务关系，不按角色名给权）**（权限总控 §数据范围 L347/L357/L411/L453）：
- 辅导员/班主任：`scope_type=CLASS/ADVISOR`，经 `getStudentAffairsScope` → `resolve_teacher_scope` → `t_teacher_student_scope` 解析，**前端不传范围**，后端从激活角色+token 解析；越权 403002 + 审计。
- 心理老师：`scope_type=PSY_STUDENT`（**逐生授权，不支持班级/学院通配**，权限总控 L610/L364）；仅作用于心理类谈话全文。
- 学院学工：本学院（摘要级）；学工处：全校（摘要级）。
- 学生本人：仅见本人「谈话邀约」事实，**不可见谈话记录内容**（总册 L553、状态机权限矩阵 L570）。

**角色×可见口径矩阵**（谈话，状态机 L519–521/L570）：

| 角色 | 谈话记录可见 | 谈话记录操作 | 心理类全文 | 统计/工作量 |
|---|---|---|---|---|
| 学工处 | ✓ 全校（摘要） | ✗ | 限（授权时） | ✓ |
| 学院学工 | 限 本院（摘要） | 限 | 限 | 限 本院 |
| 辅导员/班主任 | 限 负责班级（本人记录全文） | 限 | 授权学生 | 限 本人工作量 |
| 心理老师 | 限（心理类全文） | 限 | ✓ 授权学生 | ✗ |
| 学生本人 | 仅"已谈话"摘要 | ✗ | ✗ | ✗ |

家校联系角色矩阵（状态机 L538–540）：学工处 ✓ / 学院限 / 辅导员限（本班）/ 心理老师限（心理关联）；**完整号码查看（reveal）辅导员及以上限，原因必填+审计**。

**红线**：谈话/家校**后端必须校验**模块授权+角色+数据范围+业务关系+敏感字段（CLAUDE §3.4/§18），不得只靠前端隐藏。角色权限**不得扩大**（constructionMap L105 明令「不扩大任何角色权限」）。

---

## 7. 敏感字段脱敏与审计（CLAUDE §6 红线）

| 敏感对象 | 存储 | 脱敏出口 | 查看明文条件 | 审计 |
|---|---|---|---|---|
| 心理类谈话内容 | `talk_content_encrypted`（加密列） | 非授权角色仅见「存在心理谈话/心理类谈话 1 次」标记，**整段不返回**（防试探） | 记录人本人 / 心理老师 / 授权辅导员（PSY_STUDENT） | 取全文写 `SENSITIVE_VIEW`（表单 L446、权限总控 L536、状态机 §7.1 L324） |
| 家长/学生完整手机号 | `phone_encrypted` | `138****1234`（`_mask_phone`） | reveal 接口，reason≥5 字 | `SENSITIVE_VIEW`（API 98 L369、表单 L442） |
| 谈话/家校导出 | — | 台账导出**默认剔除心理明细**（锁死，学校不可改，参数 #24） | — | 导出走 `t_export_task` + 下载审计，水印 |

**要求**（§6）：最小授权、二次确认、填查看原因、水印、审计留痕、可追溯到人。心理明细在**任何导出被剔除**（施工包 B 验收口径 L496）。系统**不输出诊断结论**（权限总控 L536）。

---

## 8. API 契约草案

> 均取自 `13A-学工中心API契约草案.md`（已存在的草案，本卡不新造端点，只标注复用/需补）。统一响应包络与错误码：`401 未登录 / 403002 范围外 / 404 不存在 / 409001 状态冲突/重复 / 422001 校验失败 / 500 不允许业务 500`（融合设计 §0）。

**谈话（talks，前缀 `/api/v1/student-affairs/talks`）**（API L300–311）：

| # | 方法 端点 | 用途 | 关键入参 | 出参 | 权限 | 审计 |
|---|---|---|---|---|---|---|
| 73 | GET /talks | 谈话列表（管理侧默认摘要） | talkType/status/classId/dateRange, page | list[{talkId,studentNo,realName(脱敏),talkType,status,scheduledAt,talkerName}] | talk.view | 无 |
| 74 | POST /talks | 建计划 | studentIds[]必, talkType必, topic必, scheduledAt, requestId | {talkIds[]} | talk.create | AFFAIRS_TALK_PLAN |
| 75 | GET /talks/{id} | 详情（心理类按权限） | — | detail+followUps[]+linkedRisk | talk.view | 心理全文 SENSITIVE_VIEW |
| 76 | POST /talks/{id}/record | 填记录→COMPLETED | content≥20, result枚举必, needFollowUp必, version | {talkId,status} | talk.handle | AFFAIRS_TALK_RECORD |
| 77 | POST /talks/{id}/follow-up | 跟进/办结/转风险/转家校 | action(FOLLOW/CLOSE/TO_RISK/TO_HOME_SCHOOL)必, content必 | {talkId,status,linkedRiskId?} | talk.handle | AFFAIRS_TALK_FOLLOWUP |
| 78 | GET /talks/stats | 工作量统计 | groupBy(COUNSELOR/CLASS/TYPE)必, semester | metrics+breakdown[] | stats.view | 无 |

错误码（API L311）：409001 未填记录直接办结/取消已完成；403002 范围外建计划；心理类记录人以外取全文 403001（授权辅导员除外）。

**家校（home-school，前缀 `/api/v1/student-affairs/home-school`）**（API L364–371）：

| # | 方法 端点 | 用途 | 关键入参 | 出参 | 权限 | 审计 |
|---|---|---|---|---|---|---|
| 98 | POST /home-school/guardians/{id}/reveal | 查看完整号码 | reason≥5必, requestId | {guardianId,phoneFull} | homeSchool.contact.reveal | SENSITIVE_VIEW |
| 99 | GET /home-school/records | 联系/家访记录列表 | studentId/contactType/dateRange, page | list[{recordId,studentNo,contactType,contactedAt,resultSummary,linkedRiskId}] | homeSchool.view | 无 |
| 100 | POST /home-school/records | 登记联系结果 | studentId必, guardianId必, contactType必, content≥10必, result必, linkedRiskId, requestId | {recordId} | homeSchool.record.create | AFFAIRS_HOME_SCHOOL_CONTACT |

**需补的端点（需人工确认，审计文档已提示）**：
- `GET /home-school/guardians`（联系人列表，脱敏读）— 交互矩阵 L477 提示「需补 family/contact-log」。
- 家校台账导出 `GET /home-school/records/export`（脱敏）— 补丁 P-08 L404/L409。
- 「重点学生跟进」聚合端点（如 `GET /talks/follow-ups` 或复用 `/counselor/workbench` 的 `overdueFollowStudents`）— **需人工确认口径**（补丁 P-01 L197）。

**统计（复用既有）**：`GET /stats/overview`（含谈话完成率，API 108 L397）、`GET /stats/{metricGroup}` metricGroup=talk（API 109 L398–399）。

**移动端**：`GET /mobile/affairs/my-talk-summary`（学生只读谈话摘要，API 124 L461）、`POST /mobile/teacher/affairs/talks/quick-record`（教师速记，非心理简版，API 135 L500）。

---

## 9. 数据表与迁移（MySQL utf8mb4 + tenant_id + 软删除/审计字段）

**复用优先原则（CLAUDE §37/审计第八步 L573）：加列不建表、投影不平迁、不建平行表。**

| 表 | 复用/新增 | 说明 | 依据 |
|---|---|---|---|
| `t_affairs_talk_plan` | 新增（已锁名，随本包建 Alembic 迁移） | 谈话计划：`student_ids/topic_type/plan_time/place/related_risk_id/biz_status`；索引 (created_by,biz_status) | 总册 L133/L192/L566 |
| `t_affairs_talk_record` | 新增（已锁名） | 谈话记录：`plan_id/student_id/talk_time/content[心理类 content_encrypted]/student_state_eval/result/need_follow/follow_plan/prev_record_id/related_risk_id`；索引 (student_id)；FK related_risk_id→t_affairs_risk_record（可空） | 总册 L133/L192/L566、表单 §3.12 |
| `t_affairs_family_contact_log` | 新增（已锁名，总册标 P2 建，本包建） | 家校联系单：`student_id/guardian_id/contact_reason/contact_type/content/parent_feedback/next_follow_at/linked_ref/linked_risk_id`；append-only | 总册 L141、P-08 L395/L405 |
| `t_student_contact` | **复用**（不新建联系人表） | 监护人/联系人数据；完整号码查看走审计 | 总册 L141、API 98 |
| `t_cs_mental_record` | **复用**（不建新心理表） | 心理骨架强权限；谈话/风险以外键引用，心理明细读走其既有权限 + PSY_STUDENT | API L550 |
| `t_affairs_risk_record` | **复用** | 转风险/回写跟进 | 状态机 §6、表单 L348 |
| `t_student_stage_event` | **复用**（不新建 timeline 表） | 360 沉淀 event_type=`AFFAIRS_TALK_DONE`（类型+日期，内容不进） | 总册 L37/L560、L878 |
| `t_security_audit_log` | **复用** | `record()` 写敏感查看/操作审计 | 权限总控 L5 |
| `t_export_task` | **复用** | 台账导出留痕+下载审计 | 施工包 B L490/L496 |
| `t_unified_todo` | **复用** | 待谈话/家校待联系/跟进逾期待办 | 总册 L235 |

**迁移规范**（CLAUDE §36）：Alembic migration，utf8mb4 / utf8mb4_unicode_ci，每业务表含 `tenant_id`、软删除、`created_at/updated_at/created_by`、审计字段；JSON/Enum/DateTime 兼容 MySQL；迁移可重复执行。**当前是否已建这三张表：需人工确认**（本卡不查后端 models，避免越界）；若已存在则只补缺列（加列不重建）。

---

## 10. Excel 导入导出（接公共底座）

**统一接入公共 Excel 底座**（CLAUDE §38）：后端 `app/services/excel/`、前端 `components/common/excel/`（AppExportButton + AppExportConfirm），不另造解析/校验/错误行/导入记录/导出审计。

- **导出（主场景）**：谈话台账、家校联系台账——「按当前筛选导出 Excel」，权限控制，**心理明细脱敏剔除**，导出审计，文件名含模块名+租户+时间（§38.8）。走 `t_export_task`。
- **导入**：谈话/家校**通常不批量导入业务记录**（成熟系统以录入+导出台账为主）。**是否需要「重点学生名单 Excel 导入」需人工确认**；若需要，则完整走：下载 Excel 模板 → 上传 xlsx → 字段/必填/格式/业务规则/文件内重复/数据库重复校验 → 错误行预览 → 下载错误行 Excel → 确认导入 → 导入记录 → 审计（§38.7）。写操作**不得 mock 成功**。
- 文案统一：「导出 Excel 台账」「下载错误行 Excel」，不用 CSV 作正式方案（§38）。

---

## 11. 移动端入口

谈话/家校属高频（辅导员现场谈完即录、随手联系家长），移动端优先（精华原则 10）。

| 端 | 页/入口 | 口径 | 依据 |
|---|---|---|---|
| 学生端（小程序） | 「消息-谈话邀约」：确认/改约请求；`GET /mobile/affairs/my-talk-summary`「我的谈话摘要」**仅"已谈话"事实，不含内容** | **只读**；看不到记录内容（隐私红线） | 总册 §3.10 L572、API 124 L461 |
| 教师端（小程序） | T-04 谈话速记：`POST /mobile/teacher/affairs/talks/quick-record`，现场谈完即录 | 可写；**仅非心理类简版，心理类回 PC**；语音转文字入能力池 | 表单 §L118/§3.12 L335、API 135 L500 |
| 教师端 | 家校联系速记页（**新增，补丁 P-08 L403/L407**） | 可写；一键联系+记录结果；号码脱敏，看完整填原因+审计 | **需人工确认（新增页，尚无既有移动页）** |

移动端红线（补丁 P-10 L448）：弱网草稿不丢、防重复（createSubmitLock+服务端幂等 409）、**敏感数据（完整号码/心理明细）不写本地存储**、错误码逐码提示。教师写操作走既有 `/mobile/teacher` 包装层（范围校验+审计+409），不绕过 scope。

---

## 12. 验收标准（页面级用例）

**通用（每页）**：① 页面可进入、无控制台错误、无空页面/假按钮（CLAUDE §17/§20）；② 旧路由 `/talk/*`、`/family/*` 若存在则 redirect/alias 不 404；③ 三态齐全 loading / empty / error / no-permission / network-error / validation-error；④ 复用公共组件（AppPermissionButton/AppSensitiveText/AppExportButton/AppConfirmDialog/AppStudentPicker/公共日期组件，CLAUDE §40/§41），未复用则标 partial 并记欠账。

**谈话计划**：建计划选范围外学生→403 NO_DATA_SCOPE；约定后学生端收到邀约通知；取消→CANCELLED 通知学生。
**谈话记录**：内容<20 字→422001 content；talk_time 填未来→422001 talk_time；result=NEED_FOLLOW 未填跟进→422001 follow_plan；同记录人+同学生+同分钟重复→409001；未填记录直接办结→409；心理类记录对无权限角色**整段不返回**、仅见「心理类谈话 1 次」；提交后写 360（AFFAIRS_TALK_DONE，内容不进时间线）。
**重点学生跟进**：聚合口径与谈话 FOLLOW_UP/风险跟进 0 差异；逾期跟进生成待办；**分类/频次口径经甲方确认后方可标 implemented**（否则 partial）。
**家校联系人**：号码默认脱敏 `138****1234`；reveal 无原因→被拒；填原因≥5 字→返回完整号码并写 SENSITIVE_VIEW 审计。
**家校联系记录**：content<10→校验失败；append 留痕不可改历史；短期重复联系有「N 天前已联系过」提示；未配短信渠道时通知置灰（不假成功）；转入时自动带学生+原因+关联单 ref。
**谈心统计**：完成率/工作量与真实记录同源、首页-列表-明细对账 0 差异；导出带水印、**剔除心理明细**、走 t_export_task+下载审计；越权层不可见。

**自检命令**：`cd frontend && npm run build && npm run lint`；后端 `pytest`（须连 MySQL 测试库，CLAUDE §36）。完成后更新 `docs/06-开发施工与质量验收/施工记录/`（新增本模块施工记录）+ `历史欠账.md`；精确暂存本模块文件提交 1 个 commit（**禁止 git add -A**），不 push、不 tag（constructionMap L105）。

---

## 13. 依据文档索引（来源 + 章节/行号）

| 结论 | 来源文件 | 章节/行号 |
|---|---|---|
| 6 个三级页与 planned 状态、模块键 sa-talks | `frontend/src/config/navPlan.js` | L151–154（`mod('sa-talks',…,P(…))`） |
| 施工图 C 包第 9 步、页名、开发指令 | `frontend/src/config/constructionMap.js` | L101–105 |
| 谈心家校 = 谈话记录+家校联系单，10/12，C 包 | 页面树与路由设计 §施工图表 | L518 |
| 谈话页面树 10-1~10-5、家校 12-1~12-3 | 页面树与路由设计 | L122–127、L142–145、L276–280、L302–304 |
| 谈话角色四问/流程/字段/⑰必做/现场确认 | 全业务流程设计总册 §3.10 | L551–575 |
| 家校 §4.7 流程/角色/联系单 | 全业务流程设计总册 §4.7 | L707–713 |
| 谈话数据表锁名、家校表 P2 建、复用 t_student_contact | 全业务流程设计总册 | L133、L141、L192 |
| 谈话状态机 7 态 + 非法转移 + 超时 | 状态机与权限矩阵 §7 | L305–331 |
| 谈话/家校权限点与角色可见矩阵、PSY_STUDENT | 状态机与权限矩阵 | L519–521、L537–540、L570、L610 |
| 谈话记录字段/枚举/校验/防重复 | 表单字段与校验规则 §3.12 | L333–353、L489–497 |
| 敏感字段脱敏（号码/心理内容） | 表单字段与校验规则 | L442、L446 |
| 谈话 API 73–78、家校 98–100、统计 108–109、移动 124/135 | API 契约草案 §10/§13 | L300–311、L364–371、L397–399、L461、L500 |
| 三家对标/15 精华/缺口/补丁 P-01/P-08/P-10 | 商业化对标审计与补丁建议（第一轮） | 全文，重点 L73–103、L122、L125、L158、L160、L184–210、L386–411、L440–464 |
| 数据范围机制、辅导员/心理老师 scope、辅导员权责红线 | 系统管理中心-权限角色模块授权与权责边界设计 | L264、L268、L347、L357、L364、L411、L453、L536、L610、L657 |
| 交互形态基准（列表+详情双栏/复杂详情独立页） + 需补 API 标注 | 页面级交互与按钮动作矩阵 | L476（谈话）、L477（家校） |

**需人工确认清单（读不到确定依据，禁止当结论）**：
1. **谈话状态枚举三处冲突**（状态机 §7 `PLANNED/SCHEDULED/COMPLETED/FOLLOW_UP/CLOSED/CANCELLED/ARCHIVED` vs 总册 `PLANNED/DONE/MISSED` vs API `→COMPLETED`）——冻结前甲方拍板统一为唯一枚举。
2. **权限点命名三处不一致**（`.plan/.record` vs `.create/.handle` vs `.view/.handle/.export`）——按 §10 收敛为唯一集需确认。
3. **「重点学生跟进」页**无 1:1 既有设计——重点分类枚举、跟进频次阈值、聚合口径（复用 workbench overdueFollow 还是独立端点）需确认。
4. **家校联系原因/结果枚举**（P-08 建议 `LEAVE_OVERDUE/RISK/DISCIPLINE/PSY/DORM/OTHER`；API 100 `result` 未列枚举值）需确认。
5. **旧 `/talk/*`、`/family/*` 前端路由是否已注册**、需否 redirect——本卡未查前端路由表。
6. **三张表（talk_plan/talk_record/family_contact_log）是否已建 MySQL/Alembic**——本卡未查后端 models。
7. **是否需要「重点学生名单 Excel 导入」**、家长短信渠道预算与签名——现场确认。
8. **教师端家校移动速记页**为补丁新增，尚无既有移动页设计。
9. 三家厂商（正方/强智/青果）谈话/家校模块的**逐家字段级细节**——仓库审计文档为合并式精华，本会话无联网，标〔未逐条核验〕。
10. 谈话记录是否要求学生签认、心理类是否强制心理老师复核、工作量是否纳入考评口径（总册 §3.10 ⑱ L575 现场确认项）。

---

## 14. 施工顺序与依赖

**前置依赖（须已就绪）**：
- B 包已建的画像（学生 360）、辅导员工作台、数据范围引擎 `getStudentAffairsScope`、待办 `t_unified_todo`、公共组件底座、公共 Excel 底座、审计 `t_security_audit_log`。
- 风险预警（C 包已在）——谈话「转风险」、家校「关联风险」依赖 `t_affairs_risk_record` 与风险处置流水。
- 心理骨架 `t_cs_mental_record` + PSY_STUDENT 授权机制（心理类谈话全文分级依赖它）。

**建议施工与提交粒度**（每步一个 commit，精确暂存，禁止 `git add -A`）：
1. `feat(student-affairs): add talk plan/record tables + alembic migration`（建/校验 t_affairs_talk_plan/record，utf8mb4+tenant_id+审计字段）。
2. `feat(student-affairs): add talks API (plan/record/follow-up/stats) + 状态机 + 权限/scope + 审计`（后端接口 73–78，心理类分级脱敏，pytest 连 MySQL）。
3. `feat(student-affairs): add talks pages (计划/记录/统计)`（前端 3 页：谈话计划、谈话记录列表+详情+新增、谈心统计一屏；复用公共组件；planned 转 implemented）。
4. `feat(student-affairs): add home-school contact log table + reveal/records API`（t_affairs_family_contact_log，复用 t_student_contact，reveal 审计）。
5. `feat(student-affairs): add home-school pages (联系人/联系记录) + 台账导出`（家校联系人、家校联系记录 2 页；脱敏导出）。
6. `feat(student-affairs): add 重点学生跟进 aggregation page`（**待第 3 项人工确认口径后**；聚合 FOLLOW_UP+风险跟进+逾期待办）。
7. 移动端：谈话邀约（学生只读）+ 教师速记 + 教师家校速记（承接补丁 P-08，可并入或后置）。

**风险点**：
- ⚠ **枚举/权限点冲突未拍板即开工** → 返工。开工前先关闭 §13 需人工确认第 1、2、3、4 条。
- ⚠ **心理类谈话越权返回** → 合规红线，务必「整段不返回」+ 审计，pytest 覆盖无权限取全文用例。
- ⚠ **完整号码/心理明细本地缓存或导出泄露** → 移动端不落盘、导出剔除心理明细，验收抽查。
- ⚠ **重点学生跟进页做成新流程/新表** → 应为聚合台账，复用既有谈话/风险数据，不另造状态机。
- ⚠ **家长短信 mock 成功** → 未配渠道置灰，不假成功。

**完成即验收信号**：navPlan 中 6 个 `P(...)` 叶子逐个改为 `I(label, 真实path)`，占位页自动让位；`npm run build && npm run lint` 绿、后端 `pytest` 绿；施工记录 + 历史欠账更新；无 push/tag。

---

*本卡为开发前施工卡，未改动任何代码/navPlan/配置/迁移，仅新增本文件。所有「需人工确认」项须在冻结前由甲方拍板，禁止将未核验内容当作确定结论向甲方承诺。*
