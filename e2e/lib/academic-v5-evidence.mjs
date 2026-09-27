import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'

// Only reads the dedicated V5 MySQL audit trail. The core business command must
// already have been performed in a normal browser session before this is called.
const query = String.raw`
import json, os, sys
from urllib.parse import urlsplit, unquote
import pymysql

try:
    u = urlsplit(os.environ['DATABASE_URL'])
    if (u.scheme != 'mysql+pymysql' or u.hostname != '127.0.0.1' or u.port != 3311 or u.path != '/student_lifecycle_v5_e2e'):
        raise ValueError('isolated database mismatch')
    tenant, kind, object_id, action, user_id, login_name = sys.argv[1:]
    if kind not in ('AA_TASK', 'AA_TASK_BATCH') or action not in ('ASSIGN', 'TEACHER_CONFIRM', 'COLLEGE_CONFIRM', 'ACADEMIC_APPROVE'):
        raise ValueError('audit query is outside the journey scope')
    if not tenant.isdecimal() or not object_id.isdecimal() or not user_id.isdecimal():
        raise ValueError('invalid business identity')
    conn = pymysql.connect(host='127.0.0.1', port=3311, user=unquote(u.username or ''),
        password=unquote(u.password or ''), database='student_lifecycle_v5_e2e', charset='utf8mb4', autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute('START TRANSACTION READ ONLY')
            cur.execute('SELECT real_name, login_name FROM t_user WHERE tenant_id=%s AND id=%s', (tenant, user_id))
            identity = cur.fetchone()
            if not identity or identity[1] != login_name:
                raise ValueError('account identity mismatch')
            cur.execute('SELECT id, operator, role_name, occurred_at FROM t_affairs_audit_trail '
                'WHERE tenant_id=%s AND biz_type=%s AND biz_id=%s AND action=%s ORDER BY id',
                (tenant, kind, object_id, action))
            rows = [{'id': str(r[0]), 'operator': r[1], 'role': r[2],
                'occurredAt': r[3].isoformat() if r[3] else None} for r in cur.fetchall()]
            conn.rollback()
        print(json.dumps({'operator': identity[0], 'rows': rows}, ensure_ascii=False))
    finally:
        conn.close()
except Exception:
    print('V5 isolated audit read failed', file=sys.stderr)
    sys.exit(2)
`

export function auditRows({ tenantId, bizType, bizId, action, account }) {
  const url = new URL(process.env.DATABASE_URL || '')
  assert.equal(url.protocol, 'mysql+pymysql:')
  assert.equal(url.hostname, '127.0.0.1')
  assert.equal(url.port, '3311')
  assert.equal(url.pathname, '/student_lifecycle_v5_e2e')
  assert.match(String(tenantId), /^[1-9]\d*$/)
  assert.match(String(bizId), /^[1-9]\d*$/)
  assert.match(String(account.userId), /^[1-9]\d*$/)
  assert.ok(account.loginName)
  const result = spawnSync(process.env.E2E_V5_PYTHON || 'python', ['-c', query, String(tenantId), bizType, String(bizId), action, account.userId, account.loginName], {
    encoding: 'utf8', windowsHide: true, cwd: process.cwd(), env: process.env, timeout: 15_000, maxBuffer: 256_000,
  })
  assert.equal(result.status, 0, '隔离库正式审计只读核验失败；不重放任何写动作')
  return JSON.parse(result.stdout)
}

export function assertActor(evidence, { roleCode, pendingAt }) {
  const { rows, operator } = evidence
  assert.equal(rows.length, 1, '该对象动作须有且仅有一条正式审计，不能用同状态冒充本次办理')
  assert.equal(rows[0].operator, operator, '正式审计操作者与正常角色账号不符')
  assert.equal(rows[0].role, roleCode, '正式审计角色与正常角色账号不符')
  if (pendingAt) {
    const pending = Date.parse(pendingAt)
    const occurred = Date.parse(`${rows[0].occurredAt}Z`)
    assert.ok(Number.isFinite(pending) && Number.isFinite(occurred) && occurred >= pending - 2000,
      '待恢复动作的正式审计早于本次命令，不得认作原命令成功')
  }
  return rows[0]
}
