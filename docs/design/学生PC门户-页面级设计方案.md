# 学生 PC 门户 · 可扩展 SaaS 门户设计方案 V1.0

> 版本：V1.0（由「页面级设计稿」升级为「可扩展 SaaS 门户平台设计稿」）
> 范围：六域全做（导航完整、深浅不同）　落地形态：独立门户工程 `student-portal/`　状态：设计待评审，**未写代码、未建工程、未改后端**
> 商业目标：作为《职校学生全生命周期 SaaS 平台》的学生侧 Web 工作台，可一次做全六域，并可按租户/套餐持续扩展 SaaS 功能模块——做成**可扩展、可维护、可售卖**的产品，而非一次性页面堆叠。

---

## 一、产品定位升级

**学生 PC 门户 = 学生侧的 Web 工作台。** 它不是管理端（那是 `frontend/`，给老师/管理员），也不是小程序的复制品（`miniapp/` 主打日常提醒与快速操作）。它承担三类价值：

### 价值一：小程序不适合做的「重操作」
- 大文件上传（毕设开题/中期/成果文档、就业三方/合同扫描件）
- 长文本填写（实习周报、开题报告、中期报告、就业情况说明）
- 大表格查看（成绩单、学分明细、材料清单）
- 材料下载 / 打印（在校证明、成绩证明、录取通知书归档件）
- 多步骤申请表（信息更正、资助申请、证明开具）

### 价值二：学生全过程自助
查进度、补材料、提交申请、看退回意见、下载证明——学生在门户里完成"自己能自助办的一切"，减少跑窗口、少打扰辅导员。

### 价值三：未来 SaaS 扩展入口
新功能模块（如"第二课堂学分""心理测评自助""校园卡自助""升学服务"）可按**统一菜单、路由、接口、权限、组件**接入门户，不改动既有模块——这是本 V1.0 相对旧稿最大的升级。

### 端职责边界（明确写死）
| 端 | 定位 | 学生 PC 门户与它的关系 |
|---|---|---|
| 小程序 miniapp | 日常提醒 + 快速操作（高频、碎片、随身） | 提醒和轻操作留在小程序 |
| PC 门户 student-portal | **重任务、自助办理、材料中心、证明下载、长文本表单** | 本文档主体 |
| 管理端 frontend | 老师/管理员管理 | 门户**永不**触碰 |

> 一句话：**日常提醒和快速操作看小程序；重任务、传材料、下证明、填长表单来 PC 门户。**

---

## 二、整体架构升级

保留 `student-portal/` 独立工程，但确立三条原则：**前端分开、后端复用、公共能力沉淀**。

### 2.1 三端 + 后端职责
1. `frontend/` = 老师和管理端（`/admin/*`）。
2. `miniapp/` = 老师、学生高频移动端。
3. `student-portal/` = 学生 PC 自助门户（`/portal/*`）。
4. `backend/` = 统一提供接口，三端共用。

### 2.2 复用与隔离铁律
5. `student-portal` **不直接调管理端全量接口**（禁 `/admin/*`、`/students`、`/students/{id}`、`/approvals/*` 管理视角、`/todos` 全量等）。
6. `student-portal` **不复制后端业务**：读走 `/mobile/me/*` 与 `/mobile/{domain}/my`。
7. PC 特有的上传/导出/更正/回执接口**复用现有 service**（`file_service`、`domain_export_service`、六域 service、审批链），只加"本人视图 + 轻量写"薄壳，不重造业务。

### 2.3 三端共用规则（沉淀，避免漂移）
必须由后端统一 + 前端各端遵循同一份规则：
- 统一 token 处理规则（Bearer；401 refresh；登出吊销）
- 统一错误码处理（`code`/`bizCode`：0/401001/403001/404001/409001/422001/500001）
- 统一脱敏规则（手机/身份证/薪资打码，住址不返回，违纪/心理仅摘要）
- 统一四态（loading / empty / error / 弱网兜底）
- 统一审计口径（写操作/导出/下载留痕，`bizType` 命名一致）
- 统一租户品牌配置（`tenantBrandConfig`：Logo/校名/主色/水印）

> **建议**：把脱敏、错误码、格式化、四态这几套规则抽成一份共享约定（文档或轻量内部包），三端引用同一份，防止口径漂移（见第十四章风险 1）。

