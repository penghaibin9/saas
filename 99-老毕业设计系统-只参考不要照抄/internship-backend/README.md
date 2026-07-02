# 毕业设计及岗位实习管理平台 - 后端 API

> Node.js + Express + MySQL 实现的实习管理系统后端服务

## 📋 项目结构

```
internship-backend/
├── app.js                  # 应用入口文件
├── package.json            # 项目依赖配置
├── .env.example            # 环境变量示例
│
├── config/                 # 配置文件夹
│   ├── db.js              # 数据库配置和连接
│   └── index.js           # 配置导出
│
├── controllers/           # 业务逻辑层
│   ├── userController.js
│   ├── adminUserController.js
│   ├── collegeController.js
│   ├── majorController.js
│   ├── classController.js
│   ├── enterpriseController.js
│   ├── positionController.js
│   ├── applicationController.js
│   ├── reportController.js
│   ├── statsController.js
│   ├── notificationController.js
│   ├── exportController.js
│   └── index.js
│
├── models/               # 数据访问层
│   ├── userModel.js
│   ├── collegeModel.js
│   ├── majorModel.js
│   ├── classModel.js
│   ├── enterpriseModel.js
│   ├── positionModel.js
│   ├── applicationModel.js
│   ├── reportModel.js
│   ├── statsModel.js
│   ├── notificationModel.js
│   └── index.js
│
├── routes/              # 路由配置
│   ├── userRoutes.js
│   ├── adminUserRoutes.js
│   ├── collegeRoutes.js
│   ├── majorRoutes.js
│   ├── classRoutes.js
│   ├── enterpriseRoutes.js
│   ├── positionRoutes.js
│   ├── applicationRoutes.js
│   ├── reportRoutes.js
│   ├── statsRoutes.js
│   ├── notificationRoutes.js
│   ├── exportRoutes.js
│   └── index.js
│
├── middlewares/         # 中间件
│   ├── auth.js         # 身份验证和权限控制
│   └── index.js
│
├── scripts/             # 辅助脚本
│   ├── init-db.js      # 数据库初始化脚本
│   ├── init-db.sql     # SQL 建表脚本
│   ├── seed-admin.js   # 种子数据脚本
│   └── test-api.js     # API 测试脚本
│
├── utils/              # 工具函数
│   ├── response.js     # 响应格式化
│   └── index.js
│
└── uploads/            # 文件上传目录
```

## 🚀 快速开始

### 1. 环境准备

**系统要求：**
- Node.js >= 14.x
- MySQL >= 5.7

**依赖安装：**
```bash
npm install
```

### 2. 数据库初始化

**方式一：自动初始化（推荐）**
```bash
# 复制环境配置
cp .env.example .env

# 修改 .env 中的数据库配置，然后执行
npm run init:db
```

**方式二：手动初始化**
```bash
# 使用 MySQL 客户端执行 SQL 脚本
mysql -u root -p < scripts/init-db.sql
```

### 3. 启动服务

```bash
# 开发模式
npm run dev

# 生产模式
npm start
```

服务默认运行在 `http://localhost:3000`

## 📚 API 文档

### 角色说明
- `1`: 院校管理员（超级管理员）
- `2`: 分院管理员（部门管理员）
- `3`: 指导教师
- `4`: 学生

### 用户模块 `/api/users`

#### 注册
```
POST /api/users/register
Content-Type: application/json

{
  "username": "student001",
  "password": "123456",
  "real_name": "张三",
  "role": 4,
  "phone": "13800000001",
  "email": "student@example.com",
  "college_id": 1,
  "major_id": 1,
  "class_id": 1,
  "eeid": "20240001"
}

Response:
{
  "success": true,
  "message": "注册成功",
  "data": { /* user object */ }
}
```

#### 登录
```
POST /api/users/login
Content-Type: application/json

{
  "username": "student001",
  "password": "123456"
}

Response:
{
  "success": true,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGci...",
    "user": { /* user object */ }
  }
}
```

#### 获取个人信息
```
GET /api/users/profile
Authorization: Bearer <token>
```

#### 修改个人信息
```
PUT /api/users/profile
Authorization: Bearer <token>
Content-Type: application/json

{
  "real_name": "张三",
  "phone": "13800000001",
  "email": "new@example.com"
}
```

#### 修改密码
```
PUT /api/users/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "oldPassword": "123456",
  "newPassword": "654321"
}
```

