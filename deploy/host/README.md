# 生产主机安全加固 Runbook（腾讯云 CVM / Ubuntu）

> 范围：服务器主机层。它是 PR #265 应用/容器/部署安全之后的下一层，不替代 #265，也不代表已经操作真实生产服务器。
>
> 原则：**先只读审计，后逐项变更；任何可能导致 SSH 断连、Docker 重启或网络中断的动作都必须保留云控制台救援路径和第二个已验证 SSH 会话。**

## 0. 施工边界

本目录提供：

- 主机只读审计：`scripts/check/check-host-security.py`；
- Docker 运行态端口/容器边界只读审计：`scripts/check/check-docker-port-exposure.py`；
- 实际 dockerd 启动参数只读审计：`scripts/check/check-dockerd-launch-flags.py`；
- SSH / sysctl / Docker daemon 样板；
- 腾讯云控制面人工验收清单；
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

## 2. 第一遍：部署前只读预检

从待部署仓库根目录执行：

```bash
sudo python3 scripts/check/check-host-security.py \
  --ssh-port 22 \
  --secret-path /etc/school-lifecycle/security.env \
  --report /var/tmp/school-lifecycle-host-security.json

sudo python3 scripts/check/check-docker-port-exposure.py \
  --preflight-empty-ok \
  --report /var/tmp/school-lifecycle-docker-port-preflight.json

sudo python3 scripts/check/check-dockerd-launch-flags.py \
  --report /var/tmp/school-lifecycle-dockerd-launch-flags.json
```

如果 SSH 不是 22，必须把 `--ssh-port` 改为真实值。如果正式环境变量文件位置不同，可重复传入 `--secret-path`。

如果确有经过批准的账号必须加入 `docker` 组，只能显式声明，例如：

```bash
--allow-docker-user <APPROVED_ADMIN_USER>
```

未声明的 docker 组成员是 FAIL；已声明成员仍保留 WARN，因为 docker 组具备接近 root 的主机控制能力。优先使用 `sudo docker ...`，不要为了方便批量把普通账号加入 docker 组。

部署前预检允许 Docker 尚无运行容器，所以第二条命令使用 `--preflight-empty-ok`。如果此时没有容器，报告必须明确：

```json
{
  "preflightEmptyAllowed": true,
  "runtimeEvidenceComplete": false
}
```

这只允许继续**主机加固施工**，不代表 Docker 最终运行态已验收。`--preflight-empty-ok` **禁止用于最终上线证据**。

预检至少覆盖：

- SSH root/password/kbd-interactive 登录；
- SSH 会话/重试/转发策略；
- 主机真实 TCP/UDP 监听端口；
- 任意非 loopback 的非批准监听，包括绑定到具体 VPC/实例网卡 IP 的端口；
- 3306/6379/3310/2375/2376/8000 等敏感端口；
- UFW active/default-deny/SSH 来源限制及覆盖敏感端口的端口范围规则；
- Nginx 有效配置、TLS 1.2/1.3 与安全 include；
- 内核基础 hardening sysctl；
- Docker daemon TCP socket / insecure registry / live-restore / no-new-privileges / 日志轮转；
- Docker socket 权限与 docker 组成员；
- 实际 dockerd 启动参数中的 `--iptables=false` / `--ip6tables=false` / `-H tcp://...`；
- NTP、systemd、AppArmor、persistent journald；
- 指定密钥文件权限。

## 3. 腾讯云安全组：第一层网络边界

修改前先导出/备份安全组规则，详见 `deploy/host/TENCENT_CLOUD_CONTROL_PLANE.md`。

生产建议只保留下列互联网入站：

| 端口 | 来源 | 用途 |
|---|---|---|
| SSH 实际端口 | **管理员固定公网 CIDR** | 运维 |
| 80/tcp | `0.0.0.0/0`、`::/0`（如启用 IPv6） | 仅 HTTP→HTTPS/ACME |
| 443/tcp | `0.0.0.0/0`、`::/0` | 正式 HTTPS |

以下端口不得直接面向互联网：3306 MySQL、6379 Redis、3310 ClamAV、2375/2376 Docker API、8000 FastAPI upstream，以及任何临时调试/Vite/Node dev server 端口。

**不要先删 SSH 放行再测试新规则。** 先新增正确的管理员来源规则，开启第二会话验证，最后再移除旧规则。

## 4. SSH：禁 root + 禁密码

先复制模板到 drop-in：

```bash
sudo install -m 0644 deploy/host/sshd-hardening.conf.example \
  /etc/ssh/sshd_config.d/99-school-lifecycle-hardening.conf
sudo sshd -t
```

`sshd -t` 失败时立即撤销该文件，**禁止 reload**。语法通过后：

```bash
sudo systemctl reload ssh || sudo systemctl reload sshd
```

然后保持当前 SSH 会话不退出，新开第二个终端，用非 root 公钥账号登录，确认 `sudo -v` 正常，再确认 root/password 登录被拒绝。最后重新跑主机审计。

回滚：通过腾讯云控制台/VNC 删除 drop-in，`sshd -t` 通过后再 reload。

## 5. 主机防火墙：第二层网络边界

腾讯云安全组是第一层；UFW 作为第二层。但 Docker 发布端口可能通过自己的 NAT/防火墙链路绕开 UFW 的直觉判断，所以 **UFW 通过后仍必须跑 Docker 运行态审计**。

示例（替换占位值后才执行）：

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

不允许新增 3306/6379/3310/2375/2376/8000 的公网放行，也不允许用宽端口范围间接覆盖这些端口。

