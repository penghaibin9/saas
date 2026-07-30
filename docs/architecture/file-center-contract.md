# 公共文件中心冻结合同

## 1. 合同状态

- 合同版本：`file-center-contract/v1`
- 所属阶段：阶段 0
- 状态：冻结候选
- 适用范围：后端、教师/管理 PC、学生 PC、教师小程序、学生小程序
- 原则：先登记、再裁决、后迁移；没有清单记录，不允许新增文件能力。

## 2. 术语

- **文件对象**：`t_file_object` 中的一条文件元数据记录。
- **文件能力入口**：上传、下载、预览、导入、导出、归档、模板、材料关联等任何处理文件的页面、API 或服务。
- **业务提交放行**：业务记录引用文件前，对文件归属、租户、状态、安全扫描和业务绑定进行校验。
- **公共入口**：跨模块共享的文件 API。
- **业务入口**：某模块为材料、论文、协议、证明或表格提供的专用 API。
- **历史入口**：仍可能被调用，但计划迁移或删除的入口。
- **扫描门禁**：文件在安全扫描完成前不能下载、预览或进入业务提交。

## 3. 清单字段合同

每条记录必须包含下列字段，字段名不得自行变更：

| 字段 | 含义 |
|---|---|
| `module` | 业务模块或公共底座 |
| `client` | `backend`、`admin-pc`、`student-pc`、`teacher-miniapp`、`student-miniapp`、`shared` |
| `route` | 页面路由或后端路由；无页面时填 `-` |
| `page` | 前端页面源码路径；无页面时填 `-` |
| `action` | upload/download/preview/import/export/archive/link/template 等 |
| `fileCategory` | ATTACHMENT、GRADUATION_MATERIAL、INTERNSHIP、XLSX_IMPORT 等 |
| `api` | 完整 API 契约或 `internal` |
| `backendService` | 服务源码路径和函数；纯前端未知时填 `unknown` |
| `storageMode` | local/cos/configurable/database/temporary/unknown |
| `authMode` | 登录、权限码、对象级授权等 |
| `dataScope` | tenant/object/owner/class/college/school/unknown |
| `versioned` | true/false/unknown |
| `scanGated` | true/false/partial/unknown |
| `preview` | true/false/unknown |
| `download` | true/false/unknown |
| `import` | true/false |
| `export` | true/false |
| `archive` | true/false/unknown |
| `status` | active/legacy/duplicate/needs-verification/planned/removed |
| `risk` | P0/P1/P2/P3 |
| `targetPhase` | 0–7 或 `none` |

允许增加 `notes`，不得缺少冻结字段。

## 4. 冻结规则

### 4.1 阶段 0 不做接口裁决

现有下列入口全部先登记，不在阶段 0 删除：

- `POST /api/v1/files`
- `POST /api/v1/files/upload`
- `POST /api/v1/files/upload-placeholder`
- 文件元数据、URL、下载及各业务附件接口

最终唯一上传入口必须在清单完整后，结合调用量、返回合同、权限、扫描、四端迁移成本统一裁决。

### 4.2 新增能力必须登记

任何 PR 新增或修改下列内容，必须同步更新清单：

- 上传、下载、预览、文件选择；
- Excel/xlsx 导入导出、模板和错误回执；
- ZIP/归档包；
- 文件对象、附件回链、材料版本；
- 本地磁盘、COS、MinIO、对象存储；
- 文件权限、数据范围、审计、签名 URL；
- 病毒扫描、隔离区、状态放行；
- 异步文件任务。

### 4.3 禁止绕过

- 前端不得自行拼接磁盘路径或对象存储真实 Key；
- 业务表不得把服务器绝对路径当作正式文件合同；
- 下载不得只靠“知道 fileId”放行；
- 高风险文件未来必须经过统一扫描门禁；
- 导入导出必须使用 xlsx；CSV 仅作为历史风险登记，不作为目标方案；
- 生产环境不得使用假文件 ID、假签名 URL 或不落盘占位。

## 5. 状态与阶段

- `active`：当前正式使用。
- `legacy`：历史使用，仍需兼容。
- `duplicate`：与其他入口能力重叠，等待裁决。
- `needs-verification`：扫描发现，但调用、权限或存储尚未人工核实。
- `planned`：任务书目标，代码尚未存在。
- `removed`：已删除且有回归门禁。

目标阶段：

- 阶段 0：清单、合同、CI 门禁；
- 阶段 1：P0 安全底座；
- 阶段 2：存储与上传会话；
- 阶段 3：统一预览、下载和签名访问；
- 阶段 4：统一导入；
- 阶段 5：统一导出和异步任务；
- 阶段 6：归档、版本和生命周期；
- 阶段 7：迁移旧入口、删除重复实现。

## 6. 合并门禁

阶段 0 Draft PR 只有在以下检查全部通过后才能进入人工验收：

1. YAML 字段和枚举合法；
2. 全量高置信扫描无漏登；
3. 变更文件能力均已登记；
4. 文档和清单一致；
5. 业务代码变更为零；
6. 未合并 `main`。
