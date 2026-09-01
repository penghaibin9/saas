# X2 Golden Gate 最终验收

- 分支：`codex/orientation-dorm-20260901`
- 功能阶段：A0、A1、D1-D6、O1-O5、X1
- 验收日期：2026-09-01（Asia/Shanghai）
- 最终数据源：本机 MySQL `127.0.0.1:33317/saas_x2_migration_local`

## 数据库 Gate

- Alembic fresh base → head：通过。
- X1 → O5 → X1 downgrade/upgrade 往返：通过。
- `alembic current` 与 `alembic heads` 均为唯一 `20260901_school_xlsx_x1 (head)`。
- 系统角色模板完成 `studentAffairs.dorm.export` 规范权限、摘要和 permission ceiling 同步。
- 全校 Authority 只读审计：`tenantId=1000000000000000001`，`readOnly=true`，`issueCount=0`。

## 自动化 Gate

| 范围 | 最终结果 |
|---|---|
| 后端迎新/宿舍相关 16 个测试文件 | `67 passed` |
| 管理 PC ESLint | 通过 |
| 管理 PC 全量 Node 测试 | 通过 |
| 管理 PC production build + 21 路由预渲染 | 通过 |
| 学生门户 lint / test / production build | 全部通过 |
| 小程序全量测试 | `244 passed, 0 failed` |
| 小程序 H5 production build | 通过 |
| 微信小程序 production build | 通过 |
| `git diff --check` | 通过 |

管理 PC 构建仅保留仓库既有 CSS `@import` 顺序和 chunk 大小 warning，无构建错误。

## REAL 四端浏览器 Gate

使用真实后端、真实 MySQL、真实账号登录，无 mock fallback：

| 端 | 页面与关键证据 | 结果 |
|---|---|---|
| 教师/管理 PC | 宿舍房源页显示模板下载、xlsx 导入、台账导出；统计页显示 canonical 四口径 | 通过 |
| 学生 PC | 迎新页显示服务端资格、一次性凭证状态与 `canIssue=false` 阻断 | 通过 |
| 学生小程序 H5 | 迎新报到页显示服务端凭证、资格和缴费状态 | 通过 |
| 教师小程序 H5 | 宿舍现场工作台显示调宿、异常、巡检、复检和门禁 Provider 状态 | 通过 |

- 四端页面均正常渲染，未出现浏览器原生 JavaScript dialog。
- 教师宿舍确认链已使用页面内 `actionDlg`，合同测试明确禁止 `uni.showModal`；解决用户截图中的 `127.0.0.1` 原生弹窗问题。
- 门禁 Provider 未配置时明确显示 `DISABLED / 未配置`，未知人数不冒充未归人数。

## 最终判定

迁移、权限、数据 Authority、迎新签名核验、宿舍闭环、XLSX、报表、统计、四端真实页面和生产构建全部通过 X2 Golden Gate，可进入部署发布流程。
