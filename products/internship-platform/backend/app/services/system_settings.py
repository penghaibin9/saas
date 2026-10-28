"""学校基础配置与可追溯管理查询；交付资料不替代自动检测或正式验收。"""
from datetime import datetime
from pathlib import Path
import shutil
from sqlalchemy import select, func, or_
from app.config import settings
from app.core.exceptions import AppException, check_version, no_permission
from app.core.permissions import enforce_permission, has_permission
from app.db.session import get_sessionmaker, get_engine
from app.models import (Tenant, SchoolSetting, SchoolDeliveryRecord, ExcelImportJob, SecurityAuditLog,
    StudentProfile, StudentAccountLink, StaffProfile, TeacherStudentScope, User, UnifiedTodo)
from app.models.tenant import TenantBrandConfig
from app.models.audit_outbox import AuditOutbox
from app.services import system_management as sm
from app.services.system_authorization import audit, permission_name, ROLE_NAMES
from app.services.xlsx_util import build_ledger_xlsx

ACTION_NAMES={'LOGIN':'登录','LOGIN_DENIED':'登录被拒绝','LOGOUT':'退出登录','ROLE_SWITCH':'切换身份','ORG_SAVE':'维护组织','PERSON_SAVE':'维护人员',
    'STUDENT_BINDING_REPAIR':'纠正学生账号绑定',
    'ROLE_SAVE':'调整角色权限','ROLE_MEMBER':'调整角色成员','SCOPE_SAVE':'调整责任范围','IDENTITY_PREVIEW':'导入预检',
    'IDENTITY_CONFIRM':'确认师生开户','ORGANIZATION_IMPORT':'确认组织导入','IDENTITY_RECEIPT_DOWNLOAD':'领取开户回执',
    'IMPORT_ERRORS_DOWNLOAD':'下载导入错误行','IDENTITY_QUEUE':'确认导入排队','IDENTITY_JOB_FAILED':'导入整批执行失败',
    'ACCOUNT_RESET':'重置账号密码','ACCOUNT_DISABLE':'停用账号','ACCOUNT_ENABLE':'启用账号',
    'ACCOUNT_UNLOCK':'解锁账号','ACCOUNT_EXPIRY':'调整有效期','CONFIG_SAVE':'修改学校配置','DELIVERY_RECORD':'登记交付资料',
    'AUDIT_EXPORT':'导出审计','DIRECTORY_EXPORT':'导出基础资料','EXPORT_RESULT_DOWNLOAD':'领取导出结果',
    'DIRECTORY_EXPORT_QUEUE':'登记后台导出任务','DIRECTORY_EXPORT_RETRY':'重试失败导出','DIRECTORY_EXPORT_FAILED':'后台导出失败',
    'SENSITIVE_CONTACT_VIEW':'查看完整联系方式','RESPONSIBILITY_HANDOFF':'交接审批责任','LEAVE_POLICY_PUBLISH':'发布请假审批规则'}


def overview(user):
    enforce_permission(user, 'system.overview.view')
    with get_sessionmaker()() as db:
        def count(query): return db.scalar(select(func.count()).select_from(query.subquery()))
        students = sm.scoped_students(db, user)
        unbound = count(sm.people_query(db,user,'student',account_status='UNBOUND'))
        staff = sm.scoped_staff(db, user)
        review = count(sm.tenant_query(TeacherStudentScope, user).where(sm.scope_review_condition())) if sm.school_wide(user) else 0
        failed = count(sm.tenant_query(ExcelImportJob, user).where(ExcelImportJob.status == 'FAILED',
            ExcelImportJob.operator_id == sm.ids(user)[1]))
        responsibilities=sm.responsibility_gaps(db,user) if sm.school_wide(user) else {'missing':0,'duplicates':0}
        blocked=sm.blocked_tasks(db,user,size=0)['total'] if sm.school_wide(user) else 0
        backup=None
        if has_permission(user,'system.runtime.view'):
            from app.services.system_evidence import read_receipts, backup_summary
            backup=backup_summary(read_receipts(sm.ids(user)[0]))
        return {'studentCount': count(students), 'staffCount': count(staff), 'backup':backup,'issues': [
            {'name': '学生尚未绑定账号', 'count': unbound, 'path': '/admin/system/students?binding=UNBOUND'},
            {'name': '教职工尚未开通账号', 'count': count(sm.people_query(db,user,'staff',account_status='UNBOUND')), 'path': '/admin/system/staff?binding=UNBOUND'},
            {'name': '历史责任范围待核对', 'count': review, 'path': '/admin/system/scopes?review=1'},
            {'name': '组织缺少有效负责人', 'count': responsibilities['missing'], 'path': '/admin/system/scopes?issue=MISSING'},
            {'name': '多名责任人需要核对', 'count': responsibilities['duplicates'], 'path': '/admin/system/scopes?issue=DUPLICATE'},
            {'name': '原承办人已无法办理的待办', 'count': blocked, 'path': '/admin/system/scopes?blocked=1'},
            {'name': '本人失败的导入任务', 'count': failed, 'path': '/admin/system/tasks?status=FAILED'}],
            'steps': [{'name': '确认学校资料', 'path': '/admin/system/brand'},
                {'name': '建立院系、专业与班级', 'path': '/admin/system/organizations'},
                {'name': '导入教职工并开通账号', 'path': '/admin/system/identity-import/staff'},
                {'name': '导入学生并绑定账号', 'path': '/admin/system/identity-import/students'},
                {'name': '指定系统维护与实习管理负责人', 'path': '/admin/system/roles', 'note': '在对应角色中维护成员；兼任人员使用同一账号，不重复开户。'},
                {'name': '设置院系、专业与班级负责范围', 'path': '/admin/system/scopes'},
                {'name': '建立实习批次并配置参与学生', 'path': '/admin/internship/batches?panel=list', 'note': '由实习管理员办理；点击顶部“岗位实习中心”可切换到已授权身份。'},
                {'name': '分配指导教师并核对学生名单', 'path': '/admin/internship/students?panel=mentor'},
                {'name': '核对请假审批责任人', 'path': '/admin/system/leave-policy', 'note': '先完成本批次学生名单和导师分配，再核对逐级承办人并发布。'},
                {'name': '制定实习计划', 'path': '/admin/internship/plans'}],
            'note': '准备情况由当前数据计算，不代表采购验收已经通过。'}


