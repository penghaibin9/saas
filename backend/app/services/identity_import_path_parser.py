"""学生/教师身份导入 XLSX 的路径型解析器。

只在 FileObject 已通过安全扫描后调用。ZIP 结构、宏、表头、公式注入与行数规则与既有
identity_import_file_service 保持一致；openpyxl 直接读取本地路径，SHA-256 分块计算，
不把整个 XLSX 拼入内存。
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from openpyxl import load_workbook

from app.core.exceptions import AppException
from app.services.identity_import_file_service import (
    MAX_ARCHIVE_ENTRIES,
    MAX_FILE_BYTES,
    MAX_ROWS,
    MAX_UNCOMPRESSED_BYTES,
    STUDENT_HEADERS,
    STUDENT_REQUIRED_HEADERS,
    TEACHER_HEADERS,
    TEACHER_REQUIRED_HEADERS,
    _normalize_header,
    _row_cells,
)

CHUNK_SIZE = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _validate_archive(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise AppException("VALIDATION_ERROR", "上传文件为空")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise AppException("FILE_TOO_LARGE", "Excel 内部文件数量异常，请使用系统标准模板")
            if sum(max(0, int(info.file_size or 0)) for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise AppException("FILE_TOO_LARGE", "Excel 解压后超过 100MB 上限，请拆分后重试")
            names = {info.filename.lower() for info in infos}
            if any(name.endswith("vbaproject.bin") for name in names):
                raise AppException("FILE_TYPE_NOT_ALLOWED", "师生账号导入禁止包含宏代码")
            for info in infos:
                normalized = info.filename.replace("\\", "/")
                if normalized.startswith("/") or ".." in normalized.split("/"):
                    raise AppException("FILE_TYPE_NOT_ALLOWED", "Excel 内部路径不安全")
    except AppException:
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        raise AppException("FILE_TYPE_NOT_ALLOWED", "文件不是有效的标准 .xlsx，请重新下载模板") from exc


def _open(path: Path, filename: str, *, headers: tuple, required: set, what: str):
    if not str(filename or "").lower().endswith(".xlsx"):
        raise AppException("FILE_TYPE_NOT_ALLOWED", f"{what}只支持标准 .xlsx 文件")
    _validate_archive(path)
    try:
        workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        sheet = workbook["导入模板"] if "导入模板" in workbook.sheetnames else workbook.worksheets[0]
        iterator = sheet.iter_rows(values_only=True)
        raw_headers = next(iterator)
    except (StopIteration, KeyError):
        raise AppException("VALIDATION_ERROR", "Excel 没有可导入的工作表或表头")
    except Exception as exc:  # noqa: BLE001
        raise AppException("FILE_TYPE_NOT_ALLOWED", "文件不是有效的标准 .xlsx，请重新下载模板") from exc
    parsed_headers = [_normalize_header(value) for value in raw_headers]
    duplicates = sorted({item for item in parsed_headers if item and parsed_headers.count(item) > 1})
    missing = [item for item in required if item not in parsed_headers]
    unknown = [item for item in parsed_headers if item and item not in headers]
    if duplicates or missing or unknown:
        workbook.close()
        parts = []
        if duplicates:
            parts.append(f"Excel 表头重复：{','.join(duplicates)}")
        if missing:
            parts.append(f"缺少表头：{','.join(missing)}")
        if unknown:
            parts.append(f"不支持的表头：{','.join(unknown)}（请确认没有把另一类模板传到这里）")
        raise AppException("VALIDATION_ERROR", "；".join(parts) + "。请使用系统下载的最新版模板")
    return workbook, iterator, parsed_headers


def parse_identity_xlsx_path(path: str | Path, filename: str, kind: str) -> dict:
    file_path = Path(path)
    kind_up = str(kind or "").upper()
    if kind_up == "STUDENT":
        headers, required, what = STUDENT_HEADERS, STUDENT_REQUIRED_HEADERS, "学生导入"
    elif kind_up == "TEACHER":
        headers, required, what = TEACHER_HEADERS, TEACHER_REQUIRED_HEADERS, "教师导入"
    else:
        raise AppException("VALIDATION_ERROR", "身份导入类型仅支持 STUDENT 或 TEACHER")

    workbook, iterator, parsed_headers = _open(
        file_path, filename, headers=headers, required=required, what=what
    )
    header_index = {name: parsed_headers.index(name) for name in headers if name in parsed_headers}
    students: list[dict] = []
    teachers: list[dict] = []
    raw_rows: list[dict] = []
    errors: list[dict] = []
    total = 0
    try:
        for row_no, values in enumerate(iterator, 2):
            entity = "student" if kind_up == "STUDENT" else "teacher"
            cells, empty = _row_cells(values, headers, header_index, row_no, errors, entity)
            if empty:
                continue
            total += 1
            if total > MAX_ROWS:
                raise AppException("VALIDATION_ERROR", f"单次最多导入 {MAX_ROWS} 行，请拆分文件")
            if kind_up == "STUDENT":
                account_no, name = cells["学号"], cells["姓名"]
                raw_rows.append({"row": row_no, "accountType": "STUDENT", "accountNo": account_no, "name": name})
                if not account_no:
                    errors.append({"row": row_no, "entity": entity, "field": "学号", "error": "学号必填"})
                if not name:
                    errors.append({"row": row_no, "entity": entity, "field": "姓名", "error": "姓名必填"})
                if not cells["班级名称"]:
                    errors.append({
                        "row": row_no,
                        "entity": entity,
                        "field": "班级名称",
                        "error": "班级必填：学生必须归属完整的学院、专业、班级",
                    })
                students.append({
                    "_rowNo": row_no,
                    "studentNo": account_no,
                    "name": name,
                    "collegeName": cells["所属学院"],
                    "majorName": cells["所属专业"],
                    "className": cells["班级名称"],
                    "grade": cells["年级"],
                    "gender": cells["性别"],
                    "idCard": cells["身份证号"],
                })
            else:
                account_no, name = cells["工号"], cells["姓名"]
                raw_rows.append({"row": row_no, "accountType": "TEACHER", "accountNo": account_no, "name": name})
                if not account_no:
                    errors.append({"row": row_no, "entity": entity, "field": "工号", "error": "工号必填"})
                if not name:
                    errors.append({"row": row_no, "entity": entity, "field": "姓名", "error": "姓名必填"})
                if not cells["预设角色编码"]:
                    errors.append({
                        "row": row_no,
                        "entity": entity,
                        "field": "预设角色编码",
                        "error": "教师必须指定预设角色编码",
                    })
                teachers.append({
                    "_rowNo": row_no,
                    "loginName": account_no,
                    "name": name,
                    "departmentName": cells["所属部门"],
                    "positionName": cells["岗位名称"],
                    "roleCodes": cells["预设角色编码"],
                    "scopeType": cells["数据范围类型"],
                    "scopeRef": cells["数据范围引用"],
                })
    finally:
        workbook.close()
    if total == 0:
        raise AppException("VALIDATION_ERROR", "Excel 没有数据行，请填写后再上传")
    return {
        "students": students,
        "teachers": teachers,
        "rawRows": raw_rows,
        "relationships": [],
        "relationErrors": [],
        "errors": errors,
        "totalRows": total,
        "importKind": kind_up,
        "fileName": filename,
        "fileSha256": _sha256(file_path),
    }
