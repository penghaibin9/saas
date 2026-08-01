# SaaS全局产品审计与商业化运营总控方案｜V6唯一代码执行版

> 仓库：`penghaibin9/saas`  
> 审计与事实冻结基线：`main` `604eb299bdaf92d81fb31ed5f150bfd583c7189f`  
> 公共文件底座：PR #25 已合并；当前静态 Alembic revision 为 `0154_file_storage_quota_reservation`  
> 日期：2026-08-01  
> 决策：采用方案 B“标准 SaaS 控制面”，目标 3～10 所稳定付费学校。  
> **V3、V4、V5 降为历史审计底稿；本目录固定五份文件是后续系统管理与平台运营唯一施工合同。**

# 0. 唯一权威与五份文件

后续只允许以以下五份文件施工：

1. `SaaS全局产品审计与商业化运营总控方案_V6唯一代码执行版.md`
2. `01_学校系统管理中心_页面施工卡_V6唯一代码执行版.md`
3. `02_SaaS平台运营中心_页面施工卡_V6唯一代码执行版.md`
4. `03_学校角色权限矩阵_V6唯一代码执行版.md`
5. `V6控制面施工卡机器索引.yaml`

权威顺序：

```text
最新 main 代码与真实 schema
→ 本文件中的事实冻结、全仓审计与最终顺序
→ 01/02/03 三份 canonical 施工合同
→ 机器索引
→ 历史文档仅供追溯
```

冲突裁决：

- 代码事实与文档冲突：以最新 `main` 代码和数据库事实为准，先更新文档再施工；
- 三份 canonical Markdown 与机器索引字段冲突：以 canonical Markdown 为准并立即修正机器索引；
- 本文件和机器索引的执行顺序必须完全一致，不允许再建立“顺序覆盖文件”；
- PR #33 只承载这五份权威文档，不承载生产代码施工。

# 1. 当前主线已经具备的真实底座

PR #25 已将以下能力合并到主线：

```text
FileObject
FileAsset / FileVersion / FileBinding
FileScanRecord / FileJob / FileUploadSession
ImportJob / ImportRowError / ExportJob
ArchiveManifest / ArchiveManifestItem
COS 上传会话与配额预留
学校数据交换任务中心
学校文件存储治理
四端 File SDK 与公共安全组件
```

因此禁止恢复以下旧表述或重复建设：

```text
等待 PR #25
未来接入公共文件底座
建议新建 ImportJob / ExportJob
建议新建 FileAsset / FileVersion / FileBinding
系统管理另造文件任务中心
平台扫描本地 uploads 目录代表全平台存储
```

## 1.1 已确认代码事实

1. 数据交换确认以 `jobId + expectedVersion` 为权威，后端支持 `Idempotency-Key`。
2. 身份导入文件先进入隔离区和安全扫描，可用后才解析 XLSX。
3. 导出与错误/凭据回执使用 `ExportJob + FileObject`，具有有效期、撤销和短时下载票据。
4. 学校端已有 `/admin/system/data-exchange` 与 `/admin/system/file-storage-governance` 真实页面。
5. 文件容量以 `FileObject` 聚合，配额预留使用持久化 `HELD` 账本。
6. 文件治理已有总配额、模块配额、保留策略、两阶段清理和法律保留。
7. 管理 PC 已有统一 File SDK，支持服务器上传、COS STS、分片、进度、暂停、恢复和取消。
8. 平台端已有 local/COS 配置、密钥脱敏保存和连接探针，但仍是“保存即生效”。
9. WorkflowDefinition、WorkflowInstance、WorkflowTask、UnifiedTodo 已存在。
10. UnifiedMessage、MessageCampaign、MessageDeliveryJob、MessageEventOutbox 已存在。
11. SecurityAuditLog 为 append-only，并有 `traceId`。
12. SYS-02 已有实施项目、配置段、安装快照、上线检查、验收与关系回滚账本。

## 1.2 专业判断，不得伪装为已完成

