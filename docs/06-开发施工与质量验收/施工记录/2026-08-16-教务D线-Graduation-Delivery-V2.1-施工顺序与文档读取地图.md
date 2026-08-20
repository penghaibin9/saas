# 2026-08-16 教务 D 线 Graduation/Delivery V2.1 施工顺序与文档读取地图

> 固定仓库：`penghaibin9/saas`  
> 固定分支：`agent/academic-d-graduation-delivery`  
> 唯一当前施工总册：`D_教务Graduation_Delivery_当前代码精确施工总册_V2.1_20260816.md`  
> 总册原文件 SHA-256：`ec4e6f105c2df399e336a943c955e53a1a839599915c95f09de6db56fdda6d2a`  
> 创建基线：`main@414216c4a79ff035aee87d70b35572572f5c0535`

## 1. 启动事实

- `main` 启动 exact HEAD：`414216c4a79ff035aee87d70b35572572f5c0535`。
- D 线从该 exact HEAD 新建，不借用 A/B/C 或其它业务分支 HEAD。
- V2.1 原始施工总册已经完整物化到本分支；一次性传输分片与临时 workflow 已删除。
- 源文件物化 run：`31896474718`，结论 `success`；物化过程中以 SHA-256 硬校验原文件，校验不一致会直接失败。
- 纪律：Draft PR；不合并 `main`；不 force；不以 skip/xfail/ignore/mock-only 制造 Gold。

## 2. Open PR Collision Ledger