### 2.4 建议目录（升级版）
```
student-portal/
  src/
    app/                      # 应用装配（入口、全局 provider、主题注入）
    router/                   # 路由装配（由 platform/routeRegistry 生成）
    stores/                   # session / ui / featureFlags
    services/
      request.js             # 统一请求：token+错误码+四态+refresh
      portalApi.js           # /mobile/me/* 与六域 /my 读封装
      uploadApi.js           # 统一文件上传/替换/撤回
      exportApi.js           # 统一导出/证明下载
      messageApi.js          # 消息/待办/回执
    modules/                 # ★业务模块（每个模块自带 config+views+api+tests）
      dashboard/  profile/  orientation/  campusService/  academic/
      internship/  graduation/  employment/  messages/
    platform/                # ★可扩展底座（新模块只在此注册，不散落）
      moduleRegistry.js      # 模块清单（module contract 汇总）
      menuRegistry.js        # 菜单生成（按套餐/权限过滤）
      routeRegistry.js       # 路由生成
      permissionGuard.js     # 登录+学生角色+套餐守卫
      featureFlags.js        # 租户/套餐开关
    components/              # 可复用能力
      StateBlock/  SensitiveText/  FileUploader/  ExportButton/  DataTable/
      Stepper/  StatusTag/  ApplicationTimeline/  MaterialList/  ProofDownload/
    utils/
      sensitive.js  format.js  validators.js
```
说明：`modules/` 放业务；`platform/` 放**扩展机制**；`components/` 放可复用能力。新增模块=在 `modules/` 加一个自洽目录 + 在 `platform/moduleRegistry` 注册，其余（菜单/路由/守卫）自动生效。

---

## 三、模块插件化与可扩展机制

**学生 PC 门户模块注册规范**：每个模块必须声明统一的 **module contract**，禁止把菜单/路由/接口硬编码散落到各处。

### 3.1 Module Contract 字段
```
{
  moduleKey        // 唯一键，如 'academic'
  moduleName       // 模块名（可被租户品牌覆盖）
  routeBase        // 路由前缀，如 '/portal/academic'
  menuTitle        // 菜单标题
  menuIcon         // 菜单图标
  order            // 菜单排序
  enabledByTenant  // 是否受租户开关控制（true）
  requiredPackage  // 需要的套餐版本，如 'lifecycle' | 'academic_pack'
  studentOnly      // 是否仅学生可见（恒 true）
  readApi          // 主读接口，如 '/mobile/academic/my'
  writeApis        // 写接口数组
  exportApis       // 导出接口数组
  uploadApis       // 上传接口数组
  pages            // 子页面清单（含 route meta / featureFlag）
  permissions      // 前端展示级权限键（学生侧较简单）
  emptyState       // 空态文案
  errorBoundary    // 错误边界文案/兜底
  auditBizType     // 审计业务类型，如 'ACADEMIC'
}
```

### 3.2 示例
**academic**
```
moduleKey: academic
routeBase: /portal/academic
readApi: /mobile/academic/my
exportApis: [ /mobile/academic/transcript/export ]
requiredPackage: academic_pack | lifecycle
auditBizType: ACADEMIC
```
**graduation**
```
moduleKey: graduation
routeBase: /portal/graduation
readApi: /mobile/graduation/my
uploadApis: [ /mobile/graduation/submit ]
requiredPackage: graduation_pack | lifecycle
auditBizType: GRADUATION
```
**employment**
```
moduleKey: employment
routeBase: /portal/employment
readApi: /mobile/employment/my
writeApis: [ /mobile/employment/report ]
uploadApis: [ /mobile/employment/material ]
requiredPackage: employment_pack | lifecycle
auditBizType: EMPLOYMENT
```

### 3.3 新增一个 SaaS 模块的标准动作（只此 6 步）
1. 写 `modules/<key>/module.config.js`（module contract）
2. 加 `modules/<key>/routes.js`（route）
3. 加 `modules/<key>/views/*`（页面）
4. 加 `modules/<key>/api.js`（接口封装，走统一 request）
5. 加 `modules/<key>/__tests__/*`（测试）
6. 在 `platform/moduleRegistry` 注册（menu/route 自动生成）

> 不允许在 `router/`、菜单组件、守卫里散落 if-else 硬编码模块。

---

## 四、租户品牌与套餐开关（多学校 SaaS 可售卖）

### 4.1 品牌来自配置，禁止硬编码
1. 学校 Logo、学校名称、平台名称、主色、水印、背景图**全部来自 `tenantBrandConfig`**（后端按租户下发）。
2. `student-portal` **不得硬编码任何学校名称/校色**。
3. 顶栏、登录页、证明水印、导出页眉均读品牌配置。

### 4.2 套餐/模块开关
4. 菜单**按租户套餐 + 模块开关**显示。
5. 不同学校可能只买其中一部分，例如：
   - 「学业 + 实习」包
   - 「毕设 + 就业」包
   - 「全生命周期」包
   - 「只读门户」包（只能查，不能办）
