from test_affairs_aid import BASE, TID, _seed, _hdr


def test_batch_keyword_search_precedes_paging_and_escapes_wildcards(client,db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidBatch
    _seed(db_mode); headers=_hdr(client,'school_admin01')
    with get_sessionmaker()() as db:
        target=AidBatch(tenant_id=TID,batch_name='历史专项100%认定',year_code='2021-2022',status='OPEN',publicity_days=3)
        db.add(target);db.flush();target_id=target.id
        for i in range(105): db.add(AidBatch(tenant_id=TID,batch_name=f'新批次{i}',year_code='2026-2027',status='OPEN',publicity_days=5))
        db.add(AidBatch(tenant_id=TID+99,batch_name='历史专项100%认定',year_code='2021-2022',status='OPEN',publicity_days=3))
        db.commit()
    url=f'{BASE}/aid/batches'
    first=client.get(url,headers=headers,params={'pageSize':100}).json()['data']
    assert first['total']==106 and all(x['batchId']!=str(target_id) for x in first['items'])
    for keyword in ['历史专项','2021-2022','%']:
        result=client.get(url,headers=headers,params={'keyword':keyword,'pageSize':1}).json()['data']
        assert result['total']==1 and result['items'][0]['batchId']==str(target_id)
    exact=client.get(f'{url}/{target_id}',headers=headers)
    assert exact.status_code==200 and exact.json()['data']['batchId']==str(target_id)


def test_student_batch_search_and_paging_preserve_window_and_tenant_scope(client, db_mode):
    from datetime import datetime, timedelta
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import AidBatch, Role, User, UserRole, StudentAccountLink
    from test_aid_mobile_queue import _login
    ids = _seed(db_mode)
    now = datetime.utcnow()
    with get_sessionmaker()() as db:
        role = Role(tenant_id=TID, role_code='STUDENT', role_name='学生', role_type='SYSTEM', status='ACTIVE')
        db.add(role); db.flush()
        student = User(tenant_id=TID, login_name='aid_batch_student', real_name='隔离学生', user_type='STUDENT',
            password_hash=hash_password('AidQueue-Test-2026!'), status='ACTIVE', must_change_password=False)
        db.add(student); db.flush()
        db.add(UserRole(tenant_id=TID, user_id=student.id, role_id=role.id, status='ACTIVE'))
        db.add(StudentAccountLink(tenant_id=TID, user_id=student.id, student_id=ids['sa'], link_status='ACTIVE', source='MANUAL'))
        target = AidBatch(tenant_id=TID, batch_name='历史开放专项', year_code='2021-2022', status='OPEN', publicity_days=3)
        db.add(target); db.flush(); target_id = str(target.id)
        for i in range(209):
            db.add(AidBatch(tenant_id=TID, batch_name=f'当前批次{i}', year_code='2026-2027', status='OPEN', publicity_days=3))
        for fields in [{'status':'DRAFT'}, {'status':'CLOSED'}, {'apply_start':now+timedelta(days=1)},
                       {'apply_end':now-timedelta(days=1)}, {'tenant_id':TID+99}, {'is_deleted':True}]:
            db.add(AidBatch(**dict({'tenant_id':TID,'batch_name':'不可见专项','year_code':'2026-2027','status':'OPEN','publicity_days':3}, **fields)))
        db.commit()
    for prefix, kind in [('/api/v1/portal', 'PC'), ('/api/v1/mobile', 'STUDENT_MINI')]:
        headers = _login(client, 'aid_batch_student', kind)
        url = prefix + '/affairs/aid/batches'
        first = client.get(url, headers=headers)
        assert first.status_code == 200, first.text
        data = first.json()['data']
        assert data['total'] == 210 and len(data['items']) == 20
        assert target_id not in [row['batchId'] for row in data['items']]
        last = client.get(url, headers=headers, params={'page':11,'pageSize':20}).json()['data']
        assert target_id in [row['batchId'] for row in last['items']] and len(last['items']) == 10
        for word in ['历史开放','2021-2022']:
            result = client.get(url, headers=headers, params={'keyword':word}).json()['data']
            assert result['total'] == 1 and result['items'][0]['batchId'] == target_id
        hidden = client.get(url, headers=headers, params={'keyword':'不可见'}).json()['data']
        assert hidden == {'items':[], 'total':0}
        assert client.get(url, headers=headers, params={'pageSize':201}).status_code == 400
        teacher = _hdr(client,'school_admin01')
        assert client.get(url,headers=teacher).status_code == 403
