"""Batch scope checks share one resolution, not weaker authorization."""
import pytest
from app.core.exceptions import AppException
from app.services import affairs_dorm_service as dorm


def test_all_buildings_are_checked_with_one_fresh_scope_resolution(monkeypatch):
    calls=[]
    monkeypatch.setattr(dorm,'_dorm_scope_building_ids',lambda db,user:calls.append(user) or {1,2})
    assert dorm._require_dorm_scope(None,['1',2],{'userId':'staff'})=={1,2}
    assert len(calls)==1
    with pytest.raises(AppException):
        dorm._require_dorm_scope(None,[1,3],{'userId':'staff'})
    with pytest.raises(AppException):
        dorm._require_dorm_scope(None,None,{'userId':'staff'})
    assert len(calls)==3
    monkeypatch.setattr(dorm,'_dorm_scope_building_ids',lambda *_:set())
    with pytest.raises(AppException):
        dorm._require_dorm_scope(None,[1,2],{'userId':'staff'})
    monkeypatch.setattr(dorm,'_dorm_scope_building_ids',lambda *_:None)
    assert dorm._require_dorm_scope(None,[1,2],{'userId':'staff'}) is None
