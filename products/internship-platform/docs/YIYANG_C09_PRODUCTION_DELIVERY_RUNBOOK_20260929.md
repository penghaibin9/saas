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

### 2.2 独立构建和交付包

当前推荐从本产品目录运行 `python scripts/product.py build`：按四端锁文件安装、执行测试，并构建管理/教师、学生、企业电脑端及同源移动网页版。随后运行 `python scripts/product.py package --output ../岗位实习独立交付包.zip`，输出全新文件和校验值。构建回执只证明本地源码与产物一致，不表示学校或生产验收通过。

生产网关同时交付 `/mobile/`；移动网页版构建时使用 `VITE_API_BASE_URL=/`，通过同一域名的 `/api/v1` 请求后台，不保留开发机地址。

需要逐端排查时，下面命令仍有效。

在 `products/internship-platform` 下分别构建：

```bash
cd admin-web
npm ci --no-audit --no-fund
npm run build

cd ../student-web
npm ci --no-audit --no-fund
npm run build

cd ../enterprise-web
npm ci
npm run build
```

学生/教师微信小程序使用：

```bash
cd ../mobile
npm ci --no-audit --no-fund
npm run build:mp-weixin
```

小程序产物必须继续经过微信开发者工具与真实手机验收，不能用 H5 build 替代。

小程序构建前必须显式设置实际的 `VITE_API_BASE_URL`，并核对 `mobile/src/manifest.json` 的应用编号属于本次学校交付。没有正式目标时，只交付源码和移动网页版，不把本机构建当成可发布微信版本。

### 2.3 配置生产变量

**独立产品的统一入口与首次交接约定**

- `admin-web` 同时交付岗位实习与系统管理，分别使用 `/admin/internship`、`/admin/system`；共用 `/login`、`/api/v1`、同一后台与本校主档。不得把系统管理部署成另一套学校库或要求师生重复开户。
- 初始账号默认承担学校系统维护职责。本人完成首次改密后，从“系统管理概览”的学校准备与实习开局步骤，完成组织、教职工和学生开户，再在“角色与权限”中为实际负责人配置校级或院系实习身份及相应范围。兼任人员使用原账号；不因显示两个入口而自动授予审批或敏感资料查看权。
- 顶部两个区域使用同一外壳。当前身份有权时直接进入；另有已授权身份时明确选择、确认切换；没有对应身份时指向负责人配置。切换后服务端重新裁定权限，不能合并多个身份的权限。
- 安装交接时用同一学生主档与原教师账号验收：学校准备 → 实习批次及参与名单 → 导师分配 → 教师接收 → 切回系统管理核对原资料，并检查刷新、无权深链和撤权。后台与管理端候选需配套，身份发现接口返回各已授权身份的有效权限用于入口提示，不替代当前身份授权。
- 三个电脑端仍按本节构建和统一网关交付；教师与学生微信端指向同一独立后台，微信宿主、域名与真机证据单列。上述约定及本地通过不能替代空库安装、隔离恢复、真实迁移或生产发布验收。

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
- `schemaRevision=ix0036`（以后新增迁移时同步更新部署配置）
- Redis 为 READY
- fileStorage 为 READY

### 2.5 企业扫码与考勤启用检查

首次迁移成功且确认数据库完全为空后，使用安装镜像内同一初始化入口建立学校。下面回执目录须由实施人员提前创建并限制访问，不能位于网页根目录、附件目录或源码公开目录。实际学校名称、代码和账号需按交付目标填写。

```bash
docker compose --env-file .env.production -f docker-compose.production.yml run --rm --no-deps \
  --user "$(id -u):$(id -g)" --volume /srv/private/internship-handoff:/run/school-init \
  backend python -m app.initialize_school --school-code SCHOOL_CODE --school-name SCHOOL_NAME \
  --admin-login SCHOOL_OWNER --receipt-file /run/school-init/owner.json
```

命令拒绝已有学校、已有账号或已有同名回执。临时密码不打印，由受控回执交接给负责人；首次登录必须本人修改密码。不能用再次初始化来修复已有学校。

首次空校安装可保持考勤配置档关闭；健康检查通过不代表已经具备日常考勤调度。学校建好实际进行中的批次后，交付前必须完成下面的配置和运行核验。

<details>
<summary>实施人员使用：明确目标后启用，不默认扫描所有学校</summary>

