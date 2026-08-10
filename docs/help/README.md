# 跃科 SaaS 帮助中心治理与证据库

本目录用于帮助中心的**治理、审计、覆盖管理和发布证据**，不是第二套运行时正文。

## 单一真值边界

| 职责 | 当前真值位置 |
|---|---|
| 运行时结构化帮助 | `frontend/src/config/helpContent.js`、`frontend/src/config/help/` |
| verified-only 清洗与发布 | `frontend/src/config/helpCenterRuntime.js` |
| 管理端帮助中心 | `frontend/src/views/admin/help/AdminHelpView.vue` → `/admin/help` |
| 公开只读帮助 | `frontend/src/views/help/PublicHelpView.vue` → `/help` |
| 小程序统一帮助入口 | `miniapp/src/pages/common/help/index.vue` |
| 帮助指标 | `backend/app/api/v1/help_metrics.py`、`backend/app/services/help_metrics_service.py` |
| 可视化业务图 | `frontend/public/help/` |
| 治理、规范、审计和证据 | `docs/help/` |

详细架构理由见 [ADR-001](architecture/ADR-001-runtime-content-source.md)。

## 核心治理文件

- [当前知识审计报告](AUDIT_REPORT.md)
- [建设与运营方案](HELP_CENTER_PLAN.md)
- [核心覆盖矩阵](COVERAGE_MATRIX.md)
- [写作与截图规范](STYLE_GUIDE.md)
- [内容完成定义](maintenance/definition-of-done.md)
- [发布复核清单](maintenance/content-review-checklist.md)
- [可视化资产清单](assets/inventory.yml)
- [目录元数据](catalog.yml)

## 历史治理样稿

本目录仍保留几份早期 Markdown 样稿/证据：

- [学校首次开通配置顺序](getting-started/school-initial-setup.md)
- [如何新增一名学生](modules/student/create-student.md)
- [如何批量导入学生](modules/student/import-students.md)
- [为什么看不到菜单、按钮或学生数据](modules/system/data-permission.md)
- [如何使用手机扫码采集学生资料](mobile/student-scan-profile.md)

它们**不是产品运行时第二套正式正文，也不因为文件存在就自动发布**。如果这些治理样稿与 clean runtime 冲突，以重新验真的运行时任务卡为准，并修正文档；不得用旧 Markdown 覆盖 verified-only 真值。

## 当前施工状态

截至 2026-08-10：

- V2 可信知识底座 ✅
- V3-00 首页与信息架构 ✅
- V3-01 教务事实链 ✅
- V3-02 岗位实习办理链 ✅
- V3-03 毕业设计事实链 ✅
- V3-04 学工四条业务线 ✅
- V3-05 高频故障库 ✅
- V3-06 新学校第一次使用 ✅
- V3-07 页面就地帮助 ✅
- V3-08 指标与质量门 ✅
- 角色推荐细分 ✅

最新 Help Center Quality #212 已通过相关治理、帮助测试、小程序入口和管理 PC build。PR #48 仍保持 Draft，等待最新 HEAD 仓库级回归最终收口。

## 治理原则

- 帮助筛选是体验功能，不是权限控制；
- 不用菜单说明代替任务闭环；
- 不用流程图代替真实操作截图；
- 不把规划能力写成已上线能力；
- 不因为历史文件存在就让旧知识回流；
- 功能变更后必须重新核验相关帮助；
- SEARCH 无结果与 NOT_HELPFUL 用来发现真实知识缺口，而不是追求文章数量。
