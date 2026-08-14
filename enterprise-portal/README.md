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

每完成一批自动进入下一批，不重排、不跨 Authority。整线完成后进入 exact-head targeted 门禁；发现真实缺陷可回补对应批次，再重新收最终门禁。

## Authority 边界

- 企业 API 不接受客户端 `companyId` 作为 Authority。
- 企业岗位只能 `DRAFT → PENDING`；企业端不提供 `PUBLISH`。
- 企业申请 Decision 仅允许 `INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`。
- `ACCEPT_INTENT` 只表示企业拟接收并等待学校最终确认，不能调用正式落岗 Authority。
- 企业撤回拟接收遵循 A01 canonical `ACCEPT_INTENT → REJECTED`，必须填写原因；历史 Decision 保留，effect 由后端置为 `SUPERSEDED`，A02 不造 `/withdraw-accept` 第二入口。
- Decision `status` 与 `effect_status` 分离：effect 仅 `ACTIVE / EXPIRED / SUPERSEDED / CONSUMED`，均不等于正式 Placement。
- Applicant 只消费 `ApplicationMaterialSnapshot` 投影，不读取完整 StudentProfile；联系方式必须单独走后端授权/审计。
- 实习学生只读取正式 `InternshipRecord`。
- 企业评价复用现有 canonical；actor/member/source/time/audit 由后端 facade 写入。
- Campaign `CLOSED/ARCHIVED` 后 RECRUITMENT 写动作 fail-closed；历史申请/岗位/Decision 保留。
- `INTERNSHIP_COLLAB` 不能由前端根据 Campaign 状态推断；只有服务端显式确认有效 Grant 后才开放正式实习协同能力。
- A01 尚未冻结的接口只保留 adapter / loading / error / empty UI，生产环境 fail-closed，不在 A02 自造第二套后端 schema。

## 当前施工状态

- **A02-0 已完成**：独立工程壳、路由、六项固定导航、tokens/common styles、targeted workflow；已提交真实 npm lock，workflow 使用 Node 24、Actions v7、只读 `contents` 权限与 `npm ci` 可复现安装。
- **A02-1 已完成**：接入 A01 正式 `/internship/enterprise-portal/auth/login`、`auth/invite/inspect`、`auth/invite/accept`、`context?campaignId=`；Bearer/refresh token 不落浏览器持久存储；普通登录无条件清理旧 Campaign；邀请激活才锁定已校验 Campaign；支持 A01 `ENTERPRISE_CONTEXT_REQUIRED` 多 EnterpriseMember 选择并仅回传 `memberId`，不提交 `companyId` Authority；refresh 明确失效时清理会话、网络暂时失败不误登出；受保护路由无内存认证直接回登录；提供显式退出登录并清 Pinia/Campaign 上下文。
- **A02-2 已完成**：企业首页、当前招聘季/阶段/截止时间、八项运营指标、今日任务、历史招聘季；A01 未返回真值时不伪造 `OPEN`、不把缺失指标显示成 0。
- **A02-3 已完成**：企业公开资料编辑、学校控制字段只读；Logo 改为正常文件选择并走 canonical `POST /api/v1/files` 临时私有上传，不要求 HR 手填 fileId。
- **A02-4 已完成**：我的岗位高密度列表、八态中文业务标签、DRAFT 编辑/PENDING 撤回修改；后端没返回报名/拟接收/已落实计数时显示 `—`，不伪造 0。
- **A02-5 已完成**：五区岗位表单、保存草稿、提交学校审核、PENDING 只读/撤回后修改；客户端白名单过滤企业可编辑字段，不提供直接发布。
- **A02-6 已完成**：BOSS 式两栏 Applicant 工作台、Pipeline、岗位/专业/年级/志愿/匹配筛选、CandidateCard、Snapshot detail；列表固定 `pageSize=50` 服务端分页，岗位筛选使用业务下拉而不是内部岗位 ID 文本框。
- **A02-7 已完成**：`INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`；服务端 `decisionDisabledReason` 会真实禁用按钮；`ACCEPT_INTENT` 增加显式二次确认并明确“不等于正式落岗”；released ACCEPT_INTENT 不再视为有效锁定；撤回拟接收必须填写原因并走 `REJECTED` canonical transition；前端类型已承接独立 effect-state 四态；联系方式 reveal 保持后端授权审计。
- **A02-8 已完成**：正式 `InternshipRecord` 企业学生列表，HR/Mentor scope 交给后端；`pageSize=50`、状态/关键词服务端筛选和分页，不一次性拉取整家公司历史实习生。
- **A02-9 已完成**：企业评价任务服务端状态筛选/分页；五维 canonical 评分不再默认全 90，必须显式填写 0–100；提交 payload 不允许伪造 source/actor/member/time/audit。
- **A02-10 已完成**：CLOSED/ARCHIVED 招聘写权限 fail-closed；Campaign 选择页保留历史招聘季只读入口；正式实习协同仅在服务端显式 `internshipCollab=true` 时宣称可继续，否则显示权限待后端确认，不从历史状态推断 Grant。

## A01 联调依赖账本

截至最新读取的 A01 HEAD `f661f27f709f3eac0cda48ebb1e60ce72a1879af`：

已确认：

- 企业认证 / 邀请 / `RECRUITMENT` context 已正式存在。
- 后端内部已有 `resolve_internship_collab_context()`。
- EnterpriseApplicationDecision side-fact 已建立；`ACCEPT_INTENT` 有 `valid_until`，撤回要求原因并转 `REJECTED + SUPERSEDED`；学校正式落岗消费决定后为 `CONSUMED`。
- PlacementSnapshot / 正式落岗事务继续归 A01/学校 Authority，A02 不把企业 Decision 宣称为录用或正式落岗。

企业 Portal 仍未正式暴露以下 facade：

- Campaign 列表 / Dashboard 详情
- Company GET / PUT
- Position list/detail/create/update/submit/withdraw
- Application list/detail/material/resume/contact/decision
- InternshipRecord 企业投影
- 企业评价任务/提交 actor facade
- 对外可调用的 `INTERNSHIP_COLLAB` context 路由

A02 对上述缺口继续 fail-closed。A01 路由/DTO 真正落地后，联调仍按 `A02-1 → A02-10` 原顺序逐项校准，不另造 Authority。

## 最终门禁

固定收：

1. authority / privacy / negative UI / auth lifecycle contract tests
2. ESLint
3. production build
4. 固定演示凭据扫描
5. Chromium targeted Playwright：真实登录 → 招聘季选择 → Applicant Snapshot 隐私边界 + released ACCEPT_INTENT
6. `package-lock.json` + `npm ci` 可复现依赖门禁
7. exact-head workflow 与浏览器证据
