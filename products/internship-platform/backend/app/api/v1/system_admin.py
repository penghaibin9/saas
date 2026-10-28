"""学校系统管理入口。学校身份由认证上下文裁定；所有写入严格拒绝多余字段。"""
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.response import success
from app.core.security import get_current_user
from app.services import system_management as service, system_identity_import as identity
from app.services import system_settings as configurations
from app.services import system_directory_export as directory_exports
from app.services.xlsx_util import read_safe_upload

router = APIRouter(prefix='/system', tags=['学校系统管理'])
OrgKind = Literal['colleges', 'majors', 'classes', 'departments']
PersonKind = Literal['student', 'staff']
AccountStatus = Literal['', 'BOUND', 'UNBOUND']
ImportKind = Literal['students', 'staff', 'organizations']
Id = str


@router.get('/school-service')
def school_service(user=Depends(get_current_user)):
    return success(configurations.school_service_config(user))


@router.get('/context')
def context(user=Depends(get_current_user)):
    from app.api.v1.standalone_rbac import current_context
    from app.db.session import get_sessionmaker
    value = current_context(user)['data']
    with get_sessionmaker()() as db:
        value['brand'] = configurations.brand(db, user)
    return success(value)


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expectedVersion: int = Field(default=0, ge=0)
    reason: str = Field(min_length=2, max_length=500)


class Organization(Change):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50, pattern=r'^[\w.-]+$')
    parentId: str = Field(default='', pattern=r'^\d*$')
    status: Literal['ACTIVE','DISABLED'] = 'ACTIVE'
    grade: str = Field(default='', max_length=20)
    educationYears: int = Field(default=3, ge=1, le=8)
    trainingLevel: Literal['', 'SECONDARY', 'HIGHER', 'FIVE_YEAR'] = ''
    nationalCode: str = Field(default='',max_length=20,pattern=r'^\d*$')
    confirmImpact: bool = False
    impactFingerprint: str = Field(default='',max_length=64,pattern=r'^[0-9a-f]*$')


class Person(Change):
    name: str = Field(min_length=1, max_length=100)
    collegeId: str = Field(default='',pattern=r'^\d*$')
    departmentId: str = Field(default='', pattern=r'^\d*$')
    classId: str = Field(default='', pattern=r'^\d*$')
    grade: str = Field(default='', max_length=20)
    phone: str = Field(default='', pattern=r'^[0-9+ -]{0,30}$')
    status: Literal['ACTIVE','DISABLED'] = 'ACTIVE'
    confirmImpact: bool = False


class AccountChange(Change):
    action: Literal['ENABLE','DISABLE','UNLOCK','RESET','EXPIRY']
    expiresAt: datetime | None = None

    @field_validator('expiresAt')
    @classmethod
    def utc_expiry(cls, value):
        from datetime import timezone
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value


class RoleChange(Change):
    name: str = Field(min_length=1, max_length=100)
    baseRole: str = Field(min_length=1, max_length=50)
    permissions: list[str] = Field(max_length=1000)
    status: Literal['ACTIVE','DISABLED'] = 'ACTIVE'
    sensitiveConfirmed: bool = False


class MemberChange(Change):
    userId: str = Field(pattern=r'^\d+$')
    enabled: bool


class ScopeChange(Change):
    userId: str = Field(pattern=r'^\d+$')
    roleCode: str = Field(min_length=1, max_length=50)
    scopeType: Literal['COLLEGE','MAJOR','CLASS']
    refId: str = Field(pattern=r'^\d+$')
    status: Literal['ACTIVE','DISABLED'] = 'ACTIVE'


class Confirm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedVersion: int = Field(ge=0)


def spreadsheet(content, name):
    from urllib.parse import quote
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(name)}", 'Cache-Control': 'no-store'})


@router.get('/organizations/{kind}')
def organizations(kind: OrgKind, page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
                  keyword: str = Query('', max_length=100), user=Depends(get_current_user)):
    return success(service.list_organizations(user, kind, page, pageSize, keyword))


@router.get('/selection')
def selected_object(kind:Literal['colleges','majors','classes','departments','accounts','staff','student','batches'],identifier:int,user=Depends(get_current_user)):
    if kind=='batches':return success(leave_policy.batches(user,identifier=identifier))
    return success(service.selected_object(user,kind,identifier))


