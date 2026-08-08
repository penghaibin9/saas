# 跃科 SaaS 帮助中心治理与证据库

本目录用于帮助中心的**治理、审计、覆盖管理和发布证据**，不是第二套运行时正文。

## 单一真值边界

| 职责 | 当前真值位置 |
|---|---|
| 运行时结构化帮助 | `frontend/src/config/helpContent.js`、`frontend/src/config/help/` |
| 帮助中心页面 | `frontend/src/views/admin/help/AdminHelpView.vue` |
| 产品入口 | `/admin/help` |
| 可视化业务图 | `frontend/public/help/` |
| 治理、规范、审计和证据 | `docs/help/` |

详细理由见 [ADR-001](architecture/ADR-001-runtime-content-source.md)。

## 核心文件

- [二次审计报告](AUDIT_REPORT.md)
- [建设方案](HELP_CENTER_PLAN.md)
- [P0 覆盖矩阵](COVERAGE_MATRIX.md)
- [写作与截图规范](STYLE_GUIDE.md)
- [内容完成定义](maintenance/definition-of-done.md)
- [发布复核清单](maintenance/content-review-checklist.md)
- [可视化资产清单](assets/inventory.yml)
- [目录元数据](catalog.yml)

## 当前治理草稿

- [学校首次开通配置顺序](getting-started/school-initial-setup.md)
- [如何新增一名学生](modules/student/create-student.md)
- [如何批量导入学生](modules/student/import-students.md)
- [为什么看不到菜单、按钮或学生数据](modules/system/data-permission.md)
- [如何使用手机扫码采集学生资料](mobile/student-scan-profile.md)

这些草稿进入正式运行时前必须完成真实角色点击、菜单/按钮/字段/权限/状态核验，同步到运行时真值，并通过自动校验和人工复核。

## 状态

`draft → reviewed → published → stale → archived`

## 原则

- 帮助筛选是体验功能，不是权限控制；
- 不用菜单说明代替任务闭环；
- 不用流程图代替真实操作截图；
- 不把规划能力写成已上线能力；
- 事实、部分覆盖和待核验必须明确区分。
