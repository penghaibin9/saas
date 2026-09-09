# 生产主机安全加固 Runbook（腾讯云 CVM / Ubuntu）

> 范围：服务器主机层。它是 PR #265 应用/容器/部署安全之后的下一层，不替代 #265，也不代表已经操作真实生产服务器。
>
> 原则：**先只读审计，后逐项变更；任何可能导致 SSH 断连、Docker 重启或网络中断的动作都必须保留云控制台救援路径和第二个已验证 SSH 会话。**

## 0. 施工边界

本目录只提供：

- 只读主机审计器：`scripts/check/check-host-security.py`；
- SSH drop-in 样板；
- sysctl 样板；
- Docker daemon 样板；
- 明确的现场操作与回滚顺序。

本阶段 **不会自动执行**：

- 腾讯云安全组修改；
- SSH 端口/认证方式修改；
- UFW/firewalld 规则变更；
- Docker daemon 重启；
- 正式 TLS 证书签发/替换；
- 生产数据库、生产密钥或真实学校账号操作。

这些必须在目标 CVM 上由授权人员按本 Runbook 逐项实施。

---

## 1. 上机前硬门

未同时满足以下条件，不进入主机写操作：

1. PR #265 对应发布候选仍有可追溯 commit SHA；
2. 腾讯云控制台可登录，并确认拥有 CVM VNC/救援能力；
3. 已创建 **非 root** 运维账号并导入 SSH 公钥；
4. 已在第二个终端实际用该账号登录成功；
5. 已记录当前 SSH 端口和管理员来源公网 CIDR；
6. 已创建 CVM 快照或等价可回退点；
7. 已确认当前 Docker/Compose/Nginx 配置位置并做离机备份；
8. 已确认生产密钥不在 Git 仓库、不在 shell history、不在可公开日志中。

## 2. 第一遍：只读审计

从待部署仓库根目录执行：

```bash
sudo python3 scripts/check/check-host-security.py \
  --ssh-port 22 \
  --secret-path /etc/school-lifecycle/security.env \
  --report /var/tmp/school-lifecycle-host-security.json
```

如果 SSH 不是 22，必须把 `--ssh-port` 改为真实值。

如果正式环境变量文件位置不同，重复传入 `--secret-path`：

```bash
--secret-path /etc/school-lifecycle/security.env \
--secret-path /etc/school-lifecycle/backup.env
```

**返回码 0 才代表当前脚本没有发现 FAIL。** `WARN` 仍需人工判断。报告明确记录 `mutatedHost=false` 与 `productionDataAccessed=false`。

审计至少覆盖：

- SSH root/password/kbd-interactive 登录；
- SSH 会话/重试/转发策略；
- 主机监听端口；
- 3306/6379/3310/2375/2376/8000 等敏感端口是否暴露；
- 内核基础 hardening sysctl；
- Docker daemon TCP socket / insecure registry / live-restore / 日志轮转；
- Docker socket 权限；
- NTP；
- Docker/Nginx systemd 状态；
- AppArmor；
- persistent journald；
- 指定密钥文件权限。

## 3. 腾讯云安全组：作为第一层边界

生产建议只保留下列互联网入站：

| 端口 | 来源 | 用途 |
|---|---|---|
| SSH 实际端口 | **管理员固定公网 CIDR** | 运维 |
| 80/tcp | `0.0.0.0/0`、`::/0`（如启用 IPv6） | 仅 HTTP→HTTPS/ACME |
| 443/tcp | `0.0.0.0/0`、`::/0` | 正式 HTTPS |

以下端口不得直接面向互联网：

- 3306 MySQL
- 6379 Redis
- 3310 ClamAV
- 2375/2376 Docker remote API
- 8000 FastAPI upstream
- 任何临时调试端口 / Vite dev server / Node dev server

**不要先删 SSH 放行再测试新规则。** 先新增正确的管理员来源规则，开启第二会话验证，最后再移除旧规则。

## 4. SSH：禁 root + 禁密码

先复制模板到 drop-in：

```bash
sudo install -m 0644 deploy/host/sshd-hardening.conf.example \
  /etc/ssh/sshd_config.d/99-school-lifecycle-hardening.conf
sudo sshd -t
```

`sshd -t` 失败时立即撤销该文件，**禁止 reload**。

语法通过后：

```bash
sudo systemctl reload ssh || sudo systemctl reload sshd
```

然后：

1. 保持当前 SSH 会话不要退出；
2. 新开第二终端；
3. 用非 root 公钥账号重新登录；
4. 确认 `sudo -v` 正常；
5. 确认 root/password 登录被拒绝；
6. 再运行主机审计器。

回滚：通过腾讯云控制台/VNC 删除 drop-in 后 `sshd -t`，再 reload。

## 5. 主机防火墙：第二层边界

腾讯云安全组是第一层；主机防火墙作为第二层。Ubuntu 可使用 UFW，但**必须先放行真实 SSH 端口和管理员来源 CIDR**。

