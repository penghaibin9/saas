import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/modules/internship/views/RegulatoryReportingView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
const imports = [...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)]
  .flatMap(([, bindings]) => bindings.replace(/[{}]/g, '').split(',').map(name => name.trim()))
const component = new Function(...imports, script.replace(/^import[^\n]*\n/gm, '').replace('export default', 'return'))(...imports.map(() => ({})))

test('监管任务未接通或返回未知就绪状态时不显示已联通', () => {
  for (const tasks of [[], [{ externalReadiness: 'BLOCKED_EXTERNAL' }], [{ externalReadiness: 'UNKNOWN' }]]) {
    assert.equal(component.computed.externalReady.call({ tasks }), false)
  }
  assert.equal(component.computed.externalReady.call({ tasks: [{ externalReadiness: 'READY' }] }), true)
})

test('正式模板核验与外部接收分开显示，未知状态使用中文说明', () => {
  const label = component.methods.templateReadinessLabel
  assert.equal(label({ externalReadiness: 'READY', officialVerified: true }), '正式模板已核验')
  assert.equal(label({ externalReadiness: 'BLOCKED_EXTERNAL', officialVerified: false }), '待核验正式模板')
  for (const template of [undefined, { externalReadiness: 'READY', officialVerified: false }, { externalReadiness: 'UNRECOGNIZED' }]) {
    assert.equal(label(template), '模板状态待确认')
  }
  assert.equal(component.methods.statusLabel('RECEIPT_PENDING'), '待真实回执')
  assert.equal(component.methods.statusLabel('UNKNOWN_INTERNAL_CODE'), '状态待确认')
})
