# 🚀 快速启动指南

## 5分钟快速上手

### 第1步：环境配置
```bash
# 1. 复制环境配置文件
cp .env.example .env

# 2. 编辑 .env，配置你的数据库连接信息
# 默认配置通常可以直接使用（如果 MySQL 运行在本地）
```

### 第2步：初始化数据库
```bash
# 自动创建数据库、建表、插入默认数据
npm run init:db

# 输出信息：
# ✅ 连接到 MySQL 成功
# ✓ CREATE DATABASE...
# ✓ CREATE TABLE...
# ... [更多SQL操作]
# ✅ 数据库初始化完成！
#    默认账户：admin / 123456
#    请登录后修改密码！
```

### 第3步：启动服务
```bash
# 开发模式（推荐）
npm run dev

# 或生产模式
npm start

# 输出信息：
# ✅ 服务已启动，监听端口: 3000
# ✅ 数据库连接测试通过！
```

### 第4步：验证服务
```bash
# 打开浏览器或使用 curl 测试
curl http://localhost:3000/health

# 或使用集成测试
npm test
```

---

## 🔑 默认账户

初始化完成后自动创建以下账户：

| 账户名 | 密码 | 角色 | 权限 |
|-------|------|------|------|
| admin | 123456 | 院校管理员(1) | 全部功能 |

**⚠️ 重要：首次登录后必须修改密码！**

---

## 🧪 快速测试

### 测试1：用户注册和登录
```bash
# 执行集成测试（包括所有功能）
npm test

# 或使用 curl 手动测试

# 注册新用户
curl -X POST http://localhost:3000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test001",
    "password": "123456",
    "real_name": "测试用户",
    "role": 4
  }'

# 登录
curl -X POST http://localhost:3000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test001",
    "password": "123456"
  }'
```

### 测试2：查询学院
```bash
# 使用 admin 的 token（从登录响应获取）
curl -H "Authorization: Bearer <token>" \
  http://localhost:3000/api/colleges
```

---

## 📝 常见问题解决

### ❌ 错误：ECONNREFUSED - 数据库连接失败

**原因：** MySQL 服务未启动

**解决方案：**
```bash
# Windows - 启动 MySQL 服务
net start MySQL80

# macOS - 使用 Homebrew
brew services start mysql

# Linux - 使用 systemctl
sudo systemctl start mysql
```

### ❌ 错误：Port 3000 already in use

**原因：** 端口已被占用

**解决方案：**
```bash
# 方案1：使用其他端口
PORT=3001 npm run dev

# 方案2：杀死占用端口的进程
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :3000
kill -9 <PID>
```

### ❌ 错误：Access denied for user 'root'@'localhost'

**原因：** MySQL 用户名或密码错误

**解决方案：**
1. 确认 MySQL 管理员密码
2. 更新 .env 中的 `DB_PASSWORD`
3. 重新运行 `npm run init:db`

### ❌ 错误：Unknown database 'internship_management'

**原因：** 数据库初始化失败或未执行

**解决方案：**
```bash
# 重新初始化
npm run init:db

# 或手动创建
mysql -u root -p < scripts/init-db.sql
```

### ❌ 登录后仍无法访问受保护的接口

**原因：** 令牌格式错误或过期

**解决方案：**
- 确保使用 `Authorization: Bearer <token>` 格式
- 登录获取新的 token
- 检查 token 是否包含 Bearer 前缀

---

## 📊 功能验证清单

运行以下命令验证主要功能：

```bash
# ✅ 1. 启动服务
npm run dev

# ✅ 2. 初始化数据库
npm run init:db

# ✅ 3. 运行完整测试
npm test

# ✅ 4. 检查日志输出是否没有错误
```

---

## 🔄 工作流示例

### 完整的实习申请流程

```bash
# 1. 学生注册
curl -X POST http://localhost:3000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"123456","real_name":"张三","role":4}'

# 2. 学生登录获取 token
TOKEN=$(curl -X POST http://localhost:3000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"123456"}' \
  | jq -r '.data.token')

# 3. 查看可用岗位
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/positions

# 4. 提交申请
curl -X POST http://localhost:3000/api/applications \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"position_id":1,"student_remark":"我很感兴趣"}'

# 5. 查看申请状态
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/applications
```

---

## 📚 API 基础信息

- **基础 URL**: `http://localhost:3000/api`
- **认证方式**: JWT Bearer Token
- **响应格式**: JSON
- **请求超时**: 30 秒

### 标准响应格式

**成功响应 (2xx):**
```json
{
  "success": true,
  "message": "操作成功",
  "data": { /* 数据内容 */ }
}
```

**错误响应 (4xx/5xx):**
```json
{
  "success": false,
  "message": "错误描述",
  "code": 400,
  "data": { /* 可选的额外信息 */ }
}
```

---

## 🎓 角色权限参考

| 功能模块 | 学生(4) | 教师(3) | 分院管理(2) | 院校管理(1) |
|---------|--------|--------|-----------|-----------|
| 查看岗位 | ✅ | ✅ | ✅ | ✅ |
| 提交申请 | ✅ | ❌ | ❌ | ❌ |
| 审核申请 | ❌ | ✅* | ❌ | ✅ |
| 管理岗位 | ❌ | ❌ | ✅ | ✅ |
| 管理学院 | ❌ | ❌ | ❌ | ✅ |
| 查看统计 | ✅* | ✅* | ✅ | ✅ |

*仅能查看自己相关的数据

---

## 🔧 高级配置

### 修改监听端口
```bash
PORT=8080 npm run dev
```

### 修改 JWT 过期时间
编辑 `.env`:
```
JWT_EXPIRES_IN=14d  # 改为14天
```

### 启用 HTTPS
编辑 `app.js` 并配置 SSL 证书（生产环境推荐）

---

## 📞 需要帮助？

1. 查看完整文档：`README.md`
2. 检查服务日志（控制台输出）
3. 运行测试：`npm test`
4. 检查数据库连接：`node config/db.js`

---

**祝你使用愉快！** 🎉