- 设置 `ENTERPRISE_PORTAL_BASE_URL` 为本次实际部署的加密公网地址，路径与单域名反代的 `/enterprise` 一致；该值由容器配置传入后台，不能只留在宿主环境文件。
- 设置 `COMPOSE_PROFILES=attendance`，并明确填写 `ATTENDANCE_TENANT_ID`、`ATTENDANCE_BATCH_ID`；实际学校与进行中批次必须只读核验一致。没有目标时，不启动考勤程序。
- 从仓库根目录运行以下只读检查；示例文件保留空值，因此不能用示例文件取得交付通过结论。

```powershell
python products/internship-platform/scripts/check_delivery_config.py --env-file products/internship-platform/deploy/.env.production
```

检查通过并取得本次发布授权后，从本产品部署目录显式启动考勤服务：

```bash
docker compose --env-file .env.production -f docker-compose.production.yml --profile attendance up -d --build attendance-worker
docker compose --env-file .env.production -f docker-compose.production.yml ps attendance-worker
```

心跳按学校、批次分别记录；运行失败、心跳过期或查询另一个目标均不能报健康。当前一个进程只处理明确的一校一批次；多个进行中批次须分别配置进程并逐个核验，不能将一批次通过算成全部批次已调度。

</details>

配置检查不连接公网或数据库。正式交付仍须检查评价二维码指向本校原学生任务、未登录扫码后能接续、限定目标的提醒持续产生并由正常学生/导师接收，重复扫描不重复通知。本次候选补丁没有执行生产启动命令。

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

