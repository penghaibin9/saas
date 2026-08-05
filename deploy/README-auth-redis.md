# 登录验证码与生产 Redis 部署

本说明用于账号密码登录、图形验证码、失败计数、账号锁定、refresh token 与登出黑名单的生产 Redis 配置。

## 1. 服务器配置

1. 将 `deploy/auth-redis.production.env.example` 的键写入服务器受保护的环境文件或密钥管理服务。
2. 将 `REDIS_URL` 替换为腾讯云 Redis 的**内网连接地址**。密码必须 URL 编码；支持 TLS 时优先 `rediss://`。
3. 安全组只允许应用服务器访问 Redis 端口，不要向公网开放 6379/6380。
4. SaaS 多 worker / 多实例必须连接同一个 Redis 逻辑库，并使用独立的 `REDIS_KEY_PREFIX`。
5. 禁止把真实 Redis 密码、JWT 密钥或数据库密码提交到 GitHub。

## 2. 启动前验收

在应用服务器、以与正式后端相同的环境变量执行：

```bash
python backend/scripts/check_production_redis.py
```

该脚本会验证：

- 生产/预发环境必须存在 `REDIS_URL`；
- URL 协议只能是 `redis://` 或 `rediss://`；
- 默认禁止生产环境误连 `localhost`；
- Redis `PING`、临时键写入/读取；
- `GETDEL` 或 Lua 回退的单次原子消费；
- 日志仅输出主机、端口、库号、TLS 状态和前缀，不输出密码。

## 3. 正式启动

由 systemd、Supervisor、Docker Entrypoint 或发布平台调用：

```bash
bash deploy/start-backend-production.sh
```

该入口先执行 Redis 闸门，失败时后端不会启动；通过后才启动 Uvicorn 多 worker。`SCHEDULER_MODE` 应为 `external`，定时任务由独立进程运行。

## 4. 上线后检查

```bash
curl -fsS http://127.0.0.1:8000/health
```

随后用教师/管理端登录页执行两次错误密码，再确认出现验证码；填写正确验证码和密码后应进入 `/workbench`。验证码键必须在 Redis 中创建，并在登录提交时被单次消费。

> 仓库只能提供配置模板、启动闸门和自动化验收。腾讯云实例创建、VPC、安全组及真实密码注入必须在拥有服务器/腾讯云权限的环境执行。
