# 13A/13B Opus 开发输入包目录（逐阶段任务书索引）

> 文档性质：交给开发 AI（Opus/Cursor 等）的逐阶段输入包目录——每个阶段一节，规定：阶段目标 / 必须读取文档 / 允许修改范围 / 禁止修改范围 / 验收命令 / 验收标准 / 提交白名单。
> 阶段编号：本文件采用 13A-P0…P8、13B-P0…P8（P0=契约冻结）。与既有《开发阶段与验收用例》《V1范围与开发顺序》中的 P1…P9（13A）/ P1…P8（13B）存在**编号偏移**：本文件 13A-Pn = 旧文档 13A-P(n+1)；本文件 13B-P0=旧 P1、P1≈旧 P2 前半+首页、P2≈旧 P2 后半（异动）+旧 P3 方案基础、P3≈旧 P3 课程库+旧 P4 教学任务、P4≈旧 P4 课表+调停课基础、P5=旧 P5、P6=旧 P6、P7=旧 P7、P8=旧 P8。任务卡与验收用例仍以旧文档编号引用，映射以本节为准。
> 命名口径：13B 一律 academic-affairs / academicAffairs / t_aa_*（详见《13A-13B-数据表与迁移策略草案》第二章）；旧文档中 academic-affairs / t_aa_* 按对照表理解。

---

## 0. 文档底册（全部输入文件的唯一编号索引，以下各阶段按编号引用）

**公共必读（每个阶段开工前必须完整读取）**：

| 编号 | 文件（相对项目根） |
|---|---|
| C1 | docs/modules/_13-现有系统集成事实速查.md |
| C2 | docs/modules/_13-需求输入-V1.1.md |
| C3 | docs/modules/13A-13B-数据表与迁移策略草案.md（表结构唯一基线） |
| C4 | docs/modules/13A-13B-V1范围冻结表.md（范围唯一基线） |
| C5 | docs/database/00-数据库设计冻结总册.md（公共字段/横切表/枚举原则） |

**13A 专属文档（A 组，docs/modules/）**：

| 编号 | 文件 |
|---|---|
| A1 | 13A-学工中心全业务流程设计总册.md |
| A2 | 13A-学工中心与现有系统融合设计.md |
| A3 | 13A-学工中心V1范围与开发顺序.md |
| A4 | 13A-学工中心页面树与路由设计.md |
| A5 | 13A-学工中心状态机与权限矩阵.md |
| A6 | 13A-学工中心API契约草案.md |
| A7 | 13A-学工中心表单字段与校验规则.md |
| A8 | 13A-学工中心页面级交互与按钮动作矩阵.md |
| A9 | 13A-学工中心移动端入口设计.md |
| A10 | 13A-学工中心开发阶段与验收用例.md |

**13B 专属文档（B 组，docs/modules/）**：

| 编号 | 文件 |
|---|---|
| B1 | 13B-教务中心全业务流程设计总册.md |
| B2 | 13B-教务中心与现有系统融合设计.md |
| B3 | 13B-教务中心V1范围与开发顺序.md |
| B4 | 13B-教务中心页面树与路由设计.md |
| B5 | 13B-教务中心状态机与权限矩阵.md |
| B6 | 13B-教务中心API契约草案.md |
| B7 | 13B-教务中心表单字段与校验规则.md |
| B8 | 13B-教务中心页面级交互与按钮动作矩阵.md |
| B9 | 13B-教务中心移动端入口设计.md |
| B10 | 13B-教务中心开发阶段与验收用例.md |

**source-design 参考件（S 组，docs/source-design/，按阶段选读）**：

| 编号 | 文件 |
|---|---|
| S1 | 00-职校学生全生命周期SaaS平台开发冻结总册 V3.0-增强版.md |
| S2 | 00-全端UI视觉与交互设计规范 V2.1 最终冻结版.md |
| S3 | 01-学生主档与身份中心深化设计.md |
| S4 | 02-数字迎新中心深化设计 V1.0.md |
| S5 | 03-在校服务中心深化设计 V1.0.md |
| S6 | 04-学业过程中心深化设计 V1.0.md |
| S7 | 08A-学生小程序中心.md |
| S8 | 08B《教师移动工作台中心》.md |
| S9 | 09A-PC管理端中心多角色工作台补充修订 V1.1.md |
| S10 | 10-数据驾驶舱中心框架级深化设计 V1.0.md |
| S11 | 11-权限与流程中心深化设计 V1.0.md |

**通用验收命令（每阶段收尾必须全绿，各阶段只列增量专项）**：

```bash
# 后端：全量测试（基线 203 条 + 历史阶段新增，一条不许红）
cd backend && python -m pytest tests -q
# 前端 PC：lint + 构建
cd frontend && npm run lint && npm run build
# 小程序：H5 与微信双构建 + 编译自检
cd miniapp && npm run build:h5 && npm run build:mp-weixin && node check-compile.mjs
```

**通用禁止修改范围（全部 18 个阶段一体适用，逐条来自 C1）**：
- 统一响应体/错误码常量、认证与租户中间件、demo-school 只读锁、sandbox 重置机制；
- 既有六域表结构与既有 API 响应结构（仅允许 C3 列明的 nullable 加列，且只在对应阶段）；
- t_workflow_instance/t_workflow_task/t_unified_todo/t_unified_message/t_file_object/t_export_task/t_security_audit_log 表结构；
- resolve_teacher_scope / scope_match_row / can_teacher_view_student 既有行为（只允许新增 scope_type 枚举值）；
- miniapp 请求层（realFirst/401 单飞/提交锁）与 MobileGlobalState/MobileSensitiveText 组件本体；
- 既有 pytest 用例文件（不许改断言过测试）。

