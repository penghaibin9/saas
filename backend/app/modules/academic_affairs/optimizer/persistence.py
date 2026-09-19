"""MySQL-only durable proposal repository. No engine is created at import time.
The host supplies a tenant-routed session factory. No official timetable writes.
"""
from __future__ import annotations
from datetime import datetime,timedelta
from hashlib import sha256
import json
import zlib
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (MetaData,Table,Column,BigInteger,Integer,String,DateTime,Boolean,JSON,UniqueConstraint,Index,select,update,and_,or_,text)
from sqlalchemy.dialects.mysql import MEDIUMBLOB,insert as mysql_insert
from .contracts import Snapshot,InputError,canonical,fingerprint,numeric_id

from .schema import metadata,snapshots,jobs

TERMINAL={'SUCCEEDED','INFEASIBLE','UNKNOWN','REJECTED','STALE','CANCELLED','FAILED','APPLIED'}
MAX_PAYLOAD_BYTES=32*1024*1024

def pack_snapshot(snapshot):
    payload=canonical(snapshot.raw).encode('utf-8')
    if sha256(payload).hexdigest()!=snapshot.input_hash:raise InputError('SNAPSHOT_MUTATED','rebuild before submit')
    if len(payload)>MAX_PAYLOAD_BYTES:raise InputError('SNAPSHOT_TOO_LARGE',str(len(payload)))
    compressed=zlib.compress(payload,6)
    if len(compressed)>=16*1024*1024:raise InputError('SNAPSHOT_TOO_LARGE','MEDIUMBLOB')
    return payload,compressed

def unpack_snapshot(row):
    size=int(row['payload_bytes'])
    if not 0<size<=MAX_PAYLOAD_BYTES:raise InputError('SNAPSHOT_SIZE_INVALID',str(size))
    dec=zlib.decompressobj();payload=dec.decompress(row['payload_zlib'],MAX_PAYLOAD_BYTES+1)
    if len(payload)!=size or not dec.eof or dec.unconsumed_tail or dec.unused_data:
        raise InputError('SNAPSHOT_CORRUPT','size/compression mismatch')
    if sha256(payload).hexdigest()!=row['input_hash']:raise InputError('SNAPSHOT_HASH_MISMATCH','stored snapshot')
    snapshot=Snapshot.parse(json.loads(payload))
    if (int(snapshot.tenant),int(snapshot.term),int(snapshot.batch))!=(row['tenant_id'],row['term_id'],row['batch_id']):
        raise InputError('SNAPSHOT_SCOPE_MISMATCH','stored scope')
    return snapshot

def job_dto(row):
    return {'jobId':str(row['id']),'tenantId':str(row['tenant_id']),'batchId':str(row['batch_id']),
        'state':row['state'],'version':row['version'],'attempts':row['attempts'],
        'cancelRequested':row['cancel_requested'],'result':row['result_json'],'errorCode':row['last_error'],
        'createdAt':row['created_at'].isoformat(),'updatedAt':row['updated_at'].isoformat()}

