# 05-Cursor / Claude Code 任务分发表 V1.0

> 用法：按顺序复制"一句话任务"给推荐执行者；一包一停，收报告对《00-手册》第 18 章关键行后再派下一包。
> 执行者只有五种：Cursor ／ Claude Code ／ Cursor 或 Claude Code ／ fable5 只读预审 ／ 人工拍板。

| 包号 | 阶段 | 任务名称 | 推荐执行者 | 一句话任务（可直接复制） | 允许文件范围 | 禁止事项 | 完成标志 |
|---|---|---|---|---|---|---|---|
| T01 | P5 | 商业化页面清单冻结 | Cursor | 按《00-作战手册》与 P5 预审报告，将 docs/01-产品需求与范围/commercialization/01 定稿为冻结版，逐页带路由/角色/Layout，完成后停止并输出变更点清单 | docs/01-产品需求与范围/commercialization/01 | 改任何代码 | 文档定稿 |
| T02 | P5.5 | SaaS 后台蓝图预审 | fable5 只读预审 | 只读审查 02/03 两文件与 09A/11 文档的一致性，输出差异与补漏清单后停止 | 无（只读） | 改文件 | 预审报告 |
| T03 | P5.5 | 套餐与开关拍板 | **人工拍板** | 对《00-手册》第 16 章 11 项逐条确认或改写，结果记入 03 附录 | 03 附录 | — | 拍板记录 |
| T04 | P6-1 | 首批实习闭环开发 | **Claude Code** | 按 06 文档 §9/§17 与手册模板③，开发"我的实习/周报提交/周报批阅"三页（路由 /student/internship、/student/internship/reports、/admin/internship/report-review），一页一 commit，退回交互走 AppConfirmDialog≥5字+不可关 AppInlineAlert，完成三页后停止 | views/internship、modules/internship、router | 碰 dashboard 模块、P3 组件、mocks 既有集合结构；超过 3 页 | 闭环走通+lint/build 绿 |
| T05 | P6-1 | 学生端路由接入 | Claude Code | 建 /student 父路由挂 StudentPortalLayout，子路由接"我的实习"，菜单高亮与直达可访问，完成即停 | router、layouts 引用处 | 裸页面绕壳 | 直达+高亮 |
| T06 | P6-1 | 管理端路由接入 | Cursor 或 Claude Code | 建 /admin 父路由挂 BasePortalLayout 管理菜单，接周报批阅页，完成即停 | router | 菜单写死在页面 | 路由可达 |
| T07 | P6-2 | internship provider/mock 收口 | Claude Code | 按 06 §17-7 契约核对并收口 modules/internship/provider 全部方法命名与返回结构，输出契约对照表后停止 | modules/internship/provider、mocks/db.js 追加字段 | 改页面、改契约字段名 | 对照表全对齐 |
| T08 | P6-2 | graduation provider/mock 收口 | Claude Code | 仿 internship 范式按 05 §17-7 建 modules/graduation/{provider,adapter,store,types,README}，全 mock 实现，完成即停 | modules/graduation/* | 改 dashboard | 契约自检通过 |
| T09 | P6-2 | 模块授权上下文开发 | **Claude Code** | 按 03 文件 §4 数据结构实现 modules/platform/licenseContext（mock 三演示租户+store+useModule/useFeature/useQuota），附租户切换器，完成即停 | modules/platform/* | 业务页写 if 判断、造后端 | 切租户状态即变 |
| T10 | P6-2 | 动态菜单过滤开发 | **Claude Code** | 菜单抽为配置数据并按 licenseContext 过滤，BasePortalLayout/StudentPortalLayout 消费，验证关模块菜单即隐、READONLY 挂角标，完成即停 | 菜单配置文件、layouts 消费点 | 改 layouts 其他逻辑 | 03 文件 §3 表现全符合 |
| T11 | P6-2 | SaaS 后台首批 2 页 | Claude Code | 按 02 文件 §4 验收口径开发 /platform/tenants 与 /platform/tenants/:id/licenses 两页（PlatformLayout 复用 BasePortalLayout），开关翻转写审计 mock，完成即停 | views/platform、modules/platform、router | 超 2 页、渲染学生业务明细 | 02 §4 四条验收全过 |
| T12 | P6-3 | 毕设 4 页开发 | **Claude Code** | 复制实习页范式开发我的毕设/材料提交/材料批阅/课题管理四页，一页一 commit，完成即停 | views/graduation、router | 新造组件 | 毕设闭环+绿 |
| T13 | P8 | 路由守卫+按钮权限 | **Claude Code** | 全局守卫消费 licenseContext：未授权→noLicense 页、到期→只读禁写、超额→拦截提示；按钮统一 AppButton disabled，完成即停 | router 守卫、permission 工具 | 页面内散写判断 | 越权用例全拦 |
| T14 | P9 | Dashboard 下钻联动 | Claude Code | 建 drillTarget→路由+query 映射表并接首页跳转，未授权模块指标在聚合出口过滤，完成即停 | presentation 映射、首页跳转点 | 改 aggregate 口径 | 全指标可下钻 |
| T15 | 各阶段 | 阶段提交 | Cursor | 按模板⑨执行本阶段干净提交，输出 commit hash 后停止 | git | 混入无关文件 | hash+文件清单 |
| T16 | 各阶段 | 阶段验收报告 | fable5 只读预审 | 只读审计本阶段产出对照冻结文档，输出通过/不通过与修复项后停止 | 无 | 改文件 | 验收结论 |

## 执行者能力边界备忘

- **Cursor**：T01、T06、T15 及一切文档整理/样式微调/三态补齐类。
- **Claude Code**：T04/T05/T07-T14 等多文件、契约、上下文、守卫、闭环类——默认主力。
- **fable5**：T02、T16 及任何"开工前拿不准"的预审——只读，不写文件。
- **人工（你）**：T03 与第 16 章清单——只拍板，不干活。
