"""岗位实习请假的一至三级顺序审批，复用流程实例、任务与统一待办。"""
from datetime import datetime
from sqlalchemy import select, or_, func, and_
from app.core.exceptions import AppException, no_permission, check_version
from app.core.permissions import enforce_permission, has_permission, _match
from app.db.session import get_sessionmaker
from app.models import InternshipBatch, InternshipRecord, InternshipLeave, StudentProfile, SchoolClass, Major, User, Role, UserRole, RolePermission, Permission, RoleAssignmentScope
from app.models.approval import WorkflowDefinition, WorkflowInstance, WorkflowTask


from contextlib import contextmanager
from app.services.db_service import _tid
from app.core.exceptions import not_found
from app.modules.internship.services.internship_identity import stable_user_id


def _ids(user):
    tenant_id = _tid()
    if str((user or {}).get('tenantId') or '') != str(tenant_id):
        raise no_permission('当前学校上下文无效')
    return tenant_id, stable_user_id(user) or 0


def _tenant_query(model,user):
    return select(model).where(model.tenant_id==_ids(user)[0],model.is_deleted.is_(False))


def _row(db,model,identifier,user,lock=False):
    q=_tenant_query(model,user).where(model.id==int(identifier))
    value=db.scalar(q.with_for_update().execution_options(populate_existing=True) if lock else q)
    if not value:raise not_found('记录不存在或不属于当前学校')
    return value


def _school_wide(user):
    from app.modules.internship.services.internship_service import _current_scope
    return _current_scope(user).get('mode')=='ADMIN_TENANT'


@contextmanager
def _transaction(user,permission):
    enforce_permission(user,permission)
    with get_sessionmaker()() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def _edit_version(version,expected,current):
    if type(expected) is not int or int(version or 0)!=expected:
        raise AppException('DATA_CONFLICT','配置已变化，请保留草稿并重新读取核对',
            details={'current':current,'expectedVersion':int(version or 0)},http_status=409)


def _paginated(db,query,page,size,present):
    total=int(db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)
    return {'items':[present(row) for row in db.scalars(query.offset((page-1)*size).limit(size))],
            'total':total,'page':page,'pageSize':size}


def audit(db,user,action,kind,identifier,detail):
    from app.modules.internship.services.internship_audit_service import add_audit
    add_audit(db,target_type=kind,target_id=identifier,action=action,user=user,detail=detail)


def _review_roles(db):
    from app.services.system_role_shadow_service import published_system_role_permissions
    roles=db.scalars(select(Role).where(Role.tenant_id==_tid(),Role.is_deleted.is_(False),Role.status.in_(('ACTIVE','ENABLED')))).all()
    custom=dict()
    for role_id,code in db.execute(select(RolePermission.role_id,Permission.permission_code).join(Permission,Permission.id==RolePermission.permission_id).where(
        RolePermission.tenant_id==_tid(),RolePermission.is_deleted.is_(False),RolePermission.status=='ACTIVE')):
        custom.setdefault(role_id,[]).append(code)
    return {r.id:r for r in roles if _match('internship.leave.review',
        published_system_role_permissions(db,r.role_code) if r.role_type=='SYSTEM' else custom.get(r.id,()))}


def _base_role(db,role):
    if role.role_code in ('INTERN_MENTOR','INTERNSHIP_MENTOR'):
        return 'INTERN_MENTOR'
    if role.role_code in ('COLLEGE_ADMIN','SCHOOL_ADMIN'):
        return role.role_code
    from app.services.role_assignment_scope_service import role_scope_policy
    policy=role_scope_policy(db,role)
    return {'INTERN_STUDENTS':'INTERN_MENTOR','COLLEGE':'COLLEGE_ADMIN','SCHOOL':'SCHOOL_ADMIN'}.get(policy.get('scopeType'),'')


NODE_NAMES = {'GUIDE':'指导教师','COLLEGE':'院系责任人','SCHOOL':'校级责任人'}
DEFAULT_NODES = [{'type':'GUIDE','roleCode':'INTERN_MENTOR','userId':''}]