**通用提交白名单外的"共改点"**（允许小 diff、单独 commit、diff ≤ 30 行/次）：`backend/app/api/v1/router.py`（路由注册）、`backend/app/api/v1/mobile.py`（移动端点追加）、`backend/app/api/v1/stats.py` 与 `backend/app/services/`（stats 聚合扩展）、域导入导出 domain 注册点、`frontend/src/router` 注册、`miniapp/src/pages.json`。

---

## 1. 13A 学工中心（P0–P8）

### 13A-P0 融合契约冻结（对应旧 A3/A10 的 P1）

- **阶段目标**：只出契约不出功能。冻结 13A 全部 API 契约、26 张新表 DDL（含索引/唯一键）、t_cs_leave 加列清单、状态机转移表、15 个 AFFAIRS_* workflow_code/node_code、权限点全集（studentAffairs.*）、8 种消息类型使用映射、统计口径卡、导出 domain、平台规则键与默认值。
- **P0 特别项（第一任务，先于一切契约条目执行）**：命名统一核对——确认 13A 侧文档无 academic-affairs / t_aa_* 残留引用；13A 请假口径已冻结为 **t_cs_leave 加列扩展 + 必要子表**（C3 §3.1），A2/A6/A10 等文档中旧的 `t_affairs_leave_request` 写法已全部替换。
- **必须读取**：C1–C5 全部；A1、A2、A3、A5、A6（核心）；A4、A7、A8、A9、A10（页面/字段/动作/移动/用例全量索引）；S1、S3、S5、S11（学生主档/在校服务/权限流程底层）。
- **允许修改范围**：仅 `docs/modules/`（新增 13A 契约冻结文档 + 勘误记录）。
- **禁止修改范围**：全部代码目录（backend/frontend/miniapp 零改动）；不新建数据库对象。
- **验收命令**：通用三条（证明零代码改动不破坏基线）+ `cd backend && git status --porcelain`（预期仅 docs 变更）。
- **验收标准**：契约文档覆盖每接口出入参、每状态机转移表（谁在什么状态可做什么、退回回到哪）、每表逐列与 C3 一致；与 C1 §1–§11 逐条对照无冲突；A2 红线 8 条对照通过；三方（后端/前端/QA）签认打冻结标记。
- **提交白名单**：`docs/modules/**`。

### 13A-P1 首页与工作台（旧 P2）

