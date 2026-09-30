import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')
test('谈话转风险精确跳风险详情', () => { const s=read('src/modules/studentAffairs/views/TalkWorkbenchView.vue'); assert.ok(s.includes("name: 'student-affairs-risk-detail'")); assert.ok(s.includes('riskId: String(this.selected.relatedRiskId)')); assert.ok(s.includes("from: 'talk'")); })
test('谈话转家校保持 studentId/contactId', () => { const s=read('src/modules/studentAffairs/views/TalkWorkbenchView.vue'); assert.ok(s.includes("path: '/admin/student-affairs/family'")); assert.ok(s.includes('contactId: String(this.selected.relatedContactId)')); assert.ok(s.includes('studentId: String(this.selected.studentId)')); })
test('家校仅当前学生时间线聚焦 contactId', () => { const s=read('src/modules/studentAffairs/views/FamilyContactView.vue'); assert.ok(s.includes("this.contactFocusId = String(q.contactId || '').trim()")); assert.ok(s.includes('该联系记录未在当前页，已定位到该生时间线')); assert.ok(s.includes('getFamilyContacts(this.studentId')); })
test('宿舍异常展示 DORM 风险并精确跳转', () => { const s=read('src/modules/studentAffairs/views/dorm/DormExceptionView.vue'); assert.ok(s.includes("name: 'student-affairs-risk-detail'")); assert.ok(s.includes("from: 'dorm-exception'")); assert.ok(s.includes('未生成风险')); })