def available(user, permission='internship.leave.policy.view'):
    enforce_permission(user, permission)
    with get_sessionmaker()() as db:
        roles = _review_roles(db)
        from app.services.role_assignment_scope_service import active_role_membership_query
        school_roles = {r.id for r in roles.values() if _base_role(db,r)=='SCHOOL_ADMIN'}
        query = active_role_membership_query(_ids(user)[0]).where(Role.id.in_(school_roles))
        members = db.execute(query.with_only_columns(User, Role).order_by(User.id).limit(200)).all()
        assignees = {}
        for account, role in members:
            if _base_role(db, role) != 'SCHOOL_ADMIN':
                continue
            assignees.setdefault(account.id, {'id':str(account.id),'name':account.real_name,'roleCodes':[]})['roleCodes'].append(role.role_code)
        return {'roles':[{'code':r.role_code,'name':r.role_name,'baseRole':_base_role(db,r)} for r in roles.values()],
                'assignees':list(assignees.values())}


def batches(user,page=1,size=50,keyword='',identifier=None):
    if not any(has_permission(user,p) for p in ('internship.leave.policy.view','internship.leave.handoff.view')):
        raise no_permission('请假配置或责任交接的授权人员才能查询批次')
    with get_sessionmaker()() as db:
        query=_tenant_query(InternshipBatch,user)
        if identifier is not None: query=query.where(InternshipBatch.id==identifier)
        elif keyword: query=query.where(or_(InternshipBatch.batch_name.contains(keyword,autoescape=True),InternshipBatch.batch_no.contains(keyword,autoescape=True)))
        result=_paginated(db,query.order_by(InternshipBatch.id.desc()),page,size,
            lambda r:{'id':str(r.id),'name':r.batch_name,'code':r.batch_no})
        if identifier is not None:
            if not result['items']:raise not_found('批次不存在或已不在当前学校范围内')
            return result['items'][0]
        return result


def current_policy(db,user,batch_id):
    return db.scalar(_tenant_query(WorkflowDefinition,user).where(WorkflowDefinition.batch_id==int(batch_id),
        WorkflowDefinition.source_module=='internship',WorkflowDefinition.source_biz_type=='LEAVE',
        WorkflowDefinition.status=='ENABLED').order_by(WorkflowDefinition.id.desc()).limit(1))


def read(user,batch_id):
    enforce_permission(user,'internship.leave.policy.view')
    with get_sessionmaker()() as db:
        batch=_row(db,InternshipBatch,batch_id,user)
        policy=current_policy(db,user,batch_id)
        return {'batchId':str(batch.id),'batchName':batch.batch_name,'expectedVersion':batch.version,
                'policyId':str(policy.id) if policy else '', 'version':policy.definition_version if policy else '默认一级',
                'nodes':(policy.policy_snapshot_json or {}).get('nodes',DEFAULT_NODES) if policy else DEFAULT_NODES}


def resolver_context(db, user, nodes):
    from app.services.role_assignment_scope_service import active_role_membership_query, active_assignment_scope_query
    codes = {node['roleCode'] for node in nodes}
    roles = {r.role_code:r for r in _review_roles(db).values() if r.role_code in codes}
    pairs = db.execute(active_role_membership_query(_ids(user)[0]).where(Role.role_code.in_(roles))
                       .with_only_columns(User,Role)).all()
    members = {code:[] for code in codes}
    for account,role in pairs:
        members[role.role_code].append(account)
    scopes = {}
    for scope in db.scalars(active_assignment_scope_query(_ids(user)[0]).where(RoleAssignmentScope.role_code.in_(codes))):
        scopes.setdefault((scope.user_id,scope.role_code),set()).add((scope.scope_type,scope.scope_id))
    # 历史学院授权由现有公共桥读取，不能按同名教师自行推断责任。
    from app.services.role_assignment_scope_service import legacy_assignment_scopes, resolve_legacy_scope_ids
    for account,role in pairs:
        if (account.id,role.role_code) in scopes:
            continue
        legacy = legacy_assignment_scopes(db, tenant_id=_ids(user)[0],role_code=role.role_code,
            identity_keys={str(account.id),'db-'+str(account.id),account.login_name},user_id=account.id)
        values={r.ref_value for r in legacy if r.scope_type=='COLLEGE' and r.ref_value}
        ids=resolve_legacy_scope_ids(db,tenant_id=_ids(user)[0],scope_type='COLLEGE',values=values)
        if ids:scopes[(account.id,role.role_code)]={('COLLEGE',i) for i in ids}
    majors={r.id:r.college_id for r in db.scalars(_tenant_query(Major,user))}
    classes={r.id:r.major_id for r in db.scalars(_tenant_query(SchoolClass,user))}
    return {'roles':roles,'members':members,'scopes':scopes,'majors':majors,'classes':classes,
            'baseRoles':{code:_base_role(db,role) for code,role in roles.items()}}