class Repository:
    def __init__(self,session_factory,*,tenant_id,audit_hook=None,admission_hook=None):
        self.session_factory=session_factory
        self.tenant_id=numeric_id(tenant_id,'repository.tenantId')
        self.audit_hook=audit_hook
        self.admission_hook=admission_hook
    def _require_audit(self):
        if not callable(self.audit_hook):raise InputError('AUDIT_HOOK_REQUIRED','Candidate writes require same-transaction audit')
    def _audit(self,db,action,job_id,detail):
        self._require_audit()
        self.audit_hook(db,action,str(job_id),detail)
    def _scope(self,value):
        if numeric_id(value,'tenantId')!=self.tenant_id:
            raise InputError('TENANT_SCOPE_MISMATCH','Repository is bound to another tenant')
    @staticmethod
    def _guard(db):
        if db.get_bind().dialect.name!='mysql':raise RuntimeError('Optimizer repository requires real MySQL; SQLite is not accepted')
    @staticmethod
    def _now(db):return db.scalar(select(__import__('sqlalchemy').func.utc_timestamp(6)))
    def enqueue_verified(self,snapshot:Snapshot,*,actor:str,idempotency_key:str,options:dict,reason:str,actor_context:dict):
        """Internal trusted-builder entry. Never expose arbitrary client snapshots as school truth."""
        self._scope(snapshot.tenant)
        self._require_audit()
        if not callable(self.admission_hook):raise InputError('ADMISSION_HOOK_REQUIRED','Authoritative batch lock and queue limit are mandatory')
        if not isinstance(reason,str) or not 5<=len(reason.strip())<=500:
            raise InputError('REASON_REQUIRED','5..500 characters')
        reason=reason.strip()
        required={'userId','tenantId','roleCode'}
        allowed=required|{'activeContextId','roleId'}
        if not isinstance(actor_context,dict) or not required.issubset(actor_context) or set(actor_context)-allowed:
            raise InputError('ACTOR_CONTEXT_REQUIRED','Verified identity reference only; no token or permission snapshot')
        if actor_context['userId']!=actor or actor_context['tenantId']!=snapshot.tenant or not actor_context['roleCode']:
            raise InputError('ACTOR_CONTEXT_MISMATCH','Creator identity does not match current scope')
        if any(not isinstance(v,str) or len(v)>160 for v in actor_context.values()):
            raise InputError('ACTOR_CONTEXT_INVALID','Identity reference fields must be bounded strings')
        if not isinstance(actor,str) or not actor or len(actor)>128:raise InputError('ACTOR_REQUIRED','actor')
        if not isinstance(idempotency_key,str) or not 8<=len(idempotency_key)<=64:raise InputError('INVALID_IDEMPOTENCY_KEY','8..64 chars')
        from .options import normalize_options
        options=normalize_options(options,snapshot)
        payload,compressed=pack_snapshot(snapshot)
        request_hash=fingerprint({'inputHash':snapshot.input_hash,'options':options,'actor':actor,'reason':reason,'actorContext':actor_context})
        tid,bid,term=int(snapshot.tenant),int(snapshot.batch),int(snapshot.term)
        with self.session_factory() as db:
            self._guard(db);now=self._now(db)
            self.admission_hook(db,snapshot)  # Lock order: authoritative Batch -> Job -> Snapshot.
            duplicate=db.execute(select(jobs).where(jobs.c.tenant_id==tid,jobs.c.batch_id==bid,
                jobs.c.idempotency_key==idempotency_key).with_for_update()).mappings().first()
            if duplicate:
                if duplicate['request_hash']!=request_hash:raise InputError('IDEMPOTENCY_CONFLICT','Different input for existing key')
                return job_dto(duplicate)
            from sqlalchemy import func
            pending=db.scalar(select(func.count()).select_from(jobs).where(jobs.c.tenant_id==tid,
                jobs.c.batch_id==bid,jobs.c.state.in_(['QUEUED','RUNNING'])))
            if pending>=2:raise InputError('QUEUE_BUSY','At most two pending candidates per batch')
            stmt=mysql_insert(snapshots).values(tenant_id=tid,term_id=term,batch_id=bid,input_hash=snapshot.input_hash,
                source_revision=snapshot.revision,payload_zlib=compressed,payload_bytes=len(payload),created_at=now)
            db.execute(stmt.on_duplicate_key_update(input_hash=stmt.inserted.input_hash))
            snap=db.execute(select(snapshots).where(snapshots.c.tenant_id==tid,snapshots.c.input_hash==snapshot.input_hash)).mappings().one()
            unpack_snapshot(snap)
            values=dict(tenant_id=tid,term_id=term,batch_id=bid,snapshot_id=snap['id'],requested_by=actor,requested_reason=reason,actor_context_json=actor_context,
                idempotency_key=idempotency_key,request_hash=request_hash,options_json=options,state='QUEUED',version=0,
                attempts=0,cancel_requested=False,created_at=now,updated_at=now)
            created=False
            try:
                with db.begin_nested():
                    db.execute(jobs.insert().values(**values))
                created=True
            except IntegrityError:
                # Only the known idempotency row can turn a uniqueness conflict into a receipt.
                duplicate=db.execute(select(jobs.c.id).where(jobs.c.tenant_id==tid,jobs.c.batch_id==bid,
                    jobs.c.idempotency_key==idempotency_key).with_for_update()).scalar_one_or_none()
                if duplicate is None:raise
            row=db.execute(select(jobs).where(jobs.c.tenant_id==tid,jobs.c.batch_id==bid,jobs.c.idempotency_key==idempotency_key).with_for_update()).mappings().one()
            if row['request_hash']!=request_hash:raise InputError('IDEMPOTENCY_CONFLICT','same key, different input/options/actor')
            if created:self._audit(db,'CANDIDATE_ENQUEUE',row['id'],{'inputHash':snapshot.input_hash,'reason':reason})
            db.commit();return job_dto(row)
    def find_by_key(self,tenant_id,batch_id,idempotency_key):
        self._scope(tenant_id)
        numeric_id(str(batch_id),'batchId')
        if not isinstance(idempotency_key,str) or not 8<=len(idempotency_key)<=64:
            raise InputError('INVALID_IDEMPOTENCY_KEY','lookup')
        with self.session_factory() as db:
            self._guard(db)
            row=db.execute(select(jobs).where(jobs.c.tenant_id==int(tenant_id),
                jobs.c.batch_id==int(batch_id),jobs.c.idempotency_key==idempotency_key)).mappings().first()
            return job_dto(row) if row else None

    def get(self,tenant_id,job_id):
        self._scope(tenant_id)
        numeric_id(job_id,'jobId')
        with self.session_factory() as db:
            self._guard(db)
            row=db.execute(select(jobs).where(jobs.c.tenant_id==int(tenant_id),jobs.c.id==int(job_id))).mappings().first()
            if not row:raise InputError('JOB_NOT_FOUND','unknown job in current tenant')
            return job_dto(row)
    def cancel(self,tenant_id,job_id,expected_version):
        self._scope(tenant_id)
        numeric_id(job_id,'jobId')
        self._require_audit()
        if type(expected_version) is not int or expected_version<0:raise InputError('VERSION_REQUIRED','cancel')
        with self.session_factory() as db:
            self._guard(db);now=self._now(db)
            row=db.execute(select(jobs).where(jobs.c.tenant_id==int(tenant_id),jobs.c.id==int(job_id)).with_for_update()).mappings().first()
            if not row:raise InputError('JOB_NOT_FOUND','cancel')
            if row['version']!=expected_version:raise InputError('VERSION_CONFLICT','cancel')
            if row['state'] in TERMINAL:return job_dto(row)
            db.execute(update(jobs).where(jobs.c.id==row['id'],jobs.c.tenant_id==int(tenant_id)).values(
                state='CANCELLED',cancel_requested=True,lease_token=None,lease_until=None,
                version=row['version']+1,updated_at=now,completed_at=now))
            self._audit(db,'CANDIDATE_CANCEL',job_id,{'beforeVersion':row['version']})
            db.commit()
        return self.get(tenant_id,job_id)
    def claim(self,tenant_id,*,lease_seconds=30):
        self._scope(tenant_id)
        self._require_audit()
        if type(lease_seconds) is not int or not 10<=lease_seconds<=120:raise InputError('LEASE_INVALID','10..120 seconds')
        with self.session_factory() as db:
            self._guard(db);now=self._now(db)
            row=db.execute(select(jobs).where(jobs.c.tenant_id==int(tenant_id),jobs.c.cancel_requested.is_(False),
                or_(jobs.c.state=='QUEUED',and_(jobs.c.state=='RUNNING',jobs.c.lease_until<now)))
                .order_by(jobs.c.id).limit(1).with_for_update(skip_locked=True)).mappings().first()
            if not row:return None
            token=str(uuid4());row=dict(row)
            if row['attempts']>=3:
                db.execute(update(jobs).where(jobs.c.id==row['id'],jobs.c.tenant_id==int(tenant_id)).values(
                    state='FAILED',last_error='RETRY_BUDGET',lease_token=None,lease_until=None,
                    updated_at=now,version=row['version']+1,completed_at=now))
                self._audit(db,'CANDIDATE_RETRY_EXHAUSTED',row['id'],{'attempts':row['attempts']})
                db.commit();return None
            db.execute(update(jobs).where(jobs.c.id==row['id'],jobs.c.tenant_id==int(tenant_id)).values(state='RUNNING',
                lease_token=token,lease_until=now+timedelta(seconds=lease_seconds),attempts=row['attempts']+1,version=row['version']+1,updated_at=now))
            snap=db.execute(select(snapshots).where(snapshots.c.id==row['snapshot_id'],snapshots.c.tenant_id==int(tenant_id))).mappings().one()
            try:
                data=unpack_snapshot(snap)
            except InputError as error:
                db.execute(update(jobs).where(jobs.c.id==row['id'],jobs.c.tenant_id==int(tenant_id)).values(
                    state='FAILED',last_error=error.code,lease_token=None,lease_until=None,
                    version=row['version']+1,updated_at=now,completed_at=now))
                self._audit(db,'CANDIDATE_CORRUPT',row['id'],{'code':error.code})
                db.commit();return None
            self._audit(db,'CANDIDATE_CLAIM',row['id'],{'attempt':row['attempts']+1})
            db.commit()
            return {'jobId':str(row['id']),'leaseToken':token,'snapshot':data,'options':row['options_json'],
                    'requestedBy':row['requested_by'],'actorContext':row['actor_context_json'],'batchId':str(row['batch_id']),'tenantId':str(row['tenant_id'])}
    def heartbeat(self,tenant_id,job_id,token,*,lease_seconds=30):
        self._scope(tenant_id)
        numeric_id(job_id,'jobId')
        if type(lease_seconds) is not int or not 10<=lease_seconds<=120:raise InputError('LEASE_INVALID','heartbeat')
        with self.session_factory() as db:
            self._guard(db);now=self._now(db)
            count=db.execute(update(jobs).where(jobs.c.tenant_id==int(tenant_id),jobs.c.id==int(job_id),
                jobs.c.state=='RUNNING',jobs.c.lease_token==token,jobs.c.lease_until>=now,jobs.c.cancel_requested.is_(False))
                .values(lease_until=now+timedelta(seconds=lease_seconds),updated_at=now)).rowcount
            db.commit();return count==1
    def finish(self,tenant_id,job_id,token,result,*,source_current):
        self._scope(tenant_id)
        numeric_id(job_id,'jobId')
        self._require_audit()
        state={'FEASIBLE':'SUCCEEDED','INFEASIBLE':'INFEASIBLE','CANCELLED':'CANCELLED','UNKNOWN':'UNKNOWN',
               'NO_SOLUTION_IN_RESTRICTED_DOMAIN':'UNKNOWN','INPUT_CONFLICT':'REJECTED','REJECTED':'REJECTED','STALE':'STALE'}.get(result.get('status'),'FAILED')
        if not source_current:state='STALE'
        with self.session_factory() as db:
            self._guard(db);now=self._now(db)
            row=db.execute(select(jobs).where(jobs.c.tenant_id==int(tenant_id),jobs.c.id==int(job_id)).with_for_update()).mappings().first()
            if not row or row['state']!='RUNNING' or row['lease_token']!=token or row['lease_until']<now or row['cancel_requested']:
                return False
            snap=db.execute(select(snapshots).where(snapshots.c.id==row['snapshot_id'],snapshots.c.tenant_id==int(tenant_id))).mappings().one()
            trusted=unpack_snapshot(snap)
            if result.get('inputHash')!=trusted.input_hash:raise InputError('RESULT_INPUT_MISMATCH','finish')
            if result.get('status')=='FEASIBLE':
                from .validation import validate_solution
                errors=validate_solution(trusted,result.get('choices',{}))
                if errors:raise InputError('RESULT_VALIDATION_FAILED',canonical([e.as_dict() for e in errors])[:500])
            db.execute(update(jobs).where(jobs.c.id==row['id'],jobs.c.tenant_id==int(tenant_id)).values(state=state,
                result_json=result,lease_token=None,lease_until=None,completed_at=now,updated_at=now,version=row['version']+1))
            self._audit(db,'CANDIDATE_FINISH',row['id'],{'state':state,'inputHash':trusted.input_hash})
            db.commit();return True