def brand(db, user):
    school = db.get(Tenant, sm.ids(user)[0])
    item = db.scalar(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == school.id,
                                                   TenantBrandConfig.is_deleted.is_(False)))
    values = item.config_json or {} if item else {}
    return {'schoolName': school.school_name, 'shortName': school.short_name or '', 'schoolCode': school.tenant_code,
        'platformName': item.platform_name if item and item.platform_name else settings.APP_NAME,
        'subtitle': item.platform_subtitle or '' if item else '', 'contactPhone': values.get('contactPhone',''),
        'supervisionPhone': values.get('supervisionPhone',''), 'version': item.version if item else 0,
        'logoFileId': str(item.badge_file_id or '') if item else ''}


STANDARD_NAMES={'area':'地区','industry':'行业','enterpriseNature':'企业性质','major':'专业代码'}
CONFIG_DEFAULTS = {'dictionary': {'announcementCategories': ['实习通知','安全提醒','材料收集'], 'aliases': [], 'standardReferences': []},
                   'notification': {'contactPhone':'', 'responsibleUserId':'', 'faq':[],
                                    'reminderText':'请及时处理岗位实习待办。'}}
CONFIG_LABELS = {'schoolName':'学校全称','shortName':'学校简称','platformName':'平台名称','subtitle':'副标题',
    'contactPhone':'咨询电话','supervisionPhone':'监督电话','logoFileId':'校徽文件编号',
    'announcementCategories':'公告分类','aliases':'组织匹配别名','responsibleUserId':'承办人编号',
    'reminderText':'提醒附言','faq':'常见问题','standardReferences':'字典来源与版本登记'}


def config_changes(before, after):
    def display(key, value):
        if value in (None, '', []): return '未填写'
        if key in {'contactPhone','supervisionPhone'}: return '已填写（内容不进入审计）'
        if key == 'faq': return '；'.join(f'{r["question"]}：{r["answer"]}' for r in value)
        if key == 'aliases': return '；'.join(f'{r["alias"]} → {r["code"]}' for r in value)
        if key == 'standardReferences':
            return '；'.join(f'{STANDARD_NAMES[r["kind"]]}：{r["source"]}，{r["edition"]}'
                if r['source'] else f'{STANDARD_NAMES[r["kind"]]}：尚未登记' for r in value)
        if isinstance(value,list): return '、'.join(value)
        return str(value)
    return [{'field':key,'label':label,'before':display(key,before.get(key)),'after':display(key,after.get(key))}
        for key,label in CONFIG_LABELS.items() if key in after and before.get(key)!=after.get(key)]


def read_config(user, category):
    enforce_permission(user, f'system.{category}.view')
    with get_sessionmaker()() as db:
        if category == 'brand': return brand(db, user)
        item = db.scalar(sm.tenant_query(SchoolSetting, user).where(SchoolSetting.setting_key == category))
        result={**CONFIG_DEFAULTS.get(category, {}), **(item.value_json if item else {}), 'version': item.version if item else 0}
        if category=='notification':
            owner=db.scalar(sm.tenant_query(User,user).where(User.id==int(result['responsibleUserId']))) if result.get('responsibleUserId') else None
            result['responsibleValid']=valid_service_owner(db,owner)
            result['responsibleName']=(owner.real_name or owner.login_name) if result['responsibleValid'] else ''
        return result


