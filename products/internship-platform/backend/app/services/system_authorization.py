"""数据库裁定的当前身份权限；安装过程显式运行，读取请求不隐式授权。"""
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import no_permission, unauthorized
from app.models import Permission, Role, RolePermission, UserRole, Tenant

SYSTEM_RESOURCES = {
    'overview': '管理概览', 'org': '组织架构', 'staff': '教职工资料', 'student': '学生资料',
    'account': '用户账号', 'role': '角色与权限', 'scope': '责任范围', 'brand': '学校资料',
    'dictionary': '基础字典', 'leave-policy': '请假审批配置', 'notification': '通知与服务',
    'identity-import': '师生开户', 'task': '导入导出任务', 'migration': '历史迁移',
    'integration': '外部对接', 'audit': '操作审计', 'runtime': '运行与备份', 'delivery': '交付资料',
}
SYSTEM_PERMISSIONS = {f'system.{key}.view': f'查看{label}' for key, label in SYSTEM_RESOURCES.items()}
SYSTEM_PERMISSIONS.update({f'system.{key}.manage': f'维护{label}' for key, label in SYSTEM_RESOURCES.items()
                           if key not in {'overview', 'task', 'audit', 'runtime'}})
SYSTEM_PERMISSIONS.update({'system.account.reset': '受控重置账号密码',
                           'system.role.grant-business': '授予校内实习业务权限',
                           'system.role.grant-admin': '授予校内系统管理权限',
                           'system.person.sensitive': '查看完整联系方式',
                           'system.person.export': '导出组织与人员资料',
                           'system.audit.export': '导出操作审计'})
ROLE_NAMES = {'SYSTEM_ADMIN': '学校系统管理员', 'SCHOOL_ADMIN': '校级实习管理员',
              'COLLEGE_ADMIN': '院系实习管理员', 'PROFESSIONAL_LEADER': '专业负责人',
              'MAJOR_LEADER': '专业负责人', 'COUNSELOR': '班主任／辅导员', 'INTERN_MENTOR': '实习指导教师',
              'LEADER': '督导／领导', 'SECURITY_AUDITOR': '安全审计员', 'STUDENT': '学生'}

# Presentation names describe existing commands; they never grant permissions.
_BUSINESS_OBJECTS = {
    'agreement': '实习协议', 'agreement.template': '协议模板', 'application': '实习申请',
    'archive': '实习归档', 'attendance': '实习考勤', 'batch': '实习批次', 'change': '实习变更',
    'communication': '通知与沟通', 'complaint': '意见反馈', 'compliance': '上岗核验',
    'compliance.exempt': '上岗材料豁免', 'consent': '知情确认', 'dashboard': '实习工作台',
    'employment': '就业上报', 'employment.sensitive': '就业上报完整敏感信息',
    'enterprise': '实习企业', 'enterprise.contact': '企业联系人', 'enterprise.inspection': '企业考察',
    'enterprise.mentor': '企业导师', 'eval.advisor': '指导教师评价', 'eval.enterprise': '企业评价',
    'eval.self': '学生自评', 'evaluation': '实习评价汇总', 'evidence': '实习证据包',
    'filing': '特殊情形备案', 'guidance': '实习指导', 'incident': '实习事故', 'insurance': '实习保险',
    'leave': '实习请假', 'makeup': '补卡申请', 'match': '学生岗位匹配', 'match.conflict': '岗位匹配冲突',
    'match.intention': '学生岗位意向', 'match.log': '岗位分配记录', 'match.result': '岗位匹配结果',
    'material': '实习材料', 'payroll': '实习报酬', 'plan': '实习计划', 'position': '实习岗位',
    'recruitment': '招聘活动', 'report': '实习报告', 'reporting': '监管报送', 'risk': '实习风险',
    'rotation': '实习轮岗', 'safety': '实习安全', 'score': '实习成绩', 'score.config': '成绩计算规则',
    'stats': '实习统计', 'student': '实习学生', 'student.eligibility': '学生实习资格',
    'student.material': '学生实习材料', 'student.password': '学生登录密码', 'task': '实习计划任务',
    'visit': '实习巡访', 'visit.location': '巡访精确位置', 'visit.plan': '巡访计划',
}
_ACTIONS = {'view': '查看', 'manage': '维护', 'review': '审核', 'export': '导出', 'import': '导入',
    'publish': '发布', 'sign': '签署', 'execute': '执行', 'force': '强制执行', 'package': '生成',
    'revoke': '撤销', 'intake': '登记', 'sensitive': '查看完整敏感信息：', 'request': '申请',
    'approve': '审批', 'close': '关闭', 'handle': '处置', 'report': '上报', 'verify': '核验',
    'batch': '批量执行', 'manual': '人工调整', 'invite': '发送邀请：', 'reset': '受控重置'}


def permission_name(code, stored='未登记名称的权限'):
    if code in SYSTEM_PERMISSIONS:
        return SYSTEM_PERMISSIONS[code]
    parts = str(code).split('.')
    obj = _BUSINESS_OBJECTS.get('.'.join(parts[1:-1])) if parts[0] == 'internship' else None
    action = _ACTIONS.get(parts[-1])
    return action + obj if obj and action else stored


