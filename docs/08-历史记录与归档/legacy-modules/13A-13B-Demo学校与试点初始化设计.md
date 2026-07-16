# 13A/13B Demo 学校与试点初始化设计

> 版本：V1.0（2026-07-05）
> 性质：13A 学工中心 / 13B 教务中心 的演示租户数据扩充、初始化/重置机制与售前演示动线设计。只出文档，不写代码、不改脚本。
> 依据：`_13-现有系统集成事实速查.md`、`_13-需求输入-V1.1.md`、`13A-13B-数据表与迁移策略草案.md`（表名裁定 t_affairs_*/t_aa_*）、`13A-13B-现有代码库融合证据报告.md`（P0-9：演示环境约束与种子脚本进 scripts/）。
> 姊妹文档：《13A-13B-历史数据导入与迁移设计》（客户真实数据进场）、《13A-13B-第三方系统对接与开放接口设计》（外部系统）。本文件只管演示/试点租户的"假数据"体系。

---

## 一、现状复用（全部经代码核实，禁止另起炉灶）

### 1.1 双演示租户体系（既有事实）

| 项 | demo-school 正式演示租户 | sandbox-school 体验沙箱租户 | 证据 |
|---|---|---|---|
| tenant_id | 1000000000000000003 | **1000000000000000004** | backend/app/services/sandbox_service.py 第 17/20 行（SANDBOX_TID/DEMO_TID）；速查 §2 |
| tenant_code | demo-school | sandbox-school | 同上 |
| 写保护 | **中间件只读锁：写操作一律 403**，页面引导去沙箱 | 可写，**每晚 0 点自动重置** | 速查 §2/§11 |
| 账号（密码均 123456） | admin（陈管理·SCHOOL_ADMIN）/ teacher（李导师·COUNSELOR）/ student（张同学·STUDENT） | admin2 / teacher2（王老师）/ student2（李体验） | backend/scripts/_seed_two_tenants.py `_add_user`；backend/app/services/auth_service_db.py 第 22 行 ROLE_BY_LOGIN |
| 密码存储 | pbkdf2 hash 落库（复用全局 hash_password），绝无明文 | 同左 | _seed_two_tenants.py 文件头自述 |
| 数据范围 | admin→SCHOOL 全校；teacher→COUNSELOR_CLASSES 所带班级；student→SELF 本人 | admin2/teacher2/student2 同构 | auth_service_db.py ROLE_BY_LOGIN 映射 |
| 组织 | 2 学院 / 3 专业 / 3 班级（数媒2601班/软件2601班/电商2601班） | 体验学院 / 1 专业 / 体验2601班 | _seed_two_tenants.py DEMO_CLASSES；sandbox_service.py 组织段 |
| 学生 | ≥20 名，主角"张同学 2026D0006"六域富数据 | "李体验 2026S0001"最小集 | _seed_two_tenants.py / _seed_demo_school.py |
| 登录 | 全部走真实 `POST /api/v1/auth/login`，登录页明示账号 | 同左 | 速查 §2/§9 |

### 1.2 既有脚本体系（13A/13B 扩展的挂载点）

| 脚本/服务 | 职责 | 关键设计（必须继承） |
|---|---|---|
| backend/scripts/seed_two_tenants.py | 一键初始化独立入口：先 `seed_demo_school(db)`（张同学六域富数据）再 `seed_two_tenants(db)`（双租户账号+组织+业务样例）；服务器 MySQL 版为 seed_mysql_two_tenants.py | **幂等 · 分块判断 · 只新增，不删改其他租户任何数据**（文件头自述） |
| backend/scripts/_seed_two_tenants.py | demo 租户实现：品牌、账号、组织、六域三态样例、教师范围（TeacherStudentScope）、待办/消息/工作流样例 | 沙箱部分仅转调 sandbox_service.seed_sandbox（第 216–219 行），实现不分叉 |
| backend/app/services/sandbox_service.py | 沙箱种子/重置**唯一实现**（每晚 0 点定时重置与手动 CLI 共用） | 只操作 tenant_id==SANDBOX_TID 的行；`assert SANDBOX_TID != DEMO_TID`（第 77 行安全断言）；逐表条件删除、绝不 truncate、绝不无租户条件删除 |
| backend/scripts/reset_sandbox_school.py | 沙箱手动重置 CLI | `--dry-run` 与 `--confirm` **互斥且必选其一**；执行前校验库内租户 tenant_code==sandbox-school 不符即拒绝（退出码 3，防 ID 被挪用）；dry-run 打印逐表将删行数且不落库；重置前后核对 demo-school 学生数不变（保护性对账，第 54–82 行） |
| backend/scripts/_seed_demo_school.py | 张同学富数据：已批请假+**待审请假**（教师可现场演示审批）、已结工单、成绩+**待处理学业预警**（可演示处理/升级）、实习/毕设/就业样例、教师侧七类待办 | "三态"思想已成型：每域含 已完成/进行中/待处理 组合 |
| backend/scripts/_seed_core.py 等 _seed_*.py 8 份 | 主 demo 租户（…001）各域种子 | 13A/13B 新增种子沿此命名风格与幂等写法 |