@router.get('/batches')
def system_batches(page:int=Query(1,ge=1),pageSize:int=Query(50,ge=1,le=100),keyword:str=Query('',max_length=100),user=Depends(get_current_user)):
    return success(leave_policy.batches(user,page,pageSize,keyword))


@router.get('/exports/{kind}')
def directory_export(kind:Literal['colleges','majors','classes','departments','staff','student'],keyword:str=Query('',max_length=100),
                     accountStatus:AccountStatus='',user=Depends(get_current_user)):
    return spreadsheet(service.export_directory(user,kind,keyword,accountStatus),service.DIRECTORY_LABELS[kind]+'资料导出.xlsx')


class DirectoryExport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    keyword: str = Field(default='',max_length=100)
    accountStatus: AccountStatus = ''


@router.post('/exports/{kind}')
def queue_directory_export(kind:Literal['colleges','majors','classes','departments','staff','student'],body:DirectoryExport,user=Depends(get_current_user)):
    return success(directory_exports.enqueue(user,kind,body.keyword,body.accountStatus))


@router.post('/tasks/{identifier}/retry-export')
def retry_directory_export(identifier:int,body:Confirm,user=Depends(get_current_user)):
    return success(directory_exports.retry(user,identifier,body.expectedVersion))


@router.post('/organizations/{kind}')
def create_organization(kind: OrgKind, body: Organization, user=Depends(get_current_user)):
    return success(service.save_organization(user, kind, body.model_dump()))


@router.put('/organizations/{kind}/{identifier}')
def update_organization(kind: OrgKind, identifier: int, body: Organization, user=Depends(get_current_user)):
    return success(service.save_organization(user, kind, body.model_dump(), identifier))


@router.get('/organizations/{kind}/{identifier}/impact')
def organization_impact(kind:OrgKind,identifier:int,user=Depends(get_current_user)):
    return success(service.organization_impact(user,kind,identifier))


@router.get('/people/{kind}')
def people(kind: PersonKind, page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
           keyword: str = Query('', max_length=100), accountStatus:AccountStatus='',user=Depends(get_current_user)):
    return success(service.list_people(user, kind, page, pageSize, keyword,accountStatus))


@router.get('/people/{kind}/{identifier}/impact')
def person_impact(kind: PersonKind, identifier: int, user=Depends(get_current_user)):
    return success(service.impact(user, kind, identifier))