- `systemAdmin.file.manage` 仍同时影响治理动作和文件内容管理员判断；
- `systemAdmin.user.import` 仍承担任务查看、确认、下载和撤销等多个动作；
- 平台套餐 `storageLimitMb`、租户元数据 `usedStorageMb` 与学校 `TenantStorageQuota` 尚未形成唯一对账链；
- 平台租户列表存在逐租户统计的 N+1 与 Python 过滤；
- 租户状态存在 `t_tenant.status` 与 `TENANT_META.status/expireAt/readonly` 双源，部分异常路径默认 active；
- 内置角色代码基线、自定义角色数据库权限、临时授权 JSON 文档仍并行；
- 数据范围部分 provider 存在 `limit(500)` 后 Python 遍历；
- 平台路由仍主要依赖 `PLATFORM_SUPER_ADMIN`，未完成商务、交付、客户成功、运维和安全审计分权；
- pytest 公共夹具存在历史合同自动补齐，新卡不能只依赖包装后的旧测试证明正确。

## 1.3 尚无仓库证据证明已通过

- 真实腾讯云环境 STS 最小权限与过期验证；
- COS CORS、生命周期和 SSE 正式配置验收；
- 50MB、500MB 真实上传及跨进程续传；
- 真实 COS 跨租户对象隔离攻击测试；
- MySQL 与 COS 联合灾备恢复演练；
- 3、5、10 所学校混合负载公平使用测试；
- 平台角色分权、事件、问题、变更、工单等控制面完整落地。

# 2. 阶段 0 事实冻结

## 2.1 施工单元与覆盖分类

V6 共冻结 **37 个施工单元**：

- 21 张 SYS；
- 15 张 PLAT；
- 1 张 RBAC-09 专项卡。

覆盖分类：

- **A｜真实底座增强**：SYS-18、SYS-19、PLAT-07；
- **R｜旧权限仍生效，必须迁移**：RBAC-09；
- **B｜已有旧基础，V6 专属层未完成**：SYS-01～17、SYS-20、SYS-21；
- **C｜平台共用入口存在，V6 工作区待建**：除 PLAT-07 外的 PLAT 卡。

“共用 API、旧页面或旧服务存在”不等于该 V6 卡已完成。每张卡开工仍需核对真实 router/service/model/schema/page/api/test。

## 2.2 机器索引已校正的 canonical 路由

| 卡 | canonical 值 |
|---|---|
| SYS-01 | `/admin/system/overview`；依赖 SYS-02～SYS-21 |
| SYS-02 | `/admin/system/implementation/overview` |
| SYS-03 | `/admin/system/accounts/staff` |
| SYS-04 | `/admin/system/org` |
| SYS-07 | `/admin/system/roles?tab=members` |
| SYS-08 | `/admin/system/scopes` |
| SYS-11 | `/admin/system/config` |
| SYS-13 | `/admin/system/module-entitlements` |
| SYS-14 | `/admin/workflow/processes` |
| SYS-21 | `/admin/system/logs` |

## 2.3 Alembic 冻结事实

- 当前静态顶部 revision：`0154_file_storage_quota_reservation`；
- `down_revision`：`0153_file_storage_governance`；
- PR #25 最终验收记录证明当时为单一 head，MySQL 8 空库可升级到 0154；
- 当前 `main` merge commit 没有可直接继承的全绿状态；
- **每一张迁移卡开工前必须在最新分支重新运行 `alembic heads` 和 MySQL 空库升级，不得预写 0155。**

# 3. 主干全仓审计结论与纠错

当前仓库不是空系统，而是拥有大量真实模型、路由、状态机和四端入口的复杂单体。V6 的首要风险是权威源不唯一：

1. 租户状态双源；
2. 权限三轨；
3. 数据范围结构化规则、remark 回落和业务关系解析并存；
4. 环境变量、PlatformConfig、SysConfig、SystemJsonDoc 与代码默认值多级回退；
5. 真实路由、能力目录、navPlan 和 PlatformCapabilityView 承载页不能等同于真实完成度。

最终原则：**先收口权威解析器与安全边界，再建设工作区；先完成可回滚写侧，再建设总览和运营聚合。**

## 3.1 本轮自行纠错

