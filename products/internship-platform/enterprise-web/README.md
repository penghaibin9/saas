# E-A02 企业协同 Portal

固定施工分支：`agent/internship-e-a02-enterprise-portal`

目标：只建设岗位实习企业协同 facade/client，不拥有核心业务 Authority；企业、岗位、申请、落岗、评价继续复用既有 canonical facts。

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
- 企业岗位只能草稿/提交学校审核；企业端不提供直接发布或正式落岗能力。
- 企业申请 Decision 写入仅 `INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`；读取额外允许 `PENDING`。
- `ACCEPT_INTENT` 只表示企业拟接收并等待学校最终确认，不等于正式 Placement。
- 撤回拟接收使用 A01 已冻结的专用 `POST /applications/{id}/withdraw-accept`，原因至少 2 个字符；A02 不再复用通用 Decision POST 模拟撤回。
- Decision `status` 与 `effectStatus` 分离；只有 `ACTIVE` 表示当前有效企业处理事实，`EXPIRED / SUPERSEDED / CONSUMED` 均不可被客户端当成当前有效拟接收。
- Applicant 材料只消费冻结投递材料投影，不读取完整 StudentProfile；list adapter 只保留页面必需字段，主动丢弃 `studentId/studentNo/materialSnapshotId/submissionVersion/decisionVersion` 等内部标识。
- 联系方式只通过 A01 已冻结 `POST /applications/{id}/contact-view` 请求；A02 只识别当前 canonical `MASKED_ONLY / AFTER_INTERVIEW / AFTER_ACCEPT_INTENT / IMMEDIATE`，页面不自行判断是否达到阶段，只有服务端成功返回 phone/email 后才显示，并由后端记录 CONTACT_VIEW 审计。
- 未配置招聘季联系方式策略时，A01 默认只允许 `MASKED_ONLY / AFTER_INTERVIEW / AFTER_ACCEPT_INTENT`；`IMMEDIATE` 必须由学校招聘季策略显式允许，A02 不把缺配置解释为“全部允许”。
- 实习学生只读取正式 `InternshipRecord` 企业投影；未冻结前本地 fail-closed。
- 企业评价复用现有 canonical；actor/member/source/time/audit 由后端 facade 写入。
- Campaign `CLOSED/ARCHIVED` 后 RECRUITMENT 写动作 fail-closed；历史申请/岗位/Decision 保留。
- `INTERNSHIP_COLLAB` 不能由前端根据 Campaign 状态推断；只有服务端显式确认有效 Grant/capability 后才开放正式实习协同能力。
- A01 尚未冻结的接口不请求兼容/猜测路径：adapter 本地返回 `ENTERPRISE_FACADE_UNFROZEN`，运行时门禁要求网络请求数为 0。
- 前端角色门禁只用于 UX fail-closed，不替代后端权限；每个 Applicant 请求仍由 A01 重新校验 member role + tenant/company/campaign/grant scope。

## 当前施工状态

- **A02-0 已完成**：独立 Vue Portal、六项固定导航、真实 lockfile、Node 24、Actions v7、PR exact-head checkout/hard assertion；Playwright 仅安装 Chromium headless shell。
- **A02-1 已完成**：接入 A01 login / invite inspect / invite accept / refresh / recruitment context；token 仅内存、refresh single-flight、普通登录清旧 Campaign、邀请 campaign 只能来自同 tenantCode+token 刚刚 inspect 的结果；支持 `ENTERPRISE_CONTEXT_REQUIRED` 多 EnterpriseMember 且只回传 `memberId`。
- **A02-2 已完成 UI/合同**：首页/八指标/任务/历史招聘季；Campaign list/dashboard 未冻结时本地 fail-closed，不伪造 OPEN/0。
- **A02-3 已完成 UI/合同**：企业公开资料编辑、学校控制字段只读；Company GET/PUT 未冻结时编辑与 Logo 上传一起禁用，避免先上传文件再被 PUT 拒绝形成孤儿文件。
- **A02-4/A02-5 已完成 UI/合同**：岗位八态、草稿/待审、五区表单与白名单 payload；Position facade 未冻结时 0-network fail-closed，企业无直接发布能力。
- **A02-6 已接 A01 Applicant 正式读链**：`GET /applications?campaignId=&page=&pageSize=&positionId=&decisionStatus=`、`GET /applications/{id}`、`POST /applications/{id}/contact-view` 已接。当前工作台只开放 A01 已冻结且有真实数据源的“处理状态 + 分页”；岗位/专业/年级/匹配筛选不再伪装成可用。A02 list view model 最小化，只显示姓名、专业、年级、岗位、志愿、提交时间、处理状态/effect，不传播学号和内部材料 ID。`MENTOR` 导航禁用，直接 URL 也在任何 Applicant 请求前 fail-closed。
- **A02-7 已接 A01 Decision lifecycle**：通用 Decision POST、专用 withdraw-accept POST 已接；INTERVIEW 必填 `interviewAt`，ACCEPT_INTENT 二次确认，撤回原因必填。active 拟接收依据 `decisionStatus=ACCEPT_INTENT + effectStatus=ACTIVE` 判断，不再依赖 list 未返回的志愿组字段。A01 已把企业处理窗口收口到共享 Campaign operation-window guard；A02 不自行复制时间窗算法。
- **A02-8 已完成 UI/合同**：正式实习学生分页/筛选边界；企业 `InternshipRecord` 投影 facade 未冻结时本地 fail-closed。
- **A02-9 已完成 UI/合同**：评价任务分页、五维 0–100 显式评分、防伪 actor/source/time/audit；task/submit facade 未冻结时本地 fail-closed。
- **A02-10 已完成**：CLOSED/ARCHIVED 招聘写 fail-closed；历史招聘季入口保留；正式实习协同只接受服务端显式能力。
- **商业化 UX 净化已完成**：企业可见模板自动禁止 `A01 / Authority / canonical / facade / companyId / 状态机 / 真值` 等工程黑话；技术合同保留在 script/test/README。
- **依赖安全门禁已完成**：A02 targeted 执行 production-only npm audit；审计报告必须是完整 v2 JSON，metadata high/critical/total 必须与 findings 明细一致；获取失败、畸形报告、未豁免 high/critical 均 fail-closed，并上传 14 天审计证据。

