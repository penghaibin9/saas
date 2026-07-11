# 施工卡 · 学工中心 · 困难认定（sa-difficulty）

> 性质：**生产级施工卡，只写文档、不改任何代码/navPlan/配置/迁移。**供甲方明天照此开发。
> 模块键：`studentAffairs` / `sa-difficulty`（navPlan 现状：planned·待施工，6 个三级叶子）。
> 对标口径：严格遵循 `CLAUDE.md` §0.0「市场验证优先与成熟商业系统复刻规则」——先对标经市场验证的成熟学工产品（正方 / 强智 / 青果），再用本项目 SaaS 架构重新实现，不由 AI 发明功能。
> 证据规则：每条关键结论在 §13 标来源文件 + 章节/行号；仓库读不到的一律标「**需人工确认**」，不臆造字段/接口/流程。
> 撰写依据基线：本卡基于仓库现有文档与已落地后端代码（`affairs_aid.py` / `affairs_aid_service.py` / `student_affairs.py` 的 aid 段）审计撰写；**前端 PC 页面 0 落地**，故整体状态 = planned·待施工。

---

## 1. 模块定位与真实学校业务价值

**一句话定位**：面向高职院校家庭经济困难学生的**认定—评议—三级审批—公示—入库—动态调整—年度复核**全流程，产出「困难学生库 + 困难等级」，作为奖助勤贷补、绿色通道、临时补助的**唯一上游数据源**。

**真实学校谁用、解决什么**（依据总册 §3.6 ①角色四问，L361）：

| 角色 | 真实工作 | 本模块解决 |
|---|---|---|
| 学工处 / 资助中心（`studentAffairs.aid` 管理端） | 每学年建认定批次、定等级档位、终审核定、管全库、报送上级 | 批次化管理、全库台账、覆盖率统计、导出报表（脱敏+水印） |
| 学院学工负责人 | 复审本院申请、把关名额与真实性 | 本院数据范围内的复审待办、名单差额排序 |
| 辅导员 | 组织班级民主评议、录入评议结果、初审建议等级、日常动态调整发起 | 移动端评议录入 + PC 初审、本班困难生视图 |
| 班级评议小组 | 线下民主评议、公开公平打分 | 评议结果结构化留痕（防「谁定的等级说不清」） |
| 学生本人 | 手机提交家庭经济信息+材料、查进度、看结果、提异议 | 移动端强敏感申请表单、进度条、退回原因、结果通知 |

**为什么必须做成闭环而非裸 CRUD**：困难认定是学校**资助合规**的第一道闸门——「谁是困难生、什么等级、依据什么、谁审的、公示了没、有没有异议」必须全程可追溯、可审计、可上报。家庭经济信息属**强敏感个人信息**（涉低保、残疾、大病、家庭变故），一旦泄露即合规事故。产出的困难等级直接决定学生能否领国家助学金/助学贷款/勤工岗位，**错认、漏认、暗箱**都是真实投诉与审计风险点。这不是「能卖出去的自嗨功能」，而是每所职校每学年必跑、教育厅要抽查的刚需业务。

---

## 2. 三家成熟系统对标表（严格按 CLAUDE.md §0.0 十点）

> 主依据：`13A-学工中心-商业化对标审计与补丁建议（第一轮）.md`（已对标正方/强智/青果的产品精华与业务成熟度，L6 对标声明；15 条精华原则 L73–103；缺口表第 6 行困难认定 L118；逐模块检查第 6 条 L148）。
> 说明：本卡对标的是三家产品**经市场验证的业务成熟度**（流程闭环、角色分工、批量、台账、权限审计、公示合规、导入导出、移动端习惯），**不抄袭其界面、代码、数据库、商标**。三家产品的具体内部字段/接口本仓库无一手资料，凡涉及「某家某字段」的精确断言均标「需人工确认」；本表结论以「三家共同的成熟做法」为准，来源为上述审计文档的提炼。

### ① 对标对象 A：正方（教务起家、学工一体化）
- **核心流程**：认定批次 → 学生网上申请（家庭经济信息表）→ 班级评议 → 辅导员/学院/学校逐级审核 → 公示 → 入库。以「批次 + 逐级审批」为骨架，与教务学籍打通。
- **角色**：校级资助管理员、院级审核员、辅导员、学生；强调**逐级权限下放**。
- **字段**：家庭人口、家庭年收入、人均收入、致困类型、民政/村委证明。（具体字段名**需人工确认**）
- **亮点**：与学籍/成绩打通，资格校验（学籍异常、成绩）联动强；批次报表规整。
- **缺点**：家庭经济敏感字段脱敏与审计颗粒度偏弱（行业通病，**需人工确认**）；移动端评议体验一般。

### ② 对标对象 B：强智（教务+学工老牌，占有率高）
- **核心流程**：与 A 类似，突出**民主评议量化打分**与**公示合规**（公示天数、异议登记）。
- **角色**：资助中心、二级学院、评议小组、辅导员、学生；评议小组作为独立参评主体留痕。
- **字段**：评议得分、评议排名、评议参与人数、公示起止、异议记录。（具体字段名**需人工确认**）
- **亮点**：民主评议结构化（得分+排名+参评人数）＋公示与异议闭环，合规叙述强，投标响应好。
- **缺点**：动态调整/年度复核多为线下或弱线上（**需人工确认**）；家庭经济导出水印非默认强制。

