import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = (name) => readFile(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
const component = (name) => readFile(new URL(`../src/modules/academicAffairs/components/graduation/${name}.vue`, import.meta.url), 'utf8')

test('毕业管理 15 个入口共用学生、十一项证据、学院审核、教务终审、证书归档阶段', async () => {
  const [batch, audit, rail] = await Promise.all([
    view('AaGraduationBatchView'), view('AaGraduationAuditConsoleView'), component('GraduationStageRail')
  ])
  for (const label of ['审核批次', '毕业学生', '十一项证据', '学院审核', '教务终审', '证书归档']) {
    assert.match(rail, new RegExp(label))
  }
  assert.match(batch, /isBatchList.*\$route\.query\.tab==='batches'/s)
  for (const tab of ['credit', 'course', 'practice', 'thesis', 'internship', 'fee', 'discipline', 'final', 'roster', 'reason', 'results', 'archive']) {
    assert.match(audit, new RegExp(`${tab}:`), `missing graduation tab ${tab}`)
  }
})

test('毕业审核展示真实对象、责任、阻断、下一岗位和十一项正式证据', async () => {
  const source = await view('AaGraduationAuditConsoleView')
  for (const token of ['当前学生对象', '来源批次', '当前责任', '当前阻断', '下一岗位', '证据责任', '当前正式证据未提供']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /focusedItems.*tab==='final'.*items/s)
  assert.match(source, /resultSignature\(row\)/)
  assert.match(source, /sameDecision\(command\)/)
  assert.match(source, /getGradResult\(resultId\)[\s\S]*canNormalFinal\(fresh\.data\)[\s\S]*finalGrad\(resultId, this\.finalConclusion, true\)/)
})

test('费用 UNKNOWN 不伪造通过，证书发放与作废锁对象并回读台账', async () => {
  const [audit, cert] = await Promise.all([view('AaGraduationAuditConsoleView'), view('AaCertificateView')])
  assert.match(audit, /费用结清默认 UNKNOWN（不阻断）/)
  assert.match(audit, /不得显示为已自动通过/)
  for (const token of ['readCertificate(snapshot)', 'signature(before)!==this.signature(snapshot)', 'pendingCommand', 'issueCertificate', 'voidCertificate', '已回读正式证书台账']) {
    assert.ok(cert.includes(token), `missing certificate guard ${token}`)
  }
  assert.match(cert, /:pagination="pagination"/)
  assert.match(cert, /academicAffairs\.graduationCert\.manage/)
})
