# 益阳岗位实习 Standalone · C07～C09 阶段收口

日期：2026-09-29  
PR：#275  
分支：`feat/internship-standalone-yiyang-v1`  
收口基线：`433d467e7b15496c03fe058e3363654a8999c21e`

## 1. 本轮结论

本轮已完成 C07～C09 中**能够仅凭仓库、MySQL 8.4、Redis 与构建环境真实验证的工程项**，并完成五个交付面的独立源码/生产构建闭环。

本文件不是“项目全部交付完成”声明。凡是必须依赖学校、监管平台、真实历史数据、真实手机、正式域名/证书或授权压测环境的项目，继续保持 `BLOCKED_EXTERNAL` / 待现场验收，禁止用 CI、模拟数据或静态代码冒充正式证据。

PR #275 继续保持 Draft，不合并。

## 2. C07 / G18 · 两套监管上报

已完成工程能力：

- RP01 / RP02 两套独立监管报表模型与版本化模板。
- 必填、枚举、跨字段校验与错误行。
- 学号、统一社会信用代码按文本写入 Excel，避免科学计数法和前导零丢失。
- 模板源文件证据：`source_file_id/source_file_name/source_file_sha256`。
- 导出文件与错误文件证据：`output_file_id/output_sha256/error_file_id/error_sha256`。
- 状态机明确区分 GENERATED / VALIDATED / EXPORTED / SUBMITTED_EXTERNAL / RECEIPT_PENDING / ACCEPTED / REJECTED。
- 未启用真实监管回执 adapter 时，服务端拒绝伪造 ACCEPTED。
- 空 MySQL 8.4 会迁移到包含文件证据字段的 `ix0023` 后再执行 G18 验收。

当前专项成功证据：

- Workflow：`Internship Standalone C07 Regulatory Reporting`
- Run：`36569116070`
- 结果：**success**

外部未完成：

- 学校/监管平台当前正式模板原件及版本确认。
- RP01 / RP02 真实目标平台导入。
- 真实平台接收/退回回执。
- 未取得上述材料前，禁止标记“监管上报成功”。

## 3. C08 · G15～G17

### G15 · 报告与评分

已完成：

- 日报 / 周报 / 月报 / 总结最低字数按正式规则来源控制。
- 学生端图片 / 视频附件。
- 版本化报告快照。
- 通过时强制五级评价。
- 实习总结强制 0～100 分。
- 退回可不评分，但绑定当前不可变报告版本。
- 修复学生日报错误读取 `weeklyMinWords`，改为读取独立 `dailyMinWords`。
- 学生与教师微信页面均已有正式操作入口。

专项成功证据：

- Workflow：`Internship Standalone C08 G15 Report Quality`
- Run：`36563140357`
- 结果：**success**

### G16 · 通知与教师本人业务

已完成：

- 教师本人签到与学生签到事实彻底分表。
- 教师本人工作日报、周报、月报、总结。
- 教师补签事实。
- 紧急通知持久化、范围、接收人数与审计。
- 接收人数按真实实习学生集合去重，不用分页数或伪造 scalar。
- 学生/教师移动端入口和微信构建。

专项成功证据：

- Workflow：`Internship Standalone C08 G16 Teacher Activity`
- Run：`36562903398`
- 结果：**success**

### G17 · 正式打印表单 / 正式文书

已完成：

- 企业实习鉴定表。
- 实习证明。
- 实习考核成绩表。
- 实习总结正式报告。
- PDF 由已审核/已发布正式事实生成。
- 源数据快照和 SHA-256。
- 源事实变化生成新版本，历史 PDF 不覆盖。
- 管理员 PC 增加“正式文书”正式路由和导航入口。
- 修复 Standalone 管理端跨母体 Dashboard/Auth 公共目录依赖。
- Standalone 管理端 route closure、import closure、production build 均通过。

专项成功证据：

- Workflow：`Internship Standalone C08 G17 Formal Documents`
- Run：`36564028452`
- 结果：**success**

## 4. 企业协同端最终收口

本轮修复：

- 企业端依赖审计测试改为从仓库根目录读取真实 workflow。
- 评价任务的分页/服务端筛选测试同步当前扫码 deep-link 合同，不回退 `internshipId` 定向评价。
- 后端企业路由验收改为检查真实 FastAPI OpenAPI 表面，而不是 FastAPI 0.141 内部 `_IncludedRouter` 对象。
- 企业端保持独立 `/enterprise/` base。
- 企业路由仍独立于 staff dependency bundle。
- 企业前端合同测试 + production build 通过。

专项成功证据：

- Workflow：`Internship Standalone C08 Enterprise Surface`
- Run：`36568907310`
- 结果：**success**

## 5. C09 / G19 · 历史迁移

已完成工程能力：

