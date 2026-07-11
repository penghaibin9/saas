# 03 · miniapp 目录说明（miniapp/）

> `miniapp/` 是小程序端（学生端 + 教师端），uni-app + Vue3，纯 mock。**小程序后续开发就动这里**。本轮文档任务不改动它。
> 现状：H5 能跑、能构建；微信小程序能构建成功。

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
    ├── services/         数据服务层（对接 mock）
    ├── mock/             mock 假数据 ——⛔ 本轮不改
    ├── config/           配置（含 env.js：useMock 开关；brand 品牌配置）
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

开发前**必须先看**：`docs/ui/fable5-miniapp-final/`（小程序设计稿）、`docs/source-design/08A-学生小程序中心.md`、`docs/source-design/08B《教师移动工作台中心》.md`。

> 小程序**不能照抄 PC，不能做成 PC 缩小版**（项目入口文档明确要求）。

---

## 3. 关键开关：useMock（现在别动）

`src/config/env.js`：

```js
export const ENV = { useMock: true }   // 当前恒为 true = 用假数据
```

- 现在恒为 `true`，全端 mock，不接后端。
- **本阶段不要改**。切真实后端是后续阶段、由开发统一处理。

---

## 4. 命令与产物（回顾）

| 命令 | 作用 | 产物 |
|---|---|---|
| `npm install` | 装依赖 | `node_modules/` |
| `npm run dev:h5` | H5 开发调试 | http://localhost:5188/ |
| `npm run build:h5` | H5 上线构建 | `dist/build/h5/` |
| `npm run dev:mp-weixin` | 微信调试 | `dist/dev/mp-weixin/` |
| `npm run build:mp-weixin` | 微信上线构建 | `dist/build/mp-weixin/` |

部署方式见 `docs/deploy/04-miniapp小程序部署.md`。

---

## 5. 不要动的

- `package.json` / `package-lock.json`：⛔ 本轮不改。
- `dist/` `node_modules/`：❌ 机器生成。
- 本轮文档任务：**整个 `miniapp/` 都不改**，只在文档里引用说明。
