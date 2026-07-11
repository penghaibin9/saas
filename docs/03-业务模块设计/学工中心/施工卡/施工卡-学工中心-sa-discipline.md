# 施工卡 · 学工中心 · 违纪处分（sa-discipline）

> 任务包：**C 包 · 审批业务闭环补强**｜模块 key：`studentAffairs.discipline`（navPlan `sa-discipline`）
> 文档性质：生产级施工卡（供照此开发）。本卡**只描述设计与依据，不含可运行代码**。
> 编制口径：严格遵循 `CLAUDE.md` §0.0（市场验证优先与成熟商业系统复刻规则）、§34/§35/§37/§38/§39/§40/§41。
> 关键约束：**优先复用现有 `t_cs_discipline` / `t_affairs_discipline_*` 表与 `affairs_discipline_service`，禁止平行建表；planned 页不臆造未确认的具体字段/接口**。
> 编制日期：2026-07-12｜基线：13A 四件套 + 商业化对标审计（第一轮）

---

## 0. 本卡依据核对（先读后写）

| 依据文档 | 是否读取 | 用途 |
|---|---|---|
| `CLAUDE.md` §0.0 | ✅ | 三家对标表十点结构 |
| `docs/03-业务模块设计/学工中心/13A-学工中心全业务流程设计总册.md` §3.8（L453–496）、§2.4（L172–176） | ✅ | 主流程/解除/联动/归属硬约束 |
| `.../13A-学工中心状态机与权限矩阵.md` §4（L195–234）、§5（L238–261）、权限矩阵（L505–511）、数据范围（L567/581） | ✅ | 状态机、非法转移、超时、权限点、数据范围 |
| `.../13A-学工中心表单字段与校验规则.md` §3.9（L275–293）、§3.10（L295–310）、枚举表（L471–482） | ✅ | 逐字段校验、枚举值 |
| `.../13A-学工中心页面级交互与按钮动作矩阵.md` §7（L536–624） | ✅ | 页 08-2/08-4/08-6 按钮动作矩阵、Opus 验收标准 |
| `.../13A-学工中心API契约草案.md` §8（L239–265）、移动端（L462–463）、投影表（L549） | ✅ | 端点 #54–#63、错误码、联动 |
| `.../13A-学工中心移动端入口设计.md` S-06（L142–156）、T-06（L340–354） | ✅ | 学生端/教师端入口与只读边界 |
| `.../13A-学工中心-商业化对标审计与补丁建议（第一轮）.md`（L6/L73/L120/L415–435） | ✅ | 三家对标（正方/强智/青果）+15 条精华 + 缺口表 + 补丁 P-09 |
| `docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md`（L495/L512/L550/L655/L657） | ✅ | 敏感字段、处分审批链、角色权责 |
| 现有代码：`backend/app/services/affairs_discipline_service.py`、`backend/app/api/v1/student_affairs.py`（L504–566）、`backend/app/models/affairs_discipline.py`、`backend/app/models/campus_service.py`（L100–115） | ✅ | 现状核实（后端闭环已建、投影已通） |
| `frontend/src/config/navPlan.js`（L146–149）、`frontend/src/views/admin/studentAffairs/DisciplineWorkbenchView.vue`、`frontend/src/views/admin/campusService/DisciplineView.vue` | ✅ | 前端现状（1 已实现 + 6 planned + 未挂载捞回页） |

> **联网说明**：本卡编制环境未确认可联网，未执行外部 WebSearch。三家成熟系统对标以仓库内《商业化对标审计（第一轮）》为**主依据**（该文已声明对标正方/强智/青果的产品精华）。凡厂商级别的具体差异，若仓库无逐条证据，一律标「**需人工确认**」，不凭想象补厂商细节。

---

## 1. 模块定位与真实学校业务价值

**一句话定位**：违纪处分是学工中心里**程序性、合规性最强**的模块——它把「学生违纪 → 立案取证 → 逐级审批 → 处分生效 → 决定书送达 → 考察期 → 解除 / 申诉」的法定程序全过程线上化、留痕化、可核查化，并向奖助、评优、毕业资格、风险画像等模块**输出权威的处分状态结论**。

**真实学校谁在用、解决什么**（依据：总册 §3.8 ①角色四问 L455；权限总控 L550）：

| 角色 | 真实场景 | 痛点（无系统时） |
|---|---|---|
| 辅导员 / 班主任 | 登记本班违纪事实、上传证据、送达决定书、跟进教育、代发起解除 | 纸质流转慢、证据散落、送达无回证、处分是否影响评奖靠人工记 |
| 学院学工负责人 | 初审、把关事实与建议等级 | 各班尺度不一、审批留痕难 |
| 学工处管理员 | 复核定级、严重处分流转校级、撤销（申诉成立）、台账上报、归档 | 全校口径不统一、上级/教育厅要台账时临时扒表 |
| 校级审批人 | 留校察看 / 开除学籍类终审 | 重大处分程序合规压力大、需可追溯 |
| 学生本人（移动端） | 查本人生效处分、满考察期申请解除 | 不知道处分何时可解除、解除进度不透明 |
| 奖助 / 毕业资格 / 风险模块 | 只读「有无未解除处分」结论 | 跨模块口径不一致导致误发奖学金 / 错放毕业 |

**为什么值得做成生产级**：处分是学校**投标响应项与合规刚需**（决定书文号、送达回证、考察期、解除程序、历史不可篡改），也是奖助/毕业「资格硬校验」的上游数据源（总册 §3.7 L413、§2.4 L176）。做浅了会连累奖助误发、毕业错放。

**不做什么（防自嗨）**：不做违纪行为大数据画像预测、不做 AI 自动定级、不做花哨看板——这些无学校验收口径，进 backlog。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点）

