"""Explicit school/batch attendance schedule; no implicit all-school scan or auto-start."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import tempfile
import time
from datetime import date, timedelta
from sqlalchemy import select
from app.core.context import get_tenant, set_tenant
from app.core.timeutil import local_now
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import (Tenant, InternshipBatch, InternshipRecord, InternshipLeave, RiskRecord, User,
    StudentProfile, InternshipCheckin, InternshipCheckinExemption, InternshipMakeup)
from app.modules.internship.services import internship_leave_service
from app.services.message_event_outbox_service import emit_message_event, process_pending_outbox
from app.modules.internship.services.internship_student_checkin_service import calendar_status
from app.audit_worker import heartbeat_healthy, write_heartbeat


def _active_advisors(db, tenant_id, ids):
    from app.models import Role, UserRole
    from app.services.system_authorization import role_permissions
    from app.core.permissions import _matches
    from app.core.timeutil import utc_now_naive
    roles=db.execute(select(UserRole.user_id,Role).join(Role,Role.id==UserRole.role_id).where(
        UserRole.tenant_id==tenant_id,UserRole.user_id.in_(ids),UserRole.status=='ACTIVE',
        UserRole.is_deleted.is_(False),Role.tenant_id==tenant_id,Role.status=='ACTIVE',Role.is_deleted.is_(False))).all()
    unique_roles={role.id:role for uid,role in roles}
    allowed={role.id for role in unique_roles.values() if any(_matches(code,'internship.student.view') for code in role_permissions(db,role))}
    permitted={uid for uid,role in roles if role.id in allowed}
    return set(db.scalars(select(User.id).where(User.id.in_(permitted),User.tenant_id==tenant_id,
        User.status=='ACTIVE',User.is_deleted.is_(False),
        (User.expires_at.is_(None)) | (User.expires_at>utc_now_naive()))))


def _checkin_notices(db, tenant_id, batch_id):
    batch = db.scalar(select(InternshipBatch).where(InternshipBatch.id==batch_id,
        InternshipBatch.tenant_id==tenant_id).with_for_update())
    rule = (batch.rules_config or {}).get('checkin') or {}
    if not rule.get('requireDaily', True): return []
    now=local_now();today=now.date();first=today-timedelta(days=3)
    reminder=rule.get('reminderTime')
    from app.modules.internship.schemas.internship import CheckinRule
    try: CheckinRule(reminderTime=reminder)
    except ValueError: raise AppException('VALIDATION_ERROR','当天未签到提醒时间必须为有效的小时和分钟') from None
    events=[];last_id=0
    while True:
        pairs=db.execute(select(InternshipRecord,StudentProfile).join(StudentProfile,
            StudentProfile.id==InternshipRecord.student_id).where(InternshipRecord.tenant_id==tenant_id,
            InternshipRecord.batch_id==batch_id,InternshipRecord.is_deleted.is_(False),
            InternshipRecord.status.in_(('ONBOARD','ASSESSING')),InternshipRecord.id>last_id,
            StudentProfile.tenant_id==tenant_id,StudentProfile.is_deleted.is_(False))
            .order_by(InternshipRecord.id).limit(200)).all()
        if not pairs: break
        last_id=pairs[-1][0].id;ids=[r.id for r,s in pairs];students={r.id:r.student_id for r,s in pairs}
        signed={};makeups={};exempt={};leaves={}
        for model in (InternshipCheckin,InternshipMakeup):
            query=select(model).where(model.tenant_id==tenant_id,model.internship_id.in_(ids),
                model.checkin_date>=first.isoformat(),model.checkin_date<=today.isoformat(),model.is_deleted.is_(False))
            query=query.where(model.result!='LEAVE') if model is InternshipCheckin else query.where(model.status=='APPROVED')
            for row in db.scalars(query):
                (signed if model is InternshipCheckin else makeups).setdefault(row.internship_id,set()).add(row.checkin_date)
        for model,covered in ((InternshipCheckinExemption,exempt),(InternshipLeave,leaves)):
            query=select(model).where(model.tenant_id==tenant_id,model.internship_id.in_(ids),
                model.start_date<=today.isoformat(),model.end_date>=first.isoformat(),model.is_deleted.is_(False),
                model.status.in_(('APPROVED',) if model is InternshipCheckinExemption else ('APPROVED','OVERDUE','RETURNED')))
            for row in db.scalars(query):
                if row.student_id != students[row.internship_id]: continue
                if model is InternshipLeave: left,right=internship_leave_service.effective_period(row)
                else: left,right=date.fromisoformat(row.start_date),date.fromisoformat(row.end_date)
                if left is None or right is None: continue
                for offset in range(4):
                    day=first+timedelta(days=offset)
                    if left<=day<=right: covered.setdefault(row.internship_id,set()).add(day.isoformat())
        advisor_ids={r.advisor_user_id for r,s in pairs if r.advisor_user_id}
        advisors=_active_advisors(db,tenant_id,advisor_ids)
        for record,student in pairs:
            start=record.intern_start_date or batch.start_date;end=record.intern_end_date or batch.end_date
            if not start or not end: continue
            start,end=start.date(),end.date()
            statuses={}
            for offset in range(4):
                day=first+timedelta(days=offset);key=day.isoformat()
                statuses[day]=calendar_status(day,start,end,today,signed=key in signed.get(record.id,set()),
                    makeup=key in makeups.get(record.id,set()),exempt=key in exempt.get(record.id,set()),leave=key in leaves.get(record.id,set()))
            if reminder and now.strftime('%H:%M')>=reminder and statuses[today]=='PENDING':
                event=emit_message_event(db,event_code='INTERNSHIP.CHECKIN_REMIND',source_module='internship',
                    source_biz_type='internship_record',source_biz_id=record.id,recipient_refs=[{'studentId':student.id}],
                    title='今日实习尚未签到，请核对',content=f'{batch.batch_name}：{today}尚未记录签到，请从实习工作台核对；如已请假或免签，请核对审批结果。',
                    dedup_key=f'ATTENDANCE.UNSIGNED:{record.id}:{today}')
                events.append(event.id)
            if all(statuses[first+timedelta(days=i)]=='ABSENT' for i in range(3)) and record.advisor_user_id in advisors:
                event=emit_message_event(db,event_code='INTERNSHIP.CHECKIN_STREAK',source_module='internship',
                    source_biz_type='internship_record',source_biz_id=record.id,recipient_refs=[{'userId':record.advisor_user_id}],
                    title='学生连续三天未签到，请核实',
                    content=f'{batch.batch_name}：{student.real_name}（学号{student.student_no}）在{first}至{today-timedelta(days=1)}连续三天没有签到、已批准请假或免签记录，请联系学生核实。',
                    dedup_key=f'ATTENDANCE.UNSIGNED3:{record.id}:{today}:{record.advisor_user_id}')
                events.append(event.id)
    return events


def run_cycle(tenant_id: int, batch_id: int) -> dict:
    with get_sessionmaker()() as db:
        school = db.get(Tenant, int(tenant_id)); batch = db.get(InternshipBatch, int(batch_id))
        if (not school or school.is_deleted or school.status != 'ACTIVE' or not batch
                or batch.is_deleted or batch.tenant_id != school.id or batch.status != 'RUNNING'):
            raise AppException('NO_PERMISSION', '调度目标必须是有效学校的进行中实习批次')
    previous = get_tenant()
    try:
        set_tenant(tenant_id)
        result={'tenantId':str(tenant_id), 'batchId':str(batch_id),
            **internship_leave_service.refresh_overdue(reference_date=local_now().date(), system=True, batch_id=batch_id)}
        events=[];unassigned=[]
        with get_sessionmaker()() as db:
            events.extend(_checkin_notices(db,tenant_id,batch_id))
            rows=db.execute(select(RiskRecord,InternshipRecord).join(InternshipRecord,
                InternshipRecord.id==RiskRecord.internship_id).join(InternshipLeave,
                InternshipLeave.id==RiskRecord.source_id).where(
                    RiskRecord.tenant_id==tenant_id,RiskRecord.source_type=='LEAVE',
                    RiskRecord.risk_code=='INT-R06',RiskRecord.status.in_(('PENDING_HANDLE','PROCESSING')),
                    RiskRecord.is_deleted.is_(False),InternshipRecord.tenant_id==tenant_id,
                    InternshipRecord.batch_id==batch_id,InternshipRecord.is_deleted.is_(False),
                    InternshipLeave.tenant_id==tenant_id,InternshipLeave.internship_id==InternshipRecord.id,
                    InternshipLeave.is_deleted.is_(False))).all()
            advisors=_active_advisors(db,tenant_id,{record.advisor_user_id for risk,record in rows if record.advisor_user_id})
            for risk,record in rows:
                if record.advisor_user_id not in advisors:
                    unassigned.append(str(risk.id));continue
                event=emit_message_event(db,event_code='INTERNSHIP.RISK_CREATED',source_module='internship',
                    source_biz_type='risk_record',source_biz_id=risk.id,
                    recipient_refs=[{'userId':record.advisor_user_id}],title='实习请假超期未销假，请及时核对',
                    content=f'请跟进本批次实习记录{record.id}的请假超期情况，核实学生返岗后按原单办结。',
                    dedup_key=f'ATTENDANCE.OVERDUE:{risk.id}:user:{record.advisor_user_id}')
                events.append(event.id)
            db.commit()
        delivered=process_pending_outbox(limit=len(events),worker_id='internship-attendance',outbox_ids=events) if events else 0
        return {**result,'notificationsProcessed':delivered,'unassignedRiskIds':unassigned}
    finally:
        set_tenant(previous)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Scoped internship attendance scheduling')
    parser.add_argument('--tenant-id',type=int,required=True)
    parser.add_argument('--batch-id',type=int,required=True)
    parser.add_argument('--interval',type=int,default=60)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--once',action='store_true')
    mode.add_argument('--healthcheck',action='store_true')
    parser.add_argument('--heartbeat-file',type=Path)
    args=parser.parse_args(argv)
    if args.tenant_id <= 0 or args.batch_id <= 0 or args.interval < 1:
        parser.error('目标编号及调度间隔须为正数')
    heartbeat=args.heartbeat_file or Path(tempfile.gettempdir()) / f'internship-attendance-{args.tenant_id}-{args.batch_id}-heartbeat.json'
    if args.healthcheck:
        return 0 if heartbeat_healthy(heartbeat,max(30,args.interval*3)) else 1
    while True:
        try:
            result=run_cycle(args.tenant_id,args.batch_id)
            write_heartbeat(heartbeat,True)
        except Exception as exc:
            logging.error('考勤调度未完成：%s',type(exc).__name__)
            try: write_heartbeat(heartbeat,False)
            except OSError: logging.error('考勤调度心跳无法写入')
            return 1
        print(json.dumps(result),flush=True)
        if args.once:return 0
        time.sleep(args.interval)


if __name__=='__main__':
    raise SystemExit(main())