⚠️ 勘误登记（本设计发现，P0 顺手清理）：`_seed_two_tenants.py` 第 29 行模块级常量 `SANDBOX_TID = 1000000000000000004` 为陈旧残留（沙箱种子实际转调 sandbox_service，未使用该常量）；权威值是 sandbox_service.py 的 **…007**（与速查 §2 一致，…004 是 trial 租户）。`reset_sandbox_school.py` 文件头注释中的"(1000000000000000004)"同为陈旧注释，代码 import 的是 sandbox_service.SANDBOX_TID，行为正确。

**结论**：13A/13B 不新建初始化机制，只做三件事——①向种子链路增加 13A/13B 数据块；②向 sandbox_service 清表清单登记新表；③新增两份数据块脚本挂入现有入口（§3.2）。

---

## 二、13A/13B Demo 数据扩充清单（17 项逐项设计）

通用规约（各项共用）：

1. **两租户同构**：demo-school 配"讲故事的富数据"（下文口径），sandbox-school 配同结构 1/3 缩量（重置快、可写演示不空手）。
2. **三态覆盖是硬要求**：每类业务至少含"已终态 / 审批中（或进行中）/ 异常（或待发起）"，保证列表页、审批页、统计页、360 页同时有内容。
3. 全部数据挂 tenant_id；学生外键一律指 t_student_profile.id；状态字面全部取草案冻结枚举。
4. "审批中"数据必须真实生成 t_workflow_instance / t_workflow_task + t_unified_todo（assignee=teacher/registrar 等演示账号），保证登录即见待办——禁止只造业务行不造待办的"死数据"。
5. 敏感项（困难/家庭/心理线索）按加密+脱敏规则造数（假数据也走 *_encrypted），用于演示"打码→授权查看→审计"完整链路。
6. 时间字面相对"当前学期"（2026-2027-1）动态计算（种子内以 now 偏移生成），避免演示时数据显得陈旧。

### 2.1 demo 学校（租户与模块开关）

- 数据形态：既有 2 租户不动；platform features 为两租户登记 `studentAffairs` / `academicAffairs` = 开（platform_defaults.py 套餐矩阵 + t_platform_config 覆盖行各 1 条）。
- 为什么：售前第一屏登录即见"学工中心/教务中心"两个新菜单；同时保留平台端"关模块→业务 API 403"的模块级授权卖点演示位（融合证据报告 P0-4）。
- 落表：t_platform_config（features）；t_tenant_brand_config 不动。

### 2.2 学生

- 数据形态：demo 扩到 **60 名**（每班 20）。状态组合：50 在籍（ACTIVE/NORMAL）、2 休学 SUSPENDED、1 退学 WITHDRAWN、2 留级 RETAINED、5 名标记为毕业年级（供毕业预审批次圈定）；张同学保持全域主角不动。沙箱 20 名同构缩量。
- 为什么：学籍状态机主要枚举全部可视；任何列表筛选器都有非空结果；休学生用于演示"禁选课/禁考试"拦截；毕业年级 5 人是 2.16 的对象池。
- 落表：t_student_profile（student_status 一律经 change_student_status 单一入口写入，顺带产出 2.17 的异动事件）+ t_student_contact（脱敏号码假数据）。

### 2.3 教师

- 数据形态：既有 teacher（李导师）为辅导员主角不动；新增 4 名教师**档案**（任课教师×2、宿管×1、心理教师×1）——仅 t_user 行 + scope 行，**不加登录账号**（用数据不用账号，避免登录页账号膨胀）。
- 为什么：教学任务/课表需要可分配教师；宿管配 scope_type=DORM_BUILDING 行、心理教师配 PSY 授权行，演示"看得见=能处理"的范围机制向 13A 新角色的扩展（速查 §5）。
- 落表：t_user、t_teacher_student_scope（含新增 scope_type=DORM_BUILDING 样例行）。

### 2.4 辅导员（工作台供数）

- 数据形态：teacher 账号维持绑 3 班（既有 COUNSELOR_CLASSES scope 不动）；保证工作台八块全部非空：今日待办 ≥6、风险学生 ≥4、待审请假 ≥2、学业预警 ≥2、待谈话 ≥2、困难生 ≥3、就业未填报 ≥2、实习异常 ≥1。
- 为什么：辅导员工作台是 13A 最高频页与售前必看页，任何一块空白都露怯；数字全部由 2.10–2.15 业务数据聚合而来，不单独造数。
- 落表：无独立表（聚合口径），但要求种子完成后跑一次"工作台八块非空"自检断言。

### 2.5 教务员

- 数据形态：**新增账号 registrar / registrar2（123456）**，用户类型 TEACHER，角色 ACADEMIC_ADMIN，scope=SCHOOL。
- 为什么：13B 教务首页按角色出视图（需求 §3.1），无教务员账号则"教务处视角"无法登台演示。
- 落表：t_user + auth_service_db.ROLE_BY_LOGIN 登记（扩展点见 §3.2 S4）。

### 2.6 学工管理员

- 数据形态：**新增账号 saadmin / saadmin2（123456）**，角色 SA_ADMIN，scope=SCHOOL。
- 为什么：学工处视角首页（全校风险/待审/学院排行）与辅导员视角对比是 13A-01 的核心演示；也承担 2.14 的"授权查看完整敏感信息"角色。
- 落表：同 2.5。

