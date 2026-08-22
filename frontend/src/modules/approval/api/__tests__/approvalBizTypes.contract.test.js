/**
 * TP-A10：审批业务类型字典改由服务端 GET /approvals/biz-types 权威下发，前端不再自己
 * 拷贝一份完整枚举。见 approval.api.js::ensureBizTypeOptions() 的注释。
 *
 * 运行（在 frontend/ 目录）：
 *   node --test src/modules/approval/api/__tests__/approvalBizTypes.contract.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL, fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(__dirname, '../../../../..')
const mockClientUrl = pathToFileURL(path.join(__dirname, 'mock-http-client.mjs')).href

register('./approvalBizTypes.contract.hooks.mjs', import.meta.url, {
  data: { frontendRoot, mockClientUrl }
})

globalThis.__APPROVAL_BIZ_TYPE_CALLS__ = []
globalThis.__APPROVAL_BIZ_TYPE_STATE__ = {
  bizTypes: [
    { value: 'LEAVE', label: '请假审批' },
    { value: 'AID', label: '困难认定' }
  ]
}

const { approvalApi } = await import('../approval.api.js')

test('getContext() 从服务端拿到 filterOptions.bizTypes，不是前端本地静态清单', async () => {
  const res = await approvalApi.getContext()
  assert.equal(res.code, 0)
  assert.deepEqual(res.data.filterOptions.bizTypes, [
    { value: 'LEAVE', label: '请假审批' },
    { value: 'AID', label: '困难认定' }
  ])
  assert.ok(globalThis.__APPROVAL_BIZ_TYPE_CALLS__.includes('/approvals/biz-types'))
})

test('字典只在首次成功后拉一次，第二次 getContext() 不重复请求', async () => {
  globalThis.__APPROVAL_BIZ_TYPE_CALLS__.length = 0
  await approvalApi.getContext()
  const bizTypeCalls = globalThis.__APPROVAL_BIZ_TYPE_CALLS__.filter((p) => p === '/approvals/biz-types')
  assert.equal(bizTypeCalls.length, 0, '第一个测试已经加载成功过，这里不应再打一次')
})