### ③ 对标对象 C：青果（学工/迎新专精，移动端强）
- **核心流程**：移动端优先——学生手机填报家庭经济、辅导员手机评议录入、审批待办直达；PC 端做管理与台账。
- **角色**：同上，强调**辅导员移动端高频动作**。
- **字段**：材料附件、致困类型标签、困难等级、有效期。（具体字段名**需人工确认**）
- **亮点**：移动端体验、弱网草稿、材料拍照上传、进度条与退回原因醒目。
- **缺点**：与奖助金额台账的贯通、多维统计钻取偏弱（**需人工确认**）。

### ④ 三家共同具备的核心功能（= 本项目必须具备的基础能力）
1. **认定批次**（学年/申请窗/等级档位/材料要求/公示天数可配）。
2. **学生网上申请**：家庭经济信息表 + 致困类型 + 证明材料附件。
3. **班级民主评议**：评议意见 / 建议等级 / 得分排名 / 参评人数**结构化留痕**。
4. **逐级审批**：辅导员初审 → 学院复审 → 学校终审，各级可改建议等级、可退回、可驳回。
5. **公示**：脱敏名单公示 + 公示天数 + 异议登记与处理回退。
6. **入库**：产出困难学生库（等级 + 有效期），供奖助引用。
7. **动态调整 + 年度复核**：等级升降/移出、跨学年复核。
8. **家庭经济强敏感**：默认脱敏、完整值需授权+审计、导出水印。
9. **台账 + 统计**：困难生数、等级分布、覆盖率、办理进度、导出。

### ⑤ 三家里最值得吸收的最佳做法
- **B 的民主评议量化留痕**（得分+排名+参评人数）——把「暗箱定级」变成可核查证据链。
- **B 的公示与异议合规闭环**——公示脱敏 + 天数可配 + 实名异议回退复核，是资助审计必查项。
- **C 的移动端评议+申请体验**——辅导员手机录评议、学生手机填报，弱网草稿、进度条、退回原因。
- **A 的资格联动**——认定/奖助与学籍、处分状态硬校验，防不合格发放。

### ⑥ 本项目当前已有能力（有证据）
- **后端骨架已落地（partial）**：`affairs_aid.py` 已建 4 表 `t_affairs_aid_batch / _apply / _family_economy / _level_history`；`affairs_aid_service.py` 已实现批次、申请（含家庭经济隔离表 + 脱敏 `_mask_family` / 授权揭示 `_reveal_family`）、逐级 review、退回重交、公示扫描/确认、动态调整+审批、困难学生库、`is_in_difficult_library`；`student_affairs.py` 已挂 12 个 aid 端点；`mobile.py` 已挂 `/affairs/aid/my`。
- **状态机已冻结**：状态机文档 §2（13 态 + 转移表 + 非法转移防护 + 超时自动转移）。
- **表单字段已冻结**：表单文档 §3.4（家庭经济强敏感表单 6 组字段 + 校验 + 脱敏 + 422 场景）。
- **权限矩阵已定义**：状态机文档 §14（`studentAffairs.aid.*` 7 个权限点 + 8 角色可见性 + 数据范围）。
- **Excel 公共底座已存在**：`backend/app/services/excel/`（pipeline/spec/validators/job_service）+ `frontend/src/components/common/excel/`（导入抽屉/上传/错误汇总/预览/导出按钮）。

### ⑦ 缺失的生产级闭环（当前欠账）
1. **PC 前端 0 落地**：`frontend/src/views/admin/student-affairs/aid/` 目录不存在，6 个三级页全部待建（navPlan `sa-difficulty` = planned）。
2. **后端鉴权颗粒度不足**：aid 端点统一 `require_staff`，**未落到** §14 定义的 `studentAffairs.aid.*` 细粒度权限点与数据范围硬校验 → 越权风险（B 级上线前欠账）。
3. **班级评议无独立表**：现用 `t_affairs_aid_apply` 上的 `class_review_score/rank` 字段，**未建** 总册 §3.6 ⑨ 提及的 `t_affairs_aid_class_review`（评议意见/参评人数）→ 评议留痕不完整。
4. **异议处理未线上化**：状态机允许 PUBLICITY→SCHOOL_REVIEW 回退，但「异议单」登记/核查/结论无独立结构（总册 §3.6 ⑰ 标 P2）。
5. **金额/台账导出与统计页未建**：认定统计（06-8）前端未建；导出未接 Excel 底座。
6. **年度复核任务化未落地**：状态机 §2.2 有「每学年初批量生成待办」定义，服务层 `scan_publicity` 有但年度复核批量任务**需人工确认**是否已实现。

### ⑧ 进 backlog（本卡不一次性交付，纳入能力池，按授权/条件启用）
- 民政/银联等**外部数据接口核验**家庭经济真实性（总册 §3.6 ⑰ P2；依赖第三方，需采购授权）。
- **量化评分模型 / 名单智能推荐**（总册 §3.6 ⑰ P3；无算法时人工评议兜底已能跑通）。
- 家庭经济 OCR 材料自动识别（需人工确认可行性）。

