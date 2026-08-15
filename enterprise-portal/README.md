# E-A02 企业协同 Portal

固定施工分支：`agent/internship-e-a02-enterprise-portal`

目标：只建设岗位实习企业协同 facade/client，不拥有核心业务 Authority；企业、岗位、申请、落岗、评价继续复用 `EmpCompany`、`InternshipPosition`、`InternshipApplication`、`InternshipRecord` 与现有企业评价 canonical。

## 固定施工顺序

1. A02-0 企业 Portal 工程壳
2. A02-1 登录/租户/邀请承接
3. A02-2 企业首页
4. A02-3 企业资料
5. A02-4 我的岗位
6. A02-5 岗位新建/编辑/提交
7. A02-6 报名学生 BOSS 式工作台
8. A02-7 INTERESTED / INTERVIEW / ACCEPT_INTENT
9. A02-8 实习学生
10. A02-9 企业评价
11. A02-10 Campaign 关闭后的权限/历史态

每完成一批自动进入下一批，不重排、不跨 Authority。整线完成后进入 exact-head targeted 门禁；A01 新 facade/permission 冻结后仍按原顺序逐项校准，不在 A02 猜合同。

## Authority 边界

- 企业 API 不接受客户端 `companyId` 作为 Authority。
- 企业岗位只能 `DRAFT → PENDING`；企业端不提供 `PUBLISH`。
- 企业申请 Decision 仅允许 `INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`。
- `ACCEPT_INTENT` 只表示企业拟接收并等待学校最终确认，不能调用正式落岗 Authority。
- 企业撤回拟接收遵循 A01 canonical `ACCEPT_INTENT → REJECTED`，必须填写原因；历史 Decision 保留，effect 由后端置为 `SUPERSEDED`，A02 不造 `/withdraw-accept` 第二入口。
- Decision `status` 与 `effect_status` 分离：effect 仅 `ACTIVE / EXPIRED / SUPERSEDED / CONSUMED`，均不等于正式 Placement。
- Applicant 材料只消费 `ApplicationMaterialSnapshot` 投影，不读取完整 StudentProfile；学校实名标记只有 canonical school facts 或服务端显式 `studentVerified=true` 才显示。
- 联系方式只有服务端显式 `allowed=true` 才允许 reveal；缺字段、false、旧枚举都 fail-closed。
- 实习学生只读取正式 `InternshipRecord`。
- 企业评价复用现有 canonical；actor/member/source/time/audit 由后端 facade 写入。
- Campaign `CLOSED/ARCHIVED` 后 RECRUITMENT 写动作 fail-closed；历史申请/岗位/Decision 保留。
- `INTERNSHIP_COLLAB` 不能由前端根据 Campaign 状态推断；只有服务端显式确认有效 Grant 后才开放正式实习协同能力。
- A01 尚未冻结的接口**不再请求兼容/猜测路径**：adapter 在客户端本地返回 `ENTERPRISE_FACADE_UNFROZEN`，企业页面显示业务化“学校端尚未开放”提示，且运行时门禁要求网络请求数为 0。
- 前端角色门禁只用于 UX fail-closed，不替代后端权限：A01 每个 Applicant 请求仍重新校验 member role + tenant/company/campaign/grant scope。

## 当前施工状态

- **A02-0 已完成**：独立工程壳、路由、六项固定导航、tokens/common styles；真实 `package-lock.json` 已提交，workflow 使用 Node 24、Actions v7、只读 `contents` 权限与 `npm ci` 可复现安装；targeted 只保留 PR 单触发，并显式 checkout PR HEAD + hard assertion。Playwright 仅安装 headless Chromium shell，浏览器安装步骤单独 8 分钟硬超时。
- **A02-1 已完成**：接入 A01 正式 `/internship/enterprise-portal/auth/login`、`auth/invite/inspect`、`auth/invite/accept`、`context?campaignId=`；Bearer/refresh token 不落浏览器持久存储；普通登录清理旧 Campaign；邀请激活只能锁定**同一 tenantCode + token 刚刚 inspect 成功返回的 campaignId**，View 不再提交 `campaignId/companyId`；支持 A01 `ENTERPRISE_CONTEXT_REQUIRED` 多 EnterpriseMember 选择且只回传 `memberId`；refresh 明确失效时清会话、网络暂时失败不误登出；受保护路由无内存认证直接回登录；显式退出清 Pinia/Campaign 上下文。
- **A02-2 已完成**：企业首页、当前招聘季/阶段/截止时间、八项运营指标、今日任务、历史招聘季 UI 已完成；Campaign list / dashboard facade 未冻结时本地 fail-closed，不伪造 `OPEN`、不把缺失指标显示成 0，也不请求旧 compatibility root。
- **A02-3 已完成**：企业公开资料编辑、学校控制字段只读；Logo 使用正常文件选择并走 canonical `POST /api/v1/files`；Company GET/PUT facade 未冻结时本地 fail-closed。
- **A02-4 已完成**：我的岗位高密度列表、八态中文业务标签、DRAFT/PENDING 业务 UI 已完成；Position facade 未冻结时本地 fail-closed，缺失报名/拟接收/已落实计数不伪造为 0。
- **A02-5 已完成**：五区岗位表单、保存草稿、提交学校审核、PENDING 只读/撤回后修改 UI 与白名单 payload 合同已完成；未冻结前不向猜测路由发写请求，企业端始终没有直接发布 Authority。
- **A02-6 已完成并接入已冻结 Snapshot + role permission**：BOSS 式两栏工作台、分页/筛选 UI 已完成；Application list/candidate summary 仍未冻结，因此列表本地 fail-closed；材料详情只在已有经服务端校验的 applicationId + campaign context 时调用 A01 canonical `GET /internship/enterprise-portal/applications/{id}?campaignId=`。A01 已冻结 Applicant view/review 仅 `COMPANY_ADMIN / HR`；`MENTOR` 的“报名学生”导航保持六模块结构但显示为禁用项，直接路由也在任何 Applicant API 前 fail-closed。
- **A02-7 已完成并接真 Decision Authority**：`POST /internship/enterprise-portal/applications/{id}/decision?campaignId=` adapter 已接入；`ACCEPT_INTENT` 二次确认、撤回原因、effect-state、ContactSharing enum 均已对齐 A01。A01 已冻结 review permission 为 `COMPANY_ADMIN / HR`；由于当前 `/context` 尚未显式返回 `capabilities.recruitmentWrite=true`，真实生产 Decision 按钮继续 fail-closed；客户端不会从 Grant/Campaign 自行推断可写。
- **A02-8 已完成 UI/合同**：正式 `InternshipRecord` 企业学生列表的分页/筛选/Authority 边界已完成；企业投影 facade 未冻结时本地 fail-closed，不把 `ACCEPT_INTENT` 提升为正式实习生。
- **A02-9 已完成 UI/合同**：企业评价任务分页、五维 0–100 显式评分、禁止伪造 actor/source/time/audit 已完成；评价 task/submit facade 未冻结时本地 fail-closed，不保留猜测的 `evaluation-tasks/{id}/submit` 路由。
- **A02-10 已完成**：CLOSED/ARCHIVED 招聘写权限 fail-closed；历史招聘季只读入口 UI 保留；正式实习协同仅在服务端显式 `internshipCollab=true` 时开放。

