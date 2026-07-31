# 公共文件中心阶段 6–10 收口账本

> PR：#25 `audit/file-capability-inventory`；始终保持 Draft，不合并 `main`，不开启自动合并。
> 本文只记录当前代码事实、自动化证据与外部阻塞，不用“计划完成”替代真实验收。

## 1. 当前施工结论

| 阶段 | 当前代码状态 | 已形成的权威能力 | 尚需最终证据 |
|---|---|---|---|
| 6 毕业设计迁移 | 已收口，等待同一最新 HEAD 总验收 | 18 类材料规则；Asset/Version/Binding；退回重交旧版本失效；教师与移动端锁定当前安全版本；真实 Manifest、ZIP、XLSX、模板版本；回填检查点；真实 MySQL 异常扫描计数证据 | 最新 HEAD 的阶段 6专项、毕业设计总闸门和四端构建同时全绿 |
| 7 教务迁移 | 权威导入与全域导出适配已完成 | 学籍、成绩、排课统一 SCANNING→PARSING→VALIDATED；确认仅 jobId+expectedVersion并重读同一 FileObject；15 类旧同步导出前置同路径适配，强制生成 FileObject+ExportJob+一次性票据；旧页面文件响应合同保持 | 最新 HEAD 的真 MySQL、Router前置顺序、管理 PC轮询和全域导出专项全绿 |
| 8 COS 与大文件 | 代码收口，真实云环境待验 | 精确 objectKey STS；quarantine/clean/rejected；HEAD/ETag/大小/哈希/magic/OOXML/ZIP校验；短时预签名；PC分片暂停恢复；迁移/核验/回滚；分区提升改为复制核验→提交元数据→提交后删源 | 正式私有桶、真实 CAM/STS、CORS/生命周期/加密、50MB/500MB和应用重启后的真实端到端证据 |
| 9 存储治理 | 代码收口，配额并发预留仍需设计 | 租户/模块配额；保留策略；法律保留；引用保护；到期文件 DELETE_PENDING→物理核验→DELETED 两阶段清理；失败进入 DELETE_FAILED；上传会话同样可恢复；跨租户 worker和学校治理页面 | 最新 HEAD MySQL专项；并发上传配额预留不能仅靠实时聚合查询，需要 reservation 贯穿物理写入到 FileObject落库 |
| 10 最终收口 | 总验收中 | 基线感知调用扫描；机器清单；最终组合闸门；施工残留检查；旧上传在非零调用期间改为隐藏弃用且仅委托权威合同 | 所有专项与四端构建全绿；旧上传调用归零后再删除兼容入口；更新 PR 描述到最终 HEAD |

## 2. API 退役裁决

- 权威普通上传入口是 `POST /files`。
- 生产代码仍存在少量 `/files/upload` 调用，因此当前**不得物理删除**该 URL。
- 兼容入口必须满足：隐藏 OpenAPI、`deprecated=True`、响应携带弃用头、只调用 `file_contract.upload_contract`，禁止直接调用 `file_service.store_upload` 或复制鉴权、扫描、绑定逻辑。
- 旧上传调用归零后，调用扫描与最终门禁同步改为物理删除兼容入口。
- `/files/meta/{fileId}` 已无生产调用并保持退役；元数据统一使用 `/files/{fileId}`。
- `/files/download/{fileId}` 是权威代理下载合同，仅共享 File SDK或强敏感审计链使用；业务页面不得自行拼接。

## 3. 阻塞与外部验收账本

以下事项不能在无正式云资源的 GitHub Actions 中伪造为“已验证”：

1. **真实 COS 端到端**：私有测试桶、最小权限 CAM/STS、真实 CORS、生命周期与服务端加密；执行 50MB/500MB 分片、暂停恢复、应用重启后下载、预签名过期、跨租户拒绝及分区提升提交失败演练。
2. **浏览器 SDK 同源制品**：管理 PC 当前锁定 `cos-js-sdk-v5@1.10.1`，但仍由公共 CDN 动态加载。正式上线前需在可重生成 `package-lock.json` 的环境中改为 npm依赖或提交经校验的同源制品；不能手工伪造 lockfile。
3. **大文件跨会话续传**：当前支持同页面暂停/恢复/取消；浏览器关闭后的 UploadId 持久化恢复尚未取得真实 COS证据。
4. **配额并发预留**：现有硬限额覆盖单请求和直传会话创建，但旧同域上传从物理写入到 FileObject落库之间仍有并发窗口。需要 reservation token/bytes 与过期回收，不能用短暂行锁冒充完整解决。
5. **旧上传调用归零**：仍需逐个迁移大体量聚合 API 文件中的 `/files/upload` 字符串；在归零前保留委托兼容入口，调用扫描按 `LEGACY_DEBT` 展示。
6. **真实容量成本**：存储类型、请求数、流量和地域价格以腾讯云实际账单验证，GitHub Actions只验证容量与治理逻辑。

## 4. 正式环境配置检查

- COS 桶私有，禁止匿名读写。
- 永久 SecretId/SecretKey 只存在服务器密钥管理或环境变量，不进入前端、仓库、日志与任务 JSON。
- STS 仅允许一个 `quarantine/{tenantId}/.../{uuid}.{ext}` 精确 Key，默认 900 秒。
- CORS 仅开放实际学校域名和必要方法，暴露 `ETag`、`Content-Length`，生产环境不使用 `*` 来源。
- quarantine、rejected、preview、export 使用短生命周期；archive 按学校策略长期保存或沉降低频。
- clamd 只在容器内部网络或 Unix Socket，扫描异常 fail-closed。
- file-scan-worker 与 file-governance-worker 由进程守护，积压、失败和重启可观测。

## 5. 最终验收口径

只有以下证据在同一最新 HEAD 同时成立，阶段 10 才可标记完成：

1. Alembic 单一 head，真实 MySQL 8.0升级成功。
2. 阶段 6–9专项、文件安全、对象授权、导入导出、实习/学工/毕设材料中心回归全绿。
3. 调用扫描 0 `BLOCKER`；`LEGACY_DEBT` 有明确所有者和退役条件；能力清单 schema、全量基线、增量登记全绿。
4. 管理 PC、学生 PC、H5、微信小程序 lint/test/build 全绿。
5. EICAR、ClamAV停机、配额超限、分区迁移提交失败、过期/撤销下载、法律保留、DELETE_FAILED重试均 fail-closed。
6. PR 仍为 Draft、未合并、未开启自动合并；PR描述使用最终 HEAD和真实结果。
