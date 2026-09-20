import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = parse(readFileSync(new URL('../../miniapp/src/pages/teacher/dorm-review/index.vue', import.meta.url), 'utf8')).descriptor.script.content
const script = source.replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
function fixture(kind, changeSession = false) {
  let generation = 1
  const calls = []
  const fail = async (...args) => {
    calls.push(args)
    if (changeSession) generation++
    throw { kind, message: '检查失败' }
  }
  const deps = {
    teacherApi: {}, affairsContractApi: { reviewDormTransfer: fail, handleDormException: fail },
    normalizeError: error => ({ kind: error.kind, text: error.message }), realRequest: fail,
    toast: () => {}, createClientRequestId: () => 'test-request', fileSdk: {},
    currentSessionGeneration: () => generation
  }
  const options = new Function(...Object.keys(deps), script)(...Object.values(deps))
  const page = { ...options.data() }
  for (const [key, fn] of Object.entries(options.methods)) page[key] = fn.bind(page)
  page.load = async () => { page.loadSerial++ }
  return { page, calls }
}

const note = '已经现场核对学生住宿情况'
for (const operation of ['transfer', 'exception']) {
  for (const scenario of ['network', 'conflict', 'session-change']) {
    test(`${operation}: ${scenario} keeps dialog recovery scoped without replaying a command`, async () => {
      const { page, calls } = fixture(scenario === 'conflict' ? 'conflict' : 'network', scenario === 'session-change')
      const row = { transferId: '77', exceptionId: '88', version: 7, allowedActions: ['REJECT'] }
      if (operation === 'transfer') page.reviewTransfer(row, 'REJECT')
      else page.handleException(row)
      page.actionDlg.value = note
      await page.submitActionDlg()
      assert.equal(calls.length, 1, 'Recovery must not resend the business command')
      assert.equal(calls[0].at(-1), 7, 'The visible version must reach the command')
      if (scenario === 'network') {
        assert.equal(page.actionDlg.visible, true)
        assert.equal(page.actionDlg.value, note, 'A failed command must retain the entered reason')
      } else {
        assert.equal(page.actionDlg.visible, false, 'A conflict or changed identity must not reopen the stale dialog')
      }
      if (scenario === 'conflict') assert.equal(page.loadSerial, 1, 'Conflict must reload rather than silently overwrite')
      await Promise.resolve()
      assert.equal(calls.length, 1)
    })
  }
}
