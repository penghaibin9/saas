from datetime import datetime, timedelta
from types import SimpleNamespace
from sqlalchemy import select
from test_affairs_aid import BASE, TID, _seed, _hdr, _open_batch


def test_publicity_window_uses_exact_server_deadline_and_requires_batch_context():
    from app.services.affairs_aid_workspace import publicity_window
    start = datetime(2026,9,1,10)
    row = SimpleNamespace(status='PUBLICITY',publicity_at=start)
    batch = SimpleNamespace(publicity_days=3)
    assert not publicity_window(row,batch,now=start+timedelta(days=3,microseconds=-1))['publicityReady']
    assert publicity_window(row,batch,now=start+timedelta(days=3))['publicityReady']
    assert publicity_window(row,None,now=start+timedelta(days=10))['publicityEnd'] is None
    row.status='APPROVED'
    assert not publicity_window(row,batch,now=start+timedelta(days=10))['publicityReady']


def test_publicity_scan_does_not_starve_due_records_behind_waiting_or_contested_rows(client,db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch, AidObjection
    ids=_seed(db_mode); headers=_hdr(client,'school_admin01')
    batch=_open_batch(client,headers)
    now=datetime.utcnow()
    with get_sessionmaker()() as db:
        rows=[]
        for i in range(203):
            record_batch = AidBatch(tenant_id=TID,batch_name=f'队列期限验收{i}',year_code='2026-2027',status='OPEN',publicity_days=1)
            db.add(record_batch); db.flush()
            row=AidApply(tenant_id=TID,batch_id=record_batch.id,student_id=ids['sa'],apply_level='GENERAL',
                final_level='GENERAL',status='PUBLICITY',publicity_at=now if i<201 else now-timedelta(days=2))
            db.add(row); rows.append(row)
        db.flush()
        waiting,contested,due=rows[0].id,rows[-2].id,rows[-1].id
        db.add(AidObjection(tenant_id=TID,apply_id=contested,student_id=ids['sa'],status='SUBMITTED',reason='隔离验收公示异议'))
        db.commit()
    def detail(apply_id):
        response=client.get(f'{BASE}/aid/applications/{apply_id}',headers=headers)
        assert response.status_code==200,response.text
        return response.json()['data']
    before=detail(waiting)
    assert before['publicityReady'] is False and before['publicityEnd']
    premature=client.post(f'{BASE}/aid/applications/{waiting}/publicity-confirm',headers=headers,json={'version':before['version']})
    assert premature.status_code==409,premature.text
    page=client.get(f'{BASE}/aid/applications?status=PUBLICITY&pageSize=1',headers=headers).json()['data']['items'][0]
    assert page['applyId']==str(due) and page['publicityReady'] is True
    assert page['publicityEnd']==detail(due)['publicityEnd']
    response=client.post(f'{BASE}/aid/scan-publicity',headers=headers)
    assert response.status_code==200,response.text
    result=response.json()['data']
    assert result['count']==1 and result['skippedObjection']==1
    assert detail(due)['status']=='APPROVED'
    assert detail(contested)['status']==detail(waiting)['status']=='PUBLICITY'
    repeated=client.post(f'{BASE}/aid/scan-publicity',headers=headers)
    assert repeated.json()['data']['count']==0