6. 未开通模块：**菜单不显示**；直接访问其路由 → 统一页"该模块未开通，请联系学校"。
7. `featureFlags`（按租户下发，前端守卫消费）：
```
academic.enabled
internship.enabled
graduation.enabled
employment.enabled
orientation.enabled
campusService.enabled
export.enabled          // 全局导出开关（只读门户可关）
upload.enabled          // 全局上传开关
proofDownload.enabled   // 证明下载开关
messageReceipt.enabled  // 消息回执开关
profileCorrection.enabled
```
> 意义：SaaS 分版本销售的技术前提。V1.0 必须预留开关位，即便初期默认全开。

---

## 五、统一学生自助办理中心

把旧稿散落的「档案更正 / 服务申请 / 证明开具 / 就业登记 / 材料上传」抽象为**学生自助办理中心**。所有写操作归为 4 类：

| 类 | 说明 | 举例 |
|---|---|---|
| **application 申请类** | 需审批的申请 | 服务申请、档案更正、在校证明、成绩证明 |
| **material 材料类** | 上传材料 | 实习协议、毕设文档、就业合同、迎新材料 |
| **report 填报类** | 填写/提交内容 | 实习周报、就业去向、问卷/确认 |
| **receipt 回执类** | 轻确认 | 消息已读、通知回执、退回确认 |

### 5.1 统一办理记录字段（work-item）
```
id / bizType / domain / title / status / statusText
submitTime / lastOpinion / handler
canEdit / canWithdraw / attachments[] / timeline[]
```

### 5.2 聚合接口（设计好，不要求 V1 全做）
- `GET /mobile/me/work-items` —— 全部办理记录聚合（application+material+report+receipt）
- `GET /mobile/me/submissions` —— 我的提交（report 类）
- `GET /mobile/me/materials` —— 我的材料（material 类）
- `GET /mobile/me/proofs` —— 我的证明/凭证（可下载件）

> 目标：**「我的办理」页能聚合全部记录**，学生一处看清所有在办/已办/退回事项。V1 先复用 `/mobile/me/applications`，聚合接口进二期。

---

## 六、统一文件中心

文件是学生 PC 门户的核心价值之一，必须统一，禁止各模块各造上传逻辑。

### 6.1 统一文件能力
上传 / 下载 / 预览 / 替换 / 撤回 / 版本 / 审核状态 / 退回原因 / 水印 / 用途记录。

### 6.2 统一文件字段
```
fileId / bizType / bizId / fileName / fileSize / fileExt / mimeType
uploadTime / status / statusText / reviewOpinion
downloadUrl / previewUrl / version / watermarked
```

### 6.3 文件限制（安全）
- 类型白名单（按 bizType 限定：文档类 doc/docx/pdf/zip；图片类 jpg/png；禁 exe/js/html/svg）
- 大小限制（按 bizType，如毕设 ≤50MB、扫描件 ≤10MB）
- 文件名随机化落盘
- **学生只能访问本人文件**（后端按 token 校验归属）
- 下载/打印**写记录**（谁、何时、何用途）
- 生产建议**对象存储**（非本地磁盘）+ 病毒扫描

### 6.4 统一组件
`FileUploader` / `MaterialList` / `ProofDownload` / `FilePreview` / `UploadProgress`。

> **强制**：毕设、实习、就业、迎新、证明打印**全部复用文件中心**，模块内不得重复实现上传/下载。

---

## 七、统一消息与待办中心

首页、消息中心、各模块详情**共用**同一套消息/待办机制。

### 7.1 接口
```
GET  /mobile/me/messages           // 分类消息（已有）
GET  /mobile/me/todos              // 待办（已有）
POST /mobile/me/messages/{id}/read // 标记已读（需补）
POST /mobile/me/messages/{id}/receipt // 回执（可选/二期）
```

### 7.2 消息类型
`TODO / NOTICE / RETURNED / APPROVED / REJECTED / WARNING / DEADLINE`

### 7.3 待办来源
未提交周报、毕设节点未交、就业材料退回、档案更正被退回、申请待补充、学业预警确认。

### 7.4 展示规则
- 首页只展示**最重要 5 条**（待办 + 高优消息）。
- 消息中心全量、分类（待办/通知/服务进度）。
- 各模块页只展示**与该模块相关**的消息（按 domain/bizType 过滤）。
- 顶栏展示**未读数**。

> 注：当前后端消息为"按本人 todo/业务状态轻量生成"，未来接统一消息表（receiver 精准关联）后可平滑替换（见风险 8）。

---

## 八、统一流程时间线

