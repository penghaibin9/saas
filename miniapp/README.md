# 高校学生全生命周期管理平台 · 小程序端

uni-app + Vue3 小程序端（学生端 + 教师端），纯 mock 数据，独立运行，不依赖 PC 前端。

## 运行方法

```bash
cd miniapp
npm install
npm run dev:h5
```

启动后打开终端里显示的地址（默认 http://localhost:5188/ ，被占用时自动顺延）。

- 首页选「我是学生」→ 进入学生端。
- 首页选「我是老师」→ 进入身份选择页 → 选一个身份 → 进入教师工作台。

## 其他命令

```bash
npm run dev:mp-weixin   # 编译到微信小程序，用微信开发者工具打开 dist/dev/mp-weixin
npm run build:h5        # 打包 H5
```

## 说明

- 全部为 mock 数据，不接后端、不连数据库。
- 学校名称 / Logo / 平台名来自 src/config/brand.config.js（tenantBrandConfig），未硬编码。
- 只改本目录（miniapp/），未改动 PC 管理端 frontend/。