### 2.7 学院

- 数据形态：维持 2 学院（信息工程学院/经贸学院），补 13B-P2 新列 short_name（信工/经贸）、sort_order。
- 为什么：学院维度排行、下钻、对比图至少需要两个对比项；不加第三学院控制种子体积。
- 落表：t_college（加列后）。

### 2.8 专业

- 数据形态：维持 3 专业（数媒/软件/电商），补 education_years=3、training_level=高职、enroll_status=在招。
- 为什么：培养方案绑定"专业+年级"、学制推算开课学期上限（文件一 B7 预检）都依赖新列。
- 落表：t_major（加列后）。

### 2.9 班级与班干部

- 数据形态：3 班补 class_code、capacity=40、graduate_year、class_status=NORMAL；每班班干部 3 名（班长/团支书/学习委员），其中软件2601班 1 名 REMOVED（含 removed_at）展示任免史。
- 为什么：班级管理页字段齐全；班干部任免记录页有 ACTIVE/REMOVED 两态；REMOVED 行进 360 时间线验证任职经历事件。
- 落表：t_class（加列后）+ t_affairs_class_cadre（10 行）。

### 2.10 请假（13A 主秀场）

- 数据形态：demo 共 **8 条**覆盖三线——
  - 终态线：CLOSED×2（各含 t_affairs_leave_cancel_record 销假记录）、APPROVED 在假中×1、REJECTED×1；
  - 审批线：COUNSELOR_REVIEW×1（teacher 待办可现场审批——沙箱同构条目供真点）、COLLEGE_REVIEW×1（5 天长假，演示天数分级路由）；
  - 异常线：OVERDUE×1（end_time 已过且未销假，联动 2.14 风险记录+工作台红条）、EXTENSION_REVIEW 续假×1（t_affairs_leave_extension 一行）。
- 为什么：一页讲完 14 态状态机精华——审批、销假、续假、逾期转风险四条链路各有活数据；OVERDUE 是"请假→风险→辅导员"跨模块闭环的演示锚点。
- 落表：t_cs_leave（affairs_status 新列+旧 status 投影同步）+ t_affairs_leave_cancel_record / t_affairs_leave_extension + t_workflow_instance/task + t_unified_todo。

### 2.11 成绩

- 数据形态：张同学 6 科（1 科 52 分不及格）；毕业年级 5 生每人 8 科：3 人全过、1 人挂 2 科（联动 2.12 预警与 2.16 毕业异常）、1 人缺考 1 科（ABSENT）；另造等级制成绩 2 行（"良"）验证映射展示。
- 为什么：成绩查看页、挂科率统计、学业预警来源（FAIL_COURSE/ABSENT_EXAM）、毕业审核"课程未通过"异常项全部由这一份数据供给，一数多用。
- 落表：**t_acad_grade（唯一权威成绩表，草案 §4.5 硬约束）**，经 academic_service 既有创建路径写入。

### 2.12 学业预警

- 数据形态：5 条——PENDING_HANDLE×2（teacher 登录即见、可现场处理/升级）、PROCESSING×1、ESCALATED×1、CLOSED×1；source_code 覆盖 FAIL_COURSE / ABSENT_EXAM / CREDIT_GAP，rule_code 填规则中心键样例。
- 为什么：演示"13B 规则扫描产生 → 13A 辅导员处置"的跨域闭环（速查 §6：复用 t_acad_warning 不建新表）；CLOSED 行供 360 时间线与统计口径。
- 落表：t_acad_warning（+source_code/rule_code 新列）。

### 2.13 处分

- 数据形态：4 条——EFFECTIVE 警告×1（投影 t_cs_discipline record_status=ACTIVE，source_case_id 回链）、REMOVED×1（含 t_affairs_discipline_remove_apply 解除申请全记录，展示"历史保留"）、COLLEGE_REVIEW 审批中×1、REGISTERED 刚登记×1。其中 EFFECTIVE 那条落在毕业年级学生身上（制造 2.16 的"未解除处分"异常）。
- 为什么：处分登记→审批→生效→解除全生命周期一屏可视；case→投影一致性（草案 §5.3 第 5 条对账口径）现场可查；毕业联动是需求 §4 闭环 2 的原文场景。
- 落表：t_affairs_discipline_case / t_affairs_discipline_remove_apply + t_cs_discipline（投影行）。

### 2.14 困难认定（敏感演示主场景）

- 数据形态：批次 1 个（PUBLICITY 公示中）；申请 6 条——APPROVED×3（特别困难/困难/一般困难各 1，逐条写 t_affairs_aid_level_history 进困难库）、COLLEGE_REVIEW×1、REJECTED×1、DRAFT×1；家庭经济表仅对 APPROVED 行造数（income_encrypted 加密假数据）。另配 t_affairs_risk_record 4 条（source 覆盖 LEAVE_OVERDUE/ACADEMIC_WARNING/DORM/MANUAL，状态 NEW×2/PROCESSING×1/CLOSED×1）作为工作台风险区供数。
- 为什么：等级三档齐全供后续助学金演示引用；公示态可视；**脱敏三件套演示主场**——列表等级打码 → saadmin 填原因查看完整家庭经济 → t_security_audit_log 立见审计记录。
- 落表：t_affairs_aid_batch / _apply / _family_economy / _level_history；风险落 t_affairs_risk_record / _handle_record。