> **主依据**：《13A 学工中心商业化对标审计（第一轮）》L6 明确对标**正方 / 强智 / 青果**三家经市场验证的成熟学工产品的**产品精华与业务成熟度**（不抄界面/代码/DB/商标）。L120 缺口表专列「违纪处分」行。以下厂商级流程为行业通用共识 + 该审计文提炼；**逐厂商界面/字段差异仓库未逐条取证，标「需人工确认」**。

### 2.1 对标对象 A：正方（教务起家、学工一体化）
- **核心流程**：违纪登记 → 学院审核 → 学工处审定 → 处分发布 → 决定书打印 → 解除申请 → 解除审核。
- **角色**：辅导员/学院/学工处/校级，与教务学籍打通（开除→学籍异动）。
- **字段**：违纪类别、违纪事实、处分依据条款、处分种类、文号、生效日期、解除日期。
- **亮点**：与学籍/成绩/毕业资格同库联动强；处分决定书套打模板成熟。
- **缺点**：学工侧独立性弱、移动端体验较教务偏弱（**需人工确认具体版本表现**）。

### 2.2 对标对象 B：强智（教务+学工+一站式）
- **核心流程**：立案 → 多级审批工作流 → 生效 → 送达登记 → 考察期 → 解除审批；配处分台账与统计上报。
- **角色**：可配置审批链（学院/处/校）、按处分等级动态增减节点。
- **字段**：处分等级枚举、最短解除期限（按等级配置）、审批意见、台账导出列。
- **亮点**：审批链高度可配置、台账/统计报表齐全、支持退回/驳回/转办。
- **缺点**：配置复杂、实施成本高（**需人工确认**）。

### 2.3 对标对象 C：青果（学工/迎新/一卡通生态、移动端强）
- **核心流程**：登记（含移动端辅导员简表）→ 审批 → 生效 → 学生端可见本人处分 → 移动端解除申请。
- **角色**：强调辅导员移动端高频操作 + 学生自助端。
- **字段**：与 A/B 同源；突出「学生端仅见本人、明细收敛」。
- **亮点**：移动端高频体验好、学生自助解除申请体验成熟、消息触达强。
- **缺点**：重流程/重台账场景仍需回 PC（**需人工确认**）。

### 2.4 三家共同具备的核心功能（= 本项目必须具备的基础能力）
1. 违纪登记（事实 + 类别 + 证据材料）+ 防重复立案。
2. **逐级审批工作流**（学院→学工处→严重时校级），支持退回/驳回。
3. 处分**等级枚举** + **最短解除考察期**（按等级配置）。
4. 处分**生效**后产生权威状态，联动奖助/评优/毕业**资格校验**。
5. **处分决定书**（文号 + 依据条款 + 生效日期 + 申诉途径 + 水印）与**送达回证**登记。
6. **解除申请→逐级审批→解除**，历史保留不可篡改。
7. 处分**台账**（可筛选导出、脱敏、留痕）与**统计**（校/院/班维度）。
8. 学生端**仅见本人**、明细收敛；教师端按数据范围与敏感权限查看明细。

### 2.5 最值得吸收的最佳做法
- **强智的「审批链按等级动态节点」**：一般处分处末即生效，PROBATION/EXPEL 自动增校级节点（本项目已在状态机 L209–212 采纳）。
- **正方的「处分决定书套打 + 文号规则参数化」**（对标审计补丁 P-09，L415–435）。
- **青果的「学生端仅本人 + 移动端解除申请 + 送达消息直达」**（移动端 S-06 L142 已采纳）。
- 三家共有的**「处分状态是奖助/毕业的资格硬校验上游」**——本项目以 `t_cs_discipline` 投影表统一供数（§2.4 L172–176），既有消费方零改动。

### 2.6 本项目当前已有能力（现状核实，见 §3）
- 后端违纪处分**主闭环已建**：`affairs_discipline_service.py`（register/submit/cancel/review/submit_remove/review_remove）、11 态状态机、EFFECTIVE 事务内投影 `t_cs_discipline`、进 360、解除子流程（辅→院→处）、`projection_reconcile` 对账。
- 表已建：`t_affairs_discipline_case` / `t_affairs_discipline_remove_apply` / `t_cs_discipline`（投影，`source_case_id` 回链）。
- 前端：仅「违纪登记（现有）」挂 `/admin/campus-service/discipline`；另有**未挂载**的 `DisciplineWorkbenchView.vue`（自 feat 分支捞回）。

### 2.7 缺失的生产级闭环（本项目 vs 三家共同核心）
| 三家共同核心 | 本项目缺口 |
|---|---|
| 处分审批 PC 工作台 | 后端有 review 接口，**PC 审批页未接**（planned 占位） |
| 处分决定与送达 | **送达 `/deliver` 接口未实现**；决定书打印模板未落地；送达回证子记录未建 |
| 处分解除（PC） | 后端 remove/remove-review 已建，**PC 解除申请/审批页未接** |
| 申诉复核 | 状态机仅「线下受理 + CANCELLED 撤销动作」，**无线上申诉受理流程与页面**（P2） |
| 违纪台账 | **未接公共 Excel 导出底座**，无 discipline 导出 domain 落地 |
| 处分统计 | stats overview 含处分口径，**处分分组下钻页未接** |

### 2.8 本卡必须补齐（进本轮 C 包）
1. 处分审批 PC 页（08-4）接后端 review。
2. 处分决定与送达页：**新增送达 `/deliver` + 送达回证**、决定书打印模板（补丁 P-09）。
3. 处分解除申请（08-5，PC 代发起）+ 处分解除审批（08-6）接后端 remove/remove-review。
4. 违纪台账页 + **接公共 Excel 导出底座**（脱敏 + 水印 + 留痕）。
5. 处分统计页接 stats 分组下钻。
6. 学生移动端 S-06 送达签收（补丁 P-09 B）+ 教师端 T-06 只读跟进/催办。

### 2.9 进 backlog（本轮不做）
- 申诉**线上化受理流程**（先线下 + CANCELLED 动作兜底，P2）。
- 处分决定书**违纪事实模板库**（P2）、违纪行为大数据分析（P3）。
- 处分公示（对标审计缺口表列为「可配置」，需现场确认是否为学校刚需，**需人工确认**）。