def resolve(record,student,nodes,context):
    result=[]
    major_id=student.major_id or context['classes'].get(student.class_id)
    college_id=student.college_id or context['majors'].get(major_id)
    for node in nodes:
        role=context['roles'].get(node['roleCode']); kind=node['type']
        base=context['baseRoles'].get(node['roleCode'],'')
        if base not in {'GUIDE':{'INTERN_MENTOR'},'COLLEGE':{'COLLEGE_ADMIN'},'SCHOOL':{'SCHOOL_ADMIN'}}[kind]:
            raise AppException('APPROVER_MISSING',f'{NODE_NAMES[kind]}的身份类型不匹配',http_status=409)
        candidates=context['members'].get(node['roleCode'],[])
        if kind=='GUIDE': candidates=[u for u in candidates if u.id==record.advisor_user_id]
        if kind=='COLLEGE': candidates=[u for u in candidates if ('COLLEGE',college_id) in context['scopes'].get((u.id,node['roleCode']),set())]
        if node.get('userId'): candidates=[u for u in candidates if str(u.id)==node['userId']]
        if len(candidates)!=1:
            raise AppException('APPROVER_MISSING',f'{NODE_NAMES[kind]}缺失或有多个候选，请明确责任关系',http_status=409)
        if any(step['userId']==str(candidates[0].id) for step in result):
            raise AppException('APPROVER_LOOP','同一申请的多个节点不能由同一人重复审核',http_status=409)
        result.append({'type':kind,'label':NODE_NAMES[kind],'roleCode':node['roleCode'],
                       'userId':str(candidates[0].id),'name':candidates[0].real_name})
    return result


def check_nodes(nodes):
    if not isinstance(nodes,list) or not nodes or any(not isinstance(node,dict) or set(node)-{'type','roleCode','userId'}
        or node.get('type') not in NODE_NAMES or not isinstance(node.get('roleCode'),str) or not node['roleCode']
        or not isinstance(node.get('userId',''),str) or (node.get('userId') and (not node['userId'].isascii() or not node['userId'].isdigit()))
        for node in nodes):
        raise AppException('VALIDATION_ERROR','审批节点必须包含有效的责任类型、角色和可选人员')
    types=[node['type'] for node in nodes]
    if not 1<=len(types)<=3 or len(set(types))!=len(types):
        raise AppException('VALIDATION_ERROR','选择一至三级且不重复的顺序审批节点')
    if types != sorted(types,key=lambda x:['GUIDE','COLLEGE','SCHOOL'].index(x)):
        raise AppException('VALIDATION_ERROR','审批顺序应为指导教师、院系责任人、校级责任人')


def preview_in_session(db,user,batch_id,nodes):
    check_nodes(nodes)
    context=resolver_context(db,user,nodes)
    query=select(InternshipRecord,StudentProfile).join(StudentProfile,StudentProfile.id==InternshipRecord.student_id).where(
        InternshipRecord.tenant_id==_ids(user)[0],InternshipRecord.batch_id==int(batch_id),InternshipRecord.is_deleted.is_(False),
        StudentProfile.tenant_id==_ids(user)[0],StudentProfile.is_deleted.is_(False))
    items=[];errors=0;total=0
    for record,student in db.execute(query.execution_options(yield_per=200)):
        total+=1
        try: steps=resolve(record,student,nodes,context); message=''
        except AppException as exc: steps=[]; message=exc.message;errors+=1
        if len(items)<100: items.append({'studentName':student.real_name,'studentNo':student.student_no,'steps':steps,'error':message})
    return {'total':total,'errorCount':errors,'items':items,'canPublish':total>0 and errors==0}