### 2.15 宿舍

- 数据形态：楼 2 栋（男/女各 1，宿管 scope 绑楼）、房 12 间、床 48 张：占用 31 张（与在籍生对齐，入住率约 52%）、空床 16、LOCKED×1；调宿 2 条（EXECUTED×1、DORM_MANAGER_REVIEW 审批中×1）；检查任务 1 个 RUNNING：检查记录 NORMAL×4、ABNORMAL×2（其中 1 条夜不归宿——已联动写 t_cs_dorm_exception 并生成 2.14 的 DORM 来源风险）。
- 为什么：房源树、入住率统计、调宿审批、检查→异常→风险三链路全通；床位占用与既有"我的宿舍"（t_cs_dorm_record 回写）一致性现场可验（草案 §3.8 回写硬约束的活证据）。
- 落表：t_affairs_dorm_building / room / bed / transfer / check_task / check_record + t_cs_dorm_record（回写行）+ t_cs_dorm_exception。

### 2.16 毕业资格

- 数据形态：批次 1 个（PRECHECKED）圈定毕业年级 5 生：SYSTEM_PASSED×3、SYSTEM_ABNORMAL×2（1 人挂 2 科、1 人处分未解除）；item_results_json 七项三态齐全，其中"费用满足"项对 1 人置 UNKNOWN（演示三态判定不误杀）。
- 为什么：预审七项判定是 13B 收官卖点；异常下钻到具体证据行（成绩/处分）演示跨域只读引用（草案 §4.6 七项供数只读六域）。
- 落表：t_aa_graduation_audit_batch / _result。

### 2.17 学生 360 时间线

- 数据形态：张同学补 13A/13B 事件 **8 条**（source_module 两域分明）：入学注册（academic-affairs）、困难认定通过、奖学金获得（预造 1 条 GRANTED 资助申请支撑）、请假 CLOSED、处分生效、处分解除、调宿执行（student-affairs）、预警关闭；另为毕业年级 1 名 SYSTEM_PASSED 学生补"全链 12 条"直至毕业结论事件。
- 为什么：360 页是演示收束页——从任意业务点跳进 360 都有完整故事线；同时验证"终态写 t_student_stage_event、禁止自建 timeline 表"的写入规范（草案总纲 10）。
- 落表：t_student_stage_event（append-only）；支撑行落 t_affairs_funding_project/batch/application（各 1 条）。

### 2.18 教务底座数据（不占 17 项名额，2.11/2.16 的前置）

学期 2 条（2025-2026-2 ARCHIVED、2026-2027-1 PUBLISHED 且 is_current）；校历事件 6 条（教学周/考试周/国庆调休 SWAP 各有）；作息节次 10 节；课程库 12 门 ENABLED；培养方案 1 份 PUBLISHED（绑软件专业 2026 级，含课程明细 24 行）；教学任务 9 条（3 班×3 课）；课表 2 批——PUBLISHED 批（3 班每班 12 节，零冲突）+ DRAFT 批（**故意保留 1 个教师冲突**，供冲突检测演示）；注册批次 1 个（REGISTERED 55 / UNREGISTERED 3 / PENDING_REGISTER 2）。落表：t_aa_term/calendar_event/time_slot/course/program*/teaching_task*/schedule*/registration*。

**完成度口径：17/17 项全部给出数据形态（条数+状态组合）、配置理由（三态演示点）与落表；两租户同构、沙箱缩量 1/3。**

---

## 三、初始化与重置机制设计

### 3.1 机制总则（复用五条防误删设计，一条不减）

1. **dry-run/confirm 互斥必选**：一切初始化/重置 CLI 沿用 reset_sandbox_school.py 的 argparse 互斥组设计；无 --confirm 一律不落库；dry-run 打印逐表影响行数供人工复核。
2. **tenantCode 双重校验**：按 tenant_id 定位后必须复核 tenant_code 字面相等（…007↔sandbox-school、…003↔demo-school），不符打印拒绝原因并以非零码退出（现有退出码 3 口径）。
3. **安全断言与清单驱动**：保留 `SANDBOX_TID != DEMO_TID` 断言并扩展——清表动作只允许来自"表白名单清单"，每条 DELETE 必带 tenant_id 条件（静态自检），杜绝手写裸删与 truncate。
4. **保护性对账**：重置前后核对 demo-school 与主 demo（…001）关键表行数不变，变了即报错人工介入（现有"demo_before 学生数核对"模式扩展到 t_affairs_*/t_aa_* 抽样表各 3 张）。
5. **种子只新增**：初始化脚本全部幂等——分块判断"该块已存在则跳过"，重复执行零副作用；绝不 UPDATE/DELETE 其他租户任何行。

### 3.2 脚本清单建议（扩展点定位，不写代码）

