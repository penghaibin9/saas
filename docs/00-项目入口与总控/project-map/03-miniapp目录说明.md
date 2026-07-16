# 03 · miniapp 目录说明（miniapp/）

> `miniapp/` 是当前学生端 + 教师端混合的 uni-app + Vue3 工程。**现有功能继续按当前目录施工，停止扩大跨角色耦合。**
> 现状：H5/微信构建能力和真实接口封装均已存在；学生/教师小程序的目标拆分方式见 [五端产品与 SaaS 总体架构规划](../../02-总体架构与公共底座/00-五端产品与SaaS总体架构规划.md)。

---

## 1. 目录结构

```
miniapp/
├── package.json          依赖与脚本（dev:h5 / build:h5 / dev:mp-weixin / build:mp-weixin）——⛔ 本轮不改
├── vite.config.js        构建配置
├── index.html            H5 入口
├── check-compile.mjs     编译自检脚本
├── build-h5.log / build-mp.log / dev.log   构建/运行日志（排查用）
├── README.md             小程序端说明（怎么跑）
├── dist/                 构建产物 ——❌ 别手改
│   └── build/
│       ├── h5/           H5 产物（部署到 Nginx）
│       └── mp-weixin/    微信小程序产物（微信开发者工具打开）
├── node_modules/         依赖 ——❌ 别手改
└── src/                  源码 ✅（小程序开发动这里）
    ├── main.js           入口
    ├── App.vue           根组件
    ├── manifest.json     uni-app 应用配置（AppID、各端配置）
    ├── pages.json        页面路由与 tabBar 配置
    ├── pages/            所有页面（学生端 + 教师端）
    ├── components/       组件
    ├── stores/           状态管理（Pinia）
    ├── services/         数据服务层（真实优先 + 兼容数据源）
    ├── mock/             兼容/演示数据，不能冒充真实业务成功
    ├── config/           环境与品牌配置
    ├── static/           静态资源（图片等）
    ├── styles/ uni.scss  样式
    └── utils/            工具函数
```

---

## 2. 小程序后续开发一般动哪些

- `src/pages/`：加/改页面（学生端、教师端）。
- `src/pages.json`：注册页面、配置 tabBar。
- `src/components/`：抽公共组件。
- `src/services/` + `src/mock/`：数据逻辑与 mock。
- `src/config/brand.config.js`：品牌（学校名/Logo/平台名，别硬编码）。
- `src/styles/`、`uni.scss`：样式。

开发前**必须先看**：`docs/04-UI与全端交互/ui/fable5-miniapp-final/`（小程序设计稿）、`docs/08-历史记录与归档/source-design/08A-学生小程序中心.md`、`docs/08-历史记录与归档/source-design/08B《教师移动工作台中心》.md`。

> 小程序**不能照抄 PC，不能做成 PC 缩小版**（项目入口文档明确要求）。

---

## 3. 数据源与真实接口边界

当前工程已有真实请求层和学生/教师 API 封装。业务错误必须透出，写操作不得 mock 成功；是否真实闭环仍须逐模块核对页面、接口、MySQL、权限和测试，不能只凭页面存在判断完成。

在学生/教师小程序正式拆分前：

- 新页面必须明确属于学生还是教师；
- 不新增依赖运行时角色切换才能保证安全的混合页面；
- 学生写操作走学生本人接口，教师写操作走教师范围接口；
- 两端拆分是独立施工，不在业务功能 commit 中顺手搬目录。

---

## 4. 命令与产物（回顾）

| 命令 | 作用 | 产物 |
|---|---|---|
| `npm install` | 装依赖 | `node_modules/` |
| `npm run dev:h5` | H5 开发调试 | http://localhost:5188/ |
| `npm run build:h5` | H5 上线构建 | `dist/build/h5/` |
| `npm run dev:mp-weixin` | 微信调试 | `dist/dev/mp-weixin/` |
| `npm run build:mp-weixin` | 微信上线构建 | `dist/build/mp-weixin/` |

部署方式见 `docs/07-部署运维交付与商业化/deploy/04-miniapp小程序部署.md`。

---

## 5. 不要动的

- `package.json` / `package-lock.json`：⛔ 本轮不改。
- `dist/` `node_modules/`：❌ 机器生成。
- 本轮文档任务：**整个 `miniapp/` 都不改**，只在文档里引用说明。
