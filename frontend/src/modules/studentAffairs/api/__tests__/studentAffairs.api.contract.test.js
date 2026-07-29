/**
 * 学工 API 客户端契约：B 兼容层与主客户端 endpoint/method/version 一致；className 不回退 classId。
 * 运行（在 frontend/ 目录）：
 *   node --test src/modules/studentAffairs/api/__tests__/studentAffairs.api.contract.test.js
 *   npm test -- --test-name-pattern="学工 API"
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL, fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '../../../../..')
const calls = []

const mockClientUrl = pathToFileURL(path.join(__dirname, 'mock-http-client.mjs')).href
const mockConfigUrl = pathToFileURL(path.join(__dirname, 'mock-http-config.mjs')).href

register('./studentAffairs.api.contract.hooks.mjs', import.meta.url, {
  data: { frontendRoot, mockClientUrl, mockConfigUrl }
})

// 将 calls 暴露给 mock 模块（同目录 mock 文件读取 globalThis）
globalThis.__SA_API_CONTRACT_CALLS__ = calls

const { studentAffairsApi: core } = await import('../studentAffairs.api.js')
const { studentAffairsApi: compat, normalizeStudent } = await import('../studentAffairsB.api.js')

function lastCall() {
  assert.ok(calls.length, 'expected at least one request')
  return calls[calls.length - 1]
}

function clearCalls() {
  calls.length = 0
}

test('normalizeStudent 禁止 classId 冒充 className', () => {
  const withIdOnly = normalizeStudent({ id: 1, studentNo: 'S1', realName: '张三', classId: 99 })
  assert.equal(withIdOnly.className, '')
  assert.equal(withIdOnly.classId, '99')

  const named = normalizeStudent({ id: 2, className: '计应2301', class_id: 7 })
  assert.equal(named.className, '计应2301')
  assert.equal(named.classId, '7')

  const empty = normalizeStudent({ id: 3 })
  assert.equal(empty.className, '未分班')
})

test('toErr / callStrict 透出 bizCode（版本冲突）', async () => {
  clearCalls()
  globalThis.__SA_API_CONTRACT_THROW__ = {
    biz: true,
    code: 409001,
    bizCode: 'APPROVAL_VERSION_CONFLICT',
    message: '版本冲突'
  }
  const res = await core.assignRisk('1', 'u1', 3)
  globalThis.__SA_API_CONTRACT_THROW__ = null
  assert.equal(res.code, 409001)
  assert.equal(res.bizCode, 'APPROVAL_VERSION_CONFLICT')
})

test('B unwrap 把 bizCode 挂到 thrown Error', async () => {
  clearCalls()
  globalThis.__SA_API_CONTRACT_THROW__ = {
    biz: true,
    code: 409001,
    bizCode: 'APPROVAL_VERSION_CONFLICT',
    message: '版本冲突'
  }
  await assert.rejects(
    () => compat.assignRisk('1', 'u1', 3),
    (err) => err.bizCode === 'APPROVAL_VERSION_CONFLICT' && err.biz === true
  )
  globalThis.__SA_API_CONTRACT_THROW__ = null
})

const WRITE_CASES = [
  {
    name: 'assignRisk',
    runA: () => core.assignRisk('10', 'owner-1', 5),
    runB: () => compat.assignRisk('10', 'owner-1', 5),
    expect: { method: 'POST', path: '/student-affairs/risk/records/10/assign', version: 5 }
  },
  {
    name: 'processRisk',
    runA: () => core.processRisk('10', '处置内容不少于五字', 6),
    runB: () => compat.processRisk('10', '处置内容不少于五字', 6),
    expect: { method: 'POST', path: '/student-affairs/risk/records/10/process', version: 6 }
  },
  {
    name: 'approveLeave',
    runA: () => core.approveLeave('20', '同意', 2),
    runB: () => compat.approveLeave('20', '同意', 2),
    expect: { method: 'POST', path: '/student-affairs/leave/20/approve', version: 2 }
  },
  {
    name: 'followMentalReferral',
    runA: () => core.followMentalReferral('30', '回访记录不少于五字', 4),
    runB: () => compat.followMentalReferral('30', '回访记录不少于五字', 4),
    expect: { method: 'POST', path: '/student-affairs/mental/referrals/30/follow', version: 4 }
  },
  {
    name: 'reviewDormTransfer',
    runA: () => core.reviewDormTransfer('40', 'APPROVE', '', 1),
    runB: () => compat.reviewDormTransfer('40', 'APPROVE', '', 1),
    expect: { method: 'POST', path: '/student-affairs/dorm/transfers/40/review', version: 1 }
  },
  {
    name: 'closeMentalReferral',
    runA: () => core.closeMentalReferral('31', '关闭结论不少于五字', 8),
    runB: () => compat.closeMentalReferral('31', '关闭结论不少于五字', 8),
    expect: { method: 'POST', path: '/student-affairs/mental/referrals/31/close', version: 8 }
  }
]

for (const c of WRITE_CASES) {
  test(`写方法 ${c.name}：A/B endpoint+method+version 一致`, async () => {
    clearCalls()
    await c.runA()
    const aCall = { ...lastCall() }
    clearCalls()
    await c.runB()
    const bCall = { ...lastCall() }

    assert.equal(aCall.method, c.expect.method)
    assert.equal(aCall.path, c.expect.path)
    assert.equal(aCall.body?.version, c.expect.version)

    assert.equal(bCall.method, aCall.method)
    assert.equal(bCall.path, aCall.path)
    assert.deepEqual(bCall.body, aCall.body)
  })
}

test('getRisks 传递 studentId', async () => {
  clearCalls()
  await core.getRisks({ studentId: '99', page: 1, pageSize: 20 })
  const call = lastCall()
  assert.equal(call.path, '/student-affairs/risk/records')
  assert.equal(call.params.studentId, '99')

  clearCalls()
  await compat.listRiskRecords({ studentId: '99', page: 1, pageSize: 20 })
  assert.equal(lastCall().params.studentId, '99')
})
