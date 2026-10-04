import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(
  new URL('../src/modules/system/api/system.api.js', import.meta.url),
  'utf8'
).replace(/\r\n/g, '\n')

test('permission-only role saves preserve an existing CUSTOM scope target', () => {
  assert.match(source, /if \(scopeTarget !== undefined\) body\.scopeTarget = scopeTarget/)
  assert.doesNotMatch(source, /scopeTarget:\s*scopeTarget\s*\|\|\s*\{\}/)
})

function roleAssignmentClient(request) {
  const method = source.match(/async assignUserRoles\([\s\S]*?\n {2}},(?=\n\n {2}async batchDisableUsers)/)[0]
  const errorFactory = source.match(/function apiError\(error\) \{[\s\S]*?\n\}/)[0]
  return Function('request', `
    ${errorFactory}
    const ok = (data) => ({ code: 0, data, message: 'ok' })
    return ({ ${method} }).assignUserRoles
  `)(request)
}

test('role assignment sends the explicitly read version and preserves string scope identifiers', async () => {
  let sent
  const assign = roleAssignmentClient(async (path, options) => {
    sent = { path, ...options }
    return { version: 5 }
  })
  const assignments = [{ roleCode: 'COLLEGE_ADMIN', scopeType: 'COLLEGE', scopeIds: ['9007199254740993'] }]
  const result = await assign('9007199254740995', ['COLLEGE_ADMIN'], assignments, { expectedVersion: 4 })
  assert.equal(sent.path, '/system/users/9007199254740995/roles')
  assert.equal(sent.method, 'PUT')
  assert.deepEqual(sent.body, { roleCodes: ['COLLEGE_ADMIN'], roleAssignments: assignments, expectedVersion: 4 })
  assert.equal(result.data.version, 5)
})

test('role assignment keeps legacy callers unchanged when no explicit version was supplied', async () => {
  let body
  const assign = roleAssignmentClient(async (_path, options) => { body = options.body; return {} })
  await assign('12', ['COLLEGE_ADMIN'], [])
  assert.equal(Object.hasOwn(body, 'expectedVersion'), false)
})

test('role assignment preserves server conflict metadata for the editing page', async () => {
  const assign = roleAssignmentClient(async () => {
    throw Object.assign(new Error('账号已更新，请重新核对'), { code: 409001, bizCode: 'DATA_CONFLICT', httpStatus: 409 })
  })
  const result = await assign('12', ['COLLEGE_ADMIN'], [], { expectedVersion: 4 })
  assert.equal(result.code, 409001)
  assert.equal(result.bizCode, 'DATA_CONFLICT')
  assert.equal(result.httpStatus, 409)
  assert.equal(result.data, null)
})
