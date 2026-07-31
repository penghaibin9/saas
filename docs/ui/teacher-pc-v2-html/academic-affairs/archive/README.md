# 教务归档：开发还原契约

> 本目录是教师 PC V2 高保真 HTML 原型。生产状态、权限、数据域语义门禁、封存写保护和导出审计必须以真实代码为准。

## 4 个真实入口

| 生产入口 | HTML | 主要权限 | 事实源 |
|---|---|---|---|
| 归档批次 + 9 数据域完整性检查 + 学期封存 | `archive-batches.html` | `academicAffairs.archive.view` / `academicAffairs.archive.manage` | `AaArchiveConsoleView.vue` |
| 归档缺失提醒 | `archive-precheck.html` | `academicAffairs.archive.view` | `ArchivePrecheckView.vue` |
| 批量归档 | `archive-batch-workbench.html` | `academicAffairs.archive.view` / `academicAffairs.archive.manage` | 主控制台、归档服务与写保护 guard |
| 归档导出 | `archive-export.html` | `academicAffairs.archive.export` | `ArchiveExportView.vue` |

## 名称纠偏

生产菜单中的“批量归档”通过 `?entry=batch` 进入同一批次工作台。当前真实模型是一学期一个归档批次，批次内集中检查和归档多个数据域，**不是跨多个学期一键归档**。原型必须避免让用户误以为可以批量封存多个学期。

## 批次状态机

```text
DRAFT
→ CHECKING
→ READY / MISSING_ITEMS
→ ARCHIVED

DRAFT / READY / MISSING_ITEMS
→ CANCELLED

ARCHIVED
→ 特批解冻（仅学校管理员，保留原归档历史）
```

- `DRAFT`：已创建，尚未完成检查。
- `CHECKING`：正在聚合和计算。
- `READY`：所有必需门禁通过，可普通确认归档。
- `MISSING_ITEMS`：存在缺失或阻断，只能先修复或明确强制归档。
- `ARCHIVED`：批次与学期封存，核心教务写操作应返回 `409 TERM_ARCHIVED`。
- `CANCELLED`：取消批次，保留审计，不恢复为可用批次。

## 语义预检

归档预检不再把“记录数大于 0”当作“业务已完成”。每个业务域应返回：

- 域码和域名称
- 规则码 / 规则版本
- `PASS` 或 `BLOCKED`
- 业务记录数
- 阻断项数量
- 结论摘要
- 最小证据
- 去处理路由
- 数据范围说明

示例：成绩域存在 401 个任务并不代表可归档；只要仍有 12 个任务未发布，语义门禁就应阻断。

## 数据域边界

核心批次物料包含：

1. 学籍
2. 注册
3. 学籍异动
4. 培养方案
5. 教学任务
6. 课表
7. 考务
8. 成绩
9. 毕业资格

语义预检页面可能接入更多已启用业务域。原型必须区分“核心归档物料域”和“扩展语义门禁域”，不得把数量变化误认为接口错误。

部分域缺少强学期或学院维度时，页面必须如实显示全校口径、当前学期降级判据或其他范围局限，不能伪装为精确过滤。

## 高风险操作

### 普通确认归档

- 仅 `READY` 可执行。
- 归档后批次与学期进入 `ARCHIVED`。
- 必须重新读取后端状态，不能依赖页面缓存。
- 必须提示核心写操作将被拦截。

### 强制归档

- 仅 `MISSING_ITEMS` 可进入。
- 必须显示缺失域、阻断项和风险。
- 必须填写原因并写入审计。
- 不得把缺失状态改写成“完整”。

### 特批解冻

- 仅学校管理员。
- 原因至少 5 字。
- 解冻不删除原归档、检查和下载历史。
- 生产施工前要核对解冻后的目标状态与重新检查要求。

## 导出与审计

- 仅 `ARCHIVED` 批次进入正式导出列表。
- 单域导出为水印 XLSX。
- 全量导出为 ZIP 包。
- 下载用途至少 5 字。
- 记录下载人、角色、类型、用途和时间。
- 文件可能包含姓名、学号等敏感字段，受权限、数据范围和脱敏策略约束。
- 未归档批次不得生成正式封存物料。

## 公共组件映射

生产还原优先使用：

- `ModulePageShell`
- `DataTable`
- `StatusTag`
- `LoadingState` / `EmptyState` / `ErrorState`
- `AppButton`
- `AppDrawer`
- `AppConfirmDialog`
- `AppInlineAlert`
- `AppTermEntityPicker`
- `AppFormItem`
- `AppTextInput`

原型中的共享 JS 只用于离线展示，不得进入生产 Vue 运行时。

## 开发 AI 读取顺序

1. 阅读 4 个 HTML 的 route、source、permission、roles、states 和 boundary。
2. 阅读 `manifest-parts/200-archive.json`。
3. 阅读 `shared/v2-archive-workbench.js` 与 CSS。
4. 回到生产 3 个 Vue 页面、路由、API 和 `academic_affairs_archive_service.py`。
5. 核对后端 9 域计数 / 语义门禁、写保护 guard、导出水印和审计。
6. 只复用设计和交互，不复制 placeholder 数据或前端权限判断。

## 当前验证口径

- 4 个 HTML、共享 CSS/JS、README 和 manifest 已落盘。
- 路由、权限、6 状态、核心高风险操作和真实页面结构已静态核对。
- 当前连接环境未执行本批真实浏览器渲染，不能宣称控制台、溢出、焦点或三档分辨率通过。
