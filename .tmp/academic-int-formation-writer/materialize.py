from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"exact replacement guard failed for {path}: count={text.count(old)}")
    p.write_text(text.replace(old, new))


# 1) Public request DTOs: direct ProgramCourse formation must be explicit.
replace(
    "backend/app/modules/academic_affairs/routers/academic_affairs.py",
    '''class ProgramCourseBody(BaseModel):\n    courseId: Optional[str] = None\n    courseName: str = Field(..., min_length=1)\n    openTermNo: Optional[int] = None\n    module: Optional[str] = None\n    credit: Optional[float] = Field(None, ge=0)\n''',
    '''class ProgramCourseBody(BaseModel):\n    courseId: Optional[str] = None\n    courseName: str = Field(..., min_length=1)\n    openTermNo: Optional[int] = None\n    module: Optional[str] = None\n    credit: Optional[float] = Field(None, ge=0)\n    formationMode: str = Field(..., min_length=1, description="ADMIN_FIXED 行政班固定 / SELECTABLE 选课形成")\n''',
)
replace(
    "backend/app/modules/academic_affairs/routers/academic_affairs.py",
    '''class ProgramCourseUpdate(BaseModel):\n    courseName: Optional[str] = None\n    openTermNo: Optional[int] = None\n    module: Optional[str] = None\n    credit: Optional[float] = Field(None, ge=0)\n''',
    '''class ProgramCourseUpdate(BaseModel):\n    courseName: Optional[str] = None\n    openTermNo: Optional[int] = None\n    module: Optional[str] = None\n    credit: Optional[float] = Field(None, ge=0)\n    formationMode: Optional[str] = None\n''',
)

# 2) Canonical direct-mode policy. Special modes remain owned by dedicated provenance flows.
policy = Path("backend/app/modules/academic_affairs/services/academic_affairs_program_course_formation_policy.py")
if policy.exists():
    raise SystemExit(f"refuse overwrite existing {policy}")
policy.write_text('''"""Canonical formation policy for ordinary ProgramCourse writes.\n\nThe shared schema supports five modes, but the ordinary training-program editor owns\nonly ADMIN_FIXED and SELECTABLE. MERGED/RETAKE/LAYERED require dedicated,\nauditable provenance flows and must never be guessed or accepted by generic CRUD.\n"""\nfrom __future__ import annotations\n\nfrom app.core.exceptions import AppException\n\nDIRECT_FORMATION_MODES = frozenset({"ADMIN_FIXED", "SELECTABLE"})\nSPECIAL_FORMATION_MODES = frozenset({"MERGED", "RETAKE", "LAYERED"})\nALL_FORMATION_MODES = DIRECT_FORMATION_MODES | SPECIAL_FORMATION_MODES\n\n\ndef normalize_direct_mode(value) -> str:\n    mode = str(value or "").strip().upper()\n    if not mode:\n        raise AppException(\n            "FORMATION_MODE_REQUIRED",\n            "课程必须明确选择编班方式：行政班固定或选课形成",\n            http_status=409,\n        )\n    if mode not in DIRECT_FORMATION_MODES:\n        raise AppException(\n            "FORMATION_MODE_NOT_DIRECT",\n            f"普通培养方案课程不可直接使用编班方式 {mode or 'NULL'}",\n            details={"formationMode": mode or None, "allowed": sorted(DIRECT_FORMATION_MODES)},\n            http_status=409,\n        )\n    return mode\n\n\ndef assert_program_courses_direct(rows, *, program_id: int | None = None) -> None:\n    debts = []\n    for row in rows:\n        mode = str(getattr(row, "formation_mode", None) or "").strip().upper()\n        if mode not in DIRECT_FORMATION_MODES:\n            debts.append({\n                "programCourseId": str(getattr(row, "id", "")),\n                "formationMode": mode or None,\n                "reason": "MISSING" if not mode else "SPECIAL_OR_INVALID",\n            })\n    if debts:\n        raise AppException(\n            "PROGRAM_FORMATION_BLOCKED",\n            "培养方案存在未明确或非普通来源的编班方式，不能提交或生成教学任务",\n            details={"programId": str(program_id) if program_id is not None else None, "debts": debts[:50]},\n            http_status=409,\n        )\n''')

