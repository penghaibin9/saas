import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/services/messagePresentation.js', import.meta.url), 'utf8')
const api = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
const todoCard = readFileSync(new URL('../src/components/MobileTodoCard.vue', import.meta.url), 'utf8')
const home = readFileSync(new URL('../src/pages/student/home/index.vue', import.meta.url), 'utf8')

test('消息来源枚举统一转换为中文业务文案', () => {
  assert.equal(api.messageModuleLabel('student-affairs'), '学工服务')
  assert.equal(api.messageModuleLabel('ANNOUNCEMENT'), '通知公告')
  assert.equal(api.messageModuleLabel('TODO_NOTICE'), '待办提醒')
  assert.equal(api.messageModuleLabel('岗位实习'), '岗位实习')
})

test('未知消息来源不回显英文内部枚举，列表和紧急消息都走同一展示层', () => {
  assert.equal(api.messageModuleLabel('future_internal_module'), '消息通知')
  const page = api.presentMessagePage({
    list: [{ module: 'ANNOUNCEMENT' }],
    items: [{ module: 'academic-affairs' }],
    groups: { todo: [{ module: 'student-affairs' }] },
    emergencyPending: [{ module: 'EMERGENCY' }]
  })
  assert.equal(page.list[0].module, '通知公告')
  assert.equal(page.items[0].module, '教务服务')
  assert.equal(page.groups.todo[0].module, '学工服务')
  assert.equal(page.emergencyPending[0].module, '紧急通知')
})

test('待办卡和学生首页复用同一中文来源展示层', () => {
  assert.match(todoCard, /import \{ messageModuleLabel \} from '@\/services\/messagePresentation'/)
  assert.match(todoCard, /moduleLabel\(\) \{ return this\.sourceModule \? messageModuleLabel\(this\.sourceModule\) : '' \}/)
  assert.match(home, /messageModuleLabel\(n\.source\)/)
})
