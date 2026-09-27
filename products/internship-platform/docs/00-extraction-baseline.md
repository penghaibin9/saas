# W0 抽离基线与边界

## 1. 冻结基线

- Repository: `penghaibin9/saas`
- Source branch: `main`
- Source SHA: `adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c`
- Standalone branch: `feat/internship-standalone-yiyang-v1`

本阶段只在 `products/internship-platform/` 下新增文件，不改原 SaaS 生产文件。

## 2. 已确认的岗位实习交付面

当前 main 的路径/文件名含 internship 的文件约 825 个。审计时识别到：

- 后端岗位实习业务域约 152 个文件；
- 管理/教师 PC 岗位实习模块约 110 个文件；
- 学生小程序岗位实习约 20 个页面文件；
- 教师小程序岗位实习约 20 个页面文件；
- 实习相关后端测试约 140 个；
- Internship 相关历史 Alembic 迁移约 54 个；
- 企业协同 Portal 为独立前端应用，应整体纳入；
- 学生 PC 另有 internship views/modules/services。

最终文件清单必须由脚本实时生成，以上数字不是后续施工的硬编码白名单。

## 3. 最小公共底座

Standalone 必须保留：

- Tenant / User / Role / UserRole / 登录与 token；
- College / Major / SchoolClass；
- StudentProfile / StudentContact / StudentAccountLink；
- 教师身份及数据范围；
- 企业主档（现有 canonical `EmpCompany`）；
- FileObject / FileAsset / FileVersion / FileBinding / ArchiveManifest；
- Excel 导入导出底座；
- Audit / Message / Todo / Outbox；
- MySQL / Redis / 文件存储。

## 4. 必须解耦的跨域

### 就业域

现有归档/统计存在 `EmpStudent` 与 `employment_runtime_service` 依赖。Standalone 不复制完整就业中心，统一改为 `EmploymentGateway`。

### 平台生命周期

现有归档存在 `app.modules.platform.document_lifecycle.fact_hooks.internship_completed`。Standalone 改为领域事件/`LifecycleGateway`，不复制平台控制域。

## 5. 不进入 Standalone 的业务域

- 教务中心
- 学工中心
- 数字迎新
- 毕业设计
- 校园服务
- 完整就业中心
- HR
- 平台控制台
- 官网/新闻
- Student360 及其他无关模块

如岗位实习源码直接 import 上述模块，必须通过适配器消除，禁止把模块整体拖入。

## 6. 数据库策略

不复制原 SaaS 54 个 internship 历史 migration 作为新安装链。

Standalone 使用：

```text
0001_internship_standalone_baseline
0002+ 后续独立演进
```

历史 SaaS → Standalone 数据迁移另做迁移桥和一致性校验，保留原 ID / 外键关系 / 文件哈希 / 审批时间。

## 7. 益阳采购缺口进入 W4

直接沿用既有 C01～C09 / G01～G20，不重新发明另一套需求：

- C01 完整岗位字段与企业真实性
- C02 照片水印/签到日历/免签
- C03 自定义收件类型与模板
- C04 教师名单/审批/全量统计
- C05 轮岗/工资/过程事实
- C06 校级统计/完整一览表
- C07 两套监管上报
- C08 普通条款完整性
- C09 真链路/迁移/性能/交付
