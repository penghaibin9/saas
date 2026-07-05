# 07 · Nginx 部署说明

> Nginx 负责：把你 build 出来的静态网站「挂到网上」，并处理刷新 404、开启压缩、缓存静态资源、加基础安全头，将来还负责把 `/api/` 转发给后端。
> 完整可复制的示例文件：`deploy/nginx/pc-frontend.conf.example`、`deploy/nginx/miniapp-h5.conf.example`。

---

## 1. Nginx 配置放在哪、怎么生效

- 站点配置通常放在 `/etc/nginx/conf.d/xxx.conf`（每个站点一个文件）。
- 改完**一定**先测试，再重载：

```bash
sudo nginx -t                 # 测试语法。出现 syntax is ok / test is successful 才算过
sudo systemctl reload nginx   # 平滑重载，不断开现有连接
```

> 口诀：**先 `nginx -t`，过了再 `reload`。** 没测就 reload，配置写错会导致整个 Nginx 起不来。

---

## 2. PC 前端完整站点配置（逐行讲解）

```nginx
server {
    listen       80;                       # 监听 80 端口（HTTP）
    server_name  admin.example.com;         # 你的域名；没有域名就写服务器 IP

    root   /var/www/pc-frontend;            # 网站根目录 = 放 frontend/dist 内容的地方
    index  index.html;

    # ① 前端路由兜底：解决「刷新子页面 404」
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ② 开启 gzip 压缩：网页更快
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1k;
    gzip_types text/plain text/css application/json application/javascript
               application/x-javascript text/xml application/xml image/svg+xml;
    gzip_vary on;

    # ③ 静态资源长缓存：js/css/图片带哈希名，可以放心缓存一年
    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    # ④ index.html 不缓存：保证每次发版用户能拿到最新入口
    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    # ⑤ 基础安全响应头
    add_header X-Frame-Options            "SAMEORIGIN"        always;
    add_header X-Content-Type-Options     "nosniff"           always;
    add_header Referrer-Policy            "strict-origin-when-cross-origin" always;
    add_header X-XSS-Protection           "1; mode=block"     always;

    # ⑥ 【预留】API 反向代理 —— 当前后端未接入，保持注释
    # location /api/ {
    #     proxy_pass http://127.0.0.1:8000;
    #     proxy_set_header Host $host;
    #     proxy_set_header X-Real-IP $remote_addr;
    #     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #     proxy_set_header X-Forwarded-Proto $scheme;
    # }
}
```

**每段是干什么的：**

| 段 | 作用 | 不写会怎样 |
|---|---|---|
| ① try_files | 单页应用路由兜底 | 刷新子页面直接 404 |
| ② gzip | 压缩传输 | 网页加载偏慢（能用，但不优） |
| ③ 静态缓存 | 加速二次访问 | 每次都重新下载资源 |
| ④ index.html 不缓存 | 发版后立刻生效 | 用户可能一直看到旧版本 |
| ⑤ 安全头 | 基础防护（点击劫持、嗅探等） | 安全性略弱 |
| ⑥ API 代理 | 将来转发给后端 | 现在用不到，先注释 |

---

## 3. 小程序 H5 站点配置

和 PC 几乎一样，只是 `root` 换成 H5 产物目录：

```nginx
server {
    listen       80;
    server_name  m.example.com;            # 小程序 H5 的域名/IP

    root   /var/www/miniapp-h5;             # 放 miniapp/dist/build/h5 内容的地方
    index  index.html;

    location / {
        try_files $uri $uri/ /index.html;   # 同样要兜底
    }

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1k;
    gzip_types text/plain text/css application/json application/javascript image/svg+xml;

    location ~* \.(?:js|css|png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, max-age=31536000, immutable";
        access_log off;
    }

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    add_header X-Frame-Options        "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff"    always;
}
```

---

## 4. 两个站点放在同一台服务器

有两种常见方式：

**方式 A：用不同域名 / 不同 server_name（推荐）**
- PC：`admin.example.com` → `/var/www/pc-frontend`
- H5：`m.example.com` → `/var/www/miniapp-h5`
- 两个 `.conf` 文件各一个 server 块即可。

**方式 B：用不同端口（没有域名时）**
- PC：`listen 80;`
- H5：`listen 8080;`
- 访问 `http://IP/`（PC）和 `http://IP:8080/`（H5）。记得防火墙放开 8080。

---

## 5. 配 HTTPS（有域名时建议，可选）

有域名后建议上 HTTPS。最省事的方式是用 `certbot` 自动申请免费证书：

```bash
# Ubuntu
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d admin.example.com -d m.example.com
```

certbot 会自动改好 Nginx 配置并加上 443。证书会自动续期。

> 没有域名（只有 IP）时暂时用 HTTP 即可，等有域名再上 HTTPS。

---

## 6. 排查：配置改了不生效 / 起不来

```bash
sudo nginx -t                          # 先看配置对不对，报错会指出文件和行号
sudo tail -n 50 /var/log/nginx/error.log   # 看错误日志
sudo systemctl status nginx            # 看服务状态
```

常见错误：
- `unknown directive` → 拼写错了，按行号改。
- `duplicate ... server_name` → 两个站点用了同一个 server_name/端口，改成不同的。
- 改完忘了 `reload` → `sudo systemctl reload nginx`。

更多故障处理见 `docs/ops/04-日志排查手册.md` 和 `docs/ops/05-故障应急处理.md`。
