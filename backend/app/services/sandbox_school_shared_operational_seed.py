"""007 学校可安全复现的门户、数据中心、客户成功与计量演示事实。"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from sqlalchemy import func, select

REFERENCE_NOW=datetime(2026,8,28,10,30); MARKER="007-SHARED-OP-2026"
def _one(db,m,t,**w):
 q=[m.tenant_id==t]
 if hasattr(m,"is_deleted"):q.append(m.is_deleted.is_(False))
 q += [getattr(m,k)==v for k,v in w.items()]
 return db.scalars(select(m).where(*q)).first()
def _put(db,m,t,key,vals):
 r=_one(db,m,t,**key)
 if r is None:r=m(tenant_id=t,**key,**vals);db.add(r);db.flush()
 return r
def seed_shared_operational_coverage(db, tenant_id:int)->dict:
 from app.core.field_crypto import encrypt_field, hash_sensitive
 from app.models import StudentAccountLink, StudentProfile, User
 from app.models.customer_success import RenewalTask, SupportTicket, TrainingRecord
 from app.models.data_center import DataCenterReport, DataCenterReportVersion
 from app.models.feedback import Feedback
 from app.models.employment import EmpDestinationSubmission, EmpJob, EmpStudent
 from app.models.employment_recommendation import EmpRecommendation
 from app.models.file import FileObject
 from app.models.platform import PlatformConfig, PlatformNotice
 from app.models.portal import TenantPortalConfig
 from app.models.student import StudentImportBatch, StudentStageEvent
 from app.models.student_parent import StudentParentLink
 from app.models.system_governance import SystemJsonDoc
 from app.models.tenant_metering import TenantFairUseLimit, TenantFairUseViolation, TenantUsageSnapshot
 admin=_one(db,User,tenant_id,login_name="admin2"); student=_one(db,User,tenant_id,login_name="student2")
 link=db.scalars(select(StudentAccountLink).where(StudentAccountLink.tenant_id==tenant_id,StudentAccountLink.user_id==student.id,StudentAccountLink.link_status=="ACTIVE",StudentAccountLink.is_deleted.is_(False))).first() if student else None
 profile=db.get(StudentProfile,link.student_id) if link else None
 evidence=_one(db,FileObject,tenant_id,file_key="007-GOV-2026/leave-approval-evidence.md")
 if not all((admin,student,profile,evidence)):raise RuntimeError("shared seed requires 007 public users/profile/evidence")
 _put(db,PlatformConfig,tenant_id,{"config_type":"DEMO","config_key":"SCHOOL_DASHBOARD"},{"config_json":{"studentCount":20000,"dataSource":"007 business facts","refresh":"real-time"},"enabled":True,"status":"ACTIVE","remark":"007 演示学校驾驶舱配置。"})
 _put(db,PlatformNotice,tenant_id,{"title":f"{MARKER}-秋季实习服务提醒"},{"notice_type":"ANNOUNCEMENT","content":"岗位实习、请假审批和风险处置已开放演示，请按角色查看待办。","status":"PUBLISHED","publish_at":REFERENCE_NOW-timedelta(days=1),"remark":"仅面向 007 租户的演示公告。"})
 # Portal config must keep the same object shape consumed by student_portal_service.
 # Lists/strings here make the merge fail closed and incorrectly send the demo
 # student to /not-enabled even though the tenant has explicitly enabled it.
 portal_config={
  "enabled":True,
  "portalName":"跃科职业技术学院学生服务门户",
  "portalUrl":"/portal/",
  "requiredPackage":"professional",
  "modules":{
   "dashboard":True,"profile":True,"orientation":True,"campusService":True,
   "academic":True,"internship":True,"graduation":True,"employment":True,
   "messages":True,
  },
  "features":{
   "upload":True,"export":True,"proofDownload":True,
   "profileCorrection":True,"messageReceipt":True,"materialCenter":True,
   "workItems":True,"aiAssistant":False,
  },
  "loginAccountTips":{"enabled":False,"accounts":[]},
 }
 portal_row=_put(db,TenantPortalConfig,tenant_id,{}, {"config_json":portal_config})
 # _put is insert-only for immutable demo facts; this mutable configuration is
 # deliberately reconciled on every run so an older malformed seed is repaired.
 portal_row.config_json=portal_config
 _put(db,SystemJsonDoc,tenant_id,{"doc_key":"MODULE_FEATURES"},{"payload":{"source":"t_tenant_capability_setting","readOnlyFallback":False,"enabledModules":["academicAffairs","studentAffairs","internship","graduationDesign"]},"remark":"007 启用能力的兼容读取文档。"})
 students=int(db.scalar(select(func.count()).select_from(StudentProfile).where(StudentProfile.tenant_id==tenant_id,StudentProfile.is_deleted.is_(False))) or 0)
 users=int(db.scalar(select(func.count()).select_from(User).where(User.tenant_id==tenant_id,User.is_deleted.is_(False))) or 0)
 _put(db,TenantUsageSnapshot,tenant_id,{"snapshot_date":date(2026,8,28)},{"audit_event_count":78,"file_upload_bytes":386,"storage_total_bytes":386,"student_count":students,"user_count":users})
 _put(db,TenantFairUseLimit,tenant_id,{"resource_code":"FILE_UPLOAD_BYTES_PER_DAY"},{"daily_limit":1073741824,"status":"ACTIVE"})
 _put(db,TenantFairUseViolation,tenant_id,{"resource_code":"FILE_UPLOAD_BYTES_PER_DAY","violation_date":date(2026,8,20)},{"actual_value":1100000000,"limit_value":1073741824,"action_taken":"LOGGED","detected_at":REFERENCE_NOW-timedelta(days=8)})
 _put(db,SupportTicket,tenant_id,{"title":f"{MARKER}-教师工作台待办核验"},{"description":"教师角色已登录验证，可正常读取实习请假和学生事务待办。","severity":"P3","status":"RESOLVED","reporter_name":admin.real_name,"assignee_user_id":admin.id,"assignee_name":admin.real_name,"resolved_at":REFERENCE_NOW-timedelta(days=1),"resolution_note":"本地接口及角色权限验证通过。"})
 _put(db,TrainingRecord,tenant_id,{"topic":"管理员全生命周期演示培训"},{"trainer_name":admin.real_name,"scheduled_at":REFERENCE_NOW-timedelta(days=2),"status":"COMPLETED","attendee_count":12,"completed_at":REFERENCE_NOW-timedelta(days=2),"note":"覆盖学工、教务、实习、毕业设计与数据中心。"})
 _put(db,RenewalTask,tenant_id,{"due_at":REFERENCE_NOW+timedelta(days=120)},{"status":"CONTACTED","owner_user_id":admin.id,"owner_name":admin.real_name,"note":"007 正式演示租户续费意向已登记。","last_contacted_at":REFERENCE_NOW-timedelta(days=1),"closed_at":None})
 report=_put(db,DataCenterReport,tenant_id,{"report_no":f"{MARKER}-LIFECYCLE"},{"name":"学生全生命周期演示运行报告","category":"STUDENT_AFFAIRS","cycle":"MONTHLY","scope_name":"全校 20,000 名学生","description":"从真实业务记录汇总学工、教务、实习和毕业设计状态。","caliber_code":"REGISTERED","query_json":{"sources":["t_student_profile","t_internship_record","t_gd_student"]},"layout_json":{"cards":["studentCount","internshipRisk","graduationProgress"]},"status":"PUBLISHED","owner_id":str(admin.id),"owner_name":admin.real_name,"published_version_no":1,"published_at":REFERENCE_NOW-timedelta(days=1),"withdrawn_at":None,"void_reason":None,"voided_at":None,"voided_by_name":None})
 _put(db,DataCenterReportVersion,tenant_id,{"report_id":report.id,"version_no":1},{"snapshot_json":{"studentCount":students,"internshipBatch":"INT-2024-2026FALL"},"metrics_json":[{"key":"studentCount","value":students}],"trend_json":{"period":"2026-08"},"as_of":REFERENCE_NOW,"caliber_code":"REGISTERED","scope_json":{"tenantId":str(tenant_id)},"source_json":["t_student_profile","t_internship_record"],"quality_flags_json":[],"published_by_id":str(admin.id),"published_by_name":admin.real_name,"published_at":REFERENCE_NOW-timedelta(days=1)})
 _put(db,Feedback,tenant_id,{"user_key":str(student.id),"title":"实习请假材料查看建议"},{"user_type":"STUDENT","category":"建议","content":"希望在实习请假详情页同时展示审批进度和已提交材料。","contact":None,"status":"CLOSED","reply":"已在 007 演示路线中加入审批时间线与附件入口。","handled_by":admin.id})
 # 就业去向的申请人必须是该就业学生对应的真实校园账号，不能用管理员替代学生提交。
 # 只选存在有效 StudentAccountLink 的就业台账，保证 student / account / employment 三方一致。
 emp_link=db.execute(select(EmpStudent,StudentAccountLink).join(StudentAccountLink,StudentAccountLink.student_id==EmpStudent.student_id).where(EmpStudent.tenant_id==tenant_id,EmpStudent.is_deleted.is_(False),StudentAccountLink.tenant_id==tenant_id,StudentAccountLink.is_deleted.is_(False),StudentAccountLink.link_status=="ACTIVE").order_by(EmpStudent.id)).first()
 emp=emp_link[0] if emp_link else None
 emp_applicant_id=emp_link[1].user_id if emp_link else None
 job=db.scalars(select(EmpJob).where(EmpJob.tenant_id==tenant_id,EmpJob.is_deleted.is_(False)).order_by(EmpJob.id)).first()
 if emp and emp_applicant_id and job:
  legacy_submission=_one(db,EmpDestinationSubmission,tenant_id,student_id=emp.student_id,applicant_id=admin.id,destination_type="SIGNED")
  if legacy_submission and legacy_submission.applicant_id != emp_applicant_id:
   legacy_submission.applicant_id=emp_applicant_id
   legacy_submission.remark="学生本人在线提交就业去向，材料经就业老师复核。"
  _put(db,EmpDestinationSubmission,tenant_id,{"student_id":emp.student_id,"applicant_id":emp_applicant_id,"destination_type":"SIGNED"},{"emp_student_id":emp.id,"company_name":emp.company_name,"job_title":emp.job_title,"city":"上海","contact":"就业指导中心已核验","remark":"学生本人在线提交就业去向，材料经就业老师复核。","status":"APPROVED","return_reason":None,"workflow_instance_id":None,"current_task_id":None,"decision_version":1})
  _put(db,EmpRecommendation,tenant_id,{"emp_student_id":emp.id,"job_id":job.id,"reason":"专业课程与岗位技能要求匹配"},{"student_profile_id":emp.student_id,"teacher_user_id":admin.id,"teacher_name":admin.real_name,"company_name_snapshot":job.company_name,"job_title_snapshot":job.title,"note":"就业教师基于实习表现给出推荐。","status":"RECOMMENDED","outcome":"PENDING","outcome_note":None,"recommended_at":REFERENCE_NOW-timedelta(days=3)})
 _put(db,StudentImportBatch,tenant_id,{"batch_no":f"{MARKER}-STUDENT-IMPORT"},{"file_id":evidence.id,"total_rows":20,"success_rows":20,"error_rows":0,"status":"SUCCESS","remark":"标准演示学校历史学生主档导入批次，复核已通过。"})
 if _one(db,StudentStageEvent,tenant_id,student_id=profile.id,to_stage=profile.current_stage,source_module="sandbox") is None:
  db.add(StudentStageEvent(tenant_id=tenant_id,student_id=profile.id,from_stage="ENROLLED",to_stage=profile.current_stage,reason="007 演示学生生命周期主档已校验。",source_module="sandbox",occurred_at=REFERENCE_NOW-timedelta(days=30),created_by=admin.id))
 phone="13900000007";ph=hash_sensitive(phone,"phone")
 _put(db,StudentParentLink,tenant_id,{"student_id":profile.id,"guardian_phone_hash":ph,"link_status":"ACTIVE"},{"student_no":profile.student_no,"guardian_name":"演示学生家长","relation":"PARENT","guardian_phone_encrypted":encrypt_field(phone),"visible_scopes":["ACADEMIC_GRADE","CAMPUS_ALERT","CAREER_PROGRESS"]})
 db.commit();return validate_shared_operational_coverage(db,tenant_id)
def validate_shared_operational_coverage(db,tenant_id):
 from app.models.data_center import DataCenterReport
 from app.models.portal import TenantPortalConfig
 from app.models.tenant_metering import TenantUsageSnapshot
 r={"portal":bool(_one(db,TenantPortalConfig,tenant_id)),"usage":bool(_one(db,TenantUsageSnapshot,tenant_id,snapshot_date=date(2026,8,28))),"report":bool(_one(db,DataCenterReport,tenant_id,report_no=f"{MARKER}-LIFECYCLE"))};r["passed"]=all(r.values())
 if not r["passed"]:raise RuntimeError(f"shared coverage invalid: {r}")
 return r