def run_one(repository,tenant_id,*,source_validator,execution_allowed,actor_allowed):
    """One bounded job; the host MUST supply trusted tenant/permission/read-version checks."""
    from .supervisor import solve_supervised as solve
    from .options import normalize_options
    import threading
    from contextvars import copy_context
    if execution_allowed() is not True:
        return None
    claimed=repository.claim(tenant_id)
    if not claimed:
        return None
    job_id,token=claimed['jobId'],claimed['leaseToken']
    snapshot=claimed['snapshot']
    try:
        creator_valid=actor_allowed(claimed) is True
    except Exception:
        creator_valid=False
    if not creator_valid:
        result={'status':'REJECTED','inputHash':snapshot.input_hash,'choices':{},
                'diagnostics':[{'code':'CREATOR_AUTHORIZATION_LOST'}],'publishable':False}
        repository.finish(tenant_id,job_id,token,result,source_current=True)
        return {'jobId':job_id,'state':repository.get(tenant_id,job_id)['state']}
    stopped=threading.Event(); stop_heartbeat=threading.Event()
    def keepalive():
        while not stop_heartbeat.wait(5):
            try:
                if execution_allowed() is not True or actor_allowed(claimed) is not True or not repository.heartbeat(tenant_id,job_id,token):
                    stopped.set(); return
            except Exception:
                stopped.set(); return
    context=copy_context()
    thread=threading.Thread(target=lambda:context.run(keepalive),daemon=True)
    thread.start()
    try:
        try:
            options=normalize_options(claimed['options'],snapshot)
            if source_validator(snapshot) is not True:
                result={'status':'STALE','inputHash':snapshot.input_hash,'choices':{}}
            else:
                result=solve(snapshot,cancelled=stopped.is_set,**options)
            current=execution_allowed() is True and actor_allowed(claimed) is True and source_validator(snapshot) is True
        except InputError as exc:
            result={'status':'REJECTED','inputHash':snapshot.input_hash,'choices':{},
                    'diagnostics':[{'code':exc.code}], 'publishable':False}
            current=True  # Input rejection is not falsely attributed to source changes.
        except Exception as exc:
            result={'status':'FAILED','inputHash':snapshot.input_hash,'choices':{},
                    'diagnostics':[{'code':'WORKER_ERROR','type':type(exc).__name__}],
                    'publishable':False}
            current=True  # No exception string, SQL, credentials or identifiers are exported.
        repository.finish(tenant_id,job_id,token,result,source_current=current)
        return {'jobId':job_id,'state':repository.get(tenant_id,job_id)['state']}
    finally:
        stop_heartbeat.set(); thread.join(timeout=2)
