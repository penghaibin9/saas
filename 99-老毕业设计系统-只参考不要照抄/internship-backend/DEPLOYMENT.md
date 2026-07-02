# 部署指南和最佳实践

## 📦 生产环境部署

### 1. 前置准备

**服务器环境要求：**
- Node.js 14.x 或更高版本
- MySQL 5.7 或 8.0
- npm 或 yarn
- 1GB+ 可用内存
- 20GB+ 磁盘空间

**系统推荐：**
- Ubuntu 20.04 LTS
- CentOS 7/8
- Debian 10+

### 2. 部署步骤

#### 步骤1：服务器准备
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 MySQL
sudo apt install -y mysql-server

# 验证安装
node -v
npm -v
mysql --version
```

#### 步骤2：项目部署
```bash
# 克隆或上传项目
git clone <your-repo-url> internship-backend
cd internship-backend

# 安装依赖
npm install --production

# 复制环境配置
cp .env.example .env

# 配置环境变量（编辑 .env）
nano .env
```

#### 步骤3：数据库初始化
```bash
# 创建数据库用户和权限
mysql -u root -p

mysql> CREATE USER 'internship'@'localhost' IDENTIFIED BY 'strong_password';
mysql> GRANT ALL PRIVILEGES ON internship_management.* TO 'internship'@'localhost';
mysql> FLUSH PRIVILEGES;
mysql> EXIT;

# 初始化数据库结构
npm run init:db
```

#### 步骤4：使用 PM2 启动服务
```bash
# 全局安装 PM2
sudo npm install -g pm2

# 启动应用
pm2 start app.js --name "internship-api"

# 设置开机自启
pm2 startup
pm2 save

# 查看状态
pm2 status
pm2 logs internship-api
```

### 3. Nginx 反向代理配置

```nginx
# /etc/nginx/sites-available/internship-api
upstream internship_api {
    server 127.0.0.1:3000;
    keepalive 64;
}

