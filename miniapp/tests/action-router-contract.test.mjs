import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join, relative } from 'node:path'
import {
  ALLOWED_PREFIXES,
  DEFAULT_DISABLED_REASON,
  canNavigate,
  createRunAction,
  disabledReasonOf,
  isObjectFocused,
  normalizeTarget
} from '../src/services/actionRouterCore.mjs'
import { hasFocusRow, isFocusRow, readFocusId } from '../src/utils/listFocus.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

function spy() {
  const calls = []
  const fn = (value) => calls.push(value)
  fn.calls = calls
  return fn
}
function harness() {
  const navigate = spy()
  const toast = spy()
  return { navigate, toast, run: createRunAction({ navigate, toast }) }
}

const studentTarget = {
  target: { path: '/pages/student/affairs/leave', query: { recordId: '123' }, routeExact: true }
}

test('S2 只跳本端分包与共享页，越界 fail-closed', () => {
  assert.equal(canNavigate(studentTarget, 'student'), true)
  assert.equal(canNavigate(studentTarget, 'teacher'), false, '学生页不得在教师端跳转')
  assert.equal(canNavigate({ target: { path: '/pages/common/message-detail/index' } }, 'student'), true)
  assert.equal(canNavigate({ target: { path: '/pages/common/message-detail/index' } }, 'teacher'), true)
  assert.equal(canNavigate({ target: { path: '/admin/student-affairs/leave' } }, 'student'), false, 'PC 路径不得进入小程序导航')
  assert.deepEqual(ALLOWED_PREFIXES.student, ['/pages/student/', '/pages/common/'])
  assert.deepEqual(ALLOWED_PREFIXES.teacher, ['/pages/teacher/', '/pages/common/'])
})

test('S2 无 target / 空 action 一律不可跳转', () => {
  for (const action of [null, undefined, {}, { target: null }, { target: {} }, { target: { path: '' } }]) {
    assert.equal(canNavigate(action, 'student'), false)
  }
})

test('S2 runAction 不可跳转时只提示原因，绝不退化到通用大厅', () => {
  const { navigate, toast, run } = harness()
  assert.equal(run({ target: null, disabledReason: '该消息已撤回' }), false)
  assert.deepEqual(navigate.calls, [], '不得发生任何跳转')
  assert.deepEqual(toast.calls, ['该消息已撤回'])

  assert.equal(run({ target: null }), false)
  assert.equal(toast.calls[1], DEFAULT_DISABLED_REASON)
  assert.deepEqual(navigate.calls, [])
})

test('S2 runAction 只拼服务端已校验的 query 并统一 encode', () => {
  const { navigate, run } = harness()
  run(studentTarget)
  assert.deepEqual(navigate.calls, ['/pages/student/affairs/leave?recordId=123'])

  const { navigate: n2, run: r2 } = harness()
  r2({ target: { path: '/pages/student/affairs/index?tab=material', query: { materialRequirementId: 'a b&c' } } })
  assert.deepEqual(n2.calls, ['/pages/student/affairs/index?tab=material&materialRequirementId=a%20b%26c'])

  // 空值不进 query，避免拼出 recordId=undefined
  assert.equal(
    normalizeTarget({ path: '/pages/student/affairs/leave', query: { recordId: '', other: null } }),
    '/pages/student/affairs/leave'
  )
})

test('S2 routeExact 决定是否真的对象级闭环', () => {
  assert.equal(isObjectFocused(studentTarget), true)
  assert.equal(isObjectFocused({ target: { path: '/pages/student/internship/index', routeExact: false } }), false)
  assert.equal(isObjectFocused(null), false)
})

test('S2 disabledReason 优先用服务端文案', () => {
  assert.equal(disabledReasonOf({ disabledReason: '当前端暂无对应页面，请前往教师 PC / 学生 PC 办理' }),
    '当前端暂无对应页面，请前往教师 PC / 学生 PC 办理')
  assert.equal(disabledReasonOf({}), DEFAULT_DISABLED_REASON)
  assert.equal(disabledReasonOf(null), DEFAULT_DISABLED_REASON)
})