当前实际验证使用官方便携运行时`k6 v2.3.0`（压测工具第2.3.0版），下载与校验依据[官方安装说明](https://grafana.com/docs/k6/latest/set-up/install-k6/)。版本升级后应重新跑采集和校验链，不能只以脚本语法正确代替引擎运行。

### 4.1 小规模验证

小规模只验证场景、正常账号鉴权、接口地址和监控。当前证据协议为第二版，使用单台负载发生器；多个发生器的局部活动用户数不能直接汇总冒充本协议的持续并发。兼容已验证的工具版本时使用旧版机器可读汇总格式：

```bash
G20_BASE_URL=https://正式域名 \
G20_VUS=20 \
G20_AUTH_TOKEN='<测试账号token>' \
G20_BATCH_ID='<真实压测批次>' \
G20_PATHS='/health,/api/v1/internship/dashboard?batchId={batchId},/api/v1/internship/stats/procurement-overview?batchId={batchId},/api/v1/internship/stats/process-analytics?batchId={batchId}&groupBy=STUDENT&period=ALL&page=1&pageSize=50,/api/v1/internship/risks?batchId={batchId}&page=1&pageSize=20' \
k6 run --no-usage-report --new-machine-readable-summary=false --out json=g20-raw-metrics.json load/g20_internship.k6.js
```

验证结果：

```bash
python scripts/g20_validate_evidence.py g20-k6-summary.json \
  --report artifacts/g20-smoke.json
```

此时应为 `SMOKE_ONLY`（仅小规模验证），不得写入投标验收材料为“5000 并发通过”。共享单个账号的小规模验证不满足正式账号池要求。原始指标也必须留在授权测试目录，不包含令牌、密码或响应正文。

### 4.2 正式 5000 VU

必须在已获授权的测试窗口，对生产同规格或正式 UAT 环境执行，并至少包含真实鉴权后的岗位实习只读核心业务接口：

```bash
G20_BASE_URL=https://UAT正式域名 \
G20_VUS=5000 \
G20_REAL_RUN_ACK=YES \
G20_AUTH_TOKENS_FILE='/secure/g20-auth-tokens.json' \
G20_BATCH_ID='<真实压测批次>' \
G20_PATHS='/health,/api/v1/internship/dashboard?batchId={batchId},/api/v1/internship/stats/procurement-overview?batchId={batchId},/api/v1/internship/stats/process-analytics?batchId={batchId}&groupBy=STUDENT&period=ALL&page=1&pageSize=50,/api/v1/internship/risks?batchId={batchId}&page=1&pageSize=20' \
G20_P95_MS='<校方/采购SLA>' \
G20_P99_MS='<校方/采购SLA>' \
G20_MAX_ERROR_RATE='<校方/采购SLA>' \
k6 run --no-usage-report --new-machine-readable-summary=false --out json=g20-raw-metrics.json load/g20_internship.k6.js
```

正式压测账号 token 池文件必须放在压测机安全目录，格式为 JSON 字符串数组，例如：

```json
["token-user-0001", "token-user-0002", "…"]
```

要求：
- 令牌数量不少于 `G20_VUS`；5000个不同令牌不等于5000个不同账号。正式负载开始前，脚本逐个请求`GET /api/v1/auth/me`，由服务端核验当前有效数据库账号、学校及免改密码状态，以学校和账号的组合去重。使用前`G20_VUS`个令牌时必须恰好验证出同等数量的不同账号，否则在负载前拒绝；
- 文件不得提交到 Git、不得上传到投标材料；
- 压测工具只在内存中按虚拟用户分配令牌，生成的证据只记录核验数量，不记录令牌或账号明细；
- 只有单个`G20_AUTH_TOKEN`时可做小规模验证，正式模式会在开始前拒绝账号池不足。

固定采购判定与运行门禁：

- 采购原文“平均响应时间不大于3秒”固定为3000毫秒，不能通过调整运行参数提高上限。校验器分别检查总体响应和保持阶段真实业务响应，健康检查的快速返回不能替代业务耗时；
- 保留原有运行策略默认值：95%请求响应小于1500毫秒、99%请求响应小于3000毫秒、失败率小于1%。这三项可按已授权测试计划调整，不能把默认分位数门槛写成采购原文；
- 至少保持60秒是现有工程观测下限，学校认可的计划可以要求更长。保持阶段逐次采集实际活动虚拟用户数，最小值须达到申请规模，观测须覆盖窗口首尾；每个虚拟用户须至少成功参与一次实际业务请求。只填写5000、只记录峰值或只调用健康接口均不合格；
- 接口必须返回成功的业务结果。HTTP（网络请求状态）200但业务失败、返回登录网页或无法解析结果，仍计失败；
- 第一版汇总、缺失指标、字符串形式的“通过”、非有限数值及不一致的实际指标均不能通过。运行前置条件提示只表示配置和账号准备，不表示压测合格；
- `PASS`（该次性能运行合格）仅对应已测的性能要求；年度稳定运行率99.5%、备案、试运行及完整采购交付分别取证，不能由一次压测报告替代。

活动虚拟用户数和汇总字段的工具合同参考[执行上下文官方说明](https://grafana.com/docs/k6/latest/javascript-api/k6-execution/)和[自定义汇总官方说明](https://grafana.com/docs/k6/latest/results-output/end-of-test/custom-summary/)。本地仅小规模验证，不在资源紧张的共用调试主机上施加5000人负载。

再执行：

```bash
python scripts/g20_validate_evidence.py g20-k6-summary.json \
  --report artifacts/g20-formal.json \
  --require-qualified
```

本仓库当前已确认用于 G20 的只读核心接口为：

- `GET /api/v1/internship/dashboard?batchId={batchId}`
- `GET /api/v1/internship/stats/procurement-overview?batchId={batchId}`
- `GET /api/v1/internship/stats/process-analytics?batchId={batchId}&groupBy=STUDENT&period=ALL&page=1&pageSize=50`
- `GET /api/v1/internship/risks?batchId={batchId}&page=1&pageSize=20`

这些接口均走真实鉴权和数据范围，不使用 mock URL；正式压测前仍需用专用压测账号验证其对目标批次有只读权限。

正式结果必须保留：

- 申请虚拟用户数、服务端核验的不同账号数、保持阶段实际最小/最大活动用户数及成功业务参与人数；
- 总请求数 / RPS；
- 总体及保持阶段业务平均响应、保持窗口长度与首末样本；
- P95 / P99；
- HTTP 失败率；
- k6 threshold 状态；
- 服务器 CPU/内存/网络；
- MySQL 活跃连接/慢 SQL；
- 测试开始结束时间；
- 对应部署提交、运行时版本、场景配置、原始指标及汇总文件校验值。未提交源码须另附候选文件指纹，不能仅用旧提交号代表当前程序。

## 5. 备份与恢复

### 5.1 备份

```bash
cd deploy
SOURCE_COMMIT="$(sha256sum ../delivery-manifest.json | cut -d ' ' -f1)" bash ./backup/backup.sh
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
bash ./backup/restore-drill.sh backups/manifest_YYYYMMDD_HHMMSS_PID.json internship_restore_drill
```

演练会：

1. 验证 manifest / SQL / 附件包 SHA-256；
2. 在 `*_restore_drill` 隔离数据库恢复；
3. 验证 Alembic revision；
4. 验证恢复表数量；
5. 解压附件到临时目录；
6. 对 `t_file_object` 中 local 文件逐个核验 size/SHA；
7. 输出 `restore-evidence-*.json`；
8. 默认保留演练库和回执；目标库已存在时直接拒绝，不能清空重建。只有明确要求清理本次新建演练库时才设置 `KEEP_DRILL_DB=0`，不会清理此前已有的同名库。

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