### ⑨ 禁止做成假功能（红线）
- 禁止家庭经济字段**明文直出**或无审计读取路径（状态机 §2.1 L120：不写审计的读取路径不得存在）。
- 禁止公示名单**不脱敏**展示金额/致困明细（总册 §3.6 ⑤：公示脱敏是合规红线）。
- 禁止用前端隐藏冒充权限（CLAUDE.md §3.4；权限总控第 4 层校验）。
- 禁止导出**不带水印、不二次确认、不审计**（状态机 §14 L565）。
- 禁止 mock 写操作成功、禁止把 planned 占位页标 implemented。

---

## 3. 三级页面清单与状态

> **口径对齐说明**：navPlan `sa-difficulty` 与施工图按 **6 个三级**组织（认定批次/认定申请/认定审核/公示与异议/困难学生库/认定统计）；页面树文档 §3.4（L218–229）按 **8 页**细分（06-1…06-8）。二者不冲突——6 个三级页各含若干子视图/抽屉。本卡以 navPlan 的 6 三级为准，并标注对应页面树编号。

| # | 三级页（navPlan 叶子） | 路由（建议，需与旧路由兼容） | 对应页面树 | 主要角色 | 当前状态 | 备注 |
|---|---|---|---|---|---|---|
| 1 | 认定批次 | `/admin/student-affairs/aid/batches`（详情 `:batchId`） | 06-1 + 06-2 | 处/资（院只读） | planned·待施工 | 批次列表 + 详情配置（学年/时间窗/等级档/材料/公示天数） |
| 2 | 认定申请 | `/admin/student-affairs/aid/applications`（详情 `:applyId`） | 06-3 + 06-4 | 处/资/院/辅 | planned·待施工 | 申请列表（家庭经济默认脱敏）+ 详情（看完整必审计） |
| 3 | 认定审核 | `/admin/student-affairs/aid/applications/:applyId/review` | 06-5 | 当前节点人（班评/辅/院/处） | planned·待施工 | 班评/初审/复审/终审同页分节点；可改建议等级/退回/驳回 |
| 4 | 公示与异议 | `/admin/student-affairs/aid/publicity` | 06-6 | 处/资 | planned·待施工 | 脱敏公示名单 + 公示天数 + **异议登记与处理**（本卡新增闭环） |
| 5 | 困难学生库 | `/admin/student-affairs/aid/difficult-students` | 06-7 | 处/资/院/辅（脱敏+水印） | planned·待施工 | level_history 有效行物化视图；供奖助/绿通引用 |
| 6 | 认定统计 | `/admin/student-affairs/aid/stats` | 06-8 | 处/资/院 | planned·待施工 | 困难生数/等级分布/覆盖率/办理进度/年度复核完成率 + 下钻 |

**旧路由兼容**：本模块为新建，无旧 PC 路由需 redirect；旧一级 `/admin/student` 系入口按 CLAUDE.md §9.1 保留 alias。**需人工确认**是否存在旧「在校服务-困难补助」入口需指向本模块。

**移动端联动页**（详见 §11）：学生端 `pages/student/affairs/aid/apply`（申请）+「我的认定」；教师端评议录入简表 + 审批待办。

---

## 4. 业务流程与状态机

> **已实现项标注**：状态机文档 §2 已冻结，服务层 `affairs_aid_service.py` 已实现主干；本节不重复设计，只标「已实现/待补」。

**状态枚举（13 态，需求输入 §2.6 原文，已冻结）**：
`NOT_STARTED / DRAFT / SUBMITTED / CLASS_REVIEW / COUNSELOR_REVIEW / COLLEGE_REVIEW / SCHOOL_REVIEW / PUBLICITY / APPROVED / REJECTED / ADJUST_REVIEW / ARCHIVED`（总册 §3.6 ⑥ 另列 RETURNED 语义，服务层以 review action=RETURN 回退到前节点实现）。

**主流转（状态机 §2 转移表 L94–114，已实现）**：

| From | 动作（角色） | To | 服务层方法 | 状态 |
|---|---|---|---|---|
| NOT_STARTED | 发布批次 | 开放学生 DRAFT | `create_batch(publish=True)` | 已实现 |
| DRAFT | 提交（生，窗口内） | SUBMITTED→CLASS_REVIEW | `apply()`（直达班级评议） | 已实现 |
| CLASS_REVIEW | 评议录入（辅/班） | COUNSELOR_REVIEW | `review(action=APPROVE)` | 已实现（评议独立表待补，见 §9） |
| COUNSELOR_REVIEW | 初审通过/退回/驳回（辅） | COLLEGE_REVIEW / RETURNED / REJECTED | `review()` | 已实现 |
| COLLEGE_REVIEW | 复审通过/退回/驳回（院） | SCHOOL_REVIEW / … | `review()` | 已实现 |
| SCHOOL_REVIEW | 终审核定等级（处/资） | PUBLICITY | `review()` | 已实现 |
| PUBLICITY | 异议登记（处/院/资） | SCHOOL_REVIEW（复核） | **待补：异议单闭环** | 待补（§7 P2） |
| PUBLICITY | 期满无异议 | APPROVED（入库，写 level_history） | `scan_publicity()` / `confirm_publicity()` | 已实现 |
| RETURNED | 补充重交（生） | 回退节点（评议结果保留） | `resubmit()` | 已实现 |
| APPROVED | 动态调整（生/辅代发起） | ADJUST_REVIEW | `adjust()` | 已实现 |
| ADJUST_REVIEW | 调整通过/驳回（处/资） | APPROVED（新/原等级） | `approve_adjust()` | 已实现 |
| APPROVED/REJECTED | 学年归档 | ARCHIVED | **需人工确认**是否已实现 | 待补 |

