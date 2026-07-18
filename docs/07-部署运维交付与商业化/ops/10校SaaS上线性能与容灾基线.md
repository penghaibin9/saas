# 10 所学校 SaaS 上线性能与容灾基线

适用基线：10 所学校、每校约 1 万名学生，约 10 万学生主档；高峰按 10% 学生在 10 分钟内打开小程序估算。该规模不要求分库分表，先使用 MySQL 单库多租户、Redis、多后端实例和异步任务即可。是否扩容以压测和监控结果为准，不以学生总数直接判断。

## 一、生产拓扑

- Nginx：2 个后端副本的统一入口，启用连接复用、请求速率和连接数保护。
- Backend：至少 2 个容器，每容器 4 个 Uvicorn worker。不要在 Web worker 中运行定时扫描。
- Scheduler：1 个独立容器运行 `backend/scripts/run_scheduled_jobs.py`。
- MySQL 8：开启慢查询日志和 Binlog，业务连接数预算必须小于 MySQL `max_connections` 的 70%。
- Redis 7：开启 AOF，用于鉴权状态、JWT 黑名单、共享限流和短缓存；Redis 故障时系统降级到 MySQL/进程内保护。

当前 Compose 基线的最大理论业务连接数为：`2 个容器 × 4 worker × (pool_size 5 + overflow 10) = 120`。再给调度器、迁移、备份和运维连接预留至少 30 个连接。不要在没有核算 MySQL 上限时盲目增加 worker。

Compose 必须使用 `docker compose --env-file ../env/backend.mysql.env -f docker-compose.mysql.yml ...` 启动。`env_file` 只负责把变量注入容器，不会自动参与 Compose 文件中的 `${DB_PASSWORD}` 替换；漏掉 `--env-file` 可能导致 MySQL 与后端拿到不同密码。

## 二、上线参数

生产环境至少明确配置：

```env
APP_ENV=prod
TENANCY_MODE=multi
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=5
DB_POOL_RECYCLE=1800
REDIS_URL=redis://redis:6379/0
AUTH_SUBJECT_CACHE_TTL=30
HOME_CACHE_TTL=20
TENANT_API_RATE_LIMIT_PER_SECOND=500
USER_API_RATE_LIMIT_PER_SECOND=120
SLOW_QUERY_MS=500
HTTP_SLOW_REQUEST_MS=1000
SCHEDULER_MODE=external
JWT_EXPIRES_IN=7200
MYSQL_MAX_CONNECTIONS=200
MYSQL_INNODB_BUFFER_POOL_SIZE=2G
MYSQL_LONG_QUERY_TIME=0.5
REDIS_MAXMEMORY=512mb
```

`MYSQL_INNODB_BUFFER_POOL_SIZE=2G` 是 10 校基线起点，不是所有机器的固定值。数据库独占主机通常配置为物理内存的 50%～70%，并为操作系统、连接缓冲、备份和临时表预留空间。上线前必须读取 `Max_used_connections`、`Created_tmp_disk_tables`、缓冲池命中率和慢 SQL 后再调参。

Access Token 保持 2 小时，Refresh Token 保持 7 天。小程序只在 Access Token 临近过期或收到 401 时单飞刷新；刷新失败才清理会话并重新微信登录，禁止每次 `onShow` 都调用 `wx.login`。

同一个微信可能对应多所学校的教师或学生账号。绑定关系必须落 `t_wx_account_binding`，以 `tenant_id + wx_openid` 保证每校一个绑定；只有一个学校时直接登录，存在多个学校时使用 10 分钟 `wxToken` 调用 `/auth/wx-select` 选择本次学校，禁止把跨校身份合并到同一个租户令牌。

## 三、数据库与历史数据

上线按顺序执行：

```bash
cd backend
python -m alembic upgrade head
python scripts/audit_tenant_schema.py --strict
python scripts/backfill_student_domain_links.py
python scripts/backfill_student_domain_links.py --apply --confirm BACKFILL-STUDENT-ID
python scripts/audit_tenant_queries.py
```

回填脚本默认只读。先保存 dry-run 输出，人工处理同租户同名、重复学号或无法匹配记录，再执行 apply。跨模块关联以 `student_id` 为准，姓名/学号仅作为一次性历史兼容回填条件。

