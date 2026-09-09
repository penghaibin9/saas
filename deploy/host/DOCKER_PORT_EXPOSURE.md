# Docker 发布端口现场安全验收

Docker 官方明确说明：Linux 上 Docker 发布容器端口时会创建自己的防火墙/NAT 规则，流量可能在 UFW 的 `INPUT` / `OUTPUT` 规则之前被转走。因此 **UFW 显示 deny 不能单独证明容器端口没有暴露**。

生产 CVM 必须在主机基础审计之后，再运行：

```bash
sudo python3 scripts/check/check-docker-port-exposure.py \
  --report /var/tmp/school-lifecycle-docker-port-exposure.json
```

默认仅允许 **80 / 443** 对非 loopback 主机接口发布。其他容器端口如确有经审批的公网用途，必须显式传入：

```bash
--allow-public-port <PORT>
```

但 3306 / 6379 / 3310 / 2375 / 2376 / 8000 等敏感服务不应使用此例外；它们应保持不发布或仅 loopback 绑定。

审计器会读取运行中 Docker 的真实状态，不修改任何容器或网络：

- `docker inspect`：实际 host port bindings；
- `Privileged`；
- `NetworkMode=host`；
- `PublishAllPorts/-P`；
- `/var/run/docker.sock` bind mount；
- `docker network inspect`：`nat-unprotected` 与 trusted host interface；
- daemon `iptables/ip6tables` 是否被禁用；
- daemon `allow-direct-routing` 是否被显式打开。

报告固定记录：

```json
{
  "mutatedHost": false,
  "productionDataAccessed": false
}
```

返回码非 0 时禁止把“UFW 已开”作为放行理由，必须先消除实际 Docker 暴露或完成单独的网络架构安全评审。
