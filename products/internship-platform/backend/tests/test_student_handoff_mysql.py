"""Student-PC handoff on one retained synthetic MySQL school; no business/API substitutes."""
from hashlib import sha256
import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.config import settings
from app.db.session import get_sessionmaker
from app.models.file import FileBinding, FileObject, FileVersion
from app.services.file_scan_service import process_next_scan_job
from test_plan_allocation_story_mysql import ROOT, context, login, ok, seed_plan_story
from test_yiyang_write_flows_mysql import png_bytes

PORTAL = '/api/v1/portal/internship'
# The PC materials page deliberately uses this same student-owned facade as the mobile page.
MATERIALS = '/api/v1/mobile/internship/context/material-requirements'
TEACHER = '/api/v1/mobile/teacher/internship/context'


@pytest.fixture(scope='module')
def story():
    if os.environ.get('GAP09_MYSQL_ACCEPTANCE') != '1':
        pytest.skip('explicit isolated MySQL opt-in required')
    target = make_url(settings.DATABASE_URL)
    assert settings.APP_ENV == 'test' and target.get_backend_name() == 'mysql'
    assert target.host in {'127.0.0.1', 'localhost'} and 'test' in (target.database or '')
    data = seed_plan_story()
    # Use the normal school command to establish the relationship, never a final-state DB edit.
    with login(data) as school:
        record = ok(school.get(ROOT + '/intern-students/' + data['recordId']))
        ok(school.post(ROOT + '/intern-students/' + data['recordId'] + '/advisor', json={
            'advisorUserId': str(data['users']['INTERN_MENTOR']),
            'expectedVersion': record['version'],
        }))
    return data


def upload_ready(client, story, name, purpose):
    uploaded = ok(client.post('/api/v1/files', params={'bizType': purpose},
        files={'file': (name, png_bytes(), 'image/png')}))
    file_id = uploaded['fileId']
    if not uploaded['readyForBusiness']:
        scanned = process_next_scan_job(tenant_id=int(story['tenantId']), file_id=int(file_id))
        assert scanned.get('processed') is True and scanned.get('jobStatus') == 'SUCCEEDED', scanned
    meta = ok(client.get('/api/v1/files/' + file_id))
    assert meta['readyForBusiness'] is True and meta['sha256'] == sha256(png_bytes()).hexdigest()
    assert 'fileKey' not in meta and 'storagePath' not in meta
    assert client.get('/api/v1/files/download/' + file_id).content == png_bytes()
    return meta


def test_student_pc_safety_start_commit_submit_and_readback(story):
    with login(story) as school, login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher:
        dashboard = ok(student.get(PORTAL + '/my', params={'batchId': story['batchId']}))
        assert dashboard['recordId'] == story['recordId'] and dashboard['batchId'] == story['batchId']
        course = ok(school.post(ROOT + '/compliance/safety', json={
            'batchId': story['batchId'], 'title': '合成电脑端安全学习', 'courseVersion': '合成第一版',
            'contentSnapshot': '合成课程：识别岗位风险，停止危险操作，报告指导教师。',
            'requiredMinutes': 0, 'passingScore': 80, 'maxAttempts': 3, 'requireCommitment': True,
        }))
        course_id = course['id']
        courses = ok(student.get(PORTAL + '/safety/courses', params={'batchId': story['batchId']}))
        assert any(row['id'] == course_id for row in courses)
        started = ok(student.post(PORTAL + '/safety/courses/' + course_id + '/start'))
        assert started['status'] == 'IN_PROGRESS' and started['studiedMinutes'] == 0
        detail = ok(student.get(PORTAL + '/safety/courses/' + course_id + '/detail'))
        assert detail['id'] == course_id and detail['batchId'] == story['batchId']
        assert detail['completion']['id'] == started['id']
        committed = ok(student.post(PORTAL + '/safety/completions/' + started['id'] + '/commit', json={
            'expectedVersion': started['version'], 'contentHash': detail['contentHash'],
            'deviceDigest': 'synthetic-student-pc',
        }))
        assert committed['commitmentConfirmed'] and committed['version'] > started['version']
        body = {'expectedVersion': committed['version'], 'studiedMinutes': 0,
                'answers': {'readAndUnderstood': True}}
        submitted = ok(student.post(PORTAL + '/safety/courses/' + course_id + '/submit', json=body))
        assert submitted['id'] == started['id'] and submitted['status'] == 'PENDING_REVIEW'
        assert student.post(PORTAL + '/safety/courses/' + course_id + '/submit', json=body).json()['code'] != 0
        reread = ok(student.get(PORTAL + '/safety/courses/' + course_id + '/detail'))['completion']
        assert reread['id'] == submitted['id'] and reread['version'] == submitted['version']
        assert reread['status'] == 'PENDING_REVIEW' and reread['studiedMinutes'] == 0
        mobile = ok(student.get('/api/v1/mobile/internship/safety/courses/' + course_id + '/detail'))
        assert mobile['completion']['id'] == reread['id'] and mobile['completion']['status'] == reread['status']
        assert teacher.post(PORTAL + '/safety/courses/' + course_id + '/start').status_code == 403
        assert teacher.post(PORTAL + '/safety/completions/' + started['id'] + '/commit', json={
            'expectedVersion': submitted['version'], 'contentHash': detail['contentHash'],
        }).status_code == 403
        assert teacher.post(PORTAL + '/safety/courses/' + course_id + '/submit', json=body).status_code == 403