def preview(user,batch_id,nodes):
    enforce_permission(user,'internship.leave.policy.manage')
    with get_sessionmaker()() as db:
        _row(db,InternshipBatch,batch_id,user)
        return preview_in_session(db,user,batch_id,nodes)


def publish(user,batch_id,data):
    with _transaction(user,'internship.leave.policy.manage') as db:
        if not _school_wide(user): raise no_permission('请假规则由校级授权人员发布')
        batch=_row(db,InternshipBatch,batch_id,user,True)
        previous=current_policy(db,user,batch_id)
        _edit_version(batch.version,data['expectedVersion'],{'nodes':(previous.policy_snapshot_json or {}).get('nodes',DEFAULT_NODES) if previous else DEFAULT_NODES})
        result=preview_in_session(db,user,batch_id,data['nodes'])
        if not result['canPublish']: raise AppException('APPROVER_MISSING','当前批次没有可核对的学生，或存在责任人缺口，不能发布',details=result,http_status=409)
        if previous: previous.status='DISABLED'
        version=int(previous.definition_version)+1 if previous and previous.definition_version.isdigit() else 1
        policy=WorkflowDefinition(tenant_id=_ids(user)[0],batch_id=batch.id,workflow_code=f'leave-{batch.id}-{version}',
            workflow_name=f'{batch.batch_name}请假审批',source_module='internship',source_biz_type='LEAVE',
            definition_version=str(version),status='ENABLED',policy_confirmed=True,policy_confirmed_by=_ids(user)[1],
            policy_confirmed_at=datetime.utcnow(),policy_snapshot_json={'nodes':data['nodes']},
            source_profile='INTERNSHIP',installed_project_id=_ids(user)[0])
        db.add(policy);batch.version+=1;db.flush()
        audit(db,user,'LEAVE_POLICY_PUBLISH','leave-policy',policy.id,{'batchId':str(batch.id),'version':version,'nodes':data['nodes'],'reason':data['reason']})
        return {'policyId':str(policy.id),'version':version,'expectedVersion':batch.version,'checkedStudents':result['total']}


def latest_instance(db,tenant_id,leave_id):
    return db.scalar(select(WorkflowInstance).where(WorkflowInstance.tenant_id==tenant_id,
        WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE',
        WorkflowInstance.source_biz_id==leave_id,WorkflowInstance.is_deleted.is_(False)).order_by(WorkflowInstance.id.desc()).limit(1))


def start(db,leave,record):
    from app.core.context import get_current_user_ctx
    from app.modules.internship.services import internship_todo_helper as todo
    user=get_current_user_ctx() or {'tenantId':str(record.tenant_id),'userId':'db-0'}
    student=db.get(StudentProfile,record.student_id)
    policy=current_policy(db,user,record.batch_id)
    previous=latest_instance(db,record.tenant_id,leave.id)
    if not policy and not previous:
        return todo.todo_upsert(db,biz_type='INTERN_LEAVE',biz_id=leave.id,todo_type=todo.TODO_LEAVE,
            assignee_id=todo.resolve_advisor_assignee_id(db,record,preserve_unavailable=True),
            student_id=record.student_id,title=f'请假待审：{student.real_name}')
    nodes=(previous.snapshot_json or {}).get('policyNodes') if previous else None
    nodes=nodes or ((policy.policy_snapshot_json or {}).get('nodes') if policy else DEFAULT_NODES)
    steps=resolve(record,student,nodes,resolver_context(db,user,nodes))
    if previous and previous.status=='RUNNING': cancel(db,record.tenant_id,leave.id)
    instance=WorkflowInstance(tenant_id=record.tenant_id,workflow_code=previous.workflow_code if previous else policy.workflow_code if policy else 'leave-default-1',
        source_module='internship',source_biz_type='LEAVE',source_biz_id=leave.id,applicant_id=_ids(user)[1],
        title=f'{student.real_name}请假',status='RUNNING',current_node='1',
        snapshot_json={'policyId':(previous.snapshot_json or {}).get('policyId','') if previous else str(policy.id) if policy else '', 'policyNodes':nodes,'steps':steps})
    db.add(instance);db.flush()
    for i,step in enumerate(steps,1):
        db.add(WorkflowTask(tenant_id=record.tenant_id,instance_id=instance.id,node_code=str(i),sequence_no=i,
            assignee_id=int(step['userId']),assignee_role_code=step['roleCode'],status='PENDING' if i==1 else 'WAITING'))
    todo.todo_done(db,biz_id=leave.id,todo_type=todo.TODO_LEAVE)
    todo.todo_upsert(db,biz_type='INTERN_LEAVE',biz_id=leave.id,todo_type=todo.TODO_LEAVE,
        assignee_id=int(steps[0]['userId']),student_id=student.id,title=f'第1级请假待审：{student.real_name}')
    return True


