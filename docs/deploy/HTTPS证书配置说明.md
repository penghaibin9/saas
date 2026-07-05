# HTTPS 证书配置说明

> 真实学生的身份证/手机号必须走 HTTPS 传输。三种取证书方式，任选其一。

## 方式一：Let's Encrypt（免费，推荐 SaaS 云）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
# 自动改 nginx 配置并配置续期
sudo certbot renew --dry-run   # 验证自动续期
```
- 90 天有效，certbot 自动续期。
- 需域名已解析到本服务器、80 端口可访问。

## 方式二：云厂商免费证书（腾讯云/阿里云）
1. 在云控制台申请免费 DV 证书，验证域名。
2. 下载 nginx 格式证书（.crt + .key）。
3. 放到服务器（如 `/etc/nginx/ssl/`），在 nginx 配置引用：
   ```
   ssl_certificate     /etc/nginx/ssl/your.crt;
   ssl_certificate_key /etc/nginx/ssl/your.key;
   ```
- 有效期通常 1 年，到期前手动更新。

## 方式三：学校已有证书 / 私有化
- 学校信息中心提供证书文件，按方式二引用即可。
- 校内网私有化如无公网证书，可用内网 CA 或自签（浏览器需信任），但**仍要启用 TLS，不能明文**。

## 安全配置（模板已含，核对）
- [ ] 禁用 TLS 1.0 / 1.1，仅 TLS 1.2+
- [ ] `ssl_certificate` / `ssl_certificate_key` 路径正确
- [ ] 80 端口 301 跳转 443
- [ ] 证书链完整（含中间证书）
- [ ] 私钥 `.key` 权限 600，**不进 git**

## 红线
- 证书私钥、`.key`、`.pem` **一律不提交仓库**（CI 已加禁止文件检查）。
- 证书到期前提前更新，避免全站不可用。
- 配好后用浏览器确认小锁图标 + `smoke-school-trial.sh` 用 https 地址冒烟。
