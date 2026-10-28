"""反馈前端合同验证：仅用新建 SUPPORT-FLOW 合成学校，原学校与咨询单不动。"""
import pytest
from test_student_support_story_mysql import seed_support, context, result
from test_yiyang_plan_export_options_mysql import login
from test_yiyang_write_flows_mysql import upload

ROOT='/api/v1/mobile/internship/context/feedback'
STAFF='/api/v1/internship/complaints'


@pytest.mark.parametrize('level',['COLLEGE','DEPARTMENT'])
def test_new_feedback_image_receipt_school_handling_and_student_readback(level,record_property):
    data=seed_support()
    for key in ['tenantId','tenantCode','batchId','recordId']:record_property(key,data[key])
    with login(data,'STUDENT') as student,login(data) as school:
        image=upload(student,name='feedback-synthetic.png',biz='INTERNSHIP_FEEDBACK')
        row=result(student.post(ROOT,json={**context(data),'title':'合成实习指导建议','content':'建议增加每周现场指导时间。','feedbackLevel':level,'imageFileIds':[image['fileId']]}))
        assert row['status']=='RECEIVED' and row['feedbackLevel']==level
        read=result(student.get(ROOT,params=context(data)))
        assert len(read['items'])==1 and read['items'][0]['id']==row['id']
        detail=result(school.get(STAFF+'/'+row['id']))
        assert detail['category']=='STUDENT_FEEDBACK' and detail['imageFileIds']==[image['fileId']]
        assert school.get('/api/v1/files/download/'+image['fileId']).status_code==200
        for action in ['ACCEPT','INVESTIGATE','RESOLVE']:
            detail=result(school.post(STAFF+'/'+row['id']+'/transition',json={'action':action,'expectedVersion':detail['version'],'conclusion':'已核实并安排增加指导。'}))
        final=result(student.get(ROOT,params=context(data)))['items'][0]
        assert final['id']==row['id'] and final['status']=='RESOLVED' and final['conclusion']=='已核实并安排增加指导。'
        assert student.post(ROOT+'/'+row['id']+'/withdraw',json={**context(data),'expectedVersion':row['version']}).status_code==400