| # | 脚本/文件 | 动作 | 扩展点说明 |
|---|---|---|---|
| S1 | `backend/scripts/_seed_affairs_demo.py`（新增） | 13A 数据块实现：§2.9/2.10/2.13/2.14/2.15/2.17 与配套 workflow/待办 | 函数签名对齐 `seed_demo_school(db)->dict` 风格；入参含 tid 与 scale（demo=1、sandbox=1/3），两租户复用同函数 |
| S2 | `backend/scripts/_seed_aa_demo.py`（新增） | 13B 数据块实现：§2.18 底座 + 2.11/2.12/2.16；学籍状态经 change_student_status 批量入口 | 成绩写 t_acad_grade 走 academic_service 既有创建路径，预警加列后补 source_code |
| S3 | `backend/scripts/_seed_two_tenants.py`（扩展） | `seed_demo_tenant()` 末尾追加调用 S1/S2（富量）；`_add_user` 块新增 registrar/saadmin | 顺手清理第 29 行陈旧 SANDBOX_TID 常量（§1.2 勘误） |
| S4 | `backend/app/services/auth_service_db.py`（扩展） | ROLE_BY_LOGIN 增 4 行：registrar/saadmin（demo）、registrar2/saadmin2（沙箱）→ (ACADEMIC_ADMIN / SA_ADMIN, "教务处管理员"/"学工处管理员", SCHOOL, …) | 登录页演示账号提示同步更新（速查 §9"登录页明示"口径）；权限点按 P0-3 书写规范登记 |
| S5 | `backend/app/services/sandbox_service.py`（扩展） | ①`seed_sandbox()` 追加调用 S1/S2（scale=1/3）；②清表清单登记全部 13A/13B 新表（草案附录 A 43 张中沙箱涉及的全部）+ 加列表（t_cs_leave 等）的沙箱行清理规则 | **0 点定时重置与手动 CLI 共用此实现，改一处两处生效**；append-only 表仅在沙箱租户内允许随重置删除 |
| S6 | `backend/scripts/reset_sandbox_school.py`（不改主体） | 自动继承 S5（其删除/重建即 sandbox_service 转调） | dry-run 输出自然多出新表行数统计，无需改码；文件头陈旧"…004"注释随 S3 一并订正 |
| S7 | `backend/scripts/seed_two_tenants.py` / `seed_mysql_two_tenants.py`（不改主体） | 自动继承 S3，一键初始化入口维持唯一 | SQLite dev 与 MySQL 生产两版行为一致由现有双脚本机制保证 |
| S8 | `backend/scripts/reset_demo_school_13ab.py`（新增，**demo 复核模式**） | demo-school 的 13A/13B 数据块修复重置：在 --dry-run/--confirm 之外**再加 `--i-know-demo` 第三重确认**；只删 tenant_id=…003 且表∈13A/13B 新表白名单的行，随后重跑 S1/S2 富量种子 | demo-school 有只读锁、API 写不进，本脚本是唯一合法维护通道，故防护最高：tenantCode 校验 + 表白名单 + 三重确认 + 删除前自动经导出管线快照留档（t_export_task 留痕） |

### 3.3 重置日志（审计）与红线

- **重置日志**：S5/S6/S8 每次执行（**含 dry-run**）调用 `audit_log.record("SANDBOX_RESET" / "DEMO_RESEED", resource="tenant:<code>", detail={逐表行数, dryRun, 脚本名, 主机}, result)` 落 t_security_audit_log（含 traceId）；confirm 执行报告（JSON：删除行数/重建行数/耗时/保护对账结果）打印并留存日志文件。0 点定时重置沿用同函数，天然同规格留痕。
- **红线**：
  1. 正式租户（除 …003/…007 外一切租户）任何脚本不得触碰——tenant_id 白名单 + 表白名单双闸；
  2. demo-school 重置必须走 S8 三重确认；禁止把 DEMO_TID 传入沙箱重置函数（断言兜底）；
  3. 生产库执行前 dry-run 报告必须人工过目（实施 SOP 签认）；
  4. append-only 表（*_audit_trail/StageEvent/level_history/handle_record/contact_log）仅允许在两演示租户内随重置清理，正式租户永不物理删除（草案 §5.4 红线同款）；
  5. t_security_audit_log 本身任何租户都不清（审计不可自噬）。

### 3.4 一键动作汇总（运维口径）

| 动作 | 命令形态（示意） | 影响范围 | 频率 |
|---|---|---|---|
| 一键初始化/补齐双租户（含 13A/13B） | `python scripts/seed_two_tenants.py`（MySQL 版同名 mysql 脚本） | 两演示租户，幂等只新增 | 部署后/版本升级后 |
| 一键重置沙箱 | `python scripts/reset_sandbox_school.py --dry-run` → 复核 → `--confirm` | 仅 …007 | 手动按需；0 点定时自动 |
| demo 演示数据修复 | `python scripts/reset_demo_school_13ab.py --dry-run` → `--confirm --i-know-demo` | 仅 …003 的 13A/13B 白名单表 | 极低频（数据被维护误伤时） |

---

## 四、售前 15 分钟演示动线（要点脚本）

> 原则：demo-school 讲"看"（富数据+只读锁的安全感），sandbox-school 讲"改"（现场写操作）；PC 投屏、小程序手机同屏。演示前一晚确认 0 点重置成功、当天早晨跑一次 S7 幂等补齐。