## A01 联调依赖账本

最新已审计 A01 HEAD：`67c401df5746db6bad3802f2589202d292bacabe`（`fix(internship): fail closed default contact sharing`）。

### 已冻结并被 A02 消费

- 企业认证 / 邀请 / `RECRUITMENT` context。
- `GET /internship/enterprise-portal/applications`：企业 Applicant list，冻结参数 `campaignId/page/pageSize/positionId/decisionStatus`，服务端按当前 EnterpriseContext 约束企业范围。
- `GET /internship/enterprise-portal/applications/{application_id}?campaignId=`：冻结投递材料投影。
- `POST /internship/enterprise-portal/applications/{application_id}/contact-view?campaignId=`：按 current verified contact + snapshot consent + stage + scope 服务端校验后 reveal，并写 CONTACT_VIEW 审计；默认招聘季策略不允许 `IMMEDIATE`，除非学校显式配置。
- `POST /internship/enterprise-portal/applications/{application_id}/decision?campaignId=`：企业 Decision 写链；INTERVIEW 要求 `interviewAt`。
- `POST /internship/enterprise-portal/applications/{application_id}/withdraw-accept?campaignId=`：active ACCEPT_INTENT 专用撤回链，reason 必填。
- Enterprise Portal role permission：`internship.enterprise.view → COMPANY_ADMIN/HR/MENTOR`；`internship.application.view/review → COMPANY_ADMIN/HR`。
- Applicant Decision lifecycle：`PENDING → INTERESTED/INTERVIEW/ACCEPT_INTENT/REJECTED`，effect 独立为 `ACTIVE/EXPIRED/SUPERSEDED/CONSUMED`；正式 Placement 继续归学校 Authority。
- 招聘操作窗口已统一由 A01 shared window guard 执行：`INVITE / POSITION_SUBMIT / STUDENT_SELECT / ENTERPRISE_DECISION / SCHOOL_CONFIRM`；A02 不复制第二套窗口真值。

### 当前 P0 联调缺口

A01 `/context` 当前仍只返回 tenant/member/company/campaign/batch/grant 等上下文，尚未显式返回 `capabilities.recruitmentWrite` 或等价可写能力。A02 不从 `grantType=RECRUITMENT`、Campaign ID、客户端时钟或历史状态反推可写，因此真实 Decision/岗位写按钮继续 fail-closed。后端已经具备最终 operation-window 校验，但客户端仍需要显式 capability 才能安全开放入口。

### 仍未冻结的企业 Portal facade

- Campaign 列表 / Dashboard
- Company GET / PUT
- Position list/detail/create/update/submit/withdraw
- Resume PDF
- InternshipRecord 企业投影
- 企业评价任务 / 提交 actor facade
- 对外可调用的 `INTERNSHIP_COLLAB` context/capability

A02 对这些缺口继续本地 fail-closed + 0 network。A01 新合同落地后仍按 `A02-1 → A02-10` 原顺序校准。

## 集成基线

- 当前 E-series integration base：`b1e417643790d0cbe42b1c2f104c3c9b52eb0c8b`。
- A02 已两次通过二父 merge commit 同步 Authority integration/main 前进，均 `force=false`；同步后 A02 自有 diff 仍只位于 `enterprise-portal/**` 与 `.github/workflows/internship-enterprise-portal.yml`。
- A01 最新 `67c401df` 目前领先 integration base；A02 已按其公开 router/service 真合同完成客户端校准，待总集成线回收 A01 后再做 merge-ref 联调复核，不把 A01 backend 文件复制进 A02 分支。

## 最终门禁

固定收：

1. exact-head checkout + hard assertion
2. lockfile `npm ci`
3. production dependency audit acquisition integrity + high/critical fail-closed
4. authority / privacy / auth lifecycle / role permission / A01 facade / unfrozen-facade 0-network / business-facing copy contracts
5. Applicant facade 动态测试：冻结 query 参数、最小 UI DTO、contact-view、withdraw-accept
6. ESLint + production build + 固定演示凭据扫描
7. Chromium headless-shell Playwright：
   - 普通企业登录：Campaign list 未冻结时本地 fail-closed，legacy root 请求 0
   - HR 邀请：inspect campaign 绑定成功，canonical Applicant list 只发冻结参数且页面不显示 studentNo
   - HR Applicant：list → Snapshot → contact-view 真链，联系方式只在 contact-view 成功后显示；Decision 因缺显式 capability 保持禁用
   - MENTOR：报名学生导航禁用，直接 URL 的 list/Snapshot/contact 请求均为 0
8. browser evidence + dependency audit artifacts SHA-256
