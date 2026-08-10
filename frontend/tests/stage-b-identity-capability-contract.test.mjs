import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const gate = fs.readFileSync(new URL('../src/views/admin/student/StudentIdentityCapabilityView.vue', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/student/student.routes.js', import.meta.url), 'utf8')
const api = fs.readFileSync(new URL('../src/modules/student/api/student.api.js', import.meta.url), 'utf8')

test('Stage B B5 identity route passes through capability-state gate', () => {
  assert.match(routes, /path:\s*'identity'[\s\S]*StudentIdentityCapabilityView\.vue/)
  assert.match(gate, /studentApi\.getIdentityRecords\(\{ page: 1, pageSize: 1 \}\)/)
})

test('Stage B B5 capability fact comes from formal backend API, not browser hardcode', () => {
  assert.match(api, /async getIdentityRecords\(params = \{\}\)/)
  assert.match(api, /request\('\/students\/identity-records'/)
  assert.match(api, /capabilityStatus:\s*String\(data\?\.capabilityStatus \|\| 'ERROR'\)/)
  assert.doesNotMatch(api, /getIdentityRecords\(params = \{\}\) \{\s*return ok\(\{[\s\S]*capabilityStatus:\s*'NOT_CONFIGURED'/)
})

test('Stage B B5 distinguishes NOT_CONFIGURED EMPTY FORBIDDEN ERROR', () => {
  for (const state of ['NOT_CONFIGURED', 'EMPTY', 'FORBIDDEN', 'ERROR']) {
    assert.match(gate, new RegExp(state))
  }
  assert.match(gate, /capability === 'NOT_CONFIGURED'/)
  assert.match(gate, /Number\(data\.total \|\| 0\) === 0/)
  assert.match(gate, /status === 403 \? 'FORBIDDEN' : 'ERROR'/)
})

test('Stage B B5 only enters review workspace when capability is ready', () => {
  assert.match(gate, /StudentIdentityView v-if="state === 'READY'"/)
  assert.match(gate, /学校尚未配置第三方身份核验服务/)
  assert.match(gate, /核验服务已可用，当前暂无核验记录/)
  assert.match(gate, /当前账号无权查看身份核验记录/)
  assert.match(gate, /身份核验服务读取失败/)
})
