"""School administration, stable scope references and versioned leave workflow snapshots."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision = 'ix0034'
down_revision = 'ix0033'
branch_labels = None
depends_on = None


def common():
    return [sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('created_by', sa.BigInteger()),
        sa.Column('updated_at', sa.DateTime()), sa.Column('updated_by', sa.BigInteger()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0')]


def upgrade():
    op.create_table('t_school_department', *common(), sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False), sa.Column('status', sa.String(20), nullable=False),
        sa.UniqueConstraint('tenant_id', 'code', name='uk_school_department_code'))
    op.create_table('t_staff_profile', *common(), sa.Column('staff_no', sa.String(100), nullable=False),
        sa.Column('real_name', sa.String(100), nullable=False), sa.Column('user_id', sa.BigInteger(), index=True),
        sa.Column('college_id', sa.BigInteger(), index=True), sa.Column('department_id', sa.BigInteger(), index=True),
        sa.Column('phone_encrypted', sa.String(500)), sa.Column('status', sa.String(20), nullable=False),
        sa.UniqueConstraint('tenant_id', 'staff_no', name='uk_staff_profile_no'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uk_staff_profile_user'))
    op.create_table('t_school_setting', *common(), sa.Column('setting_key', sa.String(100), nullable=False),
        sa.Column('value_json', sa.JSON(), nullable=False), sa.UniqueConstraint('tenant_id','setting_key',name='uk_school_setting_key'))
    op.create_table('t_school_delivery_record', *common(), sa.Column('kind', sa.String(40), nullable=False, index=True),
        sa.Column('title', sa.String(200), nullable=False), sa.Column('status', sa.String(30), nullable=False),
        sa.Column('owner_user_id', sa.BigInteger()), sa.Column('detail_json', sa.JSON(), nullable=False),
        sa.Column('checked_at', sa.DateTime()))
    for table, columns in {
        't_user': [sa.Column('expires_at', sa.DateTime())],
        't_role': [sa.Column('base_role_code', sa.String(50))],
        't_teacher_student_scope': [sa.Column('user_id', sa.BigInteger()), sa.Column('ref_id', sa.BigInteger())],
        't_excel_import_job': [sa.Column('preview_json', sa.JSON()), sa.Column('receipt_encrypted', sa.Text()), sa.Column('expires_at', sa.DateTime())],
        't_workflow_instance': [sa.Column('snapshot_json', sa.JSON())],
        't_workflow_task': [sa.Column('assignee_role_code', sa.String(50)), sa.Column('sequence_no', sa.Integer())],
        't_workflow_definition': [sa.Column('batch_id', sa.BigInteger())],
    }.items():
        for column in columns: op.add_column(table, column)
    for name in ('user_id', 'ref_id'): op.create_index('ix_t_teacher_student_scope_'+name,'t_teacher_student_scope',[name])
    op.create_index('ix_t_workflow_definition_batch_id','t_workflow_definition',['batch_id'])
    op.alter_column('t_teacher_student_scope','role_code',existing_type=sa.String(32),type_=sa.String(50),existing_nullable=True)
    install_authorization(op.get_bind())
    migrate_scopes(op.get_bind())
    op.get_bind().execute(sa.text("""INSERT INTO t_staff_profile
        (tenant_id, staff_no, real_name, user_id, status, created_at, updated_at, is_deleted, version)
        SELECT tenant_id, login_name, real_name, id, status, UTC_TIMESTAMP(), UTC_TIMESTAMP(), 0, 0
        FROM t_user WHERE is_deleted=0 AND user_type IN ('TEACHER','SCHOOL_ADMIN','COLLEGE_ADMIN','INTERN_MENTOR','COUNSELOR','LEADER','SECURITY_AUDITOR')"""))


def install_authorization(bind):
    # Frozen grants are derived from the pre-change runtime, not mutable imports during a future upgrade.
    data = json.loads((Path(__file__).parents[1] / 'data' / '0034_school_permissions.json').read_text(encoding='utf-8'))
    metadata = sa.MetaData()
    tables = {name: sa.Table(name, metadata, autoload_with=bind) for name in
              ['t_permission','t_role','t_role_permission','t_user','t_user_role','t_school_setting','t_tenant']}
    p, role, rp, u, ur, setting, tenant = [tables[n] for n in tables]
    now = datetime.utcnow()
    def fields(tid): return {'tenant_id':tid,'created_at':now,'updated_at':now,'is_deleted':False,'version':0}
    permissions = {r.permission_code:r.id for r in bind.execute(sa.select(p))}
    for code, label in data['catalog'].items():
        if code not in permissions:
            permissions[code] = bind.execute(p.insert().values(permission_code=code,permission_name=label,
                module_code=code.split('.')[0],created_at=now)).inserted_primary_key[0]
    for tid in bind.execute(sa.select(tenant.c.id)).scalars():
        roles = {r.role_code:r.id for r in bind.execute(sa.select(role).where(role.c.tenant_id==tid))}
        for code, label in data['roles'].items():
            if code not in roles:
                roles[code] = bind.execute(role.insert().values(**fields(tid),role_code=code,role_name=label,
                    role_type='SYSTEM',base_role_code=code,status='ACTIVE')).inserted_primary_key[0]
        for code, rid in roles.items():
            bind.execute(role.update().where(role.c.id==rid).values(base_role_code=code))
            bind.execute(rp.update().where(rp.c.tenant_id==tid,rp.c.role_id==rid).values(status='DISABLED'))
            existing = {r.permission_id:r.id for r in bind.execute(sa.select(rp).where(rp.c.tenant_id==tid,rp.c.role_id==rid))}
            for permission in data['grants'].get(code, []):
                pid = permissions[permission]
                if pid in existing:
                    bind.execute(rp.update().where(rp.c.id==existing[pid]).values(status='ACTIVE',is_deleted=False))
                else:
                    bind.execute(rp.insert().values(**fields(tid),role_id=rid,permission_id=pid,status='ACTIVE'))
        for uid in bind.execute(sa.select(u.c.id).where(u.c.tenant_id==tid,u.c.user_type=='SCHOOL_ADMIN',u.c.status=='ACTIVE',u.c.is_deleted==False)).scalars():
            if not bind.execute(sa.select(ur.c.id).where(ur.c.tenant_id==tid,ur.c.user_id==uid,ur.c.role_id==roles['SYSTEM_ADMIN'])).first():
                bind.execute(ur.insert().values(**fields(tid),user_id=uid,role_id=roles['SYSTEM_ADMIN'],status='ACTIVE'))
        bind.execute(setting.insert().values(**fields(tid),setting_key='authorization-installed',value_json={'version':1}))


def migrate_scopes(bind):
    metadata = sa.MetaData()
    scope = sa.Table('t_teacher_student_scope',metadata,autoload_with=bind)
    users = sa.Table('t_user',metadata,autoload_with=bind)
    refs = {kind:(sa.Table(table,metadata,autoload_with=bind),name) for kind,table,name in
            [('COLLEGE','t_college','college_name'),('MAJOR','t_major','major_name'),('CLASS','t_class','class_name'),('STUDENT','t_student_profile','student_no')]}
    for row in bind.execute(sa.select(scope)).mappings():
        key = str(row['teacher_key'] or '')
        subject = sa.or_(users.c.login_name==key, users.c.id==int(key.removeprefix('db-'))) if key.removeprefix('db-').isdigit() else users.c.login_name==key
        candidates = list(bind.execute(sa.select(users.c.id).where(users.c.tenant_id==row['tenant_id'],users.c.is_deleted==False,subject)).scalars())
        model, name = refs.get(row['scope_type'], (None, None))
        objects = list(bind.execute(sa.select(model.c.id).where(model.c.tenant_id==row['tenant_id'],model.c.is_deleted==False,model.c[name]==row['ref_value'])).scalars()) if model is not None else []
        if len(candidates)==1 and len(objects)==1 and row['role_code']:
            bind.execute(scope.update().where(scope.c.id==row['id']).values(user_id=candidates[0],ref_id=objects[0]))
        else:
            bind.execute(scope.update().where(scope.c.id==row['id']).values(status='REVIEW'))


def downgrade():
    raise RuntimeError('School identity and authorization evidence must be preserved; use a reviewed forward repair instead of destructive downgrade')
