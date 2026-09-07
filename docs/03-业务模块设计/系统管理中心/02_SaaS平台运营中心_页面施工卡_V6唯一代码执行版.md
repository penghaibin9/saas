# 02｜SaaS平台运营中心页面施工卡｜V6唯一代码执行版

> 仓库：`penghaibin9/saas`  
> 审计基线：`main` `604eb299bdaf92d81fb31ed5f150bfd583c7189f`  
> 日期：2026-08-01  
> 目标规模：3～10所稳定付费学校。  
> 本文件融合并取代V3/V4中的P01～P36与B-PLAT-01～12。  
> 平台默认查看租户元数据、健康、用量、异常和证据，不默认查看学校强敏感业务原文。

# 0. 平台控制面边界

```text
商业控制：产品、套餐、合同、授权、配额、计量
交付控制：租户创建、初始化、实施、迁移、上线
运行控制：公共底座、服务、事件、问题、变更、灾备、容量
客户控制：健康、工单、培训、状态通知、续费
安全控制：平台职责、临时提升、受控协助、跨租户审计
```

平台运营端不是学校系统管理的超级视图：

- 平台负责商业授权和SaaS运行；
- 学校负责本校账号、组织、角色、流程和业务配置；
- 平台不能默认替学校生成业务终态；
- 平台不能默认查看心理、资助、处分、医疗等强敏感原文；
- 受控协助必须绑定租户、范围、工单/事件和有效期。

# 1. 已确认的当前仓库入口

- `backend/app/api/v1/platform.py`
- `backend/app/services/platform_service.py`
- `backend/app/services/platform_defaults.py`
- `backend/app/models/platform.py`
- `backend/app/models/tenant.py`
- `backend/app/services/module_access_service.py`
- `frontend/src/modules/platform/platform.routes.js`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `frontend/src/modules/platform/views/control/PlatformControlTenants.vue`
- `frontend/src/modules/platform/views/control/PlatformControlTenantDetail.vue`

# 2. 15张唯一施工卡

## PLAT-01｜经营、客户成功与运行总览

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/overview |
| 代码状态 | 现有平台总览可用，但运行和存储统计口径需纠正 |
| 角色 | 平台负责人；商务、客户成功、运维按视图与字段分权 |
| 首屏结论 | 今日必须处理、30/60/90天商业风险、学校风险、公共底座和事件 |
| 当前真实入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py`<br>`frontend/src/modules/platform/views/control/PlatformControlOverview.vue`<br>`frontend/src/modules/platform/api/platformControl.api.js` |
| 依赖 | 租户、订单、FileObject治理、任务、服务、事件 |
| 迁移所有者 | 无迁移，先修权威聚合 |

### 页面与交互

三视图：经营、客户成功、运行。现有租户、账号、登录、待办和审计可复用。

V6必须替换的旧统计：

- `storageUsedMb`不能扫描本地uploads目录；
- 租户`usedStorageMb`不能长期读取TENANT_META默认值；
- 文件/扫描/配额/异常必须读取公共文件治理聚合；
- 运行视图不能在后端不可达时展示Mock租户和Mock指标。

### API、DTO与权限

`GET /api/v1/platform/overview?view=business|success|operations`

响应必须含`sourceAt/dataQuality/revision`。文件部分至少包含：

```text
totalBytes
reservedBytes
tenantQuotaViolations
scanErrors
quarantineTimeouts
cosUnverified
expiredPendingCleanup
```

权限拆分：`platform.overview.business`、`.success`、`.operations`。

### 数据、迁移与兼容

不建立第二套存储计数器。允许日快照用于趋势，但每个快照必须记录来源和对账状态。

### 精确施工白名单

- `backend/app/api/v1/platform.py`
- `backend/app/services/platform_service.py`
- `backend/app/services/platform_overview_service.py`
- `backend/app/services/file_storage_governance_service.py`（只读跨租户聚合接口）
- `frontend/src/modules/platform/views/control/PlatformControlOverview.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_platform_overview_v6.py`

禁止生产Mock回退、扫描本地目录代表全平台存储、查看学校文件原文。

### 必须执行的测试

- **PLAT01-T01**：本地和COS文件均计入FileObject容量
- **PLAT01-T02**：数字与租户下钻对账
- **PLAT01-T03**：依赖失败显示未知，不显示0
- **PLAT01-T04**：正式模式网络失败不回退Mock

### 回滚与完成定义

保留旧字段兼容一个发布周期，但UI和运营决策只使用新权威聚合。

## PLAT-02｜租户学校、生命周期与租户360

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/tenants/:tenantId |
| 代码状态 | 租户列表、详情和启停等真实存在；状态与创建原子性仍需治理 |
| 角色 | 平台负责人、交付、客户成功、运维按职责裁剪 |
| 首屏结论 | 生命周期、访问模式、套餐、到期、商业额度、学校配额、健康、阻断和下一动作 |
| 当前真实入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py`<br>`backend/app/models/tenant.py`<br>`backend/app/models/platform.py`<br>`frontend/src/modules/platform/views/control/PlatformControlTenants.vue`<br>`frontend/src/modules/platform/views/control/PlatformControlTenantDetail.vue` |
| 依赖 | PLAT-03商业对账、PLAT-04开通、PLAT-07存储配置、PLAT-09事件 |
| 迁移所有者 | M-PLAT-01，先双源对账后切换 |

### 页面与交互

详情页签：概览、合同授权、联系人/管理员、实施、存储配额、健康、用量、事件、变更、支持、审计。

必须显示：

