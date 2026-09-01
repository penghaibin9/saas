# X1 XLSX、审计、统计与权限 Gate 验收证据

- 阶段提交：`f51fecb79`（`feat(platform): close xlsx audit and stats gates`）
- Alembic revision：`20260901_school_xlsx_x1`
- 上游：`20260901_orientation_checkin_o5`
- 验收日期：2026-09-01（Asia/Shanghai）

## XLSX 与导出

- 宿舍导入提供模板下载、上传、dry-run、逐行错误工作簿和原子确认，复用 `SharedImportBatch`，确认失败整批回滚。
- 迎新导入补齐错误工作簿，错误定位保持到源行和字段。
- 迎新 9 类、宿舍 9 类生产报表使用锁定文件名、用途、操作者、数据范围、水印与脱敏规则；导出任务和审计日志均在服务端生成。
- 管理 PC 已接入宿舍导入/导出/统计与迎新导出，不由浏览器聚合统计或伪造文件。

## 权限、统计与一致性审计

- 权限目录新增并激活租户级 `studentAffairs.dorm.export`，迁移同时同步系统角色模板的规范化权限行、摘要和 permission ceiling。
- `SCHOOL_ADMIN`、`STUDENT_AFFAIRS`、`STUDENT_AFFAIRS_ADMIN`、`DORM_MANAGER` 获得与职责相符的宿舍导出能力。
- 统计只读取 canonical 报到、缴费与宿舍事实；床位口径严格区分总床位、已入住、空床和锁定。
- `scripts/audit_school_authority_consistency.py` 为只读 Gate，不 flush/commit；最终在隔离 MySQL 租户上输出 `issueCount: 0`。

## 验证

- X1 目标后端用例覆盖模板、dry-run、错误工作簿、原子确认、18 类报表、权限、脱敏、水印、导出审计和统计口径。
- Alembic fresh upgrade、X1 → O5 → X1 往返、single-head 均通过。
- 最终统一后端相关套件：`67 passed`。
- 管理 PC lint、合同测试和 production build 均通过。

## 判定

X1 的生产 XLSX 闭环、18 类报表、权限同步、canonical 统计和只读一致性审计均达到发布 Gate。