def valid_service_owner(db,account):
    return bool(account and not account.is_deleted and account.status == 'ACTIVE'
        and account.user_type in {'SCHOOL_ADMIN', 'TEACHER'}
        and (account.expires_at is None or account.expires_at > datetime.utcnow())
        and not db.scalar(select(StaffProfile.id).where(StaffProfile.tenant_id==account.tenant_id,
            StaffProfile.user_id==account.id, (StaffProfile.status!='ACTIVE') | StaffProfile.is_deleted.is_(True)).limit(1)))


def school_service_config(user):
    """Authenticated school-facing presentation only; never expose management grants or provider secrets."""
    with get_sessionmaker()() as db:
        service=db.scalar(sm.tenant_query(SchoolSetting,user).where(SchoolSetting.setting_key=='notification'))
        value=service.value_json or {} if service else {}
        owner=db.scalar(sm.tenant_query(User,user).where(User.id==int(value['responsibleUserId']))) if value.get('responsibleUserId') else None
        dictionary=db.scalar(sm.tenant_query(SchoolSetting,user).where(SchoolSetting.setting_key=='dictionary'))
        branding=brand(db,user)
        return {'brand':branding,'service':{'contactPhone':value.get('contactPhone') or branding['contactPhone'],
            'supervisionPhone':branding['supervisionPhone'],
            'responsibleName':owner.real_name if valid_service_owner(db,owner) else '',
            'faq':value.get('faq',[]),'reminderText':value.get('reminderText','请及时处理岗位实习待办。')},
            'announcementCategories':(dictionary.value_json or {}).get('announcementCategories',[]) if dictionary else ['实习通知','安全提醒','材料收集']}


def save_config(user, category, data):
    with sm.transaction(user, f'system.{category}.manage') as db:
        if not sm.school_wide(user): raise no_permission('学校基础规则由校级授权人员维护')
        if category == 'brand':
            school = db.get(Tenant, sm.ids(user)[0])
            item = db.scalar(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == school.id).with_for_update())
            before = brand(db,user)
            sm.edit_version(item.version if item else 0, data['expectedVersion'], brand(db,user))
            if not item: item = TenantBrandConfig(tenant_id=school.id); db.add(item)
            school.school_name, school.short_name = data['schoolName'], data['shortName']
            school.version += 1
            item.platform_name, item.browser_title, item.platform_subtitle = data['platformName'], data['platformName'], data['subtitle']
            item.config_json = {**(item.config_json or {}), 'contactPhone': data['contactPhone'], 'supervisionPhone': data['supervisionPhone']}
            if data.get('logoFileId'):
                from app.models.file import FileObject
                image=sm.row(db,FileObject,data['logoFileId'],user)
                if image.mime_type not in ('image/png','image/jpeg','image/gif') or image.size_bytes>2*1024*1024:
                    raise AppException('VALIDATION_ERROR','校徽须为不超过2兆字节的常见图片')
                bind_system_file(db,user,image.id,'SYSTEM_BRAND',school.id)
            item.badge_file_id=int(data['logoFileId']) if data.get('logoFileId') else None
            item.version = (item.version or 0)+1
        else:
            item = db.scalar(sm.tenant_query(SchoolSetting, user).where(SchoolSetting.setting_key == category).with_for_update())
            before = {**CONFIG_DEFAULTS.get(category,{}), **(item.value_json if item else {})}
            sm.edit_version(item.version if item else 0, data['expectedVersion'], item.value_json if item else {})
            if not item: item = SchoolSetting(tenant_id=sm.ids(user)[0], setting_key=category); db.add(item)
            value = {k:v for k,v in data.items() if k not in {'reason','expectedVersion'}}
            if category == 'notification' and value['responsibleUserId']:
                account = sm.row(db, User, value['responsibleUserId'], user)
                if not valid_service_owner(db,account): raise AppException('VALIDATION_ERROR','请选择资料在职、账号未停用且未过期的校内教师或管理人员')
            if category == 'dictionary':
                # Older callers omit provenance; changing aliases must not erase it.
                value={**before,**value}
                aliases = [r['alias'] for r in value['aliases']]
                if len(set(aliases)) != len(aliases): raise AppException('VALIDATION_ERROR','匹配别名不能重复')
                codes = {r['code'] for r in value['aliases']}
                if codes != sm.unique_organization_codes(db,user,codes):
                    raise AppException('VALIDATION_ERROR','别名必须对应本校唯一的启用组织代码；无匹配或多个候选时请先核对组织')
            item.value_json = value; item.version = (item.version or 0)+1
        db.flush()
        audit(db, user, 'CONFIG_SAVE', category, item.id, {'reason': data['reason'], 'version': item.version,
            'changes':config_changes(before,data)})
        return {'version': item.version}


