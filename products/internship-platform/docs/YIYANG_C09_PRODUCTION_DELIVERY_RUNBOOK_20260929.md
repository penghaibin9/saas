# 益阳职业技术学院岗位实习 Standalone · C09 生产交付与验收 Runbook

> 适用分支：`feat/internship-standalone-yiyang-v1` / PR #275  
> 本文只定义可执行交付流程和证据口径，不把尚未在校方真实环境执行的事项写成“已验收”。

## 1. C09 的完成口径

C09 不是“代码能启动”即完成。正式交付必须同时留下以下证据：

1. 独立 MySQL 8.4 从空库迁移到当前 Alembic head；
2. `/health/ready` 同时证明数据库、迁移版本、Redis、附件目录可用；
3. 管理/教师 PC、学生 PC、企业协同端均由 HTTPS 入口提供，微信小程序另行提交微信开发者工具/真机证据；
4. G19 历史数据迁移必须有逐表数量、逻辑孤儿、文件元数据和附件字节校验报告；
5. G20 性能验收必须有真实目标环境的 k6 结果；少于 5000 VU 的结果只能标为 `SMOKE_ONLY`；
6. MySQL 与附件必须进入同一个 backup-set manifest，恢复必须进入隔离 drill DB；
7. 监管平台真实模板、真实回执、学校统一认证/门户等依赖校方资料的项目，只能在资料到位后形成正式 UAT 证据；
8. 完成 15 日试运行、培训签到/问题单/关闭单、最终验收记录。

## 2. 生产部署

### 2.1 服务器前置条件

建议生产主机至少具备：

- Linux x86_64；
- Docker Engine + Docker Compose v2；
- 80/443 对外，3306/6379 不对公网开放；
- 正式域名和可信 TLS 证书；
- 独立备份盘或异地对象存储；
- 时间同步正常。

实际 CPU、内存、带宽不得仅按开发机估算，应以 G20 压测结果反推。

### 2.2 构建三个 PC 端

在 `products/internship-platform` 下分别构建：

```bash
cd admin-web
npm install --no-audit --no-fund
npm run build

cd ../student-web
npm install --no-audit --no-fund
npm run build

cd ../enterprise-web
npm ci
npm run build
```

学生/教师微信小程序使用：

```bash
cd ../mobile
npm install --no-audit --no-fund
npm run build:mp-weixin
```

小程序产物必须继续经过微信开发者工具与真实手机验收，不能用 H5 build 替代。

### 2.3 配置生产变量

```bash
cd deploy
cp env.production.example .env.production
```

至少替换：

- `DB_PASSWORD`
- `MYSQL_ROOT_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET`
- `FIELD_ENCRYPTION_KEY`
- `SENSITIVE_SEARCH_HMAC_KEY`

不得提交真实 `.env.production`、证书私钥、学校接口密钥。

TLS 文件默认：

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

### 2.4 启动

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```

首次部署必须确认 migrate 容器正常结束，随后检查：

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
curl -fsS https://正式域名/health
curl -fsS https://正式域名/health/ready
```

`/health/ready` 的正式通过条件：

- `status=READY`
- `database=READY`
- `schemaRevision=ix0023`（以后新增迁移时同步更新部署配置）
- Redis 为 READY
- fileStorage 为 READY

## 3. G19 历史数据迁移

工具：

```text
scripts/g19_migration_bridge.py
```

### 3.1 先做 plan

```bash
python scripts/g19_migration_bridge.py \
  --source 'mysql+pymysql://...旧库...' \
  --target 'mysql+pymysql://...Standalone库...' \
  --tenant-id <学校tenant_id> \
  --mode plan \
  --report artifacts/g19-plan.json
```

Plan 只能说明可迁移性，不是迁移完成证据。

### 3.2 正式 copy

若历史附件为本地文件，同时提供源/目标附件根目录：

```bash
python scripts/g19_migration_bridge.py \
  --source 'mysql+pymysql://...旧库...' \
  --target 'mysql+pymysql://...Standalone库...' \
  --tenant-id <学校tenant_id> \
  --mode copy \
  --source-file-root /old/data/files \
  --target-file-root /new/data/files \
  --report artifacts/g19-copy.json
```

正式迁移禁止：

- 自动把原 `tenant_id` 改成 1；
- 把其他学校数据一起复制；
- 对非空目标库直接覆盖；
- 只比“总行数”而不查逻辑孤儿；
- 只复制 `t_file_object` 元数据却宣称附件迁移完成。

若历史附件在 COS/其他对象存储，数据库报告会明确给出 `BLOCKED_FILE_BYTES` 或 external storage 数量；必须另做对象级复制与 checksum 证据后才能关闭 G19。

### 3.3 verify

```bash
python scripts/g19_migration_bridge.py \
  --source 'mysql+pymysql://...旧库...' \
  --target 'mysql+pymysql://...Standalone库...' \
  --tenant-id <学校tenant_id> \
  --mode verify \
  --source-file-root /old/data/files \
  --target-file-root /new/data/files \
  --report artifacts/g19-verify.json
```

最终只接受 `g19Qualified=true`。

## 4. G20 5000+ 并发验收

工具：

```text
load/g20_internship.k6.js
scripts/g20_validate_evidence.py
```

### 4.1 小规模 smoke

小规模只验证场景、鉴权、URL 和监控：

```bash
G20_BASE_URL=https://正式域名 \
G20_VUS=20 \
G20_AUTH_TOKEN='<测试账号token>' \
G20_PATHS='/health,/api/v1/<真实只读业务接口1>,/api/v1/<真实只读业务接口2>' \
k6 run load/g20_internship.k6.js
```