class SensitivePurpose(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason:str=Field(min_length=5,max_length=500)


class BindingRepair(Change):
    userId:str=Field(pattern=r'^\d+$')
    fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')


@router.get('/people/student/{identifier}/binding-preview')
def student_binding_preview(identifier:int,userId:int=Query(gt=0),user=Depends(get_current_user)):
    return success(service.preview_binding(user,identifier,userId))


@router.post('/people/student/{identifier}/binding')
def student_binding_repair(identifier:int,body:BindingRepair,user=Depends(get_current_user)):
    return success(service.repair_binding(user,identifier,body.model_dump()))


@router.post('/people/{kind}/{identifier}/contact')
def person_contact(kind:PersonKind,identifier:int,body:SensitivePurpose,user=Depends(get_current_user)):
    return success(service.sensitive_phone(user,kind,identifier,body.reason))


@router.put('/people/{kind}/{identifier}')
def update_person(kind: PersonKind, identifier: int, body: Person, user=Depends(get_current_user)):
    return success(service.save_person(user, kind, identifier, body.model_dump()))


@router.get('/accounts')
def accounts(page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
             keyword: str = Query('', max_length=100), user=Depends(get_current_user)):
    return success(service.list_accounts(user, page, pageSize, keyword))


@router.post('/accounts/{identifier}/actions')
def account_actions(identifier: int, body: AccountChange, user=Depends(get_current_user)):
    return success(service.account_action(user, identifier, body.model_dump()))


@router.get('/roles')
def roles(user=Depends(get_current_user)):
    return success(service.list_roles(user))


@router.post('/roles')
def create_role(body: RoleChange, user=Depends(get_current_user)):
    return success(service.save_role(user, body.model_dump()))


@router.get('/roles/{identifier}/{section}')
def role_detail(identifier:int,section:Literal['members','scopes','history','impact'],page:int=Query(1,ge=1),
                userId:str=Query('',pattern=r'^\d*$'),user=Depends(get_current_user)):
    return success(service.role_detail(user,identifier,section,page,userId or None))


@router.put('/roles/{identifier}')
def update_role(identifier: int, body: RoleChange, user=Depends(get_current_user)):
    return success(service.save_role(user, body.model_dump(), identifier))


@router.post('/roles/{identifier}/members')
def role_members(identifier: int, body: MemberChange, user=Depends(get_current_user)):
    return success(service.role_member(user, identifier, body.model_dump()))


@router.get('/scopes')
def scopes(page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
           issuePage: int = Query(1, ge=1), issueType: Literal['','MISSING','DUPLICATE'] = '',
           scopeType: Literal['','COLLEGE','MAJOR','CLASS'] = '', refId: str = Query('', pattern=r'^\d*$'), reviewOnly: bool = False,
           blockedPage: int = Query(1, ge=1),
           user=Depends(get_current_user)):
    if bool(scopeType)!=bool(refId):
        from app.core.exceptions import AppException
        raise AppException('VALIDATION_ERROR','请同时指定负责类型与负责对象')
    return success(service.list_scopes(user, page, pageSize, issuePage, issueType, scopeType, refId, reviewOnly, blockedPage))


@router.post('/scopes')
def create_scope(body: ScopeChange, user=Depends(get_current_user)):
    return success(service.save_scope(user, body.model_dump()))


@router.get('/scopes/{identifier}/impact')
def scope_impact(identifier:int,user=Depends(get_current_user)):
    return success(service.scope_impact(user,identifier))


@router.put('/scopes/{identifier}')
def update_scope(identifier: int, body: ScopeChange, user=Depends(get_current_user)):
    return success(service.save_scope(user, body.model_dump(), identifier))


@router.post('/scopes/{identifier}/retire')
def retire_scope(identifier: int, body: Change, user=Depends(get_current_user)):
    return success(service.retire_legacy_scope(user,identifier,body.model_dump()))


@router.get('/identity-import/{kind}/template')
def import_template(kind: ImportKind, user=Depends(get_current_user)):
    return spreadsheet(identity.template(user, kind), '师生开户模板.xlsx')


@router.post('/identity-import/{kind}/preview')
async def import_preview(kind: ImportKind, file: UploadFile = File(...), user=Depends(get_current_user)):
    from app.core.permissions import enforce_permission
    enforce_permission(user, identity.import_permission(kind,'manage'))
    content = await read_safe_upload(file)
    return success(identity.preview(user, kind, file.filename or '师生.xlsx', content))


@router.get('/identity-import/jobs/{identifier}')
def import_job(identifier: int, page: int = Query(1, ge=1), user=Depends(get_current_user)):
    return success(identity.get_preview(user, identifier, page))


@router.post('/identity-import/jobs/{identifier}/confirm')
def import_confirm(identifier: int, body: Confirm, user=Depends(get_current_user)):
    return success(identity.enqueue(user, identifier, body.expectedVersion))


@router.get('/identity-import/jobs/{identifier}/receipt')
def import_receipt(identifier: int, user=Depends(get_current_user)):
    return spreadsheet(identity.receipt(user, identifier), '师生开户回执.xlsx')


@router.get('/identity-import/jobs/{identifier}/errors')
def import_errors(identifier:int,user=Depends(get_current_user)):
    return spreadsheet(identity.error_rows(user,identifier),'师生导入错误行.xlsx')


class Brand(Change):
    schoolName: str = Field(min_length=2,max_length=100)
    shortName: str = Field(default='',max_length=100)
    platformName: str = Field(min_length=2,max_length=100)
    subtitle: str = Field(default='',max_length=200)
    contactPhone: str = Field(default='',max_length=50)
    supervisionPhone: str = Field(default='',max_length=50)
    logoFileId: str = Field(default='',pattern=r'^\d*$')


class Alias(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    alias: str = Field(min_length=1,max_length=100)
    code: str = Field(min_length=1,max_length=50)


class StandardReference(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    kind: Literal['area','industry','enterpriseNature','major']
    source: str = Field(default='',max_length=200)
    edition: str = Field(default='',max_length=100)

    @model_validator(mode='after')
    def complete_reference(self):
        if bool(self.source) != bool(self.edition):
            raise ValueError('字典来源和版本须同时填写，未确认时请同时留空')
        return self


class Dictionary(Change):
    announcementCategories: list[str] = Field(max_length=30)
    aliases: list[Alias] = Field(max_length=200)
    standardReferences: list[StandardReference] = Field(default_factory=list,max_length=4)

    @field_validator('standardReferences')
    @classmethod
    def unique_standards(cls,values):
        if len({row.kind for row in values}) != len(values):
            raise ValueError('同一字典的来源版本只能登记一次')
        return values

    @field_validator('announcementCategories')
    @classmethod
    def category_names(cls,values):
        values=[v.strip() for v in values]
        if any(not v or len(v)>50 for v in values) or len(set(values))!=len(values):
            raise ValueError('公告分类须为不重复的1至50字中文业务名称')
        return values


class Faq(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    question: str = Field(min_length=2,max_length=100)
    answer: str = Field(min_length=2,max_length=1000)


class Notification(Change):
    contactPhone: str = Field(default='',max_length=50)
    responsibleUserId: str = Field(default='',pattern=r'^\d*$')
    faq: list[Faq] = Field(default_factory=list,max_length=30)
    reminderText: str = Field(min_length=2,max_length=200)


class DeliveryRecord(Change):
    title: str = Field(min_length=2,max_length=200)
    ownerUserId: str = Field(default='',pattern=r'^\d*$')
    status: Literal['PENDING','REVIEW','VERIFIED'] = 'PENDING'
    source: str = Field(default='',max_length=300)
    notes: str = Field(default='',max_length=5000)
    mappingRules: str = Field(default='',max_length=5000)
    identityMapping: str = Field(default='',max_length=5000)
    exceptionResolution: str = Field(default='',max_length=5000)
    expectedPeople: int = Field(default=0,ge=0)
    actualPeople: int = Field(default=0,ge=0)
    expectedRecords: int = Field(default=0,ge=0)
    actualRecords: int = Field(default=0,ge=0)
    expectedFiles: int = Field(default=0,ge=0)
    actualFiles: int = Field(default=0,ge=0)
    continuationChecked: bool = False
    fileIds: list[str] = Field(default_factory=list,max_length=20)

    @field_validator('fileIds')
    @classmethod
    def file_identifiers(cls,value):
        if any(not v.isascii() or not v.isdigit() or len(v)>19 for v in value):raise ValueError('附件编号不合法')
        return list(dict.fromkeys(value))


@router.get('/overview')
def overview(user=Depends(get_current_user)):
    return success(configurations.overview(user))


@router.get('/config/{category}')
def configuration(category: Literal['brand','dictionary','notification'],user=Depends(get_current_user)):
    return success(configurations.read_config(user,category))


@router.put('/config/brand')
def brand_config(body:Brand,user=Depends(get_current_user)):
    return success(configurations.save_config(user,'brand',body.model_dump()))


@router.put('/config/dictionary')
def dictionary_config(body:Dictionary,user=Depends(get_current_user)):
    values=body.model_dump()
    if 'standardReferences' not in body.model_fields_set: values.pop('standardReferences')
    return success(configurations.save_config(user,'dictionary',values))


@router.put('/config/notification')
def notification_config(body:Notification,user=Depends(get_current_user)):
    return success(configurations.save_config(user,'notification',body.model_dump()))


@router.get('/tasks')
def tasks(page:int=Query(1,ge=1),pageSize:int=Query(30,ge=1,le=100),keyword:str=Query('',max_length=100),
          status:Literal['','UPLOADED','VALIDATING','VALIDATED','QUEUED','CONFIRMING','IMPORTED','FAILED','CANCELLED','SUCCESS']='',user=Depends(get_current_user)):
    return success(configurations.list_tasks(user,page,pageSize,keyword,status))


@router.get('/tasks/{identifier}/result')
def task_result(identifier:int,user=Depends(get_current_user)):
    file_id=directory_exports.result_file(user,identifier)
    if file_id:
        from app.api.v1.standalone_files import response_file
        return response_file(file_id,user,False)
    return spreadsheet(service.export_result(user,identifier),f'任务{identifier}导出结果.xlsx')


@router.get('/audit')
def audit_records(page:int=Query(1,ge=1),pageSize:int=Query(30,ge=1,le=100),keyword:str=Query('',max_length=100),
                  startAt:datetime|None=None,endAt:datetime|None=None,user=Depends(get_current_user)):
    return success(configurations.list_audit(user,page,pageSize,keyword,start_at=startAt,end_at=endAt))


@router.get('/audit/export')
def audit_export(keyword:str=Query('',max_length=100),startAt:datetime|None=None,endAt:datetime|None=None,user=Depends(get_current_user)):
    return spreadsheet(configurations.list_audit(user,keyword=keyword,export=True,start_at=startAt,end_at=endAt),'操作审计.xlsx')


@router.get('/integrations')
def integrations(user=Depends(get_current_user)):
    return success(configurations.external_status(user))


@router.get('/runtime')
def runtime(user=Depends(get_current_user)):
    return success(configurations.runtime_status(user))


RecordKind=Literal['MIGRATION','DOCUMENT','BACKUP','RESTORE']


@router.get('/records/{kind}')
def records(kind:RecordKind,page:int=Query(1,ge=1),pageSize:int=Query(30,ge=1,le=100),keyword:str=Query('',max_length=100),user=Depends(get_current_user)):
    return success(configurations.delivery_records(user,kind,page,pageSize,keyword))


@router.post('/records/{kind}')
def create_record(kind:RecordKind,body:DeliveryRecord,user=Depends(get_current_user)):
    return success(configurations.save_record(user,kind,body.model_dump()))


@router.put('/records/{kind}/{identifier}')
def update_record(kind:RecordKind,identifier:int,body:DeliveryRecord,user=Depends(get_current_user)):
    return success(configurations.save_record(user,kind,body.model_dump(),identifier))


class LeaveNode(BaseModel):
    model_config=ConfigDict(extra='forbid')
    type: Literal['GUIDE','COLLEGE','SCHOOL']
    roleCode: str = Field(min_length=1,max_length=50)
    userId: str = Field(default='',pattern=r'^\d*$')


class LeavePreview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    nodes: list[LeaveNode] = Field(min_length=1,max_length=3)


class LeavePublish(Change):
    nodes: list[LeaveNode] = Field(min_length=1,max_length=3)


from app.services import system_leave_policy as leave_policy


@router.get('/leave-policies/options')
def leave_policy_options(user=Depends(get_current_user)):
    return success(leave_policy.available(user))


@router.get('/leave-policies/{batch_id}')
def read_leave_policy(batch_id:int,user=Depends(get_current_user)):
    return success(leave_policy.read(user,batch_id))


@router.post('/leave-policies/{batch_id}/preview')
def preview_leave_policy(batch_id:int,body:LeavePreview,user=Depends(get_current_user)):
    return success(leave_policy.preview(user,batch_id,[n.model_dump() for n in body.nodes]))


@router.post('/leave-policies/{batch_id}/publish')
def publish_leave_policy(batch_id:int,body:LeavePublish,user=Depends(get_current_user)):
    return success(leave_policy.publish(user,batch_id,body.model_dump()))


class Handoff(Change):
    batchId: str = Field(pattern=r'^\d+$')
    userId: str = Field(pattern=r'^\d+$')
    roleCode: str = Field(min_length=1,max_length=50)


@router.get('/handoffs')
def handoffs(batchId:int,userId:int,page:int=Query(1,ge=1),pageSize:int=Query(30,ge=1,le=100),
             taskId:str=Query('',pattern=r'^\d*$'),user=Depends(get_current_user)):
    return success(leave_policy.handoff_list(user,batchId,userId,page,pageSize,taskId))


@router.get('/handoff-options')
def handoff_options(user=Depends(get_current_user)):
    return success(leave_policy.available(user,'system.scope.view'))


@router.post('/handoffs/{task_id}')
def transfer_task(task_id:int,body:Handoff,user=Depends(get_current_user)):
    return success(leave_policy.handoff(user,task_id,body.model_dump()))