def list_tasks(user, page=1, size=30, keyword='', status=''):
    enforce_permission(user, 'system.task.view')
    with get_sessionmaker()() as db:
        query = sm.tenant_query(ExcelImportJob, user)
        if not sm.school_wide(user): query = query.where(ExcelImportJob.operator_id == sm.ids(user)[1])
        if keyword:
            matches=[ExcelImportJob.file_name.contains(keyword,autoescape=True),ExcelImportJob.operator_name.contains(keyword,autoescape=True)]
            if keyword.isdecimal() and len(keyword)<=19: matches.append(ExcelImportJob.id==int(keyword))
            query=query.where(or_(*matches))
        if status: query=query.where(ExcelImportJob.status==status)
        return sm.paginated(db, query.order_by(ExcelImportJob.id.desc()), page, size, lambda r:{**sm.common(r),
            'typeName':{'IDENTITY_STUDENTS':'学生开户','IDENTITY_STAFF':'教职工开户','IDENTITY_ORGANIZATIONS':'组织导入','DIRECTORY_EXPORT':'基础资料导出','enterprise':'企业资料导入'}.get(r.biz_type,'业务导入'),
            'name':r.file_name or '导入任务', 'operator':r.operator_name, 'total':r.total_rows,
            'succeeded':r.success_rows, 'failed':r.invalid_rows+r.failed_rows, 'createdAt':r.created_at,
            'canDownload':r.biz_type=='DIRECTORY_EXPORT' and r.status=='SUCCESS' and r.operator_id==sm.ids(user)[1] and bool(r.preview_json),
            'canRetry':r.biz_type=='DIRECTORY_EXPORT' and r.status=='FAILED' and r.operator_id==sm.ids(user)[1] and bool(r.expires_at and r.expires_at>datetime.utcnow()),
            'message':r.remark or '',
            'canOpen':r.module_key=='system' and r.biz_type.startswith('IDENTITY_') and r.operator_id==sm.ids(user)[1],
            'path':('/admin/system/organizations?jobId='+str(r.id) if r.biz_type=='IDENTITY_ORGANIZATIONS' else '/admin/system/identity-import/'+('staff' if r.biz_type=='IDENTITY_STAFF' else 'students')+'?jobId='+str(r.id)) if r.module_key=='system' else ''})


