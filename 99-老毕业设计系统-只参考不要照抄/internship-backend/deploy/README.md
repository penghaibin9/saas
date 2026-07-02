# 生产部署指南

## 部署方案：Docker 一键部署（✅ 已选定）
```bash
cd internship-backend
cp .env.example .env        # 必改：DB_PASSWORD、JWT_SECRET（>=32位随机串）
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml exec app npm run migrate:all   # 首次初始化
```
访问 http://服务器IP/ 即打开 PC 管理端（同源代理 /api，无需改前端配置）。

## 备选方案：裸机 PM2（仅在无法使用 Docker 的服务器上采用）
```bash
npm ci --omit=dev && cp .env.example .env  # 配置数据库与 JWT
npm run migrate:all
npm i -g pm2 && pm2 start deploy/ecosystem.config.js && pm2 save
```
前面挂 nginx（参考 deploy/nginx.conf，把 app:3000 改为 127.0.0.1:3000）。

## 上线检查单
- [ ] .env 中 JWT_SECRET 为强随机值，NODE_ENV=production
- [ ] MySQL 仅内网可达，root 强密码；应用账号最小权限
- [ ] HTTPS 证书（certbot/学校统一证书），80 跳 443
- [ ] crontab 配置 deploy/backup.sh 每日备份，备份文件异机存放
- [ ] 小程序后台配置 request 合法域名为 https 正式域名
- [ ] 压测：模拟 2000 学生 10 分钟内集中打卡（可用 autocannon）
- [ ] 演示账号/演示模式关闭，初始密码全部强制修改
