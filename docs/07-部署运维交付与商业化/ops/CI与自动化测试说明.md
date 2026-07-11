# CI 与自动化测试说明

## 目的
每次提交/PR 自动验证，避免全靠人工，降低"改一处炸一片"的风险。

## 工作流文件
`.github/workflows/ci.yml`，含 4 个 job：

| Job | 内容 | 阻断 |
|---|---|---|
| backend | Python 3.12 + `pip install -r requirements.txt` + `pytest -q` | 是 |
| frontend | Node 20 + `npm ci` + `npm run lint` + `npm run build` | 是 |
| miniapp | Node 20 + `npm ci` + `build:h5` + `build:mp-weixin` | 否（continue-on-error） |
| forbidden-files | 扫描被 git 跟踪的敏感/产物文件 | 是 |

## 为什么 miniapp 是可选 job
uni-app 构建对环境较敏感（编译器版本、依赖体积），在 CI 上偶发失败不代表代码问题。因此设为 `continue-on-error: true`：**保留命令与日志供排查**，但不阻断合并。本地仍应跑 `npm run build:h5` 与 `build:mp-weixin` 双构建确认。

## 禁止文件检查覆盖
`.env`、`*.db`、`uploads/`、`exports/`、`dist/`、`node_modules/`、`unpackage/`、`*.pem`、`*.key`、`.ai-backup/`、`backend/_pfull3.txt`、`backend/scripts/_sec_verify.py`、`一键构建.bat`、`docs/04-UI与全端交互/ui/*.zip|*.pdf`。
命中即 CI 失败，防止密钥/产物/大文件误入库。

## 本地等价命令
```bash
cd backend && pytest -q && cd ..
cd frontend && npm run lint && npm run build && cd ..
cd miniapp && npm run build:h5 && npm run build:mp-weixin && cd ..
```

## 后续增强（未来）
- 加 pytest 覆盖率门槛（如 `--cov` + 阈值）。
- 加缓存命中率优化、矩阵多版本。
- 部署 job（手动触发）：构建产物 → 推送到演示服务器（需配 secrets，勿写死）。
- 接入代码质量/安全扫描（bandit、npm audit）。