### 2.10 禁止做成假功能
- ❌ 送达/签收/导出 mock 成功（§39 红线）。
- ❌ 前端隐藏按钮冒充权限；越权拦截必须后端校验（§18）。
- ❌ 决定书打印「假 PDF」占位；未接打印/导出管线前该能力标 partial 并记欠账。
- ❌ 申诉页做成空壳可点入口；未定线上流程前维持 planned 占位（§42）。

---

## 3. 三级页面清单与状态（对齐施工图 navPlan `sa-discipline`）

> 依据：`navPlan.js` L146–149（1 个 `I` + 6 个 `P`）；施工图 L166–178（违纪处分二级下能力池）；页面矩阵 §7 页 08-2/08-4/08-6。

| # | 三级页面 | 推荐路由 | 当前状态 | 后端支撑 | 本轮目标 |
|---|---|---|---|---|---|
| 1 | 违纪登记（现有） | `/admin/campus-service/discipline`（现有）→ 迁 `/admin/student-affairs/discipline/create`（页 08-2） | **已实现（I）** | `POST /discipline/cases`、`/submit`、`/cancel` 已建 | 收敛到 08-2 生产页，旧路由 redirect 兼容 |
| 2 | 处分审批 | `/admin/student-affairs/discipline/:caseId/approve`（08-4） | planned（P） | `POST /discipline/cases/{id}/review` 已建 | **接后端 review**，本轮实现 |
| 3 | 处分决定与送达 | `/admin/student-affairs/discipline/:caseId`（08-3 详情，含送达区） | planned（P） | 详情已建；**`/deliver` 未建** | 新增送达接口 + 决定书打印 + 送达回证 |
| 4 | 处分解除 | 申请 `/discipline/:caseId/remove-apply`（08-5）+ 审批 `/discipline/remove/:removeId/approve`（08-6） | planned（P） | `/remove`、`/remove-review` 已建 | 接后端解除双端点 |
| 5 | 申诉复核 | `/admin/student-affairs/discipline/appeal`（**流程待定**） | planned（P） | **无专用接口**；仅 CANCELLED 动作 | **维持占位**；线上流程 P2（需人工确认） |
| 6 | 违纪台账 | `/admin/student-affairs/discipline/ledger` | planned（P） | 列表 `/discipline/cases` 已建；**导出未接** | 台账 + 公共 Excel 导出底座 |
| 7 | 处分统计 | `/admin/student-affairs/discipline/stats` | planned（P） | `stats/overview`、`stats/{group}` 含 discipline | 接分组下钻 |

> **口径纪律**：以上 6 个 planned 页在真实施工完成前，navPlan 保持 `P`（描灰 + 待施工 badge，进公共规划占位页，§42）；做完一个改 `I(label, 真实path)`，占位自动让位。**带占位页不得标 implemented / partial**。
> **注**：施工图 L166–177 还列出「调查取证 / 处分公示」等能力池项，**非本卡 7 页范围**，属能力池，无字段/流程/验收前不挂正式菜单（§7 说明）。

---

## 4. 业务流程与状态机

> 依据：状态机 §4（L195–234）+ §5（L238–261），需求输入 §2.8 原文枚举。**后端 `affairs_discipline_service.py` 已实现此状态机（11 态），本节不重复设计，仅登记口径**。

### 4.1 状态枚举（处分与解除共用一套，需求 §2.8 原文）
`REGISTERED / COLLEGE_REVIEW / STUDENT_AFFAIRS_REVIEW / SCHOOL_REVIEW / EFFECTIVE / REJECTED / RETURNED / CANCELLED / REMOVE_REVIEW / REMOVED / ARCHIVED`

### 4.2 处分主流程（REGISTERED → EFFECTIVE）— 已实现
```
（新建）辅/院 登记 → REGISTERED
REGISTERED → 提交学院初审 → COLLEGE_REVIEW（创建 workflow 实例）
           → 撤销登记(误登) → CANCELLED
COLLEGE_REVIEW → 院初审通过 → STUDENT_AFFAIRS_REVIEW
              → 退回/不予立案 → RETURNED / REJECTED
STUDENT_AFFAIRS_REVIEW → 复核通过(一般处分) → EFFECTIVE
                       → 复核通过(严重:PROBATION/EXPEL) → SCHOOL_REVIEW
SCHOOL_REVIEW → 校级通过 → EFFECTIVE ／ 退回·驳回 → RETURNED / REJECTED
RETURNED → 补充重提 → COLLEGE_REVIEW ／ 放弃 → CANCELLED
```
**EFFECTIVE 事务内联动（服务端同步，已实现）**：写决定字段（decision_no/decision_date/sanction_level/decision_file_id）→ 投影 `t_cs_discipline`（record_status=ACTIVE，`source_case_id` 回链）→ 生成风险记录（source=DISCIPLINE，分派辅导员）→ 冻结奖助/评优资格标记 → 写 360 事件 `AFFAIRS_DISCIPLINE_EFFECTIVE`。

### 4.3 送达（EFFECTIVE 后，**本轮补**）
- EFFECTIVE → 生成送达待办（辅导员，t_unified_todo）→ 辅导员线下送达并登记回执（送达时间 + 回证 file_id）→ EFFECTIVE 留痕（不改效力）。
- 超时：EFFECTIVE 后 7 天无回执 → `DEADLINE_REMINDER→辅导员`（状态机 §4.2 L232）。
- 学生移动端签收（补丁 P-09 B）：学生阅读后签收，写送达签收留痕（时间/IP/审计）；**签收仅送达留痕，不改变处分效力**。