def advance(db,user,leave,action,comment):
    from app.modules.internship.services import internship_todo_helper as todo
    instance=latest_instance(db,leave.tenant_id,leave.id)
    if not instance: return True  # Existing submitted applications retain their original single-stage contract.
    if instance.status!='RUNNING': raise AppException('DATA_CONFLICT','审批实例已处理，请重新读取',http_status=409)
    task=db.scalar(select(WorkflowTask).where(WorkflowTask.instance_id==instance.id,WorkflowTask.tenant_id==leave.tenant_id,
        WorkflowTask.status=='PENDING',WorkflowTask.is_deleted.is_(False)).with_for_update())
    if not task or task.assignee_id!=_ids(user)[1] or task.assignee_role_code!=user['currentRoleCode']:
        raise no_permission('当前审批节点由其他责任身份办理；停用或撤权后请先重新指定责任人')
    if not db.scalar(available_task_ids(db,leave.tenant_id).where(WorkflowTask.id==task.id)):
        raise no_permission('审批责任已停用或超出当前范围，请学校重新指定责任人')
    outcome={'APPROVE':'APPROVED','REJECT':'REJECTED','REQUEST_CHANGES':'NEEDS_REVISION'}[action]
    task.status=outcome;task.action_reason=comment;task.acted_at=datetime.utcnow();task.version+=1
    todo.todo_done(db,biz_id=leave.id,todo_type=todo.TODO_LEAVE)
    next_task=db.scalar(select(WorkflowTask).where(WorkflowTask.instance_id==instance.id,WorkflowTask.tenant_id==leave.tenant_id,
        WorkflowTask.sequence_no==task.sequence_no+1,WorkflowTask.is_deleted.is_(False)))
    if action=='APPROVE' and next_task:
        next_task.status='PENDING';instance.current_node=str(next_task.sequence_no);instance.version+=1
        # A disabled assignee remains a visible exception; no step is skipped or silently substituted.
        todo.todo_upsert(db,biz_type='INTERN_LEAVE',biz_id=leave.id,todo_type=todo.TODO_LEAVE,
            assignee_id=next_task.assignee_id,student_id=leave.student_id,title=f'第{next_task.sequence_no}级请假待审')
        return False
    instance.status=outcome;instance.version+=1
    for waiting in db.scalars(select(WorkflowTask).where(WorkflowTask.instance_id==instance.id,WorkflowTask.status=='WAITING')):
        waiting.status='CANCELLED'
    return True


def cancel(db,tenant_id,leave_id):
    instance=latest_instance(db,tenant_id,leave_id)
    if instance and instance.status=='RUNNING':
        instance.status='CANCELLED';instance.version+=1
        for task in db.scalars(select(WorkflowTask).where(WorkflowTask.tenant_id==tenant_id,WorkflowTask.instance_id==instance.id,
                                                        WorkflowTask.status.in_(['PENDING','WAITING']))): task.status='CANCELLED'


