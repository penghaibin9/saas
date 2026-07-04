# 归档说明（Node/Express 残留）

本目录下的文件（`package.json`、`config/`、`middlewares/`、`utils/`）是早期 **Node.js + Express5 + MySQL** 方案的残留脚手架，在 `BACKEND-P0-FASTAPI-BASELINE-CLEANUP` 任务中从 `backend/` 根目录归档到这里。

## 现状

- 没有 `app.js` 等入口文件，没有 `routes/`、没有 `models/`，无法启动、不可运行。
- `package.json` 里声明的 `migrate`、`test` 脚本指向的 `scripts/migrate.js`、`tests/*.test.js` 均不存在。
- 仅保留了部分中间件/工具/数据库连接代码（多为从旧毕业设计系统移植的半成品）。

## 结论

- 当前 `backend/` 的主技术栈已统一为 **FastAPI + Pydantic + Uvicorn**（见 `backend/app/`）。
- 本目录内容**不作为主后端技术栈**，仅作历史留存，防止误删有用参考代码。
- 不建议继续在此基础上开发；如需要参考旧系统的字段/逻辑设计，可以查阅，但不要接入当前 FastAPI 后端。

## 后续

如确认无参考价值，后续可以整体删除本目录；删除前请与项目负责人确认。