**责任人与超期升级（状态机 §2.2，已定义）**：
- 批次截止：`now > apply_end` → DRAFT 未提交单标记失效；截止前 48h `DEADLINE_REMINDER` 提醒学生。（服务层**需人工确认**是否已挂定时任务）
- 公示期满：PUBLICITY 满 N 天（默认 5 工作日，可配）无未结异议 → 自动 APPROVED。（`scan_publicity` 已实现，幂等）
- 年度复核：每学年初 APPROVED 存量批量生成 ADJUST_REVIEW 待办→辅导员。（**待补/需人工确认**）

**非法转移防护（状态机 §2.1，已实现于服务层校验）**：批次未开放/已截止提交→409；同批次重复→409（`uniq(batch_id,student_id)`）；无 sensitiveView 查完整家庭经济→403；越级/跨学院审→409/403；REJECTED 后调整→409。

---

## 5. 表单字段与校验规则

> 依据表单文档 §3.4（L184–203，已冻结）。**整表为强敏感表单**：家庭经济字段落 `t_affairs_aid_family_economy`，敏感项 `*_encrypted` 存储、列表/详情默认脱敏、导出水印、查看完整必须填理由+落审计。

### 5.1 学生申请表单（`aid/apply`）

| 字段 | 类型 | 必填 | 枚举/取值 | 校验 | 敏感级 | 后端 422 |
|---|---|---|---|---|---|---|
| 认定批次 `batch_id` | select（开放批次） | 是 | 当前 PUBLISHED 批次 | 批次时间窗内 | — | 批次已截止/未发布→422001 |
| 家庭成员 `family_members` | 子表单 1–10 行 | 是 | 每行：姓名/关系/年龄/健康/职业/年收入 | ≥1 行；姓名 2–20；关系 select；年龄 0–120；健康 select；收入≥0 | **强敏感**：姓名加密，出口姓+**；收入默认隐藏 | 0 行→422001 family_members；年龄 150→422001 family_members[i].age |
| 家庭年收入 `annual_income` | 数字(元) | 是 | 0–9,999,999 | 非负 | **强敏感**：默认显区间档，精确值需审计 | 负数/超上限→422001 |
| 人均月收入 `per_capita_income` | 只读自动算 | 自动 | 年收入÷成员数÷12 | 联动 | **强敏感** | 前后端不一致→422001 |
| 致困因素 `difficulty_factors` | 多选 | 是(≥1) | LOW_INCOME/ARCHIVED_POOR/ORPHAN/DISABILITY/SUDDEN_CHANGE/MULTI_CHILDREN/OTHER | ≥1 项；OTHER 补说明 10–200 字 | **强敏感** | 空选/枚举外→422001 |
| 是否低保/特困 `is_subsistence` | radio | 是 | true/false | 选是则低保证明必传 | **强敏感** | 选是未传证明→422001 subsistence_proof |
| 低保证明 `subsistence_proof` | 文件 | 条件必传 | PDF/JPG/PNG ≤10MB ≤3 | F1–F3 | 加密存储、预览水印 | 类型/大小→422001 |
| 民政证明 `civil_affairs_proof` | 文件 | 是 ⚙(开关) | PDF/JPG/PNG ≤10MB ≤5 | 必传开关接规则中心 | 同上 | 未传→422001 |
| 困难情况说明 `statement` | textarea | 是 | — | 10–500 字 | **强敏感**，审核页默认折叠 | 字数不符→422001 |

- 草稿：支持（保存仅校验批次；家庭成员行草稿期不拦截）。
- 防重复：同学生同批次唯一（非 REJECTED 单）→ **409001**。
- **口径差异提示**：后端 `AidApplyBody`（`student_affairs.py`）当前入参为 `applyLevel/statement/memberCount/annualIncome/debt/familyMembers/specialTags`，字段名与表单文档 §3.4 **不完全一致**（如 `annual_income` vs `annualIncome`、缺 `per_capita_income/difficulty_factors/is_subsistence` 显式入参）→ **前端联调前需人工确认统一字段契约**。

### 5.2 审核表单（`review`）
| 字段 | 类型 | 必填 | 校验 |
|---|---|---|---|
| action | select | 是 | APPROVE/REJECT/RETURN |
| level（建议/核定等级） | select | 条件 | SPECIAL/DIFFICULT/GENERAL（对应 A特困/B困难/C一般，**需人工确认枚举中英对照统一**） |
| reason（退回/驳回原因） | textarea | RETURN/REJECT 时必填 | ≤500 字；驳回原因将展示给学生 |

### 5.3 动态调整表单（`adjust`）
`targetLevel`（必填 SPECIAL/DIFFICULT/GENERAL）+ `reason`（必填 ≥1 字，建议 ≥5 字与全站退回原因口径一致，**需人工确认**）。

---

## 6. 权限矩阵与数据范围

> 依据状态机文档 §14（L489–496 权限矩阵、L565 数据范围行）+ 权限总控 §（四层校验 L70）。**引用权限总控**：`docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md`。