```text
商业存储上限：套餐/租户覆盖
学校治理配额：学校在商业上限内的内部配置
实际占用：FileObject + HELD reservation
```

### API、DTO与权限

保留现有租户API，统一新增`TenantEffectiveStateResolver`。启用、停用、到期、转正式、改套餐、配额均要求reason、expectedVersion和影响预览。

### 数据、迁移与兼容

当前`t_tenant.status`与TENANT_META.status必须先生成差异报告。`tenant_status(strict=False)`不能继续在读取异常时默认active用于正式鉴权。

### 必须执行的测试

- **PLAT02-T01**：平台显示、登录和写守卫状态一致
- **PLAT02-T02**：状态源读取失败时写操作fail-closed
- **PLAT02-T03**：商业额度、学校配额和实际占用同时展示
- **PLAT02-T04**：并发状态修改一个成功一个409
- **PLAT02-T05**：N+1租户列表优化后结果不变

### 回滚与完成定义

双读对账为零后切换解析器，旧字段保留观察期，不直接删除。

## PLAT-03｜产品、套餐、合同、授权、配额与计量对账

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/commercial-control（现有packages/orders/tenant详情整合） |
| 代码状态 | 套餐、订单、功能和租户覆盖真实存在；计量/配额对账未统一 |
| 角色 | 商务、平台负责人、财务只读、技术授权管理员分权 |
| 首屏结论 | 已付未开、未授权使用、配额不一致、计量缺失、到期与收入泄漏 |
| 当前真实入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py`<br>`backend/app/services/platform_defaults.py`<br>`backend/app/services/module_access_service.py`<br>`backend/app/models/file.py` |
| 依赖 | SYS-13学校启用、SYS-19学校配额、PLAT-13实际计量 |
| 迁移所有者 | M-PLAT-02；先建立对账服务，后决定结构化迁移 |

### 唯一对账链

```text
Contract/Order
→ Package Version
→ Entitlement
→ Provisioned
→ School Enabled
→ Commercial Quota
→ School Governance Quota
→ Actual Consumption
```

当前`storageLimitMb`必须转换为字节并与`TenantStorageQuota.total_quota_bytes`和FileObject占用自动对账。

### API、DTO与权限

新增只读对账：`GET /platform/reconciliations`。
套餐/授权/额度变更必须使用expectedVersion并生成修复任务，不直接修改学校治理数据。

### 必须执行的测试

- **PLAT03-T01**：套餐20GiB、学校配额30GiB时识别为越界
- **PLAT03-T02**：套餐降级先影响预览，不能静默删除文件
- **PLAT03-T03**：未授权模块消费被发现
- **PLAT03-T04**：FileObject实际值与平台用量一致
- **PLAT03-T05**：订单标记支付与开通失败可补偿

### 回滚与完成定义

商业额度是上限，学校配额是内部分配，实际占用是事实；三者不能混为一个字段。

## PLAT-04｜租户自动开通、初始化与上线验收

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/provisioning |
| 合并取代 | P10～P13、B-PLAT-04 |
| 角色 | 交付管理员；平台负责人高危确认 |
| 首屏结论 | 运行中、失败、待补偿、超时、待学校输入和成功率 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py`<br>`backend/app/services/system_implementation_service.py` |
| 建议新增入口 | `backend/app/services/tenant_provisioning_service.py`<br>`backend/app/models/tenant_provisioning.py`<br>`frontend/src/modules/platform/views/control/PlatformProvisioningView.vue`<br>`backend/tests/test_tenant_provisioning_recovery.py` |
| 依赖 | 租户状态、商业授权、学校实施 |
| 迁移所有者 | M-PLAT-03单一所有者 |

### 页面与交互

步骤：租户→配置→品牌→角色→首位管理员→能力→存储→消息→实施项目→健康验证。
每步显示幂等键、尝试、输入输出摘要、补偿动作和traceId。

### API、DTO与权限

`POST /platform/provisioning-jobs`、`GET /{id}`、`POST /{id}/resume|retry-step|compensate|cancel`。
最终健康验证失败不能标记READY。

### 数据、迁移与兼容

条件新增`t_provisioning_job`和`t_provisioning_step_run`。状态PENDING/RUNNING/WAITING_INPUT/SUCCEEDED/FAILED/COMPENSATING/CANCELLED。
每步必须幂等或有补偿。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/platform_service.py`
- `backend/app/services/tenant_provisioning_service.py`
- `backend/app/models/tenant_provisioning.py`
- `frontend/src/modules/platform/views/control/PlatformProvisioningView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_tenant_provisioning_recovery.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_tenant_provisioning.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `多个commit拼半初始化租户`
- `长期保存明文初始密码`

### 必须执行的测试

- **PLAT04-T01**：任一步失败可续跑
- **PLAT04-T02**：重复执行不重复创建角色/管理员
- **PLAT04-T03**：补偿失败进入人工队列
- **PLAT04-T04**：健康验证失败不READY

### 回滚与完成定义

开校可重复、可恢复、有证据，不存在不可解释半租户。