| 分钟 | 账号 / 端 | 页面 | 看什么（数据即 §二 配置） | 讲什么 |
|---|---|---|---|---|
| 0–1 | admin @ demo-school · PC | 登录页 → 学工首页 | 登录页明示演示账号；首页全校卡片：60 生 / 风险 4 / 待审请假 2 / 困难 3 / 宿舍异常 2 / 学院排行 2 项 | 真实登录非 mock；角色化首页 |
| 1–3 | 同上 | 学工·请假列表 → OVERDUE 详情 | 8 条状态各异；逾期单详情内可见联动生成的风险记录 | 逾期→风险→辅导员的自动闭环 |
| 3–5 | 同上 | 困难认定（公示批次）→ APPROVED 详情 | 列表等级打码 → 点"查看完整"强制填原因 → 切审计页立见记录 | 敏感数据三件套：脱敏/授权/审计 |
| 5–7 | teacher @ demo-school · 手机小程序 | 教师工作台 → 今日待办 → 审批 | 待办 6+；点 COUNSELOR_REVIEW 请假单尝试通过——**demo 只读锁弹 403**"请到沙箱体验" | 顺势讲双租户安全设计 |
| 7–9 | teacher2 @ sandbox-school · 手机 | 同页现场审批通过 | 状态实时流转；student2 端收到 t_unified_message；再点一次审批演示 409 | 三端同一状态机 + 乐观锁防重复审批 |
| 9–11 | registrar @ demo-school · PC | 教务首页 → 课表（PUBLISHED）→ DRAFT 批冲突报告 | 排课完成率/成绩进度卡片；故意保留的教师冲突条目 | 13B 角色视图；冲突检测能力 |
| 11–12 | 同上 | 毕业资格预审批次 | 3 过 2 异常；异常生下钻到挂科成绩行与未解除处分行 | 七项三态预审、跨域证据引用 |
| 12–13 | saadmin @ demo-school · PC | 学工统计 + 学业预警列表 | 学工处全校视角 vs 辅导员范围视角对比；预警 PENDING→CLOSED 链路 | 13B 产生、13A 处置的跨中心闭环 |
| 13–14 | admin @ demo-school · PC | 张同学 · 学生 360 | 时间线 8+ 事件两域汇流：入学→困难→奖学金→请假→处分及解除→调宿→预警关闭 | 全生命周期一页收束 |
| 14–15 | 收尾 | 数据中心 / 导入页一瞥 | 提 Excel 迁移 21 类模板与开放接口预留（两份姊妹文档） | 实施路径与报价收尾 |

**保底预案**：①网络异常时 5–9 分钟段改在 PC `/admin` 审批页完成同一闭环；②沙箱被上一场演示改乱时现场跑 `reset_sandbox_school.py --confirm`（约 1 分钟）恢复；③投屏故障时全程手机小程序动线（学生端 13 页+教师端 10 页已覆盖主链路）。

---

## 五、试点学校初始化（真实试用租户，与 Demo 严格分离）

> 场景：签约前 POC / 签约后首校试点。试点租户是**真实租户**（真实学校、真实老师、部分真实学生数据），与 demo/sandbox 假数据体系必须物理分离：**任何 _seed_*.py 演示种子、任何重置脚本都不得指向试点租户**（§3.3 红线 1 的白名单机制天然拦截）。

### 5.1 试点租户开通七步（复用现有平台端能力，不新建流程）

| 步 | 动作 | 复用能力（证据） |
|---|---|---|
| 1 | 平台端建租户（试用态，含到期时间） | /api/v1/platform 租户 CRUD/延试用/到期只读（platform.py，融合证据报告 1.14） |
| 2 | 开通模块：六域 + studentAffairs + academicAffairs 按试点范围勾选 | platform features（effective_features/feature_enabled），关模块业务 API 403 |
| 3 | 品牌配置（校名/主色/水印文案） | t_tenant_brand_config + 开校引导 onboarding |
| 4 | 建校级管理员账号（强密码，非 123456） | 平台端"建校管/重置密码"能力；试点租户**禁用弱密码**（弱密码仅存在于两演示租户，_seed_two_tenants.py 头注释口径） |
| 5 | 组织与学生数据进场 | **全部走文件一《历史数据导入与迁移设计》§5 依赖顺序**（组织→学生→学籍→…），不走种子脚本 |
| 6 | 教师账号与数据范围 | t_teacher_student_scope 逐辅导员登记（_seed_teacher_scope.py 仅作格式参考，试点用导入/后台维护） |
| 7 | 平台规则调参（长假天数分级、导入行数上限等） | 平台规则中心 safe_rule 租户覆盖（速查 §11），不改代码 |

### 5.2 试点数据边界与保护

1. **试点租户零假数据**：不跑任何 _seed 脚本；培训用测试单据统一打"TEST-"前缀编号，试运行结束后由业务功能删除（软删），不用脚本清库。
2. **重置禁区**：sandbox_service 白名单只含 …007；S8 白名单只含 …003——试点租户 ID 不在任何清表白名单内，脚本层面无法误删（验收项 7 反向验证）。
3. **敏感数据从试点第一天就按生产标准**：真实学生手机号/身份证入库即加密、出口恒脱敏、导出走水印管线——试点即生产预演，不留"试点先不脱敏"的口子。
4. **试点转正式**：平台端"转正式"动作（现有能力）+ 数据零迁移（同库同租户，只改租户状态与到期策略）；试点期产生的 TEST- 单据在转正式前完成清理并出清理报告（导出留档）。
5. **试点演示混用禁令**：给试点校领导演示用 demo-school，试点校自己练手用 sandbox-school 或试点租户内 TEST- 单据；**严禁**为了"演示好看"往试点租户灌演示种子。