### PR #96 — Academic static closure
直接碰撞：
- `backend/app/models/academic_affairs_registry.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- 教师小程序成绩录入及 rehearsal workflow/script。

D 裁决：D-W0 不碰这些文件；后续若需要服务/模型注册，由 INT/碰撞协调后再动。

### PR #132 — Internship E-series integration
直接共享高风险面：
- `backend/app/api/v1/route_registration.py`
- `backend/app/models/__init__.py`
- 独立 Alembic lineage。

D 裁决：D-W0 不碰公共路由、模型总注册和迁移；岗位实习事实只作为毕业证据消费者，不复制实习 Authority。

### PR #133 — Control Plane Option B
直接共享高风险面：
- `backend/app/core/permissions.py`
- `backend/app/core/permission_catalog.py`
- `backend/app/models/data_exchange.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/services/identity_import_service.py`
- `backend/app/api/v1/route_registration.py`
- Alembic migrations。

D 裁决：这些均归 INT/控制面冲突区；D-W0 不修改。

## 3. INT 独占共享文件（D 默认 NO-TOUCH）

- `backend/app/api/v1/route_registration.py`
- `backend/app/core/permissions.py`
- `backend/app/core/permission_catalog.py`
- `backend/app/models/data_exchange.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/services/identity_import_service.py`
- `backend/app/modules/academic_affairs/services/__init__.py`
- `backend/app/models/academic_affairs_registry.py`
- `backend/alembic/versions/**`

若某 Wave 必须修改其中之一：先记录碰撞、冻结合同、交给 INT 单一 Owner，不在 D 线私建第二写入口。

## 4. D Authority Map

### Graduation
- `GraduationEvaluationRun`：不可变评估运行，保存规则计算事实、输入快照与 hash。
- `GraduationDecisionFact`：最终正式毕业决策事实，必须引用 exact evaluation run。
- `AaGraduationAuditResult`：仅当前工作队列/可变投影，不得成为历史真值。

### Archive
- `ArchiveManifest`：不可变归档封存证据。
- `PostArchiveCorrectionCase`：归档后的合法追加纠错，不原地改历史。

### Evaluation
- `EvaluationRecord`：正式评价答卷事实。
- `submitted_count`：统计/守卫，不得成为第二答卷真值。

### R11
- 只读真实学校完整学期验证器；不生成学生、课程、任务、名单、成绩等业务事实。
- evidence hash 绑定真实阶段。

## 5. Wave 施工顺序

| Wave | 状态 | 输入/依赖 | 当前入口 | 输出合同 |
|---|---|---|---|---|
| D-W0 Graduation Policy | `IN_PROGRESS` | 无跨线硬依赖 | `academic_affairs_graduation_immutable_service.py` + `test_aa_graduation.py` + Graduation Audit UI | D-C1 Graduation Decision Contract |
| D-W1 Archive 四态 | `READY_AFTER_W0` | D-P0-03 | archive domain policy/core/evaluator | D-C2 Archive Gate Contract |
| D-W2 R11 + SELECTABLE | `WAIT_CONTRACT` | A-C4 + B TeachingRoster Contract | semester pilot service/router/tests | D-C3 Semester Pilot Contract |
| D-W3 Evaluation + 20K | `READY_DESIGN` | 真实 MySQL 压测环境 | evaluation public service/stats/perf | 性能证据；仅 SLO 不达标才申请迁移 |
| D-W4 Migration/Outbox/Restore | `WAIT_A_W4` | A-W4 Course/Program Import | file exchange/import/outbox/storage/backup | Cutover Ledger + PITR/FileObject restore evidence |
| D-W5 INT Final Gold | `WAIT_A_B_C` | A/B/C/D contracts | exact-head full replay | R11 COMPLETED + school Gold |

## 6. D-W0 Current Fact / RED

### Current backend fact
`academic_affairs_graduation_immutable_service.academic_final()` 当前存在正式旁路：

`SYSTEM_ABNORMAL + (GRADUATED | COMPLETED)`

只要 `review_note.strip()` 长度不少于 5，就可以继续引用最新 `GraduationEvaluationRun` 并写 `GraduationDecisionFact` / 学籍终态。

### Current test fact
`backend/tests/test_aa_graduation.py` 当前把“已完成人工核验，确认异常或未知项不影响本次毕业结论”作为成功路径；`test_gr3/test_gr5/test_gr7` 都依赖该旁路。

### Current frontend fact
`frontend/src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue`：
- `final` tab 对所有 `ACADEMIC_REVIEW` 行统一显示“教务终审”。
- 详情中只看 `status === ACADEMIC_REVIEW`，即使 `overall === SYSTEM_ABNORMAL` 也显示“确认终审并写学籍”。

因此当前不是“后端单点 bug”，而是后端政策 + 测试合同 + UI 操作语义三处一致地允许假绿。

### D-W0 RED
1. `SYSTEM_ABNORMAL + 5字/普通说明 + GRADUATED` 必须 409。
2. `SYSTEM_ABNORMAL + 500字说明 + GRADUATED` 仍必须 409。
3. 无正式 approved Override 不得把 SYSTEM_ABNORMAL 伪装成普通毕业。
4. 正常 `SYSTEM_PASSED` ordinary final 必须继续成功。
5. 历史 `GraduationEvaluationRun` 永不修改。

## 7. D-C1 Graduation Decision Contract（冻结草案）

普通 `academic_final`：
- 必须存在 latest formal `GraduationEvaluationRun`；
- mutable projection `overall` 必须与 latest run 一致；
- ordinary final 的 latest run 必须 `SYSTEM_PASSED`；
- `review_note` 只能解释/留痕，不能提升 SYSTEM_ABNORMAL 为 PASS；
- `GraduationDecisionFact.evaluation_run_id` 继续引用 exact run；
- 已有 DecisionFact 继续幂等冲突保护；
- 本刀不私造 Override 表/迁移/第二 Authority。若学校制度确有特批，后续按独立、强权限、强证据、append-only 的正式 Override 合同另开施工，不复活备注旁路。

## 8. Frontend Impact Matrix — D-W0

| Backend Change | API/DTO | Consumer | UI Change | Screenshot | Real Click | Status |
|---|---|---|---|---|---|---|
| ordinary final 仅 SYSTEM_PASSED | endpoint 不改；异常 final 由历史可成功变为 409 DATA_CONFLICT | 管理 PC `AaGraduationAuditConsoleView.vue` | SYSTEM_ABNORMAL 不显示普通“确认毕业/结业”；显示先治理 blocker 的明确说明 | OPEN | OPEN | `BACKEND_AND_UI_CONSTRUCTION_OPEN` |
| review_note 不再是 bypass | DTO 暂不新增第二状态机 | 管理 PC 详情/终审队列 | 备注仍展示为证据，不再暗示“备注足够即可终审” | OPEN | OPEN | OPEN |
| formal Override 暂未建设 | N/A | Graduation Audit | 不出现伪 Override/普通通过混淆 | OPEN | OPEN | N/A until formal contract |

消费者复查待办：学生毕业进度/毕业结论消费者；不存在直接写入口的端必须在该 Wave 结束前写 N/A 原因。

## 9. UI / Visual / E2E 硬门

D-W0 不能因为 backend targeted tests 绿就标 `COMPLETED`。
必须补齐：
- SYSTEM_ABNORMAL 终审队列/详情截图；
- SYSTEM_PASSED 正常终审截图；
- 可见控件真实点击 normal final；
- abnormal 负向确认普通 final 不可点击；
- refresh 后状态一致；
- console 0 error；正式网络 0 fake mock；
- 所有证据绑定同一 exact HEAD。

未完成截图/E2E 前最高状态只能按总册分级记录，不冒充 Gold。

## 10. 后续固定入口

`D-W0 RED → 后端根因 → targeted/MySQL(如涉及) → Frontend Impact Review → UI 同步 → screenshot visual audit → real-click E2E → exact-head evidence → 回写本地图 → D-W1`

D-W2 在 A-C4/B TeachingRoster 合同冻结前只允许 RED/设计，不自造 roster 合同；D-W4 在 A-W4 输入合同冻结前不私建 Course/Program import Authority。