def audit_changes(action, detail):
    """只投影管理事件的已知业务字段，不把任意审计载荷或秘密交给页面。"""
    labels={'name':'名称','code':'组织代码','parentId':'上级组织编号','status':'状态','grade':'年级',
        'collegeId':'院系编号','majorId':'专业编号','classId':'班级编号','departmentId':'部门编号',
        'educationYears':'学制（年）','trainingLevel':'培养层次','nationalCode':'国家专业目录代码',
        'userId':'人员账号编号','memberName':'关联人员','roleName':'关联角色','roleCode':'责任身份',
        'scopeType':'负责类型','refId':'负责对象编号','refName':'负责对象名称','enabled':'成员授权','expiresAt':'账号有效期'}
    fields={'ORG_SAVE':['name','code','parentId','status','grade','educationYears','trainingLevel','nationalCode'],
        'PERSON_SAVE':['name','collegeId','majorId','classId','departmentId','grade','status'],
        'ROLE_SAVE':['name','status'],'ROLE_MEMBER':['userId','memberName','roleName','enabled'],
        'SCOPE_SAVE':['userId','memberName','roleCode','scopeType','refId','refName','status']}
    def display(key,value):
        if value is None or value=='': return '未设置'
        if isinstance(value,(dict,list)): return '未记录可展示内容'
        if key=='status': return sm.STATUS_LABELS.get(value,'待核对')
        if key=='scopeType': return {'COLLEGE':'院系','MAJOR':'专业','CLASS':'班级','STUDENT':'学生'}.get(value,'待核对')
        if key=='trainingLevel': return {'SECONDARY':'中职','HIGHER':'高职','FIVE_YEAR':'五年一贯制'}.get(value,'待核对')
        if key=='roleCode': return ROLE_NAMES.get(value,'自定义管理身份')
        if key=='enabled': return '已授权' if value is True else '未授权'
        if key=='expiresAt':
            from datetime import timezone,timedelta
            try:
                moment=datetime.fromisoformat(str(value).replace('Z','+00:00'))
                return (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M（北京时间）')
            except ValueError: return '时间待核对'
        return str(value)
    before=detail.get('before') if isinstance(detail.get('before'),dict) else {}
    after=detail.get('after') if isinstance(detail.get('after'),dict) else detail
    keys=['status','expiresAt'] if action.startswith('ACCOUNT_') else fields.get(action,[])
    changes=[{'field':key,'label':labels[key],'before':display(key,before[key]) if key in before else '此前未记录',
        'after':display(key,after[key])} for key in keys if key in after and (key not in before or before[key]!=after[key])]
    if action=='CONFIG_SAVE':
        changes=[{'field':c['field'],'label':CONFIG_LABELS[c['field']],
            'before':'已脱敏' if c['field'] in {'contactPhone','supervisionPhone'} else display('',c.get('before')),
            'after':'已脱敏' if c['field'] in {'contactPhone','supervisionPhone'} else display('',c.get('after'))}
            for c in detail.get('changes',[]) if isinstance(c,dict) and c.get('field') in CONFIG_LABELS]
    if action=='ROLE_SAVE':
        for key,label in [('added','新增功能权限'),('removed','撤销功能权限')]:
            values=detail.get(key,[])
            if isinstance(values,list) and values:
                names='、'.join(permission_name(code) if '*' not in code else '历史通配权限' for code in values if isinstance(code,str))
                changes.append({'field':key,'label':label,'before':'无' if key=='added' else names,'after':names if key=='added' else '无'})
    if action=='RESPONSIBILITY_HANDOFF':
        changes.append({'field':'assignee','label':'承办人编号','before':display('',detail.get('fromUserId')),'after':display('',detail.get('toUserId'))})
    if action=='LEAVE_POLICY_PUBLISH':
        names={'GUIDE':'指导教师','COLLEGE':'院系责任人','SCHOOL':'校级责任人'}
        nodes=detail.get('nodes',[])
        if isinstance(nodes,list):
            changes.append({'field':'approval','label':'发布的请假审批顺序','before':'原申请继续沿用其提交时版本',
                'after':' → '.join(names.get(n.get('type'),'待核对节点') for n in nodes if isinstance(n,dict))})
    return changes


def list_audit(user, page=1, size=30, keyword='', export=False, start_at=None, end_at=None):
    enforce_permission(user, 'system.audit.export' if export else 'system.audit.view')
    from datetime import timezone, timedelta
    start_at=start_at.astimezone(timezone.utc).replace(tzinfo=None) if start_at and start_at.tzinfo else start_at
    end_at=end_at.astimezone(timezone.utc).replace(tzinfo=None) if end_at and end_at.tzinfo else end_at
    if start_at and end_at and start_at>end_at: raise AppException('VALIDATION_ERROR','开始时间不能晚于结束时间')
    with get_sessionmaker()() as db:
        query = select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == sm.ids(user)[0])
        if start_at: query=query.where(SecurityAuditLog.created_at>=start_at)
        if end_at: query=query.where(SecurityAuditLog.created_at<=end_at)
        if keyword:
            query = query.where(or_(SecurityAuditLog.operator_name.contains(keyword,autoescape=True),
                                    SecurityAuditLog.resource_id==keyword, SecurityAuditLog.action==keyword,
                                    SecurityAuditLog.action.in_([code for code,label in ACTION_NAMES.items() if keyword in label])))
        def item(r): return {'id':str(r.id), 'operator':r.operator_name or '系统', 'role':r.current_role,
            'roleLabel':(r.detail_json or {}).get('identityName') or (ROLE_NAMES.get(r.current_role,'自定义管理身份')+'（历史名称未留存）' if r.current_role else '系统记录'),'actionLabel':ACTION_NAMES.get(r.action,r.action if r.action and any('\u4e00'<=c<='\u9fff' for c in r.action) else '其他业务操作'),
            'action':r.action,'resource':r.resource,'objectId':r.resource_id,'result':sm.STATUS_LABELS.get(r.result,{'DENIED':'权限拒绝','FAIL':'失败'}.get(r.result,'已记录')),
            'createdAt':r.created_at,'reason':(r.detail_json or {}).get('reason',''), 'traceId':r.trace_id,
            'changes':audit_changes(r.action or '',r.detail_json or {})}
        result = sm.paginated(db,query.order_by(SecurityAuditLog.id.desc()),page,5000 if export else size,item)
        if export:
            if result['total']>5000: raise AppException('VALIDATION_ERROR','当前筛选超过5000条，请缩小范围后导出')
            audit(db,user,'AUDIT_EXPORT','audit','query',{'rows':result['total']}); db.commit()
            return build_ledger_xlsx('操作审计',['操作人','当时身份','操作','对象','结果','时间（北京时间）','原因','变更明细'],
                [[r['operator'],r['roleLabel'],r['actionLabel'],r['objectId'],r['result'],
                  r['createdAt'].replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None),r['reason'],
                  '\n'.join(f'{c["label"]}：{c["before"]} → {c["after"]}' for c in r['changes'])] for r in result['items']])
        return result