## PLAT-05｜客户健康、工单、培训与续费

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/customer-success |
| 合并取代 | P14～P17、B-PLAT-12客户部分 |
| 角色 | 客户成功、平台负责人；商务看续费字段 |
| 首屏结论 | 高风险学校、工单SLA、管理员缺失、培训未完成和90天续费 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py` |
| 建议新增入口 | `backend/app/services/customer_health_service.py`<br>`backend/app/models/customer_success.py`<br>`frontend/src/modules/platform/views/control/PlatformCustomerSuccessView.vue`<br>`backend/tests/test_customer_health_seasonality.py` |
| 依赖 | 学校治理总览、事件、合同 |
| 迁移所有者 | M-PLAT-04单一所有者 |

### 页面与交互

页签：健康、成功计划、工单、培训、联系人、续费风险、公告。
健康权重随迎新、考试、实习、毕设和续费季变化；不能全年只看登录率。

### API、DTO与权限

`/platform/customer-health|success-plans|service-requests|training-status`。
健康分返回模型版本、明细和证据；人工可备注但不能无证据改分。

### 数据、迁移与兼容

条件新增`t_customer_success_plan`、`t_service_request`、`t_training_record`。工单是唯一支持入口，微信群仅作为通知渠道。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/customer_health_service.py`
- `backend/app/models/customer_success.py`
- `frontend/src/modules/platform/views/control/PlatformCustomerSuccessView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_customer_health_seasonality.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_customer_success.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `微信群聊天作为工单权威`
- `固定登录率判断所有季节健康`

### 必须执行的测试

- **PLAT05-T01**：季节模型权重可解释
- **PLAT05-T02**：工单SLA暂停恢复正确
- **PLAT05-T03**：每个付费租户有主联系人和备用管理员

### 回滚与完成定义

客户风险、任务、责任人、期限和续费动作形成闭环。


## PLAT-06｜公共底座运行中心

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/foundations |
| 代码状态 | 页面待建；文件底座已有真实运营数据可直接消费 |
| 对象 | 账号、组织、权限、消息、待办、文件、主数据、集成、数据交换 |
| 首屏结论 | 每个底座健康、版本、错误率、任务积压、受影响租户和负责人 |
| 文件真实入口 | `file_scan_service`、`file_storage_governance_service`、`file_storage_quota_reservation_service`、`data_exchange_job_service`、治理worker |
| 依赖 | PLAT-08服务目录、PLAT-09事件 |
| 迁移所有者 | 无迁移，先做只读运营适配器 |

### 文件/数据交换运营卡

平台只能看：

```text
各租户容量与增长
HELD预留
扫描错误与隔离超时
COS未核验
清理失败
Import/Export积压和失败
底座版本与worker健康
```

平台默认不能看文件名、论文、心理材料、困难证明、原始XLSX行和凭据回执。

### API与权限

`GET /platform/foundations`
`GET /platform/foundations/FILE`
`GET /platform/foundations/DATA_EXCHANGE`
`GET /platform/foundations/{code}/affected-tenants`

权限：`platform.foundation.view`、`platform.foundation.operate`分离。

### 测试

- **PLAT06-T01**：文件异常能反查受影响租户但不返回原文
- **PLAT06-T02**：worker停机和ClamAV异常进入事件候选
- **PLAT06-T03**：数据交换失败按租户聚合
- **PLAT06-T04**：普通客户成功角色只能看影响和沟通状态

### 完成定义

一个运行中心观察公共底座，不成为第二配置中心或跨租户内容浏览器。

## PLAT-07｜文件存储后端、密钥与生产环境验证

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/file-storage |
| 代码状态 | **现有真实页面和API；当前为保存即生效，V6升级为受控激活** |
| 角色 | 平台存储管理员编辑；安全复核；变更执行者激活 |
| 首屏结论 | 当前ACTIVE版本、候选版本、连接测试、外部验收、迁移进度和回滚点 |
| 当前真实入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/storage/config.py`<br>`backend/app/services/storage/production.py`<br>`backend/app/commands/migrate_files_to_cos.py`<br>`frontend/src/modules/platform/views/control/PlatformControlFileStorage.vue`<br>`frontend/src/modules/platform/api/platformControl.api.js` |
| 依赖 | PLAT-08服务目录、PLAT-11变更、PLAT-12灾备 |
| 迁移所有者 | M-PLAT-FS-01，配置版本和验证证据 |

### 当前真实能力

- local/COS可视化配置；
- 密钥写库前加密、读回脱敏；
- 保存后重置存储backend即时生效；
- COS写探针后删除测试；
- COS STS直传、服务器写入和配额预留；
- 本地到COS迁移命令和核验服务。

### V6必须修正

1. 配置状态改为`DRAFT→TESTED→APPROVED→SCHEDULED→ACTIVE→ROLLED_BACK`；
2. 保存草稿不立即`reset_backend`；
3. 测试必须针对候选配置，而不是只测试当前生效配置；
4. 激活前计算受影响服务、租户、未迁移对象和回滚能力；
5. JWT密钥不得继续兼作COS配置加密根密钥；使用独立版本化`CONFIG_ENCRYPTION_KEY`；
6. 密钥轮换保留keyVersion并支持重加密；
7. 页面中的迁移命令必须以仓库真实命令`python -m app.commands.migrate_files_to_cos ...`为准；
8. 外部验收单独展示：STS过期、CORS、生命周期、SSE、50/500MB、跨进程续传、跨租户攻击；
9. “测试连接成功”不等于“生产就绪”。

### API

```http
GET  /platform/file-storage
POST /platform/file-storage/versions
POST /platform/file-storage/versions/{id}/test
POST /platform/file-storage/versions/{id}/approve
POST /platform/file-storage/versions/{id}/activate
POST /platform/file-storage/versions/{id}/rollback
GET  /platform/file-storage/external-validations
```

现有PUT接口保留兼容，但只创建草稿，不能直接激活。

### 测试