### 学院管理 `/api/colleges`

#### 获取学院列表
```
GET /api/colleges?status=1&keyword=工程
Authorization: Bearer <token>
```

#### 创建学院（仅院校管理员）
```
POST /api/colleges
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "信息工程学院",
  "code": "INFO",
  "description": "学院描述"
}
```

### 专业管理 `/api/majors`

#### 获取专业列表
```
GET /api/majors?college_id=1&status=1
Authorization: Bearer <token>
```

#### 创建专业（管理员）
```
POST /api/majors
Authorization: Bearer <token>
Content-Type: application/json

{
  "college_id": 1,
  "name": "计算机科学与技术",
  "code": "CS",
  "description": "专业描述"
}
```

### 班级管理 `/api/classes`

#### 获取班级列表
```
GET /api/classes?major_id=1&grade=2024
Authorization: Bearer <token>
```

#### 创建班级（管理员）
```
POST /api/classes
Authorization: Bearer <token>
Content-Type: application/json

{
  "major_id": 1,
  "name": "计科2024-1班",
  "grade": 2024
}
```

### 企业管理 `/api/enterprises`

#### 获取企业列表
```
GET /api/enterprises?status=1&page=1&page_size=20
Authorization: Bearer <token>
```

#### 创建企业（管理员）
```
POST /api/enterprises
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "北京科技有限公司",
  "short_name": "北京科技",
  "industry": "互联网",
  "address": "北京市朝阳区",
  "contact_name": "王经理",
  "contact_phone": "13800000001"
}
```

### 岗位管理 `/api/positions`

#### 获取岗位列表
```
GET /api/positions?enterprise_id=1&status=1&page=1&page_size=20
Authorization: Bearer <token>
```

#### 创建岗位（管理员）
```
POST /api/positions
Authorization: Bearer <token>
Content-Type: application/json

{
  "enterprise_id": 1,
  "title": "Java 开发工程师",
  "description": "岗位描述",
  "requirement": "岗位要求",
  "salary": "15K-25K",
  "headcount": 5,
  "location": "北京",
  "start_date": "2024-07-01",
  "end_date": "2024-12-31",
  "college_id": 1
}
```

#### 上架/下架岗位
```
PUT /api/positions/:id/toggle
Authorization: Bearer <token>
```

### 申请管理 `/api/applications`

#### 获取申请列表
```
GET /api/applications?status=0&page=1&page_size=20
Authorization: Bearer <token>
```

#### 学生提交申请
```
POST /api/applications
Authorization: Bearer <token>
Content-Type: application/json

{
  "position_id": 1,
  "student_remark": "我对这个岗位感兴趣"
}
```

#### 撤回申请（仅学生，待审核状态）
```
DELETE /api/applications/:id
Authorization: Bearer <token>
```

#### 教师审核申请
```
PUT /api/applications/:id/teacher-review
Authorization: Bearer <token>
Content-Type: application/json

{
  "agree": true,  // true 同意，false 拒绝
  "opinion": "意见内容"
}
```

#### 管理员审核申请
```
PUT /api/applications/:id/admin-review
Authorization: Bearer <token>
Content-Type: application/json

{
  "agree": true,
  "opinion": "审核意见"
}
```

#### 分配指导教师
```
PUT /api/applications/:id/assign-teacher
Authorization: Bearer <token>
Content-Type: application/json

{
  "teacher_id": 3
}
```

### 实习报告 `/api/reports`

#### 获取报告列表
```
GET /api/reports?status=0&page=1&page_size=20
Authorization: Bearer <token>
```

#### 学生创建报告
```
POST /api/reports
Authorization: Bearer <token>
Content-Type: multipart/form-data

- application_id: 申请ID
- title: 报告标题
- content: 报告内容
- file: 报告文件（可选）
```

#### 提交报告
```
PUT /api/reports/:id/submit
Authorization: Bearer <token>
```

#### 教师评阅报告
```
PUT /api/reports/:id/review
Authorization: Bearer <token>
Content-Type: application/json

{
  "teacher_score": 85,      // 0-100
  "teacher_comment": "评语"
}
```

### 数据导出 `/api/export`

#### 导出申请列表
```
GET /api/export/applications?status=0&page_size=5000
Authorization: Bearer <token>
```

#### 导出用户列表（管理员）
```
GET /api/export/users
Authorization: Bearer <token>
```