**权限点（§14 已定义 7 点）**：

| 权限点 | 处 | 院 | 辅 | 班 | 心 | 宿 | 资 | 生 |
|---|---|---|---|---|---|---|---|---|
| `studentAffairs.aid.view` | ✓ | 限本院 | 限本班 | 限(名单不含明细) | ✗ | ✗ | ✓ | 限本人 |
| `studentAffairs.aid.batch.manage` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| `studentAffairs.aid.create`（申请） | ✗ | ✗ | 限(代发起) | ✗ | ✗ | ✗ | ✗ | 限本人 |
| `studentAffairs.aid.approve/reject/return` | ✓ | 限 | 限 | 限(班级评议) | ✗ | ✗ | ✓ | ✗ |
| `studentAffairs.aid.adjust`（调整/复核） | ✓ | 限 | 限(发起) | ✗ | ✗ | ✗ | ✓ | 限本人发起 |
| `studentAffairs.aid.sensitiveView`（家庭经济完整值，强制审计） | ✓ | 限 | 限 | ✗ | ✗ | ✗ | ✓ | 限本人 |
| `studentAffairs.aid.export`（水印+二次确认） | ✓ | 限 | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |

**数据范围（来自真实业务关系，§14 L565）**：
- 学工处 = 全校；学院学工 = 本学院；辅导员 = **负责班级**（来自辅导员-班级绑定，`resolve_teacher_scope`/`getStudentAffairsScope`）；班主任 = 负责班级（名单，**无家庭经济明细**）；资助老师 = AID_STUDENT 范围或全校（按角色配置）；学生 = 本人。
- 心理老师/宿管 = **不可见**困难认定。

**⚠️ 上线前必须补齐的欠账（B 级）**：后端 aid 端点当前统一 `require_staff`（`student_affairs.py`），**未接**上述细粒度权限点与数据范围硬校验。生产前必须：① 每端点接 `studentAffairs.aid.*` 权限点；② `_scope_or_403` 已有雏形（`affairs_aid_service.py` L129）需接 `getStudentAffairsScope` 真实数据范围；③ 敏感揭示接 `sensitiveView` 权限点而非 `_can_sensitive_view` 粗判。登记至 `docs/施工记录/历史欠账.md`。

---

## 7. 敏感字段脱敏与审计

> 依据 CLAUDE.md §6 敏感数据红线 + 状态机 §2.1 L120 + 表单 §3.4 L186 + 总册 §3.6 ⑯ L402。

**强敏感字段清单**：家庭成员姓名、家庭年收入、人均收入、致困因素、疾病描述、低保/民政证明材料。全部 `*_encrypted` 加密存储于隔离表 `t_affairs_aid_family_economy`。

**脱敏规则（服务层 `_mask_family` 已实现）**：
- 列表/详情**默认脱敏**：姓名 → 姓+**；收入 → 区间档位（`_income_range`，如「1万–2万」）而非精确值；致困/病因折叠。
- 完整值揭示：走 `/aid/applications/{applyId}/reveal`，**必须填查看原因 + 落 `SENSITIVE_VIEW` 审计**（`t_security_audit_log`，含 ip/ua/traceId/原因）。**不写审计的读取路径不得存在**（状态机 §2.1 L120 红线）。
- 公示名单：**脱敏展示**（姓名部分掩码 + 班级，**不含金额/致困明细**）——合规红线（总册 §3.6 ⑤）。

**审计留痕点（总册 §3.6 ⑪）**：申请、评议录入、各级审批、公示发布、异议处理、等级变更、**查看完整家庭经济（必审计+原因）**、导出（水印 + `t_export_task` 留痕）。

**最小授权 + 二次确认**：sensitiveView 仅处/院/辅/资；导出 sensitiveView 数据前二次确认弹窗 + 强制水印。前端一律用 `AppSensitiveText` 组件（CLAUDE.md §40），不自写脱敏函数。

---

## 8. API 契约草案

> **现状**：以下端点**后端已落地**于 `backend/app/api/v1/student_affairs.py`（aid 段 L338–410）+ `affairs_aid_service.py`。前端按此对接。所有端点当前鉴权 = `require_staff`（**待升级为细粒度权限点，见 §6**）。统一响应 `success(data, message)`；分页 `paginate(items,total,page,pageSize)`。

