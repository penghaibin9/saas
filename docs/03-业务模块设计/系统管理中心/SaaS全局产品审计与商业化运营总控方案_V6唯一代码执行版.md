# SaaS全局产品审计与商业化运营总控方案｜V6唯一代码执行版

> 仓库：`penghaibin9/saas`  
> 审计基线：`main` `604eb299bdaf92d81fb31ed5f150bfd583c7189f`  
> 公共文件底座：PR #25已合并，最终分支HEAD `87ad57b7e21c00ca93ab2e790db90f353c4387d0`，合并提交即当前基线  
> 当前Alembic已知单一head：`0154_file_storage_quota_reservation`  
> 日期：2026-08-01  
> 决策：继续采用方案B“标准SaaS控制面”，目标3～10所稳定付费学校。  
> **V3、V4、V5全部降为历史审计底稿；V6五份文件是后续系统管理与平台运营唯一施工合同。**

# 0. 第四轮代码复审结论

公共文件底座已经把V5中最大的一项外部依赖变成真实代码基线：

```text
FileObject
FileAsset / FileVersion / FileBinding
FileScanRecord / FileJob / FileUploadSession
ImportJob / ImportRowError / ExportJob
ArchiveManifest / ArchiveManifestItem
COS上传会话与配额预留
学校数据交换任务中心
学校文件存储治理
四端File SDK与公共安全组件
```

因此V6不再允许出现以下旧表述：

```text
等待PR #25
未来接入公共文件底座
建议新建ImportJob/ExportJob
建议新建FileAsset/FileVersion/FileBinding
系统管理另造文件任务中心
平台按本地uploads目录估算全局存储
```

# 1. 已确认事实、推测与未证实项

## 1.1 已确认代码事实

1. PR #25已合并至`main`，阶段0～10进入正式主线。
2. 数据交换确认以`jobId + expectedVersion`为权威，后端支持`Idempotency-Key`。
3. 身份导入先进入隔离区和安全扫描，文件可用后才进行路径型XLSX解析。
4. 导出与错误/凭据回执使用`ExportJob + FileObject`，具有有效期、撤销和一次性下载票据。
5. 学校端已有`/admin/system/data-exchange`真实页面。
6. 学校端已有`/admin/system/file-storage-governance`真实页面。
7. 文件容量由`FileObject`实时聚合；配额预留使用持久化HELD账本。
8. 文件治理支持总配额、模块配额、保留策略、两阶段清理和法律保留。
9. 管理PC已有统一File SDK，并支持服务器上传、COS STS、分片、进度、暂停、恢复和取消。
10. 平台端已有本地/COS配置页面、密钥脱敏保存和连接探针。

## 1.2 根据代码作出的专业判断

以下是代码推论，不是已完成事实：

- 公共文件底座已经可作为系统管理和平台运营的正式依赖；
- 当前学校文件治理权限仍过粗，`systemAdmin.file.manage`同时影响治理动作和文件管理员能力；
- 平台套餐`storageLimitMb`、租户元数据`usedStorageMb`和学校`TenantStorageQuota`尚未形成唯一对账链；
- 平台总览仍扫描本地上传目录，不能代表COS和FileObject真实用量；
- 平台COS配置“保存即生效”，缺少测试通过、影响预览、排期激活和回滚；
- 数据交换列表按当前操作人过滤且在Python合并分页，可能不符合“学校管理员看全校任务”和规模化查询要求。

## 1.3 尚无仓库证据证明已完成

V6不会把以下内容写成已经通过：

- 真实腾讯云环境STS最小权限与过期验证；
- COS CORS、生命周期和SSE正式配置验收；
- 50MB、500MB真实上传及跨进程续传；
- 真实COS跨租户对象隔离攻击测试；
- MySQL与COS联合灾备恢复演练；
- 3、5、10所学校混合负载公平使用测试；
- 平台角色分权、事件、问题、变更、工单等控制面已经真实落地。

# 2. 合并后新增的八个P0/P1裁决

| 优先级 | 裁决 | 原因 | V6承载 |
|---|---|---|---|
| P0 | 文件治理权与文件内容权分离 | `systemAdmin.file.manage`过宽 | SYS-19、RBAC-09 |
| P0 | 平台存储额度与学校配额唯一对账 | 当前存在套餐、元数据、治理配额三种口径 | PLAT-03、PLAT-13 |
| P0 | 平台存储指标改读FileObject权威聚合 | 本地目录无法覆盖COS | PLAT-01、PLAT-06、PLAT-13 |
| P0 | COS配置改为测试后激活 | 当前保存即重置后端并生效 | PLAT-07、PLAT-11 |
| P0 | 清理预演必须与执行绑定 | 当前客户端只保存预览结果 | SYS-19 |
| P1 | 数据交换补幂等头、全校可见策略和DB分页 | 当前前端未发幂等头，列表按操作人过滤并Python分页 | SYS-18、RBAC-09 |
| P1 | 租户创建和生命周期单一状态源 | 仍存在多提交与双状态源 | PLAT-02、PLAT-04 |
| P1 | 正式平台控制面禁用网络失败Mock回退 | 否则生产故障可能显示演示学校 | PLAT-01、PLAT-15 |

# 3. V6文档关系

```text
00 全局总控
01 学校系统管理：21张canonical card
02 平台运营：15张canonical card
03 学校角色权限：22固定角色 + 6自动业务身份 + 9个治理包
V6控制面施工卡机器索引.yaml
公共文件底座：main内正式基础设施，不再是外部Draft依赖
```

# 4. 公共底座最终所有权