- `g19_migration_bridge.py` 只允许 MySQL → MySQL。
- 只迁移 Standalone 冻结清单内的表。
- `tenant_id` 与主键原样保留，不静默 remap。
- 默认拒绝向非空目标租户覆盖。
- 逐表源/目标行数对账。
- 关键业务链逻辑孤儿检查。
- 文件元数据对账。
- 本地文件真实字节 size + SHA-256 核验。
- COS/外部对象存储若没有真实字节复制证据，输出 BLOCKED，不把元数据迁移冒充文件迁移。
- 新增逐表内容 SHA-256 指纹，避免“行数一样但字段内容已损坏”仍然绿灯。

真实 MySQL 8.4 演练：

```text
source MySQL 8.4
→ alembic head
→ tenant_id=777 + 学院 + 学生主档
→ G19 copy
→ G19 verify
→ 行数一致
→ 逻辑孤儿=0
→ 内容指纹一致
→ tenant_id=777 原样保留
```

专项成功证据：

- Workflow：`Internship Standalone C09 G19 G20 Tooling`
- 真实源库→目标库迁移演练首次成功 Run：`36567554798`
- 当前收口基线 Run：`36569116083`
- 结果：**success**

外部未完成：

- 真实学校原 SaaS 全量历史库迁移。
- 真实学校全部历史附件字节迁移。
- 真实 COS 对象逐文件 SHA/ETag/字节核验。
- 以上必须拿真实源库/文件后执行，当前 CI 演练不得冒充 G19 学校正式验收。

## 6. C09 / G20 · 5000+ 性能与交付

已完成工程能力：

- k6 正式压测 harness。
- 正式运行至少 5000 VU。
- 必须显式 `G20_REAL_RUN_ACK=YES`，避免误打生产。
- 已锁定真实只读核心接口：看板、采购统计、过程统计、风险列表。
- p95 / p99 / 错误率阈值证据。
- `g20-k6-summary.json` 原始证据。
- 独立 `g20_validate_evidence.py` 最终判定。
- 低于 5000 VU 只能判 `SMOKE_ONLY`。
- 5000 条演示数据不能冒充 5000 并发。
- 正式 G20 新增强制测试身份池：`authIdentityCount >= requestedVus`。
- 5000 VU 正式验收要求至少 5000 个不同授权测试身份；共享单 token 判 `FAIL_IDENTITY_POOL`。
- token 仅从安全文件加载，不写入证据、不提交 Git。

当前门禁仅证明：工具、证据格式、防假验收逻辑、生产运行环境可用。

外部未完成：

- 已授权的正式 UAT / 同规格性能环境。
- 5000 个不同测试身份。
- 正式 5000 VU 原始 k6 运行。
- 学校/采购 SLA 对应的最终阈值。
- 因此当前 **不得宣称 G20 正式通过**。

## 7. Standalone 生产运行与五端独立构建

生产运行门禁已通过：

```text
空 MySQL 8.4
→ alembic upgrade head
→ ix0023
→ Redis READY
→ 文件目录可写
→ FastAPI 独立启动
→ /health/ready = READY
```

同时修复 Standalone 后端完整 import 闭包：

- 补入浏览器认证 session blocklist。
- 补入岗位实习实际需要的 message center service。
- 不删除企业协同、消息、认证功能来换取绿灯。

最终五端构建：

1. 管理员 / 教师 PC：success
2. 学生 PC（`/student/`）：success
3. 学生移动端：微信包 success
4. 教师移动端：同一独立微信包源码闭包 success
5. 企业协同端（`/enterprise/`）：合同测试 + production build success
6. Standalone backend import：success

最终汇总证据：

- Workflow：`Internship Standalone Five Surface Final Build`
- Run：`36569100296`
- 结果：**success**

这里的 success 是“源码闭包 + production build / backend import”证据，不冒充：

- 浏览器真实账号逐页 UAT；
- 微信开发者工具验收；
- Android / iOS 真机验收；
- 学校正式域名 / HTTPS / CAS / 门户联调。

## 8. 当前禁止误报的事项

截至本收口基线，以下仍不能写“全部完成”：

- G18 两监管平台真实导入与回执。
- G19 真实学校全量历史库 + 全附件迁移。
- G20 正式 5000 VU / 5000 测试身份压测。
- 腾讯云正式服务器、正式域名、正式 HTTPS 证书部署验收。
- 学校真实 CAS / 门户 / 消息 / 数据平台 UAT。
- 微信开发者工具与 Android/iOS 真机。
- 浏览器五端真实账号主链 G01～G20 最终证据。
- 正式备份→隔离恢复执行证据。
- 校方 15 日试运行、培训、售后与最终签字。

## 9. 下一施工顺序

继续从本基线向前，不回退 C02～C08：

```text
备份 + 附件隔离恢复真演练
→ G01～G18 浏览器/接口总验收编排
→ 接真实学校历史数据执行 G19
→ 正式 UAT 环境执行 G20
→ 微信开发者工具 / 真机
→ 学校外部联调
→ 最终交付证据包
```

在真实外部证据补齐前，PR #275 保持 Draft。
