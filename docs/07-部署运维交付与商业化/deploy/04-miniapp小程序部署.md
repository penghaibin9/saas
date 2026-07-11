# 04 · miniapp 小程序部署

> 对象：`miniapp/`（学生端 + 教师端，uni-app + Vue3，纯 mock）。
> 一份源码，能编译成两种东西：
> - **H5 网页** → 部署到 Nginx，手机/电脑浏览器打开
> - **微信小程序** → 用微信开发者工具上传体验版/正式版
> 现状：H5 能跑、能构建；微信小程序能构建成功。**都能真实部署（演示级，用 mock 假数据）。**

---

## 1. 先装依赖（首次或换机器）

```bash
cd miniapp
npm install
```

- 在哪个目录：项目里的 **`miniapp/`**（不是根目录，不是 frontend）。
- 慢的话设镜像：`npm config set registry https://registry.npmmirror.com`

---

## 2. 本地开发预览（H5，边改边看）

```bash
cd miniapp
npm run dev:h5
```

- 启动后终端会显示地址，默认 **http://localhost:5188/**（被占用会自动顺延端口）。
- 打开后：选「我是学生」→ 学生端首页；选「我是老师」→ 选身份 → 教师工作台。
- 这是**开发调试**用的，不是上线用的。上线要用下面的 `build`。

---

## 3. 构建 H5（要部署到网页时用）

```bash
cd miniapp
npm run build:h5
```

- 实际执行 `uni build`（见 `miniapp/package.json`）。
- 成功后产物在：**`miniapp/dist/build/h5/`**，里面是：
  ```
  miniapp/dist/build/h5/
  ├── index.html
  └── assets/
  ```
- 这就是可上线的 H5 静态网站。

### 部署 H5 到 Nginx

和 PC 前端一模一样的套路：把 `miniapp/dist/build/h5/` **里面的内容**放到网站目录（如 `/var/www/miniapp-h5/`），再配 Nginx。

```bash
sudo rm -rf /var/www/miniapp-h5/*
sudo cp -r miniapp/dist/build/h5/* /var/www/miniapp-h5/
```

Nginx 站点（完整示例见 `deploy/nginx/miniapp-h5.conf.example`）最小版：

```nginx
server {
    listen       80;
    server_name  你的小程序H5域名或IP;    # 例如 m.example.com

    root   /var/www/miniapp-h5;
    index  index.html;

    location / {
        try_files $uri $uri/ /index.html;   # 同样要兜底，避免刷新 404
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

> H5 也是单页应用，**同样需要 `try_files ... /index.html`**，否则刷新/直接访问子页面会 404。

---

## 4. 构建微信小程序（要上传到微信时用）

```bash
cd miniapp
npm run build:mp-weixin
```

- 实际执行 `uni build -p mp-weixin`。
- 成功后产物在：**`miniapp/dist/build/mp-weixin/`**。
- 注意：这个产物**不是网页，不能放 Nginx**，要用「微信开发者工具」打开上传。

### 用微信开发者工具打开并上传

1. 在你自己的 Windows/Mac 上安装「微信开发者工具」（微信官方下载）。
2. 打开微信开发者工具 → 新建/导入项目 → 目录选择 **`miniapp/dist/build/mp-weixin/`**。
3. 填入小程序的 AppID（学校/公司的微信小程序后台申请；没有可先用「测试号」预览）。
4. 在工具里就能看到小程序运行效果。
5. 点右上角「上传」，填版本号和备注 → 上传成功后到微信「小程序管理后台」把这个版本设为「体验版」或提交审核发布。

> 开发调试版（不用于上线）：`npm run dev:mp-weixin`，产物在 `miniapp/dist/dev/mp-weixin/`，同样用微信开发者工具打开。

---

## 5. 命令速查表

| 目的 | 命令 | 产物位置 |
|---|---|---|
| 装依赖 | `npm install` | `miniapp/node_modules/` |
| H5 本地调试 | `npm run dev:h5` | 浏览器 http://localhost:5188/ |
| H5 上线构建 | `npm run build:h5` | `miniapp/dist/build/h5/` |
| 微信小程序调试 | `npm run dev:mp-weixin` | `miniapp/dist/dev/mp-weixin/` |
| 微信小程序上线构建 | `npm run build:mp-weixin` | `miniapp/dist/build/mp-weixin/` |

> 全部命令都在 `miniapp/` 目录里执行。

---

## 6. 重要说明：现在是 mock（假数据）

- 小程序当前 `miniapp/src/config/env.js` 里 `useMock: true`，即**恒用假数据**，不连后端、不连数据库。
- 能演示完整流程（登录、看首页、填表单、提交、看「我的申请」），但数据不会真正存到服务器。
- 等后端接入后，会把 `useMock` 切成 `false` 并配置真实接口地址（那是后续阶段的事，见 `05-后端预留部署说明.md` 与 `08-环境变量说明.md`）。**现在不要改这个开关。**

---

## 7. 常见问题

| 现象 | 可能原因 | 怎么办 |
|---|---|---|
| `npm run build:h5` 报错 | 依赖没装全 / Node 版本太低 | 先 `npm install`；确认 Node 18/20；看报错最后几行 |
| H5 刷新 404 | Nginx 少了 `try_files` 兜底 | 按第 3 节加上 |
| 微信工具里报「AppID 无效」 | 没填 AppID | 用测试号，或填学校申请的正式 AppID |
| 微信里页面样式乱 | 小程序不支持某些 H5 写法 | 属于开发阶段问题，记录反馈，不在部署阶段改代码 |
| 微信小程序打不开某图片 | 域名未在小程序后台配「合法域名」 | 现阶段 mock 不涉及；后端接入后需在小程序后台配置服务器域名 |
