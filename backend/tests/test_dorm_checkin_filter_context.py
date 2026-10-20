"""迎新批次与行政班过滤必须先于分页，并沿用住宿数据范围。"""
from types import SimpleNamespace
from test_dorm_d3_allocation import _admin, _create, _seed_authorities, BASE, TID


def test_pending_roster_options_and_orientation_share_batch_context(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent, OrientationBatch, SchoolClass, StudentProfile
    from app.services import affairs_dorm_stay_service as service

    seeded = _seed_authorities(students=2, beds=2)
    headers = _admin(client)
    allocation = _create(client, headers, seeded, "ADMIN_AUTO", "CHECKIN-FILTERS")
    assert client.post(f"{BASE}/{allocation}/dry-run", headers=headers).status_code == 200
    assert client.post(f"{BASE}/{allocation}/publish", headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        first = db.get(OrientationStudent, seeded['orientationStudents'][0])
        second = db.get(OrientationStudent, seeded['orientationStudents'][1])
        original = db.get(OrientationBatch, first.batch_id)
        other = OrientationBatch(tenant_id=TID,batch_no='CHECKIN-OTHER',batch_name='另一迎新批次',year='2026',status='ACTIVE',flow_version_id=original.flow_version_id)
        cls = SchoolClass(tenant_id=TID,major_id=1,class_name='另一行政班',grade='2026',status='ACTIVE',class_status='NORMAL')
        db.add_all([other,cls]);db.flush()
        second.batch_id=other.id
        db.get(StudentProfile, second.student_id).class_id=cls.id
        batch_id, other_batch, class_id = first.batch_id, other.id, cls.id
        first_student=first.student_id
        db.commit()

    stays='/api/v1/student-affairs/dorm/stays'
    def read(path,**query):
        result=client.get(path,headers=headers,params=query)
        assert result.status_code==200,result.text
        return result.json()['data']
    selected=read(stays,status='RESERVED',orientationBatchId=str(batch_id),pageSize=1)
    assert selected['total']==1 and selected['items'][0]['studentId']==str(first_student)
    assert selected['items'][0]['className']=='D3软件2601'
    assert read(stays,status='RESERVED',orientationBatchId=str(batch_id),classId=str(class_id))['total']==0
    assert read(stays,status='RESERVED',orientationBatchId=str(other_batch),classId=str(class_id))['total']==1
    assert read(stays,status='RESERVED',orientationBatchId='99999999')['items']==[]
    orientation=read('/api/v1/orientation/dorms',batchId=str(batch_id),pageSize=1)
    assert orientation['total']==1 and orientation['items'][0]['className']=='D3软件2601'
    assert read('/api/v1/orientation/dorms',batchId='99999999')['items']==[]
    options=read(stays+'/filter-options',orientationBatchId=str(other_batch))
    assert {x['value'] for x in options['batches']}=={str(batch_id),str(other_batch)}
    assert options['classes']==[{'value':str(class_id),'label':'另一行政班'}]
    # Reuse the same trusted scope consumer for options and roster; never offer another class.
    monkeypatch.setattr(service,'_teacher_scope',lambda *_:SimpleNamespace(scope_type='CLASS',allowed_class_ids=lambda db:{class_id}))
    assert read(stays,status='RESERVED',orientationBatchId=str(batch_id))['total']==0
    assert {x['value'] for x in read(stays+'/filter-options')['batches']}=={str(other_batch)}
    monkeypatch.setattr(service,'_teacher_scope',lambda *_:SimpleNamespace(scope_type='NONE'))
    assert read(stays,status='RESERVED')['items']==[]
    assert read(stays+'/filter-options')=={'batches':[],'classes':[]}
