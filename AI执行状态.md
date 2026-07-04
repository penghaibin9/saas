# AI 执行状态

> 回来先看这里，不用记流程、不用翻历史。

## 最新更新（2026-07-04）：PC UI v2 最终验收与提交（PC-UI-V2-FINAL-ACCEPT）

本轮只做 **PC UI 最终验收 + 提交前整理**，不碰 miniapp / backend / deploy / scripts / 数据库文档。

1. **lint**：通过（eslint 0 错误 0 警告）。**build**：沙箱无法访问 npm registry（node_modules 为 Windows 版、缺 Linux 二进制），未能在沙箱执行；以本机 dev server 实测代替：12 个 /admin 页面全部打开正常，无白屏、无控制台红错、无横向滚动条。正式发布前建议本机跑一次 `npm run build` 复核。
2. 验收中修复 2 个小问题：`/admin` 裸路径无路由会白屏 → `router/index.js` 增加 `{ path: '/admin', redirect: '/' }`；工作台页脚残留「/dev/preview 旧产品体验页」入口 → 已从 `AdminWorkbenchView.vue` 移除（/dev/preview 存档路由本身保留）。
3. 前端展示文案无「职校」主名称残留（浏览器标题与门户品牌均为「高校学生全生命周期管理平台」；「演示职业技术学院」为租户名非产品名）。「产品体验中心」字样仅存于 /dev/preview 存档页内部，无对外入口。
4. 本次提交仅包含：`frontend/src/`、`docs/ui/pc-ui-v2/`、`AI执行状态.md`。miniapp / backend / deploy / scripts / 各类文档改动**未**纳入本次提交。未 push。
5. 备注：本文件此前一次写入被截断（下方 PROJECT-CONTRACT-QA-DEMO-DOCS 段仅存开头部分，`docs/backend-integration/` 及其后的 `docs/sales/`、`docs/qa/` 明细行丢失，完整清单以各目录 README 为准）。


## 2026-07-04：接口契约 / 权限 / 测试 / 演示 / 后端接入 / 销售 / 风险 七类交付文档（PROJECT-CONTRACT-QA-DEMO-DOCS）

本轮只补**交付类文档**，不碰任何业务代码、不碰数据库冻结册。只动了 `docs/api/`（仅新增，未改旧冻结册）、`docs/rbac/`、`docs/testing/`、`docs/demo/`（仅新增 README+01~06）、`docs/backend-integration/`、`docs/sales/`、`docs/qa/`、本文件。

1. **本轮做了什么：新增 7 套共 56 份文档**：
   - `docs/api/`：README + 01 接口契约总览、02 PC管理端接口契约、03 miniapp接口契约、04 统一响应结构与错误码、05 接口鉴权与数据范围、06 导入导出接口约定、07 文件上传接口约定、08 后端联调检查清单，共 **9** 份新文件。既有冻结册 `00-API契约冻结总册.md` 与按域契约 `01~05`（认证/学生/迎新/待办/岗位实习）**仅引用未改**（已核对 git 无改动）。
   - `docs/rbac/`：README + 01~07（角色体系、PC权限矩阵、miniapp权限矩阵、数据范围矩阵、角色切换规则、权限按钮清单、敏感操作清单），共 **8** 份。覆盖 7 类系统角色码 + 题面 11 类角色映射、6 类系统数据范围 + 题面 9 类范围映射（系统尚无的标注"待后端确认"）。
   - `docs/testing/`：README + 01~09（测试总览、PC/miniapp测试清单、权限/数据范围/导入导出/异常/回归/上线前验收清单），共 **10** 份。每条用例含编号/模块/角色/前置/步骤/预期/是否通过。
   - `docs/demo/`：本轮新增 README + 01~06（演示数据总览、PC/miniapp数据口径、演示角色账号、场景脚本、演示前检查），共 **7** 份。只写口径说明，未改任何 mock。（注：同目录 `一套完整演示脚本.md` 属其它任务包，非本轮所为。）
   - `docs/backend-integration/`、`docs/sales/`、`docs/qa/`：明细记录随截断丢失，见各目录 README。
