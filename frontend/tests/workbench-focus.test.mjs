import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
const source = readFileSync(new URL('../src/modules/workbench/views/WorkbenchView.vue', import.meta.url), 'utf8')
const recent = new Function(source.split('    recentTodos() {')[1].split('    currentTaskTotal() {')[0].replace(/},\s*$/, ''))
const total = new Function(source.split('    currentTaskTotal() {')[1].split('    contextItems() {')[0].replace(/},\s*$/, ''))
test('approval preview shows the actual workflow task even when unified business todos are empty', () => {
  const ctx = { taskSource: 'approval', approvals: [{ taskId: '13', title: '资助审批', applicantName: '学生甲', deadline: '', bizTypeLabel: '奖助评定' }], todos: [], summary: { pending: 1 }, todoTotal: 0 }
  const rows = recent.call(ctx)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].typedRouteTarget, '/admin/approval/todos/13')
  assert.equal(rows[0].focusMode, 'DETAIL')
  assert.equal(total.call(ctx), 1)
  ctx.taskSource = 'business'
  assert.deepEqual(recent.call(ctx), [])
  assert.equal(total.call(ctx), 0)
})
test('business preview retains server routing and its own total without mixing workflow tasks', () => {
  const todos = Array.from({ length: 10 }, (_, i) => ({ todoId: i, typedRouteTarget: '/business/' + i }))
  const ctx = { taskSource: 'business', todos, approvals: [], todoTotal: 10, summary: { pending: 0 } }
  assert.deepEqual(recent.call(ctx), todos)
  assert.equal(total.call(ctx), 10)
  assert.equal(todos.length, 10)
})

const more = new (Object.getPrototypeOf(async function(){}).constructor)('fetchTodoList', source.split('    async loadMoreBusiness() {')[1].split('    toggleEditing() {')[0].replace(/},\s*$/, ''))
test('business queue can read beyond the preview and retains data on retry',async()=>{
 const vm={businessMoreBusy:false,loading:false,todos:[{todoId:'1'}],todoTotal:3,businessPage:1,businessEpoch:0}
 await more.call(vm,async()=>{throw new Error('offline')});assert.equal(vm.businessPage,1);assert.equal(vm.todos.length,1)
 await more.call(vm,async q=>{assert.equal(q.page,2);return {items:[{todoId:'1'},{todoId:'2'},{todoId:'3'}],total:3}})
 assert.equal(vm.todos.length,3);assert.equal(vm.businessPage,2);assert.equal(vm.businessMoreError,'')
})
