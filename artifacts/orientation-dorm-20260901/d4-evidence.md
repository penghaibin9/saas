# D4 调宿 / 退宿 / 住宿历史 Authority 证据

- 阶段：D4
- 进入阶段 HEAD：`649e3800200f5446f6a03c146d985ab42399a3c5`
- 分支：`codex/orientation-dorm-20260901`
- Alembic revision：`20260901_dorm_checkout_d4`
- parent：`20260901_orientation_self_o3`
- Fresh MySQL：本机隔离 MySQL 8.0.46，`saas_d4_fresh_local`
- 阶段结束前 `origin/main`：`de4d07d9053e902e7f4a9de18d30117a09f196db`，divergence 为 `8 11`

## Authority 与阶段边界

- `DormStay` 是住宿历史 Authority；`DormBed.student_id` 仅为当前占用指针，不再承担历史语义。
- 入住、正式调宿、正式退宿都委托同一 canonical stay service，旧入口不能绕过住宿历史写入。
- 正式退宿拆分为“发起退宿单”和“宿管确认”：确认前床位、当前住宿关系和 `CsDormRecord` 均保持不变。
- 确认退宿在同一事务中结束 `DormStay`、释放 `DormBed`、关闭 `CsDormRecord` 投影、追加学生阶段事件并写消息 outbox。
- 调宿处理中会阻断退宿确认；阻断单保持可重试，CAS 与客户端请求号防止重复确认和错误覆盖。
- 退宿来源预留 `MANUAL/GRADUATION_BATCH` 和稳定 `source_biz_id`，D4 不提前实现毕业批退编排。
- `TENANT_ALL / DORM_BUILDING / CLASS / COLLEGE` 数据范围均在服务端执行；界面筛选不是授权边界。

## Schema 与迁移

- `t_affairs_dorm_stay` 增加状态与生命周期 CHECK，约束 ACTIVE/RESERVED 无退宿时间、ENDED 必有退宿时间。
- 新增 `t_affairs_dorm_checkout_request`，包含稳定 stay/bed/building/room 引用、请求类型、来源、客户端幂等号、阻断项、确认/取消操作者和时间。
- MySQL 非事务 DDL 前置校验会拒绝未知住宿状态、床位/住宿关系不一致、重复 active stay、来源键冲突和目标表碰撞。
- 从 O3 exact current 升级 D4、D4 downgrade 回 O3、再 upgrade D4：均通过。
- 负向 preflight：注入 `occupied_without_stay=1` 后迁移在 DDL 前失败，退宿表计数保持 0。
- downgrade 在存在 D4 正式退宿数据时明确阻断，避免静默丢失运行数据。
- D4 目标模型 `DormStay + DormCheckoutRequest` 的 programmatic `compare_metadata` 差异为 0；全仓历史 drift 仍按进入阶段前事实记录，未伪称全仓清零。
- 最终仓库与 Fresh DB 均为唯一 `20260901_dorm_checkout_d4 (head)`。

## 四端交付

- 教师 PC 入住页发起正式退宿单；调宿/退宿页展示待确认、阻断项和住宿历史，并由宿管执行确认或取消。
- 学生 PC “我的宿舍”展示 canonical 住宿历史，状态显式本地化为“待入住 / 当前在住 / 已退宿 / 已取消”。
- 学生小程序读取同一住宿历史 API，并使用相同状态语义；没有另建移动端历史表或业务规则。
- 移动端 `/mobile/affairs/dorm/stays/my` 与学生 PC `/my/dorm/stays` 均委托 canonical service。
- 消息事件使用 `DORM.CHECKOUT.CONFIRMED`；未启用调度器时 outbox 明确保持 PENDING，不伪造已投递。

## 浏览器 REAL 验收与体验修正