def active_roles(db, tenant_id, user_id):
    return db.scalars(select(Role).join(UserRole, UserRole.role_id == Role.id).where(
        Role.tenant_id == tenant_id, Role.status == 'ACTIVE', Role.is_deleted.is_(False),
        UserRole.tenant_id == tenant_id, UserRole.user_id == user_id,
        UserRole.status == 'ACTIVE', UserRole.is_deleted.is_(False)).order_by(UserRole.id)).all()


def role_permissions(db, role):
    return list(db.scalars(select(Permission.permission_code).join(RolePermission,
        RolePermission.permission_id == Permission.id).where(RolePermission.tenant_id == role.tenant_id,
        RolePermission.role_id == role.id, RolePermission.status == 'ACTIVE',
        RolePermission.is_deleted.is_(False))))


def authorize_subject(db, account, claims):
    school = db.get(Tenant, account.tenant_id)
    if not school or school.is_deleted or school.status != 'ACTIVE':
        raise unauthorized('学校已停用，请联系学校管理员')
    if account.expires_at and account.expires_at <= datetime.utcnow():
        raise unauthorized('账号有效期已结束，请联系学校管理员')
    current = str(claims.get('currentRoleCode') or claims.get('roleCode') or '').upper()
    role = next((r for r in active_roles(db, account.tenant_id, account.id) if r.role_code == current), None)
    if not role:
        raise unauthorized('当前身份已撤销或停用，请重新登录选择有效身份')
    claims.update(permissions=role_permissions(db, role), currentRoleName=role.role_name,
                  currentRoleBaseCode=role.base_role_code or role.role_code,
                  permissionVersion=f'{role.id}:{role.version}:{account.version}', roleId=str(role.id))
    return claims


def audit(db, user, action, resource, object_id, detail=None, *, result='SUCCESS'):
    from app.models import SecurityAuditLog
    raw = str(user.get('userId') or '').removeprefix('db-')
    db.add(SecurityAuditLog(tenant_id=int(user['tenantId']), operator_id=int(raw) if raw.isdigit() else None,
        operator_name=user.get('realName'), current_role=user.get('currentRoleCode'), action=action,
        resource=resource, resource_id=str(object_id), result=result, detail_json={**(detail or {}),
            'identityName':user.get('currentRoleName') or ROLE_NAMES.get(user.get('currentRoleCode'),'')}))


def preset_role_patterns():
    """Current installation defaults, also used for read-only school comparisons."""
    from app.core.permissions import ROLE_PERMISSIONS
    presets = {**ROLE_PERMISSIONS, 'SYSTEM_ADMIN': set(SYSTEM_PERMISSIONS),
               'SECURITY_AUDITOR': {'system.audit.view', 'system.audit.export'}}
    presets['COLLEGE_ADMIN'] = set(presets['COLLEGE_ADMIN']) | {
        'system.overview.view', 'system.org.view', 'system.org.manage',
        'system.staff.view', 'system.staff.manage', 'system.student.view', 'system.student.manage',
        'system.account.view', 'system.identity-import.view', 'system.identity-import.manage',
        'system.task.view', 'system.person.export'}
    return presets


def bootstrap_school(db, tenant_id):
    """安装时创建预配身份；已经初始化的学校保持其本地配置。"""
    from app.models import SchoolSetting, User
    school = db.scalar(select(Tenant).where(Tenant.id == tenant_id).with_for_update())
    if not school:
        raise no_permission('学校不存在')
    if db.scalar(select(SchoolSetting).where(SchoolSetting.tenant_id == tenant_id,
                                            SchoolSetting.setting_key == 'authorization-installed')):
        return
    permissions = {p.permission_code: p for p in db.scalars(select(Permission))}
    presets = preset_role_patterns()
    for code in set().union(*presets.values()):
        if code not in permissions:
            p = Permission(permission_code=code, permission_name=permission_name(code),
                           module_code=code.split('.')[0])
            db.add(p); db.flush(); permissions[code] = p
    roles = {r.role_code: r for r in db.scalars(select(Role).where(Role.tenant_id == tenant_id))}
    for code, label in ROLE_NAMES.items():
        if code not in roles:
            r = Role(tenant_id=tenant_id, role_code=code, role_name=label, role_type='SYSTEM',
                     base_role_code=code, status='ACTIVE')
            db.add(r); db.flush(); roles[code] = r
    for role in roles.values():
        role.base_role_code = role.base_role_code or role.role_code
        existing = set(db.scalars(select(RolePermission.permission_id).where(
            RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id)))
        from app.core.permissions import _matches
        codes = {code for code in permissions if '*' not in code and any(
            _matches(pattern, code) for pattern in presets.get(role.role_code, set()))}
        for code in codes:
            if permissions[code].id not in existing:
                db.add(RolePermission(tenant_id=tenant_id, role_id=role.id,
                                      permission_id=permissions[code].id, status='ACTIVE'))
    administrators = db.scalars(select(User).where(User.tenant_id == tenant_id,
        User.user_type == 'SCHOOL_ADMIN', User.status == 'ACTIVE', User.is_deleted.is_(False))).all()
    for account in administrators:
        if not db.scalar(select(UserRole).where(UserRole.tenant_id == tenant_id,
            UserRole.user_id == account.id, UserRole.role_id == roles['SYSTEM_ADMIN'].id)):
            db.add(UserRole(tenant_id=tenant_id, user_id=account.id, role_id=roles['SYSTEM_ADMIN'].id, status='ACTIVE'))
    db.add(SchoolSetting(tenant_id=tenant_id, setting_key='authorization-installed', value_json={'version': 1}))
    db.flush()