- **PLAT07-T01**：保存草稿不改变当前backend
- **PLAT07-T02**：未测试/测试失败版本不能激活
- **PLAT07-T03**：JWT轮换不导致COS密钥不可解
- **PLAT07-T04**：激活失败自动保持旧backend
- **PLAT07-T05**：迁移命令和页面说明与仓库一致
- **PLAT07-T06**：平台人员无法读取完整Secret
- **PLAT07-T07**：外部验收未完成时显示“内部通过/外部待验”，不伪装生产就绪

### 完成定义

配置变更成为可审核、可测试、可排期、可回滚的生产变更，不再是直接开关。

## PLAT-08｜服务目录、依赖与租户影响地图

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/services |
| 合并取代 | P27、B-PLAT-06 |
| 角色 | 平台运维维护；发布/事件/安全读取 |
| 首屏结论 | P0服务、降级、无owner、单点依赖、SLO风险和近期事件 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py` |
| 建议新增入口 | `backend/app/services/service_catalog_service.py`<br>`backend/app/models/service_catalog.py`<br>`frontend/src/modules/platform/views/control/PlatformServiceCatalogView.vue`<br>`backend/tests/test_service_dependency_impact.py` |
| 依赖 | 公共底座、事件、变更 |
| 迁移所有者 | M-PLAT-05单一所有者 |

### 页面与交互

服务详情：owner、responders、approvers、依赖、SLO、runbook、监控、发布、事件和租户使用。
首版覆盖API、PC、门户、小程序、MySQL、Redis、Worker、COS、ClamAV、短信。

### API、DTO与权限

`/platform/services`、`/platform/service-dependencies`、`GET /platform/service-impact?serviceCode=&releaseId=`。

### 数据、迁移与兼容

条件新增`t_platform_service`、`t_service_dependency`、`t_service_tenant_usage`。依赖图禁止循环。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/service_catalog_service.py`
- `backend/app/models/service_catalog.py`
- `frontend/src/modules/platform/views/control/PlatformServiceCatalogView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_service_dependency_impact.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_service_catalog.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `无owner P0服务允许发布`

### 必须执行的测试

- **PLAT08-T01**：依赖循环拒绝
- **PLAT08-T02**：故障计算直接/间接受影响租户
- **PLAT08-T03**：无runbook/owner的P0服务阻断发布

### 回滚与完成定义

事件和变更通过同一服务目录计算影响。

## PLAT-09｜事件、状态页与统一学校通知

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/incidents |
| 合并取代 | P18、P17故障通知、B-PLAT-08 |
| 角色 | 事件指挥、运维、客户沟通；职责分离 |
| 首屏结论 | 当前P0/P1、受影响租户、未确认告警、更新时间和通知覆盖 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py` |
| 建议新增入口 | `backend/app/services/incident_service.py`<br>`backend/app/models/incident.py`<br>`frontend/src/modules/platform/views/control/PlatformIncidentView.vue`<br>`backend/tests/test_incident_notification_scope.py` |
| 依赖 | 服务目录、学校消息中心 |
| 迁移所有者 | M-PLAT-06单一所有者 |

### 页面与交互

时间线、影响服务、租户列表、缓解措施、负责人和学校更新。
状态：DETECTED→ACKNOWLEDGED→MITIGATING→MONITORING→RESOLVED。
站内通知必选，短信/邮件/Webhook按策略。

### API、DTO与权限

`/platform/incidents`、`/{id}/updates`、`/{id}/affected-tenants`、`POST /{id}/publish`。
外部更新与内部时间线分离，避免暴露漏洞、IP和其他租户。

### 数据、迁移与兼容

条件新增`t_incident`、`t_incident_tenant`、`t_incident_update`。
每次发布保存模板版本、受众快照、结果和失败重试。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/incident_service.py`
- `backend/app/models/incident.py`
- `frontend/src/modules/platform/views/control/PlatformIncidentView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_incident_notification_scope.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_incident.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `逐校手工复制通知`
- `外部状态页泄露内部敏感细节`

### 必须执行的测试

- **PLAT09-T01**：一次发布只给受影响租户
- **PLAT09-T02**：通知失败重试不重复
- **PLAT09-T03**：RESOLVED后可转Problem

### 回滚与完成定义

P0一次通知、持续更新、恢复和学校侧接收闭环。

## PLAT-10｜问题管理、已知错误与事故复盘

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/problems |
| 合并取代 | P29、B-PLAT-09 |
| 角色 | 问题负责人、技术负责人、平台负责人只读监督 |
| 首屏结论 | 重复事件、未定位根因、已知错误、逾期整改和再次发生 |
| 当前仓库入口 | `backend/app/api/v1/platform.py` |
| 建议新增入口 | `backend/app/services/problem_management_service.py`<br>`backend/app/models/problem_management.py`<br>`frontend/src/modules/platform/views/control/PlatformProblemView.vue`<br>`backend/tests/test_problem_postmortem_lifecycle.py` |
| 依赖 | 事件、变更 |
| 迁移所有者 | M-PLAT-07单一所有者 |

### 页面与交互

Incident负责恢复，Problem负责根因，Postmortem负责复盘和整改。
展示相似事件、workaround、根因证据、整改动作、验证和复发。

### API、DTO与权限

`/platform/problems`、`/platform/known-errors`、`/platform/postmortems`、`/platform/corrective-actions`。
事件解决不自动关闭Problem。

### 数据、迁移与兼容

条件新增`t_problem`、`t_known_error`、`t_postmortem`、`t_corrective_action`。
整改必须owner、期限、验证证据和防复发测试。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/problem_management_service.py`
- `backend/app/models/problem_management.py`
- `frontend/src/modules/platform/views/control/PlatformProblemView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_problem_postmortem_lifecycle.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_problem_management.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `用事故描述代替可验证整改`

