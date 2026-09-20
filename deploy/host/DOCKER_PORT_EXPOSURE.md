# Docker 发布端口现场安全验收

Docker 官方明确说明：Linux 上 Docker 发布容器端口时会创建自己的防火墙/NAT 规则，流量可能在 UFW 的 `INPUT` / `OUTPUT` 规则之前被转走。因此 **UFW 显示 deny 不能单独证明容器端口没有暴露**。

生产 CVM 必须在主机基础审计之后，再连续运行两条只读验收：

```bash
sudo python3 scripts/check/check-docker-port-exposure.py \
  --report /var/tmp/school-lifecycle-docker-port-exposure.json

sudo python3 scripts/check/check-dockerd-launch-flags.py \
  --report /var/tmp/school-lifecycle-dockerd-launch-flags.json
```

第一条读取**运行中容器和 Docker 网络真实状态**。默认仅允许 **80 / 443** 对非 loopback 主机接口发布。其他容器端口如确有经审批的公网用途，必须显式传入：

```bash
--allow-public-port <PORT>
```

但 3306 / 6379 / 3310 / 2375 / 2376 / 8000 等敏感服务不应使用此例外；它们应保持不发布或仅 loopback 绑定。

运行态端口审计会检查：

- `docker inspect`：实际 host port bindings；
- `Privileged`；
- `NetworkMode=host`；
- `PublishAllPorts/-P`；
- `/var/run/docker.sock` bind mount；
- `docker network inspect`：`nat-unprotected` 与 trusted host interface；
- daemon.json 中 `iptables/ip6tables` 是否被禁用；
- daemon.json 中 `allow-direct-routing` 是否被显式打开。

第二条读取**真实 dockerd 进程 `/proc/<pid>/cmdline`**，专门封堵“daemon.json 看起来安全，但 systemd `ExecStart` 通过启动参数绕过”的情况：

- `--iptables=false` / `--ip6tables=false`：FAIL；
- `-H tcp://...` / `--host=tcp://...`：FAIL；
- `--allow-direct-routing=true`：WARN，必须单独做网络架构评审；
- Docker TCP 管理端口即使配 TLS 也不作为本系统的允许方案。

两份报告都固定记录：

```json
{
  "mutatedHost": false,
  "productionDataAccessed": false
}
```

任意返回码非 0 时，禁止把“UFW 已开”“daemon.json 没写 hosts”或“安全组没放行”作为放行理由；必须先消除真实 Docker 暴露/启动参数绕过，或完成单独的网络架构安全评审。
