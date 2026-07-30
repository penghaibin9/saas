# 阶段 E：容量测试与可观测性

本目录用于验证系统在真实 MySQL、Redis、多 Worker/多实例和集中访问下的容量边界。

## 范围

第一批只压测核心只读接口：

- 学生：首页、待办、消息、本人档案
- 教师：工作台总览、待办、我的班级、风险学生

明确禁止：

- 文件上传、下载、预览、附件、公共文件中心
- COS、ClamAV、导入导出、归档任务
- 未经确认的生产高并发
- 用单个账号冒充 500/1000/3000 个真实用户

## 档位

| PROFILE | 目的 | 默认是否允许 |
|---|---|---|
| smoke | 2 VU，验证脚本、鉴权和指标采集 | 是 |
| baseline | 20 VU 基础容量 | 是 |
| p500 | 500 并发阶梯 | 否，需显式解锁 |
| p1000 | 1000 并发阶梯 | 否，需显式解锁 |
| p3000 | 3000 并发阶梯 | 否，需显式解锁 |

`smoke` 和 `baseline` 允许使用专用测试账号自动登录。高并发档位必须使用预签发 Token 池，避免登录限流污染容量结论。

## PR 自包含容量矩阵

修改容量脚本、合同或工作流后，GitHub Actions 会自动并行运行 `smoke` 与 `baseline`，不需要服务器地址、服务器密码、真实师生账号或仓库 Secrets。

每个档位都会自动完成：

1. 启动临时 MySQL 8 与 Redis 7；
2. 执行真实 Alembic 迁移；
3. 创建临时学生主档和短期学生/教师 Token；
4. 启动真实 FastAPI 后端；
5. 压测前检查 `/health/ready` 与 `/internal/metrics`；
6. 对学生/教师 8 个只读接口执行混合负载；
7. 压测后再次检查 readiness、MySQL、Redis 和指标完整性；
8. 生成 `k6-summary.json`、`capacity-verdict.json`、前后探针和后端日志；
9. 分档上传 Artifact。

`capacity-verdict.json` 会强制裁决：

- smoke 请求数不少于 100，baseline 不少于 1000；
- HTTP 错误率 `<0.5%`；
- 业务检查通过率 `>99.5%`；
- P95 `<1000ms`，P99 `<2000ms`；
- 压测前后均为 `READY`；
- MySQL、Redis、迁移和指标键完整；
- 监控统计中不存在非 2xx 响应。

## 生产运行参数审计

在服务器已经加载正式环境变量后执行：

```bash
python performance/tools/audit_capacity_runtime.py
```

它会拒绝以下状态进入容量验收：

- 未显式使用 production 模式
- 未启用真实 MySQL
- 未配置 Redis
- 仍是单 Worker 且未启用多实例
- 多 Worker/多实例仍把 Scheduler 放在 Web 进程
- 未配置 `INTERNAL_OPS_TOKEN`
- MySQL 连接池预算不足

建议先声明数据库最大连接预算：

```bash
export CAPACITY_DB_CONNECTION_BUDGET=200
python performance/tools/audit_capacity_runtime.py
```

脚本只输出安全状态和计算结果，不回显密钥或完整数据库连接串。

## 准备真实环境账号表

真实预发或正式环境压测需要专用最低权限账号，不使用个人师生账号：

```bash
cd backend
python ../performance/tools/prepare_k6_credentials.py \
  --template ../performance/local/capacity-accounts.xlsx
```

填写账号或预签发 Token 后生成本地 Secret 文件：

```bash
python ../performance/tools/prepare_k6_credentials.py \
  --input ../performance/local/capacity-accounts.xlsx \
  --out ../performance/secrets
```

`performance/local/`、`performance/secrets/` 和账号表不得提交。工具只输出数量，不回显密码和 Token。

## 压测前监控探针

```bash
export INTERNAL_OPS_TOKEN='服务器实际运维探针令牌'
python performance/tools/probe_observability.py \
  --base-url https://staging.example.com \
  --samples 3 \
  --output performance/results/observability.json
```

探针要求 `/health/ready` 为 `READY`，并验证 `/internal/metrics` 包含 P50/P95/P99 所需的基础指标结构。Token 只从环境变量读取。

## 本地或预发手工运行

```bash
export BASE_URL=https://staging.example.com
export PROFILE=smoke
export SCENARIO=mixed
export K6_STUDENT_TOKENS_JSON="$(cat performance/secrets/student-tokens.json)"
export K6_TEACHER_TOKENS_JSON="$(cat performance/secrets/teacher-tokens.json)"
mkdir -p performance/results

docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work" -w /work \
  -e BASE_URL -e PROFILE -e SCENARIO \
  -e K6_STUDENT_TOKENS_JSON -e K6_TEACHER_TOKENS_JSON \
  -e SUMMARY_PATH=/work/performance/results/k6-summary.json \
  grafana/k6:0.54.0 run performance/k6/capacity.js
```

运行前后探针完成后，可生成统一裁决：

```bash
python performance/tools/evaluate_capacity_result.py \
  --profile "$PROFILE" \
  --summary performance/results/k6-summary.json \
  --before performance/results/observability-before.json \
  --after performance/results/observability-after.json \
  --output performance/results/capacity-verdict.json
```

## GitHub Actions：真实服务器作业

PR 自包含矩阵无需配置。只有对真实预发或正式服务器执行远程压测时，才进入仓库 `Settings` → `Secrets and variables` → `Actions` 配置。

仓库 Variable：

- `PERF_BASE_URL`：目标 API 根地址，必须 HTTPS，例如 `https://api.example.com`

仓库 Secrets：

- `PERF_STUDENT_CREDENTIALS_JSON`
- `PERF_TEACHER_CREDENTIALS_JSON`
- `PERF_INTERNAL_OPS_TOKEN`

学生账号 Secret 示例（单行 JSON，不要使用真实学生个人账号）：

```json
[{"loginName":"perf_student","password":"替换为专用测试密码","tenantCode":"替换为学校租户码"}]
```

教师账号 Secret 示例（单行 JSON，只给最低必要的只读角色）：

```json
[{"loginName":"perf_teacher","password":"替换为专用测试密码","tenantCode":"替换为学校租户码"}]
```

`PERF_INTERNAL_OPS_TOKEN` 必须与服务器环境变量 `INTERNAL_OPS_TOKEN` 完全相同。至少 16 位，建议本地生成 48 字节随机值：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

将生成值同时放到服务器正式环境变量和 GitHub Secret，修改服务器环境变量后重启后端进程。

### 高负载阶段以后再配置

仓库 Secrets：

- `PERF_STUDENT_TOKENS_JSON`
- `PERF_TEACHER_TOKENS_JSON`

仓库 Variables：

- `PERF_ALLOW_HIGH_LOAD=true`：解锁 p500/p1000/p3000
- `PERF_ALLOW_PRODUCTION_HIGH_LOAD=true`：仅在正式批准后允许对 `api.hnyueke.com` 执行高负载

夜间远程任务在配置真实目标后执行 smoke。p500 以上只能手动触发，并需要解锁变量。每次压测前后都会抓取就绪状态和进程指标，随 k6 结果一起上传 Artifact。

## 验收门槛

- HTTP 错误率 `<0.5%`
- 业务检查通过率 `>99.5%`
- 核心读接口 `P95<1000ms`
- 核心读接口 `P99<2000ms`
- 无跨租户数据
- 无数据库连接池耗尽
- 无持续 502/504

结果必须填写到 `capacity-report-template.md`。没有真实执行的档位必须标记“未验证”，禁止直接宣称支持 10 万人同时在线。