### 必须执行的测试

- **PLAT10-T01**：事件解决后Problem仍OPEN
- **PLAT10-T02**：整改含owner/期限/证据
- **PLAT10-T03**：重复事件触发复发告警

### 回滚与完成定义

根因、已知错误、整改和防复发测试可追踪。

## PLAT-11｜变更、发布、兼容性、灰度与回滚

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/changes |
| 合并取代 | P23、P28、P31、B-PLAT-07 |
| 角色 | 变更发起、审批、执行分离；一人阶段加强控制 |
| 首屏结论 | 今日变更、待审批、高风险、冻结冲突、不兼容租户和失败变更 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py` |
| 建议新增入口 | `backend/app/services/change_management_service.py`<br>`backend/app/models/change_management.py`<br>`frontend/src/modules/platform/views/control/PlatformChangeView.vue`<br>`backend/tests/test_change_impact_and_rollback.py` |
| 依赖 | 服务目录、学校日历、CI结果作为证据 |
| 迁移所有者 | M-PLAT-08单一所有者 |

### 页面与交互

对象：代码、数据库迁移、平台配置、套餐、公共底座版本、紧急修复。
状态：DRAFT→ASSESSED→APPROVED→SCHEDULED→IMPLEMENTING→VERIFIED/FAILED/ROLLED_BACK。
影响必须列出服务、API、数据库、客户端最低版本、套餐、租户和学校关键窗口。

### API、DTO与权限

`/platform/changes`、`/platform/compatibility-checks`、`/platform/release-rollouts`、`POST /changes/{id}/start|verify|fail|rollback`。
平台只记录Git SHA/PR/CI证据，不直接执行GitHub合并。

### 数据、迁移与兼容

条件新增`t_change_request`、`t_change_impact`、`t_change_execution`、`t_maintenance_window`。
考试、迎新、成绩发布、实习检查和答辩可配置冻结窗口。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/change_management_service.py`
- `backend/app/models/change_management.py`
- `frontend/src/modules/platform/views/control/PlatformChangeView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_change_impact_and_rollback.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_change_management.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `运营页面直接合并PR`
- `不兼容租户仍全量发布`

### 必须执行的测试

- **PLAT11-T01**：发布前列出服务和租户影响
- **PLAT11-T02**：冻结窗口阻断普通变更
- **PLAT11-T03**：灰度失败停止扩展并回滚
- **PLAT11-T04**：不可逆迁移有替代恢复方案

### 回滚与完成定义

每次生产变更有评估、批准、执行、验证和回滚证据。

## PLAT-12｜备份、恢复验证与灾备

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/disaster-recovery |
| 合并取代 | P30、B-PLAT-10 |
| 角色 | 运维发起测试，安全/平台负责人查看；生产恢复高危审批 |
| 首屏结论 | 最近备份、RPO偏差、最后恢复验证、RTO演练和失败项 |
| 当前仓库入口 | `backend/app/api/v1/platform.py` |
| 建议新增入口 | `backend/app/services/disaster_recovery_service.py`<br>`backend/app/models/disaster_recovery.py`<br>`frontend/src/modules/platform/views/control/PlatformDisasterRecoveryView.vue`<br>`backend/tests/test_restore_verification_workflow.py` |
| 依赖 | 备份脚本、FileObject/ArchiveManifest清单、COS对象核验和PLAT-07配置版本 |
| 迁移所有者 | M-PLAT-09，仅证据元数据 |

### 页面与交互

备份成功和恢复验证成功分开。测试恢复必须选择隔离目标、恢复点、数据集、核对规则和销毁计划。
页面不得允许手工填写“恢复成功”代替真实任务。

### API、DTO与权限

`/platform/backups`、`POST /platform/restore-tests`、`GET /restore-tests/{id}`、`/platform/dr-plans`。

### 数据、迁移与兼容

条件新增`t_backup_evidence`、`t_restore_test_run`、`t_restore_check_result`。
不保存备份内容和密钥，只保存位置引用、校验和、时间、结果和证据。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/disaster_recovery_service.py`
- `backend/app/models/disaster_recovery.py`
- `frontend/src/modules/platform/views/control/PlatformDisasterRecoveryView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_restore_verification_workflow.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_disaster_recovery.py`
- `ops/restore-test/<NEW_ISOLATED_SCRIPTS_ONLY>`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `backend/app/services/file_service.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/modules/graduation/services/graduation_material_center_service.py`
- `backend/app/modules/graduation/routers/graduation_material_center.py`
- `backend/app/modules/academic_affairs/routers/academic_file_exchange_router.py`
- `backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py`
- `backend/app/modules/academic_affairs/services/academic_file_exchange_service.py`
- `frontend/src/modules/academicAffairs/api/academic-file-exchange.api.js`
- `frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue`
- `docs/architecture/file-capability-inventory.yaml`
- `docs/architecture/file-capability-inventory.d/`
- `.github/workflows/file-capability-inventory.yml`
- `.github/workflows/academic-file-exchange-center.yml`
- `手工录入成功代替恢复`
- `测试恢复连接生产业务库`

### 必须执行的测试

- **PLAT12-T01**：MySQL恢复到隔离库并核对关键表
- **PLAT12-T02**：文件对象抽样SHA-256一致
- **PLAT12-T03**：失败状态和证据保留
- **PLAT12-T04**：隔离环境按计划销毁

### 回滚与完成定义

