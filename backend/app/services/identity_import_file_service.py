"""师生账号唯一导入入口的 .xlsx 模板、解析、预检批次与错误回执。

本服务刻意只接受标准 xlsx，不接受 csv/xls/xlsm。预检后的结构化数据仅在短时批次中保存，
确认时按租户与操作者再次校验，避免跨租户确认或替换文件后绕过预检。
"""
from __future__ import annotations

import hashlib
import io
import secrets
import time
import zipfile
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from app.core.exceptions import AppException, not_found
from app.services.saas_role_templates import role_catalog
from app.services.xlsx_util import build_ledger_xlsx, pack_xlsx_result

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2000
MAX_ROWS = 2000
BATCH_TTL_SECONDS = 30 * 60

HEADERS = (
    "账号类型", "工号/学号", "姓名", "预设角色编码（教师）", "班级名称（学生）",
    "年级（学生）", "性别（学生）", "数据范围类型（教师）", "数据范围引用（教师）",
)
REQUIRED_HEADERS = {"账号类型", "工号/学号", "姓名"}
_TYPE_ALIASES = {
    "STUDENT": "STUDENT", "学生": "STUDENT",
    "TEACHER": "TEACHER", "教师": "TEACHER", "老师": "TEACHER",
}
_BATCHES: dict[str, dict] = {}


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalize_header(value) -> str:
    return _cell_text(value).rstrip(" *").strip()


