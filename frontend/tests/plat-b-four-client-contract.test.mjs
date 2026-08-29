import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import test from 'node:test'

const root = path.resolve(process.cwd(), '..')
const files = {
  staffPanel: 'frontend/src/modules/platform/businessForms/components/CompliancePanel.vue',
  staffForm: 'frontend/src/modules/platform/businessForms/components/SchemaBusinessForm.vue',
  staffVersions: 'frontend/src/modules/platform/businessForms/components/BusinessFormVersionWorkbench.vue',
  studentForm: 'student-portal/src/components/businessForms/SchemaBusinessForm.vue',
  miniForm: 'miniapp/src/components/businessForms/SchemaBusinessForm.vue',
  staffRuntime: 'frontend/src/modules/platform/businessForms/schemaRuntime.js',
  studentRuntime: 'student-portal/src/components/businessForms/schemaRuntime.js',
  miniRuntime: 'miniapp/src/components/businessForms/schemaRuntime.js',
}

function source(name) { return fs.readFileSync(path.join(root, files[name]), 'utf8') }

test('Staff compliance UI preserves all normalized non-pass states and source identity', () => {
  const panel = source('staffPanel')
  for (const state of ['BLOCKER', 'WARNING', 'PENDING', 'NOT_EVALUATED', 'NOT_APPLICABLE', 'EXEMPTED']) {
    assert.match(panel, new RegExp(state))
  }
  assert.match(panel, /providerCode/)
  assert.match(panel, /policyVersion/)
  assert.match(panel, /尚未评估/)
  assert.match(panel, /evaluated/)
  assert.doesNotMatch(panel, /NOT_EVALUATED:\s*'通过'/)
})

test('Staff and Student PC submit exact form identity instead of copied business rules', () => {
  for (const name of ['staffForm', 'studentForm']) {
    const form = source(name)
    assert.match(form, /formVersionId/)
    assert.match(form, /schemaHash/)
    assert.match(form, /clientType/)
    assert.match(form, /values/)
    assert.match(form, /Object\.fromEntries/)
    assert.match(form, /state\.readonly/)
    assert.doesNotMatch(form, /v-html|javascript:|remoteOptionsUrl|eval\s*\(|new Function/)
  }
})

test('Teacher and Student miniapp share one safe renderer and fail closed to PC', () => {
  const form = source('miniForm')
  assert.match(form, /TEACHER_MINIAPP/)
  assert.match(form, /STUDENT_MINIAPP/)
  assert.match(form, /FORM_CLIENT_UNSUPPORTED/)
  assert.match(form, /fallback:\s*'PC'/)
  assert.match(form, /formVersionId/)
  assert.match(form, /schemaHash/)
  assert.match(form, /MOBILE_FIELD_TYPES/)
  assert.doesNotMatch(form, /MOBILE_FIELD_TYPES[^\n]+datetime/)
  assert.doesNotMatch(form, /v-html|javascript:|remoteOptionsUrl|eval\s*\(|new Function/)
})

test('Client condition runtimes are bounded presentation-only DSLs', () => {
  for (const name of ['staffRuntime', 'studentRuntime', 'miniRuntime']) {
    const runtime = source(name)
    for (const op of ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'all', 'any']) {
      assert.match(runtime, new RegExp(`['"]${op}['"]`))
    }
    assert.match(runtime, /depth\s*>\s*8/)
    assert.doesNotMatch(runtime, /eval\s*\(|new Function|Function\s*\(/)
  }
})