分页接口必须设置上限，默认每页 20、最大 100；导出超过 5000 行改为后台任务。列表查询禁止逐行加载关系，优先一次 join/select-in 批量加载。上线前用真实数量级脱敏数据执行 `EXPLAIN ANALYZE`，重点检查消息、待办、预警、审计、首页聚合和导出查询。

## 四、备份与 Binlog 恢复

MySQL 必须配置：

```ini
[mysqld]
server-id=1
log_bin=mysql-bin
binlog_format=ROW
binlog_expire_logs_seconds=604800
sync_binlog=1
innodb_flush_log_at_trx_commit=1
slow_query_log=ON
long_query_time=0.5
```

每天 02:00 执行 `deploy/backup/backup-mysql.sh`（Windows 使用 `.ps1`），生成压缩全量备份、SHA256 和 Binlog 起点。备份必须复制到不同故障域的对象存储；本机保留 14 天，异地至少保留 30 天。

时间点恢复（PITR）演练步骤：

1. 建立隔离的恢复库，绝不直接覆盖生产库。
2. 校验备份 SHA256，用 restore 脚本恢复最近一次全量备份。
3. 从备份头部的 `CHANGE REPLICATION SOURCE TO` 注释确认 Binlog 文件和位置。
4. 使用 `mysqlbinlog --start-position=<pos> --stop-datetime='YYYY-MM-DD HH:MM:SS' mysql-bin.00xxxx | mysql <恢复库>` 回放到故障前时间点。
5. 校验租户数、学生数、关键业务表数量、抽样业务流程和跨租户隔离，再制定切换方案。

目标：RPO 不超过 5 分钟（取决于 Binlog 异地同步），RTO 不超过 2 小时。每月至少一次自动可读性校验，每季度一次完整恢复演练并记录实际 RPO/RTO。

## 五、监控与告警阈值

接口和连接池可从 `/health/ready`、`/health/metrics` 采集；多 worker/多副本时必须逐实例采集并聚合。

| 指标 | 预警 | 严重告警 |
|---|---:|---:|
| API p95 | > 500 ms 持续 5 分钟 | > 1000 ms 持续 5 分钟 |
| HTTP 5xx | > 1% 持续 5 分钟 | > 3% 持续 2 分钟 |
| DB 池占用 | > 70% 持续 5 分钟 | > 90% 或出现 pool timeout |
| MySQL 慢 SQL | > 10 条/分钟 | > 50 条/分钟或单条 > 5 秒 |
| MySQL 连接 | > `max_connections` 70% | > 85% |
| Redis 延迟 | p95 > 20 ms | 不可用超过 1 分钟或命中率骤降 |
| Redis 内存 | > 70% | > 85% 或发生 eviction |
| 磁盘 | > 70% | > 85% |
| 备份 | 24 小时无成功备份 | 校验失败或 48 小时无可用备份 |
| 调度任务 | 一次失败 | 连续三次失败或延迟超过一个周期 |

## 六、上线检查清单

- [ ] Alembic 为唯一 head，`upgrade head` 成功，新增组合索引在实库可见。
- [ ] 历史 `student_id` dry-run 无未处理歧义，apply 后再次扫描为零异常。
- [ ] 两个不同学校的读、改、导出、文件下载自动化用例均返回 403/404。
- [ ] Redis AOF、密码/网络 ACL 和内存上限已配置；主动断开 Redis 验证降级。
- [ ] Web 容器 `SCHEDULER_MODE=external`，只有一个 Scheduler 实例。
- [ ] 首页只有一个 `/mobile/home` 请求，冷缓存和热缓存结果一致。
- [ ] 以 10 校峰值模型完成 30 分钟压测，记录 p95、错误率、DB 池和 Redis 指标。
- [ ] 全量备份、SHA256、异地复制成功；在隔离库完成恢复和 Binlog 回放。
- [ ] 告警接收人、升级路径和维护窗口已确认。
- [ ] 发布前保留旧应用镜像和数据库变更回滚方案；涉及数据回填时只前滚修复，不盲目降级结构。
