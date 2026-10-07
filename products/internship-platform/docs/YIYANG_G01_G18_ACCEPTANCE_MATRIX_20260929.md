# 益阳岗位实习 Standalone · G01～G18 连续验收矩阵

日期：2026-09-29  
PR：#275  
分支：`feat/internship-standalone-yiyang-v1`

> 口径：本表只记录已经存在的可复验证据。  
> `PASS_ENGINEERING` 表示仓库内业务/数据库/构建验收已通过；  
> `BLOCKED_EXTERNAL` 表示必须由学校、监管平台、授权第三方数据源或真机现场才能关闭。  
> 禁止把静态代码、模拟工商数据、导出成功或演示数据写成外部正式验收通过。

| Gate | 招标验收点 | 当前状态 | 已验证内容 | 证据 |
|---|---|---|---|---|
| G01 | 多校、多院系、多计划 | PASS_ENGINEERING | tenant 隔离、同校多学院企业范围、跨校本地 ID 可复用、一学生多正式计划、重复计划约束、scope fail-closed | `Internship Standalone G01 G04 Core Acceptance` / Run `36572889815` |
| G02 | 完整岗位填报 | PASS_ENGINEERING | 企业/岗位/地址/联系人/日期/方式/对口/薪资/协议等完整字段保存→提交→审核→主记录回写；真实 FileObject + FileBinding；非法信用代码/日期顺序拦截 | 同 Run `36572889815` |
| G03 | 企业登记联想 | PASS_ENGINEERING + BLOCKED_EXTERNAL | 校内企业库按企业名称/信用代码搜索；脏企业名/信用代码拦截；学生自报 VERIFIED 无法伪造核验；企业身份改变强制回 UNVERIFIED | 同 Run `36572889815`；真实工商/企业登记数据源仍待授权接入 |
| G04 | 单位变更顺序 | PASS_ENGINEERING | 变更审批单事务、目标岗位强制、旧岗位释放→新岗位占用、主记录版本冻结、变更后重新到岗、旧合规/协议失效合同 | 同 Run `36572889815` |
| G05 | 照片水印与绑定 | PASS_ENGINEERING | 现场照片、服务端时间/地点水印、附件与签到事实绑定 | `Internship Standalone C02 Checkin` / Run `36346024120` |
| G06 | 定位异常与隐私 | PASS_ENGINEERING | 定位异常、精度/异常事实、按操作采集而非后台持续定位 | 同 Run `36346024120` |
| G07 | 境外签到 | PASS_ENGINEERING | 境外/无国内行政区场景仍可形成签到事实，不以国内地区字段错误阻断 | 同 Run `36346024120` |
| G08 | 完整日历 / 补卡 / 免签 | PASS_ENGINEERING | 打卡日历、补卡、免签、异常和审批链 | 同 Run `36346024120` |
| G09 | 自定义材料 | PASS_ENGINEERING | 管理员配置材料项、学生提交、版本/附件、审核与归档 | `Internship Standalone C03 Materials` / Run `36347120823` |
| G10 | 分页统计真值 | PASS_ENGINEERING | 统计由服务端全范围事实计算，不以当前 20 行分页冒充全量；分页下钻 | `Internship Standalone G10 Statistics` / Run `36363598687` |
| G11 | 受控重置密码 | PASS_ENGINEERING | 指导教师只可重置本人指导学生；同学院非本人、跨校均拒绝 | `Internship Standalone G11 IAM` / Run `36363459232` |
| G12 | 轮岗全过程 | PASS_ENGINEERING | 轮岗事实表、开始/结束/当前岗位与过程链、移动端闭环 | `Internship Standalone C05 Process Facts` / Run `36364204300` |
| G13 | 月度工资单 | PASS_ENGINEERING | 工资主单/版本事实、月度记录、移动端读取/闭环 | 同 Run `36364204300` |
| G14 | 指标口径 | PASS_ENGINEERING | `matchRate` 不冒充专业对口率；独立 `majorMatchRate` 只认正式已审核事实；校级统计对账 | `Internship Standalone G14 Statistics Truth` / Run `36364519253` |
| G15 | 报告与评分 | PASS_ENGINEERING | 日/周/月/总结规则、附件、版本、五级评价、总结百分制；修复日报最低字数来源 | `Internship Standalone C08 G15 Report Quality` / Run `36563140357` |
| G16 | 通知与教师本人业务 | PASS_ENGINEERING | 教师本人签到/日报周报月报总结/补签；紧急通知持久化、范围、去重收件人数、审计；微信 build | `Internship Standalone C08 G16 Teacher Activity` / Run `36562903398` |
| G17 | 正式打印表单 | PASS_ENGINEERING | 鉴定表、实习证明、考核成绩表、总结正式报告 PDF；源快照/SHA/版本；管理 PC 正式入口；production build | `Internship Standalone C08 G17 Formal Documents` / Run `36564028452` |
| G18 | 两平台导出 / 导入 | PASS_ENGINEERING + BLOCKED_EXTERNAL | RP01/RP02 两套独立模板、校验、Excel 文本格式、模板/输出/错误文件 SHA 证据、状态机、拒绝伪造回执、MySQL `ix0023` | `Internship Standalone C07 Regulatory Reporting` / Run `36569116070`；真实监管模板/导入/回执仍待现场 |

## 一、连续性结论

