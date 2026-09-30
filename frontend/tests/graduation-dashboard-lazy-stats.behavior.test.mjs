import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const dashboard = readFileSync(resolve(root, 'src/modules/graduation/views/GraduationDashboardView.vue'), 'utf8')
const service = readFileSync(resolve(root, '../backend/app/modules/graduation/services/graduation_service.py'), 'utf8')

test('graduation dashboard defers collapsed cross-module statistics', () => {
  assert.match(dashboard, /@toggle="onModuleStatsToggle"/)
  assert.match(dashboard, /graduationRiskArchiveApi\.getOverviewStats/)
  assert.match(dashboard, /async loadModuleStats\(\)/)
})

test('graduation dashboard summary does not synchronously aggregate cross-module statistics', () => {
  const dashboardService = service.slice(service.indexOf('def get_dashboard('))
  assert.doesNotMatch(dashboardService, /stats_svc\.overview_stats/)
  assert.match(dashboardService, /"moduleStatsDeferred": True/)
})
