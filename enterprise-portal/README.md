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

每完成一批自动进入下一批，不重排、不跨 Authority。

## Authority 边界

- 企业 API 不接受客户端 `companyId` 作为 Authority。
- 企业岗位只能 `DRAFT → PENDING`；企业端不提供 `PUBLISH`。
- 企业申请 Decision 仅允许 `INTERESTED / INTERVIEW / ACCEPT_INTENT / REJECTED`。
- `ACCEPT_INTENT` 只显示“等待学校最终确认”，不能调用 `assign_position_in_tx()`。
- 实习学生只读取正式 `InternshipRecord`。
- 企业评价复用现有 canonical；actor/member/source/time/audit 由后端 facade 写入。
- Campaign `CLOSED/ARCHIVED` 后 RECRUITMENT 写动作 fail-closed；历史申请/岗位保留，正式实习协同由有效 `INTERNSHIP_COLLAB` Grant 继续。
- A01 尚未冻结的接口只保留 adapter / loading / error / empty UI，生产环境 fail-closed。

## 当前施工状态

- A02-0：已完成工程壳、路由、六项固定导航、tokens/common styles。
- A02-1：已完成并联调 A01 正式企业认证入口：`/internship/enterprise-portal/auth/login`、`auth/invite/inspect`、`auth/invite/accept`、`context?campaignId=`；token 不落浏览器持久存储，租户切换会清理旧招聘季选择。
- A02-2：已完成企业首页并做生产硬化：A01 未显式返回 Campaign 状态/写 capability 时不伪造 `OPEN`，dashboard 未返回时指标保持 `—`，不以假 0 冒充真实统计；Campaign/dashboard 详情 facade 继续等待 A01。
- A02-3：已完成企业公开资料编辑 + 学校控制字段只读；下一批继续清理文件 ID 技术输入并校准 A01 Company facade。
- A02-4：已完成高密度岗位列表；等待 A01 企业岗位 facade。
- A02-5：已完成五区岗位表单、保存草稿、提交学校审核；等待 A01 企业岗位 facade。
- A02-6：已完成两栏报名学生工作台、Pipeline、筛选、CandidateCard、Snapshot detail；等待 A01 ApplicationMaterialSnapshot facade。
- A02-7：已完成四类 Decision、联系方式 reveal、LOCKED/released UX；等待 A01 Decision/contact facade。
- A02-8：已完成正式 InternshipRecord 企业学生列表与 HR/MENTOR scope UI；等待 A01 InternshipRecord projection facade。
- A02-9：已完成企业评价任务、五维评分与 canonical facade 提交；等待 A01 企业 actor 适配。
- A02-10：已完成 CLOSED/ARCHIVED 招聘写权限 fail-closed、历史招聘季展示与实习协同继续态。

下一批固定进入：A02-3 企业资料生产硬化 → A02-4/A02-5 岗位 facade 校准 → A02-6/A02-7 Applicant/Decision 校准 → A02-8/A02-9/A02-10 → targeted test/build/browser gate。