1. `PLAT-02` 前移到 `PLAT-03` 前：先统一租户有效状态，消除默认 active。
2. `PLAT-15` 前移：平台高危写能力扩建前先完成职责分离。
3. `SYS-11` 前移到角色范围激活链之前：先统一有效配置。
4. `PLAT-04` 移到服务目录、学校实施和集成闭环之后。
5. `PLAT-07` 先完成受控配置代码但保持不可激活；`PLAT-12` 真实恢复与外部 COS 验收后再解锁。
6. `SYS-02` 从“规划型”纠正为“真实实施底座增强型”，禁止从零重建。
7. SYS-14、SYS-15、SYS-16、SYS-21 统一做注册、策略、ServicePolicy、证据和解释增强，禁止再建第二套 Workflow、Todo、Message、Outbox 或 Audit 公共表。

# 4. 公共底座最终所有权

| 底座 | 权威控制面 | 当前真实基础 | 业务模块只能做什么 |
|---|---|---|---|
| 账号 | 系统管理 | User、稳定身份绑定、账号导入任务 | 引用稳定主体 ID |
| 组织 | 系统管理 | 学院/专业/班级及现有任职投影 | 提供业务关系 |
| 权限 | 角色权限控制面 | Role、RolePermission、DataScopeRule | 声明权限码、范围 resolver |
| 消息 | 系统管理通信治理 | UnifiedMessage、Campaign、Outbox | 发布 eventCode 和变量 |
| 待办 | 系统管理任务治理 | UnifiedTodo、WorkflowTask | 提供产生和完成证据 |
| 文件 | 公共文件中心 | 0154 及以前文件模型、API、SDK | 材料规则、resolver、业务状态机 |
| 主数据 | 系统管理治理 + 业务 owner | 学生、教职工、组织、课程、企业等权威表 | 维护本域主数据 |
| 集成 | 系统管理 + 平台服务目录 | 现有连接/同步能力 | 提供 adapter 与映射 |
| 数据交换 | 公共数据交换中心 | ImportJob、ExportJob、FileObject | 提供 ImportSpec、确认器、导出构建器 |

# 5. 唯一最终施工顺序

以下顺序同时写入机器索引，其他历史顺序全部失效：

```text
阶段0主干全仓审计冻结
→ SYS-18
→ RBAC-09
→ PLAT-02
→ PLAT-15
→ PLAT-03
→ SYS-19
→ SYS-12
→ SYS-04
→ SYS-11
→ SYS-06
→ SYS-08
→ SYS-09
→ SYS-10
→ SYS-13
→ SYS-03
→ SYS-05
→ SYS-07
→ SYS-02
→ SYS-17
→ SYS-14
→ SYS-15
→ SYS-16
→ PLAT-08
→ SYS-20
→ PLAT-04
→ PLAT-09
→ PLAT-11
→ SYS-21
→ PLAT-07
→ PLAT-12
→ PLAT-06
→ PLAT-10
→ PLAT-13
→ PLAT-14
→ SYS-01
→ PLAT-05
→ PLAT-01
→ V6全局验收
```

## 5.1 阶段解释

1. **公共数据与跨租户安全**：SYS-18 → RBAC-09 → PLAT-02 → PLAT-15 → PLAT-03 → SYS-19。
2. **学校时间、组织与安全版本**：SYS-12 → SYS-04 → SYS-11 → SYS-06 → SYS-08 → SYS-09 → SYS-10。
3. **账号、关系与学校实施**：SYS-13 → SYS-03 → SYS-05 → SYS-07 → SYS-02 → SYS-17。
4. **学校公共横切服务**：SYS-14 → SYS-15 → SYS-16。
5. **平台交付与运行控制**：PLAT-08 → SYS-20 → PLAT-04 → PLAT-09 → PLAT-11 → SYS-21。
6. **存储、灾备与运营治理**：PLAT-07 → PLAT-12 → PLAT-06 → PLAT-10 → PLAT-13 → PLAT-14。
7. **只读聚合与经营**：SYS-01 → PLAT-05 → PLAT-01。

总览永远最后，禁止总览页面复制账号、权限、文件、任务或商业业务逻辑。

# 6. 共享文件占用矩阵

同一时间只能有一个施工分支拥有以下共享文件写权限：

