"""Every selection read uses explicit round/record identity before discovery or material reads."""
from uuid import uuid4

import pytest

from app.core.security import get_current_user
from app.db.session import get_sessionmaker
from app.models.internship_enterprise_portal import InternshipRecruitmentCampaign
from app.models.internship_volunteer_group import InternshipVolunteerGroup
from tests.test_internship_student_volunteer_results import own_group
from tests.test_internship_school_volunteers import TID


@pytest.mark.parametrize('prefix', ['/api/v1/portal/internship', '/api/v1/mobile/internship'])
def test_original_round_reads_do_not_follow_new_open_round(client, auth_headers, db_mode, prefix):
    ids, user = own_group()
    with get_sessionmaker()() as db:
        group = db.get(InternshipVolunteerGroup, ids['0'])
        group.status = 'NEEDS_REVISION'
        record_id = group.record_id
        old = db.get(InternshipRecruitmentCampaign, ids['campaign'])
        old.status = 'CLOSED'
        newer = InternshipRecruitmentCampaign(tenant_id=TID, batch_id=ids['batch'],
            campaign_code=uuid4().hex, campaign_name='另一轮招聘季', round_no=2, status='OPEN',
            application_material_policy_json={'requiredProfileFields': ['strengths']})
        db.add(newer); db.commit(); newer_id = newer.id
    previous = client.app.dependency_overrides.get(get_current_user)
    client.app.dependency_overrides[get_current_user] = lambda: user
    headers = {**auth_headers, 'X-Internship-Batch-Id': str(ids['batch'])}
    params = {'campaignId': ids['campaign'], 'recordId': record_id}
    try:
        current = client.get(prefix+'/catalog/context', headers=headers)
        assert current.status_code == 200, current.json()
        assert current.json()['data']['campaignId'] == str(newer_id)
        original = client.get(prefix+'/catalog/context', headers=headers, params=params)
        assert original.status_code == 200, original.json()
        assert original.json()['data']['campaignId'] == str(ids['campaign'])
        assert original.json()['data']['recordId'] == str(record_id)
        assert original.json()['data']['canSelect'] is False
        new_material = client.get(prefix+'/profile/completeness', headers=headers)
        assert new_material.status_code == 200, new_material.json()
        assert new_material.json()['data']['readyToSubmit'] is False
        old_material = client.get(prefix+'/profile/completeness', headers=headers, params=params)
        assert old_material.status_code == 200, old_material.json()
        assert old_material.json()['data']['campaignId'] == str(ids['campaign'])
        assert old_material.json()['data']['readyToSubmit'] is True
        preview = client.get(prefix+'/profile/preview', headers=headers, params=params)
        assert preview.status_code == 200, preview.json()
        assert preview.json()['data']['campaignId'] == str(ids['campaign'])
        volunteers = client.get(prefix+'/context/volunteers', headers=headers, params=params)
        assert volunteers.status_code == 200, volunteers.json()
        assert volunteers.json()['data']['campaignId'] == str(ids['campaign'])
        assert volunteers.json()['data']['status'] == 'NEEDS_REVISION'
        assert len(volunteers.json()['data']['items']) == 1
        # All subordinate reads validate the same explicit identity, including direct details.
        for suffix in ['/catalog/context', '/catalog/positions', '/catalog/positions/999999',
                       '/catalog/companies/999999', '/context/volunteers',
                       '/context/volunteers/material-preview', '/context/volunteers/submissions',
                       '/profile/completeness', '/profile/preview',
                       '/context/volunteers/submissions/1']:
            response = client.get(prefix+suffix, headers=headers,
                                  params={**params, 'recordId': record_id+999999})
            assert response.status_code == 409, (suffix, response.json())
        wrong_pdf = client.post(prefix+'/profile/pdf-preview', headers=headers,
            params={**params, 'recordId': record_id+999999}, json={'previewHash': preview.json()['data']['previewHash']})
        assert wrong_pdf.status_code == 409, wrong_pdf.json()
        mismatch = client.get(prefix+'/catalog/context', params=params,
            headers={**headers, 'X-Internship-Batch-Id': str(ids['batch']+999999)})
        assert mismatch.status_code == 409, mismatch.json()
        explicit_batch = client.get(prefix+'/catalog/context', params={**params, 'batchId': ids['batch']},
            headers={**headers, 'X-Internship-Batch-Id': str(ids['batch']+999999)})
        assert explicit_batch.status_code == 200, explicit_batch.json()
        assert explicit_batch.json()['data']['campaignId'] == str(ids['campaign'])
        record_only = client.get(prefix+'/catalog/context', headers=headers,
                                 params={'recordId': record_id+999999})
        assert record_only.status_code == 409, record_only.json()
        invalid = client.get(prefix+'/catalog/context', headers=headers, params={'campaignId': 0})
        assert invalid.status_code in (400, 422), invalid.json()
    finally:
        if previous is None: client.app.dependency_overrides.pop(get_current_user, None)
        else: client.app.dependency_overrides[get_current_user] = previous