多模块都有状态流程，抽成统一组件 `ApplicationTimeline` / `ProgressStepper`，不允许每页各画一套。

### 8.1 适用场景
迎新流程、服务申请、实习周报、毕设节点、就业去向核验、档案更正、材料审核。

### 8.2 统一节点字段
```
stepKey / stepName / status / statusText
operator / operateTime / opinion / canAction / actionText
```

---

## 九、页面设计补强（10 页 + 扩展点）

> 每页读接口均"只看本人 + 脱敏"，不再逐页重复。每页补充：`route meta` / `moduleKey` / `featureFlag` / 空态 / 错误态 / 骨架屏 / 可扩展操作区 / 未来子页面 / 依赖组件 / 验收点。

### 9.1 登录 `/login`
- meta：`{ public:true }`；moduleKey：`-`；featureFlag：`-`
- 接口：`POST /auth/login`（或 `/auth/mock-login` 演示）
- 空/错：账号密码错 → 后端 message 直出；非学生角色 → "请用学生账号登录"
- 骨架：登录按钮 loading + 防重复
- 依赖：品牌头、SensitiveText（无）
- 验收：未登录访问 `/portal/*` 跳登录；非学生拒绝

### 9.2 首页 Dashboard `/portal/home`
- meta：`{ requiresAuth:true, studentOnly:true }`；moduleKey：`dashboard`
- 接口：`GET /mobile/me/overview` + `GET /mobile/me/todos`
- 展示：阶段卡、待办 Top5、预警、六域进度总览卡、快捷入口
- 空/错：无待办 → "暂无待办"；弱网 → 后端不可达提示
- 扩展操作区：快捷入口按套餐动态生成
- 未来子页：个性化提醒、日程订阅
- 依赖：TodoPanel、ModuleCard、StateBlock、StatusTag
- 验收：宽屏两栏；点卡片跳对应域

### 9.3 我的档案 `/portal/profile`
- moduleKey：`profile`；featureFlag：`profileCorrection.enabled`
- 接口读：`GET /mobile/me/profile`（脱敏，住址不返回）
- 写：`POST /mobile/me/profile/correction`（更正申请，application 类）
- 空/错：无档案 → "尚未建立档案，请联系辅导员"
- 扩展操作区：证照下载/打印
- 未来子页：家庭信息、紧急联系人、证照管理
- 依赖：SensitiveText、ApplicationTimeline、FileUploader
- 验收：敏感字段无明文；更正走审批时间线

### 9.4 数字迎新 `/portal/orientation`（轻量）
- moduleKey：`orientation`；featureFlag：`orientation.enabled`
- 接口：`GET /mobile/orientation/my`
- 写：无（现场/移动为主）
- 空/错：无迎新记录 → 空态
- 扩展点：`material-upload`（迎新材料补交，接文件中心）
- 依赖：ProgressStepper、StateBlock
- 验收：只读时间线；卡点清晰

### 9.5 在校服务 `/portal/campus-service`（中）
- moduleKey：`campusService`；featureFlag：`campusService.enabled`
- 接口读：`GET /mobile/campus-service/my` + `GET /mobile/me/applications`
- 写：`POST /mobile/campus-service/apply`（已有，reason≥5 否则 422）
- 扩展点：`proof-apply`（证明开具）、`proof-download`
- 空/错：无申请 → 空态；403/409/422 明确提示；弱网暂存并告知"未提交服务器"
- 依赖：ApplicationTimeline、StatusTag、FileUploader
- 验收：违纪/心理仅摘要不展示明细

### 9.6 学业过程 `/portal/academic` ★
- moduleKey：`academic`；featureFlag：`academic.enabled` + `export.enabled`
- 接口读：`GET /mobile/academic/my`
- 导出：`GET /mobile/academic/transcript/export`（成绩单/学分，脱敏+水印）
- 扩展点：`transcript` / `credit-progress` / `warning-confirm` / `proof-apply` / `proof-download`
- 空/错：无学业记录 → 空态；无预警 warnings 空数组不 500
- 依赖：DataTable（筛选/排序/导出）、ExportButton、StatusTag
- 验收：大表可用；导出带水印+记录

### 9.7 岗位实习 `/portal/internship` ★
- moduleKey：`internship`；featureFlag：`internship.enabled` + `upload.enabled`
- 接口读：`GET /mobile/internship/my`
- 写：`POST /mobile/internship/weekly`（已有，同周重复 409，正文<20→422）
- 上传：`POST /mobile/internship/material`（需补，协议等）
- 扩展点：`weekly-edit` / `weekly-history` / `material-upload` / `checkin-map-summary` / `company-evaluation`
- 空/错：未进入实习 → 空态；周报 409 明确提示
- 依赖：长文本表单、FileUploader、ProgressStepper、Timeline
- 验收：写长周报 + 传附件顺畅

