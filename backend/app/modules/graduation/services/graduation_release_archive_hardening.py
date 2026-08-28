"""Graduation archive exact-batch reconciliation and material resolver hardening."""
from __future__ import annotations
from sqlalchemy import func, or_, select
from app.core.context import get_current_user_ctx
from app.models import GraduationArchiveRecord, GraduationStudent
from app.services.db_service import _tid, session
from app.modules.graduation.services.graduation_release_hardening_common import _student_scope_select


def _install_archive_hardening() -> None:
    from app.modules.graduation.services import graduation_archive_read_service as read
    from app.modules.graduation.services import graduation_archive_service as archive
    from app.modules.graduation.services import graduation_service as legacy
    from app.modules.graduation.services import graduation_material_center_service as material_v2

    def query_parts(db, tid, *, keyword=None, status=None, batch_id=None, archive_batch_no=None):
        scope_q = _student_scope_select(db, tid, batch_id=batch_id)
        filters = [GraduationArchiveRecord.tenant_id == tid, GraduationArchiveRecord.is_deleted.is_(False), GraduationStudent.tenant_id == tid, GraduationStudent.is_deleted.is_(False), GraduationStudent.record_status == "ACTIVE", GraduationStudent.id.in_(scope_q)]
        if batch_id: filters.append(GraduationStudent.batch_id == int(batch_id))
        if status: filters.append(GraduationArchiveRecord.status == status)
        if archive_batch_no: filters.append(GraduationArchiveRecord.archive_batch_no == str(archive_batch_no))
        value = str(keyword or "").strip()
        if value: filters.append(or_(GraduationStudent.name.contains(value), GraduationStudent.student_no.contains(value)))
        return GraduationStudent.id == GraduationArchiveRecord.gd_student_id, filters

    def list_archives(page, page_size, keyword=None, status=None, batch_id=None, archive_batch_no=None):
        # The HTTP router caps pageSize at 200. Internal exporters may request a
        # larger page and must not silently truncate while still reporting total.
        tid = _tid(); p = max(1, int(page)); size = max(1, int(page_size))
        with session() as db:
            join_on, filters = query_parts(db, tid, keyword=keyword, status=status, batch_id=batch_id, archive_batch_no=archive_batch_no)
            total = int(db.scalar(select(func.count(func.distinct(GraduationArchiveRecord.id))).select_from(GraduationArchiveRecord).join(GraduationStudent, join_on).where(*filters)) or 0)
            rows = db.execute(select(GraduationArchiveRecord, GraduationStudent).join(GraduationStudent, join_on).where(*filters).order_by(GraduationArchiveRecord.id.desc()).offset((p-1)*size).limit(size)).all()
            return [read._row(a, s) for a, s in rows], total

    def resolve_material_download(file_id):
        # V2 resolver is the authorization authority and returns (FileObject, Path).
        # The legacy HTTP download contract expects (Path, filename).
        file_obj, path = material_v2.resolve_material_download(file_id, get_current_user_ctx() or {})
        filename = str(getattr(file_obj, "file_name", None) or getattr(path, "name", ""))
        return path, filename

    read.list_archives = list_archives
    archive.list_archives = list_archives
    legacy.resolve_material_download = resolve_material_download
