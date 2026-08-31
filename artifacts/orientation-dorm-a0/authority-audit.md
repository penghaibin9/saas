# A0 — Exact-Head 全校 Authority 真值审计

审计时间：2026-09-01（Asia/Shanghai）
仓库：`penghaibin9/saas`
工作分支：`codex/orientation-dorm-20260901`
审计基线：`origin/main @ 37e077cd452e3cbbbe7612cba4316d740cf871f6`
工作树 HEAD：`37e077cd452e3cbbbe7612cba4316d740cf871f6`
Alembic exact head：`20260831_iam_alias_backfill`（single head）

## 1. 审计结论

A0 证据闸门通过，但产品闸门尚未通过。当前代码不是“迎新/宿舍从零实现”：宿舍已有真实楼/房/床、入住、退宿、调宿、检查、异常、权限和楼栋范围链路；迎新已有真实学生台账、批次 CRUD、流程配置、学生提交、教师核验、导入、导出和四端页面。后续施工必须在这些能力上收口，不得另造第二套宿舍、文件、消息、导入导出或学生主档。

当前最大的 Authority 缺口是：

1. `OrientationStudent` 未关联 `OrientationBatch`，组织仍有名称字符串和字符串 `class_id`，流程状态仍以 `steps_json` 为主要真值。
2. 迎新报到资格由前端推导，教师核验继续把 `admissionNo` 当报到码，且普通更新可直接改报到/宿舍字符串状态。
3. `DormBed.student_id` 是当前占床真值，但没有可审计的入住历史 Authority；`CsDormRecord` 和迎新宿舍字符串只是投影，却可能被消费者误当真值。
4. 调宿虽有可靠性锁和原子换床，但主流程使用私有状态与私有待办封装，未完整接入统一工作流定义/实例/任务。
5. 迎新导出调用列表服务时未传用户范围，存在导出绕过 Data Scope 的结构性风险。
6. `RoleAssignmentScope` 持久化枚举没有 `DORM_BUILDING`，运行时却支持它；宿管楼栋范围还依赖 `manager_teacher_key`，其中存在真实姓名回退匹配。
7. `0001_init_core_tables` 是“当前 ORM metadata.create_all 活基线”。Fresh MySQL 能建出当前模型，但会掩盖缺失的显式增量迁移；后续 Schema 包必须同时做纯 Alembic Fresh MySQL、迁移前后快照和 ORM drift 检查。

本阶段未连接、写入或修复任何业务数据库；数据层输出为只读一致性检查计划，见 `data-consistency-plan.md`。

## 2. 开工状态与分支/PR 证据

- 已执行 `git fetch origin main`；审计时 `origin/main` 与工作树 HEAD 完全一致。
- 审计工作树干净；原始 `main` 工作树的用户改动未被暂存、重置、覆盖或带入本分支。
- 远端存在若干 student-affairs 审计/修复分支，但没有可作为本次 Orientation/Dorm Authority 的已合并 main 真值。
- 开放 PR 中与学工最接近的是 #203（审计 runner，且 base 不是 main）；其余主要为依赖升级、平台或其他中心工作。它们都不改变本次 exact-head 判断。
- 本次没有 merge、push、force push 或 PR 写操作。

## 3. Authority 判定规则

- **Authority**：业务状态只能由这一处创建/迁移/终结，其他表和端只能引用或投影。
- **Projection**：可重建、允许短暂延迟，不得反向决定 Authority。
- **Snapshot**：用于历史展示/审计，必须记录来源与生成时点，不能静默覆盖主档。
- **Duplicate truth**：两个位置都可被写入且都被消费者当作最终状态。
- **REAL**：端到端调用真实后端并由后端 Authority 裁定。
- **DISABLED**：明确不可用且没有成功假象。
- **NOT_APPLICABLE**：该角色/端不应具备该动作。

## 4. 全校 Authority Map

