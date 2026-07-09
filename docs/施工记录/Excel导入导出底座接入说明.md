# 公共 Excel 导入导出底座 · 接入说明（V1.1）

> 面向后续所有模块（实习学生、毕设选题、成绩、学籍、奖助…）。
> 目标：**新模块只写「字段配置 + 校验规则 + 落库 + 导出查询」，不再各写一套 Excel 代码。**
> 正式口径遵守 CLAUDE.md §38（学校用 Excel/xlsx，不拿 CSV 糊弄）、§39（商业交付标准）。

---

## 0. 底座在哪

| 层 | 位置 | 职责 |
|----|------|------|
| 底层引擎 | `backend/app/services/xlsx_util.py` | 纯 xlsx 读/写/模板/错误行/台账（openpyxl）。**四模块已依赖，勿破坏** |
| 接入契约 | `backend/app/services/excel/spec.py` | `ColumnSpec` / `ImportSpec` / `ExportSpec` |
| 校验器 | `backend/app/services/excel/validators.py` | 必填/长度/整数/小数/日期/手机号/身份证/统一社会信用代码/邮箱/枚举 |
| 核心管道 | `backend/app/services/excel/pipeline.py` | `build_template / read_upload / pre_validate / build_error_rows / confirm_import / build_export` |
| 导入记录 | `backend/app/services/excel/job_service.py` + `models/excel_import_job.py`（`t_excel_import_job`） | 通用导入作业台账（真库） |
| 通用端点 | `backend/app/api/v1/excel.py` | `GET /api/v1/excel/import-jobs` 导入记录查询 |
| Pydantic | `backend/app/schemas/excel.py` | `ExcelImportRows / ExcelErrorRows / PreValidateResult / ImportJobItem` |
| 前端组件 | `frontend/src/components/common/excel/` | `AppExcelImportDrawer / AppExcelUpload / AppImportPreviewTable / AppImportErrorSummary / AppExportButton` |

---

## 1. 后端：怎么定义字段（接入契约）

```python
from app.services.excel import ColumnSpec, ImportSpec, ExportSpec, validators

def build_import_spec() -> ImportSpec:
    return ImportSpec(
        module_key="internship", biz_type="intern-student",
        template_name="实习学生导入",
        columns=[
            ColumnSpec("studentNo", "学号", required=True, unique_in_file=True, example="2023115001",
                       help_text="须为在校学生学号"),
            ColumnSpec("name", "姓名", required=True, max_length=30, example="张三"),
            ColumnSpec("phone", "手机号", type="phone", example="13800000000"),
            ColumnSpec("idCard", "身份证号", type="idcard"),
            ColumnSpec("enrollDate", "报名日期", type="date", example="2026-07-07"),
            ColumnSpec("kind", "类型", type="enum", options=["集中", "分散"], example="集中"),
        ],
        notes=["1. 仅导入「导入模板」页；带 * 为必填。", "2. 学号须存在于学籍库。"],
        duplicate_check=_db_dup_check,       # 库内查重（可选）
        business_validate=_business_rule,     # 业务规则（可选）
        transform_row=_to_db_row,             # 行清洗（可选）
        persist_rows=_persist,                # 落库（确认导入用，必填才能 confirm）
        permission_key="internship.internStudent.import",
        audit_action="导入实习学生",
    )
```

**字段类型 `type`**：`str`(默认) / `int` / `decimal` / `date` / `phone` / `idcard` / `creditcode` / `email` / `enum`。
枚举需配 `options=[...]`。需要额外规则时，往 `ColumnSpec.validators=[fn]` 追加，`fn(value, col) -> str | None`。

---

## 2. 后端：怎么做校验（统一预校验结构）

```python
from app.services import excel

pre = excel.pre_validate(spec, rows)
# 统一返回：
# {
#   moduleKey, bizType, templateVersion,
#   total, validRows, invalidRows, passed,   # passed = 无错误且 total>0
#   rows: [...原始行...],                      # 供错误行重建 + 确认导入
#   errors: [{ rowNo, field, title, rawValue, message }],
# }
```

校验顺序（底座已内置，勿重复实现）：
必填 → 最大长度 → 类型/格式 → 枚举 → 自定义 validators → 文件内重复（`unique_in_file`，支持多列联合）→ `business_validate` → `duplicate_check`（库内，整批一次）。

**扩展点签名**：
- `duplicate_check(rows) -> dict[int, str]`：`{1-based 行号: 冲突原因}`。
- `business_validate(row, row_no) -> str | None`。

---

## 3. 后端：怎么确认导入

```python
result = excel.confirm_import(spec, rows)   # 内部强制再跑 pre_validate，有失败行直接抛 DATA_CONFLICT
# result = { moduleKey, bizType, total, created, ...persist_rows 的返回 }

# 建议同时登记导入记录 + 审计：
from app.services import audit_log
from app.services.excel import job_service
job_service.record_import(spec.module_key, spec.biz_type, file_name=name,
                          pre=pre, result=result, status="IMPORTED")
audit_log.record(spec.audit_action, f"{spec.module_key}:{spec.biz_type}:import", detail=result)
```