至少一次自动化MySQL+FileObject元数据+本地/COS字节恢复验证；外部COS验收未完成前不得标记灾备就绪。

## PLAT-13｜租户用量、容量、成本与公平使用

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/fair-use |
| 合并取代 | P19/P20、P33、B-PLAT-11 |
| 角色 | 运维、平台负责人；商务只看套餐摘要 |
| 首屏结论 | Top消耗租户、超阈值、异常增长、限流、共享资源影响和成本 |
| 当前仓库入口 | `backend/app/services/platform_service.py`<br>`backend/app/api/v1/platform.py` |
| 建议新增入口 | `backend/app/services/tenant_metering_service.py`<br>`backend/app/services/fair_use_service.py`<br>`backend/app/models/tenant_metering.py`<br>`frontend/src/modules/platform/views/control/PlatformFairUseView.vue`<br>`backend/tests/test_fair_use_core_service_protection.py` |
| 依赖 | PLAT-03商业对账、FileObject实时聚合、HELD预留、Import/Export/FileJob和服务指标 |
| 迁移所有者 | M-PLAT-10单一所有者 |

### 页面与交互

指标：RPS、并发、DB时间、队列、导出、上传、扫描、短信、存储、活跃账号。
核心登录/认证/审批优先于大导出、统计和扫描；所有限流动作可解释并审计。

### API、DTO与权限

`/platform/meters`、`/platform/fair-use/policies|violations`、`POST /platform/fair-use/actions`。

### 数据、迁移与兼容

条件新增`t_tenant_meter_daily`、`t_tenant_fair_use_policy`、`t_tenant_fair_use_violation/action`。
日聚合可追溯到原始指标，不跨租户泄露明细。

### 精确施工白名单

允许修改：

- `backend/app/services/platform_service.py`
- `backend/app/api/v1/platform.py`
- `backend/app/services/tenant_metering_service.py`
- `backend/app/services/fair_use_service.py`
- `backend/app/models/tenant_metering.py`
- `frontend/src/modules/platform/views/control/PlatformFairUseView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_fair_use_core_service_protection.py`
- `backend/alembic/versions/<NEXT_SINGLE_OWNER>_tenant_metering.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `backend/app/services/file_service.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/modules/graduation/services/graduation_material_center_service.py`
- `backend/app/modules/graduation/routers/graduation_material_center.py`
- `backend/app/modules/academic_affairs/routers/academic_file_exchange_router.py`
- `backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py`
- `backend/app/modules/academic_affairs/services/academic_file_exchange_service.py`
- `frontend/src/modules/academicAffairs/api/academic-file-exchange.api.js`
- `frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue`
- `docs/architecture/file-capability-inventory.yaml`
- `docs/architecture/file-capability-inventory.d/`
- `.github/workflows/file-capability-inventory.yml`
- `.github/workflows/academic-file-exchange-center.yml`
- `静默删除学校数据`
- `单租户大任务拖慢全平台登录`

### 必须执行的测试

- **PLAT13-T01**：大导出限流但登录审批保持SLO
- **PLAT13-T02**：临时提升有到期审计
- **PLAT13-T03**：套餐配额与meter对账

### 回滚与完成定义

3/5/10租户混合负载证明噪声租户不拖慢核心链路。

## PLAT-14｜数据治理、集成目录与合规证据

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/governance |
| 合并取代 | P21、P25/P26、P35/P36、B-PLAT-12治理部分 |
| 角色 | 平台安全、数据治理、审计；默认只看元数据和证据 |
| 首屏结论 | 无owner数据域、接口失败、证据过期、权限复核缺失和安全整改 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/services/platform_service.py` |
| 建议新增入口 | `backend/app/services/platform_governance_service.py`<br>`frontend/src/modules/platform/views/control/PlatformGovernanceView.vue`<br>`backend/tests/test_platform_governance_privacy.py` |
| 依赖 | 学校主数据、系统审计、服务目录、DR、公共文件底座 |
| 迁移所有者 | 优先复用各控制表 |

### 页面与交互

页签：数据域/API/事件目录、数据责任、跨租户审计、证据、留存、例外。
平台看数量、状态、owner、SLA和契约，不默认查看学校原文。

### API、DTO与权限

`/platform/data-governance`、`/platform/integration-catalog`、`/platform/compliance-evidence`、`/platform/cross-tenant-audit`。

### 数据、迁移与兼容

以目录和证据引用为主。强敏感内容仅在受控协助会话中按最小范围访问。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/services/platform_governance_service.py`
- `frontend/src/modules/platform/views/control/PlatformGovernanceView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_platform_governance_privacy.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `backend/app/services/file_service.py`
- `backend/app/services/data_exchange_confirm_service.py`
- `backend/app/modules/graduation/services/graduation_material_center_service.py`
- `backend/app/modules/graduation/routers/graduation_material_center.py`
- `backend/app/modules/academic_affairs/routers/academic_file_exchange_router.py`
- `backend/app/modules/academic_affairs/routers/academic_affairs_bundle.py`
- `backend/app/modules/academic_affairs/services/academic_file_exchange_service.py`
- `frontend/src/modules/academicAffairs/api/academic-file-exchange.api.js`
- `frontend/src/modules/academicAffairs/views/AaRosterImportExportView.vue`
- `docs/architecture/file-capability-inventory.yaml`
- `docs/architecture/file-capability-inventory.d/`
- `.github/workflows/file-capability-inventory.yml`
- `.github/workflows/academic-file-exchange-center.yml`
- `平台超级管理员默认读取全部强敏感材料`

### 必须执行的测试