| 数据类 | 当前 Authority | 合法 projection/snapshot | 审计判断 |
|---|---|---|---|
| 租户 | `t_tenant` | `t_tenant_brand_config` 是租户品牌配置 | 已有，禁止前端内置租户品牌作为回退真值 |
| 学院/专业/班级 | `t_college` / `t_major` / `t_class` | 业务表名称快照 | 稳定 ID 已有；迎新仍主要存字符串，需 O1 关联 |
| 用户/RBAC | `t_user`、`t_role`、`t_permission`、`t_user_role`、`t_role_permission` | 后端 current-context、前端只读权限投影 | 已有；前端本地角色/权限矩阵不得做 Authority |
| 数据范围 | `t_role_assignment_scope` + 后端范围解析器 | current-context scope 投影 | 持久化类型与运行时 `DORM_BUILDING` 不一致；必须 fail closed |
| 学生主档 | `t_student_profile` | `t_cs_service_student` 等业务域兼容投影 | 全校学生唯一 Authority；迎新不得重复造学生 |
| 学生账号绑定 | `t_student_account_link` | 登录态/端侧会话 | 已有稳定链接，禁止姓名/手机号猜绑定 |
| 生命周期事件 | `t_student_stage_event` | 画像/时间线 | append-only Authority；迎新 finalize 应写事件 |
| 工作流定义/实例/任务 | `t_workflow_definition`、`t_workflow_node_definition`、`t_workflow_instance`、`t_workflow_task` | 域状态、页面步骤 | 统一能力已存在；宿舍调宿不应永久停留私有流程 |
| 待办 | `t_unified_todo` | 四端待办列表 | 已有；域内可写适配器，不能造第二张待办真值 |
| 消息 | `t_unified_message`、campaign/delivery/audience/outbox 系列表 | 未读数、端侧消息列表 | 已有；`t_orientation_notice_task` 是重复私有任务，不应继续扩张 |
| 文件 | `t_file_object`、asset/version/scan/binding 系列表 | 域表 file id/binding | 已有；绿色通道已接绑定，`OrientationMaterial.file_name` 不是文件 Authority |
| 导入 | `t_shared_import_batch`（现有迎新两阶段导入）及通用 `t_import_job` 体系 | 校验结果/错误行 | 已有底座，禁止另造；需统一长期 Authority 边界 |
| 导出 | `t_export_task`（现有 domain export）及通用 `t_export_job` 体系 | xlsx 文件 | 已有底座；必须传 Data Scope、用途、水印、审计 |
| 安全审计 | `t_security_audit_log` | 域审计 trail/操作历史 | 域 trail 可作业务审计投影，不得替代安全审计 |

## 5. Orientation 真值审计

### 5.1 模型与服务

| 对象 | 当前事实 | Authority 结论 |
|---|---|---|
| `t_orientation_batch` | 有批次 CRUD、批次号唯一 | 批次 Authority 已存在，但未与新生关联，O1 必须加 `batch_id` |
| `t_orientation_student` | `student_id` 可回链主档；`admission_no` 租户内唯一；学院/专业/班级主要为字符串；无 `batch_id` | 仅可作为迎新过程实例；身份和组织 Authority 属于主档/组织表 |
| `steps_json` | 读写端直接把步骤标成 DONE，`resolve_blocked` 也写 DONE | 当前是脆弱重复真值；后续应由资格/材料/缴费/住宿/报到事实投影生成 |
| `t_orientation_flow_config` | 每租户每 step 唯一，读路径会自动播种默认步骤，无版本 | 可作为草案配置，不能作为可发布、可追溯流程 Authority；O1/O2 后需版本化 |
| `t_orientation_notice_task` | INAPP 只增加 sent_count，未通过 UnifiedMessage 真投递 | 私有重复能力；应迁移到统一消息，其他通道保持 DISABLED |
| `t_orientation_material` | 只有 `file_name` 字符串 | 不是文件证据 Authority；应通过 FileBinding/版本/扫描记录 |
| `t_orientation_archive` | 只记录名称、范围、数量和 DONE | 不是不可变归档包；应复用文件/归档 manifest/export/audit |
| 宿舍字段 | `building_name`、`room_no`、`dorm_status` 可由迎新普通更新写入 | 只能做 Dorm Authority 的 projection，不得独立分配或确认入住 |
| 报到码 | 教师以 `admissionNo` 核验；学生端展示同一永久标识 | 不合格；O3 需要短期签名 token、过期、一次性/幂等消费与资格预检 |
| 报到资格 | 教师 PC 根据 blocked step/stage 在浏览器计算 | 不合格；O2/O4 需要服务端 verdict、原因、override/waiver 证据 |

### 5.2 API、权限与 Data Scope

