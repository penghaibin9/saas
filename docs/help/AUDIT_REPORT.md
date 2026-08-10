# Help Center V3 最终知识审计报告

审计日期：2026-08-10  
审计对象：`penghaibin9/saas`，Draft PR #48  
审计基线：最新 `main=f8a99ff820077be0ce1fac22b6a49499142b34a8`

## 1. 结论

PR #48 已从早期“补一套帮助文档”的思路，收口为真正的 **Help Center 专项治理与自助服务 PR**。

当前正式架构是：

> **运行时帮助真值在 `frontend/src/config/help*`；公开/管理帮助页消费同一套结构化知识；`docs/help` 只承担治理、审计和证据，不复制第二套正式正文。**

本轮同步最新 main 后再次执行知识清洗原则：

- 能验证 → 收编；
- 半真半假 → 改写；
- 无代码依据 → 删除/隔离；
- 重复 → 合并；
- 未重新验真的历史知识继续由 verified-only 发布门隔离。

当前 Help Center V3 的 V3-00～V3-08 均已完成专项施工并通过 Help Center Quality #212。PR 仍保持 Draft，等待仓库级长回归最终收口。

## 2. 单一真值与发布边界

| 职责 | 当前权威位置 |
|---|---|
| 运行时结构化帮助 | `frontend/src/config/helpContent.js` + `frontend/src/config/help/` + `helpCenterRuntime.js` |
| verified-only 发布门 | `frontend/src/config/helpCenterRuntime.js` |
| 管理端帮助中心 | `frontend/src/views/admin/help/AdminHelpView.vue` |
| 公开只读帮助 | `frontend/src/views/help/PublicHelpView.vue`，路由 `/help` |
| 小程序帮助入口 | `miniapp/src/pages/common/help/index.vue` |
| 搜索/阅读/反馈指标 | `backend/app/api/v1/help_metrics.py` + `help_metrics_service.py` |
| 治理、规范和证据 | `docs/help/` |

`docs/help` 中的 Markdown 不作为第二套运行时正文；如果与运行时发生冲突，以重新验真的 runtime clean source 为准，并回头修正文档。

## 3. 已完成能力

### 3.1 V2 可信知识底座

- verified-only 白名单发布；
- 未重新验真的旧卡、旧百科、旧流程默认隔离；
- 七维正式任务合同：角色、入口、步骤、前置、成功结果、异常排查、权限说明；
- PC / 学生小程序 / 教师小程序尽量复用同一正文；
- 问题式搜索支持中文自然语言和错误码分词。

### 3.2 V3-00～V3-04 核心业务自学

已建立并验证：

- 首页三类意图：我要办一件事 / 我遇到问题 / 核心业务流程；
- 教务完整事实链；
- 岗位实习完整办理链；
- 毕业设计完整事实链；
- 学工四条高频办理线。

帮助中的权限解释统一为：

> permissionCode + 数据范围 + 稳定业务关系/owner/assignee + 当前业务状态。

角色名称和帮助筛选均不是授权凭证。

### 3.3 V3-05 高频故障库

16 张 verified-only 自助排障卡覆盖：

- 400 / 401 / 403 / 404 / 409 / 429 / 500 / 503；
- 权限/数据范围；
- ASSIGNEE_NOT_CONFIGURED；
- RETURNED vs REJECTED；
- 发布门；
- Excel 错误行；
- 待办一致性；
- 敏感数据；
- 文件上传/安全扫描；
- 异步导出/下载票据。

### 3.4 V3-06 新学校第一次使用

`sys-card-first-school-setup` 已形成 8 步开局链，覆盖实施项目、Excel、组织、角色/数据范围、账号、真实登录抽查、学期配置、READY_FOR_ACCEPTANCE；BLOCKER 不能人工确认绕过。

### 3.5 V3-07 页面就地帮助

