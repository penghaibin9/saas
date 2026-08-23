/**
 * TP-A07：批量审批必须逐条携带业务事实 sourceVersion；TRANSFER 不需要业务事实快照。
 *
 * 运行（在 frontend/ 目录）：
 *   node --test src/modules/approval/api/__tests__/approvalBatchSourceVersion.contract.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL, fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '../../../../..')
const mockClientUrl = pathToFileURL(path.join(__dirname, 'mock-batch-source-version-client.mjs')).href

register('./approvalBizTypes.contract.hooks.mjs', import.meta.url, {
  data: { frontendRoot, mockClientUrl }
})

globalThis.__APPROVAL_BATCH_VERSION_CALLS__ = []
globalThis.__APPROVAL_BATCH_VERSION_STATE__ = {
  details: {
    '11': {
      taskId: '11', instanceId: '101', sourceBizType: 'LEAVE', status: 'PENDING', version: 2,
      businessContext: { sourceBizType: 'LEAVE', sourceVersion: 7, versionGuardRequired: true, completeness: 'FULL' }
    },
    '12': {
      taskId: '12', instanceId: '102', sourceBizType: 'AID', status: 'PENDING', version: 4,
      businessContext: { sourceBizType: 'AID', sourceVersion: 9, versionGuardRequired: true, completeness: 'FULL' }
    },
    '13': {
      taskId: '13', instanceId: '103', sourceBizType: 'COMPANY_CHANGE', status: 'PENDING', version: 1,
      businessContext: { sourceBizType: 'COMPANY_CHANGE', sourceVersion: null, versionGuardRequired: false, completeness: 'UNSUPPORTED' }
    }
  }
}

const { approvalApi } = await import('../approval.api.js')

function resetCalls() {
  globalThis.__APPROVAL_BATCH_VERSION_CALLS__.length = 0
  globalThis.__APPROVAL_BATCH_VERSION_STATE__.lastBatchBody = null
}

test('batchApprove 对列表选择逐条预检详情并携带 expectedSourceVersion', async () => {
  resetCalls()
  const res = await approvalApi.batchApprove([
    { taskId: '11', version: 2 },
    { taskId: '12', version: 4 },
    { taskId: '13', version: 1 }
  ])
  assert.equal(res.code, 0)

  const detailPaths = globalThis.__APPROVAL_BATCH_VERSION_CALLS__
    .filter((x) => x.path.startsWith('/approvals/tasks/'))
    .map((x) => x.path)
    .sort()
  assert.deepEqual(detailPaths, ['/approvals/tasks/11', '/approvals/tasks/12', '/approvals/tasks/13'])

  assert.deepEqual(globalThis.__APPROVAL_BATCH_VERSION_STATE__.lastBatchBody.items, [
    { taskId: '11', version: 2, expectedSourceVersion: 7 },
    { taskId: '12', version: 4, expectedSourceVersion: 9 },
    { taskId: '13', version: 1 }
  ])
})

test('已看过详情时 batchApprove 保留用户看到的旧 sourceVersion，不在动作前偷偷刷新', async () => {
  resetCalls()
  const detail = await approvalApi.getApprovalDetail('11')
  assert.equal(detail.code, 0)

  // 模拟用户看完详情后，业务事实又被其它窗口修改到 version=8。
  globalThis.__APPROVAL_BATCH_VERSION_STATE__.details['11'].businessContext.sourceVersion = 8
  resetCalls()
  const res = await approvalApi.batchApprove([{ taskId: '11', version: 2 }])
  assert.equal(res.code, 0)

  const detailCalls = globalThis.__APPROVAL_BATCH_VERSION_CALLS__
    .filter((x) => x.path === '/approvals/tasks/11')
  assert.equal(detailCalls.length, 0, '已有用户实际看过的快照时，不应动作前自动刷新成当前版本')
  assert.equal(globalThis.__APPROVAL_BATCH_VERSION_STATE__.lastBatchBody.items[0].expectedSourceVersion, 7)
})

test('batchTransfer 只使用 task 乐观锁，不额外请求业务 Context sourceVersion', async () => {
  resetCalls()
  const res = await approvalApi.batchTransfer(
    [{ taskId: '12', version: 4 }],
    { targetUserId: '9001', note: '转交代办' }
  )
  assert.equal(res.code, 0)
  assert.equal(
    globalThis.__APPROVAL_BATCH_VERSION_CALLS__.filter((x) => x.path === '/approvals/tasks/12').length,
    0
  )
  assert.deepEqual(globalThis.__APPROVAL_BATCH_VERSION_STATE__.lastBatchBody.items, [
    { taskId: '12', version: 4 }
  ])
})