- `orientation.py` 路由有域权限依赖，但列表服务没有用户/范围参数；租户过滤不等于 Data Scope。
- GET 使用 `studentAffairs.orientation.view`，写使用 `.manage`，导出使用 `.export`；当前学工权限注册表只登记 `.view`，而导入导出鉴权又使用 legacy `orientation.import/export`。这是权限码双轨。
- `domain_export_service._call_list()` 对 orientation 直接调用租户级列表；范围未下沉，可能越范围导出。
- `domain_import_service` 是真实两阶段 validate/confirm，但规范化只保留姓名、录取号、班级名，无法可靠绑定稳定组织 ID、批次和来源。
- 所有后续读写都必须以 tenant 条件开头，并在服务层应用 school/college/major/class/student 范围；未知范围必须返回空/403，不能退化租户全量。

### 5.3 四端消费者

- 教师 PC：真实 CRUD/批次/流程/异常/看板页面存在；import/export UI 被本地 capability 表标为 501；资格 verdict 在前端；本地品牌/角色/范围/权限有回退 Authority。
- 学生 PC：`/portal/orientation/my|collect|green-channel|print` 真实；只应操作账号稳定绑定的本人记录。
- 学生小程序：真实优先 API 存在，但代码保留可配置 mock fallback；生产构建必须 fail closed。报到码仍是 admissionNo。
- 教师小程序：真实核验 API 存在，但提交 admissionNo；O3 前只能认定为“真实接口、错误凭证模型”。

### 5.4 测试与 seed

- `test_orientation.py` 覆盖基本 CRUD、批次、流程、通知、归档和当前宿舍字符串闭环。
- `test_portal_orientation.py` 覆盖学生本人读取/提交与非学生拒绝。
- `test_orientation_dorm_init.py` 直接播种 `StudentProfile`/`OrientationStudent` 后调用初始化脚本，覆盖幂等和 dry-run；它不是从空库、名单导入开始的 Golden Journey。
- 缺失：跨租户、学院/专业/班级 Data Scope、导出范围、稳定账号绑定、重复名单、批次锁定、服务器资格、WAIVED 与 DONE 区分、签名报到码并发消费、finalize 生命周期、四端同一学生证据。
- 结论：当前测试**没有真正覆盖迎新 Golden Journey**。

## 6. Dorm 真值审计

### 6.1 模型与可靠性链路

| 对象 | 当前事实 | Authority 结论 |
|---|---|---|
| `t_affairs_dorm_building/room/bed` | 房源层级和床位唯一键已存在；`DormBed.student_id/status/version` 由可靠性服务加锁更新 | 当前房源与“当前占床” Authority，必须复用 |
| `t_affairs_dorm_transfer` | 有两节点状态、目标床、乐观版本、统一待办适配 | 调宿申请 Authority；后续应接统一 WorkflowInstance/Task，不能再造调宿表 |
| `t_affairs_dorm_check_task/record` | 有检查任务、逐房记录、异常/风险关联 | 可扩展；当前记录粒度不足以承载多检查项/供应商归寝事件的完整证据 |
| `t_cs_dorm_record` | 保存楼/房/床字符串和 IN 状态，由床位服务回写 | 兼容 projection，不是新业务 Authority；必须可从 DormStay/Bed 重建 |
| `t_cs_dorm_exception` | 宿舍异常并可关联风险 | 异常 Authority 可保留；缺少稳定楼/房/床来源字段时范围审计不完整 |
| DormStay | 不存在 | D2 确有必要：承载入住、调宿、退宿历史，保证一生一条 current stay |
| Allocation Batch | 不存在 | D2/D3 确有必要：承载排宿模式、发布、锁定、版本、来源和统计口径 |

`affairs_dorm_reliability_service` 已在事务内锁学生当前床和目标床，严格校验性别、空床、版本，并在调宿执行时先占新床再释放旧床；`checkout_guard` 要求显式版本；`transfer_scope_guard` 对辅导员和宿管做节点/范围约束。路由启动时按固定顺序安装这些覆盖，因此后续必须测试“实际路由后的函数”，不能只测未打补丁的基础 service。

### 6.2 身份、权限和范围风险

- 学工权限注册表已有 `studentAffairs.dorm.view/resource.manage/allocation.manage/transfer.create/transfer.approve/inspection.manage/inspection.input/exception.handle/import/export`。
- 运行时 scope 解析支持 `DORM_BUILDING`，调宿列表/审核未知范围会收敛为空或拒绝；这是可复用的 fail-closed 基线。
- `RoleAssignmentScope` 模型注释/约束只列 SCHOOL/COLLEGE/MAJOR/CLASS/STUDENT，和运行时范围枚举不一致。
- 楼栋仍用 `manager_teacher_key`；解析器可退回唯一真实姓名匹配。这是 name identity 风险，必须迁移到稳定 `user_id`/role assignment scope，姓名只能展示。
- `CsServiceStudent` 是域内兼容投影，禁止用姓名或字符串 student_no 代替 `StudentProfile.id` 进行跨域写入。

