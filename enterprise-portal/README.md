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

每完成一批自动进入下一批，不重排、不跨 Authority。A01 或总集成线新增真合同后，仍按 `A02-1 → A02-10` 原顺序校准，不在 A02 自造后端路径、DTO 或权限真值。

## Authority / fail-closed 边界

- 企业 API 不接受客户端 `companyId` 作为 Authority；企业范围只由服务端 EnterpriseMember / Grant / Context 重校验。
- 企业岗位只允许草稿与提交学校审核；企业端没有 `PUBLISH`、正式落岗或 `assign_position` Authority。
- 企业 Decision 仅 `INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`；`ACCEPT_INTENT` 不是正式 Placement。
- 撤回拟接收遵循 canonical `ACCEPT_INTENT → REJECTED` 且必须填写原因；不造 `/withdraw-accept` 第二入口。
- Decision `status` 与 `effect_status` 分离；effect 仅 `ACTIVE / EXPIRED / SUPERSEDED / CONSUMED`。
- Applicant 只消费 `ApplicationMaterialSnapshot` 企业投影；学校实名只认 canonical school facts / 显式 `studentVerified=true`；联系方式只在服务端显式 `allowed=true` 时 reveal。
- A01 未冻结 facade 一律客户端本地 `ENTERPRISE_FACADE_UNFROZEN`，运行时门禁要求网络请求数严格为 0；不再请求 `/enterprise/internship/*` compatibility root。
- A01 已冻结 Applicant 权限：`COMPANY_ADMIN / HR` 可 view/review；`MENTOR` 不能处理 Applicant。A02 只做 UX fail-closed，服务端仍是最终权限 Authority。
- Campaign `CLOSED/ARCHIVED` 后 RECRUITMENT 写动作 fail-closed；`INTERNSHIP_COLLAB` 不从 Campaign/Grant 客户端推断。
- 企业可见 Vue template 不允许泄漏 `A01 / Authority / canonical / facade / companyId / 状态机 / 真值` 等工程术语；技术合同留在 script/test/README，企业界面只使用业务语言。

## 当前施工状态

- **A02-0 已完成**：独立 Vue Portal、六模块导航、真实 `package-lock.json`、Node 24、Actions v7、只读 `contents`、`npm ci`；targeted 仅 PR 触发，显式 checkout `pull_request.head.sha` + hard assertion；Playwright 仅安装 Chromium headless shell，并有独立安装超时。
- **A02-1 已完成**：接入 A01 login / invite inspect / invite accept / refresh / context；token 只在内存；refresh single-flight；认证明确失效清会话、暂时网络失败不误登出；普通登录清旧 Campaign；邀请激活只能使用同一 `tenantCode + token` 刚刚 inspect 返回的 campaignId，View 不提交 campaignId/companyId；支持 `ENTERPRISE_CONTEXT_REQUIRED` 多 EnterpriseMember 选择且只回传 `memberId`；显式退出清会话/Pinia/Campaign。
- **A02-2 已完成 UI/合同**：首页、招聘季上下文、八项运营指标、任务、历史招聘季；Campaign list/dashboard 未冻结时本地 fail-closed，不伪造 `OPEN` 或缺失指标 0。
- **A02-3 已完成 UI/合同**：企业资料学校控制字段只读，Logo 使用文件选择；Company GET/PUT 未冻结时编辑区/保存/上传全部禁用，并保证 `facadeReady` guard 发生在 File Center 上传之前，防止孤儿临时文件。
- **A02-4/A02-5 已完成 UI/合同**：岗位八态、草稿/待审、岗位表单、白名单 payload；Position facade 未冻结时 0-network fail-closed；企业没有直接发布入口。
- **A02-6 已接已冻结 Snapshot + role permission**：BOSS Applicant 工作台、服务端分页合同完成；Application list/candidate summary 未冻结时 fail-closed；canonical Snapshot GET 已接；MENTOR 报名学生导航禁用，直接 URL 也在任何 Applicant 请求前 fail-closed。
- **A02-7 已接真 Decision Authority**：canonical Decision POST 已接；ACCEPT_INTENT 二次确认、撤回原因、effect-state、ContactSharing enum 已对齐。当前 `/context` 未显式返回 `capabilities.recruitmentWrite=true`，所以真实生产写按钮继续 fail-closed。
- **A02-8 已完成 UI/合同**：正式 `InternshipRecord` 企业学生分页/筛选边界；enterprise projection facade 未冻结时本地 fail-closed，不把 ACCEPT_INTENT 提升为正式实习生。
- **A02-9 已完成 UI/合同**：五维 0–100 企业评价、服务端分页、防伪 actor/source/time/audit 合同；task/submit facade 未冻结时本地 fail-closed。
- **A02-10 已完成**：历史招聘季只读、招聘写 fail-closed；正式实习协同只接受服务端显式 capability。

