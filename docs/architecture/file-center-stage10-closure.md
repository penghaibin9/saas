# 公共文件中心阶段 6–10 收口报告

本报告对应 Draft PR #25 `audit/file-capability-inventory`。阶段 6–10 的仓库内施工收口到统一 FileObject、FileAsset/FileVersion/FileBinding、ImportJob/ExportJob、流式归档、COS 生产存储适配，以及租户配额、保留和清理治理。

## 已冻结的仓库合同

- 毕业设计与岗位实习归档使用流式 ZIP64、分块 SHA-256 和路径型 FileObject，不整文件读入内存。
- 身份导入先写入隔离区并完成安全扫描，CLEAN 后才进行路径型 openpyxl 解析。
- COS 直传和服务器物理写入统一使用持久化 HELD reservation，成功后消费，失败、放弃或过期后释放。
- 普通上传、系统字节文件和路径型大型文件都在物理 persist 前进入业务模块配额作用域。
- 业务 Router 不直接构造 FileResponse，统一使用包含 no-store、nosniff 和下载审计的公共响应合同。
- 管理 PC 使用精确锁定的 `cos-js-sdk-v5@1.10.1`，不在运行时加载 CDN，不向前端保存永久密钥。
- 阶段 10 严格扫描器确认旧上传调用归零，并检查直接 FileResponse、整文件读取、上传内存拼包、运行时 COS CDN、永久密钥和一次性施工文件。

## 仓库内最终门禁

最终 HEAD 必须执行并记录：

1. 能力清单、增量登记、严格调用扫描、上传合同和密钥审计；
2. MySQL 8.0 单一 Alembic head，升级到 `0154_file_storage_quota_reservation`；
3. 身份导入扫描后解析、配额 reservation、模块配额作用域、流式归档测试；
4. 阶段 6–10 文件中心定向 pytest 和五个真实 MySQL acceptance；
5. 管理 PC lint/test/build、学生 PC lint/test/build、H5 与微信小程序生产构建。

测试结果只以真实执行日志和 PR 验收评论为证据；本报告不把未执行测试写成通过。

## 真实 COS 外部环境验收阻塞

真实 COS 端到端验收必须在腾讯云 COS 与生产域名环境执行，不能由 fake client 或单元测试冒充：

1. STS 最小权限与过期行为；
2. COS CORS 白名单；
3. COS 生命周期策略；
4. 服务端加密 SSE；
5. 50MB 与 500MB 真实上传；
6. 大文件跨会话续传，以及跨进程暂停、恢复和取消；
7. 真实跨租户对象隔离与越权验证。

在上述外部验收完成前，PR 仍为 Draft，不合并 main。
