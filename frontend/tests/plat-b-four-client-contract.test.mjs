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

const productionFiles = {
  staffApi: 'frontend/src/modules/system/api/businessForms.api.js',
  staffPage: 'frontend/src/modules/system/views/SystemBusinessFormsView.vue',
  staffRoutes: 'frontend/src/modules/system/system.routes.js',
  studentPage: 'student-portal/src/views/forms/BusinessFormView.vue',
  studentApi: 'student-portal/src/services/portalApi.js',
  studentRoutes: 'student-portal/src/router/index.js',
  miniPage: 'miniapp/src/pages/common/business-form/index.vue',
  miniApi: 'miniapp/src/services/businessFormApi.js',
  miniPages: 'miniapp/src/pages.json',
}

function source(name) { return fs.readFileSync(path.join(root, files[name]), 'utf8') }
function read(relativePath) { return fs.readFileSync(path.join(root, relativePath), 'utf8') }

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
  assert.match(source('studentForm'), /selectedOptions/)
  assert.match(source('studentForm'), /entry\.field\.multiple/)
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
  assert.match(form, /field\.type === 'select' && field\.multiple/)
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

test('Staff and Student PC components are wired to real APIs and routable pages', () => {
  const staffApi = read(productionFiles.staffApi)
  const staffPage = read(productionFiles.staffPage)
  const staffRoutes = read(productionFiles.staffRoutes)
  const studentPage = read(productionFiles.studentPage)
  const studentApi = read(productionFiles.studentApi)
  const studentRoutes = read(productionFiles.studentRoutes)
  assert.match(staffApi, /platform\/business-form-versions/)
  assert.match(staffApi, /platform\/compliance\/evaluate/)
  assert.match(staffPage, /BusinessFormVersionWorkbench/)
  assert.match(staffPage, /CompliancePanel/)
  assert.match(staffRoutes, /SystemBusinessFormsView\.vue/)
  assert.match(studentPage, /businessFormLoad/)
  assert.match(studentPage, /fileSdk\.upload/)
  assert.match(studentPage, /expectedBusinessVersion/)
  assert.match(studentPage, /complianceRequests\.value/)
  assert.match(studentPage, /:server-errors="fieldErrors"/)
  assert.match(studentApi, /business-forms\/runtime\/submit/)
  assert.match(studentRoutes, /business-forms\/:formCode\/:versionId/)
})

test('Teacher and Student miniapp use one registered common typed-action target', () => {
  const page = read(productionFiles.miniPage)
  const api = read(productionFiles.miniApi)
  const pages = read(productionFiles.miniPages)
  assert.match(page, /TEACHER_MINIAPP/)
  assert.match(page, /STUDENT_MINIAPP/)
  assert.match(page, /SchemaBusinessForm/)
  assert.match(page, /result\.nextAction \|\| result\.next_action/)
  assert.match(page, /complianceRequests: this\.complianceRequests/)
  assert.match(page, /runAction\(nextAction/)
  assert.match(api, /business-forms\/runtime\/load/)
  assert.match(pages, /pages\/common\/business-form\/index/)
})
