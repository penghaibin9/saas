import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/modules/orientation/api/orientation.api.js', import.meta.url), 'utf8')

const unsupportedPermissions = [
  'orientation.student.import',
  'orientation.student.export',
  'orientation.student.batchRemind',
  'orientation.student.batchAssign',
  'orientation.progress.export',
  'orientation.payment.export',
  'orientation.material.export',
  'orientation.dorm.export',
  'orientation.exception.export',
  'orientation.followup.edit'
]

test('P1-04 unsupported orientation capabilities are intersected with role permissions', () => {
  assert.match(source, /const UNSUPPORTED_ACTIONS = Object\.freeze\(/)
  assert.match(source, /const allowed = roleAllowed && !unsupportedReason/)
  for (const permission of unsupportedPermissions) {
    assert.ok(source.includes(`'${permission}'`), `${permission} must be declared unsupported until a real backend action exists`)
  }
})

test('P1-04 unsupported operations remain API fail-closed as a second guard', () => {
  for (const fn of [
    'batchRemindStudents',
    'batchAssignCounselor',
    'updateExceptionFollowUp',
    'validateImport',
    'confirmImport',
    'createExport'
  ]) {
    assert.match(source, new RegExp(`export async function ${fn}\\([^]*?501001`, 'm'), `${fn} must fail closed`)
  }
})