# 3) ProgramCourse persistence/read/update uses the canonical direct policy, never defaults.
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''from app.services.db_service import _iso, _tid, session\n''',
    '''from app.services.db_service import _iso, _tid, session\n\nfrom . import academic_affairs_program_course_formation_policy as formation_policy\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''        c = AaProgramCourse(tenant_id=_tid(), program_id=p.id,\n                            course_id=(int(body.courseId) if getattr(body, "courseId", None) else None),\n                            course_name=getattr(body, "courseName", None),\n                            open_term_no=getattr(body, "openTermNo", None),\n                            module=getattr(body, "module", None),\n                            credit_snapshot=getattr(body, "credit", None))\n''',
    '''        formation_mode = formation_policy.normalize_direct_mode(getattr(body, "formationMode", None))\n        c = AaProgramCourse(tenant_id=_tid(), program_id=p.id,\n                            course_id=(int(body.courseId) if getattr(body, "courseId", None) else None),\n                            course_name=getattr(body, "courseName", None),\n                            open_term_no=getattr(body, "openTermNo", None),\n                            module=getattr(body, "module", None),\n                            credit_snapshot=getattr(body, "credit", None),\n                            formation_mode=formation_mode)\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''        return {"programCourseId": str(c.id), "programId": str(program_id),\n                "courseName": c.course_name or ""}\n''',
    '''        return {"programCourseId": str(c.id), "programId": str(program_id),\n                "courseName": c.course_name or "", "formationMode": c.formation_mode}\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''        d["courses"] = [{"programCourseId": str(c.id), "courseName": c.course_name or "",\n                         "openTermNo": c.open_term_no, "module": c.module or "",\n                         "credit": c.credit_snapshot} for c in courses]\n''',
    '''        d["courses"] = [{"programCourseId": str(c.id), "courseName": c.course_name or "",\n                         "openTermNo": c.open_term_no, "module": c.module or "",\n                         "credit": c.credit_snapshot, "formationMode": c.formation_mode} for c in courses]\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''        if getattr(body, "credit", None) is not None:\n            c.credit_snapshot = body.credit\n        _audit(db, p.id, "UPDATE_COURSE", c.course_name or "")\n''',
    '''        if getattr(body, "credit", None) is not None:\n            c.credit_snapshot = body.credit\n        fields_set = set(getattr(body, "model_fields_set", set()) or set())\n        if "formationMode" in fields_set:\n            c.formation_mode = formation_policy.normalize_direct_mode(getattr(body, "formationMode", None))\n        _audit(db, p.id, "UPDATE_COURSE", c.course_name or "")\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_core_service.py",
    '''        return {"programCourseId": str(c.id), "programId": str(c.program_id), "courseName": c.course_name or "",\n                "openTermNo": c.open_term_no, "module": c.module or "", "credit": c.credit_snapshot}\n''',
    '''        return {"programCourseId": str(c.id), "programId": str(c.program_id), "courseName": c.course_name or "",\n                "openTermNo": c.open_term_no, "module": c.module or "", "credit": c.credit_snapshot,\n                "formationMode": c.formation_mode}\n''',
)