### 9.8 毕业设计 `/portal/graduation` ★★
- moduleKey：`graduation`；featureFlag：`graduation.enabled` + `upload.enabled`
- 接口读：`GET /mobile/graduation/my`
- 上传：`POST /mobile/graduation/submit`（开题/中期/成果，大文件）
- 扩展点：`proposal-submit` / `midterm-submit` / `final-submit` / `plagiarism-result` / `defense-arrangement` / `archive-download`
- 空/错：未进入毕设 → 空态；超大/格式不符 → 422
- 依赖：FileUploader（大文件+进度）、ProgressStepper、MaterialList
- 验收：docx/pdf/zip 大文件上传是核心刚需，必须稳

### 9.9 就业服务 `/portal/employment` ★
- moduleKey：`employment`；featureFlag：`employment.enabled` + `upload.enabled`
- 接口读：`GET /mobile/employment/my`
- 写：`POST /mobile/employment/report`（去向/意向）
- 上传：`POST /mobile/employment/material`（三方/合同扫描件）
- 扩展点：`intention-form` / `destination-report` / `material-upload` / `job-recommendation` / `verification-result`
- 空/错：未开始就业 → 空态；核验中/退回清晰展示
- 依赖：表单分组、FileUploader、StatusTag、Timeline
- 验收：薪资脱敏；传扫描件顺畅

### 9.10 消息中心 `/portal/messages`
- moduleKey：`messages`
- 接口：`GET /mobile/me/messages`；`POST /mobile/me/messages/{id}/read`（需补）
- 扩展点：回执 `receipt`、站内搜索、按域筛选
- 空/错：无消息 → 空态
- 依赖：StateBlock、StatusTag
- 验收：分类正确；未读数与顶栏一致；仅本人消息

---

## 十、PC 门户 UI 与体验原则

清透学院蓝 + 教育科技感，克制、不花哨，有产品质感。

1. 首页一屏看清下一步。
2. 左侧导航稳定（不随页面跳动）。
3. 顶部：学校 + 学生 + 阶段 + 消息 + 退出。
4. 内容区卡片化。
5. 大表格可筛选、可排序、可导出。
6. 长表单分组（分区/分步）。
7. 上传区清晰显示**支持格式和大小**。
8. 所有提交按钮有 loading + 防重复。
9. 所有状态有清晰标签（StatusTag）。
10. 所有空态给**下一步建议**。
11. 不出现"mock/演示数据"字样。
12. 适配 **1366 宽度**（不只看 2K 屏）。
13. 大字体 / 无障碍作为后续扩展预留。

**组件建议**：PortalLayout、ModuleCard、TodoPanel、ProgressStepper、StatusTag、StateBlock、FileUploader、DataTable、ActionBar、SensitiveText、Timeline、ProofDownload。

---

## 十一、后端接口契约补强

> 通用约束：全部 `Depends(get_current_user)`；`userType==STUDENT` 否则 403；数据只本人；响应 `{code,bizCode,message,data}`；敏感字段脱敏；空数据不 500。以下为**草案**，编码前再评审定稿。

### 11.1 必做（V1 高价值域闭环）

**① POST `/mobile/me/profile/correction`** —— 档案信息更正申请
- auth：学生本人
- body：`{ field, oldValueMasked?, newValue, reason }`（field ∈ 可更正白名单：phone/emergency/address 等）
- resp：`{ id, status, message }`
- error：422（字段不可更正/newValue 非法）、404（无档案）
- audit：`PROFILE_CORRECTION`
- scope：本人；复用管理端学生更正 + 审批链
- tests：可更正字段成功、锁定字段 422、非本人 403

**② GET `/mobile/academic/transcript/export`** —— 成绩单/学分导出
- query：`{ type: 'transcript'|'credit', format: 'pdf'|'xlsx' }`
- resp：文件流 / `{ downloadUrl }`（脱敏 + 水印 + 用途留痕）
- error：403（export 未开通）、404（无学业记录）
- audit：`ACADEMIC_EXPORT`（记录用途）
- file：带水印，学生只导本人
- tests：导出成功且带水印、写导出记录、非本人 403、export.enabled=false 时 403

