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

## 三、PC 浏览器证据

已完成 Standalone 三类 PC 浏览器证据：

- 管理/教师 PC：登录页 → Standalone 岗位实习工作台，Run `36576971195`，**success**。
- 学生 PC：登录页 → 独立学生岗位实习页，Run `36576971195`，**success**。
- 企业 Portal：招聘季登录/刷新、企业首页、企业资料、岗位、报名学生、冻结档案 PDF、招聘授权失效后的实习协同降级、实习学生、评价任务，Run `36577104582`，**success**。
- 三类浏览器任务均上传 Chromium screenshot / trace 证据。

边界说明：

> 当前浏览器证据使用隔离 API fixture 验证真实页面、路由、鉴权客户端状态机和交互流程；它证明 PC 前端主链可运行，但**不等于真实 MySQL 后端账号 + 学校正式数据的端到端 UAT**。

## 四、下一道验收门

接下来不再横向新增 G01～G18 功能，优先补“真实后端/现场方式证据”：

1. G01～G18 当前 HEAD MySQL 8.4 聚合回归；
2. 管理/教师 PC + 学生 PC 真实 FastAPI / MySQL 账号链；
3. 学生/教师微信开发者工具与真机；
4. 外部企业登记、监管平台、学校统一认证/门户；
5. 正式 G19 / G20 / 15 日试运行与最终签字。

PR #275 在上述现场项关闭前继续保持 Draft。