验证结果：

```bash
python scripts/g20_validate_evidence.py g20-k6-summary.json \
  --report artifacts/g20-smoke.json
```

此时应为 `SMOKE_ONLY`，不得写入投标验收材料为“5000 并发通过”。

### 4.2 正式 5000 VU

必须在已获授权的测试窗口，对生产同规格或正式 UAT 环境执行，并至少包含真实鉴权后的岗位实习只读核心业务接口：

```bash
G20_BASE_URL=https://UAT正式域名 \
G20_VUS=5000 \
G20_REAL_RUN_ACK=YES \
G20_AUTH_TOKEN='<专用压测账号token>' \
G20_BATCH_ID='<真实压测批次>' \
G20_PATHS='/health,/api/v1/<批次统计接口>,/api/v1/<过程统计接口>,/api/v1/<风险列表接口>' \
G20_P95_MS='<校方/采购SLA>' \
G20_P99_MS='<校方/采购SLA>' \
G20_MAX_ERROR_RATE='<校方/采购SLA>' \
k6 run load/g20_internship.k6.js
```

再执行：

```bash
python scripts/g20_validate_evidence.py g20-k6-summary.json \
  --report artifacts/g20-formal.json \
  --require-qualified
```

正式结果必须保留：

- VU 数；
- 总请求数 / RPS；
- 平均响应；
- P95 / P99；
- HTTP 失败率；
- k6 threshold 状态；
- 服务器 CPU/内存/网络；
- MySQL 活跃连接/慢 SQL；
- 测试开始结束时间；
- 对应部署 commit。

## 5. 备份与恢复

### 5.1 备份

```bash
cd deploy
SOURCE_COMMIT="$(git rev-parse HEAD)" ./backup/backup.sh
```

一个有效恢复点由以下文件共同组成：

```text
manifest_*.json
manifest_*.json.sha256
mysql_*.sql.gz
mysql_*.sql.gz.sha256
files_*.tar.gz
files_*.tar.gz.sha256
```

manifest 是提交标记。禁止只留 SQL、不留附件，或 SQL 与附件来自不同时间点却写成一个完整备份。

### 5.2 隔离恢复演练

```bash
./backup/restore-drill.sh backups/manifest_YYYYMMDD_HHMMSS.json internship_restore_drill
```

演练会：

1. 验证 manifest / SQL / 附件包 SHA-256；
2. 在 `*_restore_drill` 隔离数据库恢复；
3. 验证 Alembic revision；
4. 验证恢复表数量；
5. 解压附件到临时目录；
6. 对 `t_file_object` 中 local 文件逐个核验 size/SHA；
7. 输出 `restore-evidence-*.json`；
8. 默认清理 drill DB。

COS/其他对象存储必须另留 provider-level 恢复和 checksum 证据，不能由 local-file drill 代替。

## 6. 15 日试运行计划

### 第 1～2 日：上线与主数据

- 学校管理员、学院管理员、指导老师、学生、企业账号开通；
- 学院/专业/班级/批次/学生主数据核对；
- 权限与数据范围抽查；
- 新老系统数据数量对账；
- 附件抽样回读。

### 第 3～5 日：实习前

- 企业/岗位；
- 学生报名/志愿/匹配；
- 自主实习申请；
- 三方协议；
- 保险；
- 安全教育；
- 特殊岗位/高风险备案。

### 第 6～10 日：实习中

- 学生签到、水印、定位异常；
- 日/周/月/总结报告；
- 教师批阅；
- 教师签到、走访、指导；
- 请假/变更；
- 风险预警；
- 紧急通知与回执；
- 企业协同。

### 第 11～13 日：实习后与监管

- 企业评价；
- 学生评价；
- 成绩合成/申诉；
- 证明/鉴定/正式文书；
- 材料归档；
- 两类监管报表导出/校验；
- 若真实监管接口已提供，则执行真实回执闭环。

### 第 14 日：性能与灾备

- 真实 G20 性能验收；
- 备份；
- 隔离恢复；
- 恢复后登录/查询/附件回读。

### 第 15 日：关闭问题与签字

- P0/P1 问题必须清零；
- P2 明确处理计划；
- 培训签到；
- 管理员操作手册确认；
- 试运行问题单与关闭单归档；
- 形成最终 UAT/验收报告。

## 7. 培训与售后交付清单

至少覆盖：

- 学校管理员：组织、账号、权限、批次、监管、归档、导出；
- 学院/指导老师：学生范围、计划、签到异常、报告批阅、走访指导、风险处置；
- 学生：报名、申请、协议、签到、报告、变更、评价；
- 企业：岗位、候选人、评价、证明/证书；
- 运维：部署、日志、升级、备份、恢复、性能证据。

培训材料必须对应当前版本截图和当前菜单，不使用旧 SaaS/旧就业模块截图冒充 Standalone。

## 8. 当前仍必须由真实学校/UAT关闭的外部项

以下内容不能靠仓库代码“自动完成”：

- 学校正式域名与可信 TLS 证书；
- 学校提供的统一认证/门户/消息接口资料（若本项目现场要求）；
- 监管平台正式导入模板、接口凭证、正式回执；
- 真实 5000 VU 授权压测窗口与目标环境；
- 正式历史库/附件源；
- 微信小程序 AppID、合法域名、开发者工具与真实手机；
- 校方试运行人员、培训签到和最终签字。

这些项目资料未到位时，状态必须写“待现场/UAT”，不能写“已验收”。
