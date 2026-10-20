import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source = fs.readFileSync(new URL('../src/services/realApi.js', import.meta.url), 'utf8')
const body = source.match(/export async function teacherWorkbenchReal\(roleKey\) \{([\s\S]*?)\n\}/)[1]
const roleSource = fs.readFileSync(new URL('../src/config/roles.config.js', import.meta.url), 'utf8')
const { roleConfigs, roleKeyFromBackendRole } = await import('data:text/javascript;base64,' + Buffer.from(roleSource).toString('base64'))
const compile = request => new Function('realRequest', 'roleConfigs', 'roleKeyFromBackendRole', `return async function(roleKey) {${body}}`)(request, roleConfigs, roleKeyFromBackendRole)

test('leave entry shows Chinese role, source and metric names while retaining navigation machine values', async () => {
  const load = compile(async path => path === '/todos/summary' ? { role: 'COUNSELOR', pending: 1 }
    : path.includes('/count') ? { byType: { LEAVE: 1 } }
    : path === '/teacher-mobile/todos' ? { items: [{ id: '7', title: '请假 · Alice', sourceModule: 'student-affairs', todoType: 'LEAVE' }] } : { list: [] })
  const page = await load('counselor')
  assert.equal(page.contextTitle, '辅导员')
  assert.equal(page.dueSoon[0].module, '学工事务')
  assert.equal(page.dueSoon[0].todoType, 'LEAVE')
  assert.equal(page.dueSoon[0].title, '请假 · Alice')
  assert.equal(page.metrics[2].label, '请假审批')
})
test('unknown workbench identifiers do not become visible fallback text', async () => {
  const load = compile(async path => path === '/todos/summary' ? { role: 'FUTURE_ROLE' }
    : path.includes('/count') ? { byType: { INTERNAL_QUEUE: 1 } }
    : path === '/teacher-mobile/todos' ? { items: [{ sourceModule: 'internal_module', todoType: 'NEW_TASK' }] } : { list: [] })
  const page = await load()
  assert.equal(page.contextTitle, '教师')
  assert.equal(page.metrics[2].label, '业务待办')
  assert.equal(page.dueSoon[0].module, '业务待办')
})
