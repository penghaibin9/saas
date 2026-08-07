import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS,
  ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES
} from '../help/academicAffairsVerifiedOverrides.js'
import { buildHelpSearchText } from '../helpCenterCore.js'

test('stale fixed usual-final grade long doc is quarantined', () => {
  assert.match(ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS.docs['doc-aa-grade'], /动态成绩项/)
})

test('grade entry card uses current dynamic component truth', () => {
  const card = ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES['aa-card-grade-entry']
  const text = buildHelpSearchText(card)

  assert.match(text, /1–12 个动态成绩项/)
  assert.match(text, /严格合计 100/)
  assert.match(text, /not_started/)
  assert.match(text, /inputting/)
  assert.match(text, /returned/)
  assert.match(text, /首次正式录分后方案会锁定/)
  assert.match(text, /可选成绩项未提交按 0 分/)
  assert.match(text, /absent \/ deferred \/ exempt \/ cheat/)
  assert.match(text, /特殊状态不是 0 分/)
})

test('grade entry no longer claims one universal usual plus final scheme', () => {
  const text = buildHelpSearchText(ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES['aa-card-grade-entry'])
  assert.match(text, /成绩一定是“平时分 \+ 期末分”吗？ 不是/)
  assert.doesNotMatch(text, /总评 = 平时分×平时比例 \+ 期末分×期末比例/)
  assert.doesNotMatch(text, /已设好平时\+期末比例/)
})

test('grade publish guide separates committed publish from best-effort warning scan', () => {
  const card = ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES['aa-card-grade-review-publish']
  const text = buildHelpSearchText(card)

  assert.match(text, /冻结正式教学名单快照/)
  assert.match(text, /academic_review/)
  assert.match(text, /pUBLISHED/i)
  assert.match(text, /正式 academicgrade 投影/)
  assert.match(text, /不及格记录.*academic_warning/)
  assert.match(text, /warningscanok \/ warningscanerror/)
  assert.match(text, /扫描失败.*不会回滚已经发布的成绩/)
  assert.match(text, /不要重复发布成绩/)
})
