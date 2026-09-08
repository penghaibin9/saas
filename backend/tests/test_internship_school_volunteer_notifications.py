"""School results: durable delivery, canonical account recipients and company privacy."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.context import set_tenant
from app.db.session import get_sessionmaker
from app.models import User, StudentAccountLink, InternshipRecord, MessageEventOutbox, UnifiedMessage
from app.models.internship_enterprise_portal import InternshipEnterpriseMember, InternshipEnterpriseAccessGrant
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from app.modules.internship.services import internship_school_volunteer_service as svc
from app.modules.internship.services.internship_volunteer_notification_service import emit_school_result_in_tx
from app.services import message_event_outbox_service as outbox
from tests.test_internship_school_volunteer_actions import ready, TID, ADMIN


def recipients(ids):
    now=datetime.utcnow()
    with get_sessionmaker()() as db:
        record=db.get(InternshipRecord,ids['record'])
        users=[User(tenant_id=TID,login_name=uuid4().hex,real_name='虚构消息接收人',
            password_hash='unused-test-account',user_type=kind,status='ACTIVE') for kind in ['STUDENT','ENTERPRISE','ENTERPRISE']]
        db.add_all(users);db.flush()
        db.add(StudentAccountLink(tenant_id=TID,student_id=record.student_id,user_id=users[0].id,link_status='ACTIVE'))
        for index,user in enumerate(users[1:]):
            member=InternshipEnterpriseMember(tenant_id=TID,company_id=ids['company'],user_id=user.id,member_role='HR',status='ACTIVE')
            db.add(member);db.flush()
            db.add(InternshipEnterpriseAccessGrant(tenant_id=TID,member_id=member.id,company_id=ids['company'],
                campaign_id=ids['campaign'],batch_id=ids['batch'],grant_type='RECRUITMENT',status='ACTIVE',
                valid_from=now-timedelta(days=2),valid_until=now+timedelta(days=1) if not index else now-timedelta(days=1)))
        db.commit();return [user.id for user in users]


@pytest.mark.parametrize('action',['confirm','return'])
def test_school_result_outbox_delivery_and_retry_are_scoped_and_idempotent(db_mode,monkeypatch,action):
    ids=ready();student,enterprise,expired=recipients(ids)
    set_tenant({'tenantId':str(TID)})
    drain=outbox.try_process_pending_outbox
    monkeypatch.setattr(outbox,'try_process_pending_outbox',lambda **kwargs:None)
    try:
        args=dict(campaign_id=ids['campaign'],group_id=ids['0'],user=ADMIN,
                  expected_group_version=0,expected_record_version=0)
        if action=='confirm':
            svc.confirm_group(**args,application_id=ids['app'],expected_application_version=0)
        else:
            svc.return_group(**args,reason='学生私密补正说明：补充本人实训经历')
        with get_sessionmaker()() as db:
            events=list(db.scalars(select(MessageEventOutbox).where(MessageEventOutbox.tenant_id==TID,
                MessageEventOutbox.source_biz_type=='INTERNSHIP_VOLUNTEER_GROUP',MessageEventOutbox.source_biz_id==ids['0'])))
            assert len(events)==3 and all(event.status=='PENDING' for event in events)
            event_ids=[event.id for event in events]
            assert db.get(InternshipVolunteerGroup,ids['0']).status==('APPROVED' if action=='confirm' else 'NEEDS_REVISION')
            repeated=emit_school_result_in_tx(db,group=db.get(InternshipVolunteerGroup,ids['0']),
                record=db.get(InternshipRecord,ids['record']),selected_application_id=ids['app'] if action=='confirm' else None)
            assert sorted(repeated)==sorted(event_ids);db.commit()
        drain(outbox_ids=event_ids);drain(outbox_ids=event_ids)
        with get_sessionmaker()() as db:
            assert all(db.get(MessageEventOutbox,event_id).status=='SUCCEEDED' for event_id in event_ids)
            messages=list(db.scalars(select(UnifiedMessage).where(UnifiedMessage.tenant_id==TID,
                UnifiedMessage.receiver_user_id.in_([student,enterprise,expired]))))
            assert len(messages)==3
            own=[message for message in messages if message.receiver_user_id==student]
            company=[message for message in messages if message.receiver_user_id==enterprise]
            assert len(own)==1 and own[0].receiver_type=='STUDENT'
            assert own[0].action_key=='student.internship.volunteer-result'
            assert own[0].action_params_json['groupId']==str(ids['0'])
            assert own[0].action_params_json['groupVersion']==str(db.get(InternshipVolunteerGroup,ids['0']).version)
            from app.student_portal.services.action_projection_service import build_message_action
            action=build_message_action(own[0].action_key,own[0].action_params_json)
            assert action['target']['path']=='/internship/volunteer-result'
            assert action['target']['query']['groupId']==str(ids['0'])
            assert action['focusMode']=='DETAIL'
            from app.services.mobile_action_service import build_message_action as mobile_action
            mobile=mobile_action(own[0].action_key,own[0].action_params_json)
            assert mobile['target']['path']=='/pages/student-internship/volunteer-result/index'
            assert mobile['target']['query']['groupId']==str(ids['0'])
            assert mobile['focusMode']=='DETAIL'
            assert len(company)==2 and all(message.receiver_type=='ENTERPRISE' for message in company)
            assert all(message.action_key=='enterprise.internship.application' for message in company)
            assert {message.action_params_json['applicationId'] for message in company}=={str(ids['app']),str(ids['sibling'])}
            assert all(message.action_params_json['campaignId']==str(ids['campaign']) for message in company)
            assert all('私密补正' not in message.content for message in company)
            if action=='return':assert '私密补正' in own[0].content
    finally:set_tenant(None)