def external_status(user):
    enforce_permission(user,'system.integration.view')
    from app.services.file_scan_config import get_file_scan_config
    from app.services.system_evidence import read_receipts
    from app.models import InternshipRegulatoryTask
    from app.models.file import FileScanRecord
    from app.models.message import MessageChannelDelivery, MessageEventOutbox, UnifiedMessage
    scan = get_file_scan_config()
    with get_sessionmaker()() as db:
        latest_scan=db.scalar(sm.tenant_query(FileScanRecord,user).where(FileScanRecord.completed_at.is_not(None))
            .order_by(FileScanRecord.completed_at.desc(),FileScanRecord.id.desc()).limit(1))
        sms=db.scalar(sm.tenant_query(MessageChannelDelivery,user).where(MessageChannelDelivery.channel=='SMS')
            .order_by(MessageChannelDelivery.updated_at.desc(),MessageChannelDelivery.id.desc()).limit(1))
        message=db.scalar(sm.tenant_query(MessageEventOutbox,user)
            .order_by(MessageEventOutbox.updated_at.desc(),MessageEventOutbox.id.desc()).limit(1))
        delivered=db.scalar(sm.tenant_query(UnifiedMessage,user).where(UnifiedMessage.delivery_status=='DELIVERED',
            UnifiedMessage.delivered_at.is_not(None),UnifiedMessage.receiver_user_id.is_not(None))
            .order_by(UnifiedMessage.delivered_at.desc(),UnifiedMessage.id.desc()).limit(1))
        reports=[]
        for code,label in [('RP01','第一套监管报送'),('RP02','第二套监管报送')]:
            last=db.scalar(sm.tenant_query(InternshipRegulatoryTask,user).where(InternshipRegulatoryTask.report_code==code).order_by(InternshipRegulatoryTask.updated_at.desc()).limit(1))
            state={'ACCEPTED':'最近报送已收到接收回执','REJECTED':'最近报送被退回','RECEIPT_PENDING':'最近报送待接收回执','SUBMITTED_EXTERNAL':'已提交，待接收回执'}.get(last.status if last else '', '尚无外部接收回执')
            reports.append({'name':label,'statusLabel':state,'detail':'依据正式报送任务及接收回执，不表示其他报送已通过',
                'failureReason':'接收方退回，请在监管报送原单查看补正要求' if last and last.status=='REJECTED' else '',
                'lastCheckedAt':last.receipt_at if last else None})
        sms_result=delivery_status(sms,external=True)
        message_result=delivery_status(message)
        if delivered and (not message_result['lastCheckedAt'] or delivered.delivered_at > message_result['lastCheckedAt']):
            message_result={'statusLabel':'最近站内消息已送达','lastCheckedAt':delivered.delivered_at,'failureReason':''}
        scan_result={'statusLabel':'尚无已完成扫描回执','failureReason':'','lastCheckedAt':None}
        if latest_scan:
            scan_result={'statusLabel':{'CLEAN':'最近文件扫描通过','INFECTED':'最近扫描发现风险文件','ERROR':'最近扫描失败'}.get(latest_scan.result,'扫描结果待核对'),
                'lastCheckedAt':latest_scan.completed_at,
                'failureReason':{'ClamAVUnavailable':'扫描服务不可用或连接超时','ClamAVError':'文件或扫描返回结果异常'}.get(latest_scan.error_code,'扫描未完成，请联系实施人员核对') if latest_scan.result=='ERROR' else ''}
    service=school_service_config(user)['service']
    evidence=read_receipts(sm.ids(user)[0])
    items=[]
    for code,name in [('ENTERPRISE','企业信息核验'),('MAP','地图与位置')]:
        receipts=[r for r in evidence['items'] if r.get('kind')=='INTEGRATION' and r.get('service')==code]
        last=max(receipts,key=lambda r:datetime.fromisoformat(r['checkedAt'])) if receipts else None
        items.append({'name':name,'statusLabel':last['statusLabel'] if last else '尚无有效检测回执',
            'detail':last['detail'] if last else '仅保留现有业务能力；外部服务连通性尚未验证',
            'lastCheckedAt':last['checkedAt'] if last else None,'failureReason':last['failureReason'] if last else '',
            'receiptId':last['sha256'][:12] if last else ''})
    items.extend([
        {'name':'站内消息',**message_result,'detail':'依据业务消息投递队列与个人送达记录；送达不等于收件人已读'},
        {'name':'短信服务',**sms_result,'configurationLabel':'已启用' if settings.SMS_ENABLED else '未启用',
         'detail':'依据本校最近渠道投递记录；历史发送回执不代表当前配置可用'},
        {'name':'文件安全扫描',**scan_result,'configurationLabel':'已启用' if scan.enabled else '未启用',
         'detail':'依据实际扫描完成记录；仅证明对应文件当时的扫描结果'},*reports])
    return {'checkedAt':datetime.utcnow(),'evidenceNote':evidence['note'],
        'items':[{**r,'responsibleName':service['responsibleName'] or '学校尚未指定服务承办人'} for r in items]}