server {
    listen 80;
    listen [::]:80;
    server_name api.example.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.example.com;

    # SSL 证书配置
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 日志
    access_log /var/log/nginx/internship-api-access.log;
    error_log /var/log/nginx/internship-api-error.log;

    # 代理设置
    location / {
        proxy_pass http://internship_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 上传文件大小限制
    client_max_body_size 20M;
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/internship-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. SSL 证书配置（Let's Encrypt）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书
sudo certbot certonly --standalone -d api.example.com

# 自动续期设置
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 5. 备份策略

#### 数据库备份
```bash
# 创建备份目录
mkdir -p /backups/database

# 每天凌晨2点执行备份
0 2 * * * mysqldump -u internship -p'strong_password' internship_management > /backups/database/backup_$(date +\%Y\%m\%d).sql

# 定期清理旧备份
0 3 * * * find /backups/database -mtime +30 -delete
```

#### 应用备份
```bash
# 定期备份 uploads 目录
0 3 * * 0 tar -czf /backups/uploads/uploads_$(date +\%Y\%m\%d).tar.gz /path/to/internship-backend/uploads
```

---

## 🔒 安全配置

### 1. 环境变量安全

**生产环境 .env 配置：**
```env
# 修改所有密钥和密码
DB_HOST=db.example.com
DB_USER=internship_user
DB_PASSWORD=<strong_random_password>

JWT_SECRET=<long_random_string_min_32_chars>
JWT_EXPIRES_IN=7d

# 可选的应用监听地址
PORT=3000
NODE_ENV=production
```

### 2. 防火墙规则

```bash
# UFW 防火墙配置
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 允许 SSH
sudo ufw allow 22/tcp

# 允许 HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 启用防火墙
sudo ufw enable
```

### 3. 速率限制

在 app.js 中添加速率限制中间件：

```javascript
const rateLimit = require('express-rate-limit');

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15分钟
  max: 100 // 限制100个请求
});

app.use('/api/', limiter);

// 登录接口更严格的限制
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5
});

app.post('/api/users/login', loginLimiter, (req, res) => {
  // ...
});
```

### 4. CORS 配置

```javascript
// app.js 中的 CORS 配置
app.use(cors({
  origin: process.env.NODE_ENV === 'production' 
    ? 'https://example.com' 
    : 'http://localhost:3000',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));
```

### 5. 密钥轮转

```bash
# 定期更新 JWT_SECRET（需要所有用户重新登录）
# 更新 .env 中的 JWT_SECRET
# 重启应用
pm2 restart internship-api
```

---

## 📊 性能优化

### 1. 数据库优化

```sql
-- 添加重要查询的索引
ALTER TABLE t_user ADD INDEX idx_username_status (username, status);
ALTER TABLE t_application ADD INDEX idx_student_status (student_id, status);
ALTER TABLE t_application ADD INDEX idx_teacher_status (teacher_id, status);

-- 启用查询缓存
SET GLOBAL query_cache_size = 268435456; -- 256MB

-- 连接池参数优化
-- 在 config/db.js 中：
// waitForConnections: true,
// connectionLimit: 20,  // 从10增加到20
// queueLimit: 0
```

### 2. Node.js 优化

```bash
# 使用集群模式（PM2 配置文件 ecosystem.config.js）
module.exports = {
  apps: [{
    name: 'internship-api',
    script: './app.js',
    instances: 'max',  // 使用所有CPU核心
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production'
    }
  }]
};

# 启动
pm2 start ecosystem.config.js
```

### 3. 缓存策略

```javascript
// 在控制器中添加缓存
const redis = require('redis');
const client = redis.createClient({
  host: 'localhost',
  port: 6379
});

// 缓存大学列表（1小时过期）
async function getColleges(req, res) {
  const cacheKey = 'colleges:all';
  
  // 尝试从缓存获取
  const cached = await client.get(cacheKey);
  if (cached) {
    return res.json(JSON.parse(cached));
  }
  
  // 查询数据库
  const data = await collegeModel.getAll();
  
  // 存入缓存
  await client.setex(cacheKey, 3600, JSON.stringify(data));
  
  res.json(data);
}
```

### 4. 静态资源优化

```javascript
// 启用 gzip 压缩
const compression = require('compression');
app.use(compression());

// 添加缓存头
app.use((req, res, next) => {
  res.set('Cache-Control', 'public, max-age=3600');
  next();
});
```

---

## 📈 监控和日志

### 1. PM2 监控

```bash
# 启用 PM2 监控面板
pm2 web

# 访问 http://localhost:9615

# 导出日志
pm2 logs internship-api > app.log

# 监控实时输出
pm2 monit
```

### 2. 系统日志配置

```bash
# 配置 systemd journalctl 日志
journalctl -u pm2-root -f  # 实时查看日志

# 查看历史日志
journalctl -u pm2-root -n 100
```

### 3. 应用日志

在 app.js 中添加日志记录：

```javascript
const fs = require('fs');
const path = require('path');

const logDir = path.join(__dirname, 'logs');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir);
}

// 记录所有请求
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  const log = `[${timestamp}] ${req.method} ${req.path}`;
  console.log(log);
  
  fs.appendFileSync(path.join(logDir, 'access.log'), log + '\n');
  next();
});

// 错误日志
process.on('uncaughtException', (err) => {
  const log = `[${new Date().toISOString()}] ERROR: ${err.message}\n${err.stack}`;
  fs.appendFileSync(path.join(logDir, 'error.log'), log + '\n');
});
```

---

## 🔍 故障诊断

### 常见问题解决

**问题 1: 应用崩溃**
```bash
# 查看 PM2 日志
pm2 logs internship-api --err

# 重启应用
pm2 restart internship-api

# 检查是否有内存泄漏
pm2 show internship-api
```

**问题 2: 数据库连接缓慢**
```bash
# 检查 MySQL 连接数
mysql -u root -p -e "SHOW PROCESSLIST;"

# 增加连接池大小或查询超时设置
```

**问题 3: 高 CPU 占用**
```bash
# 使用 clinic.js 诊断
npm install -g clinic
clinic doctor -- node app.js
```

---

## 📋 检查清单

### 部署前检查
- [ ] 所有依赖包已安装
- [ ] .env 配置完整且正确
- [ ] 数据库初始化成功
- [ ] 防火墙规则已配置
- [ ] SSL 证书已安装
- [ ] Nginx 反向代理已配置
- [ ] PM2 自启已配置
- [ ] 备份脚本已设置

### 部署后检查
- [ ] 应用正在运行（pm2 status）
- [ ] 数据库连接正常
- [ ] API 接口可访问
- [ ] SSL 证书有效
- [ ] 日志文件正常记录
- [ ] 监控告警已配置

---

## 📞 紧急联系

如有生产环境问题，请立即：
1. 查看应用日志
2. 检查数据库连接
3. 验证磁盘空间
4. 检查内存占用
5. 查看 Nginx 错误日志

```bash
# 快速诊断命令
pm2 status
pm2 logs
mysql -u root -p -e "SELECT * FROM information_schema.PROCESSLIST;"
df -h
free -m
```

---

**最后更新**: 2024年6月  
**版本**: 1.0.0