### 4.4 解除子流程（EFFECTIVE → REMOVED）— 后端已实现
```
EFFECTIVE（满最短考察期）→ 学生/辅代发起解除申请 → REMOVE_REVIEW
REMOVE_REVIEW: 辅导员节点 → 学院节点 → 学工处节点（同一状态内 node_code 推进）
  任一节点 驳回 → 回 EFFECTIVE（可再申请）
  任一节点 退回补件 → REMOVE_REVIEW（发起人补件）
  学工处终审通过 → REMOVED（更新投影 t_cs_discipline.record_status=REMOVED，进 360 保留历史）
REMOVED → 联动解冻（奖助/评优恢复；毕业读最新状态）→ 可 ARCHIVED
```

### 4.5 申诉 / 撤销（V1 口径）
- 学生对处分**申诉**：V1 **线下受理**，结果以「撤销」动作线上化——学工处执行 `CANCELLED`（必填撤销依据 + 文号，投影行置 CANCELLED，360 更正事件）。
- **申诉复核页（planned #5）线上受理流程未定** → **需人工确认**：受理主体、受理时限、是否维持/撤销/降级三分支、是否走独立 workflow。未定前维持占位。

### 4.6 非法转移与超时（依据 §4.1/§4.2/§5.1/§5.2）
- EFFECTIVE 记录 append-only，改请求 → **409**；更正走「撤销 + 重登」全程审计。
- 未到 EFFECTIVE 发起解除 → 409。未满最短考察期提交解除 → 409（message 带最早可申请日）。同处分在途解除重复提交 → 409。
- 跨学院登记/审批 → 403 NO_DATA_SCOPE；无权限点角色调创建/审批 → 403 NO_PERMISSION。
- REMOVED 后「抹除记录」请求 → 403（合规，历史不可清除）。
- 解除审批节点停留 ≥72h → `DEADLINE_REMINDER` 催办，**无自动通过**。

### 4.7 责任人矩阵（依据 §4 表「执行角色」列）
| 环节 | 责任人 |
|---|---|
| 登记 / 撤销 / 补充材料 | 辅导员 / 学院（登记人） |
| 学院初审 | 学院学工负责人 |
| 学工处复核 / 撤销（申诉成立） | 学工处管理员 |
| 校级终审（严重） | 校级审批人（处代操作，需人工确认口径） |
| 送达回执登记 | 辅导员 |
| 解除申请 | 学生本人 / 辅导员代发起 |
| 解除审批 | 辅导员初审 → 学院 → 学工处终审 |

---

## 5. 表单字段与校验规则

> 依据：表单校验 §3.9（L275–293）、§3.10（L295–310）、枚举表（L471–482）；API 契约字段（L244/251）。逐字段标必填/校验/敏感级。

### 5.1 处分登记（08-2，PC 专属；基于 `t_cs_discipline` 扩展，材料落 `t_affairs_discipline_material`）

| 字段 | 类型 | 必填 | 校验 | 敏感级 | 失败码 |
|---|---|---|---|---|---|
| 学生 studentId | 学生选择器（范围内） | 是 | 在籍 + 数据范围命中 | 学号/姓名列表脱敏 | 422001 / 403002 跨范围 |
| 违纪日期 violation_date | 日期选择 | 是 | **不晚于当日**（T1 反向适用，服务器时间） | — | 422001 violation_date |
| 违纪地点 | 文本 | 否（需人工确认是否必填） | ≤100 字 | — | 422001 |
| 违纪类别 violation_type | select | 是 | 枚举：ATTENDANCE/EXAM/DORM/FIGHT/PROPERTY/CYBER/OTHER；OTHER 须在事实中说明 | — | 422001 violation_type |
| 违纪事实描述 fact_desc | 长文本 | 是 | **20–1000 字**（L4）；涉他人建议匿写提示 | 事实含第三方姓名，展示脱敏提示 | 422001 fact_description |
| 依据条款 | 文本/选择 | 否（可查校规库，平台规则中心维护） | — | — | — |
| 建议处分等级 suggested_level | select | 是 | 枚举：WARNING/SERIOUS_WARNING/DEMERIT/PROBATION/EXPEL；PROBATION/EXPEL 前端提示「将升级校级审批」 | — | 422001 suggested_level |
| 证据材料 evidence_files | 文件（file_id[]） | 是（≥1） | 至少 1 个 file_id | 证据属敏感附件 | 422001 evidence_files |
| 知情送达方式 | select | 否（需人工确认枚举） | — | — | — |

- **防重复**：同学生 + 同违纪日期 + 同违纪类别的进行中案件唯一 → **409001**「疑似重复登记」（人工确认后可继续，总册 §3.8 ② L456）。
- 支持 DRAFT 暂存（表单校验 L58：处分**解除**申请支持草稿；**处分登记是否支持草稿**——按钮矩阵 L562 列「暂存草稿」为辅/院/处可用，**需人工确认与 L58 一致性**）。

### 5.2 处分解除申请（08-5 / 移动端）

| 字段 | 类型 | 必填 | 校验 | 敏感级 | 失败码 |
|---|---|---|---|---|---|
| 原处分单 case_id | 隐藏（详情带入） | 是 | 状态须 EFFECTIVE 且范围内 | — | 422001 case_id / 状态非法 |
| 表现说明 performance_desc | 长文本 | 是 | **50–1000 字**（移动端 20 字下限见 API #62，**口径不一致需人工确认统一**） | — | 422001 performance_statement |
| 表现证明材料 proof_files | 文件（file_id[]） | 是 | ≤10MB 必传 | 敏感附件 | 422001 proof_files |

- **前提硬校验**：原处分 EFFECTIVE + 满最短考察期（默认 6 个月，按等级可分档，参数中心 `studentAffairs.discipline.probationMonths`，表单 L82）。
- **防重复**：同处分单同时仅一条在途解除（REMOVE_REVIEW）→ 409001；每处分每学期最多申请 1 次（⚙ 可配，需人工确认）。

### 5.3 审批 / 送达表单
- 审批意见（退回/驳回必填，≥5 字，API #58 reason）。改定处分等级与建议不一致时**必填理由**（按钮矩阵 L577）。
- 送达：送达时间 deliveredAt（必）、送达回证 receiptFileId（必）（API #59）。

