"""No database mutations: critical authorization, identity-file and approver resolution checks."""
import io
from types import SimpleNamespace as Item
import pytest
from openpyxl import Workbook
from app.core.exceptions import AppException
from app.core.permissions import has_permission
from app.api.v1.system_admin import Organization, RoleChange
from app.services.system_identity_import import _text_identifiers
from app.services.system_leave_policy import resolve, check_nodes
from app.services.mobile_teacher_service import scope_match_row


def test_dictionary_provenance_is_paired_unique_and_cannot_change_business_enums():
    from pydantic import ValidationError
    from app.api.v1.system_admin import Dictionary
    base={'announcementCategories':['实习通知'],'aliases':[],'reason':'来源登记验收'}
    reference={'kind':'major','source':'学校实际使用的专业目录','edition':'合成测试版'}
    assert Dictionary(**base,standardReferences=[reference]).standardReferences[0].edition=='合成测试版'
    for rows in [[{**reference,'edition':''}],[reference,reference],[{**reference,'kind':'approvalStatus'}],
                 [{**reference,'values':['任意新增状态']}]]:
        with pytest.raises(ValidationError): Dictionary(**base,standardReferences=rows)
    assert 'standardReferences' not in Dictionary(**base).model_dump(exclude_unset=True)


def test_delivery_receipt_never_exposes_provider_errors_or_invents_check_time():
    from datetime import datetime
    from app.services.system_settings import delivery_status
    now=datetime(2026,1,1)
    row=Item(status='PENDING',sent_at=None,processed_at=None,updated_at=now,attempt_count=0,last_error_code='secret')
    assert delivery_status(row,True)['lastCheckedAt'] is None
    row.status='DEAD';row.attempt_count=1
    result=delivery_status(row,True)
    assert result['lastCheckedAt']==now and 'secret' not in str(result)
    row.last_error_code='SMS_PROVIDER_NOT_CONFIGURED'
    assert result['statusLabel']=='投递失败，已停止重试'
    assert delivery_status(row,True)['failureReason']=='短信服务商尚未配置'
    row.status='SENT'
    assert delivery_status(row,True)['statusLabel']=='投递回执不完整，待核对'