> `confirm_import` **一定会再次校验**，即便前端跳步也不会让脏数据落库。写操作不得 mock 成功。

---

## 4. 后端：怎么导出（台账 + 脱敏）

```python
export_spec = ExportSpec(
    module_key="internship", biz_type="intern-student", sheet_title="实习学生台账",
    columns=[
        ColumnSpec("name", "姓名"),
        ColumnSpec("phone", "手机号", mask=lambda v: v[:3] + "****" + v[-4:]),  # 敏感字段脱敏
        ColumnSpec("kind", "类型"),
    ],
)
items = query_items(**filters)                       # 业务自己查（含权限/数据范围）
packed = excel.build_export(export_spec, items, operator_name=op, tenant_label=tenant)
audit_log.record("导出实习学生", "internship:intern-student:export", detail={"rowCount": packed["rowCount"]})
return success(packed)   # packed = { filename, contentBase64, mediaType, rowCount }，首行含导出人/时间水印
```

---

## 5. 前端：怎么接组件

```vue
<script setup>
import { AppExcelImportDrawer, AppExportButton } from '@/components/common/excel'
import { xxxApi } from '@/modules/xxx/api/xxx.api'

const importVisible = ref(false)
const downloadTemplate = () => xxxApi.downloadImportTemplate()       // 后端 blob
const upload = (file) => xxxApi.uploadImportXlsx(file)              // res.data = 统一预校验结构
const confirm = ({ rows }) => xxxApi.confirmImport(rows)            // res.data.created
const downloadErrors = ({ rows, errors }) => xxxApi.downloadImportErrors(rows, errors)
const doExport = () => xxxApi.exportLedger(currentFilters.value)
</script>

<template>
  <AppButton @click="importVisible = true">导入 Excel</AppButton>
  <AppExportButton :export-fn="doExport" :has-permission="canExport" />

  <AppExcelImportDrawer
    v-model:visible="importVisible"
    title="实习学生导入"
    template-name="实习学生导入模板.xlsx"
    :required-fields="['学号', '姓名']"
    :preview-fields="['studentNo', 'name']"
    :download-template-fn="downloadTemplate"
    :upload-fn="upload"
    :confirm-fn="confirm"
    :download-errors-fn="downloadErrors"
    @imported="refreshList"
  />
</template>
```

组件负责：下载模板、上传 .xlsx、总行/有效/错误统计、错误行预览、下载错误行 Excel、确认导入、loading/成功/失败提示、导出触发下载、权限不足提示。
**页面只注入 4 个真实后端调用**，不在浏览器里造复杂 Excel。

---

## 6. 新模块接入步骤（清单）

1. 后端：写 `build_import_spec()` / `build_export_spec()`（字段 + 校验 + 落库 + 导出列）。
2. 后端路由挂 5 个端点：`import/template`（下载模板）、`import/xlsx`（上传预校验）、`import/errors-xlsx`（错误行）、`import/confirm`（确认）、`export`（台账）。可直接调用 `excel.build_template/read_upload+pre_validate/build_error_rows/confirm_import/build_export`。
3. 后端确认导入时调用 `job_service.record_import` + `audit_log.record`。
4. 前端 api 层加对应 4 个方法。
5. 前端页面接 `AppExcelImportDrawer` + `AppExportButton`。
6. 补 pytest（模板/预校验/错误行/确认/导出）。
7. `navPlan` 状态与历史欠账保持一致。

---

## 7. 禁止事项

1. 禁止绕过底座各写一套 Excel 解析/校验/台账代码。
2. 禁止「Excel 导入」与「高级粘贴导入」两套校验规则不一致——共用同一 `ImportSpec`。
3. 禁止正式入口出现 CSV 文案 / `.csv` 下载；保留粘贴只能叫「高级粘贴导入」并注明「少量临时录入，正式批量请用 Excel 模板」。
4. 禁止写操作 mock 成功；`confirm_import` 必须真实落库。
5. 禁止敏感字段（手机号/身份证/家庭经济/心理/处分）导出明文——用 `ColumnSpec.mask` 脱敏，并保证导出写审计。
6. 禁止 SQLite 冒充 MySQL 验收；导入记录表以 MySQL 为准。

---

## 8. 已接入 / 待接入

| 模块 | 现状 | 说明 |
|------|------|------|
| 数字迎新 / 企业库 / 岗位库 / 实习批次 | 已用 `xlsx_util` 直连 | 四模块 Excel 主链路已收口；**可平滑迁到底座 spec**（非必须，能力等价，见历史欠账） |
| 实习学生 | CSV（历史债） | 下一轮**必须按本说明改 Excel + 接底座** |
| 毕设学生 | ✅ Excel + 底座 | 2026-07-07 已接入 `ImportSpec/ExportSpec` + `AppExcelImportDrawer` |
| 后续新模块 | — | **一律按本说明接入底座**，不得再新写一套 |

> 底座 V1.1 已通过 `backend/tests/test_excel_base.py`（12 项，MySQL 测试库）。
