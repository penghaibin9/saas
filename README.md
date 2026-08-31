# 职校学生全生命周期系统

本仓库是面向职业院校的多租户学生全生命周期系统。根目录只保留工程入口；业务设计、施工记录、测试和交付资料统一放在 `docs/`。

## 工程目录

| 目录 | 用途 |
|---|---|
| `backend/` | FastAPI 后端、MySQL 迁移、权限与审计 |
| `frontend/` | 学校管理 PC 端 |
| `student-portal/` | 学生 PC 门户 |
| `miniapp/` | 学生与教师移动端 |
| `enterprise-portal/` | 企业协同门户 |
| `e2e/` | 浏览器验收 |
| `deploy/` | 部署与恢复配置 |
| `scripts/` | 开发、检查和发布脚本 |
| `docs/` | 当前文档入口与历史归档 |

## 从这里开始

- 开发和安全规则：[`CLAUDE.md`](./CLAUDE.md)
- 文档总入口：[`docs/README.md`](./docs/README.md)
- 部署资料：[`docs/07-部署运维交付与商业化/deploy/README.md`](./docs/07-部署运维交付与商业化/deploy/README.md)
- 测试资料：[`docs/06-开发施工与质量验收/testing/README.md`](./docs/06-开发施工与质量验收/testing/README.md)

目录干净不代表版本已经通过上线门禁。正式发布前仍必须完成迁移、测试、构建、浏览器链路、安全、备份恢复和容量验收。