G01～G18 已不再存在“完全没有专项证据”的空档。

其中：

- **G01、G02、G04、G05～G17**：仓库工程验收已有通过证据。
- **G03**：内部企业库联想与真实性防伪已通过；真实企业登记/工商查询仍为 `BLOCKED_EXTERNAL`。
- **G18**：两套上报文件生成、校验、证据链已通过；真实监管平台导入/回执仍为 `BLOCKED_EXTERNAL`。

因此当前允许表述：

> G01～G18 的仓库内生产级能力已形成连续验收证据；涉及授权企业登记数据源和监管平台真实回执的外部部分尚待现场关闭。

当前禁止表述：

> G01～G18 已全部由学校/监管平台正式验收通过。

## 二、G19～G20 衔接状态

- G19：MySQL 8.4 源库→目标 Standalone 已做真实迁移演练，保留 tenant_id，数量/孤儿/内容指纹一致；学校正式历史库与全部历史附件仍待真实源。
- G20：正式 k6 harness 与证据验证器已完成；5000 VU 必须至少 5000 个不同授权测试身份；未在正式 UAT 环境执行前不得写“5000 并发通过”。
- C09 灾备：MySQL + 本地附件同一 backup-set → 隔离恢复 → Alembic/表数/附件 size+SHA 已真实执行成功，Run `36570679259`。

## 三、当前 HEAD 聚合回归

为避免只引用历史专项绿灯，已新增并执行：

`Internship Standalone G01 G18 Current Head Acceptance`

Run：`36578706708`，结果：**success**。

同一张卡完成：

- 空 MySQL 8.4 → Alembic `head=ix0023`；
- G01～G04 核心权限与业务流；
- G05～G09 签到、自定义材料与归档；
- G10～G14 申请统计、IAM、轮岗、薪资与统计；
- G15～G18 报告评分、教师本人业务、正式文书与监管报表。

聚合回归只证明**当前仓库工程合同**没有把 G01～G18 已完成能力回归掉；G03 外部登记源和 G18 监管真实导入/回执仍保持 `BLOCKED_EXTERNAL`。

## 三、PC 浏览器证据

已完成 Standalone 三类 PC 浏览器证据：

- 管理/教师 PC：登录页 → Standalone 岗位实习工作台，Run `36576971195`，**success**。
- 学生 PC：登录页 → 独立学生岗位实习页，Run `36576971195`，**success**。
- 企业 Portal：招聘季登录/刷新、企业首页、企业资料、岗位、报名学生、冻结档案 PDF、招聘授权失效后的实习协同降级、实习学生、评价任务，Run `36577104582`，**success**。
- 三类浏览器任务均上传 Chromium screenshot / trace 证据。

补充真实后端证据：

- `Internship Standalone Browser Auth` / Run `36580751862`：真实 MySQL 8.4 + Redis 下，Staff/Student 浏览器登录、HttpOnly refresh、`/auth/me`、Standalone RBAC、学生 Portal 配置、`/portal/internship/my`、staff 业务接口与学生越权 403 均通过。
- `Internship Standalone Fullstack PC Browser` / Run `36581139541`：**无 API mock**，真实 MySQL 8.4 + Redis + FastAPI + Vite + Chromium，学校管理员 PC 与学生 PC 完整登录并进入岗位实习页面，真实命中 RBAC、批次、看板、portal-config、internship-my。
- `Internship Standalone Fullstack PC Browser` / Run `36581895278`：在同一真实栈追加 `INTERN_MENTOR` 指导教师账号；教师可读取批次与工作台，但不拥有 `internship.batch.manage`，管理员/教师/学生三类 PC 真实后端浏览器旅程全部成功。

因此 PC 端当前允许表述：

> 管理员 PC、指导教师 PC、学生 PC 已完成真实 MySQL/FastAPI/Chromium 工程级端到端验收；企业 Portal 也已完成真实 MySQL/FastAPI/Chromium 工程级全栈验收。

企业 Portal 真后端证据进一步包括：

- `Internship Standalone Fullstack Enterprise Browser` / Run `36587566385`：真实企业账号登录、招聘季、企业首页/资料、真实岗位列表，**success**。
- Run `36588732900`：在同一真实栈继续打通 `INTERNSHIP_COLLAB` 授权、实习学生、待评价任务，**success**。
- Run `36589268583`：企业 HR 在 Chromium 中真实填写五项评分和总体评价并提交；随后 MySQL 回查 `t_internship_enterprise_eval` 的学生/批次/企业/岗位/PlacementSnapshot、五项分数、`ENTERPRISE_ONLINE` 来源、`SUBMITTED/PENDING` 状态，并回查 `ENTERPRISE_ONLINE_SUBMIT` 审计，全部通过，**success**。
- 上述企业全栈链不使用 API route mock。

仍不能把上述 CI/UAT 同规格证据表述为“校方正式数据已签字验收”。

## 四、下一道验收门

接下来不再横向新增 G01～G18 功能，优先补“真实后端/现场方式证据”：

1. ~~企业 Portal 真实 MySQL/FastAPI 浏览器账号链；~~ 已完成工程级全栈验收；
2. 学生/教师微信开发者工具与真机；
3. 外部企业登记、监管平台、学校统一认证/门户；
4. 正式 G19 / G20 / 15 日试运行与最终签字。

PR #275 在上述现场项关闭前继续保持 Draft。
