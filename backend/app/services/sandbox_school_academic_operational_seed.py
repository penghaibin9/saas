"""007 现有学期上的教务操作性补充，不改变课程/注册规模基线。"""
from __future__ import annotations
from datetime import datetime,timedelta
from sqlalchemy import select
REFERENCE_NOW=datetime(2026,8,28,10,30); MARKER="007-ACADEMIC-OP-2026"
def _one(db,m,t,**w):
 q=[m.tenant_id==t]
 if hasattr(m,"is_deleted"):q.append(m.is_deleted.is_(False))
 q += [getattr(m,k)==v for k,v in w.items()]
 return db.scalars(select(m).where(*q)).first()
def _put(db,m,t,key,v):
 r=_one(db,m,t,**key)
 if r is None:r=m(tenant_id=t,**key,**v);db.add(r);db.flush()
 return r
def seed_academic_operational_coverage(db,tenant_id:int)->dict:
 from app.models import AaCourse,AaRegistration,AaRegistrationBatch,AaTerm,AaTimeSlot,StudentProfile,User
 from app.models.file import FileObject
 from app.models.academic_affairs import AaClassTimeBand,AaCourseMaterial,AaRegistrationDeferral,AaScheduleRule,AaTeacherAvailability
 term=db.scalars(select(AaTerm).where(AaTerm.tenant_id==tenant_id,AaTerm.is_current.is_(True),AaTerm.is_deleted.is_(False))).first()
 slot=db.scalars(select(AaTimeSlot).where(AaTimeSlot.tenant_id==tenant_id,AaTimeSlot.is_deleted.is_(False)).order_by(AaTimeSlot.id)).first()
 course=db.scalars(select(AaCourse).where(AaCourse.tenant_id==tenant_id,AaCourse.is_deleted.is_(False)).order_by(AaCourse.id)).first()
 batch=db.scalars(select(AaRegistrationBatch).where(AaRegistrationBatch.tenant_id==tenant_id,AaRegistrationBatch.term_id==term.id,AaRegistrationBatch.is_deleted.is_(False)).order_by(AaRegistrationBatch.id)).first() if term else None
 registration=db.scalars(select(AaRegistration).where(AaRegistration.tenant_id==tenant_id,AaRegistration.batch_id==batch.id,AaRegistration.is_deleted.is_(False)).order_by(AaRegistration.id)).first() if batch else None
 student=db.get(StudentProfile,registration.student_id) if registration else None
 admin=_one(db,User,tenant_id,login_name="admin2");teacher=_one(db,User,tenant_id,login_name="teacher2");file=_one(db,FileObject,tenant_id,file_key="007-GOV-2026/leave-approval-evidence.md")
 if not all((term,slot,course,batch,registration,student,admin,teacher,file)):raise RuntimeError("academic seed prerequisites unavailable")
 _put(db,AaClassTimeBand,tenant_id,{"slot_id":slot.id,"campus_code":"MAIN"},{"band_name":"秋季标准作息","effective_start":term.start_date,"effective_end":term.end_date,"start_time":slot.start_time,"end_time":slot.end_time,"status":"ENABLED"})
 _put(db,AaCourseMaterial,tenant_id,{"course_id":course.id,"material_type":"SYLLABUS","title":f"{MARKER}-课程教学大纲"},{"file_id":str(file.id),"file_name":file.file_name,"remark":"与当前培养方案和教学任务对应的课程大纲材料。","uploader":teacher.real_name,"status":"ACTIVE"})
 _put(db,AaRegistrationDeferral,tenant_id,{"batch_id":batch.id,"student_id":student.id},{"reason":"家庭突发事务影响报到材料递交，申请延后补交。","requested_until":REFERENCE_NOW+timedelta(days=3),"status":"APPROVED","review_note":"不影响学籍注册，补交材料后完成核验。","reviewed_at":REFERENCE_NOW-timedelta(days=1),"reviewed_by":admin.id})
 _put(db,AaScheduleRule,tenant_id,{"term_id":term.id,"batch_id":None,"rule_key":"maxDailySlots"},{"rule_value_json":"{\"value\":6}","remark":"当前学期教师与学生单日排课上限。","status":"ENABLED"})
 _put(db,AaTeacherAvailability,tenant_id,{"teacher_key":str(teacher.id),"term_id":term.id,"weekday":5,"slot_no":slot.slot_no},{"teacher_name":teacher.real_name,"reason":"企业巡访与学生实习指导固定时段。","review_reason":"与实习导师职责冲突，学院已采纳。","status":"ADOPTED"})
 db.commit();return validate_academic_operational_coverage(db,tenant_id)
def validate_academic_operational_coverage(db,tenant_id):
 from app.models.academic_affairs import AaCourseMaterial,AaScheduleRule
 r={"material":bool(_one(db,AaCourseMaterial,tenant_id,title=f"{MARKER}-课程教学大纲")),"scheduleRule":bool(_one(db,AaScheduleRule,tenant_id,rule_key="maxDailySlots"))};r["passed"]=all(r.values())
 if not r["passed"]:raise RuntimeError(f"academic coverage invalid: {r}")
 return r
