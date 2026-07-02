# 实习管理平台 · 微信小程序

面向「学生」与「指导教师」的实习 / 毕业设计管理小程序，与本仓库 `internship-backend` 后端共用同一套 REST API。

## 一、目录结构

```
miniprogram/
├── app.js / app.json / app.wxss      # 全局逻辑、页面注册、全局样式
├── project.config.json               # 开发者工具项目配置
├── sitemap.json                      # 站点索引配置
├── custom-tab-bar/                   # 自定义底部 TabBar（按角色切换）
├── utils/
│   ├── request.js                    # 网络请求封装（含 401/403 拦截、文件上传）
│   └── util.js                       # 日期格式化、距离计算等
└── pages/                            # 业务页面
    ├── login/        登录
    ├── home/         首页工作台（学生进度 / 教师待办 + 通知入口）
    ├── checkin/      实习打卡（GPS / 模拟）
    ├── logs/ newlog/ 实习周报 / 月报（支持附件）
    ├── leave/        请假申请
    ├── achievements/ 毕业设计成果（支持附件）
    ├── reports/      实习报告（支持附件）
    ├── positions/    实习岗位浏览 + 申请
    ├── applications/ 我的申请（含撤回）
    ├── topics/ tasks/ 毕设选题 / 任务节点
    ├── insurances/   实习保险
    ├── grade/        毕设成绩
    ├── announcements/ notifications/ 公告 / 通知（支持单条已读）
    ├── profile/ mine/ 个人资料 / 我的
    ├── assignment/   我的实习分配
    ├── students/     我的实习生（教师）
    ├── review/       待批阅（教师：申请/周报/请假/成果/报告）
    ├── guidance/     指导记录（教师）
    ├── trecords/     工作记录（教师月报 / 走访，支持附件）
    └── quality/      质量检查审阅（教师）
```

## 二、导入与运行

1. 安装并打开 **微信开发者工具**（稳定版即可）。
2. 选择「导入项目」，目录指向本仓库的 `miniprogram/` 文件夹。
3. AppID：开发调试可选择「测试号」；正式发布需填入自己的小程序 AppID（同时更新 `project.config.json` 的 `appid`）。
4. 先启动后端：在 `internship-backend/` 执行 `npm install && npm start`，默认监听 `http://localhost:3000`。
5. 在开发者工具中点击「编译」即可预览。

## 三、后端地址配置

请求基址定义在 `config.js`，开发版、体验版和正式版可以分别配置：

```js
apiBase: {
  develop: 'http://localhost:3000/api',
  trial: 'https://your-domain.com/api',
  release: 'https://your-domain.com/api'
}
```

- **本地开发**：保持 `http://localhost:3000/api`，并在开发者工具「详情 → 本地设置」中勾选
  **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**，否则真机/预览会拦截 http 请求。
- **真机 / 发布**：必须在 `config.js` 改为 **HTTPS 域名**（如 `https://your-domain.com/api`），并在
  微信公众平台「开发 → 开发管理 → 开发设置 → 服务器域名」中，把该域名加入
  **request 合法域名** 与 **uploadFile / downloadFile 合法域名**（附件上传/下载用到）。

## 四、登录与角色

- 使用与 PC / H5 相同的账号密码登录（`POST /api/users/login`）。
- 首次登录若后端返回 `mustChangePassword`，会强制跳转到「个人资料」修改初始密码。
- 登录后根据角色（学生 role=4 / 教师 role=3）自动切换底部 TabBar 与可见功能。
- 登录态（token、用户信息）保存在本地 `Storage`；token 失效（401）会自动跳回登录页。

## 五、注意事项

- **附件上传**：通过 `wx.chooseMessageFile` 选择文件，使用 `wx.uploadFile`（仅 POST）上传，
  因此周报 / 成果 / 报告的附件仅在「新建」时上传；编辑时不替换附件。
- **附件下载**：报告附件通过鉴权接口 `GET /api/reports/:id/download` 下载，
  需在合法域名中配置 downloadFile 域名。
- **定位打卡**：需在 `app.json` 中声明 `requiredPrivateInfos: ["getLocation"]` 及
  `permission.scope.userLocation`（已配置），真机首次使用会请求授权。
```
