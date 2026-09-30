import test from 'node:test'
import assert from 'node:assert/strict'

import {
  coreGroupEntitled,
  entitlementSignature,
  moduleCodeForNav,
  moduleEntitled,
} from '../src/security/moduleEntitlement.js'

const technical = ['workbench', 'todoMessage', 'systemAdmin', 'auditLog', 'approval']

test('shared studentProfile does not imply purchased studentAffairs', () => {
  const entitlement = [...technical, 'internship', 'studentProfile']
  assert.equal(coreGroupEntitled('student-affairs', entitlement, true), false)
  assert.equal(coreGroupEntitled('internship', entitlement, true), true)
})

test('all four canonical centre aliases remain exact', () => {
  assert.equal(moduleEntitled('INTERNSHIP', ['internship'], true), true)
  assert.equal(moduleEntitled('GRADUATION', ['graduationDesign'], true), true)
  assert.equal(moduleEntitled('ACADEMIC_AFFAIRS', ['academicAffairs'], true), true)
  assert.equal(moduleEntitled('STUDENT_AFFAIRS', ['studentAffairs'], true), true)
})

test('internship never implicitly grants employment or platform API', () => {
  assert.equal(moduleEntitled('EMPLOYMENT', ['internship'], true), false)
  assert.equal(moduleEntitled('PLATFORM', ['internship'], true), false)
})

test('nav module inference matches route meta vocabulary', () => {
  assert.equal(moduleCodeForNav('internship', '/admin/internship'), 'INTERNSHIP')
  assert.equal(moduleCodeForNav('graduation', '/admin/graduation'), 'GRADUATION')
  assert.equal(moduleCodeForNav('student-affairs', '/admin/student-affairs/dashboard'), 'STUDENT_AFFAIRS')
  assert.equal(moduleCodeForNav('academic-affairs', '/admin/academic-affairs'), 'ACADEMIC_AFFAIRS')
})

test('unhealthy and unknown commercial contexts have distinct cache signatures', () => {
  assert.equal(entitlementSignature([], false), '__module_authority_unhealthy__')
  assert.equal(entitlementSignature(null, true), '__module_authority_unknown__')
  assert.notEqual(entitlementSignature([], true), entitlementSignature(null, true))
})

// Keep the real adapter regressions in the existing M2 CI entrypoint.
await import('./module-commerce-layout-context.test.mjs')
