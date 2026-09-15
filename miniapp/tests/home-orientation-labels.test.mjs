import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const { orientationStepLabel } = await import('data:text/javascript;base64,' + Buffer.from(
  readFileSync(new URL('../src/services/orientationPresentation.js', import.meta.url), 'utf8')
).toString('base64'))

const script = readFileSync(new URL('../src/pages/student/home/index.vue', import.meta.url), 'utf8')
  .match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return')
const page = new Function('go', 'toast', 'deadlineText', 'messageModuleLabel', 'orientationStepLabel', script)(
  () => {}, () => {}, () => '', () => '', orientationStepLabel)

test('WeChat home displays Chinese orientation names instead of raw step codes', () => {
  const steps = page.computed.orientationSteps.call({ orientation: { steps: [
    { key: 'IDENTITY', status: 'TODO' }, { key: 'FINANCE', status: 'TODO' },
    { key: 'CUSTOM', label: '学院资料确认', status: 'DONE' },
    { key: 'UNKNOWN_CODE', label: 'UNKNOWN_LABEL', status: 'TODO' }
  ] } })
  assert.deepEqual(steps.map(step => step.label), ['身份核验', '绿色通道', '学院资料确认', '报到事项'])
  assert.equal(page.computed.orientationNextLabel.call({ orientationCurrentStep: steps[0] }), '身份核验')
  assert.deepEqual(steps.map(step => step.state), ['now', 'wait', 'done', 'wait'])
})