#### 导出报告列表
```
GET /api/export/reports?status=1
Authorization: Bearer <token>
```

#### 导入学生（管理员）
```
POST /api/export/students
Authorization: Bearer <token>
Content-Type: multipart/form-data

- file: Excel 文件
```

#### 下载导入模板
```
GET /api/export/template
Authorization: Bearer <token>
```

### 统计概览 `/api/stats`

#### 获取统计数据
```
GET /api/stats/overview
Authorization: Bearer <token>

返回数据根据角色不同：
- 院校管理员：全校统计数据
- 分院管理员：本学院统计数据
- 教师：个人指导申请统计
- 学生：个人申请统计
```

### 通知管理 `/api/notifications`

#### 获取通知列表
```
GET /api/notifications?page=1&page_size=20
Authorization: Bearer <token>
```

#### 获取未读数
```
GET /api/notifications/unread-count
Authorization: Bearer <token>
```

#### 标记单条已读
```
PUT /api/notifications/:id/read
Authorization: Bearer <token>
```

#### 标记全部已读
```
PUT /api/notifications/read-all
Authorization: Bearer <token>
```

## 🧪 测试

### 运行集成测试
```bash
# 确保服务已启动，数据库已初始化
npm test

# 或直接运行
node test-integration.js
```

### 测试流程
1. 服务健康检查
2. 用户注册和登录
3. 学院、专业、班级管理
4. 企业和岗位管理
5. 申请流程（提交、分配、审核）
6. 个人信息管理
7. 数据导出
8. 统计概览

## 🔒 权限控制

| 模块 | 操作 | 权限 |
|-----|------|------|
| 学院 | 查看 | 所有登录用户 |
| 学院 | 增删改 | 院校管理员(1) |
| 专业/班级 | 查看 | 所有登录用户 |
| 专业/班级 | 增删改 | 管理员(1,2) |
| 企业/岗位 | 查看 | 所有登录用户 |
| 企业/岗位 | 增删改 | 管理员(1,2) |
| 用户管理 | 查看 | 管理员(1,2) |
| 用户管理 | 增删改 | 管理员(1,2) |
| 申请 | 查看 | 申请人、指导教师、管理员 |
| 申请 | 提交 | 学生(4) |
| 申请 | 撤回 | 申请学生 |
| 申请 | 教师审核 | 指导教师(3) |
| 申请 | 管理员审核 | 管理员(1,2) |
| 申请 | 分配教师 | 管理员(1,2) |
| 报告 | 创建/提交 | 学生(4) |
| 报告 | 评阅 | 指导教师(3) |
| 统计 | 查看 | 根据角色自动过滤数据 |

## 📊 数据库说明

### 主要表结构

**t_user** - 用户表
- role: 1=院校管理员, 2=分院管理员, 3=教师, 4=学生
- status: 1=启用, 0=禁用
- college_id: 所属学院

**t_application** - 申请表
- status: 0=待审核, 1=教师同意, 2=教师拒绝, 3=院校通过, 4=院校拒绝, 5=已录用, 6=未录用

**t_report** - 报告表
- status: 0=草稿, 1=已提交, 2=已评阅

**t_position** - 岗位表
- college_id: NULL 表示全校可见

## 🐛 常见问题

### 1. 连接数据库失败
- 确认 MySQL 服务已启动
- 检查 .env 中的数据库配置
- 确保数据库用户有权限

### 2. 端口被占用
```bash
# 修改 .env 中的 PORT 或杀死占用进程
lsof -i :3000  # 查看
kill -9 <PID>  # 杀死进程
```

### 3. 导入学生文件失败
- 确保 Excel 文件列名正确（用户名、姓名、学号、手机号、邮箱）
- 确保有上传文件夹 uploads/

## 📝 日志和错误处理

- 所有错误响应格式统一
- 支持自定义错误代码
- 完整的堆栈跟踪用于开发调试

## 🔐 安全建议

1. **生产环境必须：**
   - 修改 JWT_SECRET
   - 使用强密码
   - 启用 HTTPS
   - 配置防火墙

2. **数据保护：**
   - 定期备份数据库
   - 使用 bcrypt 加密密码
   - 实施访问控制

## 📄 许可证

MIT License

## 👥 技术支持

如有问题，请检查以下内容：
1. 查看服务器日志
2. 运行集成测试
3. 检查数据库连接

---

**最后更新**: 2024年6月  
**版本**: 1.0.0
