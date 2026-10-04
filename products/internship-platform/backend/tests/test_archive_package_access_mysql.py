"""Normal account / MySQL archive-file boundaries with prepared frozen prerequisites.

Setup is not evidence for the archive lifecycle UI. Package generation, download,
restore checks and revoke use the real registered commands and stored ZIP bytes.
"""
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
from sqlalchemy import select

from app.db.session import get_sessionmaker
from app.models import InternshipArchive, InternshipRecord, InternshipEvidencePackage, Role, User, UserRole, TeacherStudentScope
from app.core.security import hash_password
from app.models.file import ArchiveManifest, ArchiveManifestItem, FileAsset, FileVersion, FileObject, FileBinding
from app.modules.internship.services import internship_material_center_service as core, internship_audit_service as audit
from test_yiyang_write_flows_mysql import flow, login, png_bytes, seed_flow, upload, PASSWORD

ROOT = '/api/v1/internship'


def ok(response):
    assert response.status_code == 200 and response.json()['code'] == 0, response.text
    return response.json()['data']


@pytest.fixture
def frozen(flow):
    with login(flow) as school:
        photo = upload(school, biz='INTERNSHIP_REPORT')
    prepare_frozen(flow, int(flow['recordId']), photo)
    audit.process_pending(limit=1000)
    return flow


def prepare_frozen(flow, record_id, photo):
    with get_sessionmaker()() as db:
        record = db.get(InternshipRecord, record_id)
        record.status = 'ARCHIVED'
        tenant = int(flow['tenantId'])
        archive = InternshipArchive(tenant_id=tenant, internship_id=record.id,
            student_id=record.student_id, batch_id=record.batch_id, status='ARCHIVED',
            previous_record_status='ASSESSING', completeness=100, version=1)
        asset = FileAsset(tenant_id=tenant, asset_code='ARCHIVE-PROOF:'+str(record.id),
            title='合成归档材料', category_code='PROCESS_REPORT')
        db.add_all([archive, asset]); db.flush()
        version = FileVersion(tenant_id=tenant, asset_id=asset.id,
            file_object_id=int(photo['fileId']), version_no=1, status='ARCHIVED')
        manifest = ArchiveManifest(tenant_id=tenant, module_code=core.MODULE_CODE,
            archive_type=core.ARCHIVE_TYPE, target_type=core.TARGET_TYPE, target_id=str(record.id),
            revision=1, status='FROZEN', rule_version='TEST-FROZEN-1', frozen_at=datetime.utcnow())
        db.add_all([version, manifest]); db.flush()
        item = ArchiveManifestItem(tenant_id=tenant, manifest_id=manifest.id,
            material_code='PROCESS_REPORT', asset_id=asset.id, version_id=version.id,
            file_object_id=int(photo['fileId']), file_name_snapshot=photo['fileName'],
            size_snapshot=photo['sizeBytes'], sha256_snapshot=photo['sha256'],
            review_status='APPROVED', scan_result='NOT_REQUIRED', sort_no=1)
        db.add(item); db.flush()
        manifest.manifest_sha256 = core.manifest_digest(manifest, [item])
        db.commit()
        flow.update(manifestId=manifest.id, materialId=int(photo['fileId']), versionId=version.id)
    return record_id


def generate(school, data, kind):
    route = f"/archive/{data['recordId']}/package" if kind == 'single' else f"/archive-batches/{data['batchId']}/packages"
    return ok(school.post(ROOT+route, json={} if kind == 'single' else {'limit':20}))


def specialized(row, kind):
    return ROOT+('/archive-packages/' if kind == 'single' else '/archive-batch-packages/')+row['packageId']+'/download'


def revoke(school, data):
    with get_sessionmaker()() as db:
        archive = db.scalar(select(InternshipArchive).where(InternshipArchive.internship_id == int(data['recordId'])))
        record = db.get(InternshipRecord, int(data['recordId']))
        versions = {'expectedVersion':archive.version, 'recordExpectedVersion':record.version}
    return ok(school.post(ROOT+f"/archive/{data['recordId']}/revoke",
        json={**versions,'reason':'合成归档材料需要撤销重新核对确认'}))


