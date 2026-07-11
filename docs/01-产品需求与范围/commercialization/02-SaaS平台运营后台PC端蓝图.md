# 02-SaaS 平台运营后台 PC 端蓝图 V1.0

> 性质：蓝图冻结文档（P5.5 产物），本阶段不开发任何页面代码。
> 路由域冻结：**`/platform`**（与总册 V3.0 §5.2 一致；不用 /console、/saas-admin）。
> Layout：PlatformLayout，基于 BasePortalLayout 派生（禁止复制壳），主色可用 --gray-900 侧边以视觉区分学校端。
> 铁律：平台后台管"学校们"（租户/钱/开关），学校端管"学生们"（业务）。/platform 下**永不渲染任何学生业务明细**（总册红线）。

## 1. 页面总清单（21 页）

优先级：P1=商业化必做（P6-2 起分批开发）；P2=可后期；P3=只冻结不开发。

| # | 页面 | 路由 | 作用 | 主要字段 | 主要操作 | 影响学校端什么 | 优先级 |
|---|---|---|---|---|---|---|---|
| 1 | 运营总览 | /platform | 厂商首页：租户数/试用数/即将到期/风险客户 | 租户总数、TRIAL 数、30天内到期数、活跃度 | 下钻到租户 | 无（只读汇总） | P1 |
| 2 | 学校租户管理 | /platform/tenants | 全部学校列表 | 校名/code/地区/状态/套餐/到期日/学生数 | 新建租户、启停用、进详情 | 租户 status=停用 → 全端不可登录 | **P1（首批第 1 页）** |
| 3 | 租户详情 | /platform/tenants/:id | 单校全景 | 基本信息+订阅+licenses+quotas+账号 | 页签切换 | — | P1 |
| 4 | 模块授权中心 | /platform/tenants/:id/licenses | **核心开关页**：该校各模块授权 | moduleCode/status(TRIAL/ACTIVE/EXPIRED/READONLY/DISABLED)/起止/features | 开通、停用、续期、转只读、改功能点 | 菜单显隐、路由可达、按钮可用、指标显隐 | **P1（首批第 2 页）** |
| 5 | 套餐管理 | /platform/packages | 套餐模板维护 | 套餐名/模块集/featureFlags/配额默认/价格 | 建/改/停售套餐 | 新租户初始化的默认开关 | P1 |
| 6 | 试用与到期管理 | /platform/expiry | 到期雷达 | 租户/模块/剩余天数/试用转化状态 | 一键续期、转只读、发提醒 | 到期日→学校端只读横幅 | P1 |
| 7 | 学校账号管理 | /platform/tenants/:id/accounts | 开校管理员账号 | 账号/角色/状态/最后登录 | 建校级管理员、重置密码 | 学校首个管理员可登录 | P1 |
| 8 | 操作审计日志 | /platform/audit | 平台侧所有开关操作留痕 | 谁/何时/对哪校/改了什么/前后值 | 筛选、导出 | 无（合规底座） | P1 |
| 9 | 模块商品管理 | /platform/modules | 模块目录与依赖关系 | moduleCode/名称/dependsOn/可售状态 | 上下架模块 | 授权中心可选项 | P2 |
| 10 | 订单与合同管理 | /platform/orders | 成交记录 | 订单号/租户/条目/金额/合同号 | 录单、关联订阅 | 生成/续期 subscription | P2 |
| 11 | 续费与开票记录 | /platform/billing | 财务台账 | 续费记录/发票状态 | 登记开票 | 无 | P2 |
| 12 | 功能开关配置 | /platform/tenants/:id/features | feature 级细开关 | featureKey/on-off（如 internship.enterprise_portal、export.encrypted_pdf） | 逐项开关 | 按钮/入口级显隐 | P2 |
| 13 | 数据用量统计 | /platform/usage | 各校 quota 消耗 | 学生数/教师数/存储/导出次数 | 导出报表 | 超限预警依据 | P2 |
| 14 | 公告与消息推送 | /platform/announcements | 向学校端发公告 | 标题/对象租户/渠道/时间 | 发布、撤回 | 学校端消息中心收到 | P2 |
| 15 | 系统参数配置 | /platform/settings | 平台级参数 | 试用默认天数、只读宽限期等 | 修改参数 | 新授权默认值 | P2 |
| 16 | 权限模板管理 | /platform/templates/permissions | 角色-权限点模板 | 模板名/permCodes | 维护模板 | 新租户初始角色 | P3 冻结 |
| 17 | 菜单模板管理 | /platform/templates/menus | 各端菜单树模板 | menuKey/path/moduleCode/order | 维护模板 | 学校端菜单结构 | P3 冻结 |
| 18 | 角色模板管理 | /platform/templates/roles | 8+8 角色模板 | roleCode/dataScope | 维护模板 | 学校端角色初始化 | P3 冻结 |
| 19 | 模块开关配置（批量） | /platform/switches | 跨租户批量开关 | 多选租户×模块 | 批量开/停 | 同 #4 批量版 | P3 冻结 |
| 20 | 集成开放配置 | /platform/integrations | API key/回调 | key/配额/白名单 | 发 key | 12 中心能力 | P3 冻结 |
| 21 | 版本与灰度发布 | /platform/releases | 按租户灰度 | 版本/灰度租户集 | 圈租户发版 | 学校端功能可见性 | P3 冻结（后期） |

## 2. 分级结论

- **商业化必做 8 页**（P1）：#1-#8。其中 **P6-2 首批只做 2 页：#2 租户列表 + #4 模块授权中心**——这两页足以让 licenseContext 有配置端，学校端全线受控。
- **可后期 7 页**（P2）：#9-#15，签下第 3 所学校前后再做。
- **只冻结不开发 6 页**（P3）：#16-#21，结构进文档、路由占坑、代码不写。

## 3. 平台后台 vs 学校 PC 管理端（一张表说清）

| 维度 | /platform 平台后台 | /admin 学校管理端 |
|---|---|---|
| 用户 | SaaS 厂商运营（你自己团队） | 学校教师/管理员 |
| 管的对象 | 租户、套餐、授权、钱 | 学生、课题、实习、成绩 |
| 数据边界 | 看所有学校的"壳信息"，看不到学生明细 | 只看本校，看得到学生明细 |
| 菜单来源 | 平台固定菜单 | 模块授权+角色动态生成 |
| 到期影响 | 自己不受套餐控制 | 受 license 全面控制 |
| 审计重点 | 开关/授权/续期操作 | 业务审批/敏感查看 |

## 4. 首批 2 页的验收口径（供 T09 任务包引用）

1. /platform/tenants：列出 ≥3 个 mock 租户（试用校/单模块校/标准版校），可进详情。
2. /platform/tenants/:id/licenses：翻转某模块 ACTIVE→DISABLED 后，切到该校学校端（mock 租户切换器），对应菜单立即消失、直达路由展示 AppGlobalState noLicense 态；转 READONLY 后学校端该模块页头出现不可关闭只读横幅、全部写按钮 disabled。
3. 每次开关翻转写入一条审计 mock 记录（页 #8 未开发前先落 console+store）。
4. lint 0/0、build 通过；PlatformLayout 复用 BasePortalLayout，无复制壳。