def pending_for_actor(user):
    """同一条件用于管理列表和待办数量；历史一级申请沿用原有业务范围。"""
    instances=select(WorkflowInstance.id).where(WorkflowInstance.tenant_id==_ids(user)[0],
        WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE',
        WorkflowInstance.source_biz_id==InternshipLeave.id,WorkflowInstance.is_deleted.is_(False))
    assigned=instances.join(WorkflowTask,WorkflowTask.instance_id==WorkflowInstance.id).where(
        WorkflowInstance.status=='RUNNING',WorkflowTask.tenant_id==_ids(user)[0],WorkflowTask.status=='PENDING',
        WorkflowTask.is_deleted.is_(False),WorkflowTask.assignee_id==_ids(user)[1],
        WorkflowTask.assignee_role_code==user.get('currentRoleCode'))
    return or_(~instances.exists(),assigned.exists())


def available_task_ids(db, tenant_id):
    from app.services.role_assignment_scope_service import active_role_membership_query, active_assignment_scope_query
    roles = _review_roles(db)
    active = active_role_membership_query(tenant_id).with_only_columns(UserRole.id).where(
        UserRole.user_id==WorkflowTask.assignee_id,Role.role_code==WorkflowTask.assignee_role_code,Role.id.in_(roles))
    kind=func.json_unquote(func.json_extract(WorkflowInstance.snapshot_json,
        func.concat('$.steps[',WorkflowTask.sequence_no-1,'].type')))
    college = func.coalesce(StudentProfile.college_id,Major.college_id)
    scope=active_assignment_scope_query(tenant_id).with_only_columns(RoleAssignmentScope.id).where(
        RoleAssignmentScope.user_id==WorkflowTask.assignee_id,RoleAssignmentScope.role_code==WorkflowTask.assignee_role_code,
        RoleAssignmentScope.scope_type=='COLLEGE',RoleAssignmentScope.scope_id==college).correlate(WorkflowTask,StudentProfile,Major).exists()
    school_codes={r.role_code for r in roles.values() if _base_role(db,r)=='SCHOOL_ADMIN'}
    guide_codes={r.role_code for r in roles.values() if _base_role(db,r)=='INTERN_MENTOR'}
    college_codes={r.role_code for r in roles.values() if _base_role(db,r)=='COLLEGE_ADMIN'}
    return select(WorkflowTask.id).join(WorkflowInstance,WorkflowInstance.id==WorkflowTask.instance_id).join(
        InternshipLeave,InternshipLeave.id==WorkflowInstance.source_biz_id).join(InternshipRecord,InternshipRecord.id==InternshipLeave.internship_id).join(
        StudentProfile,StudentProfile.id==InternshipRecord.student_id).outerjoin(SchoolClass,and_(SchoolClass.id==StudentProfile.class_id,SchoolClass.tenant_id==tenant_id,
        SchoolClass.is_deleted.is_(False))).outerjoin(Major,and_(Major.id==func.coalesce(StudentProfile.major_id,SchoolClass.major_id),
        Major.tenant_id==tenant_id,Major.is_deleted.is_(False))).where(
        WorkflowTask.tenant_id==tenant_id,WorkflowTask.is_deleted.is_(False),WorkflowInstance.tenant_id==tenant_id,
        WorkflowInstance.is_deleted.is_(False),WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE',
        InternshipLeave.tenant_id==tenant_id,InternshipLeave.is_deleted.is_(False),InternshipRecord.tenant_id==tenant_id,
        InternshipRecord.is_deleted.is_(False),StudentProfile.tenant_id==tenant_id,StudentProfile.is_deleted.is_(False),
        active.correlate(WorkflowTask).exists(),or_(
            and_(kind=='GUIDE',WorkflowTask.assignee_role_code.in_(guide_codes),InternshipRecord.advisor_user_id==WorkflowTask.assignee_id),
            and_(kind=='COLLEGE',WorkflowTask.assignee_role_code.in_(college_codes),scope),
            and_(kind=='SCHOOL',WorkflowTask.assignee_role_code.in_(school_codes)))).correlate(None)