### 5.3 试点验收口径（初始化部分）

- 文件一 §5.3 迁移验收清单全绿（21 domain 按试点范围裁剪）；
- 模块开关矩阵与合同一致（平台端截图归档）；
- 全部教师账号 scope 行覆盖率 100%（无 TENANT_FALLBACK 兜底行，对齐融合证据报告 R5"标准版应逐步清零"）；
- t_security_audit_log 自开通日起连续留痕。

---

## 六、验收标准

1. `seed_two_tenants.py` 连续执行 3 次，第 2/3 次行数零增长（幂等验证）；§二 17 项在两租户逐项核对：条数、状态组合、待办/工作流配套、StageEvent 配套全对。
2. 演示账号矩阵（admin/teacher/student/registrar/saadmin 及沙箱对应 *2 账号，共 10 个）全部真实登录成功，角色视图与数据范围正确（ROLE_BY_LOGIN 扩展生效，teacher 只见 3 班数据）。
3. `reset_sandbox_school.py --dry-run` 输出包含全部 13A/13B 新表行数；`--confirm` 后沙箱数据回到种子态，demo-school 与主 demo 租户抽样表行数不变（保护对账日志留存）。
4. 0 点定时重置连续 3 日成功，t_security_audit_log 每日有 SANDBOX_RESET 记录（含 dry_run=false 与逐表 detail）。
5. demo-school 任一 13A/13B 写端点返回 403（只读锁覆盖新模块）；同一操作在沙箱成功并留审计。
6. §四 动线按分钟表完整走通一遍：无空页、无 404 深链（pages.json 校验，P0-8）、无 mock 兜底数据（新页面禁用 withFallback，融合证据报告 R8）。
7. S8 demo 复核模式演练一次：缺 `--i-know-demo` 拒绝执行、dry-run 行数正确、confirm 后 17 项数据恢复且有快照留档。
8. 试点隔离反向验证（§5.2）：将试点租户 ID 传入沙箱重置函数被断言/白名单拒绝；试点租户内无任何 _seed 来源数据。

---

## 附录 A：demo-school 种子数据逐条明细（S1/S2 实现对照清单）

> 用途：种子脚本实现与验收核对的行级基线。学号段：主角 2026D0006（张同学）；毕业年级 2023G0001–2023G0005；其余 2026D/2026R 段。时间以"当前学期开学日"（记 T0）偏移表示。

### A.1 请假 8 条（§2.10）

| # | 学生 | 类型 | 起止（相对 T0） | affairs_status | 配套 |
|---|---|---|---|---|---|
| L1 | 张同学 | SICK | T0+10 ～ +12（3 天） | CLOSED | 销假记录 1 条（辅导员已确认）；StageEvent |
| L2 | 2026D0011 | PERSONAL | T0+15 ～ +16 | CLOSED | 销假记录 1 条 |
| L3 | 2026D0012 | SICK | 今-1 ～ 今+2 | APPROVED（在假中） | 到期前提醒待办（DEADLINE_REMINDER） |
| L4 | 2026D0013 | PERSONAL | T0+20 ～ +21 | REJECTED | 审批任务 REJECTED + action_reason |
| L5 | 2026D0014 | SICK | 今+1 ～ 今+2（2 天） | COUNSELOR_REVIEW | workflow 实例 + teacher 待办（**沙箱同构条目供现场审批**） |
| L6 | 2026D0015 | PERSONAL | 今+3 ～ 今+8（5 天） | COLLEGE_REVIEW | 天数分级路由展示（辅导员已过、学院节点 PENDING） |
| L7 | 2026D0016 | SICK | 今-6 ～ 今-3 | **OVERDUE** | 联动 R1 风险记录 + 辅导员红条待办；overdue_pushed_at 已置 |
| L8 | 2026D0012 | 续假 | 原单 L3 延至 今+4 | EXTENSION_REVIEW | t_affairs_leave_extension 1 条 + 审批中 |

### A.2 风险 4 条（§2.14 后半）

| # | 学生 | source | risk_level | 状态 | 处置流水 |
|---|---|---|---|---|---|
| R1 | 2026D0016 | LEAVE_OVERDUE（ref=L7） | HIGH | NEW | — |
| R2 | 2023G0002 | ACADEMIC_WARNING（ref=W1） | MEDIUM | PROCESSING | HANDLE×1（含 next_plan） |
| R3 | 2026D0021 | DORM（ref=夜不归宿 D-AB2） | MEDIUM | NEW | — |
| R4 | 2026D0022 | MANUAL | LOW | CLOSED | ASSIGN+HANDLE+CLOSE 三条流水；StageEvent |

### A.3 学业预警 5 条（§2.12）

