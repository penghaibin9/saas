"""默认办理队列只核验当前页，查询总数不能触发全校逐人资格核验。"""
from test_dorm_d3_allocation import _admin, _seed_authorities


def test_default_queue_evaluates_only_visible_students(client, db_mode, monkeypatch):
    from app.services import orientation_qualification_service as service

    seeded = _seed_authorities(students=205, beds=1)
    headers = _admin(client)
    evaluated = []
    original = service.evaluate

    def observe(db, student, *args, **kwargs):
        from sqlalchemy import event
        evaluated.append(str(student.id))
        queries = []
        def count(*args):
            queries.append(1)
        engine = db.get_bind()
        event.listen(engine, 'before_cursor_execute', count)
        try:
            result = original(db, student, *args, **kwargs)
        finally:
            event.remove(engine, 'before_cursor_execute', count)
        assert queries == [], 'queue evaluation must not issue per-student queries'
        assert result == original(db, student)
        return result

    monkeypatch.setattr(service, 'evaluate', observe)
    response = client.get('/api/v1/orientation/qualifications', params={
        'page': 2, 'pageSize': 2,
    }, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()['data']
    expected = [str(x) for x in sorted(seeded['orientationStudents'])[2:4]]
    assert data['total'] == 205
    assert [item['id'] for item in data['items']] == expected
    assert all(item['className'] == 'D3软件2601' for item in data['items'])
    assert evaluated == expected
    evaluated.clear()
    response = client.get('/api/v1/orientation/qualifications', params={
        'page': 104, 'pageSize': 2,
    }, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data']['items'] == []
    assert response.json()['data']['total'] == 205
    assert evaluated == []
    evaluated.clear()
    response = client.get('/api/v1/orientation/qualifications', params={
        'page': 2, 'pageSize': 2, 'queue': 'blocked',
    }, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['data']['total'] == 205
    assert [r['id'] for r in response.json()['data']['items']] == expected
    assert len(evaluated) == 205
    assert len(set(evaluated)) == 205
