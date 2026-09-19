# 职校学生全生命周期系统

面向职业院校销售、部署和验收的多租户学生全生命周期 SaaS。本仓库不是静态原型：正式能力以当前代码、MySQL 迁移、权限校验和自动化测试为准。

## 工程入口

| 目录 | 职责 | 主要技术 |
|---|---|---|
| `backend/` | 统一后端、权限、审计、迁移 | FastAPI / SQLAlchemy / Alembic / MySQL |
| `frontend/` | 官网、学校管理 PC、平台运营控制面 | Vue 3 / Vite |
| `student-portal/` | 学生 PC 门户 | Vue 3 / Vite |
| `miniapp/` | 学生与教师移动端 | uni-app / Vue 3 |
| `enterprise-portal/` | 岗位实习企业门户 | Vue 3 / Vite |
| `e2e/` | 跨端真实浏览器验收 | Playwright |
| `shared/` | 跨端契约与生成索引 | JSON / scripts |
| `deploy/` | 部署、回滚与运维配置 | Docker / Nginx / systemd |

## 当前状态

- 项目状态：[`docs/00-项目入口与总控/project-status.json`](docs/00-项目入口与总控/project-status.json)
- 文档总导航：[`docs/README.md`](docs/README.md)
- 最高开发与安全规则：[`AGENTS.md`](AGENTS.md)
- 兼容施工模式细则：[`CLAUDE.md`](CLAUDE.md)
- 部署与上线入口：[`docs/07-部署运维交付与商业化/deploy/README.md`](docs/07-部署运维交付与商业化/deploy/README.md)

`implemented` 只表示代码能力存在，不等于已通过统一交付门禁。只有当 `project-status.json` 的基线与候选提交一致且 `releaseGates` 全部通过时，该状态文件才可作为交付证据。

## 常用验证

### 本机日常沙箱

双击根目录 `start-system.cmd`，或运行 `scripts/dev/launch-local.ps1`。日常验收固定使用 Docker
`student-lifecycle-v8-mysql`（3307）的 `student_lifecycle_runtime_20260902`，学校为
`sandbox-school`（`1000000000000000007`）。启动器校验学校和迁移版本，禁止自动清库或换端口。

学校/教师 PC 为 `http://localhost:5173/login?tenant=sandbox-school`，学生 PC 为
`http://localhost:5199/portal/login?tenant=sandbox-school`，教师与学生 H5 共用 5188，实习企业入口为 5202；
全部连接本机 8000 后端。数据库凭据仅放在未入库的 `backend/.env`；启动器不会采用其他任务继承的数据库连接。
桌面的“一键启动职校学生全生命周期系统”快捷方式也使用这个入口。代码或本地配置更新后再次启动，
会更新已由该启动器登记的服务；需要强制重启可加 `-Restart`。停止服务使用 `scripts/dev/stop-dev.ps1`，数据库记录保留。
教师与学生 H5 的演示数据回退已在日常配置中关闭；网络失败会明确报错。
清理型自动测试仍使用独立测试库，不能清理这份持久沙箱；任务完成后须在日常沙箱复核对应四端业务。

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