- **PLAT14-T01**：普通运维看不到强敏感原文
- **PLAT14-T02**：跨租户审计字段脱敏
- **PLAT14-T03**：证据过期生成整改任务

### 回滚与完成定义

元数据治理、跨租户隐私边界和合规证据可验证。

## PLAT-15｜平台人员职责、临时提升与受控协助

| 项目 | V6唯一合同 |
|---|---|
| 唯一正式路由 | /admin/platform/access |
| 合并取代 | P16、P24及平台权限增补 |
| 角色 | 平台负责人管理职责；安全审计监督 |
| 首屏结论 | 永久高权、临时提升、受控协助、职责冲突和过期权限 |
| 当前仓库入口 | `backend/app/api/v1/platform.py`<br>`backend/app/core/permissions.py` |
| 建议新增入口 | `backend/app/services/platform_access_governance_service.py`<br>`frontend/src/modules/platform/views/control/PlatformAccessView.vue`<br>`backend/tests/test_platform_control_plane_access.py` |
| 依赖 | 平台角色独立于学校角色 |
| 迁移所有者 | 条件迁移，先盘点平台账号模型 |

### 页面与交互

平台负责人、商务、交付、客户成功、运维、安全审计六类职责。
高权默认临时提升；受控协助必须绑定租户、范围、事件/工单、期限并显示全程横幅。

### API、DTO与权限

`/platform/access-assignments`、`/platform/elevation-sessions`、`/platform/support-sessions`、`/platform/access-reviews`。

### 数据、迁移与兼容

需要时建立平台角色分配有效期、提升会话和支持会话表；不得复用学校角色编码。

### 精确施工白名单

允许修改：

- `backend/app/api/v1/platform.py`
- `backend/app/core/permissions.py`
- `backend/app/services/platform_access_governance_service.py`
- `frontend/src/modules/platform/views/control/PlatformAccessView.vue`
- `frontend/src/modules/platform/api/platformControl.api.js`
- `backend/tests/test_platform_control_plane_access.py`

禁止修改：

- `任何未在本卡白名单中的业务模块文件`
- `使用 git add -A 或 git add .`
- `直接合并 main、关闭Draft或开启自动合并`
- `通过弱化租户隔离、权限、审计、文件扫描让测试通过`
- `未读取当前 alembic heads 就写死迁移编号`
- `平台角色与学校角色混用`
- `无工单/事件进入学校数据`

### 必须执行的测试

- **PLAT15-T01**：商务无权改技术授权或看敏感日志
- **PLAT15-T02**：临时提升自动到期
- **PLAT15-T03**：协助只访问批准租户和范围

### 回滚与完成定义

平台不再长期依赖单一超级管理员，所有越权协助可追踪。
# 3. 逻辑迁移序列（从0154之后运行时分配）

```text
M-PLAT-01 租户有效状态
M-PLAT-02 商业授权与计量基础
M-PLAT-03 自动开通
M-PLAT-04 客户成功
M-PLAT-FS-01 文件存储配置版本与验证证据
M-PLAT-05 服务目录
M-PLAT-06 事件
M-PLAT-07 问题与复盘
M-PLAT-08 变更管理
M-PLAT-09 灾备证据
M-PLAT-10 租户计量与公平使用
```

平台迁移与系统管理、角色权限、公共文件底座迁移必须串行预约。

# 4. 生产级测试拓扑

除学校系统管理拓扑外，增加：

```text
3租户、5租户、10租户混合数据
单租户大导出/扫描/同步任务
平台角色分权账号
隔离恢复MySQL实例
状态通知测试渠道
发布灰度租户组
```

必须验证：

1. 租户停用、到期、只读、转正式；
2. 合同、授权、开通、启用、消费对账；
3. 自动开通中途失败和恢复；
4. 服务故障的租户影响计算；
5. P0事件一次通知；
6. 问题与事件生命周期分离；
7. 发布兼容检查和灰度回滚；
8. MySQL与文件真实恢复；
9. 噪声租户不拖慢登录和审批；
10. 平台普通角色看不到强敏感原文；
11. 受控协助自动到期；
12. 平台页面无演示数据回退。

# 5. 平台单卡完成定义

除通用完成定义外，还必须满足：

- 指标可下钻并对账；
- 所有租户影响可以解释；
- 高危动作有学校通知；
- 事件、问题和变更严格分离；
- 备份成功与恢复验证成功分开展示；
- 平台运营页面不能直接合并GitHub PR；
- 平台角色与学校角色逻辑和数据边界分离；
- 任何跨租户查询均有用途和审计。

# 6. 核心MySQL DDL模板

> 执行前必须schema diff；以下表是目标字段合同，不是要求无条件全部新建。