### 6.3 四端消费者

- 教师 PC：旧 `/dormitory` 与新 `/dorm/resource|checkin|transfer|check|exception|stats` 都存在并调用真实 API；新页功能较粗，D1 应做专业工作区而不是新造 API。
- 学生 PC：`AffairsFourEndView` 使用 `/mobile/affairs/dorm/*` 获取本人床位、候选房/床、提交调宿和查看本人申请。
- 学生小程序：`student/affairs/dorm.vue` 调真实本人宿舍与调宿接口，接口失败不会等同“0 条”；生产仍需禁止 mock fallback。
- 教师小程序：有 dorm review 真接口/页面，主要用于节点审核；D6 需补齐角色、楼栋范围和并发冲突浏览器证据。

### 6.4 测试覆盖

- 已覆盖建楼铺床、入住回写、占用/性别冲突、调宿执行、宿管最小权限、楼栋范围、跨楼写拒绝、异常风险关联、学生调宿身份纪律和覆盖安装顺序。
- 未覆盖 DormStay（尚不存在）、分配批次/发布/撤回、自选/半自动/全自动排宿模式、归寝 Provider unavailable、100/500 并发、完整退宿历史、四端同一业务状态、旧 projection 漂移自动检测。
- 结论：当前测试**没有真正覆盖宿舍 Golden Journey**，但已有并发与范围基线可复用。

## 7. 重复真值与 projection 清单

1. `OrientationStudent.college_name/major_name/class_id/class_name` 与组织表重复；组织表 ID 是 Authority。
2. `OrientationStudent.building_name/room_no/dorm_status` 与 DormBed/CsDormRecord 重复；Dorm Authority 是房源/当前床，后续历史为 DormStay。
3. `OrientationStudent.steps_json` 与材料、缴费、绿色通道、宿舍、现场报到事实重复；只能做可重建投影。
4. `OrientationNoticeTask` 与 UnifiedMessage/Campaign/Delivery 重复；统一消息是 Authority。
5. `OrientationMaterial.file_name` 与文件中心重复；FileObject/Binding/Version/Scan 是 Authority。
6. `CsDormRecord` 与 DormBed 当前占用重复；它是旧接口 projection。
7. 前端 `orientation.meta.js` 的品牌、角色、scope、权限与后端 current-context 重复；后端是 Authority。
8. orientation 权限码存在 `orientation.*` 与 `studentAffairs.orientation.*` 双轨；必须统一并保留必要兼容映射。

## 8. 历史文档 stale 清单

| 文档/事实 | stale 原因 | 使用规则 |
|---|---|---|
| `docs/03-业务模块设计/数字迎新中心/03-数字迎新API.md` | 自身标注代码优先；未反映当前 domain import/export、稳定账号和后续 Authority 设计 | 仅参考，API 以 exact-head + 本总册为准 |
| `docs/03-业务模块设计/数字迎新中心/02-数字迎新中心深化设计 V1.0.md` | V1 业务来源，不含当前统一文件/消息/账号/数据范围收口 | 只作业务来源 |
| `docs/03-业务模块设计/数字迎新中心/02A-*` 及 2026-07 施工记录 | 提交 hash、Alembic head、完成度和 501 能力事实已过时 | 不得作为当前完成证明 |
| `docs/03-业务模块设计/学工中心/施工包/宿舍与公寓-*` | 仍记录状态枚举/表粒度/范围实现“待人工确认”；部分行号与现代码漂移 | 保留业务意图，Authority 以代码和本总册为准 |
| `docs/06-开发施工与质量验收/施工记录/2026-07-12-宿舍与公寓-*` | 记录旧 head `0044_13a_psy_referral`、旧经理 key 范围与当时测试数 | 历史证据，不是 2026-09 exact-head 证据 |
| `docs/08-历史记录与归档/**` | 总导航明确“仅追溯，禁止作施工依据” | 禁止用于施工裁决 |
| 前端 `stage-b-orientation-capability-contract` | 断言 import/export 必须保持 501，而后端已有真实能力 | A1 应更新契约测试，不得让产品迎合 stale 测试 |