---

## 6. 权限矩阵与数据范围

> 依据：状态机权限矩阵 L505–511；数据范围 L567；权限总控 L495/L550/L655/L657/L443。

### 6.1 权限点（§3.8 ⑦ L479；命名遵 CLAUDE.md §10 `module.domain.action`）
`studentAffairs.discipline.view`（明细）/ `.create`（登记）/ `.approve` / `.reject` / `.return` / `.schoolApprove`（校级）/ `.deliver`（送达）/ `.remove.create`（解除申请）/ `.remove.approve`（解除审批）/ `.cancel`（撤销）/ `.export`（台账导出）。

### 6.2 角色 × 权限（依据 L505–511）
| 权限点 | 学工处 | 学院学工 | 辅导员 | 班主任 | 心理师 | 宿管 | 资助师 | 学生本人 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| view（明细） | ✓ | 限本院 | 限本班 | 限本班 | ✗ | ✗ | 限(仅资格结论只读) | 限(本人仅状态+文书) |
| create（登记） | ✓ | 限本院 | 限本班 | ✗ | ✗ | ✗ | ✗ | ✗ |
| approve/reject/return | ✓ | 限(初审) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| deliver（送达） | — | — | 限本班 | ✗ | ✗ | ✗ | ✗ | ✗ |
| remove.create（解除申请） | ✗ | ✗ | 限(代发起) | ✗ | ✗ | ✗ | ✗ | 限(本人) |
| remove.approve | ✓(终审) | 限 | 限(初审) | ✗ | ✗ | ✗ | ✗ | ✗ |
| export（台账） | ✓ | 限本院 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

### 6.3 数据范围（依据 L567；来自真实业务关系，非角色名）
| 角色 | 可见范围 | 数据范围来源（业务关系） |
|---|---|---|
| 学工处 | 全校（学工域） | 学工处角色 + SCHOOL scope |
| 学院学工 | 本学院 | COLLEGE scope（组织归属） |
| 辅导员 | 负责班级/学生 | **辅导员-班级绑定关系**（`resolve_teacher_scope`，ADVISOR/CLASS scope） |
| 班主任 | 负责班级 | 班主任-班级绑定 |
| 资助老师 | 仅「有无未解除处分」结论，**不见明细** | FUNDING_BIZ 动态范围（L611），仅资格结论字段 |
| 学生本人 | 本人（状态 + 文书，无办理过程） | SELF scope |
| 心理/宿管 | **不可见** | 无处分权限点 → 403 |

> 后端 `_scope_or_403(db, student_id, user)` 已实现范围校验（service 现状核实）。**前端不做视图裁定**，字段裁剪由服务端按 scope 计算（API 契约 L132）。

---

## 7. 敏感字段脱敏与审计

> 依据：CLAUDE.md §6 红线；权限总控 L495/L512/L516/L581；状态机 L581；总册 §3.8 ⑪ L483。

| 敏感对象 | 默认口径 | 查看/导出条件 | 留痕 |
|---|---|---|---|
| 处分明细（违纪事实/证据材料/文书办理过程） | 仅结论（等级/状态/日期）对非授权角色 | `studentAffairs.discipline.view` + 数据范围命中 | **明细读取写审计**（L581） |
| 违纪事实中第三方姓名 | 登记时提示匿写 | — | — |
| 处分台账导出 | 仅结论字段，明细不出（API 契约导出表 L430） | `.export` + **用途必填≥5 字** + 脱敏列 + 首行水印 | `t_export_task` 留痕，5 次/分限流 |
| 学生端处分 | 仅本人、仅数量 + 文书状态（沿 `t_cs_discipline` 约定） | 学生令牌访问明细接口 → **403001** | 越权访问审计 |

**全审计动作清单**（§3.8 ⑪ L483）：登记 / 改等级 / 各级审批 / 生效 / 送达签收 / 解除 / 撤销 / 查看明细 / 导出。`t_cs_discipline` 投影变更走 `t_affairs_audit_trail` **双留痕**。审计不可伪造，只展示后端真实审计（§40 红线，用 `AppAuditTrail`）。

---

## 8. API 契约草案

> 依据：API 契约 §8（L239–265）、移动端（L462–463）。**下列 #54–#63 大部分已在 `student_affairs.py` L522–566 实现**；标注「已实现/本轮新增」。错误码统一 401/403/404/409/422。

