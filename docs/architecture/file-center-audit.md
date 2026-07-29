# 全平台公共文件能力审计

> 阶段 0：精确清单与冻结合同  
> 分支：`audit/file-capability-inventory`  
> 本阶段只盘点、登记和建立门禁，不改变任何上传、下载、预览、导入、导出、归档业务行为。

## 1. 审计目标

把教师/管理 PC、学生 PC、教师小程序、学生小程序和后端中的文件能力统一登记为机器可读清单，回答：

- 哪个模块、哪个端、哪个页面在处理文件；
- 调用哪个 API、进入哪个后端服务、最终采用什么存储方式；
- 使用什么身份认证和数据范围；
- 是否有版本、病毒扫描放行、预览、下载、导入、导出、归档；
- 当前是正式能力、重复入口、历史兼容、待核实还是拟删除；
- 风险级别和目标整改阶段是什么。

## 2. 阶段边界

### 允许

- 新增审计文档、机器清单、扫描脚本和 CI 门禁；
- 读取路由、前端 API、页面、服务、模型、迁移和测试；
- 把发现的入口登记为 `active`、`legacy`、`duplicate`、`needs-verification` 或 `planned`；
- 记录风险和后续阶段，不在本阶段修复。

### 禁止

- 删除或改名 `/api/v1/files`、`/api/v1/files/upload` 等现有接口；
- 修改 `file_service`、存储后端、权限、数据范围或业务状态机；
- 新建数据库表或 Alembic 迁移；
- 接入 ClamAV、COS、MinIO、签名 URL 或异步任务；
- 修改四端页面交互。

## 3. 已核实的公共底座

| 能力 | 当前入口/实现 | 阶段 0 结论 |
|---|---|---|
| 正式文件创建 | `POST /api/v1/files` | 已存在，登记，不裁决是否为最终唯一入口 |
| 历史上传入口 | `POST /api/v1/files/upload` | 已存在，登记为重复/兼容候选，不在阶段 0 删除 |
| 文件元数据 | `GET /api/v1/files/meta/{file_id}` | 已存在，对象级授权 |
| 文件 URL | `GET /api/v1/files/{file_id}/url` | 已存在，返回同域下载路径 |
| 文件下载 | `GET /api/v1/files/download/{file_id}` | 已存在，租户、对象授权、下载审计 |
| 文件服务 | `backend/app/services/file_service.py` | 负责校验、登记、存储、授权和下载解析 |
| 存储抽象 | `backend/app/services/storage/` | 支持可插拔存储，当前模式由配置决定 |
| 文件对象 | `t_file_object` | 统一文件元数据对象 |
| 非生产占位 | `POST /api/v1/files/upload-placeholder` | 仅非生产注册，列为高风险历史入口 |

## 4. 当前已确认风险

### P0：大文件扫描读取方式

`file_service.store_upload()` 对超过 8MB 的文件使用 `target.read_bytes()` 读取整个文件进行内容检查。阶段 1 必须改为流式/路径式扫描；阶段 0 只登记。

### P0：扫描放行合同尚未统一

当前存在文件状态和内容校验基础，但全平台业务提交是否统一经过“文件已安全可用”门禁，需要按业务入口逐项核实。

### P1：普通上传存在双入口

`POST /files` 与 `POST /files/upload` 均可上传并调用公共文件服务。最终保留哪一个，要在清单完整、调用关系迁移方案明确后裁决。

### P1：非生产占位入口

占位上传虽然只在非生产注册，但会生成不落盘的假文件标识。需要确认测试、文档和前端是否仍引用。

### P1：业务附件授权存在两层

公共文件服务做对象级授权，部分业务模块还提供自己的附件关联/下载路由。需要确认是否重复、是否绕过统一下载审计。

### P1：导入导出实现分散

Excel、迁移、教务、学工、实习、毕设等模块存在导入/导出能力。需核对是否统一使用 xlsx、错误行回执、数据范围、审计和异步任务。

## 5. 审计方法

机器脚本 `scripts/audit_file_capabilities.py` 扫描：

- FastAPI 路由装饰器及包含 upload/download/preview/import/export/archive/file 的路径；
- `UploadFile`、`FileResponse`、`StreamingResponse`；
- `file_service.store_upload/store_bytes/get_file_meta/resolve_download`；
- 浏览器/uni-app 的 `uploadFile`、`downloadFile`、`chooseFile`；
- `openpyxl`、`load_workbook`、`Workbook`、`ZipFile`；
- `Content-Disposition` 和附件响应；
- 关键本地文件读写调用。

脚本提供两类门禁：

1. **全量基线检查**：现有高置信文件能力必须被清单覆盖；
2. **增量检查**：PR 新增或修改文件能力时，必须同步登记清单。

## 6. 验收口径

阶段 0 只有同时满足以下条件才算完成：

- 四个规定输出文件存在并可读取；
- 清单每条记录包含冻结字段；
- 全量脚本扫描无未登记的高置信入口；
- CI 对新增文件能力实施登记门禁；
- 人工已知入口全部进入清单；
- 没有修改业务代码、路由行为和数据库；
- Draft PR 保持未合并。

## 7. 后续阶段约束

阶段 0 验收前：

- 不开始阶段 1；
- 不删除 `/files/upload`；
- 不统一接口名称；
- 不修改存储或病毒扫描实现；
- 不把任何“建议目标”当成“当前事实”。

阶段 0 完成后，以 `file-capability-inventory.yaml` 作为阶段 1–7 的唯一施工入口清单。
