"""AP03 real MySQL/API plan save, publish, frozen snapshot and batch document tests."""
import base64
from io import BytesIO
from pypdf import PdfReader
from app.db.session import get_sessionmaker
from app.models import InternshipBatch
from test_yiyang_gap09_minimum_age_mysql import admin, scenario
from test_yiyang_sm02_plan_contract import _payload
from test_yiyang_ap03_bulk_export import exported_rows

BASE='/api/v1/internship/plans'

def make_published_plan(admin, scenario, number):
    import uuid
    number = number + "-" + uuid.uuid4().hex[:12]
    record=scenario(years=20)
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,int(record['batchId']))
        batch.rules_config={**(batch.rules_config or {}),
          'checkin':{'requiredDays':0},'weeklyReport':{'requiredCount':0,'minWordCount':0},
          'processReport':{'dailyRequiredCount':0,'dailyMinWords':30,'monthlyRequiredCount':4,
                           'monthlyMinWords':500,'summaryRequiredCount':1,'summaryMinWords':1000}}
        db.commit()
    body={**_payload(),'planNo':number,'title':'正式实习计划 '+number,
          'content':'在企业开展岗位实习，完成安全教育、岗位训练、过程记录与实习总结。',
          'tasks':[{'sortOrder':1,'name':'岗位实习总结','requirement':'提交真实岗位实习过程总结及相关证明材料','deadline':'2026-12-30'}]}
    response=admin.put(f"{BASE}/batch/{record['batchId']}",json=body)
    assert response.status_code==200 and response.json()['code']==0,response.text
    saved=response.json()['data']
    published=admin.post(f"{BASE}/batch/{record['batchId']}/publish",json={'expectedVersion':saved['version']})
    assert published.json()['code']==0,published.text
    return record,published.json()['data']


def test_published_plans_export_canonical_fields_without_refreshing_live_rules(admin,scenario):
    first,plan1=make_published_plan(admin,scenario,'000000000000000001')
    second,plan2=make_published_plan(admin,scenario,'000000000000000002')
    with get_sessionmaker()() as db:
        batch=db.get(InternshipBatch,int(first['batchId']))
        batch.rules_config={'processReport':{'monthlyRequiredCount':99}}
        db.commit()
    ids=[first['batchId'],second['batchId'],first['batchId']]
    result=admin.post(BASE+'/bulk-export.xlsx',json={'batchIds':ids})
    assert result.status_code==200 and result.json()['code']==0,result.text
    data=result.json()['data']
    assert data['rowCount']==2
    rows=exported_rows(data); headers=next(x for x in rows if '批次名称' in x)
    entries=[dict(zip(headers,x)) for x in rows[rows.index(headers)+1:] if len(x)==len(headers)]
    assert {x['计划编号'] for x in entries}=={plan1['planNo'],plan2['planNo']}
    assert all(x['月报篇数']=='4' and x['签到天数']=='0' for x in entries)
    result=admin.post(BASE+'/bulk-export.pdf',json={'batchIds':ids})
    assert result.json()['code']==0,result.text
    reader=PdfReader(BytesIO(base64.b64decode(result.json()['data']['contentBase64'])))
    content=''.join(page.extract_text() for page in reader.pages)
    assert plan1['planNo'] in content and plan2['planNo'] in content
    assert '按学校实习补贴管理办法执行' in content


def test_missing_or_inaccessible_plan_does_not_yield_partial_export(admin,scenario):
    first,_=make_published_plan(admin,scenario,'P-001')
    second=scenario(years=20)
    for other in [second['batchId'],'9223372036854775807']:
        response=admin.post(BASE+'/bulk-export.xlsx',json={'batchIds':[first['batchId'],other]})
        assert response.json()['code']!=0,response.text
        assert 'contentBase64' not in response.text


def test_student_cannot_export_school_plans(admin,scenario):
    from test_yiyang_sp06_sp07_formal_document_mysql import own_client
    first,_=make_published_plan(admin,scenario,'P-002')
    with own_client(first) as student:
        response=student.post(BASE+'/bulk-export.xlsx',json={'batchIds':[first['batchId']]})
        assert response.status_code==403,response.text


def test_duplicate_plan_number_returns_409_without_partial_plan(admin,scenario):
    from app.models import InternshipBatchPlan
    from sqlalchemy import select
    first,plan=make_published_plan(admin,scenario,'PLAN-UNIQUE')
    second=scenario(years=20)
    body={**_payload(),'planNo':plan['planNo'],'title':'重复编号测试计划',
          'content':'按照学校实习计划安排开展岗位实习、过程记录与企业考核，测试编号冲突。',
          'tasks':[{'sortOrder':1,'name':'岗位任务','requirement':'完成岗位实践总结与过程记录'}]}
    response=admin.put(f"{BASE}/batch/{second['batchId']}",json=body)
    assert response.status_code==409,response.text
    assert response.json()['bizCode']=='DATA_CONFLICT'
    with get_sessionmaker()() as db:
        assert db.scalar(select(InternshipBatchPlan).where(InternshipBatchPlan.batch_id==int(second['batchId']))) is None
    original=admin.get(f"{BASE}/batch/{first['batchId']}")
    assert original.json()['data']['planNo']==plan['planNo']
    assert original.json()['data']['status']=='PUBLISHED'
