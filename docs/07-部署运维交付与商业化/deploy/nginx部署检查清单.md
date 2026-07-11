# nginx 部署检查清单

> 配套模板：`deploy/nginx/nginx.https.conf.example`。反代后端 + 托管前端静态资源 + HTTPS。

## 配置要点
- [ ] 后端只监听 `127.0.0.1:8000`，由 nginx 反代 `/api/`（8000 不对公网）。
- [ ] PC 管理端 `dist/` 作为站点根，`try_files $uri /index.html`（前端路由）。
- [ ] 学生/教师 H5（miniapp build:h5）单独路径或子域名。
- [ ] `/api/` → `proxy_pass http://127.0.0.1:8000;` 并透传 `Authorization`、`Host`、`X-Real-IP`。
- [ ] 上传大小：`client_max_body_size 50m;`（毕设/材料大文件）。
- [ ] 仅放行 80/443；80 跳转 443。

## 检查清单（reload 前）
- [ ] `nginx -t` 通过
- [ ] 证书路径正确、未过期（见《HTTPS证书配置说明》）
- [ ] TLS 版本收敛：禁用 TLS1.0/1.1（模板已含）
- [ ] gzip 开启（静态资源）
- [ ] 反代超时合理（大文件上传 `proxy_read_timeout` 调大）
- [ ] 安全响应头（可选）：`X-Content-Type-Options nosniff` 等

## 常见问题
| 现象 | 排查 |
|---|---|
| 前端刷新 404 | 缺 `try_files ... /index.html` |
| 接口 502 | 后端未起 / 端口不对 / 防火墙 |
| 登录后立即掉登录 | `Authorization` 头没透传 |
| 大文件上传失败 | `client_max_body_size` 太小 |
| 跨域报错 | 后端 `CORS_ORIGINS` 与实际域名不一致 |

## reload
```bash
nginx -t && systemctl reload nginx
```
改完用 `scripts/check/smoke-school-trial.sh` 冒烟验证。