def _validate_xlsx_archive(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise AppException("FILE_TOO_LARGE", "Excel 内部文件数量异常，请使用系统标准模板")
            if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise AppException("FILE_TOO_LARGE", "Excel 解压后超过 100MB 上限，请拆分后重试")
            names = {info.filename.lower() for info in infos}
            if any(name.endswith("vbaproject.bin") for name in names):
                raise AppException("FILE_TYPE_NOT_ALLOWED", "师生账号导入禁止包含宏代码")
    except AppException:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise AppException("FILE_TYPE_NOT_ALLOWED", "文件不是有效的标准 .xlsx，请重新下载模板") from exc


def _user_key(user: dict) -> str:
    return str(user.get("userId") or user.get("sub") or user.get("loginName") or "")


def _clean_expired_batches() -> None:
    now = time.monotonic()
    for key in [k for k, v in _BATCHES.items() if v["expiresAtMono"] <= now]:
        _BATCHES.pop(key, None)


def build_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    ws.append([f"{h} *" if h in REQUIRED_HEADERS else h for h in HEADERS])
    fill = PatternFill("solid", fgColor="DCE6F1")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    widths = [16, 20, 16, 30, 24, 18, 16, 26, 28]
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=index).column_letter].width = width
    ws.freeze_panes = "A2"
    ws.column_dimensions["B"].number_format = "@"
    type_validation = DataValidation(type="list", formula1='"STUDENT,TEACHER"', allow_blank=False)
    ws.add_data_validation(type_validation)
    type_validation.add(f"A2:A{MAX_ROWS + 1}")

    notes = wb.create_sheet("填写说明")
    instructions = [
        "只允许上传本模板生成的 .xlsx 文件，不支持 CSV、旧版 .xls 或启用宏的 .xlsm。",
        "账号类型只能填写 STUDENT（学生）或 TEACHER（教师）。",
        "学生账号固定绑定 STUDENT 角色，不填写预设角色编码。",
        "教师必须填写预设角色编码；多个角色用中文/英文逗号、分号或竖线分隔。",
        "工号/学号请设置为文本，避免前导零丢失；同一学校内必须唯一。",
        "辅导员必须填写 CLASS 或 ADVISOR 数据范围及对应引用。",
        "预检通过后才能整批确认；任何错误都会阻止整批写入。",
    ]
    notes.append(["填写说明"])
    notes["A1"].font = Font(bold=True, size=12)
    for index, item in enumerate(instructions, 2):
        notes.cell(row=index, column=1, value=item)
    notes.column_dimensions["A"].width = 100

    samples = wb.create_sheet("填写示例（不要导入）")
    samples.append(list(HEADERS))
    samples.append(["STUDENT", "20260001", "张同学", "", "软件2601", "2026", "男", "", ""])
    samples.append(["TEACHER", "T2026001", "李老师", "ACADEMIC_TEACHER", "", "", "", "", ""])
    for cell in samples[1]:
        cell.font = Font(bold=True)
        cell.fill = fill

    roles = wb.create_sheet("教师预设角色")
    roles.append(["角色编码", "角色名称", "默认数据范围", "分类"])
    for item in role_catalog(teacher_only=True)["items"]:
        roles.append([item["roleCode"], item["roleName"], item["defaultScope"], item["category"]])
    for cell in roles[1]:
        cell.font = Font(bold=True)
        cell.fill = fill
    for col, width in zip(("A", "B", "C", "D"), (30, 24, 26, 22)):
        roles.column_dimensions[col].width = width
    roles.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_xlsx(content: bytes, filename: str) -> dict:
    if not str(filename or "").lower().endswith(".xlsx"):
        raise AppException("FILE_TYPE_NOT_ALLOWED", "师生账号导入只支持标准 .xlsx 文件")
    if not content:
        raise AppException("VALIDATION_ERROR", "上传文件为空")
    if len(content) > MAX_FILE_BYTES:
        raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
    _validate_xlsx_archive(content)
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
        ws = wb["导入模板"] if "导入模板" in wb.sheetnames else wb.worksheets[0]
        iterator = ws.iter_rows(values_only=True)
        raw_headers = next(iterator)
    except (StopIteration, KeyError):
        raise AppException("VALIDATION_ERROR", "Excel 没有可导入的工作表或表头")
    except Exception as exc:  # noqa: BLE001
        raise AppException("FILE_TYPE_NOT_ALLOWED", "文件不是有效的标准 .xlsx，请重新下载模板") from exc

    headers = [_normalize_header(value) for value in raw_headers]
    duplicate_headers = sorted({h for h in headers if h and headers.count(h) > 1})
    if duplicate_headers:
        wb.close()
        raise AppException("VALIDATION_ERROR", f"Excel 表头重复：{','.join(duplicate_headers)}")
    missing = [h for h in HEADERS if h not in headers]
    unknown = [h for h in headers if h and h not in HEADERS]
    if missing or unknown:
        wb.close()
        parts = []
        if missing:
            parts.append(f"缺少表头：{','.join(missing)}")
        if unknown:
            parts.append(f"不支持的表头：{','.join(unknown)}")
        raise AppException("VALIDATION_ERROR", "；".join(parts) + "。请使用系统下载的最新版模板")

    header_index = {name: headers.index(name) for name in HEADERS}
    students, teachers, raw_rows, errors = [], [], [], []
    total = 0
    for row_no, values in enumerate(iterator, 2):
        cells = {name: _cell_text(values[index] if index < len(values) else "")
                 for name, index in header_index.items()}
        if not any(cells.values()):
            continue
        total += 1
        if total > MAX_ROWS:
            wb.close()
            raise AppException("VALIDATION_ERROR", f"单次最多导入 {MAX_ROWS} 行，请拆分文件")
        account_type = _TYPE_ALIASES.get(cells["账号类型"].upper())
        account_no = cells["工号/学号"]
        name = cells["姓名"]
        raw_rows.append({"row": row_no, "accountType": cells["账号类型"],
                         "accountNo": account_no, "name": name})
        if not account_type:
            errors.append({"row": row_no, "entity": "file", "field": "账号类型",
                           "error": "账号类型只能填写 STUDENT 或 TEACHER"})
            continue
        if account_type == "STUDENT":
            role = cells["预设角色编码（教师）"]
            if role and role.upper() != "STUDENT":
                errors.append({"row": row_no, "entity": "student", "field": "预设角色编码（教师）",
                               "error": "学生角色由系统固定为 STUDENT，请留空"})
            students.append({
                "_rowNo": row_no, "studentNo": account_no, "name": name,
                "className": cells["班级名称（学生）"], "grade": cells["年级（学生）"],
                "gender": cells["性别（学生）"],
            })
        else:
            teachers.append({
                "_rowNo": row_no, "loginName": account_no, "name": name,
                "roleCodes": cells["预设角色编码（教师）"],
                "scopeType": cells["数据范围类型（教师）"],
                "scopeRef": cells["数据范围引用（教师）"],
            })
    wb.close()
    if total == 0:
        raise AppException("VALIDATION_ERROR", "Excel 没有数据行，请填写后再上传")
    return {
        "students": students, "teachers": teachers, "rawRows": raw_rows,
        "errors": errors, "totalRows": total,
        "fileName": filename, "fileSha256": hashlib.sha256(content).hexdigest(),
    }