| # | 方法 路径 | 说明 | 权限点 | 审计事件 | 现状 |
|---|---|---|---|---|---|
| 54 | GET `/api/v1/student-affairs/discipline/cases` | 处分案件列表（脱敏） | discipline.view | — | ✅ 已实现 |
| 55 | POST `/discipline/cases` | 登记违纪（factDesc≥20字、level enum、occurredAt、fileIds[]、requestId） | discipline.create | AFFAIRS_DISCIPLINE_REGISTER | ✅ 已实现 |
| 56 | GET `/discipline/cases/{caseId}` | 详情（明细按权限；资格方仅结论）→ detail+materials[]+reviews[]+removeApplies[] | discipline.view | 明细读取审计 | ✅ 已实现 |
| 57 | POST `/discipline/cases/{caseId}/submit` | 提交学院初审 → COLLEGE_REVIEW | discipline.create | APPROVAL | ✅ 已实现 |
| 58 | POST `/discipline/cases/{caseId}/review` | 逐级审批（action APPROVE/REJECT/RETURN、reason、version、requestId） | discipline.approve/reject/return | APPROVAL | ✅ 已实现 |
| 59 | POST `/discipline/cases/{caseId}/deliver` | 送达回执登记（deliveredAt、receiptFileId、requestId） | discipline.deliver（辅导员范围） | AFFAIRS_DISCIPLINE_DELIVER | ⚠ **本轮新增** |
| 60 | POST `/discipline/cases/{caseId}/cancel` | 撤销登记（reason≥5字、version） | discipline.cancel/create | AFFAIRS_DISCIPLINE_CANCEL | ✅ 已实现（现为 /cancel） |
| 61 | GET `/discipline/removals` | 解除申请列表 | discipline.view | — | 需人工确认（service 有 list，路由待核） |
| 62 | POST `/discipline/removals`（现 `/cases/{id}/remove`） | 发起解除（caseId、performanceDesc≥20字、fileIds[]） | discipline.remove.create | AFFAIRS_DISCIPLINE_REMOVE_APPLY | ✅ 已实现（路径口径待统一） |
| 63 | POST `/discipline/removals/{removeId}/review`（现 `/cases/{id}/remove-review`） | 解除逐级审批（辅→院→处） | discipline.remove.approve | APPROVAL | ✅ 已实现（路径口径待统一） |
| — | GET `/discipline/reconcile` | 处分投影一致性对账 | discipline.view | — | ✅ 已实现（运维用） |
| 108/109 | GET `/stats/overview`、`/stats/discipline` | 处分统计 + 分组下钻（COLLEGE/CLASS/GRADE） | stats.view | — | overview ✅；discipline 分组下钻**本轮接** |
| 导出 | POST `/api/v1/export/domain/affairs_discipline` | 台账导出（用途必填、脱敏、水印、留痕） | discipline.export | 导出审计 | ⚠ **本轮新增（接公共底座）** |
| 125 | GET `/api/v1/mobile/affairs/my-discipline` | 我的处分（数量+文书状态，无明细） | 学生本人 | — | 需人工确认（对齐 mobile.py） |
| 126 | POST `/api/v1/mobile/affairs/discipline/{caseId}/remove-apply` | 学生本人发起解除 | 学生本人 | AFFAIRS_DISCIPLINE_REMOVE_APPLY | 需人工确认 |
| — | POST `/api/v1/mobile/affairs/discipline/{caseId}/acknowledge` | 学生移动端签收（补丁 P-09 B） | 学生本人 | 送达签收审计 | ⚠ **本轮新增** |
| — | POST `/api/v1/mobile/teacher/affairs/discipline/{caseId}/remind` | 教师端催办（包装：范围+审计+409） | 辅导员范围 | 催办审计 | ⚠ **本轮新增**（移动端 T-06 L350） |

**统一错误码**（依据 L263）：`401001` 未登录；`403001` 无权限点（心理/宿管/资助/学生调创建审批）；`403002` 跨学院/非范围；`404001` 案件不存在；`409001` EFFECTIVE 记录修改 / 未生效发起解除 / 未满期限（带最早可申请日）/ 在途解除重复；`422001` 字段/材料非法（逐字段 field）。

> **路径口径待统一（需人工确认）**：契约文用 `/discipline/removals`，现有代码用 `/discipline/cases/{id}/remove`。本轮不强行改动已实现接口，若前端按契约对接需先与后端确认最终 path，或保留现路径并更新契约。**不得两套并存无兼容**。

---

## 9. 数据表与迁移

> 依据：总册 §2.4（L172–176）、落表映射（L127–129）、API 投影说明（L549）；MySQL-only（CLAUDE.md §36）。**优先复用，禁止平行建表**。

### 9.1 复用/现有表（已建，核实自 models）
| 表 | 角色 | 说明 |
|---|---|---|
| `t_affairs_discipline_case` | **流程主表** | 11 态全过程；含 student_id/violation_type/fact_desc/occurred_at/suggest_level/sanction_level/decision_no/decision_date/decision_file_id/biz_status/workflow_instance_id/`cs_discipline_id`（投影回链）。已建。 |
| `t_affairs_discipline_remove_apply` | 解除子流程表 | case_id/perform_desc/proof_file_ids/counselor_opinion/biz_status。已建。 |
| `t_cs_discipline` | **生效台账（结论投影表）** | record_status=ACTIVE/REMOVED/CANCELLED；`source_case_id` 回链；**既有读端点/毕业/奖助消费方零改动**（§2.4 硬约束）。已建。 |
| `t_workflow_task` / workflow 实例 | 审批链 | workflow_code=AFFAIRS_DISCIPLINE / AFFAIRS_DISCIPLINE_REMOVE（**不建 review 独立表**，L129）。复用平台。 |
| `t_unified_todo` / `t_unified_message` | 待办/通知 | 送达待办、审批待办、结果消息。复用。 |
| `t_student_stage_event` | 360 | event_type=AFFAIRS_DISCIPLINE_EFFECTIVE/REMOVED/CANCELLED（**不建 timeline 表**，L37）。复用。 |
| `t_affairs_audit_trail` / `t_export_task` | 审计/导出留痕 | 复用平台。 |

### 9.2 本轮新增（最小化，需 Alembic migration）
| 变更 | 表 | 字段 | 理由 | 影响 |
|---|---|---|---|---|
| 送达回证 | `t_affairs_discipline_case` **加列** | `deliver_receipt_file_id`、`delivered_at` | 送达登记（§3.8 ⑨ L481 已列该字段，属补建） | 加列，不影响历史（NULL 默认） |
| 学生签收 | 同上或子记录 | `ack_at`、`ack_ip`（**需人工确认**是否用子表 `t_affairs_discipline_ack`） | 补丁 P-09 B 送达签收留痕 | 若加列则轻量；子表更规范，二选一需确认 |

> **所有新增列/表须**：MySQL utf8mb4 + utf8mb4_unicode_ci、带 tenant_id、软删除/审计字段（CommonMixin/TenantMixin，与现有模型一致）、写 Alembic 可重复迁移，**禁止 create_all 冒充**（§36）。**不新建**：消息/待办/审批/审计/学生主表/心理表/预警表。

---

## 10. Excel 导入导出

> 依据：CLAUDE.md §38（Excel-only）+ §40（接公共底座）；总册 L32 domain 已声明 `affairs_discipline`；导出表 L430（仅结论字段）。