| 文件 | 主要占用卡 | 锁规则 |
|---|---|---|
| `backend/app/api/v1/system.py` | SYS-01、03～17、20、21 | 单卡独占写锁 |
| `frontend/src/modules/system/api/system.api.js` | SYS-01～17、20、21 | 单卡独占写锁 |
| `backend/app/api/v1/platform.py` | PLAT-01～15 | 平台卡单卡独占写锁 |
| `frontend/src/modules/platform/api/platformControl.api.js` | PLAT-01～15 | 平台卡单卡独占写锁 |
| `backend/app/core/permissions.py` | SYS-06、09、10、PLAT-15、RBAC-09 | 权限迁移期独占 |
| `backend/app/services/data_scope_service.py` | SYS-08、09、10 | 顺序锁 08→09→10 |
| `frontend/src/modules/system/system.routes.js` | SYS-02、05、07、12 等 | 路由预约 |
| `frontend/src/modules/system/systemManagementCatalog.js` | SYS-18、SYS-19 | 两卡不得并行 |
| `frontend/src/modules/platform/platform.routes.js` | 平台新工作区 | 路由预约 |
| `backend/alembic/versions/` | 所有迁移卡 | 同时只允许一个 migration owner |
| `backend/app/api/v1/route_registration.py`、`router.py`、`models/__init__.py` | 公共注册 | 必须单卡预约 |

PR #25 文件底座保护路径默认只读，只有卡片白名单明确允许且完成相关回归才可修改。

# 7. 迁移所有者队列

实际 revision 号必须在开工时读取最新唯一 head 后分配。

| 顺序 | 卡 | 迁移裁决 |
|---:|---|---|
| 1 | SYS-18 | 优先无迁移 |
| 2 | RBAC-09 | 优先双权限兼容；结构不足时 RBAC 单一序列 |
| 3 | PLAT-02 | `M-PLAT-01`，双源对账后切读 |
| 4 | PLAT-15 | 先盘点平台账号模型，条件迁移 |
| 5 | PLAT-03 | 先做对账服务，再决定 `M-PLAT-02` |
| 6 | SYS-19 | 优先无迁移；确需结构化时独立迁移 |
| 7 | SYS-12 | `M-SYS-03` |
| 8 | SYS-04 | `M-SYS-01` |
| 9 | SYS-11 | `M-SYS-02` |
| 10 | SYS-06 | `M-RBAC-01` |
| 11 | SYS-08 | `M-RBAC-03` |
| 12 | SYS-09 | `M-RBAC-04` |
| 13 | SYS-10 | `M-RBAC-05` |
| 14 | SYS-13 | `M-SYS-04` |
| 15 | SYS-03 | 优先复用账号/身份表 |
| 16 | SYS-05 | 无迁移，registry + resolver |
| 17 | SYS-07 | `M-RBAC-02` |
| 18 | SYS-02 | 优先复用实施表 |
| 19 | SYS-17 | `M-SYS-05` |
| 20 | SYS-14 | 优先复用 workflow，仅条件扩展 |
| 21 | SYS-15 | registry/adapter 先行，条件迁移 |
| 22 | SYS-16 | registry/adapter 先行，条件策略表 |
| 23 | PLAT-08 | `M-PLAT-05` |
| 24 | SYS-20 | 先 adapter 旧 JSON，结构化迁移单独实施 |
| 25 | PLAT-04 | `M-PLAT-03` |
| 26 | PLAT-09 | `M-PLAT-06` |
| 27 | PLAT-11 | `M-PLAT-08` |
| 28 | SYS-21 | 优先复用审计表 |
| 29 | PLAT-07 | `M-PLAT-FS-01` |
| 30 | PLAT-12 | `M-PLAT-09`，只保存证据元数据 |
| 31 | PLAT-06 | 无迁移，只读运营 adapter |
| 32 | PLAT-10 | `M-PLAT-07` |
| 33 | PLAT-13 | `M-PLAT-10` |
| 34 | PLAT-14 | 优先复用控制表 |
| 35 | SYS-01 | 无迁移 |
| 36 | PLAT-05 | `M-PLAT-04` |
| 37 | PLAT-01 | 无迁移，修权威聚合 |

# 8. SYS-18 旧消费者冻结清单

## 8.1 学校端直接消费者

- `SystemDataExchangeView.vue`：列表、确认、下载、撤销；当前页汇总并使用 `window.confirm/window.prompt`。
- `SystemStudentImportView.vue`：`validateIdentity → getImport → confirmImport`。
- `SystemTeacherImportView.vue`：同上。
- `SystemMigrationView.vue`：迁移预检后调用统一确认。
- `ImportDialog.vue`：承接 DTO，禁止恢复前端 rows 权威。
- `dataExchange.api.js`：确认请求补 `Idempotency-Key`，新增 summary/errors/cancel/retry/visibility。
- `systemManagementCatalog.js`：从 `user.import` 拆为 dataExchange 原子动作。