def delivery_status(row,external=False):
    if row is None: return {'statusLabel':'尚无投递回执','lastCheckedAt':None,'failureReason':''}
    states={'PENDING':'等待投递','PROCESSING':'正在投递','SUCCEEDED':'最近站内投递完成',
        'SENT':'最近渠道发送成功','RETRY_WAIT':'投递失败，等待重试','DEAD':'投递失败，已停止重试','SKIPPED':'最近投递未执行'}
    failures={'SMS_DISABLED':'短信未启用','SMS_PROVIDER_NOT_CONFIGURED':'短信服务商尚未配置',
        'PHONE_UNAVAILABLE':'收件人缺少有效手机号','TRANSIENT_PROVIDER':'服务商请求失败，可重试',
        'INVALID_PROVIDER_RESPONSE':'服务商返回内容不符合预期'}
    failed=row.status in ('RETRY_WAIT','DEAD','SKIPPED')
    completed=row.sent_at if external else row.processed_at
    if row.status in ('SENT','SUCCEEDED') and not completed:
        return {'statusLabel':'投递回执不完整，待核对','lastCheckedAt':None,'failureReason':'缺少实际完成时间'}
    return {'statusLabel':states.get(row.status,'投递状态待核对'),
        'lastCheckedAt':completed or (row.updated_at if row.attempt_count else None),
        'failureReason':failures.get(row.last_error_code,'投递未完成，请联系服务承办人核对') if failed else ''}


def runtime_status(user):
    enforce_permission(user,'system.runtime.view')
    from app.main import readiness
    from fastapi import HTTPException
    try: health = readiness()
    except HTTPException as exc: health = exc.detail
    labels={'database':'数据库','redis':'认证缓存','fileStorage':'文件存储'}
    states={'READY':'检测通过','NOT_CONFIGURED':'未配置','UNAVAILABLE':'服务不可用','SCHEMA_MISMATCH':'数据库版本待升级','UNKNOWN':'未检测'}
    rows=[{'name':label,'statusLabel':states.get(health['checks'].get(key),'未检测')} for key,label in labels.items()]
    with get_sessionmaker()() as db:
        pending=db.scalar(select(func.count()).select_from(AuditOutbox).where(AuditOutbox.tenant_id==sm.ids(user)[0],AuditOutbox.status.in_(['RETRY_WAIT','DEAD'])))
        rows.append({'name':'审计投递异常','statusLabel':f'{pending}条待处理'})
    from app.services.system_evidence import read_receipts
    evidence=read_receipts(sm.ids(user)[0])
    storage=Path(settings.FILE_STORAGE_DIR)
    try:
        free=shutil.disk_usage(storage).free
        rows.append({'name':'附件可用存储','statusLabel':f'{free//(1024**3)} GB（吉字节）','detail':'文件所在磁盘剩余空间；不代表学校分配额度'})
    except OSError: rows.append({'name':'附件可用存储','statusLabel':'无法检测'})
    from app.models.file import FileJob
    with get_sessionmaker()() as db:
        failed_scans=db.scalar(select(func.count()).select_from(FileJob).where(FileJob.tenant_id==sm.ids(user)[0],
            FileJob.job_type=='FILE_SCAN',FileJob.status.in_(['RETRY','DEAD']),FileJob.is_deleted.is_(False)))
    rows.append({'name':'文件扫描异常任务','statusLabel':f'{failed_scans}条待处理','detail':'文件未通过安全检查时保持不可用于业务'})
    return {'items':rows,'checkedAt':datetime.utcnow(),'schemaRevision':health['checks'].get('schemaRevision'),
        'backups':[r for r in evidence['items'] if r.get('kind') in ('BACKUP','RESTORE') or not r.get('kind')],
        'backupNote':evidence['note']}