示例（把占位值替换成真实值后再执行）：

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <ADMIN_CIDR> to any port <SSH_PORT> proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status numbered
```

确认第二 SSH 会话仍正常后才：

```bash
sudo ufw enable
sudo ufw status verbose
```

不允许新增 3306/6379/3310/2375/2376/8000 的公网放行。

## 6. sysctl：保守型云主机基线

模板故意不强制 `rp_filter`、不禁 IPv6，避免破坏腾讯云/VPC 路由。

```bash
sudo install -m 0644 deploy/host/sysctl-hardening.conf.example \
  /etc/sysctl.d/99-school-lifecycle-hardening.conf
sudo sysctl --system
```

执行后立刻重新跑只读审计器。如果发现网络异常，先移除该文件并重新 `sysctl --system`。

## 7. Docker daemon

**不要直接覆盖现有 `/etc/docker/daemon.json`。** 先备份并合并模板字段：

```bash
sudo cp -a /etc/docker/daemon.json /etc/docker/daemon.json.before-school-hardening 2>/dev/null || true
cat deploy/host/docker-daemon.json.example
```

目标：

- `live-restore=true`；
- 默认 `no-new-privileges=true`；
- 有界日志轮转；
- 不存在 `tcp://...` Docker 管理监听；
- 不允许 insecure registries。

合并完成后先验证 JSON：

```bash
python3 -m json.tool /etc/docker/daemon.json >/dev/null
```

若当前 Docker 支持配置验证，再执行：

```bash
sudo dockerd --validate --config-file=/etc/docker/daemon.json
```

在维护窗口内才允许重启 Docker。重启前确认当前容器、Compose 项目、备份任务和回滚路径均已记录。

## 8. Nginx / TLS

继续复用仓库已有：

- `deploy/nginx/security-http.conf`
- `deploy/nginx/security-server.conf`
- `deploy/nginx/security-headers.conf`
- #265 的 HTTPS 四端部署基线

现场硬门：

```bash
sudo nginx -t
```

正式站点必须：

- 80 只做 301/308 → HTTPS 或 ACME；
- TLS 仅 1.2 / 1.3；
- 证书链完整；
- `/docs`、调试入口、内部管理端口不对公网开放；
- upstream FastAPI 不直接暴露公网；
- 证书自动续期任务存在，并进行一次 dry-run/等价验证。

替换正式证书前先备份当前证书引用与 Nginx 配置；`nginx -t` 成功后只 reload，不无条件 restart。

## 9. 补丁、时间与主机防护

最低要求：

- NTP 同步正常；
- Ubuntu/Debian security update timer 启用；
- 腾讯云主机安全/CWP 或等价主机防护启用并在线；
- AppArmor 保持启用；
- journald 使用持久化日志；
- 不在生产主机长期保留编译器、调试器、临时脚本和明文凭据。

系统内核/容器运行时大版本升级必须进入独立维护窗口，不能与业务发布混在同一次操作中。

## 10. 备份与恢复：直接复用现有生产资产

仓库已经有完整备份/恢复施工，不另造第二套：

- `deploy/backup/machine-backup-runner.sh`
- `deploy/backup/machine-restore-drill.sh`
- `deploy/backup/restore-drill.sh`
- `deploy/backup/pitr-drill.sh`

机器备份入口会运行现有 verified offsite backup，并记录机器证据；恢复入口要求：

```bash
bash deploy/backup/machine-restore-drill.sh <manifest.json> <drill_db_name>
```

恢复脚本明确拒绝非本机数据库地址，并对恢复后的 local FileObject 数量、文件字节与 SHA-256 进行核对。

**生产发布前必须至少完成一次隔离恢复演练。** 演练库必须与生产库不同名，禁止把“备份文件存在”当成恢复成功。

## 11. 主机上线验收顺序

按以下顺序，不并行跳步：

1. 云控制台/VNC/快照可回滚；
2. 只读主机审计；
3. 腾讯云安全组；
4. 第二 SSH 公钥会话；
5. SSH hardening；
6. 主机防火墙；
7. sysctl；
8. Docker daemon；
9. Nginx/TLS；
10. 补丁/NTP/CWP/AppArmor/日志；
11. 备份；
12. 隔离恢复演练；
13. 再跑只读主机审计并归档 JSON；
14. 最后才进入真实学校账号、CAS/微信、首管权限与生产数据验收。

## 12. 最终发布判定

代码侧全绿 **不等于** 主机已安全上线。最终发布至少需要同时具备：

- PR #265 的 exact-head 自动化绿灯证据；
- 本主机审计 `passed=true`；
- 安全组截图/导出；
- SSH 二次登录验收；
- Docker/Nginx/TLS 现场验收；
- 腾讯云主机安全在线；
- 最新成功备份证据；
- 隔离恢复演练证据；
- 真实首管岗位最小权限盘点；
- 微信/CAS 等真实身份源验收。
