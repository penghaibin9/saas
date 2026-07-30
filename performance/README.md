# 阶段 E：容量测试与可观测性

本目录用于验证系统在真实MySQL、Redis、多Worker/多实例和集中访问下的容量边界。

## 范围

第一批只压测核心只读接口：

- 学生：首页、待办、消息、本人档案
- 教师：工作台总览、待办、我的班级、风险学生

明确禁止：

- 文件上传、下载、预览、附件、公共文件中心
- COS、ClamAV、导入导出、归档任务
- 未经确认的生产高并发
- 用单个账号冒充500/1000/3000个真实用户

## 档位

| PROFILE | 目的 | 默认是否允许 |
|---|---|---|
| smoke | 验证脚本、鉴权和指标采集 | 是 |
| baseline | 20 VU基础容量 | 是 |
| p500 | 500并发阶梯 | 否，需显式解锁 |
| p1000 | 1000并发阶梯 | 否，需显式解锁 |
| p3000 | 3000并发阶梯 | 否，需显式解锁 |

`smoke`和`baseline`允许使用专用测试账号自动登录。高并发档位必须使用预签发Token池，避免登录限流污染容量结论。

## 生产运行参数审计

在服务器已经加载正式环境变量后执行：

```bash
python performance/tools/audit_capacity_runtime.py
```

它会拒绝以下状态进入容量验收：

- 未显式使用production模式
- 未启用真实MySQL
- 未配置Redis
- 仍是单Worker且未启用多实例
- 多Worker/多实例仍把Scheduler放在Web进程
- 未配置`INTERNAL_OPS_TOKEN`
- MySQL连接池预算不足

建议先声明数据库最大连接预算：

```bash
export CAPACITY_DB_CONNECTION_BUDGET=200
python performance/tools/audit_capacity_runtime.py
```

脚本只输出安全状态和计算结果，不回显密钥或完整数据库连接串。

## 准备XLSX账号表

```bash
cd backend
python ../performance/tools/prepare_k6_credentials.py \
  --template ../performance/local/capacity-accounts.xlsx
```

在本地填写学生和教师测试账号或预签发Token，然后生成k6 Secret文件：

```bash
python ../performance/tools/prepare_k6_credentials.py \
  --input ../performance/local/capacity-accounts.xlsx \
  --out ../performance/secrets
```

`performance/local/`、`performance/secrets/`和账号表不得提交。工具只输出数量，不回显密码和Token。

## 压测前监控探针

```bash
export INTERNAL_OPS_TOKEN='服务器实际运维探针令牌'
python performance/tools/probe_observability.py \
  --base-url https://staging.example.com \
  --samples 3 \
  --output performance/results/observability.json
```

探针要求`/health/ready`为READY，并验证`/internal/metrics`包含P50/P95/P99所需的基础指标结构。Token只从环境变量读取。

## 本地smoke示例

```bash
export BASE_URL=https://staging.example.com
export PROFILE=smoke
export SCENARIO=mixed
export K6_STUDENT_TOKENS_JSON="$(cat performance/secrets/student-tokens.json)"
export K6_TEACHER_TOKENS_JSON="$(cat performance/secrets/teacher-tokens.json)"
mkdir -p performance/results

docker run --rm \
  -v "$PWD:/work" -w /work \
  -e BASE_URL -e PROFILE -e SCENARIO \
  -e K6_STUDENT_TOKENS_JSON -e K6_TEACHER_TOKENS_JSON \
  -e SUMMARY_PATH=/work/performance/results/k6-summary.json \
  grafana/k6:0.54.0 run performance/k6/capacity.js
```

## GitHub Actions配置

入口：仓库 `Settings` → `Secrets and variables` → `Actions`。

### 新手首次smoke只需配置

仓库Variable：

- `PERF_BASE_URL`：目标API根地址，必须HTTPS，例如 `https://api.example.com`

仓库Secrets：

- `PERF_STUDENT_CREDENTIALS_JSON`
- `PERF_TEACHER_CREDENTIALS_JSON`
- `PERF_INTERNAL_OPS_TOKEN`

学生账号Secret示例（单行JSON，不要使用真实学生个人账号）：

```json
[{"loginName":"perf_student","password":"替换为专用测试密码","tenantCode":"替换为学校租户码"}]
```

教师账号Secret示例（单行JSON，只给最低必要的只读角色）：

```json
[{"loginName":"perf_teacher","password":"替换为专用测试密码","tenantCode":"替换为学校租户码"}]
```

`PERF_INTERNAL_OPS_TOKEN`必须与服务器环境变量`INTERNAL_OPS_TOKEN`完全相同。至少16位，建议本地生成48字节随机值：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

将生成值同时放到：

1. 服务器后端正式环境变量 `INTERNAL_OPS_TOKEN`
2. GitHub Secret `PERF_INTERNAL_OPS_TOKEN`

修改服务器环境变量后需要重启后端进程。

### 高负载阶段以后再配置

仓库Secrets：

- `PERF_STUDENT_TOKENS_JSON`
- `PERF_TEACHER_TOKENS_JSON`

仓库Variables：

- `PERF_ALLOW_HIGH_LOAD=true`：解锁p500/p1000/p3000
- `PERF_ALLOW_PRODUCTION_HIGH_LOAD=true`：仅在正式批准后允许对`api.hnyueke.com`执行高负载

夜间任务固定执行smoke。p500以上只能手动触发，并需要解锁变量。每次压测前后都会抓取就绪状态和进程指标，随k6结果一起上传Artifact。

## 验收门槛

- HTTP错误率 `<0.5%`
- 业务检查通过率 `>99.5%`
- 核心读接口 `P95<1000ms`
- 核心读接口 `P99<2000ms`
- 无跨租户数据
- 无数据库连接池耗尽
- 无持续502/504

结果必须填写到`capacity-report-template.md`。没有真实执行的档位必须标记“未验证”，禁止直接宣称支持10万人同时在线。