- **阶段目标**：学工首页三角色视图 + 辅导员工作台 + 班级管理骨架上线，只聚合既有六域数据（13A 自有业务卡空态），先验证 scope 与角色 preset 机制。
- **必须读取**：C1、C3、C4；A3（P2 节）、A4（首页/工作台/班级路由）、A6（dashboard/workbench/classes 契约）、A8（对应页面动作矩阵）、A10（P2 任务卡与用例）；S9（PC 多角色工作台）、S10（驾驶舱指标模式）、S2（UI 规范）。
- **允许修改范围**：`backend/app/api/v1/student_affairs.py`（新建）、`backend/app/services/affairs_dashboard_service.py`（新建）、`backend/app/models/affairs.py`（仅 t_affairs_class_cadre）、`backend/alembic/versions/`（本阶段 revision）、`backend/tests/test_affairs_dashboard.py`、`frontend/src/modules/studentAffairs/**`（api/routes/views）、共改点（router.py/前端路由注册）。
- **禁止修改范围**：通用禁改项；不做任何 13A 业务写操作端点；不改 stats 既有四端点行为；不建 cadre 之外的 t_affairs_* 表。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_dashboard.py -q`。
- **验收标准**：三角色（学工处/学院学工/辅导员）dashboard 结构与 scope 差异用例过；辅导员跨班 403+审计；13 模块卡全渲染且未上线业务空态；demo-school 可读。
- **提交白名单**：`backend/app/api/v1/student_affairs.py`、`backend/app/services/affairs_*.py`、`backend/app/models/affairs.py`、`backend/alembic/versions/*`、`backend/tests/test_affairs_*.py`、`frontend/src/modules/studentAffairs/**` + 共改点。

### 13A-P2 请假销假闭环（旧 P3，流程范式阶段）

- **阶段目标**：请假/审批/销假/续假/逾期全链路，落地"范式五件套"（状态机+workflow 建流+待办消息+360 沉淀+统计点亮）；执行 t_cs_leave 加列 + 存量 backfill + 双状态列并行（C3 §3.1/§5.2/§5.3）。
- **必须读取**：C1、C2（§2.5）、C3（§3.1+§5 全部）、C4；A2（§5.1 请假融合+§2.3 workflow 表）、A5（请假 14 态与权限）、A6（leave 族契约）、A7（请假表单校验）、A8（请假 8 页动作）、A9（学生请假 5 页）、A10（P3 任务卡+用例 L1-L8）；S5（在校服务现状）、S7（小程序机制）、S8（教师移动审批）。
- **允许修改范围**：13A 白名单目录 + `miniapp/src/pages/student/affairs/**`（leave 5 页）+ `backend/scripts/`（backfill 脚本 `_migrate_cs_leave.py`，dry-run 默认）+ campus_service 请假端点的**内部转发实现**（`backend/app/api/v1/campus_service.py` / `backend/app/services/campus_service_service.py`，响应结构不变）。
- **禁止修改范围**：通用禁改项；不删 t_cs_leave 任何既有列与旧 API 路径；不自建审批/消息表；不做家长短信。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_leave.py tests/test_campus_service.py -q` + `cd backend && python scripts/_backfill_cs_leave_affairs_status.py --dry-run`（对账 0 差异）。
- **验收标准**：14 态转移矩阵用例全过（非法转移 409/422）；重复提交 409；跨学生 403/404；天数阈值经规则中心改值即生效；逾期→OVERDUE→风险占位记录→辅导员待办；小程序提交→移动审批→销假→CLOSED→360 时间线→首页卡变化全链演示；旧读端点回归绿。
- **提交白名单**：同 P1 白名单 + `miniapp/src/pages/student/affairs/**`、`backend/scripts/_migrate_cs_leave.py`、`backend/app/api/v1/campus_service.py`、`backend/app/services/campus_service_service.py` + 共改点（mobile.py）。

### 13A-P3 困难认定与奖助基础（旧 P4，敏感数据范式阶段）

- **阶段目标**：困难认定批次全流程（12 态+公示定时流转）+ 困难库聚合 + 奖学金/助学金申请评审公示；家庭经济强敏感管线（独立表+看完整审计+导出水印列剔除）。
- **必须读取**：C1（§3 敏感/§8 导入导出）、C2（§2.6/§2.7）、C3（§3.3/§3.4）、C4；A5（认定/奖助状态机与敏感矩阵）、A6（aid/funding 族）、A7（认定与奖助表单）、A8、A9（aid/funding 3 页）、A10（P4 任务卡+用例 A1-A5/S1-S5+敏感四连测）；S3（家庭信息敏感原则）、S7。
- **允许修改范围**：13A 白名单目录 + `miniapp/src/pages/student/affairs/**`（aid/funding 页）+ 导出 domain 注册共改点。
- **禁止修改范围**：通用禁改项；不做勤工/贷款/减免/临补/绿通；不做推荐算法；列表接口禁回家庭经济数字。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_aid.py tests/test_affairs_funding.py -q`。
- **验收标准**：一批次创建→申请→三级评审→公示（定时流转幂等）→APPROVED→ARCHIVED 全程；困难库供助学金前置校验；奖学金四类校验 422/409；敏感四连测（默认脱敏/越权 403+审计/查看完整审计落表/导出列剔除+水印）全过；360 出认定与获奖记录。
- **提交白名单**：同 P2 模式（affairs 相关 + miniapp affairs 页 + 共改点）。

### 13A-P4 处分与风险预警（旧 P5）

- **阶段目标**：处分登记→生效→解除全流程 + t_cs_discipline 投影同步（事务内）；风险预警中枢（五来源接入/分派/处置/升级/关闭/重开 + 超时升级扫描幂等）。
- **必须读取**：C1（§6 表级衔接）、C2（§2.8/§2.9）、C3（§3.5/§3.6）、C4；A2（§5.3–§5.6 各域来源融合）、A5（处分 11 态/风险 8 态）、A6（discipline/risk 族）、A8、A10（P5 任务卡+用例 D1-D5/R1-R5+投影对账）；S6（学业预警现状）、S8（教师移动处置）。
- **允许修改范围**：13A 白名单目录 + `miniapp/src/pages/teacher/**`（risk-handle 处置页）+ mobile.py 共改点；t_cs_discipline 加列（source_case_id）revision。
- **禁止修改范围**：通用禁改项；不改 t_cs_discipline 既有列/t_acad_warning 结构（13B 负责其加列）/实习域表；不做行为大数据预警；处分不联动德育积分。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_discipline.py tests/test_affairs_risk.py -q`。
- **验收标准**：登记→学院→学工处→EFFECTIVE→投影行一致→送达通知→360→解除→REMOVED 全链；投影一致性对账（EFFECTIVE case 数=ACTIVE 投影行数）；五来源风险各一条全部走到 CLOSED；(source,source_ref_id) 唯一防重复；心理来源明细对普通教师隐藏；学生端处分数量接口回归绿。
- **提交白名单**：同 P2 模式 + `miniapp/src/pages/teacher/**`。

### 13A-P5 谈话与 360 沉淀（旧 P6）

- **阶段目标**：谈心谈话全流程 + 学生画像/时间线聚合端点补全 + 家校联系（完整号码审计）——集中兑现 P2–P4 全部"进 360"承诺。
- **必须读取**：C1（§6 学生360现状）、C2（§2.3/§2.10/§2.13）、C3（§3.7）、C4；A4（画像/谈话/家校路由）、A6（talk/family/profile/timeline 族）、A8、A9（talk-record 速记页）、A10（P6 任务卡+用例 T1-T5+兼容快照）；S3（主档聚合）、S8。
- **允许修改范围**：13A 白名单目录 + `backend/app/services/mobile_teacher_service.py`（student/{id} 聚合追加 affairs 节点，既有节点结构不动）+ miniapp teacher 页。
- **禁止修改范围**：通用禁改项；不改聚合端点既有六域节点结构（快照对比零破坏）；敏感明细不写入 timeline 摘要；不做家长端。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_talk.py tests/test_mobile.py -q`。
- **验收标准**：工作台点开任一学生→画像八区块+时间线倒序合并（StageEvent+域事件）完整呈现 P2–P4 沉淀；谈话转风险/转家校联动；完整号码查看必填原因+审计；心理类谈话仅授权可见；聚合端点向后兼容快照 0 差异。
- **提交白名单**：同 P4 模式 + `backend/app/services/mobile_teacher_service.py`（小 diff 单独 commit）。

### 13A-P6 宿舍基础与归档（旧 P7）

- **阶段目标**：房源台账（楼/房/床）+ 迎新分宿初始化导入（dry-run 对账）+ 调宿流程（床位占用校验+t_cs_dorm_record 回写）+ 宿舍检查（异常→风险）+ 学工归档批次（水印包+t_export_task 登记）。
- **必须读取**：C1（§6 宿舍/迎新、§8 导出）、C2（§2.11/§2.14）、C3（§3.8/§3.9+§5.2 宿舍初始化）、C4；A2（§5.2 迎新融合）、A5（调宿/检查/归档状态机+DORM_BUILDING scope）、A6（dorm/archive 族）、A8、A9（dorm 2 页）、A10（P7 任务卡+用例 M1-M5/V1-V4+床位对账）；S4（迎新分宿数据）。
- **允许修改范围**：13A 白名单目录 + miniapp student affairs（dorm 2 页）+ `backend/scripts/_init_dorm_from_orientation.py` + 导入 domain 注册共改点 + teacher_scope 枚举新增（DORM_BUILDING）。
- **禁止修改范围**：通用禁改项；不做智能排宿/文明寝室评比；不动迎新历史数据；归档不物理删除业务数据。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_affairs_dorm.py tests/test_affairs_archive.py -q` + `python scripts/_init_dorm_from_orientation.py --dry-run`。
- **验收标准**：床位视图与 t_cs_dorm_record 对账 0 差异；目标床位已占 409；调宿通过后原床释放/新床占用/回写一致；检查异常→t_cs_dorm_exception→风险单；归档批次到水印包下载全程，sha256 落 t_export_task，审计链完整。
- **提交白名单**：同 P3 模式 + `backend/scripts/_init_dorm_from_orientation.py`。

### 13A-P7 多端入口（旧 P8）

- **阶段目标**：学生端 13A 页面全量收口（leave×5/aid×2/funding×1/dorm×2）+ 教师移动工作台卡片补全 + 双演示租户种子扩展（sandbox reset 覆盖 13A 表）。
- **必须读取**：C1（§9 前端事实）、C4；A9（全量移动清单，核心）、A4（跳转链路）、A8（按钮矩阵终验）、A10（P8 任务卡+错误分支清单）；S7、S8（小程序/教师端机制）。
- **允许修改范围**：`miniapp/src/pages/student/affairs/**`、`miniapp/src/pages/teacher/**`、`miniapp/src/pages.json`、`backend/scripts/_seed_affairs*.py`、`backend/scripts/reset_sandbox_school.py`（追加 13A 表清理与种子，dry-run 保护不动）。
- **禁止修改范围**：通用禁改项；不开学生 PC 门户；不为小程序另开非 mobile 前缀端点；不加 mock 兜底；后端业务端点冻结（仅修缺陷）。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests -q`（全量）+ `python scripts/reset_sandbox_school.py --dry-run`。
- **验收标准**：401/403/409/422 分支逐页符合请求层标准；提交锁防连点；demo 账号写 403 引导沙箱文案；sandbox 重置后 13A 种子完整（含各状态存量单据）；双租户演示话术（A3 §10）全程走通。
- **提交白名单**：`miniapp/src/**`、`backend/scripts/**`（种子/重置）。

### 13A-P8 测试验收（旧 P9）

- **阶段目标**：全量回归 + A10 第二部分验收用例 100% 执行 + 状态机非法转移矩阵扫描 + 权限矩阵抽测 + 上线检查单；契约偏差清零或评审豁免。
- **必须读取**：A10（全文，验收唯一依据）、C3（§5.3 对账口径）、C4（红线清单）、A3（§5 门禁/§10 演示脚本）。
- **允许修改范围**：仅缺陷修复（涉及文件按缺陷单逐一授权）+ `backend/tests/**`（补用例）。
- **禁止修改范围**：不加功能；不为过测试放宽校验/删断言；不跳过失败用例。
- **验收命令**：`cd backend && python -m pytest tests -q`（全量含并发审批 409/导出限流 429 用例）+ 通用前端/小程序构建 + 对账脚本（请假投影/处分投影/床位三项）。
- **验收标准**：验收用例通过率 100%；回归红线三项（既有 pytest 全绿/demo 只读锁/教师范围机制）零违反；列表接口 P95<500ms（种子量级）；t_cs_leave 双状态列对账 0 差异；偏差记录清零或豁免签认。
- **提交白名单**：`backend/tests/**` + 缺陷单授权文件。

---

## 2. 13B 教务中心（P0–P8）

### 13B-P0 契约冻结（对应旧 B3/B10 的 P1）

- **阶段目标**：只出契约不出功能。冻结七份清单：①17 张 t_aa_* DDL + 4 表加列（对照 C3 第四章）；②OpenAPI 草案（**13B 新建** `/api/v1/academic-affairs/*` + `/api/v1/mobile/academic-affairs/*`；**复用既有** `/api/v1/academic/*` 学业过程端点标注不动）；③与既有 /api/v1/academic 端点冲突盘点表（B2 §5.6 为底稿）；④14 个 ACAD_* workflow_code/node_code + on_approved 回调职责；⑤academicAffairs.* 权限点全集与角色矩阵；⑥规则中心 10 键默认值 + 导出 domain 4 项；⑦stats 11 指标口径卡。另：203 条 pytest 基线清单与既有 /academic、/mobile/academic/my 响应快照建档。
- **P0 特别项（第一任务，先于一切契约条目执行）**：**命名统一替换**——按 C3 §2.3 对照表，把 13B 契约产出物中全部 `academic-affairs`→`academic-affairs`（PC 路由/前端目录/权限点前缀/center-dashboard→affairs-dashboard/center-audit-logs→affairs-audit-logs）、`t_aa_*`→`t_aa_*` 完成文档层替换；对 B1–B10 逐文件生成"旧写法→新写法"勘误对照附录（不回改历史文档正文）；替换完成并签认后才允许冻结其余契约条目。
- **必须读取**：C1–C5 全部；B1、B2、B3、B5、B6（核心）；B4、B7、B8、B9、B10（全量索引）；S1、S3（主档/学籍）、S6（学业过程现状）、S11（权限流程）。
- **允许修改范围**：仅 `docs/modules/`（13B 契约冻结文档 + 勘误对照附录）。
- **禁止修改范围**：全部代码目录；不预占 C3 之外的表名；不单方面变更与 13A 共用的公共契约（消息类型/scope_type/规则中心）。
- **验收命令**：通用三条（证明零代码改动）+ `git status --porcelain`（仅 docs）。
- **验收标准**：七份清单齐备且与 C1 逐条无冲突；t_acad_*/t_aa_* 职责划分表三方签认；命名替换勘误附录覆盖 B 组全部 10 份文档；快照与基线建档完成。
- **提交白名单**：`docs/modules/**`。