## 8.2 教务与公共底座消费者

- `AaRosterImportExportView.vue`、`academic-file-exchange.api.js`；
- `academic_file_exchange_router.py`、`academic_file_exchange_service.py`；
- `data_exchange_confirm_service.py`：统一确认权威，只调用不重写；
- `identity_import_scan_orchestrator.py`：扫描失败或未完成禁止确认；
- `data_exchange_cleanup_service.py`；
- `migration.py` 老系统迁移 adapter。

冻结裁决：SYS-18 先建立显式 visibility 与新动作双权限兼容；随后 RBAC-09 拆权限；RBAC-09 通过后才允许 SYS-19 收口治理权限。

# 9. 单卡施工与测试规则

正确施工单位：

```text
一张卡
一个从最新 main 创建的分支
一个 Draft PR
一个迁移所有者
一份精确文件白名单
一套定向测试与必要关联回归
一次独立复审
```

硬规则：

1. 不使用 `git add -A` 或 `git add .`；
2. 不自动合并，不关闭 Draft，不直接合并 main；
3. MySQL-only，不允许 SQLite/PostgreSQL 回落；
4. 事实不清楚时输出差异报告，不猜测施工；
5. 新 V6 测试必须包含直接 service、原始 HTTP、两租户、expectedVersion、并发/幂等和旧兼容；
6. 每张卡只跑有目的的定向测试和关联回归，不做无目的全库长跑；
7. 任何扫描未完成文件不得提交、预览、下载或归档；
8. 不得通过弱化租户隔离、权限、审计或文件扫描让测试通过。

每张卡开工前必须输出：

- 当前分支、HEAD、工作区和 `alembic heads`；
- 现有 router/service/model/schema/page/api/test；
- 旧接口所有消费者；
- 复用、修改、新增、退役清单；
- 精确允许文件与禁止文件；
- 依赖 PR、迁移 owner 和共享锁；
- 测试与回滚计划。

# 10. 六个阶段闸门

## GATE-A｜SYS-19 后

- SYS-18、RBAC-09、SYS-19 联合回归；
- PLAT-02 租户状态一致性；
- PLAT-03 商业额度、学校配额、实际占用对账；
- 跨租户隔离与文件内容隐私。

## GATE-B｜SYS-10 后

- 两后端实例与 Redis；
- 草稿/审核不影响真实鉴权；
- 激活与回滚原子性；
- 缓存失效与 decisionTrace。

## GATE-C｜SYS-02 后

- 新学校完整开局；
- 组织、角色、范围、账号、模块、数据交换闭环；
- 上线验收证据。

## GATE-D｜PLAT-04 后

- 自动开通幂等；
- 失败续跑与补偿；
- 无半租户；
- 无长期明文初始密码。

## GATE-E｜PLAT-12 后

- MySQL 隔离恢复；
- FileObject 元数据恢复；
- 本地与 COS 字节 SHA-256；
- PLAT-07 真实外部 COS 激活验收。

## GATE-F｜PLAT-01 后

- 3、5、10 租户混合负载；
- 噪声租户不影响登录和审批；
- 跨租户隐私；
- 管理 PC、学生 PC、H5、微信小程序构建；
- V6 全局验收。

# 11. V6 总验收

- 五份 V6 无重复卡、重复路由权威、重复模型或顺序覆盖文件；
- 数据交换与文件治理复用主线公共底座；
- 文件治理权限不再自动授予内容访问；
- 学校配额不超过平台商业额度；
- 平台容量读取 FileObject 权威聚合；
- COS 配置必须测试、批准、激活、回滚，不再保存即切换；
- 清理执行绑定服务器预演快照；
- 数据交换具备 OWN/MODULE/TENANT 可见策略和数据库分页；
- 平台正式模式无 Mock 租户回退；
- 租户创建可恢复且状态单一解析；
- 事件、问题、变更与灾备形成真实证据；
- MySQL、Redis、多实例、四端和外部 COS 门禁通过；
- 独立复审无 P0/P1；
- 最终仍由用户决定是否合并。