**③ POST `/mobile/graduation/submit`** —— 毕设文档上传
- body：`{ stage: 'PROPOSAL'|'MIDTERM'|'FINAL', fileId, note? }`（fileId 来自文件上传）
- resp：`{ id, status, message }`
- error：409（该节点已提交且不可覆盖）、422（阶段非法/文件缺失）、404（无毕设记录）
- audit：`GRADUATION_SUBMIT`
- file：doc/docx/pdf/zip ≤50MB；本人
- tests：各阶段提交成功、重复节点 409、超大/错类型 422、非本人 403

**④ POST `/mobile/internship/material`** —— 实习材料上传
- body：`{ materialType, fileId, note? }`
- resp：`{ id, status, message }`
- error：422（类型/文件非法）、404（无实习记录）
- audit：`INTERNSHIP_MATERIAL`
- file：pdf/jpg/png ≤10MB；本人
- tests：上传成功、错类型 422、非本人 403

**⑤ POST `/mobile/employment/report`** —— 就业去向/意向登记
- body：`{ destinationType, companyName?, jobTitle?, city?, intention? }`
- resp：`{ id, status, message }`
- error：422（去向类型非法/必填缺失）、404（无就业记录）
- audit：`EMPLOYMENT_REPORT`
- tests：登记成功、缺字段 422、非本人 403

**⑥ POST `/mobile/employment/material`** —— 就业材料（三方/合同扫描件）
- body：`{ materialType: 'AGREEMENT'|'CONTRACT'|..., fileId }`
- resp：`{ id, status, message }`
- error：422、404
- audit：`EMPLOYMENT_MATERIAL`
- file：pdf/jpg/png ≤10MB；本人
- tests：上传成功、错类型 422、非本人 403

**⑦ POST `/mobile/me/messages/{id}/read`** —— 消息已读
- resp：`{ id, status:'READ' }`
- error：404（消息不存在或非本人）
- audit：`MESSAGE_READ`（可轻量）
- tests：本人已读成功、他人消息 404

### 11.2 可选 / 二期
- `GET /mobile/me/work-items` —— 办理记录聚合（application+material+report+receipt）
- `GET /mobile/me/materials` —— 我的材料聚合
- `GET /mobile/me/proofs` —— 我的可下载证明/凭证
- `POST /mobile/me/messages/{id}/receipt` —— 通知回执
- `POST /mobile/campus-service/proof/apply` —— 证明开具申请
- `GET /mobile/campus-service/proof/{id}/download` —— 证明下载（水印+记录）

---

## 十二、测试与验收补强（5 类）

### 1) 后端测试
学生只能本人；非学生进任一 `/mobile/me/*`、写接口 → 403；上传格式白名单；上传大小限制；重复提交 409（周报/毕设节点）；导出带水印 + 写记录；空数据不 500；错误码 403/404/409/422 正确。

### 2) student-portal 前端测试
`npm run lint`、`npm run build` 通过；路由守卫（未登录跳登录、非学生拒绝、未开通模块提示）；API 封装（token 注入、错误码解析、四态）；空态/错误态；FileUploader 组件（格式/大小/进度/失败）；ExportButton（loading/防重复）。

### 3) E2E 冒烟
登录 → 首页 → 学业导出 → 实习周报 → 毕设上传 → 就业材料 → 消息已读，全链跑通。

### 4) 跨端一致性
- 小程序提交后，PC 门户能看到；
- PC 提交后，小程序能看到状态；
- 老师管理端处理后，学生 PC + 小程序同步变化（同一后端数据源）。

### 5) 构建部署
`student-portal build`、`backend pytest`、`frontend build`、`miniapp build:h5`、`miniapp build:mp-weixin` 全绿。

---

## 十三、分期策略（工程分阶段提交，便于回滚）

即便 AI 连续开发，**Git 提交必须分阶段**：

| 阶段 | 内容 | 交付 |
|---|---|---|
| **P0** | 文档冻结 + 接口契约定稿 | 本文档 + 7 接口契约 |
| **P1** | `student-portal` 工程初始化 + 公共底座（request/守卫/布局/platform 注册机制/组件骨架/lint） | 空跑可登录 |
| **P2** | 只读六域页面接入（复用 `/mobile/*`） | 六域可查 |
| **P3** | PC 特有写/上传/导出接口（后端 7 接口 + 前端封装） | 接口就绪 |
| **P4** | 高价值域完整闭环：学业/实习/毕设/就业 | 4 域可办 |
| **P5** | 轻量域补齐：迎新/在校服务/档案/消息 | 六域齐 |
| **P6** | 跨端一致性 + 全量测试 | 测试绿 |
| **P7** | 上线部署准备（构建/nginx/对象存储/备份） | 可部署 |

---

## 十四、风险与取舍补强

> 每条：风险说明 / 影响 / 规避方案 / 是否阻断 P1。

