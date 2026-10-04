"""School configuration rejects incomplete or ambiguous location authority."""
from copy import deepcopy
import pytest
from pydantic import ValidationError
from app.modules.internship.schemas.internship import TeacherCheckinRuleCfg
from app.modules.internship.services import internship_teacher_activity_service as teacher

SITE = {'name':'合成地点', 'centerLat':0, 'centerLng':0, 'radiusM':30, 'coordinateSystem':'WGS84'}

@pytest.mark.parametrize('change', [
    {'name':' '}, {'centerLat':91}, {'centerLng':181}, {'radiusM':29},
    {'coordinateSystem':'UNKNOWN'}, {'centerLat':float('nan')}, {'centerLng':float('inf')},
])
def test_invalid_site_cannot_become_school_configuration(change):
    with pytest.raises(ValidationError):
        TeacherCheckinRuleCfg(locations=[{**SITE,**change}])

def test_zero_coordinates_are_valid_and_duplicate_names_are_rejected():
    assert TeacherCheckinRuleCfg(locations=[SITE]).locations[0].centerLat==0
    with pytest.raises(ValidationError):
        TeacherCheckinRuleCfg(locations=[SITE,deepcopy(SITE)])

@pytest.mark.parametrize('field', ['latitude','longitude','accuracyM'])
def test_nonfinite_sensor_input_is_rejected_by_service(field):
    from app.core.exceptions import AppException
    for value in [float('nan'),float('inf')]:
        with pytest.raises(AppException):
            teacher._location({'latitude':28,'longitude':112,'accuracyM':1,field:value})


def test_risk_flags_are_bounded_codes_and_not_unstructured_audit_text():
    from app.api.v1.teacher_mobile_internship import TeacherCheckinBody
    assert TeacherCheckinBody(batchId=1,deviceRiskFlags=['MOCK_LOCATION']).deviceRiskFlags==['MOCK_LOCATION']
    with pytest.raises(ValidationError):
        TeacherCheckinBody(batchId=1,deviceRiskFlags=['unstructured private text'])
    with pytest.raises(ValidationError):
        TeacherCheckinBody(batchId=1,mockLocation='false')
