import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

const proposal = read('frontend/src/modules/graduation/views/ProposalListView.vue')
const finalSubmission = read('frontend/src/modules/graduation/views/FinalSubmissionListView.vue')
const layout = read('frontend/src/modules/graduation/views/AdminGraduationLayout.vue')
const service = read('backend/app/modules/graduation/services/graduation_service.py')

test('proposal and final reminder copy reflects the real message write chain', () => {
  for (const [name, source] of [['proposal', proposal], ['final', finalSubmission]]) {
    assert.match(source, /创建真实站内消息并写入催办留痕/, `${name} must state the real reminder effect`)
    assert.match(source, /发送.*催交站内消息并记录催办留痕/, `${name} success toast must reflect the real message effect`)
    assert.doesNotMatch(source, /当前仅记录线下催办留痕/, `${name} must not claim offline-only reminder`)
    assert.doesNotMatch(source, /未发送站内消息/, `${name} must not claim message was not sent`)
  }
})

test('graduation layout does not rewrite child reminder copy through the DOM', () => {
  assert.doesNotMatch(layout, /normalizeReminderCopy/)
  assert.doesNotMatch(layout, /querySelectorAll\(['"]\.gd-business-view \.mp-note/)
  assert.match(layout, /催交会发送真实站内消息/)
})

test('backend reminder service retains explicit message and delivery-failure truth', () => {
  assert.match(service, /UnifiedMessage/)
  assert.match(service, /DELIVERY_FAILED/)
})