def test_external_receipts_require_school_time_checksum_and_safe_failure(tmp_path,monkeypatch):
    import hashlib,json
    from app.config import settings
    from app.services.system_evidence import read_receipts
    monkeypatch.setattr(settings,'SYSTEM_EVIDENCE_DIR',str(tmp_path))
    folder=tmp_path/'7';folder.mkdir();path=folder/'probe.json'
    base={'kind':'EXTERNAL_SERVICE','tenantId':7,'service':'MAP','outcome':'FAILED',
          'completedAtUtc':'2026-01-01T00:00:00Z','errorCode':'TIMEOUT','rawResponse':'secret'}
    def write(value):
        path.write_text(json.dumps(value),encoding='utf-8')
        path.with_suffix('.json.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
        return read_receipts(7)['items']
    row=write(base)[0]
    assert row['failureReason']=='服务请求超时' and not row['passed'] and 'secret' not in str(row)
    assert write({**base,'tenantId':8})==[]
    for changes in [{'outcome':'PASSED'},{'completedAtUtc':'2099-01-01T00:00:00Z'},
                    {'completedAtUtc':'2026-01-01'},{'errorCode':'secret'},{'service':'arbitrary'}]:
        assert write({**base,**changes})[0]['statusLabel']=='回执无法读取，未验证'
    assert write({**base,'outcome':'PASSED','errorCode':''})[0]['passed']
    from app.services.system_evidence import backup_summary
    assert backup_summary({'items':write({**base,'errorCode':'unknown'}),'note':''})['statusLabel']=='尚未取得备份与恢复演练回执'
    path.write_text('{}')
    assert '校验失败' in read_receipts(7)['items'][0]['statusLabel']


def test_legacy_preview_omits_empty_or_incomplete_organization_proposals_without_losing_errors():
    from app.services.system_identity_import import public_preview
    problems=[{'row':2,'message':'专业代码不能为空'}]
    job=Item(id=17,version=1,status='FAILED',file_name='旧错误预检.xlsx',total_rows=1,invalid_rows=1,
        expires_at=None,remark=None,receipt_encrypted=None,preview_json={'kind':'students','errors':problems,
            'entries':[{'row':2,'refs':{'college':'colleges:C01','major':'majors:','class':'classes:'}}],
            'newOrganizations':[{'kind':'colleges','code':'C01','name':'拟新增学院'},
                {'kind':'majors','code':'','name':'','parentCode':'C01'},
                {'kind':'classes','code':'','name':'','parentCode':''},
                {'kind':'majors','code':'M01','name':'缺上级专业','parentCode':''}]})
    result=public_preview(job)
    assert result['newOrganizations']==[{'kind':'colleges','code':'C01','name':'拟新增学院'}]
    assert result['newOrganizationCount']==1 and result['errors']==problems
    assert result['invalidRows']==1 and result['status']=='FAILED'


def test_explicit_empty_role_never_restores_static_privileges():
    assert not has_permission({'currentRoleCode':'SCHOOL_ADMIN','permissions':[]},'internship.student.view')
    assert not has_permission({'currentRoleCode':'SCHOOL_ADMIN','permissions':[],'permissionCodes':['*']},'system.account.manage')
    assert has_permission({'currentRoleCode':'CUSTOM_A','permissions':['internship.student.view']},'internship.student.view')
    assert not has_permission({'currentRoleCode':'CUSTOM_A','permissions':['internship.student.view']},'internship.student.password.reset')
    from app.modules.internship.services.internship_safety_authority_service import _role
    from app.modules.internship.services.internship_enterprise_eval_service import _role_code
    custom={'currentRoleCode':'CUSTOM_MENTOR','currentRoleBaseCode':'INTERN_MENTOR','permissions':[]}
    assert _role(custom)==_role_code(custom)=='INTERN_MENTOR'
    assert not has_permission(custom,'internship.leave.review')


def test_permission_names_distinguish_sensitive_and_business_commands():
    from app.services.system_authorization import permission_name
    assert permission_name('internship.student.password.reset') == '受控重置学生登录密码'
    assert permission_name('internship.visit.location.view') == '查看巡访精确位置'
    assert permission_name('internship.compliance.exempt.approve') == '审批上岗材料豁免'
    assert len({permission_name('internship.archive.'+action) for action in ['force','execute','package','revoke']}) == 4
    assert permission_name('future.read','已登记的业务名称') == '已登记的业务名称'


def test_audit_changes_project_only_known_fields_and_freeze_identity_label():
    from app.services.system_settings import audit_changes
    from app.services.system_authorization import audit
    secret='must-never-appear'
    change=audit_changes('PERSON_SAVE',{'before':{'classId':'1','password':secret},
        'after':{'classId':'2','phone':secret,'token':secret,'name':{'unsafe':secret}}})
    assert {'field':'classId','label':'班级编号','before':'1','after':'2'} in change
    assert secret not in str(change)
    role=audit_changes('ROLE_SAVE',{'added':['internship.leave.review'],'removed':['system.person.sensitive'],
        'before':{'status':'ACTIVE'},'after':{'status':'DISABLED'}})
    assert role==[{'field':'status','label':'状态','before':'正常','after':'停用'},
        {'field':'added','label':'新增功能权限','before':'无','after':'审核实习请假'},
        {'field':'removed','label':'撤销功能权限','before':'查看完整联系方式','after':'无'}]
    legacy=audit_changes('SCOPE_SAVE',{'before':{'refId':'1'},'refId':'2','scopeType':'COLLEGE'})
    assert legacy[0]['after']=='院系' and legacy[0]['before']=='此前未记录'
    contacts=audit_changes('CONFIG_SAVE',{'changes':[{'field':'contactPhone','before':secret,'after':secret},
        {'field':'password','before':secret,'after':secret}]})
    assert len(contacts)==1 and secret not in str(contacts)
    assert audit_changes('UNKNOWN',{'before':{'password':secret},'after':{'password':secret}})==[]
    for expiry in ['2026-10-08T00:00:00Z','2026-10-08T00:00:00']:
        assert audit_changes('ACCOUNT_EXPIRY',{'after':{'expiresAt':expiry}})[0]['after']=='2026-10-08 08:00（北京时间）'
    rows=[]
    audit(Item(add=rows.append),{'tenantId':'7','userId':'10','currentRoleCode':'CUSTOM_TEST','currentRoleName':'操作时身份'},
        'PERSON_SAVE','staff',1,{'reason':'身份快照验收'})
    assert rows[0].detail_json['identityName']=='操作时身份'


def test_import_identifiers_preserve_leading_zeros_and_reject_numeric_or_formula():
    for value, valid in [('000123',True),(123,False),('=1+1',False)]:
        wb=Workbook();ws=wb.active;ws.append(['学号或工号']);ws.append([value]);content=io.BytesIO();wb.save(content)
        if valid: _text_identifiers(content.getvalue())
        else:
            with pytest.raises(AppException): _text_identifiers(content.getvalue())


def test_stable_scope_distinguishes_same_name_and_survives_rename():
    scope={'mode':'SCOPED','roleCode':'COLLEGE_ADMIN','collegeIds':{12}}
    assert scope_match_row(scope,college_id=12,college_name='改名后学院')
    assert not scope_match_row(scope,college_id=13,college_name='改名后学院')
    assert not scope_match_row(scope,college_name='改名后学院')


def test_leave_nodes_require_unambiguous_distinct_real_assignees():
    nodes=[{'type':'GUIDE','roleCode':'TEACH','userId':''},{'type':'COLLEGE','roleCode':'COLLEGE','userId':''}]
    context={'roles':{'TEACH':Item(base_role_code='INTERN_MENTOR',role_code='TEACH'),
                      'COLLEGE':Item(base_role_code='COLLEGE_ADMIN',role_code='COLLEGE')},
        'members':{'TEACH':[Item(id=10,real_name='教师甲')],'COLLEGE':[Item(id=11,real_name='院系负责人')]},
        'scopes':{(11,'COLLEGE'):{('COLLEGE',20)}},'majors':{},'classes':{}}
    record=Item(advisor_user_id=10);student=Item(major_id=None,class_id=None,college_id=20)
    check_nodes(nodes)
    assert [s['userId'] for s in resolve(record,student,nodes,context)]==['10','11']
    context['members']['COLLEGE'].append(Item(id=12,real_name='另一负责人'));context['scopes'][(12,'COLLEGE')]={('COLLEGE',20)}
    with pytest.raises(AppException,match='多个候选'): resolve(record,student,nodes,context)
    context['members']['COLLEGE']=[Item(id=10,real_name='教师甲')];context['scopes'][(10,'COLLEGE')]={('COLLEGE',20)}
    with pytest.raises(AppException,match='同一人'): resolve(record,student,nodes,context)
    with pytest.raises(AppException): check_nodes(nodes[::-1])


def test_management_input_rejects_tenant_injection_and_invalid_state():
    from pydantic import ValidationError
    with pytest.raises(ValidationError): Organization(name='院系',code='001',reason='测试',tenantId='2')
    with pytest.raises(ValidationError): Organization(name='院系',code='001',reason='测试',status='APPROVED')
    with pytest.raises(ValidationError): RoleChange(name='管理员',baseRole='SYSTEM_ADMIN',permissions=[],reason='测试',userType='STUDENT')


def test_script_receipts_require_hash_and_matching_school(tmp_path,monkeypatch):
    import hashlib,json
    from app.config import settings
    from app.services.system_evidence import read_receipts
    monkeypatch.setattr(settings,'SYSTEM_EVIDENCE_DIR',str(tmp_path))
    folder=tmp_path/'7';folder.mkdir()
    path=folder/'migration.json'
    value={'gate':'G19','tenantId':7,'g19Qualified':True,'databaseQualified':True,'fileBytesQualified':True,
           'verification':{'tableCounts':[],'countMismatches':[],'logicalOrphans':[]}}
    path.write_text(json.dumps(value),encoding='utf-8')
    assert '缺少校验' in read_receipts(7)['items'][0]['statusLabel']
    checksum=folder/'migration.json.sha256';checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='utf-8')
    assert read_receipts(7)['items'][0]['kind']=='MIGRATION'
    assert read_receipts(8)['items']==[]
    path.write_text(json.dumps({**value,'tenantId':8}),encoding='utf-8')
    assert '校验失败' in read_receipts(7)['items'][0]['statusLabel']
    checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='utf-8')
    assert read_receipts(7)['items']==[]
    for payload,kind,passed in [
        ({'product':'internship-standalone','backupSetId':'test'},'BACKUP',False),
        ({'product':'internship-standalone','backupSetId':'test','database':{'sha256':'a'*64,'sizeBytes':1},'files':{'sha256':'b'*64,'sizeBytes':1}},'BACKUP',True),
        ({'gate':'C09-RESTORE','verdict':'PASS','tableCount':1,'externalStorageObjects':0,
            'localFileObjectsVerified':0,'hashedFileObjectsVerified':0,'restoreSeconds':0},'RESTORE',True),
        ({'gate':'C09-RESTORE','verdict':'FAIL','tableCount':1,'externalStorageObjects':0},'RESTORE',False),
    ]:
        path.write_text(json.dumps(payload),encoding='utf-8')
        checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='utf-8')
        row=read_receipts(7)['items'][0]
        assert row['kind']==kind and row['passed'] is passed
    for malformed in [[], {'gate':'G19','tenantId':7,'verification':[{'unexpected':'shape'}]},
        {'gate':'G19','tenantId':7,'verification':{'tableCounts':'t_user'}}]:
        path.write_text(json.dumps(malformed),encoding='utf-8')
        checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='utf-8')
        assert read_receipts(7)['items'][0]['statusLabel']=='回执无法读取，未验证'