1. **三端规则漂移**：脱敏、错误码、四态三端各写一份，口径易漂。影响：合规与体验不一致。规避：抽共享约定（文档或内部包），三端引用同一份。阻断 P1？**否**（但 P1 需先定规则文件）。
2. **新工程维护成本**：独立 `student-portal` = 第三套前端。影响：组件/请求层重复维护。规避：共享组件规范 + 复制统一 utils；控制模块粒度。阻断 P1？否。
3. **文件容量/对象存储**：大文件本地磁盘扛不住。影响：磁盘爆、无法横向扩展。规避：生产接对象存储 + 大小/类型限制 + 扫描。阻断 P1？否（P1 用本地占位，P7 换对象存储）。
4. **自助导出数据外泄**：学生自助导出成绩/证明。影响：批量导出=泄露口子。规避：水印 + 用途必填 + 审计 + 频率限制。阻断 P1？否（P3 接导出时落地）。
5. **门户与小程序状态不同步**：同一学生两端展示不一致。影响：学生困惑。规避：同一后端数据源 + 拉取即最新 + 不本地长缓存业务数据。阻断 P1？否（P6 专项验证）。
6. **老师处理后学生端不同步**：管理端审批后学生消息/状态未更新。影响：学生看不到退回/通过。规避：状态由后端计算，学生端每次拉取；消息由业务状态生成。阻断 P1？否（P6 验证）。
7. **套餐开关缺失导致卖版本难**：无 featureFlags 就无法分版本售卖。影响：商业化受阻。规避：**P1 就预留 featureFlags + 菜单过滤机制**（默认全开）。阻断 P1？**是**（必须 P1 预留）。
8. **统一消息表缺失**：消息长期靠轻量生成。影响：消息中心能力受限、回执难。规避：先轻量生成满足 V1，二期接统一消息表平滑替换。阻断 P1？否。
9. **teacher_student_scope 影响**：对学生门户影响小（学生只看本人），但影响"老师处理→学生看到联动"的范围正确性。影响：联动边界。规避：学生侧不依赖该表；老师侧后续补。阻断 P1？否。
10. **无 module registry 导致散乱**：新增模块硬编码菜单/路由。影响：越扩越乱、不可维护。规避：**P1 就落 platform/moduleRegistry + menu/route 自动生成**。阻断 P1？**是**（可扩展性的根，必须 P1 做）。

### 十四·补 已锁定的工程约束（源自五项工程决策，作为硬性红线）

1. **套餐技术开关必须 P1 预留**：`featureFlags` + `requiredPackage` + `moduleRegistry` + `menuRegistry` + `routeGuard` 在 P1 就位（业务默认全开）。缺失将导致后续无法分版本售卖——**P1 阻断项**。
2. **storageProvider 不能写死**：文件读写一律经存储适配层（`local/cos/oss/minio`），业务 service 禁止直接 import 某家云 SDK。否则私有化交付与云版无法共用一套代码——**P1 阻断项**（适配层接口先定，实现可分期）。
3. **电子章不纳入 V1 承诺**：V1 证明仅 PDF + 水印 + 用途记录 + 审计；电子章/CA 签章为授权后增强，销售话术不得把电子章列为 V1 交付——**非阻断项**。
4. **共用账号但 session 隔离**：三端同后端账号体系与 `/auth/login`，`student-portal` 独立 `sp_token_v1`；`roleCode !== STUDENT` 一律拒入 `/portal/*`。这是防止学生误触管理端能力的硬边界——**P1 阻断项**（守卫先做）。
5. **独立工程 + shared 包是最终路线**：`student-portal` 物理隔离；三端共用能力 P2 起沉淀到 `packages/shared`（P1 先复制最小工具）。这是"隔离干净"与"规则不漂移"的平衡点，最终路线锁定，不再讨论是否合并工程——**非阻断项**（P1 复制、P2 抽包）。

---

## 十五、最终输出

### 1. 修改了哪些章节
- 标题升级为《学生 PC 门户 · 可扩展 SaaS 门户设计方案 V1.0》。
- 第一章「一句话定位」→「产品定位升级」（三类价值 + 端职责边界）。
- 第二章「技术架构」→「整体架构升级」（三端职责 + 复用铁律 + 三端共用规则 + 升级版目录含 platform/）。
- 第九章「页面级设计」→「页面设计补强」（每页加 route meta/moduleKey/featureFlag/扩展点/子页面/依赖/验收）。
- 第十一章「接口清单」→「接口契约补强」（7 个必做接口逐个契约化 + 6 个可选/二期）。
- 第十二章「验收标准」→「测试与验收补强」（5 类测试）。
- 第十三章「分期」→ 重写为 P0–P7。
- 第十四章「风险」→ 补强至 10 条，每条含影响/规避/是否阻断 P1。