| 方法 | 端点 | 用途 | 关键入参 | 出参 | 错误码 |
|---|---|---|---|---|---|
| POST | `/aid/batches` | 建/发布批次 | batchName/schoolYear/applyStart/applyEnd/publicityDays/levelConfig/publish | batch row | 401/403/422 |
| GET | `/aid/batches` | 批次列表 | schoolYear?/status?/page/pageSize | 分页 | 401/403 |
| POST | `/aid/applications` | 发起申请（含家庭经济，直达班评） | batchId/studentId/applyLevel/statement/annualIncome/familyMembers… | apply row | 401/403/**409**(重复)/**422**(校验) |
| GET | `/aid/applications` | 申请列表（默认脱敏） | batchId?/status?/level?/page/pageSize | 分页(脱敏) | 401/403 |
| GET | `/aid/applications/{applyId}` | 申请详情（脱敏） | applyId | apply+family(脱敏) | 401/403/**404** |
| POST | `/aid/applications/{applyId}/review` | 各级评审 | action(APPROVE/REJECT/RETURN)/level?/reason? | 新状态 | 401/403/**409**(状态冲突)/422 |
| POST | `/aid/applications/{applyId}/resubmit` | 退回后重交 | applyId | 新状态 | 401/403/409 |
| POST | `/aid/applications/{applyId}/publicity-confirm` | 人工确认公示满→通过 | applyId | APPROVED | 401/403/409 |
| POST | `/aid/scan-publicity` | 公示满扫描（定时/手动，幂等） | — | 处理数 | 401/403 |
| POST | `/aid/applications/{applyId}/adjust` | 发起等级动态调整 | targetLevel/reason | ADJUST_REVIEW | 401/403/**409**(非APPROVED) |
| POST | `/aid/applications/{applyId}/adjust-approve` | 调整审批 | action | APPROVED | 401/403/409 |
| POST | `/aid/applications/{applyId}/reveal` | 查看完整家庭经济 | reason | 完整值+**审计** | 401/**403**(无sensitiveView)/404 |
| GET | `/aid/difficult-students` | 困难学生库 | level?/page/pageSize | 分页 | 401/403 |
| GET(m) | `/mobile/affairs/aid/my` | 学生我的认定 | — | 我的申请+等级 | 401 |

**待新增端点（缺口，需开发）**：
- `GET /aid/stats?drillLevel=&parentId=`（认定统计：困难生数/等级分布/覆盖率/办理进度/年度复核完成率 + 下钻脱敏）——**需人工确认**是否已有。
- `POST /aid/applications/{applyId}/objection`（异议登记）+ `POST …/objection/{id}/resolve`（异议处理）——**异议线上化，本卡缺口**。
- `POST /aid/export`（导出台账，接 Excel 底座，水印+脱敏+审计）——**待接**。
- `GET /aid/import-template` + `POST /aid/import`（批量导入历史困难生/家庭经济，接 Excel 底座）——**需人工确认**是否需要。

**错误码语义（全站统一）**：401 未登录；403 无权限/无数据范围(NO_DATA_SCOPE)/无 sensitiveView(NO_PERMISSION)；404 单据不存在；409 状态冲突/重复申请(IDEMPOTENCY)；422 表单校验(422001+字段名)；500 服务异常。

---

## 9. 数据表与迁移

> 规则：MySQL utf8mb4 + `utf8mb4_unicode_ci`；`tenant_id` 行级隔离；软删除 + 审计字段（CommonMixin）。**优先复用现有表，不建平行表**。依据总册 §3.6 ⑨（L389）、数据表草案 L122/L188、模型 `affairs_aid.py`。

**已存在表（复用，来自 `backend/app/models/affairs_aid.py`）**：

| 表 | 状态 | 关键字段 | 约束/说明 |
|---|---|---|---|
| `t_affairs_aid_batch` | 已建 | school_year / apply_start / apply_end / publicity_days / level_config / biz_status | PKMixin+TenantMixin+CommonMixin |
| `t_affairs_aid_apply` | 已建 | batch_id / student_id / apply_level / statement / suggest_level / final_level / biz_status / workflow_instance_id / **class_review_score / class_review_rank** | **uniq(batch_id, student_id)**（同批次唯一） |
| `t_affairs_aid_family_economy` | 已建 | apply_id / member_json / annual_income_encrypted / illness_desc_encrypted / proof_file_ids | **强敏感隔离表**，敏感列 `*_encrypted` |
| `t_affairs_aid_level_history` | 已建(append-only) | student_id / level(A特困/B困难/C一般) / effective_year / status / source_apply_id | 「困难学生库」= 本表最新有效行物化视图 |

**建议新增表（缺口）**：
| 表 | 用途 | 依据 | 优先级 |
|---|---|---|---|
| `t_affairs_aid_class_review` | 班级评议独立留痕（opinion/suggest_level/attendee_count/评议成员）——现仅靠 apply 上 score/rank 字段，评议留痕不完整 | 总册 §3.6 ⑨ L389 明确列此表 | 建议补（评议合规） |
| `t_affairs_aid_objection` | 公示异议单（提出人/内容/核查/结论/回退关联）——异议线上化 | 缺口 §7 | P2（可先线下+备注） |

- **迁移**：新增表必须写 Alembic migration（现有 aid 表迁移**需人工确认**版本号，参考 `backend/alembic/versions/`）；禁止 create_all 长期替代。
- **不建平行表红线**：奖助引用困难库走 `is_in_difficult_library()` 只读，**不复制**困难数据；家庭信息**不回写** `t_student_contact`（总册 §3.6 ⑯）。

---

## 10. Excel 导入导出

> 规则 CLAUDE.md §38 + §40：**正式导入导出用 xlsx**，接公共底座 `backend/app/services/excel/` + `frontend/src/components/common/excel/`（均已存在），**不自造解析/校验/错误行/导出审计**。

**导出困难学生库台账 / 认定名单**（必做）：
- 前端用 `AppExportButton` + `AppExportConfirm`（二次确认）；按当前筛选条件导出。
- 敏感字段**脱敏导出**（收入区间档、姓名掩码），除非 sensitiveView 权限 + 二次确认才导完整并**强制水印**。
- 文件名含：模块名 + 学校/租户 + 时间（如 `困难学生库_XX职院_20260712.xlsx`）。
- 导出落 `t_export_task` + 审计（状态机 §14 L565：导出强制水印+二次确认）。

**导入（历史困难生/家庭经济批量建档，按需，需人工确认是否要）**：
- 下载 Excel 模板 → 上传 xlsx → 字段/必填/格式/业务规则校验 → 文件内重复 + 库内重复校验 → 错误行预览（`AppImportPreviewTable`/`AppImportErrorSummary`）→ 下载错误行 Excel → 确认导入 → 导入记录 + 审计。
- 家庭经济为强敏感 → 导入的敏感列同样加密落隔离表，导入操作审计。

**验收**：CSV 不得作为正式方案；导入导出与页面校验规则**同源复用**（不得两套）。

---

## 11. 移动端入口

> 依据移动端设计文档 + 总册 §3.6 ⑮（L401）+ 已落地 `mobile.py` `/affairs/aid/my`。困难认定属**学生高频 + 辅导员高频**，移动端优先。

**学生端**（`pages/student/affairs/aid/apply`，可写）：
- 「资助-困难认定申请」：强敏感家庭经济分组表单 + 致困类型 + 材料拍照上传；支持**弱网草稿**（表单 §3.4 草稿支持）、防重复提交（`createSubmitLock`）。
- 「我的认定」：进度条 + 当前节点名 + 退回原因醒目 + 结果通知（`/mobile/affairs/aid/my` 已实现）。
- 敏感红线：家庭经济明细**不写本地存储/缓存**，仅内存态展示（对标审计 L451）。

**教师端**（辅导员，可写有限）：
- 班级评议录入简表（评议意见/建议等级/参评人数）+ 审批待办直达。
- 长表单/终审/导出/统计仍回 PC（对标 C：移动录评议、PC 管理台账）。

**只读/可写口径**：学生仅本人可写；辅导员移动端限本班、仅评议录入+初审待办，**不代终审、不看跨班家庭经济明细**。

---

## 12. 验收标准（页面级用例）

每个三级页必须通过：

1. **进入**：6 个三级页均可从侧栏进入，无空白页、无假按钮；planned 让位后 navPlan 叶子改 `I(label, path)`。
2. **旧路由兼容**：旧一级 `/admin/student*` 入口不 404（redirect/alias）；**需人工确认**旧困难补助入口指向。
3. **权限**：无 `studentAffairs.aid.*` 对应权限点的角色，端点返回 403（后端校验，非前端隐藏）；心理老师/宿管访问困难数据→403。
4. **数据范围**：辅导员只见本班申请与困难生；学院只见本院；跨学院审→403 NO_DATA_SCOPE；班主任见名单**不含家庭经济明细**。
5. **脱敏**：列表/详情/公示家庭经济默认脱敏；收入显区间档；公示名单不含金额/致困明细。
6. **审计**：`/reveal` 查看完整家庭经济必填原因并落 SENSITIVE_VIEW 审计；无原因被拒；导出落 `t_export_task`。
7. **三态**：每列表页 loading / empty / error / no-permission / network-error 五态齐备（CLAUDE.md §17）。
8. **导出带水印**：sensitiveView 导出强制水印 + 二次确认；文件名含模块+租户+时间。
9. **状态机**：批次未开放/已截止提交→409；同批次重复→409；越级审→409；REJECTED 后调整→409。
10. **闭环真实**：申请→评议→三级审→公示→入库全流程可跑通，数据刷新后仍在；困难库等级与 level_history 有效行 0 差异；统计数与下钻明细对账 0 差异。
11. **无控制台错误**、无 mock 写成功、无未接后端的假交互。

---

## 13. 依据文档索引（每条关键结论标来源）

| 结论 | 来源文件 + 章节/行号 |
|---|---|
| §0.0 十点对标结构 | `CLAUDE.md` §0.0（系统指令） |
| 三家对标（正方/强智/青果）+ 15 精华 + 缺口表 | `13A-学工中心-商业化对标审计与补丁建议（第一轮）.md` L6/L73–103/L118（困难行）/L148（逐模块第6条） |
| 状态机 13 态 + 转移 + 防护 + 超时 | `13A-学工中心状态机与权限矩阵.md` §2（L90–130） |
| 权限点 7 个 + 8 角色矩阵 + 数据范围 | 同上 §14（L489–496、L565） |
| 表单字段 + 校验 + 脱敏 + 422 | `13A-学工中心表单字段与校验规则.md` §3.4（L184–203）+ 敏感清单 L445/致困枚举 L460–466 |
| 全流程 ①–⑰（角色/前置/主流程/字段/审批码/统计/入口/模块关系） | `13A-学工中心全业务流程设计总册.md` §3.6（L359–403） |
| 页面树 8 页（06-1…06-8）+ 路由 | `13A-学工中心页面树与路由设计.md` §3.4（L218–229、L80–88）+ 流程 §4.3（L366–377） |
| navPlan 6 三级叶子 planned·待施工 | `frontend/src/config/navPlan.js` L136–138 |
| 施工图困难认定 = C 包·P1·部分完成 | `13A-学工中心全量规划施工图.md` L36、L134–141 |
| 后端 4 表模型 | `backend/app/models/affairs_aid.py`（AidBatch/AidApply/AidFamilyEconomy/AidLevelHistory） |
| 后端服务主干（批次/申请/review/公示/调整/困难库/脱敏揭示） | `backend/app/services/affairs_aid_service.py` |
| 后端 12 端点 + 入参模型 | `backend/app/api/v1/student_affairs.py` aid 段（L299–410） |
| 移动端我的认定 | `backend/app/api/v1/mobile.py` L608–610 |
| Excel 公共底座存在 | `backend/app/services/excel/` + `frontend/src/components/common/excel/` |
| 权限四层校验 + 数据范围机制 | `docs/03-业务模块设计/系统管理中心/00-系统管理中心-权限角色模块授权与权责边界设计.md` L5/L70 |
| 关联索引（C 包施工卡 + 前端目标目录） | `13A-学工中心/文档关联索引.md` L14 |

**需人工确认清单**（仓库无一手依据，不得写成确定结论）：
1. 三家产品的**具体内部字段/接口名**（本卡仅对标业务成熟度，未抄字段）。
2. 后端 aid 端点是否已挂**细粒度权限点 + 真实数据范围**（现见 `require_staff`，判定为欠账）。
3. `t_affairs_aid_class_review` / `t_affairs_aid_objection` 是否需建、迁移版本号。
4. 年度复核批量任务、批次截止定时提醒是否已实现。
5. 前端申请入参字段契约（后端 `AidApplyBody` 与表单 §3.4 字段名不完全一致）。
6. 等级枚举中英对照（SPECIAL/DIFFICULT/GENERAL ↔ A特困/B困难/C一般）是否全站统一。
7. 认定统计 `/aid/stats`、导出 `/aid/export`、导入模板是否已有。
8. 旧「在校服务-困难补助」入口是否需 redirect 到本模块。

---

## 14. 施工顺序与依赖

**前置模块 / 复用**：
- **公共组件底座**（CLAUDE.md §40/§41）：`AppApprovalPanel`（审批）、`AppWorkflowTimeline`（流转）、`AppFilePreview`（材料）、`AppSensitiveText`（脱敏）、`AppExportButton`+`AppExportConfirm`（导出）、`AppAuditTrail`（审计）、`AppStatusTag`、`AppExcelImportDrawer`、`AppStudentPicker`、`AppPageShell`/`AppToolbar`/`AppForm`——**必须复用，不自写**。
- **数据范围函数** `getStudentAffairsScope` / `resolve_teacher_scope`（后端）。
- **困难库下游**：奖助勤贷补（`sa-aid`）通过 `is_in_difficult_library()` 引用，**与本模块同批施工**（施工图 L36–37：与奖助一起施工）。

**建议施工顺序（做完一个亮一个，navPlan 逐叶转 `I`）**：
1. **前端脚手架**：建 `frontend/src/views/admin/student-affairs/aid/` + 路由 + 面包屑高亮（按 CLAUDE.md §9.4 leafKey 唯一高亮铁律实测）。
2. **认定批次**（06-1/2）：列表 + 详情配置，接已落地 `/aid/batches`。
3. **认定申请 + 认定审核**（06-3/4/5）：列表（脱敏）+ 详情 + 审核（`AppApprovalPanel`），接 review/resubmit/reveal。**敏感揭示 + 审计**是本步验收重点。
4. **公示与异议**（06-6）：脱敏公示名单 + `scan-publicity`/`publicity-confirm`；**异议单闭环为缺口**（先落 t_affairs_aid_objection 或线下+备注，标 partial）。
5. **困难学生库**（06-7）：difficult-students 列表（脱敏+水印）+ 导出（接 Excel 底座）。
6. **认定统计**（06-8）：需**先补后端 `/aid/stats`**，再建前端下钻页。

**风险点**：
- **R1（B 级，上线前必补）**：后端 `require_staff` 粗鉴权 → 越权风险；施工时同步升级细粒度权限点 + 数据范围，登记历史欠账。
- **R2（合规红线）**：家庭经济脱敏/审计/公示脱敏若做漏即合规事故；每个涉敏页必过 §7 检查。
- **R3（数据留痕）**：班级评议无独立表 → 评议合规留痕不足；建议补 `t_affairs_aid_class_review`。
- **R4（字段契约）**：前后端申请入参字段名不一致 → 联调前先对齐契约（需人工确认）。

**建议 commit 粒度**（小步、可回滚，CLAUDE.md §15）：
1. `docs: 困难认定施工卡`（本卡，纯文档）
2. `feat(sa-difficulty): 前端脚手架+路由+批次页`
3. `feat(sa-difficulty): 申请列表/详情/审核（脱敏+审计）`
4. `feat(sa-difficulty): 公示+困难库+导出（Excel底座）`
5. `feat(sa-difficulty): 认定统计（含后端 /aid/stats）`
6. `fix(sa-difficulty): aid 端点接细粒度权限点+数据范围（销 R1 欠账）`

每完成一叶：navPlan 对应 `P(...)` 叶改 `I(label, path)`，侧栏实测（当前页只亮一叶、跨页点击真跳转+渲染），并更新 `docs/施工记录/历史欠账.md`。

---

> 本卡为**只读设计产物**，未改任何代码/navPlan/配置/迁移。开发前请重读 CLAUDE.md §0.0 与本卡 §13 需人工确认清单，凡标「需人工确认」处先与甲方对齐再落地，不得凭本卡臆造为既成事实。
