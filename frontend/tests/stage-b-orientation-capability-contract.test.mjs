import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(path, import.meta.url), 'utf8')
const api = read('../src/modules/orientation/api/orientation.api.js')
const meta = read('../src/modules/orientation/constants/orientation.meta.js')
const routes = read('../src/modules/orientation/orientation.routes.js')
const navPlan = read('../src/config/navPlan.js')
const importDialog = read('../src/modules/orientation/components/ImportDialog.vue')
const exportDialog = read('../src/modules/orientation/components/ExportDialog.vue')
const dormOverview = read('../src/modules/studentAffairs/views/StudentAffairsDormitoryView.vue')
const backendImportExport = read('../../backend/app/api/v1/import_export.py')
const backendAuth = read('../../backend/app/core/import_export_auth.py')
const backendExport = read('../../backend/app/services/domain_export_service.py')

const stillUnsupported = [
  'orientation.student.batchRemind',
  'orientation.student.batchAssign',
  'orientation.progress.export',
  'orientation.payment.export',
  'orientation.material.export',
  'orientation.dorm.export',
  'orientation.exception.export',
  'orientation.followup.edit'
]

test('A1 orientation permissions come only from real current-context patterns', () => {
  assert.match(api, /request\('\/tenant\/brand'\)/)
  assert.match(api, /request\('\/rbac\/current-context'\)/)
  assert.match(api, /matchPermission\(patterns, permissionCode\)/)
  assert.doesNotMatch(api, /enrichContext|permissionActionsByRole|currentRoleId/)
  assert.doesNotMatch(meta, /tenantBrandConfig|permissionActionsByRole|export const roles|export const state/)
  assert.doesNotMatch(meta, /演示职业技术学院|梧桐苑|信息工程学院/)
})

test('A1 routes and navigation use the canonical backend orientation view permission', () => {
  assert.match(routes, /permissionKey: 'studentAffairs\.orientation\.view'/)
  assert.doesNotMatch(routes, /permissionKey: 'orientation\./)
  const orientationNav = navPlan.slice(navPlan.indexOf("mod('sa-orientation'"), navPlan.indexOf("mod('sa-leave'"))
  assert.match(orientationNav, /studentAffairs\.orientation\.view/)
  assert.doesNotMatch(orientationNav, /'orientation\./)
})

test('A1 student import is a real xlsx template, upload dry-run and atomic confirm chain', () => {
  assert.match(api, /request\('\/import\/domain\/orientation\/template'\)/)
  assert.match(api, /requestUpload\('\/import\/domain\/orientation\/validate-file', file\)/)
  assert.match(api, /request\('\/import\/domain\/confirm'/)
  assert.match(api, /status === 'DRY_RUN_PASSED'/)
  assert.match(importDialog, /accept="\.xlsx"/)
  assert.match(importDialog, /downloadXlsxFromApi\(res\.data\)/)
  assert.match(importDialog, /batchNo: this\.validation\.batchNo/)
  assert.doesNotMatch(importDialog, /模拟下载|\.xls 格式/)
  assert.match(backendImportExport, /@import_router\.get\("\/domain\/\{domain\}\/template"/)
  assert.match(backendImportExport, /@import_router\.post\("\/domain\/\{domain\}\/validate-file"/)
  assert.match(backendImportExport, /read_safe_upload\(file\)/)
  assert.match(backendImportExport, /domain_import_service\.dry_run/)
})

test('A1 student export is scoped, purpose-bound, watermarked, audited and downloadable', () => {
  assert.match(api, /request\('\/export\/domain\/orientation'/)
  assert.match(api, /purpose\.length < 5/)
  assert.match(api, /\/api\/v1\/export\/tasks\/\$\{data\.taskId\}\/download/)
  assert.match(exportDialog, /v-model\.trim="purpose"/)
  assert.match(exportDialog, /downloadXlsxFromApi\(res\.data\)/)
  assert.match(backendExport, /elif domain == "orientation"/)
  assert.match(backendExport, /fn\(1, MAX_EXPORT_ROWS, user=user, batch_id=orientation_batch_id\)/)
  assert.match(backendAuth, /studentAffairs\.orientation\.import/)
  assert.match(backendAuth, /studentAffairs\.orientation\.export/)
})

test('A1 every remaining unsupported orientation action is disabled before invocation', () => {
  assert.match(api, /const UNSUPPORTED_ACTIONS = Object\.freeze\(/)
  assert.match(api, /const allowed = permissionAllowed && !unsupportedReason && !readonlyBlocked/)
  for (const action of stillUnsupported) {
    assert.ok(api.includes(`'${action}'`), `${action} must remain explicitly disabled`)
  }
  assert.doesNotMatch(api, /'orientation\.student\.(import|export)':\s*'当前后端尚未提供/)
})

test('A1 old dormitory route remains an honest overview of real workspaces', () => {
  assert.match(dormOverview, /住宿运行结论/)
  assert.match(dormOverview, /待办工作区/)
  assert.match(dormOverview, /房态与入住入口/)
  assert.match(dormOverview, /聚合待办数：后端未配置/)
  for (const path of ['resource', 'checkin', 'transfer', 'check', 'exception']) {
    assert.ok(dormOverview.includes(`/admin/student-affairs/dorm/${path}`), `${path} workspace must remain reachable`)
  }
})
