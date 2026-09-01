# O3 学生预报到自助与材料文件 Authority 证据

- 阶段：O3
- 进入阶段 HEAD：`d4bd6f8cf51390d548e612a5b4c7b0847947b84f`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_orientation_self_o3`
- parent：`20260901_dorm_allocation_d3`
- Fresh MySQL：MySQL 8.0 / `saas_d3_fresh`（名称沿用 D3 验收库，最终 schema 已升级到 O3）
- 阶段结束前 `origin/main`：`de4d07d9053e902e7f4a9de18d30117a09f196db`，divergence 为 `7 11`

## 上游漂移审计

- O3 开始时 `origin/main` 为 `37e077cd452e3cbbbe7612cba4316d740cf871f6`；阶段内 fetch 后前移 11 个提交。
- 逐文件审计 `37e077..origin/main`：变化集中在 V8 控制面交付、平台/系统管理、租户开通恢复、通用响应与审计，以及相应测试和前端控制面页面。
- 上游没有新增 Alembic revision，也没有修改迎新、学生 Authority、正式文件 Authority、O3 学生端路由或本阶段迁移文件。
- 因此本阶段不存在 public schema / authority 冲突；遵守总册约束，不 merge、不 rebase、不把无关控制面提交混入 O3 阶段提交。

## 阶段边界与权威切换

- 学生身份只允许通过 `StudentAccountLink → StudentProfile → OrientationStudent.student_id` 的稳定主键链解析；学号、姓名、录取号均不能作为授权依据。
- 仅允许当前租户唯一 ACTIVE 批次、已 LINKED 且 ACTIVE 的迎新学生在开放窗口内操作；链路缺失、跨租户、窗口外或已完成现场报到均 fail-closed。
- 信息采集写入学生联系方式 Authority：电话与紧急联系人电话加密保存并保存检索哈希；读模型只返回掩码，不返回明文。
- 新增 `t_orientation_arrival_plan`，按学生稳定主键唯一保存到站方式、时间、站点、车次、接站与陪同人数；更新采用 `expectedVersion` CAS，首版版本号为 1。
- 强化 `t_orientation_material`：持有 `student_id`、提交序号、当前版本标记、被替代记录、客户端幂等号、FileAsset 与 FileVersion 稳定引用。
- 正式材料上传建立 `FileObject → FileAsset → FileVersion → FileBinding` 全链；原字节不可覆盖，退回后只能新建版本并使旧提交退出 current。
- 同一 `clientSubmissionId` 仅在文件对象和业务参数完全一致时幂等返回；换文件复用幂等号返回 409 `IDEMPOTENCY_CONFLICT`。
- 教师材料列表只展示 current 提交，并通过学工 Data Scope 过滤；通过/退回同步更新正式 FileVersion 状态。
- O3 不签发报到码：`reportCode` 始终为空，`reportCodeValid=false`、`reportCodeStatus=NOT_ISSUED`，录取号不再伪装报到凭证。

## 四端交付

- 学生 PC 新增并接通 `/orientation/info`、`/orientation/arrival`、`/orientation/materials`；涵盖确认声明、日期选择、CAS、正式文件 SDK、版本历史和不可用态。
- 学生小程序新增真实 arrival/material 页面与 API；信息采集补齐紧急联系人和确认声明；首页及报到码页明确显示“尚未签发”。
- 教师 PC 沿用材料审核页面，接入 current 材料、学工 Data Scope 与正式文件版本状态同步。
- 移动端/门户的 `my`、信息采集、到站计划和材料提交全部委托同一 canonical service，没有四端各自复制业务规则。
- handoff manifest 已重新生成：142 routes，Alembic head 为 O3，包哈希同步到本阶段产物。

## Expand → Backfill → Validate → Switch → Contract

- Preflight：在 MySQL 非事务 DDL 前拒绝材料父学生缺失、跨租户父链以及旧数据未知状态；失败时不创建 O3 表/列。
- Expand：新增到站计划表并为材料表增加稳定学生、版本、幂等和正式文件引用字段。
- Backfill：按租户与迎新学生稳定父键补齐 `student_id`，使用 `ROW_NUMBER() OVER` 生成提交序号和 current 版本。
- Validate：验证租户父链、提交序号/current 唯一性、状态集合与正式文件引用一致性。
- Switch：学生四端写入口、教师 current 列表和审核均切到 O3 canonical service / authority。
- Contract：MySQL CHECK 和 UNIQUE 保证状态、版本、学生材料幂等及到站计划唯一性；downgrade 在存在 O3 运行数据时明确阻断。

## Fresh MySQL 迁移与漂移

- 从 D3 exact current 升级 O3：通过；O3 downgrade 回 D3、再 upgrade O3：通过。
- 负向 preflight 库 `saas_o3_preflight`：注入缺失父学生材料后升级以“orientation material parent is missing or cross-tenant”失败；revision 保持 D3、到站表为 0、材料 O3 列为 0。修复数据后升级通过，临时库已删除。
- 首次元数据比较发现 6 个 O3 comment/default 差异；修正 migration 后 programmatic `compare_metadata` 的 O3 目标差异为 0。
- 全仓 `alembic check` 仍包含进入本阶段前的历史 drift；O3 新增表、列、约束、索引与模型目标漂移为 0。
- 最终 `alembic heads` 与 Fresh DB `alembic current` 均为唯一 `20260901_orientation_self_o3 (head)`。
- Fresh schema 核验：到站计划表 1；材料 O3 新列 8；O3 CHECK 6；O3 UNIQUE 2。

## 自动化测试与构建

- 后端广域回归：`test_orientation.py`、`test_portal_orientation.py`、O2 authority、O3 self-service 共 `27 passed`，耗时 498.44s。
- 最终代码 O3 专项在重新创建的独立 MySQL 库执行：`2 passed, 5711 warnings in 205.83s`；覆盖学生稳定身份、信息加密、到站 CAS、正式文件链、跨学生文件拒绝、未绑定账号拒绝、材料重交、幂等冲突、教师审核与 FileVersion APPROVED 同步。
- 学生 PC 全量测试：`124/124 passed`；production build 通过（6.93s）。
- 学生端 + 教师端小程序全量测试：`243/243 passed`；微信 release build 通过，主包 483.9/520 KiB、学生分包 698.5/850 KiB、教师分包 799.0/950 KiB、总包 1.93 MiB、`budgetPass=true`。
- 教师 PC 全量测试：`735/735 passed`；production build 与官方 21 路由预渲染通过（35.20s）。
- `py_compile`、最终 O3 migration 静态断言和 `git diff --check`：通过。
- warnings 为仓库既有 `datetime.utcnow()`、SQLAlchemy/FastAPI deprecation 提示，没有测试失败或被忽略的 O3 错误。

## Chromium REAL E2E

- 使用真实 Chromium、真实后端、学生 PC、教师 PC 和 MySQL；mock login 关闭。
- 隔离租户起点只写最小 Authority：租户、用户/角色/权限、稳定 StudentProfile/StudentAccountLink、流程/步骤、ACTIVE 批次与 LINKED OrientationStudent；没有预填联系方式、到站计划或材料。
- 学生真实登录后提交手机号/生源地/紧急联系人/确认声明，页面显示“已填写”及掩码电话。
- 学生提交 2026-09-03 10:30、TRAIN、长沙南站、G100、需要接站、1 名陪同，到站页显示“已提交”。
- 学生经浏览器文件选择器上传测试文件，材料页显示“第1版 待审核”；正式 FileAsset、FileVersion 与 FileBinding 均落库。
- 教师以 `STUDENT_AFFAIRS_ADMIN` 真实登录，页面显示“数据范围：全校学工域”，且只看见当前租户该学生的一条 current 材料。
- 首次审核暴露 `FileVersion` 错误导入；修复为 `app.models.file.FileVersion` 并重启后，教师点击通过成功，学生刷新显示“第1版·已通过”。最终专项自动化测试也覆盖该修复。
- 在线字节预览未配置时，教师弹窗明确说明不可预览并仅展示文件名，没有伪造预览结果。
- 最终 HTTP/DB 探针：`O3_E2E_PROBE=PASS orientation=18 arrivalVersion=1 material=17 asset=2 fileVersion=3 binding=3 contactCount=2 conflict=409`。
- 探针同时验证两条联系人记录均非明文、asset current version、FileVersion APPROVED、binding 的 student/asset/version 稳定关联，以及换文件复用幂等号返回 409。
- 所有浏览器标签和三项服务均已关闭；隔离 E2E 库、专项测试库、临时脚本、临时浏览器文件及精确定位的物理上传文件均已删除。Fresh 验收库保留。

## 负向用例

| 用例 | 结果 |
|---|---|
| 无 StudentAccountLink 的学生账号仅携带同名/同学号声明 | 403，拒绝推测身份 |
| 另一名已绑定学生读取本学生 FileObject | 404，fail-closed |
| 到站计划用旧 `expectedVersion=0` 覆盖首版 | 409，CAS 冲突 |
| 同一客户端提交号改用不同物理文件 | 409 `IDEMPOTENCY_CONFLICT` |
| 未退回/未拒绝时直接覆盖当前材料 | 拒绝，只允许不可变版本链 |
| 迁移前存在缺失或跨租户材料父链 | DDL 前失败，schema 不半升级 |
| 存在 O3 运行数据时 downgrade | 明确阻断，防止静默丢失到站与版本数据 |
| 未配置线上文件字节预览 | 明确 DISABLED，不返回虚假预览 |

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | O3 证据 |
|---|---|---|
| 稳定学生身份与自助资格 | REAL | 仅解析 AccountLink/Profile/OrientationStudent 稳定主键链，未绑定与跨学生均 fail-closed |
| 信息采集与敏感联系方式 | REAL | 确认声明必填，联系方式加密+哈希落 Authority，跨端只返回掩码 |
| 到站计划 | REAL | 独立表、窗口校验、唯一学生行、CAS 首版/并发冲突均实测 |
| 材料不可变版本链 | REAL | FileObject→Asset→Version→Binding、current/supersedes、退回重交和严格幂等均实测 |
| 教师审核与数据范围 | REAL | STUDENT_AFFAIRS_ADMIN 全校学工域，current-only，审核同步 FileVersion 状态 |
| 学生 PC 与学生小程序 O3 页面 | REAL | 精确路由、真实 API、全量测试、构建；PC 另有 Chromium 提交验收 |
| O3 报到码签发/现场核验 | DISABLED | 明确 `NOT_ISSUED`；签名 token、核验与 finalize 留到 O5 |
| 教师线上文件字节预览 | DISABLED | 未配置预览服务时明确提示，只提供可信元数据，不伪造内容 |
| 缴费、绿色通道、Qualification 规则中心 | NOT_APPLICABLE | 属于 O4，不在 O3 提前建立第二套规则 |
| 现场报到、签名凭证与最终完成 | NOT_APPLICABLE | 属于 O5 |
| 宿舍 IoT provider | NOT_APPLICABLE | 属于 D6 |
