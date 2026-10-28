import pytest
from app.api.v1 import mobile_internship_context as context
from app.core.exceptions import AppException
from app.modules.internship.services import internship_service as reports


def call(**changes):
    return context.teacher_review_queue(**{'batchId':'','recordId':'','exceptionId':'91',
        'weeklyPage':1,'exceptionPage':1,'pageSize':20,'user':{'userId':'4'},**changes})


def test_exception_focus_reuses_scoped_detail_and_survives_first_page(monkeypatch):
    calls=[]
    monkeypatch.setattr(context,'enforce_permission',lambda user,permission:calls.append(permission))
    monkeypatch.setattr(context,'teacher_internship_context',lambda user:{'data':{'defaultBatchId':'2','batches':[{'id':'2'},{'id':'7'}]}})
    monkeypatch.setattr(reports,'get_exception_detail',lambda ident,user: {'id':ident,'batchId':'7','status':'PENDING_HANDLE','version':3})
    monkeypatch.setattr(reports,'list_weekly_reports',lambda *args,**kwargs:([],0))
    def exceptions(*args,**kwargs):
        assert kwargs['batch_id']=='7'
        return ([{'id':str(i)} for i in range(20)],30)
    monkeypatch.setattr(reports,'list_attendance_exceptions',exceptions)
    result=call()['data']
    assert result['batchId']=='7' and result['focusExceptionId']=='91'
    assert result['abnormalCheckins'][0]['id']=='91'
    assert 'internship.attendance.view' in calls


def test_exception_focus_cannot_switch_supplied_batch_or_mix_report(monkeypatch):
    monkeypatch.setattr(context,'enforce_permission',lambda *args:None)
    monkeypatch.setattr(reports,'get_exception_detail',lambda ident,user:{'id':ident,'batchId':'7'})
    with pytest.raises(AppException) as wrong:
        call(batchId='8')
    assert wrong.value.http_status==409
    with pytest.raises(AppException) as mixed:
        call(recordId='19')
    assert mixed.value.http_status==422
