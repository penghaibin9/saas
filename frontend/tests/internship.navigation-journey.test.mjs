import test from 'node:test'
import assert from 'node:assert/strict'
import { internshipBatchSwitch, internshipLocation, internshipWorkspaces, withInternshipBatch } from '../src/modules/internship/navigation.js'
import { workspaceCurrentPage, workspacePages } from '../src/components/workspace/teacherWorkspace.js'

test('navigation never drops workflow parameters, explicit batch, or hash', () => {
  assert.deepEqual(withInternshipBatch('/admin/internship/applications?status=PENDING_REVIEW&type=SELF_ARRANGED#record', 'batch 2'), {
    path: '/admin/internship/applications', query: { status: 'PENDING_REVIEW', type: 'SELF_ARRANGED', batchId: 'batch 2' }, hash: '#record'
  })
  assert.equal(withInternshipBatch('/admin/internship/reports/24?batchId=original', 'new').query.batchId, 'original')
  assert.deepEqual(withInternshipBatch('/admin/employment/students?source=internship', 'batch'), {
    path: '/admin/employment/students', query: { source: 'internship' }, hash: ''
  })
})

test('batch, paging and filters do not break menu identity or the risk branch', () => {
  assert.equal(internshipLocation('/admin/internship/students?batchId=17&panel=mentor&page=2').workspaceKey, 'in-match-assign')
  assert.equal(internshipLocation('/admin/internship/students?panel=eligibility&batchId=17').workspaceKey, 'in-batch-rules')
  assert.equal(internshipLocation('/admin/internship/compliance?tab=incidents&batchId=17').workspaceKey, 'in-risk')
  assert.equal(internshipLocation('/admin/internship/compliance?batchId=17&tab=overview').workspaceKey, 'in-match-assign')
  assert.equal(internshipLocation('/admin/internship/changes?panel=pending&batchId=17').workspaceKey, 'in-risk')
  assert.equal(internshipLocation('/admin/internship/process-reports/24?batchId=17').workspaceKey, 'in-attendance-leave')
})

test('missing permissions produce no business navigation, read-only users retain view pages', () => {
  assert.deepEqual(internshipWorkspaces(null), [])
  assert.deepEqual(internshipWorkspaces({ permissionPatterns: ['*'], permissionServiceError: 'unavailable' }), [])
  const readOnly = internshipWorkspaces({ permissionPatterns: ['internship.report.view', 'internship.insurance.view', 'internship.archive.view'], ctxKey: 'reader' })
  assert.deepEqual(readOnly.map((w) => w.key), ['in-match-assign', 'in-attendance-leave', 'in-employment-archive-stats'])
  assert.equal(readOnly[0].path, '/admin/internship/insurance')
  assert.equal(readOnly[1].path, '/admin/internship/reports?panel=review')
  assert.equal(readOnly.flatMap((w) => w.children).some((l) => l.permissionKey.endsWith('.manage')), false)
})

test('switching batches exits object details and clears the previous selection but preserves list filters', () => {
  assert.deepEqual(internshipBatchSwitch('/admin/internship/process-reports/24?batchId=old&queueKey=old-queue', 'new'), {
    path: '/admin/internship/reports', query: { panel: 'review', batchId: 'new' }, hash: ''
  })
  assert.deepEqual(internshipBatchSwitch('/admin/internship/students?panel=mentor&batchId=old&page=8&studentId=24#record', 'new'), {
    path: '/admin/internship/students', query: { panel: 'mentor', batchId: 'new' }, hash: ''
  })
  assert.equal(internshipBatchSwitch('/admin/internship/batches/new?batchId=old', 'new').path, '/admin/internship/batches')
})

test('formal volunteer details keep the placement menu and cannot carry a campaign across batches', () => {
  assert.equal(internshipLocation('/admin/internship/volunteer-review/7?campaignId=2&batchId=1&section=materials').workspaceKey, 'in-match-assign')
  assert.deepEqual(internshipBatchSwitch('/admin/internship/volunteer-review?campaignId=2&batchId=1&status=ALL&page=3&section=materials', '9'), {
    path: '/admin/internship/volunteer-review', query: { status: 'ALL', batchId: '9' }, hash: ''
  })
})

test('all visible internship menu entries retain their identity with batch and paging context', () => {
  const pages = workspacePages(internshipWorkspaces({ permissionPatterns: ['*'] }))
  for (const page of pages) {
    const destination = new URL(page.path, 'https://local.invalid')
    destination.searchParams.set('batchId', '9007199254740999')
    destination.searchParams.set('page', '3')
    assert.equal(workspaceCurrentPage(pages, destination.pathname + destination.search).id, page.id, page.title)
  }
})

test('process report details stay under report review even with report-only permissions', () => {
  const pages = workspacePages(internshipWorkspaces({ permissionPatterns: ['internship.report.view'] }))
  for (const path of ['/admin/internship/reports/9?batchId=1', '/admin/internship/process-reports/9?batchId=1']) {
    assert.equal(workspaceCurrentPage(pages, path).title, '报告与任务')
  }
})

test('switching batches clears appeal, file and form state before a new child page mounts', () => {
  const target = internshipBatchSwitch('/admin/internship/scores?stage=appeal&batchId=1&appealId=99&fromAppeal=88&appealPage=3&id=7&mode=compute&file=4&receipt=created&keyword=周同学', '2')
  assert.deepEqual(target, { path: '/admin/internship/scores', query: { stage: 'appeal', keyword: '周同学', batchId: '2' }, hash: '' })
  assert.equal(internshipBatchSwitch('/admin/internship/scores?mode=new&batchId=1', '2').query.mode, undefined)
})