def delivery_records(user, kind, page=1,size=30,keyword=''):
    permission='migration' if kind=='MIGRATION' else 'delivery'
    enforce_permission(user,f'system.{permission}.view')
    with get_sessionmaker()() as db:
        query=sm.tenant_query(SchoolDeliveryRecord,user).where(SchoolDeliveryRecord.kind==kind)
        if keyword: query=query.where(or_(SchoolDeliveryRecord.title.contains(keyword,autoescape=True),SchoolDeliveryRecord.detail_json['source'].as_string().contains(keyword,autoescape=True)))
        result=sm.paginated(db,query.order_by(SchoolDeliveryRecord.id.desc()),
            page,size,lambda r:{**sm.common(r),'title':r.title,'ownerUserId':str(r.owner_user_id or ''),
                               'statusLabel':{'PENDING':'待处理','REVIEW':'待核对','VERIFIED':'学校登记已核验'}.get(r.status,'待核对'),
                               'details':r.detail_json,'checkedAt':r.checked_at,'evidenceLabel':'学校登记资料，须另行核验'})
        from app.services.system_evidence import read_receipts
        evidence=read_receipts(sm.ids(user)[0])
        result['receipts']=[r for r in evidence['items'] if r.get('kind')=='MIGRATION'] if kind=='MIGRATION' else []
        result['version']={'name':settings.RELEASE_VERSION or '未登记发布版本',
            'commit':settings.RELEASE_COMMIT or '', 'schemaRevision':settings.EXPECTED_ALEMBIC_REVISION or ''}
        result['evidenceNote']=evidence['note']
        return result


def save_record(user, kind, data, identifier=None):
    permission='migration' if kind=='MIGRATION' else 'delivery'
    with sm.transaction(user,f'system.{permission}.manage') as db:
        item=sm.row(db,SchoolDeliveryRecord,identifier,user,True) if identifier else SchoolDeliveryRecord(tenant_id=sm.ids(user)[0],kind=kind)
        sm.edit_version(item.version or 0,data['expectedVersion'],{'title':item.title,'status':item.status,
            'ownerUserId':str(item.owner_user_id or ''),**(item.detail_json or {})})
        if item.kind != kind: raise no_permission()
        if data['ownerUserId']: sm.row(db,User,data['ownerUserId'],user)
        item.title,item.status,item.owner_user_id=data['title'],data['status'],int(data['ownerUserId']) if data['ownerUserId'] else None
        item.detail_json={k:data[k] for k in ['source','notes','mappingRules','identityMapping','exceptionResolution','expectedPeople','actualPeople','expectedRecords','actualRecords','expectedFiles','actualFiles','continuationChecked','fileIds']}
        item.version=(item.version or 0)+1; item.checked_at=datetime.utcnow() if data['status']=='VERIFIED' else None
        if data['status']=='VERIFIED' and kind=='MIGRATION':
            if any(not data[key] for key in ['source','mappingRules','identityMapping','exceptionResolution']):
                raise AppException('VALIDATION_ERROR','请补齐来源、映射规则、组织人员对应关系和异常处理记录；无异常也须明确登记')
            if any(data['expected'+part]!=data['actual'+part] for part in ['People','Records','Files']) or not data['continuationChecked']:
                raise AppException('VALIDATION_ERROR','人数、业务记录与附件须对账一致，并完成师生继续办理检查')
        db.add(item);db.flush()
        for fid in data['fileIds']: bind_system_file(db,user,fid,'SYSTEM_MIGRATION' if kind=='MIGRATION' else 'SYSTEM_DOCUMENT',item.id)
        audit(db,user,'DELIVERY_RECORD','delivery',item.id,{'kind':kind,'reason':data['reason'],'declaredStatus':item.status})
        return {'id':str(item.id),'version':item.version}


def bind_system_file(db,user,file_id,kind,target_id):
    from app.services.file_business_binding_service import bind_file_to_business
    return bind_file_to_business(db,file_id=file_id,biz_type=kind,biz_id=target_id,actor=user,
        subject_type='SCHOOL',subject_id=str(sm.ids(user)[0]),module_code='SYSTEM')


def authorize_system_file(db,file,user,action):
    from app.core.permissions import has_permission
    if not db or action not in ('meta','download','preview'):return False
    if file.tenant_id!=sm.ids(user)[0]:return False
    if file.biz_type=='SYSTEM_DIRECTORY_EXPORT':
        from app.services.system_directory_export import authorize_file
        return authorize_file(db,file,user)
    if file.biz_type=='SYSTEM_BRAND':
        return db.scalar(select(TenantBrandConfig.id).where(TenantBrandConfig.tenant_id==file.tenant_id,
            TenantBrandConfig.badge_file_id==file.id,TenantBrandConfig.is_deleted.is_(False))) is not None
    category='migration' if file.biz_type=='SYSTEM_MIGRATION' else 'delivery'
    if not has_permission(user,f'system.{category}.view') or not str(file.biz_id or '').isdigit():return False
    record=db.scalar(sm.tenant_query(SchoolDeliveryRecord,user).where(SchoolDeliveryRecord.id==int(file.biz_id)))
    return bool(record and str(file.id) in (record.detail_json or {}).get('fileIds',[]))