- **导入**：违纪处分**不做批量导入正式入口**（立案须逐条事实 + 证据材料 + 审批，无学校批量导入场景）。**如后续确有历史台账迁入需求 → 需人工确认**，再评估是否接导入。本轮**不做导入**。
- **导出（本轮做）**：接 `app/services/excel/` 公共底座，注册/复用 domain `affairs_discipline`：
  - 前端用 `AppExportButton` + `AppExportConfirm`（§40），文案「导出 Excel 台账」。
  - 按当前筛选条件导出（学号/姓名脱敏、学院/班级、类别、等级、状态、文号、生效日期、解除日期、当前节点）。
  - **仅结论字段，违纪事实明细/证据不出**（L430）。
  - 用途必填≥5 字、首行水印（学校/租户 + 时间 + 操作人）、`t_export_task` 留痕、5 次/分、5000 行上限。
  - 文件名含模块名 + 学校/租户 + 时间。
  - `.export` 权限 + 数据范围裁剪 + 导出审计。
- **决定书打印**（补丁 P-09 A）：EFFECTIVE 后 08-3「导出 PDF」生成处分决定书（文号 / 事实 / 依据条款 / 处分等级 / 生效日期 / 申诉途径 / 签发 / 水印），走导出管线并归档收录；文号规则参数化 `studentAffairs.discipline.docNoRule`。**未接打印管线前该项标 partial + 记欠账**。

---

## 11. 移动端入口

> 依据：移动端设计 S-06（L142–156）、T-06（L340–354）；边界 L514（处分登记与审批仅 PC）。

### 11.1 学生端 S-06「我的处分」★（只读 + 满考察期可申请解除）
- 路径：`pages/student/affairs/discipline/my` / `.../detail` / `.../remove-apply`。
- 可见口径：**仅本人 EFFECTIVE 及之后状态**（审批中登记单不下发）；生效后可见明细（违纪事实脱敏第三方、依据条款、处分决定、考察期至、解除条件）。
- 写：满考察期显示「申请解除」（未满显倒计时不可点）；`POST /mobile/affairs/discipline/{caseId}/remove-apply`（防重复 createSubmitLock，在途再提 409001）。
- **送达签收（本轮补，P-09 B）**：处分送达 STATUS_CHANGED 消息直达详情 →「确认送达」→ 签收留痕（不改效力）。

### 11.2 教师端 T-06「处分跟进」★（只读 + 催办；登记/审批必回 PC）
- 路径：`pages/teacher/affairs/discipline/list` / `.../detail`。
- 只读本班处分进度 + 考察期到期提醒；`GET /mobile/teacher/affairs/discipline`；写仅 `POST /mobile/teacher/affairs/discipline/{caseId}/remind`（催办，包装范围+审计+409）。
- **处分登记、各级审批、严重处分终审、解除审批全部回 PC**（材料多、程序性强、须 PC 留痕）。

### 11.3 学生端 S-11 德育积分流水（关联，非本模块）
- 处分扣分作为来源事件之一在积分流水出现（L214/L220）——**只读联动**，不在本卡范围开发。

---

## 12. 验收标准（页面级）

> 依据：页面矩阵各页 Opus 验收标准（L558/L586/L615）+ CLAUDE.md §20。三态 = loading/empty/error。

| 页 | 验收用例 |
|---|---|
| 08-2 登记 | ①同学生同违纪日期同类别在途再提 → **409001**；②建议等级 PROBATION/EXPEL 提交后审批链**自动含 SCHOOL_REVIEW**；③事实 15 字/未传证据 → 422001 逐字段；④旧路由 `/admin/campus-service/discipline` **redirect 兼容不 404**（§9.1） |
| 08-4 审批 | ①生效后该生 07 资助校验处分项**即时标红且不可通过**；②退回后单据回登记人回填态、学院节点待办消失；③非节点人进入 → 403002 + 审计；④改定等级与建议不一致**必填理由** |
| 08-3 送达 | ①仅 EFFECTIVE 可登记送达回证；②决定书含**文号 + 水印**；③送达 7 天无回执 → 辅导员收 DEADLINE_REMINDER；④学生签收留痕**不改处分效力** |
| 08-5/08-6 解除 | ①未满考察期任意节点同意 → **422001/409001 拦截**（带最早可申请日）；②终审通过后 360 **同时保留处分 + 解除两条事件**；③REMOVED 后 07 资助放行、毕业读最新状态 |
| 申诉复核 | 线上流程未定 → **维持规划占位页**（描灰 + 待施工），不得出现假业务按钮/假数据（§42） |
| 违纪台账 | ①导出**仅结论字段**（事实/证据不出）；②导出**带水印 + 用途必填 + 留痕**；③无 `.export` 权限 → 403001；④筛选条件生效 |
| 处分统计 | ①校/院/班下钻口径与 stats overview 同源；②下钻需 `.view` 权限；③空范围显示 empty 文案 |
| 全模块 | 无控制台错误、无空页面、无假按钮；敏感明细按角色收敛；学生端明细接口对学生令牌 403001；导出/查看明细写审计可查 |

---

## 13. 依据文档索引（逐结论溯源）