- 使用真实 Chromium、真实后端、真实学生/教师登录、本机 MySQL；`mock_login=false`。
- 教师 PC 通过页面完成入住，床位变为 OCCUPIED，住宿历史新增 ACTIVE。
- 教师发起退宿后，待确认数量为 1，床位仍占用；宿管确认后待确认归零，住宿历史变为 ENDED，床位释放。
- 验收中发现退宿和调宿使用原生 `window.confirm`，会显示 `127.0.0.1` 浏览器弹窗；已删除两处原生确认，统一改为站内 `AppConfirmDialog`。
- 站内退宿对话框明确展示学生、床位和“关闭住宿历史并立即释放床位”的影响，主按钮为“确认退宿并释放床位”。
- 修正后再次通过真实页面完成“入住 → 发起退宿 → 站内确认 → 已退宿”，源文件及合同测试同时断言不存在 `window.confirm`。
- 学生 PC 真实登录后读取两条 successive stay 历史，页面均显示“已退宿”，不再回退为“状态待确认”。
- 本轮创建的浏览器标签已全部关闭。

## 数据库终态探针

真实浏览器完成两轮连续入住/退宿后：

- `DormStay`：2 条，均为 `ENDED` 且 `checkout_at` 非空；
- `DormCheckoutRequest`：2 条，均为 `CONFIRMED`，`blockers_json=[]`；
- `DormBed`：`VACANT`、`student_id=NULL`、`occupied_at=NULL`、`cs_dorm_record_id=NULL`；
- `CsDormRecord`：2 条，均为 `OUT / INACTIVE`；
- `StudentStageEvent`：2 条 `DORM_CHECKOUT_CONFIRMED`；
- `MessageEventOutbox`：2 条 `DORM.CHECKOUT.CONFIRMED / PENDING`，与关闭调度器的验收配置一致。

## 自动化测试与构建

- 后端 D4 目标回归：`6 passed`，234.39s。
- 后端最终全流程：`1 passed`，340.66s；覆盖调宿阻断、阻断确认 409、驳回调宿、确认退宿、重复确认冲突、床位释放、DormStay 结束和 `CsDormRecord OUT`。
- 教师 PC D4 合同及关联合同：`19/19 passed`；最终 D4 UX 合同 `2/2 passed`。
- 教师 PC production build 与官方 21 路由预渲染通过（最终 UX 代码 28.75s）。
- 学生 PC production build 通过（2.58s）。
- 微信小程序 release build 通过：主包 484.0 KiB、学生分包 699.4 KiB、教师分包 799.0 KiB、总包 1.94 MiB、`budgetPass=true`。
- `py_compile`、迁移静态合同、`git diff --check`：通过。

## 负向用例

| 用例 | 结果 |
|---|---|
| 调宿审批处理中确认退宿 | 409，退宿单标记 BLOCKED，原床保持不变 |
| 旧版本号或已确认退宿单重复确认 | 409，拒绝重复释放床位 |
| 客户端请求号复用但请求参数改变 | 幂等冲突，拒绝覆盖原单 |
| 床位占用但无 canonical active stay | 迁移 DDL 前失败 |
| DormStay 未知状态或生命周期时间不一致 | 迁移/数据库 CHECK 拒绝 |
| 无宿舍楼/班级/学院数据范围访问 | 服务端 fail-closed |
| 退宿消息调度器关闭 | outbox 保持 PENDING，不显示虚假“已送达” |

## REAL / DISABLED / NOT_APPLICABLE

| 能力面 | 状态 | D4 证据 |
|---|---|---|
| DormStay 住宿历史 Authority | REAL | 入住、调宿、退宿统一写入；自动化与浏览器终态均实测 |
| 正式退宿单与宿管确认 | REAL | 确认前不释放、确认后事务内释放，CAS/幂等/阻断均实测 |
| 教师 PC | REAL | 真实登录完成入住、退宿发起和站内确认 |
| 学生 PC | REAL | 真实登录读取两条已退宿历史，状态文案已核验 |
| 学生/教师小程序 D4 入口 | REAL | 真实 API 契约、全量 release 构建和包预算通过 |
| 退宿站内消息事件 | REAL | 真实 outbox 与阶段事件落库 |
| 外部短信/微信实际下发 | DISABLED | 本阶段关闭调度器/provider，只承诺可信 outbox，不伪造送达 |
| 毕业批量退宿编排 | NOT_APPLICABLE | 仅预留来源键，正式编排属于毕业阶段消费者 |
| 门禁/归寝 provider | NOT_APPLICABLE | 属于 D6；D4 不生成伪 IoT 数据 |