### 2. 新增了哪些关键设计
- **模块插件化**：module contract + moduleRegistry（新增模块只 6 步、不散落硬编码）。
- **租户品牌与套餐开关 featureFlags**：SaaS 分版本销售的技术前提。
- **统一学生自助办理中心**：application/material/report/receipt 四类 + work-item 统一字段 + 聚合接口。
- **统一文件中心**：统一能力/字段/限制/组件，禁止各模块各造上传。
- **统一消息与待办中心**、**统一流程时间线**：跨模块复用。
- **UI 与体验 13 原则 + 组件清单**。

### 3. 已拍板的 5 个工程决策（最终定稿，不再保留疑问）

1. **套餐版本**：技术上**从 P1 起预留** `featureFlags`、`requiredPackage`、`moduleRegistry`、`menuRegistry`、`routeGuard`，支持**试点版 / 标准版 / 专业版 / 私有化版**四档。**销售初期先全开**，不做复杂拆版；前 1–3 个学校以「全生命周期试点版/标准版」销售，后续再按套餐拆分。→ 结论：技术开关必做，业务上默认全开。

2. **对象存储**：开发/本地支持 `local` 或 `MinIO`；SaaS 云版默认**腾讯云 COS**；私有化/校内网部署默认 **MinIO**。后端必须设计 **`storageProvider` 适配层**，取值 `local / cos / oss / minio`，**严禁业务 service 直接写死某一家 SDK**。文件中心（第六章）统一经适配层读写。

3. **证明打印**：V1 **只做 PDF 导出 + 学校水印 + 用途记录 + 审计**，**不做电子章 / CA 签章**。电子章作为学校正式授权后的**增强能力**，**不作为 V1 阻断项**。所有证明导出必须记录：学生、时间、用途、文件水印。

4. **登录体系**：学生门户与管理端**共用后端账号体系和 `/auth/login`，但前端 session 隔离**。`student-portal` 使用**独立 token key**（如 `sp_token_v1`）；**只有 `roleCode === STUDENT` 才能进入 `/portal/*`**；非学生账号登录后提示「请使用学生账号登录」。

5. **工程与复用**：坚持 `student-portal` **独立工程**，与 `frontend/`、`miniapp/` 物理隔离，避免学生误触管理端能力。但**允许抽 `packages/shared` 包**，沉淀三端共用能力：`errorCodes`、`sensitive`、`format`、`createRequest`、`StateBlock`、`SensitiveText`、`StatusTag`、`FileUploader` 等。**P1 先复制最小公共工具**，**P2 起抽 `packages/shared`**，防止三端规则漂移。

### 4. 是否建议进入编码
**建议先冻结本文档 + 定稿 7 个接口契约（P0），再进入编码。** 门户是要卖钱的产品，底座（platform 注册机制 + featureFlags + 统一文件/消息/时间线）必须先对齐，否则后期返工大。

### 5. 编码时第一阶段（P1）应做什么
`student-portal` 工程初始化 + 公共底座：request（token/错误码/四态/refresh）、permissionGuard（登录+学生角色+套餐）、PortalLayout、**platform 的 moduleRegistry/menuRegistry/routeRegistry/featureFlags（可扩展根，必须先做）**、核心组件骨架（StateBlock/SensitiveText/FileUploader/DataTable/StatusTag/Stepper）、lint 配置。**不接业务数据**，先让"空门户可登录、菜单按开关生成、路由守卫生效"。

### 6. 后续 Cursor 提交白名单（按分期，届时）
- **P0**：`docs/design/学生PC门户-页面级设计方案.md`（本文档）、`docs/api/学生门户接口契约.md`（新增契约文档）。
- **P1**：`student-portal/`（工程初始化 + 底座）——不含业务数据。
- **P2**：`student-portal/src/modules/*`（只读六域）。
- **P3**：`backend/app/api/v1/mobile.py` + `mobile_student_service.py`（7 新接口）+ `backend/tests/test_mobile_portal.py`；`student-portal/src/services/{uploadApi,exportApi,messageApi}.js`。
- **P4–P7**：按阶段分别提交高价值域闭环 / 轻量域 / 测试 / 部署。
- **绝不提交**：`.env`、`*.db`、`node_modules`、`dist`、真实证书/密钥、临时脚本、日志、Office 锁文件。

---

（本文件为 V1.0 设计稿，本轮仅升级文档，未写代码、未建工程、未改后端、未做任何 git 操作。改完停止，等待确认。）
