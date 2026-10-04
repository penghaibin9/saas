"""Normal teacher, school administrator and student roles against real MySQL."""
from io import BytesIO
from hashlib import sha256
from PIL import Image
from sqlalchemy import select
from app.db.session import get_sessionmaker
from app.models import InternshipRecord, InternshipTeacherCheckin
from app.models.file import FileBinding
from test_yiyang_write_flows_mysql import flow, login, upload, seed_flow

BASE='/api/v1/teacher-mobile/internship/activity/checkins'


def body(flow,file_id):
    return {'batchId':flow['batchId'],'timezoneName':'Asia/Shanghai','latitude':28.2282345,
        'longitude':112.9388765,'accuracyM':1,'coordinateSystem':'GCJ02','locationProvider':'SYNTHETIC_TEST',
        'address':'合成教师照片位置，非真实现场','note':'合成指导教师照片联调','photoFileId':file_id}


def test_teacher_original_and_watermark_follow_current_authority(flow):
    output=BytesIO()
    Image.new('RGB',(800,600),(228,238,246)).save(output,format='JPEG')
    original=output.getvalue()
    with login(flow,'INTERN_MENTOR') as teacher,login(flow) as school,login(flow,'STUDENT') as student:
        photo=upload(teacher,original,name='teacher-camera.jpg',mime='image/jpeg',biz='INTERNSHIP_TEACHER_CHECKIN_PHOTO')
        response=teacher.post(BASE,json=body(flow,photo['fileId']))
        assert response.status_code==200 and response.json()['code']==0, response.text
        row=response.json()['data']
        ids=[row['photoFileId'],row['watermarkedFileId']]
        hashes=[row['photoSha256'],row['watermarkedSha256']]
        for index,file_id in enumerate(ids):
            assert teacher.get('/api/v1/files/'+file_id).status_code==200
            assert school.get('/api/v1/files/'+file_id).status_code==200
            own=teacher.get('/api/v1/files/download/'+file_id)
            school_read=school.get('/api/v1/files/download/'+file_id)
            assert own.status_code==200 and school_read.status_code==200 and own.content==school_read.content
            assert sha256(own.content).hexdigest()==hashes[index]
            if index==0: assert own.content==original
            assert student.get('/api/v1/files/download/'+file_id).status_code==404
        foreign=seed_flow()
        with login(foreign,'INTERN_MENTOR') as outsider:
            for file_id in ids:
                assert outsider.get('/api/v1/files/'+file_id).status_code==404
                assert outsider.get('/api/v1/files/download/'+file_id).status_code==404
        with get_sessionmaker()() as db:
            record=db.get(InternshipRecord,int(flow['recordId']))
            previous_advisor=record.advisor_user_id
            record.advisor_user_id=flow['users']['SCHOOL_ADMIN']
            db.commit()
        for file_id in ids:
            assert teacher.get('/api/v1/files/'+file_id).status_code==404
            assert teacher.get('/api/v1/files/download/'+file_id).status_code==404
            assert school.get('/api/v1/files/download/'+file_id).status_code==200
        with get_sessionmaker()() as db:
            db.get(InternshipRecord,int(flow['recordId'])).advisor_user_id=previous_advisor
            db.commit()
        for file_id in ids:
            assert teacher.get('/api/v1/files/download/'+file_id).status_code==200
        with get_sessionmaker()() as db:
            bindings=db.scalars(select(FileBinding).where(FileBinding.tenant_id==int(flow['tenantId']),
                FileBinding.biz_type=='INTERNSHIP_TEACHER_CHECKIN')).all()
            for binding in bindings: binding.status='INACTIVE'
            db.commit()
        for file_id in ids:
            assert teacher.get('/api/v1/files/'+file_id).status_code==404
            assert teacher.get('/api/v1/files/download/'+file_id).status_code==404
            assert school.get('/api/v1/files/download/'+file_id).status_code==404


def test_teacher_cannot_use_students_private_camera_file(flow):
    output=BytesIO()
    Image.new('RGB',(800,600),(228,238,246)).save(output,format='JPEG')
    with login(flow,'STUDENT') as student,login(flow,'INTERN_MENTOR') as teacher:
        photo=upload(student,output.getvalue(),name='student-camera.jpg',mime='image/jpeg',biz='INTERNSHIP_CHECKIN_PHOTO')
        denied=teacher.post(BASE,json=body(flow,photo['fileId']))
        assert denied.status_code in {403,404}, denied.text
    with get_sessionmaker()() as db:
        assert not db.scalars(select(InternshipTeacherCheckin).where(InternshipTeacherCheckin.tenant_id==int(flow['tenantId']))).all()


def test_teacher_watermark_keeps_the_maximum_permitted_address(flow):
    output=BytesIO()
    Image.new('RGB',(800,600),(228,238,246)).save(output,format='JPEG')
    address=('合成最长中文现场地址'*50)[:500]
    with login(flow,'INTERN_MENTOR') as teacher:
        photo=upload(teacher,output.getvalue(),name='teacher-long-address.jpg',mime='image/jpeg',biz='INTERNSHIP_TEACHER_CHECKIN_PHOTO')
        response=teacher.post(BASE,json={**body(flow,photo['fileId']),'address':address})
        assert response.status_code==200 and response.json()['code']==0, response.text
        row=response.json()['data']
        assert address in row['watermarkText'] and len(row['watermarkText'])>500
        listed=teacher.get(BASE,params={'batchId':flow['batchId']})
        assert listed.status_code==200 and listed.json()['data'][0]['watermarkText']==row['watermarkText']
        image=teacher.get('/api/v1/files/download/'+row['watermarkedFileId'])
        assert image.status_code==200 and sha256(image.content).hexdigest()==row['watermarkedSha256']
        with Image.open(BytesIO(image.content)) as rendered:
            assert rendered.width==800 and rendered.height>600