| 底座 | 权威控制面 | 当前真实基础 | 业务模块只能做什么 |
|---|---|---|---|
| 账号 | 系统管理 | User、稳定身份绑定、账号导入任务 | 引用稳定主体ID |
| 组织 | 系统管理 | 学院/专业/班级及现有任职投影 | 提供业务关系 |
| 权限 | 角色权限控制面 | Role、RolePermission、DataScopeRule | 声明权限码、范围解析器 |
| 消息 | 系统管理通信治理 | 现有消息/待办服务 | 发布业务事件和变量 |
| 待办 | 系统管理任务治理 | UnifiedTodo/WorkflowTask等现有能力 | 提供产生和完成证据 |
| 文件 | 公共文件中心 | 0154及以前文件中心模型、API、SDK | 材料规则、resolver、业务状态机 |
| 主数据 | 系统管理治理+业务owner | 学生、教职工、组织、课程、企业等权威表 | 维护本域主数据 |
| 集成 | 系统管理+平台服务目录 | 现有连接/同步能力 | 提供adapter与映射 |
| 数据交换 | 公共数据交换中心 | ImportJob/ExportJob/FileObject | 提供ImportSpec、确认器、导出构建器 |

# 5. V6施工成功率口径

V6仍不承诺“一次把五份文件交给AI就有90%成功率”。

| 执行方式 | 工程估算 |
|---|---:|
| 五份V6一次全做 | 25%～40% |
| 单卡但不重新核对HEAD | 55%～70% |
| 单卡+现状扫描+白名单+真实MySQL | 78%～88% |
| 单卡+完整V6闸门+独立复审 | 85%～92% |

公共底座已合并会降低重复建设和迁移冲突风险，但权限、安全激活、租户状态、配置生效、灾备和多实例缓存仍必须独立复审。

# 6. 更新后的施工顺序

```text
阶段0  控制面事实冻结与公共底座消费矩阵
阶段1  文件/数据交换权限收口与平台容量权威化
阶段2  学期、配置、模块启用和学校治理总览
阶段3  角色、范围、DENY、安全激活和访问解释
阶段4  账号、组织、任职、业务关系和主数据
阶段5  消息、待办、任务、集成和审计
阶段6  租户状态、商业授权、自动开通和客户成功
阶段7  服务、COS配置激活、事件、问题、变更
阶段8  灾备恢复、公平使用、合规和平台人员权限
```

## 6.1 第一批建议施工卡

先做能够消除公共底座合并后不一致的卡：

```text
SYS-18 数据交换任务中心增强
SYS-19 文件存储治理增强
RBAC-09 文件与数据交换权限包
PLAT-03 套餐/授权/配额/计量对账
PLAT-06 公共底座运行中心
PLAT-07 文件存储后端与生产验证
```

但仍然一次只施工一张卡。

# 7. 分支与迁移规则

建议第一阶段：

```text
audit/v6-control-plane-fact-freeze
feat/v6-data-exchange-governance
feat/v6-file-storage-governance
feat/v6-file-data-permissions
feat/v6-platform-storage-reconciliation
```

硬规则：

1. 每个分支从最新`main`创建；
2. 开始前确认`alembic heads`只有一个；
3. 当前已知head为`0154_file_storage_quota_reservation`，新编号必须运行时分配，V6不写死`0155`；
4. `route_registration.py`、`router.py`、`models/__init__.py`、`system.routes.js`、`systemManagementCatalog.js`、`platform.routes.js`、Alembic目录属于预约文件；
5. 一个时间点只有一个分支拥有公共预约文件和迁移head；
6. 不使用`git add -A`；
7. 保持Draft，不自动合并，不合并main，除非用户明确确认。

# 8. 公共文件底座不可破坏合同

任何系统管理或平台运营施工都必须保留：

- 普通上传权威入口`POST /api/v1/files`；
- 对象授权失败统一404；
- 扫描未完成不得业务提交、预览、下载或归档；
- `FileObject`物理对象不可覆盖；
- 业务重交使用`FileVersion`；
- 业务关联使用`FileBinding`和resolver；
- 导入确认只信任服务端Job；
- 生成文件进入`ExportJob + FileObject`；
- 归档Manifest引用不可变版本和SHA-256；
- 配额判断包含HELD reservation；
- 业务Router不得重新直接构造不受控FileResponse；
- 模块新增文件能力必须更新文件能力清单和门禁。

# 9. 统一测试环境

```text
MySQL 8
Redis
backend-web A
backend-web B
file worker
任务 worker
ClamAV
本地存储测试后端
COS fake client仅用于单测
真实COS预生产环境用于外部验收
教师/管理PC
学生PC
H5与微信小程序
```

每张相关卡至少验证：

1. 跨租户；
2. 当前角色和数据范围；
3. 文件扫描状态；
4. expectedVersion；
5. Idempotency-Key；
6. 两实例并发；
7. 配额预留竞争；
8. 缓存失效；
9. 失败/空/无权限/冲突态；
10. 旧接口兼容；
11. Alembic空库和当前主线升级；
12. 独立AI复审。

# 10. V6总验收闸门

- 五份V6无重复卡、重复路由权威和重复模型；
- 数据交换与文件治理直接复用主线公共底座；
- 文件治理权限不再自动授予内容访问；
- 学校配额不超过平台商业额度；
- 平台使用FileObject权威容量；
- COS配置必须测试、激活、回滚，不再保存即切换；
- 清理执行绑定服务器预演快照；
- 数据交换具备OWN/TENANT可见策略和DB分页；
- 平台正式模式无Mock租户回退；
- 租户创建可恢复且状态单一解析；
- 事件、问题、变更和灾备形成真实证据；
- 全部真实MySQL、Redis、多实例、四端、外部COS门禁完成；
- 独立复审无P0/P1；
- 最终仍由用户决定是否合并。
