"""真实 MySQL：新增成绩办理与学期封存共用锁，不遗留封存后的在途单。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event, select

from app.core.exceptions import AppException
from app.db.session import get_engine, get_sessionmaker
from app.models import AaGradeRecheck, AaGradeTask, AaTerm, AffairsAuditTrail, WorkflowInstance
from tests.test_aa_grade_correction_command import TID, _activate, _application_body, _seed_published_grade, command
from tests.test_aa_grade_recheck import BASE, _stu_token


def _counts():
    with get_sessionmaker()() as db:
        return tuple(db.query(model).filter(model.tenant_id == TID).count()
                     for model in (AaGradeRecheck, WorkflowInstance, AffairsAuditTrail))


@pytest.mark.parametrize("actor", ["student", "teacher"])
@pytest.mark.parametrize("concurrent", [False, True])
def test_archived_term_rejects_new_grade_proceeding_without_partial_write(client, db_mode, actor, concurrent):
    _activate()
    ids = _seed_published_grade()
    body = _application_body(ids) if actor == 'teacher' else None
    with get_sessionmaker()() as db:
        term_id = db.get(AaGradeTask, ids['taskId']).term_id
    before = _counts()

    def apply():
        if actor == 'teacher':
            try:
                user = _activate('teacher01', 'ACADEMIC_TEACHER')
                command.change_request(ids['taskId'], ids['recordId'], user, body)
            except AppException as error:
                return error.code
            return 'UNEXPECTED_SUCCESS'
        response = client.post(f'{BASE}/grade-recheck/submit', headers=_stu_token('更正甲', 'GC001'),
            json={'acadGradeId': str(ids['gradeId']), 'reason': '请核对卷面与登记成绩'})
        assert response.status_code == 409, response.status_code
        return response.json()['bizCode']

    with get_sessionmaker()() as sealing:
        term = sealing.scalar(select(AaTerm).where(AaTerm.id == term_id).with_for_update())
        term.status = 'ARCHIVED'
        sealing.flush()
        if concurrent:
            reached_lock = Event()

            def observe(conn, cursor, statement, parameters, context, executemany):
                if 't_aa_term' in statement and 'FOR UPDATE' in statement.upper():
                    reached_lock.set()

            engine = get_engine()
            event.listen(engine, 'before_cursor_execute', observe)
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(apply)
                    try:
                        assert reached_lock.wait(15), '申请没有进入共同学期锁'
                        assert not pending.done(), '封存事务提交前，申请必须等待'
                    finally:
                        sealing.commit()
                    assert pending.result(timeout=20) == 'TERM_ARCHIVED'
            finally:
                event.remove(engine, 'before_cursor_execute', observe)
        else:
            sealing.commit()
            assert apply() == 'TERM_ARCHIVED'
    assert _counts() == before