## 总集成同步状态

A02 已安全同步当前 E-series integration base `b1e417643790d0cbe42b1c2f104c3c9b52eb0c8b`：

- 先以二父 merge 同步 `deddb723913bf1d39140593efdeef9c0b8a1bdec`；
- integration 随后合入最新 main 后前进到 `b1e41764`，A02 再以二父 merge 同步；
- 两轮同步前都完成碰撞审计，base 增量均未触碰 `enterprise-portal/**` 或 A02 专属 workflow；
- 全程 `force=false`，未 merge main 到 A02 自己的施工逻辑，也未覆盖其他智能体分支；
- 最新 compare 必须继续满足 `behind_by=0` 才允许称为最终候选。

## A01 联调账本

最新已审计 A01 HEAD：`a02513cc275ed8ba156d6a52765f21e4a69c9d6d`。

### 已冻结并被 A02 消费

- 企业认证 / 邀请 / `RECRUITMENT` context。
- `GET /internship/enterprise-portal/applications/{application_id}?campaignId=`：canonical ApplicationMaterialSnapshot 企业投影。
- `POST /internship/enterprise-portal/applications/{application_id}/decision?campaignId=`：canonical 企业 Decision 写链。
- 企业角色权限：
  - `internship.enterprise.view` → `COMPANY_ADMIN / HR / MENTOR`
  - `internship.application.view` → `COMPANY_ADMIN / HR`
  - `internship.application.review` → `COMPANY_ADMIN / HR`
- public auth 路由与受保护路由 auth policy 已由 A01 回归测试冻结。
- EnterpriseApplicationDecision / PlacementSnapshot / 正式落岗事务继续归 A01/学校 Authority。

### 当前 P0 联调缺口

A01 `/context` 仍只返回 tenant/member/company/campaign/batch/grant 等上下文，**没有显式 `capabilities.recruitmentWrite` 或等价安全写能力**。A02 不从 `grantType=RECRUITMENT`、Campaign ID 或历史状态反推可写性，因此 Decision/岗位写动作继续 fail-closed。

### 仍未冻结 facade

- Campaign list / dashboard
- Company GET / PUT
- Position list/detail/create/update/submit/withdraw
- Application list / candidate summary
- Resume PDF / contact-view
- InternshipRecord 企业投影
- 企业评价 task / submit actor facade
- outward `INTERNSHIP_COLLAB` context

上述全部保持本地 fail-closed + 0 network；A01 真路由/DTO 落地后继续按固定顺序校准。

## 生产门禁

最终候选固定收：

1. exact PR head checkout + `git rev-parse` hard assertion
2. `package-lock.json` + `npm ci`
3. production-only `npm audit --omit=dev`
4. audit JSON acquisition 完整性：必须是 npm audit v2，必须显式包含 high/critical/total，metadata 必须与 vulnerability 明细一致；网络错误 JSON、非法 JSON、缺计数或计数隐瞒一律 RED
5. 共享 high/critical production dependency policy + 14 天审计 artifact；不允许用 dev dependency 噪声冒充 runtime 阻断
6. authority / privacy / auth lifecycle / role-permission / business-copy / A01 facade / unfrozen-facade 0-network contract tests
7. ESLint
8. production build
9. 固定演示凭据扫描
10. Chromium headless-shell targeted Playwright：普通登录未冻结 Campaign list fail-closed；HR invite campaign 绑定；HR canonical Snapshot 隐私边界；MENTOR 直链 0 Snapshot 请求
11. browser evidence artifact SHA-256
12. 同 HEAD 仓库级 synthetic merge-ref CI，单独验证与当前 integration base 的集成，不与 exact-head 证据混用
