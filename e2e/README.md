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
   - 管理员复核状态和审批留痕；
   - 学生端确认最终状态。
5. 岗位实习请假完整点击链：
   - 学生在门户填写并提交请假；
   - 实习指导教师从待审批队列打开同一请假单并确认通过；
   - 学生在已通过请假单上填写销假说明并办理销假；
   - 学校管理员复核最终 `RETURNED` 状态，以及 `APPLY`、`REVIEW_APPROVE`、`RETURN` 三段审计事件。

毕业设计批次、导师、学生、课题和任务书属于流程前置条件，由 `lib/api-fixture.mjs` 通过真实后端 API 在独立测试库准备。

岗位实习批次、学生实习档案、指导教师绑定、企业和岗位属于流程前置条件，由 `backend/scripts/e2e_seed_internship_sandbox.py` 直接写入独立 E2E MySQL；脚本不会创建请假单或请假审计记录。请假提交、教师审批和学生销假全部必须由浏览器可见操作完成。

## 强制安全门

运行前必须同时满足：

- `E2E_ALLOW_DESTRUCTIVE_TESTS=true`
- `APP_ENV`、`DEPLOYMENT_MODE` 不是 production
- `DATABASE_URL` 包含 `e2e` 或 `test`
- 默认只允许 localhost 数据库、API 和页面地址
- 远程环境必须显式设置 `E2E_ALLOW_REMOTE=true` / `E2E_ALLOW_REMOTE_DB=true`

岗位实习前置脚本还会再次校验本地数据库地址，并只向 `sandbox-school` 写入测试批次数据。运行时元数据写入 `e2e/runtime/internship-fixture.json`，不含账号密码，也不在 Actions Artifact 收集范围内。

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

账号默认使用仓库已有的 E2E 引导脚本生成；岗位实习数据要在账号生成后准备：

```bash
cd backend
python scripts/e2e_bootstrap_graduation_accounts_ci.py
python scripts/e2e_reset_graduation_passwords.py
python scripts/e2e_verify_graduation_accounts.py
python scripts/e2e_seed_internship_sandbox.py
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