test('S2 LIST_FOCUS 工具按聚焦参数定位，找不到时明确失败', () => {
  assert.equal(readFocusId({ recordId: ' 42 ' }), '42')
  assert.equal(readFocusId({ materialRequirementId: '7' }, 'materialRequirementId'), '7')
  assert.equal(readFocusId({}), '')
  assert.equal(readFocusId(undefined), '')

  const rows = [{ leaveId: 41 }, { leaveId: 42 }]
  assert.equal(hasFocusRow(rows, '42', ['leaveId']), true)
  assert.equal(hasFocusRow(rows, '99', ['leaveId']), false, '对象不在列表里必须能被判定出来')
  assert.equal(hasFocusRow([], '42', ['leaveId']), false)
  assert.equal(hasFocusRow(rows, '', ['leaveId']), false)
  assert.equal(isFocusRow({ leaveId: 42 }, '42', ['leaveId']), true)
  assert.equal(isFocusRow({ leaveId: 41 }, '42', ['leaveId']), false)
})

// ── 源码契约：任何页面都不得再自建业务路由表 ──

function collect(dir, acc = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) collect(full, acc)
    else if (/\.(vue|js|mjs)$/.test(entry)) acc.push(full)
  }
  return acc
}

test('S2 message-detail 不再按 actionKey/module 猜业务路由', () => {
  const source = read('src/pages/common/message-detail/index.vue')
  const script = source.slice(source.indexOf('<script>'))
  assert.doesNotMatch(script, /const ACTION_ROUTES\s*=/)
  assert.doesNotMatch(script, /const MODULE_ROUTES\s*=/)
  assert.doesNotMatch(script, /resolveTarget\s*\(/)
  assert.match(script, /runAction\(/)
  assert.match(script, /canNavigate\(/)
  // 兜底文案不得再指向任何通用大厅页
  assert.doesNotMatch(script, /'\/pages\/student\/(affairs|my-applications)\/index'/)
})

test('S2 页面不得再声明本地业务路由映射表', () => {
  const offenders = []
  for (const file of collect(resolve(root, 'src/pages'))) {
    const source = readFileSync(file, 'utf8')
    if (/const\s+(ACTION_ROUTES|MODULE_ROUTES|BIZ_ROUTES|TODO_ROUTES)\s*=/.test(source)) {
      offenders.push(relative(root, file))
    }
  }
  assert.deepEqual(offenders, [], `以下页面重新引入了客户端业务路由表:\n${offenders.join('\n')}`)
})

test('S2 声明 LIST_FOCUS 的页面必须真的消费聚焦参数', () => {
  for (const [file, idKey, prefix] of [
    ['src/pages/student/affairs/leave.vue', 'leaveId', 'leave-'],
    ['src/pages/student/affairs/aid.vue', 'applyId', 'aid-'],
    ['src/pages/student/affairs/funding.vue', 'applicationId', 'funding-']
  ]) {
    const source = read(file)
    assert.match(source, /readFocusId\(query\)/, `${file} 必须从 query 读聚焦值`)
    assert.match(source, /this\.applyFocus\(\)/, `${file} 必须在数据就绪后定位对象`)
    assert.match(source, new RegExp(`hasFocusRow\\(rows, this\\.focusId, \\['${idKey}'\\]\\)`), `${file} 必须按真实主键判定`)
    assert.match(source, new RegExp(`:id="'${prefix}' \\+ x\\.${idKey}"`), `${file} 行必须可被 selector 定位`)
    assert.match(source, /v-if="focusMissing"/, `${file} 找不到对象时必须明确告知，不得假装已定位`)
  }
})

test('S2 补交材料入口沿用它自己的聚焦参数名', () => {
  const source = read('src/pages/student/affairs/index.vue')
  assert.match(source, /query\.materialRequirementId/)
})
