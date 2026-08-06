# Playwright 生产级交互测试底座

本目录只用于 **真实浏览器 + 真实后端 + 独立 MySQL 测试库**。它不会连接正式数据库，也不会把 mock 接口当作通过。

## 当前覆盖

1. 教师 PC 与学生 PC 的真实表单登录。
2. `demo-school` 与 `sandbox-school` 双会话租户隔离。
3. 多角色账号从可见“身份列表”切换，验证令牌轮换和工作台重建。
4. 毕业设计完整点击链：
   - 学生签署任务书并提交开题；
   - 导师打开待审队列并驳回；
   - 学生读取驳回原因、修改、重交；
   - 导师通过新版本；
   - 管理员切换毕设管理员身份，复核状态和审批留痕；
   - 学生端确认最终状态。

批次、导师、学生、课题、任务书属于流程前置条件，由 `lib/api-fixture.mjs` 通过真实后端 API 在独立测试库准备。所有关键状态动作必须由浏览器点击完成。

## 强制安全门

运行前必须同时满足：

- `E2E_ALLOW_DESTRUCTIVE_TESTS=true`
- `APP_ENV`、`DEPLOYMENT_MODE` 不是 production
- `DATABASE_URL` 包含 `e2e` 或 `test`
- 默认只允许 localhost 数据库、API 和页面地址
- 远程环境必须显式设置 `E2E_ALLOW_REMOTE=true` / `E2E_ALLOW_REMOTE_DB=true`

## 本地运行

先启动独立 MySQL 测试库、后端、教师 PC 和学生 PC，再执行：

```bash
cd e2e
npm install
npx playwright install chromium
E2E_ALLOW_DESTRUCTIVE_TESTS=true \
APP_ENV=test \
DEPLOYMENT_MODE=local \
DATABASE_URL='mysql+pymysql://root:password@127.0.0.1:3306/student_lifecycle_e2e' \
npm test
```

账号默认使用仓库已有的 E2E 引导脚本生成：

```bash
cd backend
python scripts/e2e_bootstrap_graduation_accounts.py
python scripts/e2e_reset_graduation_passwords.py
python scripts/e2e_verify_graduation_accounts.py
```

## 失败证据

每个失败测试自动保留：

- 页面截图
- Chromium 录像
- Playwright trace
- API 请求/响应元数据（认证、Cookie、密码和令牌已脱敏）
- Console error 和 pageerror
- HTML 报告和 JUnit XML

GitHub Actions 还会上传后端、教师端、学生端启动日志，便于区分页面错误、接口错误和环境错误。