最新 main 的 `BasePortalLayout` 已有“本页帮助 / 重看本页引导 / 帮助中心”入口。本 PR 不重写共享布局壳，而是通过运行时原地清洗与专项合同确保：

- 当前页只落到 verified-only 正式任务卡；
- 详情页可回落到对应业务任务卡；
- 正文展示下一步、自助排查和何时找管理员；
- 403 / 409 等阻断可进入统一故障库；
- 小程序携带 role/source 复用同一公开帮助正文。

`pageContextHelpV307.test.js` 已进入 Help Center Quality #212 并通过。

### 3.6 V3-08 真实指标

已真实记录：

- SEARCH；
- ARTICLE_VIEW；
- HELPFUL；
- NOT_HELPFUL。

公开 `/help` 与管理帮助页均纳入统计。搜索原文不落库，只保存不可逆 SHA-256 指纹、长度、命中数等低敏字段。学校管理员可查看近 30 天搜索命中率和明确反馈解决率。

在尚未打通真实人工升级/工单闭环前，`trueSelfServiceResolutionRate` 明确不可用，不用反馈率冒充真实自助解决率。

## 4. 最新 main 同步后的知识真值修正

本次同步发现一个典型“帮助比代码更超前”的问题：心理逐生范围帮助曾写成 `teacher_name / realName` 已完全退出授权链，但最新 main 仍保留历史姓名兼容兜底。

处理方式不是越界修改业务授权，也不是降低测试，而是按知识清洗原则改写帮助：

- `teacher_key` 是优先的稳定授权标识；
- 历史 `teacher_name / realName` 兜底仍存在，不能宣传“同名天然安全”；
- 学校应优先回填稳定 `teacher_key`；
- 同名教师场景需要管理员核对历史授权；
- 不建议继续新增姓名授权。

这类“业务实现尚未完成治理升级”的事实必须在帮助中如实披露。

## 5. 角色推荐现状

帮助角色筛选已从原来的 5 个粗粒度组扩展到更贴近实际使用的相关性筛选，包括：

- 教务处管理员；
- 学院管理员；
- 辅导员 / 班主任；
- 学工处管理员；
- 心理老师；
- 资助老师；
- 任课 / 录分教师；
- 实习指导 / 企业导师；
- 毕设导师 / 评阅 / 答辩角色；
- 学生等。

原 authRole 粗粒度映射保持兼容；细分筛选只减少帮助噪音，不改变真实权限。

## 6. 已关闭的历史复审问题

3 条历史 Codex review 已全部修复并 resolve：

1. 小程序生产构建注入真实 `VITE_HELP_CENTER_URL`；
2. 公开 `/help` 接入 tenant-aware 搜索、阅读和反馈指标；
3. 问题式搜索按中文自然语言/错误码拆词，不要求整句连续命中。

## 7. 仍然不能冒充“已完成”的事项

以下不是当前 Help Center 代码缺陷，但仍属于商业化运营阶段的真实验收工作：

- 不代表所有学校的真实角色、真实数据范围组合都已经人工走完；
- 不代表所有微信机型、弱网、隐私授权场景都完成实机验证；
- 不代表所有可视化 HTML 都等价于真实页面逐步截图；
- 不代表真实人工客服/工单升级闭环已经上线；
- 不代表帮助内容以后无需随业务变更持续复核。

这些事项应在正式学校实施、设备验收和持续运营中形成证据，不应通过编造文案“补齐”。

## 8. 当前质量结论

最新 Help Center 专项 HEAD 已通过 **Help Center Quality #212**：

- governance / links / ids / assets ✅
- 小程序帮助入口与生产 URL 合同 ✅
- V2/V3 全量帮助测试 ✅
- V3-07 页面就地帮助合同 ✅
- 角色推荐细分合同 ✅
- 管理 PC build ✅

PR #48 当前仍保持 Draft。最终是否 Ready for review 继续以后续 CI / Main / Playwright / Student Affairs / Graduation / File center 等仓库级闸门的最新 HEAD 结果为准。
