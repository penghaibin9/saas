"""School role ledger: filter, aggregate and page in MySQL before hydrating rows."""
from datetime import timedelta

from sqlalchemy import and_, case, exists, func, literal, select, union_all

from app.core.exceptions import AppException
from app.models import Role, User, UserRole
from app.models.role_assignment import RoleAssignmentValidity as Validity


def list_page(db, *, tenant_id, now, role_code, bucket, page, page_size):
    from app.services import role_assignment_service as rules

    link_join = and_(UserRole.id == Validity.user_role_id,
                     UserRole.tenant_id == tenant_id, UserRole.is_deleted.is_(False))
    registered = select(
        literal(0).label('kind'), Validity.id.label('id'),
        Validity.user_id.label('user_id'), Validity.role_code.label('role_code'),
        Validity.status.label('status'), func.coalesce(UserRole.status, '').label('link_status'),
        Validity.expires_at.label('expires_at'), Validity.source_type.label('source_type'),
        Validity.last_reviewed_at.label('reviewed_at'),
    ).outerjoin(UserRole, link_join).where(
        Validity.tenant_id == tenant_id, Validity.is_deleted.is_(False))
    # Determine registration before role filtering, so another role's registered
    # link cannot reappear as an unregistered historical authorization.
    has_registration = exists(select(Validity.id).where(
        Validity.tenant_id == tenant_id, Validity.user_role_id == UserRole.id,
        Validity.is_deleted.is_(False)))
    legacy = select(
        literal(1).label('kind'), UserRole.id.label('id'),
        UserRole.user_id.label('user_id'), func.coalesce(Role.role_code, '').label('role_code'),
        literal('ACTIVE').label('status'), UserRole.status.label('link_status'),
        literal(None).label('expires_at'), literal('UNKNOWN').label('source_type'),
        literal(None).label('reviewed_at'),
    ).outerjoin(Role, and_(Role.id == UserRole.role_id, Role.tenant_id == tenant_id,
                          Role.is_deleted.is_(False))).where(
        UserRole.tenant_id == tenant_id, UserRole.is_deleted.is_(False),
        UserRole.status == 'ACTIVE', ~has_registration)
    all_rows = union_all(registered, legacy).subquery('assignment_rows')
    scoped = select(all_rows)
    code = str(role_code or '').strip().upper()
    if code:
        scoped = scoped.where(all_rows.c.role_code == code)
    rows = scoped.subquery('school_assignments')
    c = rows.c
    filters = {
        rules.BUCKET_EXPIRING_SOON: and_(c.status == 'ACTIVE', c.expires_at.is_not(None),
                                        c.expires_at <= now + timedelta(days=rules.EXPIRING_SOON_DAYS)),
        rules.BUCKET_EXPIRED_NOT_RECLAIMED: and_(c.status == 'EXPIRED', c.link_status == 'ACTIVE'),
        rules.BUCKET_UNREVIEWED: and_(c.status == 'ACTIVE', c.expires_at.is_(None), c.reviewed_at.is_(None)),
        rules.BUCKET_UNKNOWN_SOURCE: c.source_type == 'UNKNOWN',
    }
    high_roles = select(c.role_code).where(
        c.role_code.in_(sorted(rules.HIGH_PRIVILEGE_ROLES)), c.status == 'ACTIVE',
    ).group_by(c.role_code).having(func.count(func.distinct(c.user_id)) > 1).subquery('multi_holder_roles')
    summary_row = db.execute(select(
        func.count().label('total'),
        *(func.coalesce(func.sum(case((predicate, 1), else_=0)), 0).label(key)
          for key, predicate in filters.items()),
    ).select_from(rows)).one()._mapping
    summary = {key: int(summary_row[key]) for key in filters}
    summary[rules.BUCKET_HIGH_PRIV_MULTI] = int(db.scalar(select(func.count()).select_from(high_roles)) or 0)
    filters[rules.BUCKET_HIGH_PRIV_MULTI] = and_(
        c.status == 'ACTIVE', c.role_code.in_(select(high_roles.c.role_code)))
    if bucket and bucket not in filters:
        raise AppException('VALIDATION_ERROR', f'未知的分类：{bucket}')
    predicate = filters.get(bucket)
    total = int(summary_row['total'])
    query = select(c.kind, c.id).select_from(rows)
    if predicate is not None:
        query = query.where(predicate)
        total = int(db.scalar(select(func.count()).select_from(rows).where(predicate)) or 0)
    keys = list(db.execute(query.order_by(c.kind, c.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    items = {}
    valid_ids = [row.id for row in keys if row.kind == 0]
    legacy_ids = [row.id for row in keys if row.kind == 1]
    if valid_ids:
        detail_query = select(Validity, UserRole.role_id, func.coalesce(Role.role_name, ''),
                              func.coalesce(UserRole.status, ''), func.coalesce(User.login_name, ''),
                              func.coalesce(User.real_name, '')).outerjoin(
            UserRole, link_join).outerjoin(Role, and_(Role.id == UserRole.role_id,
            Role.tenant_id == tenant_id, Role.is_deleted.is_(False))).outerjoin(User, and_(User.id == Validity.user_id,
            User.tenant_id == tenant_id, User.is_deleted.is_(False))).where(
            Validity.tenant_id == tenant_id, Validity.id.in_(valid_ids), Validity.is_deleted.is_(False))
        for row, role_id, role_name, status, login, name in db.execute(detail_query):
            items[(0, row.id)] = {**rules._row_dto(row, status, login, name, now=now),
                                  'roleId': str(role_id) if role_id is not None else '',
                                  'roleName': role_name}
    if legacy_ids:
        detail_query = select(UserRole, func.coalesce(Role.role_code, ''), func.coalesce(Role.role_name, ''),
                              func.coalesce(User.login_name, ''), func.coalesce(User.real_name, '')).outerjoin(
            Role, and_(Role.id == UserRole.role_id, Role.tenant_id == tenant_id, Role.is_deleted.is_(False))).outerjoin(
            User, and_(User.id == UserRole.user_id, User.tenant_id == tenant_id, User.is_deleted.is_(False))).where(
            UserRole.tenant_id == tenant_id, UserRole.id.in_(legacy_ids), UserRole.is_deleted.is_(False))
        for link, role, role_name, login, name in db.execute(detail_query):
            items[(1, link.id)] = {
                'assignmentId': '', 'userRoleId': str(link.id), 'userId': str(link.user_id),
                'roleId': str(link.role_id),
                'loginName': login, 'realName': name, 'roleCode': role, 'roleName': role_name,
                'status': 'ACTIVE', 'linkStatus': str(link.status or ''),
                'effectiveAt': str(link.created_at or '')[:19], 'expiresAt': '', 'daysLeft': None,
                'sourceType': 'UNKNOWN', 'sourceId': '', 'reason': '', 'grantedBy': '',
                'lastReviewedAt': '', 'lastReviewedTerm': '', 'transferredToUserId': '', 'version': int(link.version or 0),
            }
    return {'list': [items[(row.kind, row.id)] for row in keys if (row.kind, row.id) in items],
            'total': total, 'page': page, 'pageSize': page_size, 'summary': summary}