## 6. sysctl：保守型云主机基线

模板故意不强制 `rp_filter`、不禁 IPv6，避免破坏腾讯云/VPC 路由。

```bash
sudo install -m 0644 deploy/host/sysctl-hardening.conf.example \
  /etc/sysctl.d/99-school-lifecycle-hardening.conf
sudo sysctl --system
```

执行后立刻重新跑只读主机审计。如果发现网络异常，先移除该文件并重新 `sysctl --system`。

## 7. Docker daemon + 实际运行态

**不要直接覆盖现有 `/etc/docker/daemon.json`。** 先备份并人工合并模板字段：

```bash
sudo cp -a /etc/docker/daemon.json /etc/docker/daemon.json.before-school-hardening 2>/dev/null || true
cat deploy/host/docker-daemon.json.example
```

目标：

- `live-restore=true`；
- 默认 `no-new-privileges=true`；
- 有界日志轮转；
- 不存在 Docker TCP 管理监听；
- 不允许 insecure registries；
- Docker `iptables/ip6tables` 集成不被关闭；
- docker 组成员为零，或只有逐个审批并在审计命令中显式列出的例外账号。

合并完成后：

```bash
python3 -m json.tool /etc/docker/daemon.json >/dev/null
sudo dockerd --validate --config-file=/etc/docker/daemon.json
```

如当前 Docker 版本不支持 `--validate`，不要跳过人工配置复核。

在维护窗口内才允许重启/重载 Docker。重启前确认当前容器、Compose 项目、备份任务和回滚路径均已记录。

生产容器启动后，必须执行**最终严格模式**，这里禁止带 `--preflight-empty-ok`：

```bash
sudo python3 scripts/check/check-docker-port-exposure.py \
  --report /var/tmp/school-lifecycle-docker-port-exposure.json
sudo python3 scripts/check/check-dockerd-launch-flags.py \
  --report /var/tmp/school-lifecycle-dockerd-launch-flags.json
```

最终 Docker 端口报告必须同时满足：

- `passed=true`；
- `preflightEmptyAllowed=false`；
- `runtimeEvidenceComplete=true`。

运行态检查覆盖真实 `docker inspect` / `docker network inspect`，包括 `Privileged`、host network、`-P`、docker.sock bind、published ports、`nat-unprotected` 和 trusted host interfaces。

`daemon.json` 安全但实际 dockerd 启动参数出现 `--iptables=false`、`--ip6tables=false` 或 `-H/--host tcp://...`，仍判定不通过。详见 `deploy/host/DOCKER_PORT_EXPOSURE.md`。

## 8. Nginx / TLS

继续复用：

- `deploy/nginx/security-http.conf`
- `deploy/nginx/security-server.conf`
- `deploy/nginx/security-headers.conf`
- #265 HTTPS 四端部署基线

现场先执行：

```bash
sudo nginx -t
```

正式站点必须满足：80 仅 301/308→HTTPS 或 ACME、TLS 仅 1.2/1.3、证书链完整、`/docs`/调试入口不可公网访问、FastAPI upstream 不直接暴露、证书自动续期任务存在并完成 dry-run/等价验证。

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

## 10. 备份与恢复：复用现有生产资产

仓库已经有完整备份/恢复施工，不另造第二套：

- `deploy/backup/machine-backup-runner.sh`
- `deploy/backup/machine-restore-drill.sh`
- `deploy/backup/restore-drill.sh`
- `deploy/backup/pitr-drill.sh`

恢复入口示例：

```bash
bash deploy/backup/machine-restore-drill.sh <manifest.json> <drill_db_name>
```

恢复脚本要求隔离环境，并对恢复后的对象/文件字节/SHA-256 等证据进行核对。**生产发布前必须至少完成一次隔离恢复演练。** 演练库必须与生产库不同名，禁止把“备份文件存在”当成恢复成功。

## 11. 主机上线验收顺序

按以下顺序，不并行跳步：

1. 云控制台/VNC/快照可回滚；
2. 部署前主机只读预检；
3. 腾讯云安全组与控制面检查；
4. 第二 SSH 公钥会话；
5. SSH hardening；
6. 主机防火墙；
7. sysctl；
8. Docker daemon；
9. 启动正式容器；
10. Docker 运行态端口 + 实际 dockerd 参数最终严格审计；
11. Nginx/TLS；
12. 补丁/NTP/CWP/AppArmor/日志；
13. 备份；
14. 隔离恢复演练；
15. 再跑主机审计 + Docker 最终严格审计并归档 JSON；
16. 最后才进入真实学校账号、CAS/微信、首管权限与生产数据验收。

## 12. 最终发布判定

代码侧全绿 **不等于** 主机已安全上线。最终发布至少需要同时具备：

- PR #265 exact-head 自动化绿灯证据；
- 主机安全审计 `passed=true`；
- Docker 运行态端口审计 `passed=true` 且 `runtimeEvidenceComplete=true`；
- Docker 最终报告 `preflightEmptyAllowed=false`；
- dockerd 实际启动参数审计 `passed=true`；
- 安全组截图/导出；
- SSH 二次登录验收；
- Docker/Nginx/TLS 现场验收；
- 腾讯云主机安全在线；
- 最新成功备份证据；
- 隔离恢复演练证据；
- 真实首管岗位最小权限盘点；
- 微信/CAS 等真实身份源验收。

任何 `--preflight-empty-ok` 产生的报告都只能作为部署前施工证据，**不得作为最终发布证据**。
