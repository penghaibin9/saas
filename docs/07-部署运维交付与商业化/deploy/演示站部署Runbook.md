# 演示站部署 Runbook

> 面向：搭一个**长期在线的售前演示站**（给学校看，不接真实学生数据）。比生产宽松，但也要安全。

## 与生产的区别
- 演示站**可以开** `mock-login`（方便一键体验演示账号），但**必须用演示数据、不放真实学生**。
- 演示站可保留 `/docs`（方便技术对接），生产必须关。
- 数据可随时重置。

## 步骤
1. 🟦 服务器 + 域名（如 demo.你的域名）+ HTTPS（见《HTTPS证书配置说明》）。
2. 🟦 `backend/.env`：
   - `APP_ENV=production`（仍建议，收敛安全）或 `demo`
   - `DEBUG=false`
   - 强 `JWT_SECRET`
   - `DB_ENABLED=true` + 独立演示库 `saas_lifecycle_demo`
   - `CORS_ORIGINS=https://demo.你的域名`
   - `MOCK_LOGIN_ENABLED=true`（演示站可开）
   - `SMS_ENABLED=false`
3. 🟦 灌演示数据：`python backend/scripts/seed_mysql_demo_data.py`（含六域 + 演示学生张一鸣等）。
4. 🟦 构建前端/小程序 H5 并部署到 nginx（同生产步骤）。
5. 🟩 冒烟：`BASE_URL=https://demo.你的域名 bash scripts/check/smoke-school-trial.sh`（注意演示站 mock-login 开、/docs 可开，个别 INFO 属正常）。
6. 🟦 定期（如每周）重置演示库，保持数据干净。

## 演示站红线
- **绝不放真实学生数据**（演示数据即可）。
- 演示账号口令不要用于任何真实环境。
- 演示站也要 HTTPS（避免账号明文传输被截）。
- 演示站与生产**库、域名、密钥全部分开**。
