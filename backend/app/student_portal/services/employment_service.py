"""学生 PC 门户 · 就业服务（V3 施工手册 Lane S / S4 第一阶段）。

Authority 边界
────────────────────────────────────────────────────────────
就业的 canonical 事实源是 `app.modules.employment.services.employment_service`
（EmpStudent / EmpMaterial / EmpFollowup 与 L_DEST/L_VERIFY/L_MAT/L_HELP 字典）。
本文件只做「学生 PC 视角的投影 + 学生自助提交入口」，不另建第二套业务枚举、
不另建第二张表、不自己解释状态含义。

本轮（SP-E01/E02/E03/E04/E07/E08/E09/E10）关闭的问题
────────────────────────────────────────────────────────────
- SP-E01 学生表单发 `companyName`，旧实现却读 `unitName` → 单位名被静默丢弃。
  现在 canonical 字段是 `companyName`，`unitName` 仅作为 deprecated 兼容别名。
- SP-E02/E04 `destination_register()` 改走结构化
  `app.modules.employment.services.employment_destination_submission_service`
  （`EmpDestinationSubmission` 模型 + 真实单节点 workflow：就业老师审核）。
  jobTitle/city/contact 现在是类型化列，不再靠拼文本+逐字段截断勉强不丢；
  批准后在**同一事务**内原子写回 canonical `EmpStudent`
  （destination_type/company_name/job_title）。city/contact 目前没有对应
  EmpStudent 列，如实只落在提交记录里，不假装已建台账新列。
- SP-E03 学生 PC 之前硬编码 `FURTHER/MILITARY`，与 canonical
  `FURTHER_STUDY/ENLISTED` 漂移，且缺 `STARTUP/FREELANCE`。现在改为服务端
  下发 canonical 选项，非 canonical code 一律 422 拒绝。
- SP-E08 `destination_print()` 真实生成 PDF（File Center fileId + sha256），
  不再只写打印审计留痕。
- SP-E09 `materialStatus`（材料审核）与 `verifyStatus`（去向核验）是两个独立
  事实，DTO 同时下发、各自带 label，前端不得互推；提交/审批批准同样不动
  `verify_status`——核验仍必须走独立的
  `employment_destination_verification_service`（要求正式材料证据）。
- SP-E10 状态字典由服务端下发，前端只做 tone 映射，不再本地维护业务枚举。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found
from app.modules.employment.services import employment_service as canonical
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common

#: 学生自助登记允许提交的去向类型 = canonical L_DEST 全集。
#: 不在这里另抄一份枚举，canonical 增删去向类型时学生端自动跟随。
_DESTINATION_CODES = tuple(canonical.L_DEST.keys())

#: 各去向类型的必填字段与应交材料。
#: designSource=existing_code —— 材料类型直接取 canonical `L_MATTYPE` 已有的
#: 语义（AGREEMENT/CONTRACT/OFFER 对应签约、STUDY_PROOF 对应升学、
#: ENLIST_PROOF 对应入伍、STARTUP_PROOF 对应创业），不是 AI 现编的清单；
#: 必填字段取 EmpStudent 上真实存在的列（company_name/job_title）。
#: 未在此登记的去向类型按「无强制字段」处理，不臆造要求。
_DESTINATION_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "SIGNED": {"requiredFields": ["companyName"], "requiredMaterials": ["AGREEMENT", "CONTRACT", "OFFER"]},
    "FLEXIBLE": {"requiredFields": ["companyName"], "requiredMaterials": []},
    "FURTHER_STUDY": {"requiredFields": ["companyName"], "requiredMaterials": ["STUDY_PROOF"]},
    "ENLISTED": {"requiredFields": [], "requiredMaterials": ["ENLIST_PROOF"]},
    "STARTUP": {"requiredFields": ["companyName"], "requiredMaterials": ["STARTUP_PROOF"]},
    "FREELANCE": {"requiredFields": [], "requiredMaterials": []},
    "UNEMPLOYED": {"requiredFields": [], "requiredMaterials": []},
}

#: 各去向类型下 companyName 的业务称谓（升学是学校、创业是创业实体，不都叫"单位"）。
_COMPANY_LABELS: dict[str, str] = {
    "SIGNED": "签约单位",
    "FLEXIBLE": "用工单位",
    "FURTHER_STUDY": "升学院校",
    "STARTUP": "创业实体名称",
}


def _options(code: str) -> dict:
    req = _DESTINATION_REQUIREMENTS.get(code, {"requiredFields": [], "requiredMaterials": []})
    return {
        "code": code,
        "label": canonical.L_DEST[code],
        "companyLabel": _COMPANY_LABELS.get(code, "单位名称"),
        "requiredFields": list(req["requiredFields"]),
        "requiredMaterials": [
            {"code": m, "label": canonical.L_MATTYPE.get(m, m)} for m in req["requiredMaterials"]
        ],
    }


def destination_options(user: dict) -> dict:
    """SP-E03/SP-E10：服务端下发 canonical 去向选项与状态字典。

    前端据此渲染，不再自写业务枚举——canonical 新增去向/状态时学生端自动跟随，
    不会再出现"显示 raw code"或"与管理端不是同一套 code"。
    """
    _require_student(user)
    return {
        "destinationTypes": [_options(code) for code in _DESTINATION_CODES],
        # 两个独立状态字典分别下发，正是为了让前端无法把二者混为一谈（SP-E09）。
        "verifyStatuses": [{"code": k, "label": v} for k, v in canonical.L_VERIFY.items()],
        "materialStatuses": [{"code": k, "label": v} for k, v in canonical.L_MAT.items()],
        "materialTypes": [{"code": k, "label": v} for k, v in canonical.L_MATTYPE.items()],
        "helpLevels": [{"code": k, "label": v} for k, v in canonical.L_HELP.items()],
    }


def _latest_submission_summary(user: dict) -> dict | None:
    """SP-E02/E04：批准前 EmpStudent 可能根本不存在（原子写回只在批准那一刻发生），
    所以"我的就业"必须独立于 canonical 台账查一次最近一条提交——否则学生刚提交、
    甚至被退回，首页仍然显示"暂无就业记录"，看不出自己到底做没做过这件事。"""
    from app.modules.employment.services.employment_destination_submission_service import (
        list_my_submissions)

    with stu._session() as db:
        student = stu.resolve_student(db, user)
        if not student:
            return None
        sid = int(student.id)
    rows, _total = list_my_submissions(sid, page=1, page_size=1)
    return rows[0] if rows else None


def my(user: dict) -> dict:
    """我的就业（本人：去向/核验状态/材料/回访）。

    SP-E09/SP-E10：在 canonical 读端结果上补齐 label，并显式保持
    `verifyStatus`（去向核验）与 `materialStatus`（材料审核）两个独立事实——
    #183 之后教师端有独立的去向核验命令，学生端更不能拿材料状态去推核验状态。
    """
    latest_submission = _latest_submission_summary(user)
    data = stu.employment_my(user) or {}
    if not data.get("hasData"):
        data["latestSubmission"] = latest_submission
        return data

    destination_type = data.get("destinationType") or ""
    verify_status = data.get("verifyStatus") or ""
    material_status = data.get("materialStatus") or ""
    help_level = data.get("helpLevel") or ""

    data["destinationLabel"] = canonical.L_DEST.get(destination_type, destination_type or "")
    data["verifyStatusLabel"] = canonical.L_VERIFY.get(verify_status, verify_status or "")
    data["materialStatusLabel"] = canonical.L_MAT.get(material_status, material_status or "")
    data["helpLevelLabel"] = canonical.L_HELP.get(help_level, help_level or "")
    data["materials"] = [
        {
            **m,
            "typeLabel": canonical.L_MATTYPE.get(m.get("type") or "", m.get("type") or ""),
            "statusLabel": canonical.L_MAT.get(m.get("status") or "", m.get("status") or ""),
        }
        for m in (data.get("materials") or [])
    ]
    data["followUps"] = [
        {**f, "wayLabel": canonical.L_WAY.get(f.get("way") or "", f.get("way") or "")}
        for f in (data.get("followUps") or [])
    ]
    data["latestSubmission"] = latest_submission
    return data


def _clean(value) -> str:
    return str(value or "").strip()


#: 单字段进入工单正文的长度上限。CsWorkOrder.detail 是 String(1000)，六个字段
#: 各留 150 字加上标签仍安全落在上限内。
_FIELD_MAX = 150


def _field_text(value: str) -> str:
    if not value:
        return "—"
    return value if len(value) <= _FIELD_MAX else value[:_FIELD_MAX] + "…(已截断)"


def destination_register(user: dict, body: dict) -> dict:
    """就业去向登记（本人）。

    SP-E02/E04：改走结构化 `EmpDestinationSubmission` 模型 + 真实单节点审批
    （`employment_destination_submission_service`），不再拼自由文本工单——
    jobTitle/city/contact 现在是真正的类型化列，不再靠逐字段截断"尽量不丢"；
    批准后在同一事务原子写回 canonical `EmpStudent`。

    本轮同时修正的真实数据问题：
    - SP-E01：canonical 字段名是 `companyName`；旧 `unitName` 只作兼容别名，
      不再出现"学生填了单位、后端读不到"的静默丢失。
    - SP-E03：`destinationType` 必须是 canonical code，未知值直接拒绝，
      不再让学生端提交出管理端无法识别的 `FURTHER`/`MILITARY`。
    """
    # 权限必须先于入参校验：否则非学生调用者会拿到 VALIDATION_ERROR / allowed 枚举，
    # 等于把 canonical 去向字典泄漏给无权访问的人，还把 403 降级成 422。
    u = _require_student(user)
    body = body or {}
    dtype = _clean(body.get("destinationType"))
    if not dtype:
        raise AppException("VALIDATION_ERROR", "去向类型（destinationType）必填")
    if dtype not in canonical.L_DEST:
        raise AppException(
            "VALIDATION_ERROR",
            f"不支持的去向类型：{dtype}",
            details={"allowed": list(_DESTINATION_CODES)},
        )

    # companyName 是 canonical 名；unitName 是历史别名，短期兼容，优先取 canonical。
    company = _clean(body.get("companyName")) or _clean(body.get("unitName"))
    job_title = _clean(body.get("jobTitle"))
    city = _clean(body.get("city"))
    contact = _clean(body.get("contact"))
    remark = _clean(body.get("remark")) or _clean(body.get("reason"))

    required = _DESTINATION_REQUIREMENTS.get(dtype, {}).get("requiredFields") or []
    if "companyName" in required and not company:
        label = _COMPANY_LABELS.get(dtype, "单位名称")
        raise AppException("VALIDATION_ERROR", f"{canonical.L_DEST[dtype]}必须填写{label}")

    from app.modules.employment.services.employment_destination_submission_service import submit

    with stu._session() as db:
        student = stu.resolve_student(db, u)
        if not student:
            raise not_found("尚未建立你的学生档案，无法登记就业去向")
        student_id, student_name = int(student.id), student.real_name

    return submit(
        student_id=student_id, student_name=student_name, destination_type=dtype,
        company_name=company or "", job_title=job_title or "", city=city or "",
        contact=contact or "", remark=remark or "",
    )


def destination_print(user: dict, body: dict) -> dict:
    """就业去向登记表：生成真实 PDF（File Center fileId + sha256），并保留原有
    PORTAL_PRINT 审计留痕（两者不是互斥关系，审计证明"谁在什么时候打印过"，
    文件本身才是"打印了什么"）。

    SP-E08：此前这里只写审计留痕，没有生成任何真实文件——按钮"成功"却拿不到
    fileId/hash，不能证明文档确实存在。现在必须先建立就业档案（EmpStudent）
    才能生成登记表；文档内容如实打印当前核验状态，未核验不冒充已核验。
    """
    u = _require_student(user)
    from app.models import EmpStudent
    from app.modules.employment.services.employment_destination_document_service import (
        ensure_destination_document_in_tx,
    )

    with stu._session() as db:
        student = stu.resolve_student(db, u)
        if not student:
            raise not_found("尚未建立你的学生档案，无法生成登记表")
        emp = stu._resolve_domain_student(db, EmpStudent, student)
        if not emp:
            raise not_found("尚未登记就业去向，请先完成登记后再生成登记表")
        file_obj = ensure_destination_document_in_tx(db, emp)
        result = {
            "fileId": str(file_obj.id),
            "fileName": file_obj.file_name,
            "sha256": file_obj.sha256,
            "sizeBytes": int(file_obj.size_bytes or 0),
            "sourceVersion": int(emp.destination_document_source_version or 0),
        }
        db.commit()

    log = common.print_log(user, {"bizType": "EMPLOYMENT",
                                  "bizId": str((body or {}).get("bizId") or result["fileId"]),
                                  "docName": "就业去向登记表"})
    return {**log, **result}