def progress_many(db,leaves,user=None):
    if not leaves: return {}
    tenant_id=leaves[0].tenant_id
    latest=select(func.max(WorkflowInstance.id)).where(WorkflowInstance.tenant_id==tenant_id,
        WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE',
        WorkflowInstance.source_biz_id.in_([r.id for r in leaves]),WorkflowInstance.is_deleted.is_(False)).group_by(WorkflowInstance.source_biz_id)
    instances=db.scalars(select(WorkflowInstance).where(WorkflowInstance.id.in_(latest))).all()
    tasks=db.scalars(select(WorkflowTask).where(WorkflowTask.tenant_id==tenant_id,
        WorkflowTask.instance_id.in_([r.id for r in instances]),WorkflowTask.is_deleted.is_(False)).order_by(WorkflowTask.sequence_no)).all()
    available_ids=set(db.scalars(available_task_ids(db,tenant_id).where(WorkflowTask.id.in_([t.id for t in tasks]))))
    states={'WAITING':'等待前级','PENDING':'待审批','APPROVED':'已通过','REJECTED':'已驳回','NEEDS_REVISION':'已退回补正','CANCELLED':'已结束'}
    result={r.id:{'label':'指导教师一级审核','steps':[],'canReview':r.status=='PENDING'} for r in leaves}
    by_instance={}
    for task in tasks: by_instance.setdefault(task.instance_id,[]).append(task)
    for instance in instances:
        steps=[];can_review=False
        frozen=(instance.snapshot_json or {}).get('steps',[])
        for i,task in enumerate(by_instance.get(instance.id,[])):
            available=task.id in available_ids
            if task.status=='PENDING' and available and user:
                can_review=task.assignee_id==_ids(user)[1] and task.assignee_role_code==user.get('currentRoleCode')
            steps.append({'label':frozen[i]['label'] if i<len(frozen) else '审批节点',
                'assignee':frozen[i]['name'] if i<len(frozen) else '',
                'statusLabel':'待重新指定责任人' if task.status in ('PENDING','WAITING') and not available else states.get(task.status,'待核对'),
                'comment':task.action_reason or '', 'actedAt':task.acted_at.isoformat() if task.acted_at else ''})
        result[instance.source_biz_id]={'label':f'共{len(steps)}级审批 · 当前第{instance.current_node}级',
            'steps':steps,'canReview':can_review,'workflowStatus':instance.status}
    return result


def progress(db,leave,user=None):
    return progress_many(db,[leave],user)[leave.id]


def handoff_list(user,batch_id,source_id,page=1,size=30,task_id=''):
    enforce_permission(user,'internship.leave.handoff.view')
    if not _school_wide(user): raise no_permission('任务交接由校级授权人员办理')
    with get_sessionmaker()() as db:
        _row(db,InternshipBatch,batch_id,user)
        query=select(WorkflowTask,WorkflowInstance,InternshipLeave,StudentProfile).join(WorkflowInstance,
            WorkflowInstance.id==WorkflowTask.instance_id).join(InternshipLeave,InternshipLeave.id==WorkflowInstance.source_biz_id)
        query=query.join(InternshipRecord,InternshipRecord.id==InternshipLeave.internship_id).join(StudentProfile,
            StudentProfile.id==InternshipLeave.student_id).where(WorkflowTask.tenant_id==_ids(user)[0],
            WorkflowTask.assignee_id==int(source_id),WorkflowTask.status.in_(['PENDING','WAITING']),WorkflowTask.is_deleted.is_(False),
            WorkflowInstance.tenant_id==_ids(user)[0],WorkflowInstance.status=='RUNNING',WorkflowInstance.is_deleted.is_(False),
            WorkflowInstance.source_module=='internship',WorkflowInstance.source_biz_type=='LEAVE',
            InternshipRecord.tenant_id==_ids(user)[0],InternshipRecord.batch_id==int(batch_id),InternshipRecord.is_deleted.is_(False),
            InternshipLeave.tenant_id==_ids(user)[0],InternshipLeave.is_deleted.is_(False),
            StudentProfile.tenant_id==_ids(user)[0],StudentProfile.is_deleted.is_(False))
        if task_id: query=query.where(WorkflowTask.id==int(task_id))
        total=db.scalar(select(func.count()).select_from(query.subquery()))
        values=db.execute(query.order_by(WorkflowTask.id).offset((page-1)*size).limit(size)).all()
        current=progress_many(db,list({leave.id:leave for _,_,leave,_ in values}.values()))
        return {'total':total,'items':[{'id':str(task.id),'version':task.version,'studentName':student.real_name,
            'title':instance.title,'leaveId':str(leave.id),'step':task.sequence_no,'roleCode':task.assignee_role_code,
            'statusLabel':current[leave.id]['steps'][task.sequence_no-1]['statusLabel']} for task,instance,leave,student in values],
            'note':'指导教师交接先从实习学生名单办理导师重新分配；这里接续已冻结的请假节点，原审批历史保留。'}