## A01 联调依赖账本

最新读取 A01 HEAD：`10ab5d32a3548eedb5f9c5b863939ab89ddae961`。

### 已冻结并已被 A02 消费

- 企业认证 / 邀请 / `RECRUITMENT` context。
- `GET /internship/enterprise-portal/applications/{application_id}?campaignId=`：canonical ApplicationMaterialSnapshot 企业投影。
- `POST /internship/enterprise-portal/applications/{application_id}/decision?campaignId=`：canonical 企业 Decision 写链。
- Enterprise Portal role permission：
  - `internship.enterprise.view` → `COMPANY_ADMIN / HR / MENTOR`
  - `internship.application.view` → `COMPANY_ADMIN / HR`
  - `internship.application.review` → `COMPANY_ADMIN / HR`
  - `MENTOR` 属于后续实习协同面，不能处理 Applicant。
- EnterpriseApplicationDecision side-fact：`ACCEPT_INTENT` 有 `valid_until`；撤回要求原因并转 `REJECTED + SUPERSEDED`；学校正式落岗消费后为 `CONSUMED`。
- PlacementSnapshot / 正式落岗事务继续归 A01/学校 Authority，A02 不把企业 Decision 宣称为录用或正式落岗。

### 当前 P0 联调缺口

A01 `/context` 当前仍只返回 tenant/member/company/campaign/batch/grant 等上下文，**尚未显式返回 `capabilities.recruitmentWrite` 或可供客户端判定的 Campaign 写状态**。A02 不从 `grantType=RECRUITMENT`、Campaign ID 或历史状态反推可写性，因此生产环境 Decision/岗位写动作会继续 fail-closed，直到 A01 明确冻结写 capability。这是当前最优先的 A01→A02 联调缺口，不在 A02 绕过。

### 仍未冻结的企业 Portal facade

- Campaign 列表 / Dashboard 详情
- Company GET / PUT
- Position list/detail/create/update/submit/withdraw
- Application 列表 / candidate summary
- Resume PDF / contact-view
- InternshipRecord 企业投影
- 企业评价任务 / 提交 actor facade
- 对外可调用的 `INTERNSHIP_COLLAB` context 路由

A02 对上述缺口统一**本地 fail-closed + 0 network**。A01 路由/DTO 真正落地后，联调仍按 `A02-1 → A02-10` 原顺序逐项校准，不另造 Authority。

## 最终门禁

固定收：

1. explicit exact-head checkout + hard assertion
2. `package-lock.json` + `npm ci`
3. authority / privacy / negative UI / auth lifecycle / A01 facade / role-permission / unfrozen-facade 0-network contract tests
4. ESLint
5. production build
6. 固定演示凭据扫描
7. Chromium headless-shell targeted Playwright：
   - 普通企业登录后 Campaign list 未冻结时本地 fail-closed，legacy compatibility root 请求数必须为 0
   - HR 邀请 inspect → accept 后，accept 响应不带 campaignId 仍只能使用同 tenantCode + token 已校验的 campaignId 请求 canonical `/context`；无写 capability 时保持只读
   - HR 已校验 Campaign context 下 canonical Snapshot 可读取，敏感字段不泄露，Decision 因缺显式 capability 保持禁用
   - MENTOR 的“报名学生”导航禁用；即使直接进入 Applicant URL，也在发出 canonical Snapshot 请求前本地拒绝
8. 浏览器证据 artifact SHA-256