def test_student_pc_stamped_material_upload_teacher_review_and_same_original(story):
    with login(story) as school, login(story, 'STUDENT') as student, login(story, 'INTERN_MENTOR') as teacher, login(story, 'OTHER_MENTOR') as unrelated:
        requirement = ok(school.post(ROOT + '/material-requirements', json={
            'batchId': story['batchId'], 'materialCode': 'PC_STAMP_' + uuid4().hex[:10].upper(),
            'materialName': '合成盖章企业鉴定表', 'isRequired': True,
            'allowedExtensions': ['png'], 'minFiles': 1, 'maxFiles': 2,
        }))
        requirement_id = requirement['id']
        template = upload_ready(school, story, '合成鉴定表模板.png', 'INTERNSHIP_MATERIAL_TEMPLATE')
        ok(school.post(ROOT + '/material-requirements/' + requirement_id + '/template',
                       json={'fileId': template['fileId']}))
        ok(school.post(ROOT + '/material-requirements/' + requirement_id + '/publish'))
        rows = ok(student.get(MATERIALS, params=context(story)))
        assert next(row for row in rows if row['id'] == requirement_id)['batchId'] == story['batchId']
        evidence = upload_ready(student, story, '合成盖章鉴定表.png', 'INTERNSHIP_CUSTOM_MATERIAL')
        file_id = evidence['fileId']
        assert teacher.get('/api/v1/files/download/' + file_id).status_code == 404
        body = {**context(story), 'fileIds': [file_id], 'expectedVersion': 0,
                'comment': '合成电脑端材料，提交指导教师审核'}
        submitted = ok(student.post(MATERIALS + '/' + requirement_id + '/submit', json=body))
        assert submitted['requirementId'] == requirement_id and submitted['status'] == 'SUBMITTED'
        assert submitted['internshipId'] == story['recordId'] and submitted['batchId'] == story['batchId']
        queue = ok(teacher.get(TEACHER + '/material-requirements/' + requirement_id + '/students',
                               params={'state': 'PENDING_REVIEW'}))
        assert [row['submission']['id'] for row in queue['items']] == [submitted['id']]
        assert teacher.get('/api/v1/files/download/' + file_id).content == png_bytes()
        review = {'action': 'APPROVE', 'expectedVersion': submitted['version'],
                  'comment': '合成盖章鉴定表完整，按正常导师权限审核'}
        review_path = TEACHER + '/material-submissions/' + submitted['id'] + '/review'
        assert student.post(review_path, json=review).status_code == 403
        assert unrelated.post(review_path, json=review).status_code in {403, 404}
        assert unrelated.get('/api/v1/files/download/' + file_id).status_code == 404
        approved = ok(teacher.post(review_path, json=review))
        assert approved['id'] == submitted['id'] and approved['status'] == 'APPROVED'
        reread = next(row for row in ok(student.get(MATERIALS, params=context(story)))
                      if row['id'] == requirement_id)['submission']
        assert reread['id'] == submitted['id'] and reread['version'] == approved['version']
        assert reread['status'] == 'APPROVED' and reread['files'][0]['fileId'] == file_id
        assert ok(teacher.get(TEACHER + '/material-requirements/' + requirement_id + '/students',
                              params={'state': 'PENDING_REVIEW'}))['items'] == []
        assert student.post(MATERIALS + '/' + requirement_id + '/submit', json=body).status_code == 409
        wrong_context = {**context(story), 'batchId': story['batches'][1]['id']}
        assert student.get(MATERIALS, params=wrong_context).status_code in {400, 403, 404, 409}
        with get_sessionmaker()() as db:
            file_object = db.get(FileObject, int(file_id))
            binding = db.scalar(select(FileBinding).where(
                FileBinding.tenant_id == int(story['tenantId']), FileBinding.file_id == int(file_id),
                FileBinding.biz_type == 'INTERNSHIP_CUSTOM_MATERIAL', FileBinding.is_current.is_(True)))
            assert binding and binding.student_id == int(story['studentId'])
            assert binding.biz_id == submitted['id'] + ':1'
            version = db.get(FileVersion, binding.version_id)
            assert version.is_current and version.status == 'APPROVED'
            assert version.file_object_id == file_object.id
            assert file_object.sha256 == sha256(png_bytes()).hexdigest()
