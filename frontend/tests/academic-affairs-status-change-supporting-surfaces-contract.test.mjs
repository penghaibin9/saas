import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const printUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangePrintView.vue', import.meta.url)
const portalRoutesUrl = new URL('../../student-portal/src/router/academicRoutes.js', import.meta.url)
const portalSectionUrl = new URL('../../student-portal/src/views/academic/AcademicSectionRouteView.vue', import.meta.url)
const portalAcademicUrl = new URL('../../student-portal/src/views/academic/AcademicView.vue', import.meta.url)
const portalEnumsUrl = new URL('../../student-portal/src/services/visibleEnumLocalization.js', import.meta.url)
const miniappUrl = new URL('../../miniapp/src/pages/student/academic-affairs/status.vue', import.meta.url)

test('D3-U print shows scheduled effective time independently from suspend expiry', async () => {
  const source = await readFile(printUrl, 'utf8')

  assert.match(source, /<th>生效方式<\/th>/)
  assert.match(source, /<th>计划生效时间<\/th>/)
  assert.match(source, /change\.effectiveDate \? '指定日期' : '终审通过立即生效'/)
  assert.match(source, /<tr v-if="change\.expireDate"><th>休学到期<\/th><td colspan="3">/)
  assert.doesNotMatch(source, /v-if="change\.expireDate"[^\n]*change\.effectiveDate/)
})

test('D3-U student portal locks the real status route to canonical pending-effective display', async () => {
  const [routes, section, academic, enums] = await Promise.all([
    readFile(portalRoutesUrl, 'utf8'),
    readFile(portalSectionUrl, 'utf8'),
    readFile(portalAcademicUrl, 'utf8'),
    readFile(portalEnumsUrl, 'utf8')
  ])

  assert.match(routes, /academicSection\('status', 'academic-status', '学籍异动'/)
  assert.match(section, /import AcademicView from '\.\/AcademicView\.vue'/)
  assert.match(academic, /<AutoTable :rows="status\.changes" :columns="STATUS_CHANGE_COLS"/)
  assert.match(academic, /\{ key: 'effectiveDate', label: '生效日期' \}/)
  assert.match(enums, /IN_REVIEW: '审批中'/)
  assert.match(enums, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(enums, /EFFECTIVE: '已生效'/)
  assert.match(enums, /SUSPENDED: '休学'/)
  assert.match(enums, /PRESERVED: '保留学籍'/)
  assert.match(enums, /WITHDRAWN: '退学'/)
})

test('D3-U miniapp localizes pending-effective and shows planned time', async () => {
  const source = await readFile(miniappUrl, 'utf8')

  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /c\.status === 'APPROVED_PENDING_EFFECTIVE'/)
  assert.match(source, /c\.effectiveDate/)
})