@pytest.mark.parametrize('kind', ['single','batch'])
def test_valid_zip_and_all_owner_file_routes_deny_after_real_revoke(frozen, kind):
    with login(frozen) as school:
        row = generate(school, frozen, kind)
        raw = school.get(specialized(row, kind))
        assert raw.status_code == 200 and sha256(raw.content).hexdigest() == row['sha256']
        with zipfile.ZipFile(BytesIO(raw.content)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            items = manifest['items'] if kind == 'single' else manifest['records'][0]['items']
            assert len(archive.infolist()) == 2 and len(items) == 1
            assert archive.read(items[0]['archivePath']) == png_bytes()
        restore = ok(school.post(ROOT+'/archive-packages/'+row['packageId']+'/restore-check'))
        assert restore['restoreReady'] and restore['verifiedRowCount'] == 1 and restore['verifiedFileCount'] == 1
        generic = '/api/v1/files/download/'+row['fileId']
        assert school.get(generic).content == raw.content
        assert revoke(school, frozen)['invalidatedPackageCount'] == 1
        assert school.get(specialized(row, kind)).status_code == 404
        for route in [generic, '/api/v1/files/preview/'+row['fileId'], '/api/v1/files/'+row['fileId'], '/api/v1/files/'+row['fileId']+'/url']:
            denied = school.get(route)
            assert denied.status_code == 404, f"revoked archive leaked through {route}: {denied.status_code}"


@pytest.mark.parametrize('kind', ['single','batch'])
def test_archive_file_cannot_bypass_package_permission(frozen, kind):
    with login(frozen) as school, login(frozen, 'INTERN_MENTOR') as mentor, login(frozen, 'STUDENT') as student:
        row = generate(school, frozen, kind)
        # Normal mentor has archive.view, never package/execute/revoke.
        assert mentor.get(specialized(row, kind)).status_code == 403
        for actor in (mentor, student):
            assert actor.get('/api/v1/files/download/'+row['fileId']).status_code == 404
        with get_sessionmaker()() as db:
            file = db.get(FileObject, int(row['fileId']))
            file.owner_user_id = frozen['users']['INTERN_MENTOR']
            db.commit()
        assert mentor.get('/api/v1/files/download/'+row['fileId']).status_code == 404


@pytest.mark.parametrize('kind', ['single','batch'])
@pytest.mark.parametrize('change', ['failed','unbound','retagged','fingerprint','manifest-revoked',
    'manifest-drift','member-count','missing-members','spliced-metadata',
    'source-quarantined','source-version-invalidated','source-fingerprint'])
def test_invalid_frozen_authority_denies_generic_dedicated_and_restore(frozen, kind, change):
    with login(frozen) as school:
        row = generate(school, frozen, kind)
        with get_sessionmaker()() as db:
            package = db.get(InternshipEvidencePackage, int(row['packageId']))
            file = db.get(FileObject, int(row['fileId']))
            binding = db.scalar(select(FileBinding).where(FileBinding.file_id == file.id))
            payload = json.loads(json.dumps(package.manifest_json))
            if change == 'failed': package.status = 'FAILED'
            elif change == 'unbound': binding.status = 'INVALIDATED'
            elif change == 'retagged':
                file.biz_type, file.biz_id = 'TEMP_PRIVATE', None
                binding.status = 'INVALIDATED'
                db.add(FileBinding(tenant_id=int(frozen['tenantId']),file_id=file.id,biz_type='TEMP_PRIVATE',
                    biz_id='OTHER',subject_type='USER',subject_id=str(frozen['users']['SCHOOL_ADMIN']),status='ACTIVE'))
            elif change == 'fingerprint': file.sha256 = 'a'*64
            elif change == 'manifest-revoked': db.get(ArchiveManifest, frozen['manifestId']).status = 'REVOKED'
            elif change == 'manifest-drift':
                item = db.scalar(select(ArchiveManifestItem).where(ArchiveManifestItem.manifest_id == frozen['manifestId']))
                item.sha256_snapshot = 'b'*64
            elif change == 'source-quarantined': db.get(FileObject,frozen['materialId']).scan_status = 'INFECTED'
            elif change == 'source-version-invalidated': db.get(FileVersion,frozen['versionId']).status = 'INVALIDATED'
            elif change == 'source-fingerprint': db.get(FileObject,frozen['materialId']).sha256 = 'c'*64
            elif change == 'member-count': package.row_count += 1
            elif change == 'missing-members': package.included_items = []
            elif change == 'spliced-metadata':
                records = payload['records'] if kind == 'batch' else [payload]
                records[0]['studentId'] = '999999999'
                package.manifest_json = payload
                # Matching included list cannot make the ZIP manifest match edited metadata.
                if kind == 'single': package.included_items = payload['items']
            db.commit()
        for url in ['/api/v1/files/download/'+row['fileId'], specialized(row, kind), '/api/v1/files/'+row['fileId']]:
            denied = school.get(url)
            assert denied.status_code == 404, f"{change} leaked through {url}: {denied.status_code}"
        response = school.post(ROOT+'/archive-packages/'+row['packageId']+'/restore-check')
        expected = 400 if change == 'failed' else 404
        assert response.status_code == expected and not response.json().get('data'), response.text
        assert response.json()['code'] != 0


@pytest.mark.parametrize('kind', ['single','batch'])
def test_foreign_school_does_not_read_or_revoke_package(frozen, kind):
    foreign = seed_flow()
    with login(frozen) as school, login(foreign) as outsider:
        row = generate(school, frozen, kind)
        for url in [specialized(row, kind), '/api/v1/files/'+row['fileId'], '/api/v1/files/download/'+row['fileId']]:
            assert outsider.get(url).status_code == 404
        denied = outsider.post(ROOT+f"/archive/{frozen['recordId']}/revoke",json={
            'reason':'外校合成测试不能撤销此学校归档材料','expectedVersion':1,'recordExpectedVersion':0})
        assert denied.status_code == 404
        assert school.get(specialized(row, kind)).status_code == 200


@pytest.mark.parametrize('kind', ['single','batch'])
def test_modified_zip_bytes_fail_both_download_paths(frozen, kind):
    from pathlib import Path
    from app.config import settings
    from app.services.storage import get_backend
    with login(frozen) as school:
        row = generate(school, frozen, kind)
        with get_sessionmaker()() as db:
            file = db.get(FileObject, int(row['fileId']))
            assert file.tenant_id == int(frozen['tenantId'])
            path = get_backend().fetch_local(file.file_key).resolve()
            assert path.is_relative_to(Path(settings.FILE_STORAGE_DIR).resolve())
        original = path.read_bytes()
        try:
            path.write_bytes(original+b'SYNTHETIC-CORRUPTION')
            for url in [specialized(row, kind), '/api/v1/files/download/'+row['fileId']]:
                assert school.get(url).status_code == 409
            restore = school.post(ROOT+'/archive-packages/'+row['packageId']+'/restore-check')
            # Existing restore command reports a business conflict with HTTP 400.
            assert restore.status_code == 400 and restore.json()['bizCode'] == 'DATA_CONFLICT'
            assert not restore.json().get('data')
        finally:
            path.write_bytes(original)
        assert school.get(specialized(row, kind)).content == original


def add_scoped_admin(data):
    with get_sessionmaker()() as db:
        tenant = int(data['tenantId'])
        role = Role(tenant_id=tenant,role_code='COLLEGE_ADMIN',role_name='合成范围管理员',role_type='SYSTEM',status='ACTIVE')
        user = User(tenant_id=tenant,login_name='college_admin',real_name='合成范围管理员',password_hash=hash_password(PASSWORD),
            user_type='COLLEGE_ADMIN',status='ACTIVE',credential_version=0,must_change_password=False)
        db.add_all([role,user]); db.flush()
        scope = TeacherStudentScope(tenant_id=tenant,teacher_key='db-'+str(user.id),role_code='COLLEGE_ADMIN',
            scope_type='STUDENT',ref_value='S0',status='ACTIVE')
        db.add_all([scope,UserRole(tenant_id=tenant,user_id=user.id,role_id=role.id,status='ACTIVE')]); db.commit()
        return user.id, scope.id


def test_real_scoped_owner_requires_every_batch_member_and_loses_old_session_access(frozen):
    user_id, scope_id = add_scoped_admin(frozen)
    with login(frozen) as school, login(frozen,'COLLEGE_ADMIN') as scoped:
        first = generate(scoped, frozen, 'single')
        assert scoped.get(specialized(first,'single')).status_code == 200
        with get_sessionmaker()() as db:
            other = db.scalar(select(InternshipRecord).where(InternshipRecord.batch_id == int(frozen['batches'][1]['id'])))
            other.batch_id = int(frozen['batchId']); other_id = other.id; db.commit()
        photo = upload(school,biz='INTERNSHIP_REPORT')
        prepare_frozen(frozen, other_id, photo)
        both = generate(school, frozen, 'batch')
        with get_sessionmaker()() as db:
            # Even the owner cannot use a first in-scope member to authorize the whole ZIP.
            db.get(FileObject,int(both['fileId'])).owner_user_id = user_id; db.commit()
        assert scoped.get(specialized(both,'batch')).status_code == 403
        assert scoped.get('/api/v1/files/download/'+both['fileId']).status_code == 404
        with get_sessionmaker()() as db:
            db.get(TeacherStudentScope,scope_id).status = 'REVOKED'; db.commit()
        assert scoped.get('/api/v1/files/download/'+first['fileId']).status_code == 404
        assert scoped.get(specialized(first,'single')).status_code == 403


def test_new_package_keeps_old_frozen_version_downloadable_and_restore_verifiable(frozen):
    with login(frozen) as school:
        first = generate(school,frozen,'single')
        second = generate(school,frozen,'single')
        assert int(second['packageVersion']) == int(first['packageVersion']) + 1
        for row in [first,second]:
            response = school.get(specialized(row,'single'))
            assert response.status_code == 200 and sha256(response.content).hexdigest() == row['sha256']
            assert ok(school.post(ROOT+'/archive-packages/'+row['packageId']+'/restore-check'))['restoreReady']
        assert revoke(school,frozen)['invalidatedPackageCount'] == 2
        assert all(school.get('/api/v1/files/download/'+row['fileId']).status_code == 404 for row in [first,second])


@pytest.mark.parametrize('kind',['single','batch'])
def test_package_pointer_cannot_download_a_different_owner_private_file(frozen, kind):
    with login(frozen) as school:
        row = generate(school,frozen,kind)
        private = upload(school,biz='INTERNSHIP_REPORT')
        with get_sessionmaker()() as db:
            package = db.get(InternshipEvidencePackage,int(row['packageId']))
            package.package_file_id = private['fileId']
            package.package_sha256, package.package_size_bytes = private['sha256'], private['sizeBytes']
            db.commit()
        assert school.get(specialized(row,kind)).status_code == 404
        assert school.post(ROOT+'/archive-packages/'+row['packageId']+'/restore-check').status_code == 404
        # Ordinary own private files retain their existing authorization.
        assert school.get('/api/v1/files/download/'+private['fileId']).content == png_bytes()
