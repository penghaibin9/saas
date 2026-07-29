"""阶段 2：真实 MySQL 对象级授权验收。"""
from __future__ import annotations

import os

from sqlalchemy import delete

TENANT_ID = 990000000000000125
OTHER_TENANT_ID = 990000000000000126
OWNER_ID = 990000000000000127


def assert_hidden(callable_) -> None:
    from app.core.exceptions import AppException

    try:
        callable_()
    except AppException as exc:
        assert exc.http_status == 404, (exc.code, exc.http_status, exc.message)
        assert exc.code == "DATA_NOT_FOUND"
    else:
        raise AssertionError("expected resource-hiding 404")


def cleanup() -> None:
    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding, FileObject

    db = get_sessionmaker()()
    try:
        db.execute(delete(FileBinding).where(FileBinding.tenant_id.in_([TENANT_ID, OTHER_TENANT_ID])))
        db.execute(delete(FileObject).where(FileObject.tenant_id.in_([TENANT_ID, OTHER_TENANT_ID])))
        db.commit()
    finally:
        db.close()


def seed() -> tuple[str, str]:
    from app.db.session import get_sessionmaker
    from app.models.file import FileBinding, FileObject

    db = get_sessionmaker()()
    try:
        student_file = FileObject(
            tenant_id=TENANT_ID,
            file_key="stage2/student.pdf",
            file_name="学生材料.pdf",
            ext="pdf",
            mime_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            biz_type="GRADUATION_MATERIAL",
            biz_id="GD-100",
            owner_user_id=OWNER_ID,
            visibility="BIZ_SCOPED",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        batch_file = FileObject(
            tenant_id=TENANT_ID,
            file_key="stage2/batch.pdf",
            file_name="批次材料.pdf",
            ext="pdf",
            mime_type="application/pdf",
            size_bytes=10,
            sha256="b" * 64,
            biz_type="GRADUATION_MATERIAL",
            biz_id="GD-BATCH-1",
            owner_user_id=OWNER_ID,
            visibility="BIZ_SCOPED",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add_all([student_file, batch_file])
        db.flush()
        db.add_all([
            FileBinding(
                tenant_id=TENANT_ID,
                file_id=student_file.id,
                biz_type="GRADUATION_MATERIAL",
                biz_id="GD-100",
                relation_type="ATTACHMENT",
                subject_type="STUDENT",
                subject_id="S-100",
                version_no=1,
                is_current=True,
                status="ACTIVE",
            ),
            FileBinding(
                tenant_id=TENANT_ID,
                file_id=batch_file.id,
                biz_type="GRADUATION_MATERIAL",
                biz_id="GD-BATCH-1",
                relation_type="ATTACHMENT",
                subject_type="BUSINESS_OBJECT",
                batch_id="B-100",
                version_no=1,
                is_current=True,
                status="ACTIVE",
            ),
        ])
        db.commit()
        return str(student_file.id), str(batch_file.id)
    finally:
        db.close()


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    from app.core.context import set_current_user, set_tenant
    from app.services import file_access_resolvers as _file_access_resolvers  # noqa: F401
    from app.services.file_access_service import require_file_access

    cleanup()
    try:
        set_tenant({"tenantId": TENANT_ID, "tenantCode": "file-access-stage2"})
        student_file_id, batch_file_id = seed()

        allowed_student = {
            "userId": 1001,
            "userType": "STUDENT",
            "studentNo": "S-100",
            "permissions": [],
        }
        set_current_user(allowed_student)
        assert require_file_access(student_file_id, user=allowed_student, action="meta").id

        other_student = {
            "userId": 1002,
            "userType": "STUDENT",
            "studentNo": "S-200",
            "permissions": [],
        }
        assert_hidden(lambda: require_file_access(student_file_id, user=other_student, action="meta"))

        allowed_batch = {
            "userId": 2001,
            "userType": "TEACHER",
            "allowedBatchIds": ["B-100"],
            "permissions": ["graduationDesign.view"],
        }
        set_current_user(allowed_batch)
        assert require_file_access(batch_file_id, user=allowed_batch, action="meta").id

        other_batch = {
            "userId": 2002,
            "userType": "TEACHER",
            "allowedBatchIds": ["B-200"],
            "permissions": ["graduationDesign.view"],
        }
        assert_hidden(lambda: require_file_access(batch_file_id, user=other_batch, action="meta"))

        no_scope = {
            "userId": 2003,
            "userType": "TEACHER",
            "permissions": ["graduationDesign.view"],
        }
        assert_hidden(lambda: require_file_access(batch_file_id, user=no_scope, action="meta"))

        no_permission = {
            "userId": 2004,
            "userType": "TEACHER",
            "allowedBatchIds": ["B-100"],
            "permissions": [],
        }
        assert_hidden(lambda: require_file_access(batch_file_id, user=no_permission, action="meta"))

        set_tenant({"tenantId": OTHER_TENANT_ID, "tenantCode": "other-school"})
        assert_hidden(lambda: require_file_access(student_file_id, user=allowed_student, action="meta"))

        print("Stage 2 MySQL access acceptance passed")
    finally:
        set_tenant({"tenantId": TENANT_ID, "tenantCode": "file-access-stage2"})
        cleanup()
        set_current_user(None)
        set_tenant(None)


if __name__ == "__main__":
    main()