| # | 学生 | source_code | 状态 |
|---|---|---|---|
| W1 | 2023G0002 | FAIL_COURSE（挂 2 科） | PENDING_HANDLE |
| W2 | 2023G0003 | ABSENT_EXAM | PENDING_HANDLE |
| W3 | 张同学 | FAIL_COURSE（1 科 52 分） | PROCESSING |
| W4 | 2026D0018 | CREDIT_GAP | ESCALATED |
| W5 | 2026D0019 | FAIL_COURSE | CLOSED（进 360） |

### A.4 处分 4 条（§2.13）

| # | 学生 | disc_type | 状态 | 配套 |
|---|---|---|---|---|
| C1 | 2023G0003 | WARNING | EFFECTIVE | 投影 t_cs_discipline ACTIVE；毕业异常源 |
| C2 | 2026D0023 | SERIOUS_WARNING | REMOVED | remove_apply 全记录；两条 StageEvent（生效/解除） |
| C3 | 2026D0024 | DEMERIT | COLLEGE_REVIEW | workflow + saadmin 待办 |
| C4 | 2026D0025 | WARNING | REGISTERED | 刚登记，无投影 |

### A.5 困难认定 6 条（§2.14 前半，批次 AID-2026 公示中）

| # | 学生 | 等级 | 状态 | 配套 |
|---|---|---|---|---|
| A1 | 2026D0031 | 特别困难 | APPROVED | family_economy 1 行（加密）；level_history；StageEvent |
| A2 | 2026D0032 | 困难 | APPROVED | 同上 |
| A3 | 张同学 | 一般困难 | APPROVED | 同上（衔接奖学金故事线） |
| A4 | 2026D0033 | 申报困难 | COLLEGE_REVIEW | workflow + 待办 |
| A5 | 2026D0034 | — | REJECTED | 驳回原因 |
| A6 | 2026D0035 | — | DRAFT | 学生端"继续填写"入口演示 |

### A.6 宿舍（§2.15）

- 楼：B1 梅苑1栋（M，宿管 scope 绑定）、B2 兰苑1栋（F）；房：每栋 6 间（101–103/201–203）；床：每间 4 张共 48。
- 占用 31（在籍生对齐分配）、空 16、LOCKED 1（B1-203-4，备注"维修"）。
- 调宿：T1 EXECUTED（2026D0041，B1-101-2→B1-102-3，原床已释放）；T2 DORM_MANAGER_REVIEW（2026D0042，含辅导员已审节点）。
- 检查：任务 K1（B1 栋卫生+夜不归宿，RUNNING）→ 记录 NORMAL×4；ABNORMAL D-AB1（B1-201 卫生不合格，RECTIFYING）；ABNORMAL D-AB2（2026D0021 夜不归宿 → t_cs_dorm_exception + R3 风险）。

### A.7 毕业预审 5 条（§2.16，批次 GRAD-2027 PRECHECKED）

| 学生 | overall | 异常项 |
|---|---|---|
| 2023G0001 | SYSTEM_PASSED | —（全链 12 条 StageEvent 主角） |
| 2023G0002 | SYSTEM_ABNORMAL | 课程未通过（挂 2 科，证据=成绩行） |
| 2023G0003 | SYSTEM_ABNORMAL | 未解除处分（证据=C1）+ 费用项 UNKNOWN |
| 2023G0004 | SYSTEM_PASSED | — |
| 2023G0005 | SYSTEM_PASSED | 费用项 UNKNOWN（三态演示） |

### A.8 教务底座关键行（§2.18）

- 学期：2025-2026-2（ARCHIVED）、2026-2027-1（PUBLISHED，is_current，18 教学周）。
- 课程 12 门：C01 高等数学 4 学分 REQUIRED ～ C12 电商运营实务（含实践学时样例、先修链 C05→C08 一组）。
- 方案 PRG-软件-2026（PUBLISHED，152 学分，课程明细 24 行，绑定软件2601班）。
- 教学任务 9 条（3 班 × 高数/软件基础/思政）；课表 PUBLISHED 批 36 节零冲突 + DRAFT 批 8 节含教师冲突 1 处（李导师 周三第 2 节双班）。
- 注册批次 REG-2026（ENROLL）：REGISTERED 55 / UNREGISTERED 3 / PENDING_REGISTER 2（precheck_json 含缴费未达样例）。

### A.9 张同学 360 时间线 8 条（§2.17，按时间序）

1. 入学注册完成（academic-affairs，REG-2026）
2. 困难认定通过·一般困难（student-affairs，A3）
3. 奖学金获得·校级三等（student-affairs，funding GRANTED 支撑行）
4. 请假结束·销假完成（student-affairs，L1）
5. 处分生效（student-affairs，历史样例，与 C2 学生区分：张同学线用轻量警告已解除故事）
6. 处分解除（student-affairs）
7. 调宿执行（student-affairs，宿舍变更）
8. 学业预警关闭（academic-affairs 产生、student-affairs 处置备注）

> 沙箱缩量口径：A.1 取 L1/L5/L7 三条、A.3 取 W1/W5、A.4 取 C1、A.5 取 A1/A4、A.6 楼 1 栋 3 间 12 床、A.7 取 2 生、A.9 取 4 条；其余同构缩减，保证每页仍非空且可写演示（L5 同构单供现场审批）。

*（完）*
