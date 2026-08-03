import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const urlFor = (path) => new URL(`../../${path}`, import.meta.url)
const read = (path) => fs.readFileSync(urlFor(path), 'utf8')
const exists = (path) => fs.existsSync(urlFor(path))

test('student clients use the server allowedActions contract without runtime adapters', () => {
  for (const removed of [
    'student-portal/src/services/affairsAllowedActions.js',
    'miniapp/src/services/affairsAllowedActions.js'
  ]) {
    assert.equal(exists(removed), false, `${removed} must stay deleted`)
  }

  for (const mainPath of ['student-portal/src/main.js', 'miniapp/src/main.js']) {
    assert.doesNotMatch(read(mainPath), /affairsAllowedActions/)
  }

  const portal = read('student-portal/src/views/affairs/AffairsFourEndView.vue')
  assert.match(portal, /const allows = \(item, action\) => Array\.isArray\(item\?\.allowedActions\) && item\.allowedActions\.includes\(action\)/)
  assert.match(portal, /allows\(item, 'EDIT_RETURNED'\)/)
  assert.match(portal, /allows\(item, 'RESUBMIT'\)/)
  assert.match(portal, /allows\(item, 'SUBMIT_CANCEL'\)/)
  assert.match(portal, /allows\(item, 'SUBMIT_EXTENSION'\)/)
  assert.match(portal, /allows\(item, 'SUBMIT_OBJECTION'\)/)
  assert.match(portal, /allows\(item, 'SUBMIT_APPEAL'\)/)

  for (const pagePath of [
    'miniapp/src/pages/student/affairs/leave.vue',
    'miniapp/src/pages/student/affairs/aid.vue',
    'miniapp/src/pages/student/affairs/funding.vue',
    'miniapp/src/pages/student/affairs/discipline.vue'
  ]) {
    const source = read(pagePath)
    assert.match(source, /Array\.isArray\(item && item\.allowedActions\) && item\.allowedActions\.includes\(action\)/)
    assert.doesNotMatch(source, /canResubmit|canObject|canAppeal/)
  }
})


test('admin student-affairs actions fail closed when allowedActions is absent', () => {
  const workStudy = read('frontend/src/modules/studentAffairs/views/funding/WorkStudyView.vue')
  const loan = read('frontend/src/modules/studentAffairs/views/funding/StudentLoanView.vue')
  const fee = read('frontend/src/modules/studentAffairs/views/funding/FeeReductionView.vue')
  const dorm = read('frontend/src/modules/studentAffairs/views/dorm/DormTransferView.vue')
  const mental = read('frontend/src/modules/studentAffairs/views/mental/MentalReferralFollowView.vue')
  assert.match(workStudy, /Array\.isArray\(row\?\.allowedActions\) \? row\.allowedActions : \[\]/)
  assert.match(loan, /Array\.isArray\(row\?\.allowedActions\) && row\.allowedActions\.includes\('ADVANCE'\)/)
  assert.match(fee, /Array\.isArray\(row\?\.allowedActions\) && row\.allowedActions\.includes\(action\)/)
  assert.match(dorm, /Array\.isArray\(row\.allowedActions\) && row\.allowedActions\.includes\(action\)/)
  assert.match(mental, /Array\.isArray\(row\.allowedActions\) \? row\.allowedActions : \[\]/)
  for (const source of [workStudy, loan, fee, dorm, mental]) {
    assert.doesNotMatch(source, /FALLBACK_ACTIONS/)
  }
})