@pytest.mark.parametrize('kind,changes',[
    ('BACKUP',{'database':{'sha256':'not-a-checksum','sizeBytes':1}}),
    ('BACKUP',{'files':{'sha256':'b'*64,'sizeBytes':True}}),
    ('RESTORE',{'localFileObjectsVerified':-1}),
    ('RESTORE',{'hashedFileObjectsVerified':2}),
    ('RESTORE',{'restoreSeconds':-1}),
    ('MIGRATION',{'databaseQualified':False}),
    ('MIGRATION',{'fileBytesQualified':'false'}),
    ('MIGRATION',{'verdict':'FAIL_VERIFY'}),
    ('MIGRATION',{'verification':{'tableCounts':[{'table':'t_user'}],'countMismatches':[{'table':'t_user'}],'logicalOrphans':[]}}),
    ('MIGRATION',{'verification':{'tableCounts':[],'countMismatches':[],'logicalOrphans':[]}}),
])
def test_script_receipts_do_not_promote_contradictory_or_incomplete_evidence(tmp_path,monkeypatch,kind,changes):
    import hashlib,json
    from app.config import settings
    from app.services.system_evidence import read_receipts
    values={
        'BACKUP':{'product':'internship-standalone','backupSetId':'test',
            'database':{'sha256':'a'*64,'sizeBytes':1},'files':{'sha256':'b'*64,'sizeBytes':1}},
        'RESTORE':{'gate':'C09-RESTORE','verdict':'PASS','tableCount':1,'externalStorageObjects':0,
            'localFileObjectsVerified':1,'hashedFileObjectsVerified':1,'restoreSeconds':0},
        'MIGRATION':{'gate':'G19','tenantId':7,'verdict':'PASS','g19Qualified':True,
            'databaseQualified':True,'fileBytesQualified':True,
            'verification':{'tableCounts':[{'table':'t_user'}],'countMismatches':[],'logicalOrphans':[]}},
    }
    monkeypatch.setattr(settings,'SYSTEM_EVIDENCE_DIR',str(tmp_path))
    folder=tmp_path/'7';folder.mkdir();path=folder/'receipt.json'
    def read(value):
        path.write_text(json.dumps(value),encoding='utf-8')
        path.with_suffix('.json.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest(),encoding='utf-8')
        return read_receipts(7)['items'][0]
    # Pure parser fixtures; these files never become a real school's delivery evidence.
    rejected=read({**values[kind],**changes})
    assert rejected['statusLabel'] not in {'备份脚本已完成','恢复演练通过','数据与附件核对通过，仍须师生办理验收'}
    assert rejected.get('passed') is False
    assert read(values[kind]).get('passed') is True


def test_backup_summary_keeps_missing_failed_and_restore_evidence_distinct():
    from app.services.system_evidence import backup_summary
    def summary(*items): return backup_summary({'items':list(items),'note':'真实回执来源'})['statusLabel']
    backup={'kind':'BACKUP','passed':True}
    restore={'kind':'RESTORE','passed':True}
    assert summary()=='尚未取得备份与恢复演练回执'
    assert summary({'kind':'MIGRATION','passed':True})==summary()
    assert summary(backup)=='已有备份回执，尚缺恢复演练回执'
    assert summary(restore)=='尚缺备份完成回执'
    assert summary(backup,restore)=='已有备份与恢复回执，请核对时间和版本'
    assert summary(backup,{'kind':'RESTORE','passed':False})=='存在失败或尚未核验的回执'
    assert summary(backup,restore,{'statusLabel':'校验失败'})=='存在失败或尚未核验的回执'
def test_stable_advisor_never_falls_back_to_names_and_only_todos_keep_unavailable(monkeypatch):
    from types import SimpleNamespace
    from app.modules.internship.services import internship_todo_helper as todo
    monkeypatch.setattr(todo,'_tid',lambda:7)
    record=SimpleNamespace(advisor_user_id=11,advisor_name='同名教师')
    for row,expected in [(None,0),(SimpleNamespace(id=11,tenant_id=8,status='ACTIVE',is_deleted=False),0),
            (SimpleNamespace(id=11,tenant_id=7,status='DISABLED',is_deleted=False),11),
            (SimpleNamespace(id=11,tenant_id=7,status='ACTIVE',is_deleted=True),11)]:
        db=SimpleNamespace(get=lambda model,identifier:row)
        assert todo.resolve_advisor_assignee_id(db,record)==0
        assert todo.resolve_advisor_assignee_id(db,record,preserve_unavailable=True)==expected
