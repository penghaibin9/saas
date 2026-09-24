import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/mental/MentalReferralFollowView.vue', import.meta.url), 'utf8').replaceAll('\r', '')

test('psychology workbench keeps the exact referral in the current workspace', () => {
  assert.match(source, /this\.\$route\.query\.referralId \|\| this\.\$route\.query\.recordId/)
  assert.match(source, /findIndex\(\(row\) => String\(row\.referralId\) === this\.focusedReferralId\)/)
  assert.match(source, /mental-row--focused/)
})

test('follow, escalate and close use server actions and the current version', () => {
  assert.match(source, /const action = dlg\.kind === 'follow' \? 'FOLLOW'/)
  assert.match(source, /escalateMentalReferral\(dlg\.row\.referralId, text, dlg\.row\.version\)/)
  assert.match(source, /followMentalReferral\(dlg\.row\.referralId, text, dlg\.row\.version\)/)
  assert.match(source, /closeMentalReferral\(dlg\.row\.referralId, text, dlg\.row\.version\)/)
  assert.match(source, /openRisk\(row\.riskId\)/)
})