# 4) Public submit must fail closed on historical NULL/special rows before approval state transition.
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_service.py",
    '''from . import academic_affairs_program_core_service as _core\nfrom . import academic_affairs_program_governance_service as governance\n''',
    '''from . import academic_affairs_program_core_service as _core\nfrom . import academic_affairs_program_course_formation_policy as formation_policy\nfrom . import academic_affairs_program_governance_service as governance\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_program_service.py",
    '''        validation = governance.validate_program_db(db, program.id)\n''',
    '''        from app.models import AaProgramCourse\n        courses = db.query(AaProgramCourse).filter(\n            AaProgramCourse.tenant_id == _tid(),\n            AaProgramCourse.program_id == program.id,\n            AaProgramCourse.is_deleted.is_(False),\n        ).all()\n        formation_policy.assert_program_courses_direct(courses, program_id=program.id)\n\n        validation = governance.validate_program_db(db, program.id)\n''',
)

# 5) Task generation must persist the exact ProgramCourse formation mode and refuse debt.
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py",
    '''from . import academic_affairs_program_activation_service as program_activation\nfrom . import academic_affairs_task_core_service as core\n''',
    '''from . import academic_affairs_program_activation_service as program_activation\nfrom . import academic_affairs_program_course_formation_policy as formation_policy\nfrom . import academic_affairs_task_core_service as core\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py",
    '''                for program_course in courses:\n                    try:\n                        open_term_no = int(program_course.open_term_no)\n''',
    '''                for program_course in courses:\n                    formation_mode = formation_policy.normalize_direct_mode(program_course.formation_mode)\n                    try:\n                        open_term_no = int(program_course.open_term_no)\n''',
)
replace(
    "backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py",
    '''                        total_hours=total_hours, weekly_hours=weekly_hours,\n                        start_week=1, end_week=teaching_weeks, status="PENDING_ASSIGN",\n''',
    '''                        total_hours=total_hours, weekly_hours=weekly_hours,\n                        formation_mode=formation_mode,\n                        start_week=1, end_week=teaching_weeks, status="PENDING_ASSIGN",\n''',
)

# 6) PC editor requires an explicit two-mode choice and sends it in the canonical payload.
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''            <input v-model.trim="addForm.module" class="aa-input aa-input--sm" placeholder="课程模块" />\n            <AppButton variant="primary" :disabled="!canAddCourse" :loading="adding" @click="addCourse">添加</AppButton>\n''',
    '''            <input v-model.trim="addForm.module" class="aa-input aa-input--sm" placeholder="课程模块" />\n            <select v-model="addForm.formationMode" class="aa-input aa-input--sm" aria-label="编班方式">\n              <option value="" disabled>选择编班方式</option>\n              <option value="ADMIN_FIXED">行政班固定</option>\n              <option value="SELECTABLE">选课形成</option>\n            </select>\n            <AppButton variant="primary" :disabled="!canAddCourse" :loading="adding" @click="addCourse">添加</AppButton>\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''            <thead><tr><th>学期</th><th>模块</th><th>课程</th><th>学分</th><th>校验</th></tr></thead>\n''',
    '''            <thead><tr><th>学期</th><th>模块</th><th>课程</th><th>编班方式</th><th>学分</th><th>校验</th></tr></thead>\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''                <td>{{ course.courseName || '未命名课程' }}</td>\n                <td>{{ course.credit ?? '未设置' }}</td>\n''',
    '''                <td>{{ course.courseName || '未命名课程' }}</td>\n                <td>{{ course.formationMode === 'SELECTABLE' ? '选课形成' : course.formationMode === 'ADMIN_FIXED' ? '行政班固定' : '未明确' }}</td>\n                <td>{{ course.credit ?? '未设置' }}</td>\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''      addForm: { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' },\n''',
    '''      addForm: { courseId: '', courseName: '', credit: null, openTermNo: null, module: '', formationMode: '' },\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''    canAddCourse() { return Boolean(this.addForm.courseId && this.addForm.openTermNo && this.addForm.module) }\n''',
    '''    canAddCourse() { return Boolean(this.addForm.courseId && this.addForm.openTermNo && this.addForm.module && this.addForm.formationMode) }\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''        openTermNo: this.addForm.openTermNo,\n        module: this.addForm.module\n''',
    '''        openTermNo: this.addForm.openTermNo,\n        module: this.addForm.module,\n        formationMode: this.addForm.formationMode\n''',
)
replace(
    "frontend/src/modules/academicAffairs/views/AaProgramEditorView.vue",
    '''        this.addForm = { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' }\n''',
    '''        this.addForm = { courseId: '', courseName: '', credit: null, openTermNo: null, module: '', formationMode: '' }\n''',
)
