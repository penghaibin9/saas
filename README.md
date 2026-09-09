# 职校学生全生命周期系统

面向职业院校销售、部署和验收的多租户学生全生命周期 SaaS。本仓库不是静态原型：正式能力以当前代码、MySQL 迁移、权限校验和自动化测试为准。

## 工程入口

| 目录 | 职责 | 主要技术 |
|---|---|---|
| `backend/` | 统一后端、权限、审计、迁移 | FastAPI / SQLAlchemy / Alembic / MySQL |
| `frontend/` | 学校管理端 PC | Vue 3 / Vite |
| `student-portal/` | 学生 PC 门户 | Vue 3 / Vite |
| `miniapp/` | 学生与教师移动端 | uni-app / Vue 3 |
| `enterprise-portal/` | 岗位实习企业门户 | Vue 3 / Vite |
| `e2e/` | 跨端真实浏览器验收 | Playwright |
| `shared/` | 跨端契约与生成索引 | JSON / scripts |
| `deploy/` | 部署、回滚与运维配置 | Docker / Nginx / systemd |

## 当前状态

- 项目状态：[`docs/00-项目入口与总控/project-status.json`](docs/00-项目入口与总控/project-status.json)
- 文档总导航：[`docs/README.md`](docs/README.md)
- 开发与安全约束：[`CLAUDE.md`](CLAUDE.md)
- 部署与上线入口：[`docs/07-部署运维交付与商业化/deploy/README.md`](docs/07-部署运维交付与商业化/deploy/README.md)

`implemented` 只表示代码能力存在，不等于已通过统一交付门禁。是否可交付以 `project-status.json` 中的 `releaseGates` 为准。

## 常用验证

```powershell
# 后端（必须使用独立 MySQL 测试库）
cd backend
python -m pytest

# 学校管理端
cd ..\frontend
npm ci
npm run lint
npm test
npm run build

# 学生 PC、小程序、企业门户
cd ..\student-portal; npm ci; npm test; npm run build
cd ..\miniapp; npm ci; npm test; npm run build:h5; npm run build:mp-weixin
cd ..\enterprise-portal; npm ci; npm test; npm run build
```

运行测试前先阅读 [`e2e/README.md`](e2e/README.md)；浏览器验收会写入独立测试库，不得指向正式环境。

## 仓库整理

```powershell
# 只预览，不删除任何文件
scripts\maintenance\cleanup-local-artifacts.ps1

# 生成仓库、文档和项目状态清单
python scripts\maintenance\generate-repo-inventory.py
node scripts\maintenance\generate-project-status.mjs
python scripts\maintenance\generate-workflow-inventory.py

# 检查禁止跟踪的产物、大文件与重复文件
python scripts\check\check-repo-hygiene.py --fail-on-duplicates

# 只预览“已有权威副本的归档重复文件”
python scripts\maintenance\cleanup-archived-duplicates.py
```

清理脚本默认永远是预览模式；只有显式传入 `-Apply` 才会处理白名单中的可再生本地产物，且处理前会先备份。