```sql
CREATE TABLE t_provisioning_job (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NULL,
  job_code VARCHAR(64) NOT NULL,
  requested_tenant_code VARCHAR(64) NOT NULL,
  status VARCHAR(24) NOT NULL,
  current_step VARCHAR(64) NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  input_json JSON NOT NULL,
  result_json JSON NULL,
  error_code VARCHAR(64) NULL,
  error_message VARCHAR(2000) NULL,
  requested_by BIGINT NOT NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  started_at DATETIME(6) NULL,
  finished_at DATETIME(6) NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_provisioning_job_code (job_code),
  UNIQUE KEY uk_provisioning_idempotency (idempotency_key),
  KEY idx_provisioning_status_time (status, created_at)
) ENGINE=InnoDB;

CREATE TABLE t_provisioning_step_run (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  job_id BIGINT NOT NULL,
  step_code VARCHAR(64) NOT NULL,
  attempt_no INT NOT NULL DEFAULT 1,
  status VARCHAR(24) NOT NULL,
  input_hash VARCHAR(128) NOT NULL,
  output_json JSON NULL,
  error_code VARCHAR(64) NULL,
  error_message VARCHAR(2000) NULL,
  compensation_status VARCHAR(24) NULL,
  started_at DATETIME(6) NULL,
  finished_at DATETIME(6) NULL,
  UNIQUE KEY uk_provisioning_step_attempt (job_id, step_code, attempt_no),
  KEY idx_provisioning_step_status (job_id, status)
) ENGINE=InnoDB;

CREATE TABLE t_platform_service (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  service_code VARCHAR(64) NOT NULL,
  service_name VARCHAR(128) NOT NULL,
  service_tier VARCHAR(16) NOT NULL,
  owner_user_id BIGINT NULL,
  owner_role_code VARCHAR(64) NOT NULL,
  responder_json JSON NOT NULL,
  approver_json JSON NOT NULL,
  slo_json JSON NOT NULL,
  runbook_url VARCHAR(500) NULL,
  status VARCHAR(24) NOT NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_platform_service_code (service_code),
  KEY idx_platform_service_owner_status (owner_role_code, status)
) ENGINE=InnoDB;

CREATE TABLE t_service_dependency (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  upstream_service_id BIGINT NOT NULL,
  downstream_service_id BIGINT NOT NULL,
  dependency_type VARCHAR(32) NOT NULL,
  criticality VARCHAR(16) NOT NULL,
  description VARCHAR(1000) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_service_dependency (upstream_service_id, downstream_service_id, dependency_type),
  KEY idx_dependency_downstream (downstream_service_id)
) ENGINE=InnoDB;

CREATE TABLE t_incident (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  incident_code VARCHAR(64) NOT NULL,
  title VARCHAR(300) NOT NULL,
  severity VARCHAR(8) NOT NULL,
  status VARCHAR(24) NOT NULL,
  commander_user_id BIGINT NOT NULL,
  primary_service_id BIGINT NULL,
  internal_summary VARCHAR(4000) NOT NULL,
  external_summary VARCHAR(2000) NULL,
  detected_at DATETIME(6) NOT NULL,
  acknowledged_at DATETIME(6) NULL,
  resolved_at DATETIME(6) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_incident_code (incident_code),
  KEY idx_incident_status_severity (status, severity, detected_at)
) ENGINE=InnoDB;

CREATE TABLE t_incident_tenant (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  incident_id BIGINT NOT NULL,
  tenant_id BIGINT NOT NULL,
  impact_level VARCHAR(16) NOT NULL,
  impact_json JSON NOT NULL,
  notification_status VARCHAR(24) NOT NULL,
  last_notified_at DATETIME(6) NULL,
  UNIQUE KEY uk_incident_tenant (incident_id, tenant_id),
  KEY idx_incident_tenant_notify (tenant_id, notification_status)
) ENGINE=InnoDB;

CREATE TABLE t_change_request (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  change_code VARCHAR(64) NOT NULL,
  change_type VARCHAR(32) NOT NULL,
  title VARCHAR(300) NOT NULL,
  status VARCHAR(24) NOT NULL,
  risk_level VARCHAR(16) NOT NULL,
  source_ref VARCHAR(300) NULL,
  planned_start_at DATETIME(6) NULL,
  planned_end_at DATETIME(6) NULL,
  rollback_plan TEXT NOT NULL,
  compatibility_status VARCHAR(24) NOT NULL,
  requested_by BIGINT NOT NULL,
  approved_by BIGINT NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_change_code (change_code),
  KEY idx_change_status_schedule (status, planned_start_at)
) ENGINE=InnoDB;

CREATE TABLE t_restore_test_run (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  run_code VARCHAR(64) NOT NULL,
  backup_ref VARCHAR(500) NOT NULL,
  target_environment VARCHAR(128) NOT NULL,
  status VARCHAR(24) NOT NULL,
  rpo_seconds BIGINT NULL,
  rto_seconds BIGINT NULL,
  check_summary_json JSON NULL,
  evidence_file_id BIGINT NULL,
  started_by BIGINT NOT NULL,
  started_at DATETIME(6) NULL,
  finished_at DATETIME(6) NULL,
  destroyed_at DATETIME(6) NULL,
  version INT NOT NULL DEFAULT 1,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_restore_run_code (run_code),
  KEY idx_restore_status_time (status, started_at)
) ENGINE=InnoDB;

CREATE TABLE t_tenant_meter_daily (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  tenant_id BIGINT NOT NULL,
  metric_date DATE NOT NULL,
  meter_code VARCHAR(64) NOT NULL,
  quantity DECIMAL(20,6) NOT NULL,
  unit VARCHAR(32) NOT NULL,
  source_revision VARCHAR(128) NOT NULL,
  source_hash VARCHAR(128) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  UNIQUE KEY uk_tenant_meter_day (tenant_id, metric_date, meter_code),
  KEY idx_meter_code_date (meter_code, metric_date),
  KEY idx_meter_tenant_date (tenant_id, metric_date)
) ENGINE=InnoDB;
```

执行规则：

- 服务依赖写入前必须检测循环；
- 事件外部摘要与内部摘要分列；
- 计量记录可重算且必须防重复；
- 恢复测试表只存证据元数据，不存备份内容或密钥；
- 变更记录只引用Git/CI证据，不允许运营页面直接改仓库；
- 所有平台高危写操作必须expectedVersion、reason、audit、affectedTenants。