| 结论 | 来源文件 + 定位 |
|---|---|
| 三家对标（正方/强智/青果）+15 精华 | `13A-学工中心-商业化对标审计与补丁建议（第一轮）.md` L6/L73/L120 |
| 补丁 P-09（决定书打印 + 学生签收） | 同上 L415–435 |
| 角色四问 / 主流程 / 解除 / 联动 | `13A-学工中心全业务流程设计总册.md` §3.8 L453–496 |
| 处分归属硬约束（case=流程表，cs=投影台账） | 同上 §2.4 L172–176；落表映射 L127–129 |
| 状态机 11 态 / 非法转移 / 超时 | `13A-学工中心状态机与权限矩阵.md` §4 L195–234、§5 L238–261 |
| 权限点 × 角色 / 数据范围 | 同上 L505–511、L567、L581 |
| 逐字段校验 / 枚举 | `13A-学工中心表单字段与校验规则.md` §3.9 L275–293、§3.10 L295–310、枚举 L471–482 |
| 页 08-2/08-4/08-6 按钮矩阵 + 验收 | `13A-学工中心页面级交互与按钮动作矩阵.md` §7 L536–624 |
| API #54–#63 / 错误码 / 联动 / 导出 domain | `13A-学工中心API契约草案.md` §8 L239–265、L430、L549 |
| 移动端 S-06 / T-06 / 回 PC 边界 | `13A-学工中心移动端入口设计.md` L142–156、L340–354、L514 |
| 敏感字段 / 处分审批链 / 角色权责 | `00-系统管理中心-权限角色模块授权与权责边界设计.md` L495/L512/L550/L655/L657 |
| 后端现状（闭环已建） | `backend/app/services/affairs_discipline_service.py`、`backend/app/api/v1/student_affairs.py` L504–566、`backend/app/models/affairs_discipline.py`、`campus_service.py` L100–115 |
| 前端现状（1 实现 + 6 planned + 未挂载捞回页） | `frontend/src/config/navPlan.js` L146–149、`.../studentAffairs/DisciplineWorkbenchView.vue` |

**需人工确认清单**（依据缺失或口径冲突，不得凭空定论）：
1. 申诉复核**线上受理流程**（受理主体/时限/维持-撤销-降级分支/是否独立 workflow）——状态机仅线下 + CANCELLED。
2. 解除表现说明**字数下限**：PC 稿 50 字（表单 L28）vs API #62 移动端 20 字——需统一。
3. 解除接口 **path 口径**：契约 `/discipline/removals` vs 现有代码 `/discipline/cases/{id}/remove`——需统一并保证兼容。
4. 处分**登记是否支持草稿**：按钮矩阵 L562 有暂存 vs 表单 L58 未列登记入草稿名单。
5. 校级审批**触发条件与操作主体**（PROBATION/EXPEL 是否均入 SCHOOL_REVIEW、是否处代校级操作）——总册 ⑱ L496 列为现场确认。
6. 学生本人**可见明细边界**（处分是否对本人可见事实明细）——总册 L277/⑱ L496 列现场确认。
7. 送达**签收留痕落列 vs 落子表**、`知情送达方式`枚举。
8. 处分**公示**是否学校刚需（施工图列「可配置」）——本卡未纳入 7 页。
9. 处分等级**枚举与最短考察期分档**（默认 6 个月，是否按等级 6/12 分档）——参数中心 `probationMonths`。

---

## 14. 施工顺序与依赖

### 14.1 前置依赖
- **必须先就绪**：平台 workflow 引擎、`t_unified_todo/message`、file 上传（证据/回证/表现材料 file_id）、公共 Excel 导出底座、审计/导出留痕、规则中心（考察期/文号规则/校规库）。
- **复用不重建**：`affairs_discipline_service`（主闭环已建）、`t_cs_discipline` 投影（奖助/毕业消费方零改动，§2.4）、公共组件 `AppApprovalPanel`/`AppWorkflowTimeline`/`AppSensitiveText`/`AppExportButton`/`AppAuditTrail`（§40）。

### 14.2 建议施工顺序（做一个亮一个，navPlan P→I）
1. **08-2 登记收敛**：现有登记页升级到生产页 08-2，旧 `/admin/campus-service/discipline` redirect 兼容。（后端已就绪，低风险）
2. **08-4 处分审批**：接 `review`，`AppApprovalPanel` + 严重等级校级节点验收。
3. **08-3 处分决定与送达**：**新增 `/deliver` 接口 + 送达回证列（Alembic）** + 决定书打印模板（打印未接则该子项标 partial + 记欠账）。
4. **08-5/08-6 解除**：接 `remove`/`remove-review`，统一 path 口径（先确认 §13-3）。
5. **违纪台账**：接公共 Excel 导出（脱敏 + 水印 + 留痕）。
6. **处分统计**：接 stats 分组下钻。
7. **移动端**：S-06 签收（P-09 B）+ T-06 催办（各新增 1 包装接口）。
8. **申诉复核**：**维持占位**，待 §13-1 流程确认后单独立卡。

### 14.3 风险点
- **path/字数口径冲突**（§13-2/13-3）：先与后端对齐再对接前端，避免两套并存。
- **决定书打印/PDF 管线**：未接前禁止假 PDF；标 partial 记欠账（§39/§40 红线）。
- **投影一致性**：EFFECTIVE/REMOVED/CANCELLED 必须与 `t_cs_discipline` **同事务**同步；用现有 `/discipline/reconcile` 对账兜底。
- **敏感明细泄漏**：资助老师/班主任/学生端字段裁剪必须**后端做**，前端 `AppSensitiveText` 仅展示层。

### 14.4 建议 commit 粒度（每步独立可回滚，§37）
- `feat(sa-discipline): 08-2 登记收敛 + 旧路由 redirect`
- `feat(sa-discipline): 08-4 处分审批接 review`
- `feat(sa-discipline): 08-3 送达接口 + 回证列迁移 + 决定书打印(partial)`
- `feat(sa-discipline): 08-5/08-6 解除申请与审批`
- `feat(sa-discipline): 违纪台账接公共 Excel 导出`
- `feat(sa-discipline): 处分统计分组下钻`
- `feat(sa-discipline): 移动端 S-06 签收 + T-06 催办`
- 每步：`npm run build` 通过 + 相关 pytest 通过 + 更新 `docs/施工记录/历史欠账.md`（决定书打印 partial、申诉线上化 backlog、path 口径待统一）。

---

> **收口纪律**：本卡范围内**只写文档**。真实施工时，navPlan 每完成一页由 `P` 改 `I(label, 真实path)`；未完成项维持 planned 占位（§42）；partial/backlog 项同步登记 `docs/施工记录/历史欠账.md`（§35）与「上线前必做清单-总闸门」。