def create_batch(user: dict, parsed: dict, report: dict) -> dict:
    _clean_expired_batches()
    batch_no = f"IDIMP{datetime.now():%Y%m%d%H%M%S}{secrets.token_hex(3).upper()}"
    errors = list(report.get("errors") or [])
    invalid_rows = {int(item.get("row") or 0) for item in errors if int(item.get("row") or 0) > 0}
    total = int(parsed["totalRows"])
    invalid_count = len(invalid_rows) if invalid_rows else (1 if errors else 0)
    entry = {
        "batchNo": batch_no, "tenantId": str(report.get("tenantId") or ""),
        "userKey": _user_key(user), "payload": {
            "tenantId": report.get("tenantId"), "students": parsed["students"],
            "teachers": parsed["teachers"], "atomic": True,
        },
        "rawRows": parsed["rawRows"], "errors": errors, "report": report,
        "fileName": parsed["fileName"], "fileSha256": parsed["fileSha256"],
        "expiresAtMono": time.monotonic() + BATCH_TTL_SECONDS,
    }
    _BATCHES[batch_no] = entry
    return {
        "batchNo": batch_no, "fileName": parsed["fileName"],
        "total": total, "valid": max(total - invalid_count, 0),
        "invalid": invalid_count, "errors": [
            {"row": item.get("row", 0), "entity": item.get("entity", ""),
             "field": item.get("field", ""), "message": item.get("error") or item.get("message") or "校验失败"}
            for item in errors
        ],
        "roleTemplateVersion": report.get("roleTemplateVersion"),
        "entities": report.get("entities") or {},
        "expiresInMinutes": BATCH_TTL_SECONDS // 60,
    }


def get_batch(user: dict, tenant_id: object, batch_no: str, *, require_valid: bool = False) -> dict:
    _clean_expired_batches()
    entry = _BATCHES.get(str(batch_no or ""))
    if (not entry or entry["tenantId"] != str(tenant_id or "")
            or entry["userKey"] != _user_key(user)):
        raise not_found("导入批次不存在或已过期，请重新上传预检")
    if require_valid and entry["errors"]:
        raise AppException("VALIDATION_ERROR", "该批次存在错误，禁止确认导入")
    return entry


def mark_confirmed(batch_no: str) -> None:
    _BATCHES.pop(batch_no, None)


def build_error_workbook(entry: dict) -> bytes:
    raw = {int(row["row"]): row for row in entry.get("rawRows") or []}
    rows = []
    for item in entry.get("errors") or []:
        row_no = int(item.get("row") or 0)
        source = raw.get(row_no, {})
        rows.append([
            row_no or "全局", source.get("accountType", ""), source.get("accountNo", ""),
            source.get("name", ""), item.get("entity", ""), item.get("field", ""),
            item.get("error") or item.get("message") or "校验失败",
        ])
    return build_ledger_xlsx(
        "师生账号导入错误", ["Excel行号", "账号类型", "工号/学号", "姓名", "对象", "错误字段", "错误原因"],
        rows, watermark="本文件仅含预检失败行；修正原导入模板后重新上传，不会自动创建账号。")


def build_credential_receipt(entry: dict, report: dict) -> dict | None:
    """把仅本次返回的初始密码封装为 xlsx 回执；调用方不得记录返回内容。"""
    student_names = {str(row.get("studentNo")): str(row.get("name") or "")
                     for row in entry["payload"].get("students") or []}
    teacher_names = {str(row.get("loginName")): str(row.get("name") or "")
                     for row in entry["payload"].get("teachers") or []}
    credential_rows = [
        ["STUDENT", item["studentNo"], student_names.get(str(item["studentNo"]), ""),
         item["initialPassword"], "首次登录必须修改密码"]
        for item in report.get("studentCredentials") or []
    ] + [
        ["TEACHER", item["loginName"], teacher_names.get(str(item["loginName"]), ""),
         item["initialPassword"], "首次登录必须修改密码"]
        for item in report.get("teacherCredentials") or []
    ]
    if not credential_rows:
        return None
    return pack_xlsx_result(
        build_ledger_xlsx(
            "初始账号凭据", ["账号类型", "工号/学号", "姓名", "初始密码", "安全要求"],
            credential_rows,
            watermark="初始密码仅本次生成和显示；请安全转交，禁止通过公开群聊传播。"),
        f"师生账号初始凭据_{entry['batchNo']}.xlsx", len(credential_rows))