def handoff(user,task_id,data):
    from app.modules.internship.services import internship_todo_helper as todo
    with _transaction(user,'internship.leave.handoff.manage') as db:
        if not _school_wide(user): raise no_permission('任务交接由校级授权人员办理')
        # Match review's lock order: leave first, then task. Locks protect against simultaneous review.
        task=_row(db,WorkflowTask,task_id,user)
        instance=_row(db,WorkflowInstance,task.instance_id,user)
        if instance.source_module!='internship' or instance.source_biz_type!='LEAVE': raise no_permission()
        leave=_row(db,InternshipLeave,instance.source_biz_id,user,True)
        task=_row(db,WorkflowTask,task_id,user,True);check_version(task.version,data['expectedVersion'])
        if instance.status!='RUNNING' or task.status not in ('PENDING','WAITING'):
            raise AppException('DATA_CONFLICT','该节点已办理，不能交接历史结论',http_status=409)
        record=_row(db,InternshipRecord,leave.internship_id,user)
        if str(record.batch_id)!=data['batchId']: raise no_permission('请假不属于当前交接批次')
        snapshot=dict(instance.snapshot_json or {});steps=[dict(s) for s in snapshot['steps']]
        original=steps[task.sequence_no-1]
        node={'type':original['type'],'roleCode':data['roleCode'],'userId':data['userId']}
        recipient=resolve(record,_row(db,StudentProfile,leave.student_id,user),[node],resolver_context(db,user,[node]))[0]
        if any(str(t.assignee_id)==data['userId'] for t in db.scalars(_tenant_query(WorkflowTask,user).where(
            WorkflowTask.instance_id==instance.id,WorkflowTask.id!=task.id))):
            raise AppException('APPROVER_LOOP','接收人已承担本申请其他节点，不能重复审核',http_status=409)
        previous_id=task.assignee_id
        task.assignee_id=int(data['userId']);task.assignee_role_code=data['roleCode'];task.version+=1
        steps[task.sequence_no-1]=recipient;snapshot['steps']=steps
        snapshot['handoffs']=[*(snapshot.get('handoffs') or []),{'from':original,'to':recipient,
            'at':datetime.utcnow().isoformat(),'operator':str(_ids(user)[1]),'reason':data['reason']}]
        instance.snapshot_json=snapshot;instance.version+=1
        if task.status=='PENDING':
            from app.models import UnifiedTodo
            for old in db.scalars(_tenant_query(UnifiedTodo,user).where(UnifiedTodo.source_module=='internship',
                UnifiedTodo.source_biz_id==leave.id,UnifiedTodo.todo_type==todo.TODO_LEAVE,UnifiedTodo.assignee_id==previous_id,
                UnifiedTodo.status=='PENDING')): old.status='CANCELLED';old.remark='责任交接，原审批未办理';old.version+=1
            todo.todo_upsert(db,biz_type='INTERN_LEAVE',biz_id=leave.id,todo_type=todo.TODO_LEAVE,
                assignee_id=task.assignee_id,student_id=leave.student_id,title=f'第{task.sequence_no}级请假待审（已交接）')
        audit(db,user,'RESPONSIBILITY_HANDOFF','leave',leave.id,{'fromUserId':str(previous_id),'toUserId':data['userId'],
            'taskId':str(task.id),'reason':data['reason']})
        return {'id':str(task.id),'version':task.version,'message':f'已交接给{recipient["name"]}，按原审批顺序继续办理'}
