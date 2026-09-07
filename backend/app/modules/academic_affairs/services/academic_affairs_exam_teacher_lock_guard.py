"""考务监考/巡考教师时间线首建锁收口。

只替换公开考务 facade 的私有互斥锁 helper，不接管任何状态机、权限或业务写链。
AaExamTeacherLock 已存在时仍只锁该教师行；只有首建尚无锁行时，才短暂锁现有租户行，
把“查无记录 -> INSERT 锁行”串行化，避免两个事务同时 INSERT 导致 MySQL 1213，随后
SQLAlchemy 回滚已经被 MySQL 取消的 SAVEPOINT 又暴露 1305。
"""
from __future__ import annotations

from app.core.exceptions import AppException, not_found


def lock_teacher_timeline(db, teacher_key: str):
    from app.models import AaExamTeacherLock, Tenant
    from app.modules.academic_affairs.services import academic_affairs_exam_service as public_facade

    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "教师工号不能为空")
    tenant_id = int(public_facade._legacy._tid())

    def _query():
        return db.query(AaExamTeacherLock).filter(
            AaExamTeacherLock.tenant_id == tenant_id,
            AaExamTeacherLock.teacher_key == key,
            AaExamTeacherLock.is_deleted.is_(False),
        )

    lock_row = _query().with_for_update().first()
    if lock_row is not None:
        return lock_row

    # 首建没有可锁的 teacher row。锁租户这条稳定父记录，使同一租户下“首建锁行”
    # 顺序完成；下一次同教师操作会直接走上面的细粒度 teacher-row lock。
    tenant = db.query(Tenant.id).filter(
        Tenant.id == tenant_id,
        Tenant.is_deleted.is_(False),
    ).with_for_update().scalar()
    if tenant is None:
        raise not_found("学校不存在")

    # 等待父锁期间另一事务可能已经创建并提交该教师锁，必须在当前读下再检查一次。
    lock_row = _query().with_for_update().first()
    if lock_row is not None:
        return lock_row

    # 不使用 begin_nested/savepoint：首建路径已经由稳定父行串行，不需要靠唯一键异常竞争。
    lock_row = AaExamTeacherLock(tenant_id=tenant_id, teacher_key=key)
    db.add(lock_row)
    db.flush()
    return lock_row


def install(public_facade) -> None:
    """安装私有并发 helper；公开函数 owner 仍保持 academic_affairs_exam_facade。"""
    public_facade._lock_teacher_timeline = lock_teacher_timeline
