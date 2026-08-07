import test from 'node:test'
import assert from 'node:assert/strict'
import {
  ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS,
  ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES
} from '../help/academicAffairsVerifiedOverrides.js'

test('stale fixed usual-final grade long doc remains quarantined', () => {
  assert.match(ACADEMIC_AFFAIRS_LEGACY_EXCLUSIONS.docs['doc-aa-grade'], /动态成绩项/)
})

test('academic runtime override layer is retired after knowledge cleaning V2', () => {
  assert.deepEqual(ACADEMIC_AFFAIRS_VERIFIED_OVERRIDES, {})
})