## 9. 后续 Schema 包必要性裁决

| 包 | 拟议变更 | 必要性 | A0 依据 |
|---|---|---|---|
| O1 | `batch_id`、稳定组织 ID、source、回填 | 必须 | 当前学生未关联批次且组织字符串化 |
| D2 | DormStay、AllocationBatch | 必须 | 当前只有瞬时床位和字符串 projection，无入住历史/分配发布 Authority |
| O2 | 名单/主档/账号/阶段关联与来源证据 | 必须但应最小化 | `student_id` 已有，须补强约束/来源，不得重复造 StudentProfile |
| D3 | 分配规则/分配项/锁定与发布状态 | 必须 | 当前没有可审计分配批次和模式 |
| O3 | 签名报到 token/消费记录/资格快照 | 必须 | admissionNo 不是安全报到码，缺并发消费证据 |
| D4 | 调宿执行/退宿历史和工作流关联字段 | 必须但复用现有 transfer | 不得重造调宿表；新增历史/执行证据和统一 workflow 关联即可 |
| O4 | 阻断、豁免、材料要求/证据、资格决策 | 必须 | 当前 resolve blocked 直接写 DONE，文件名不是证据 |
| D5 | 统计快照/一致性审计（如确需持久化） | 条件必要 | 优先实时/可重建投影；只有性能和不可变审计证据成立才加表 |
| D6/O5/X1/X2 | 四端/回归/证据 | 默认不应新增业务 Authority | 除非前序验证发现不可由现有 Authority 表达的最小缺口 |

每包都必须提供单独 revision、明确 `down_revision`、幂等回填、唯一/外键/索引、Fresh MySQL 升降级验证，并证明没有把当前 ORM 活基线当成迁移替代品。

## 10. 已有能力，明确禁止重造

- `StudentProfile`、`StudentAccountLink`、`StudentStageEvent`。
- Tenant/Org/User/RBAC/current-context 与现有 permission gate。
- WorkflowDefinition/Instance/Task、UnifiedTodo。
- UnifiedMessage campaign/delivery/outbox。
- FileObject/Asset/Version/Scan/Binding/ArchiveManifest。
- SharedImportBatch/domain import 与 ExportTask/domain export/xlsx 安全底座。
- DormBuilding/Room/Bed、DormTransfer、DormCheckTask/Record、CsDormException。
- 现有 dorm reliability/checkout/scope/node/message/projection guards。
- 教师 PC 六个宿舍路由和旧 `/dormitory` 兼容入口。
- 学生 PC/小程序本人宿舍与调宿接口。

## 11. 四端动作总判定

详细逐动作证据见 `authority-matrix.csv`。总判定：

| 端 | Orientation | Dorm |
|---|---|---|
| 教师 PC | CRUD/批次/流程/异常为 REAL；import/export 后端 REAL 但 UI DISABLED/501；资格和报到码模型不合格 | 旧入口与六页 API 均 REAL；专业驾驶舱/房态细节需 D1 |
| 学生 PC | 本人读取/采集/绿色通道/打印 REAL；签名二维码 NOT_APPLICABLE（尚未实现） | 本人床位/候选/调宿/本人申请 REAL |
| 学生小程序 | 真实 API 存在；生产 mock fallback 待封；报到码是错误凭证模型 | 本人宿舍/调宿 REAL |
| 教师小程序 | 现场核验 API REAL，但 admissionNo 模型待 O3 | 调宿审核 REAL；完整工作区待 D6 |

所有未实现动作必须保持 DISABLED 或 NOT_APPLICABLE；不得 toast 成功、不得 0 条伪装接口失败、不得回退业务 mock。

## 12. A0 Exit Gate

- exact main/head：PASS。
- single Alembic head：PASS。
- 全校 Authority/Projection/重复真值：PASS（已审计）。
- Orientation/Dorm 模型、服务、API、四端、权限、范围、测试、导入导出、seed：PASS（证据已列）。
- 历史文档 stale：PASS（已列）。
- 数据一致性：PASS FOR A0（只读检查计划已形成；未提供生产数据集，因此实数计数为 NOT_APPLICABLE）。
- 产品生产级闭环：FAIL/DEFERRED（由 A1—X2 逐包收口，不属于 A0 修改范围）。

A0 允许进入 A1；这不表示任何后续 Schema 或四端功能自动通过。