### 13B-P1 首页与学年学期/学籍（旧 P2 前半 + 首页）

- **阶段目标**：教务首页四角色视图（affairs-dashboard）；时间轴基座（t_aa_term/t_aa_calendar_event/t_aa_time_slot）；学籍名册（读主档+脱敏+导入 domain=academic-roster）；入学/学年注册（t_aa_registration_batch/t_aa_registration，读 orientation 供数）；`change_student_status()` 单一写入口上线（本阶段仅注册类 change_type）。
- **必须读取**：C1、C2（§3.1–§3.3）、C3（§4.1/§4.2）、C4；B2（§1 学籍融合+§5.5 迎新取数）、B4（首页/学期/学籍/注册路由）、B5（学期/注册状态机）、B6（terms/roster/registrations 契约）、B7（对应表单）、B10（P2 任务卡前半）；S3（主档）、S4（迎新数据）、S9（PC 工作台）、S10（指标）。
- **允许修改范围**：`backend/app/models/academic_affairs.py`（新建）、`backend/app/api/v1/academic_affairs.py`（新建）、`backend/app/services/academic_affairs_*.py`（新建，含 change_student_status）、`backend/alembic/versions/`、`backend/tests/test_aa_*.py`、`frontend/src/modules/academicAffairs/**`、导入 domain 注册与 router.py 共改点。
- **禁止修改范围**：通用禁改项；任何代码直接 UPDATE student_status（必须经单一入口，Code Review 红线）；不写 current_stage；不建 roster 表；不发明新消息类型。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_term.py tests/test_aa_registration.py -q`。
- **验收标准**：学期发布后首页/校历即时生效且重复发布幂等；种子学生"迎新完成→注册→在籍"五处（主档/StageEvent/待办/消息/统计）正确；学籍导入 dry-run 行级错误可复现、确认整批事务；全库 student_status 硬编码引用清单建档，"在籍判定"工具函数提供。
- **提交白名单**：`backend/app/models/academic_affairs.py`、`backend/app/api/v1/academic_affairs.py`、`backend/app/services/academic_affairs_*.py`、`backend/alembic/versions/*`、`backend/tests/test_aa_*.py`、`frontend/src/modules/academicAffairs/**` + 共改点。

### 13B-P2 学籍异动与方案基础（旧 P2 后半 + P3 方案骨架）

- **阶段目标**：四类异动全链路（t_aa_status_change + ACAD_STATUS_* 五流程 + 单一入口全量 change_type）；组织三表加列维护页；培养方案基础骨架（t_aa_program/program_course/program_binding 建表 + 编制页雏形，审批发布留到 P3 一并联调）。
- **必须读取**：C1（§4 Workflow）、C2（§3.3/§3.4）、C3（§4.2/§4.3）、C4；B2（§1.5 时序 B+§2 workflow 表）、B5（异动/方案状态机）、B6（status-changes/orgs/programs 契约）、B7（异动动态表单）、B8、B10（P2 任务卡后半）；S11（审批组件）。
- **允许修改范围**：13B 白名单目录（同 P1）+ `miniapp/src/pages/student/academic/status*`（异动发起，可与 P7 合并交付）。
- **禁止修改范围**：通用禁改项；MERGED/RECYCLED 学生异动必须 422；转专业不改 student_status 字面（仅 change_type）；不实现排课/成绩逻辑。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_status_change.py -q`。
- **验收标准**：休学/复学/转专业/退学四类全链路（通过/驳回/退回重提）；重复发起与审批版本冲突 409；异动 EFFECTIVE 后"在籍判定"返回 false、各域入口冻结用例过；跨租户 404/非 scope 403/demo 只读 403；组织三表存量行零破坏。
- **提交白名单**：同 P1 + `miniapp/src/pages/student/academic/**`。

### 13B-P3 课程库与教学任务（旧 P3 课程库 + P4 教学任务）

- **阶段目标**：课程库两级审核（t_aa_course + ACAD_COURSE_APPROVE）；培养方案编制→两审→发布→绑定年级全链路（ACAD_PROGRAM_PUBLISH，版本规则：发布后改动强制新版本、历史年级锁旧版）；教学任务批次生成→分配→教师确认→提交审核（t_aa_teaching_task_batch/teaching_task + ACAD_TASK_CONFIRM，generate 幂等）。
- **必须读取**：C2（§3.4–§3.6）、C3（§4.3/§4.4 前半）、C4；B2（§2 workflow）、B5（课程/方案/任务状态机）、B6（courses/programs/teaching-tasks 契约）、B7（编制页校验器规格）、B8、B10（P3/P4 任务卡）；S6（课程数据现状）。
- **允许修改范围**：13B 白名单目录 + 课程/方案导入 domain 注册共改点。
- **禁止修改范围**：通用禁改项；方案发布后原地改内容；课程绕审直接 ENABLED；方案内联自造课程；无教师任务提交（422）。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_course.py tests/test_aa_program.py tests/test_aa_teaching_task.py -q`。
- **验收标准**：一个专业"建 10 门课→审→启用→编方案→两审→发布→绑 2026 级→生成任务→分配→确认→审核"全链路；学分汇总校验实时 422 且编制页可见差额；A 学院负责人操作 B 学院 403；generate 重跑幂等。
- **提交白名单**：同 P1 模式。

### 13B-P4 课表查看与调停课基础（旧 P4 课表）

- **阶段目标**：课表项手工维护/导入双通道（同一冲突检测器）；班级/教师/学生三视图（学生按行政班服务端推导）；课表批次预发布→发布（通知师生）→导出水印；**调停课仅"基础"**：ACAD_SCHEDULE_CHANGE 编码与状态占位落契约、发布前撤回重排、发布后"作废批次重发"运维通道（留审计），不做流转审批。
- **必须读取**：C2（§3.7/§3.8）、C3（§4.4）、C4（调停课档位说明）、B2（§4 指标）、B5（课表批次状态机）、B6（schedule 族契约）、B8、B10（P4 任务卡）；S2（周历网格 UI）、S7/S8（移动课表）。
- **允许修改范围**：13B 白名单目录 + `miniapp/src/pages/student/academic/schedule*`、`miniapp/src/pages/teacher/my-schedule*` + 课表导入/导出 domain 共改点。
- **禁止修改范围**：通用禁改项；自动排课；调停课流转审批；发布后静默改课表项；学生视图前端拼接。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_schedule.py -q`。
- **验收标准**：冲突检测表驱动六组合（教师/班级/教室 × 手工/导入）全部拒绝且提示冲突对方；发布通知落 t_unified_message 断言；三视图数据一致；导出带水印落 t_export_task；作废重发通道审计可查。
- **提交白名单**：同 P2 模式 + miniapp 课表页。

### 13B-P5 成绩查看与预警（旧 P5）

- **阶段目标**：成绩读侧（/academic/grade-views 聚合 + 学生成绩单可见性矩阵 + 挂科清单下钻 360，零写入）；学业预警规则引擎（t_acad_warning 加 source_code/rule_code 两列 + 规则中心键 + 扫描幂等 + 复用既有处置全链路）。
- **必须读取**：C1（§6 学业预警）、C2（§3.11/§3.13）、C3（§4.5）、C4（不新增成绩写端点红线）；B2（§5.1 D1/D2 + §5.2）、B6（grade-views/warning-rules/scan 契约）、B10（P5 任务卡）；S6（t_acad_* 现状，核心）、S10（挂科率指标）。
- **允许修改范围**：13B 白名单目录 + t_acad_warning 加列 revision + `miniapp/src/pages/student/academic/grades*` + 规则中心键注册共改点。
- **禁止修改范围**：通用禁改项；新建预警表；写 t_acad_grade；改既有 warnings/grades 端点与响应结构；扫描绕过既有创建逻辑直插表。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_grade_view.py tests/test_aa_warning_scan.py tests/test_academic.py -q`（最后一项证明既有域回归绿）。
- **验收标准**：造数两门挂科→扫描→中级预警→待办/消息双落点→辅导员移动处置→关闭全链含 360；重复扫描不重复生成（student+source+term）；阈值改规则中心即生效；三处挂科数据一致；既有 warnings/grades 端点快照 0 差异。
- **提交白名单**：同 P2 模式。

### 13B-P6 毕业资格预审（旧 P6）

- **阶段目标**：审核批次（圈定/生成/预审均幂等）→七项供数三态判定（PASS/FAIL/UNKNOWN+证据引用，只读六域）→异常清单按责任人推待办→学院初审→教务终审（经单一入口写 student_status，强制二次确认）→三名单（毕业/结业/延毕）导出水印。
- **必须读取**：C1（§6 六域衔接）、C2（§3.14）、C3（§4.6）、C4；B2（§5.4 供数契约，核心）、B5（审核 10 态）、B6（graduation-audit 族）、B10（P6 任务卡+试跑要求）；S6（学分聚合）、13A 侧 A2 §5.1 处分投影口径（跨模块契约）。
- **允许修改范围**：13B 白名单目录 + 导出 domain 共改点。
- **禁止修改范围**：通用禁改项；要求六域改表供数；预审直接改各域数据；把 UNKNOWN 判成 FAIL；就业未填报默认卡审（默认提醒，规则开关）；发证书文书。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_aa_graduation_audit.py -q`。
- **验收标准**：全通过/供数异常/供数缺失/处分联动四类种子学生各 1 例；补齐实习归档后重审转 PASS（重跑幂等，结果覆盖非追加）；异常待办责任人路由断言（实习→指导教师/毕设→导师/处分→辅导员/欠费→学院教务员）；30 人批次 <60s；终审二次确认+append-only 审计。
- **提交白名单**：同 P2 模式。

### 13B-P7 多端入口（旧 P7）

- **阶段目标**：学生端五页（课表/成绩/学籍+异动申请/毕业进度/考试占位空态）+ 教师端我的课表，全部 realFirst 真数据；/academic/my 页仅加四个入口链接。
- **必须读取**：C1（§9）、C4；B9（移动全量清单，核心）、B6（mobile 契约）、B8（按钮矩阵）、B10（P7 任务卡）；S7、S8。
- **允许修改范围**：`miniapp/src/pages/student/academic/**`、`miniapp/src/pages/teacher/**`、`miniapp/src/pages.json`、既有 academic/my 页入口链接小 diff、`backend/app/api/v1/mobile.py` 共改点、`backend/scripts/_seed_academic_affairs*.py` + reset 脚本追加。
- **禁止修改范围**：通用禁改项；改 /mobile/academic/my 响应结构；学生端出现教师功能；绕过 mobile 前缀直调 PC 端点；本地缓存敏感字段。
- **验收命令**：通用三条 + `cd backend && python -m pytest tests/test_mobile.py tests/test_aa_mobile.py -q` + `python scripts/reset_sandbox_school.py --dry-run`。
- **验收标准**：五页四态齐备；异动连点仅一条+重放 409；学生 A 携 B 参数仍回本人或 403/404；401 单飞刷新；demo student 写 403 引导沙箱；异动全链路小程序发起→PC 三级审批→生效→小程序状态页与 360 同步；/academic/my 快照回归。
- **提交白名单**：`miniapp/src/**`、`backend/scripts/**` + mobile.py 共改点。

### 13B-P8 测试验收（旧 P8）

- **阶段目标**：全量回归 + B10 第二部分 11 流程 ≥52 条验收用例逐条签认 + 回归红线四项专项（既有 pytest/既有端点快照/demo 只读/教师范围）+ 演示数据固化（管理员主线+学生主线两条脚本）+ 规则中心逐键改值验证并复位。
- **必须读取**：B10（全文，验收唯一依据）、B3（§2.9 门禁/§2.10 演示策略）、C3（§5 迁移对账）、C4（红线清单）。
- **允许修改范围**：仅缺陷修复（按缺陷单授权）+ `backend/tests/**` 补用例 + 种子脚本修正。
- **禁止修改范围**：为过测试放宽校验/删断言；跳过越权与幂等用例；夹带新功能。
- **验收命令**：`cd backend && python -m pytest tests -q`（基线 203 + 13B 新增 ≥101 全绿）+ 通用前端/小程序构建 + sandbox 重置复跑主线。
- **验收标准**：回归红线零违反；验收用例 100%（含复测）；"注册→方案→任务→课表→成绩→预警→毕业预审"主线 2 轮演练通过；t_aa_* 全表纳入 demo 只读中间件核查清单与 reset 脚本（逐表勾选）。
- **提交白名单**：`backend/tests/**` + 缺陷单授权文件。

---

## 3. 输入包完成度总览

| 阶段 | 目标 | 必读清单 | 允许/禁止范围 | 验收命令 | 验收标准 | 提交白名单 | 状态 |
|---|---|---|---|---|---|---|---|
| 13A P0–P8（9 阶段） | ✅ | ✅（编号索引精确到文件） | ✅ | ✅ | ✅ | ✅ | 输入包就绪 |
| 13B P0–P8（9 阶段） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 输入包就绪 |

**开工顺序建议**：13A-P0 与 13B-P0 合并评审（共用 Workflow/待办/消息/scope/规则中心/导入导出公共附录一次冻结）→ 13A-P2 请假范式先行并评审通过后，13A-P3/P4 与 13B 各阶段方可动工（防止多套审批写法）→ 13A-P4（处分）先于 13B-P6（毕业预审读处分）完成，倒挂时 13B 按 t_cs_discipline.record_status 口径实现并留规则开关。

**给开发 AI 的三条元规则**：①任何实现与 C3/C4 冲突时停下来报偏差，不得自行取舍；②每阶段第一个 commit 必须是"读毕清单确认 + 契约复述"（不含代码）；③白名单外文件出现在 diff 中即视为阶段失败，共改点必须单独 commit 且 diff ≤ 30 行。

---

## 4. 阶段 × 文档矩阵（速查：某文档在哪些阶段必读）

●=必读全文；○=选读对应章节；C1–C5 全阶段必读不列。

| 文档 | A-P0 | A-P1 | A-P2 | A-P3 | A-P4 | A-P5 | A-P6 | A-P7 | A-P8 |
|---|---|---|---|---|---|---|---|---|---|
| A1 流程总册 | ● | ○ | ○ | ○ | ○ | ○ | ○ | — | — |
| A2 融合设计 | ● | — | ●(§5.1/§2.3) | ○ | ●(§5.3-5.6) | ○(§6) | ●(§5.2) | ○ | — |
| A3 V1范围与顺序 | ● | ●(P2节) | ●(P3节) | ●(P4节) | ●(P5节) | ●(P6节) | ●(P7节) | ●(P8节) | ●(§5/§10) |
| A4 页面树路由 | ● | ● | ○ | ○ | ○ | ● | ○ | ●(跳转链路) | — |
| A5 状态机权限 | ● | ○ | ●(请假14态) | ●(认定/奖助) | ●(处分/风险) | ○ | ●(调宿/检查/归档) | — | ●(矩阵扫描) |
| A6 API契约 | ● | ●(dashboard族) | ●(leave族) | ●(aid/funding) | ●(discipline/risk) | ●(talk/profile) | ●(dorm/archive) | ○ | — |
| A7 表单校验 | ○ | — | ●(请假) | ●(认定/奖助) | ○ | ○ | ○ | ○ | — |
| A8 按钮动作矩阵 | ○ | ● | ● | ● | ● | ● | ● | ●(终验) | — |
| A9 移动端入口 | ○ | — | ●(请假5页) | ●(aid/funding页) | ○(risk-handle) | ○(talk-record) | ●(dorm 2页) | ●(全量) | — |
| A10 阶段与验收用例 | ● | ●(P2卡) | ●(P3卡+L组) | ●(P4卡+A/S组) | ●(P5卡+D/R组) | ●(P6卡+T组) | ●(P7卡+M/V组) | ●(P8卡) | ●(全文) |

| 文档 | B-P0 | B-P1 | B-P2 | B-P3 | B-P4 | B-P5 | B-P6 | B-P7 | B-P8 |
|---|---|---|---|---|---|---|---|---|---|
| B1 流程总册 | ● | ○ | ○ | ○ | ○ | ○ | ○ | — | — |
| B2 融合设计 | ● | ●(§1/§5.5) | ●(§1.5/§2) | ●(§2) | ○(§4) | ●(§5.1/§5.2) | ●(§5.4) | ○(§6) | — |
| B3 V1范围与顺序 | ● | ●(P2节) | ●(P2节) | ●(P3/P4节) | ●(P4节) | ●(P5节) | ●(P6节) | ●(P7节) | ●(P8节/§2.9/§2.10) |
| B4 页面树路由 | ● | ● | ○ | ○ | ○ | ○ | ○ | ○ | — |
| B5 状态机权限 | ● | ●(学期/注册) | ●(异动/方案) | ●(课程/任务) | ●(课表批次) | ○(复用既有) | ●(审核10态) | — | ●(矩阵扫描) |
| B6 API契约 | ● | ●(terms/roster/registrations) | ●(status-changes/orgs) | ●(courses/programs/tasks) | ●(schedule族) | ●(grade-views/scan) | ●(graduation-audit) | ●(mobile族) | — |
| B7 表单校验 | ○ | ○ | ●(异动动态表单) | ●(编制校验器) | ○ | — | ○ | ○ | — |
| B8 按钮动作矩阵 | ○ | ● | ● | ● | ● | ● | ● | ●(终验) | — |
| B9 移动端入口 | ○ | — | ○(status页) | — | ○(schedule页) | ○(grades页) | ○(progress页) | ●(全量) | — |
| B10 阶段与验收用例 | ● | ●(P2卡) | ●(P2卡) | ●(P3/P4卡) | ●(P4卡) | ●(P5卡) | ●(P6卡) | ●(P7卡) | ●(全文) |

## 5. 每阶段统一退出自检清单（Exit Checklist，验收标准之外逐条勾选）

1. **四件套自检**：本阶段每个写操作均有 ①Workflow 或明确"不走审批"裁定 ②t_unified_todo/t_unified_message 落点 ③360 沉淀（StageEvent/域记录）或明确"不进 360"裁定 ④audit_log.record + 域 trail。
2. **错误码自检**：401001/403001/403002/404001/409001/422001/429001/400001 之外无新码；业务错误绝不 500。
3. **幂等自检**：本阶段全部 POST 写端点有防重复策略（唯一键/在途查重/client 幂等键），并有对应 409 用例。
4. **scope 自检**：新增列表/详情/写端点全部经 scope 函数；每端点至少一条越权 403 用例入 CI。
5. **租户自检**：新表全带 tenant_id；跨租户访问 404；demo-school 写 403；到期租户只读对新端点生效。
6. **敏感自检**：新增出口字段对照脱敏矩阵；导出列剔除+水印；"查看完整"必有原因+审计。
7. **回归自检**：`python -m pytest tests -q` 全绿；既有端点响应快照（13B 专项）0 差异；前端/小程序双构建通过。
8. **文档自检**：实现与契约偏差已登记；C3/C4 需要回写处已提交 docs 修订。
9. **种子自检**：demo/sandbox 种子增量已合入且 reset 脚本 dry-run 通过；不污染既有种子学生。
10. **白名单自检**：`git diff --name-only` 全部命中本阶段白名单或共改点清单。

## 6. 环境、账号与种子约定（演示与验收共用）

- **租户矩阵**：开发库自由写；demo-school（…003，中间件只读锁，验证只读 403 引导）；sandbox-school（…007，每晚 0 点重置，演示写操作）；trial/expired/disabled（…004/005/006）不加 13A/13B 种子，仅验证到期/禁用逻辑对新端点生效。
- **演示账号**（登录页明示，C1 §9）：demo-school admin/teacher/student·123456（只读）；sandbox-school admin2/teacher2/student2·123456（0 点重置）。
- **种子纪律**：13A/13B 不新造学生，为既有种子学生补挂业务数据；13A 种子含各状态存量单据（DRAFT/审批中/OVERDUE/CLOSED/ARCHIVED 至少各一）；13B 七类典型画像种子（全通过毕业生/两门挂科生/实习未归档生/老生无实习/ACTIVE 处分生/休学在途生/欠费绿通生）。
- **本地运行**：后端 `DB_ENABLED=true` 时启动自动 create_all（app/db/init_db.py）；生产建表仅 `alembic upgrade head`；backfill 脚本一律先 `--dry-run`。
- **联调顺序**：后端端点合入并出 OpenAPI 后，前端/小程序才允许对接（契约冻结 + 偏差记录制度，禁止口头契约）。

## 7. 交付节奏与里程碑对齐（与两份《V1范围与开发顺序》的泳道对应）

| 里程碑 | 达成条件 | 对应阶段 |
|---|---|---|
| M1 契约双冻结 | 13A-P0 + 13B-P0 合并评审签认（公共附录一次冻结） | A-P0 / B-P0 |
| M2 范式定型 | 13A-P2 请假五件套评审通过（13A-P3/P4 与 13B 写侧阶段的准入门禁） | A-P2 |
| M3 学籍主线通 | 注册+异动全链路（单一写入口成为事实标准，13A 在籍校验切换该函数） | B-P1 / B-P2 |
| M4 教学主线通 | 方案→任务→课表→发布 | B-P3 / B-P4 |
| M5 风险闭环通 | 13A 五来源风险 + 13B 预警扫描互通（预警→工作台→转风险→关闭） | A-P4 / B-P5 |
| M6 毕业预审通 | 七项供数四类学生走通（依赖 A-P4 处分口径，倒挂时走规则开关） | B-P6 |
| M7 多端收口 | 双端小程序页全量真数据 + 双租户演示走通 | A-P7 / B-P7 |
| M8 验收发布 | 两侧 P8 验收 100% + 回归红线零违反 → V1 发布评审 | A-P8 / B-P8 |
