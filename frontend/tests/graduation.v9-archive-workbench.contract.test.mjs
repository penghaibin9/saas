import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

const view = readFileSync(new URL('../src/modules/graduation/views/GraduationRiskArchiveView.vue', import.meta.url), 'utf8')
const riskService = readFileSync(new URL('../../backend/app/modules/graduation/services/graduation_risk_service.py', import.meta.url), 'utf8')

test('U7 archive missing-item links preserve exact student and batch/source context', () => {
  assert.match(view, /name:\s*'graduation-student-detail'/)
  assert.match(view, /params:\s*\{ id: String\(sid\) \}/)
  assert.match(view, /source:\s*'archive'/)
  assert.match(view, /batchId:\s*String\(this\.batchStore\.selectedBatchId\)/)
  assert.match(view, /name\.includes\('任务书'\).*tab = 'taskbook'/s)
  assert.match(view, /name\.includes\('开题'\).*tab = 'proposals'/s)
  assert.match(view, /name\.includes\('中期'\).*tab = 'midterm'/s)
  assert.match(view, /name\.includes\('指导'\).*tab = 'guidance'/s)
  assert.match(view, /name\.includes\('查重'\).*tab = 'plagiarisms'/s)
  assert.match(view, /name\.includes\('评阅'\).*tab = 'review'/s)
  assert.match(view, /name\.includes\('成果'\).*tab = 'finals'/s)
  assert.match(view, /missingItem:\s*name/)
  assert.match(view, /returnTo:\s*this\.archiveReturnTo\(\)/)

  for (const old of [
    '/admin/graduation/process?panel=taskbook',
    '/admin/graduation/process?panel=midterm',
    '/admin/graduation/defense-grade?panel=review',
    '/admin/graduation/finals'
  ]) assert.ok(!view.includes(old), `stale broad deep-link remains: ${old}`)
})

test('U7 dirty archive rows are visibly read-only and preview reasons are human-readable', () => {
  assert.ok(view.includes("selectedArchive.dataAnomaly ? '查看学生档案 →' : '去补齐 →'"))
  assert.ok(view.includes('历史主档异常，当前归档记录仅允许只读查看'))
  assert.ok(view.includes("dirty_data: '历史主档异常（只读）'"))
  assert.match(
    view,
    /<span v-if="selectedArchive\.dataAnomaly"[^>]*>历史主档异常，当前归档记录仅允许只读查看<\/span>\s*<template v-else>[\s\S]*?@click="doGenerate\(selectedArchive\)"[\s\S]*?@click="doSubmit\(selectedArchive\)"[\s\S]*?@click="doFile\(selectedArchive\)"[\s\S]*?@click="askRejectArchive\(selectedArchive\)"[\s\S]*?<\/template>/
  )
})

test('G7 projects the canonical 13-risk catalog from server byCode instead of a browser-owned rule table', () => {
  assert.match(view, /graduationRiskArchiveApi\.getRiskStats\(\{ batchId \}\)/)
  assert.match(view, /Array\.isArray\(this\.riskStats\?\.byCode\)/)
  assert.match(view, /riskCode:\s*String\(row\?\.riskCode/)
  assert.match(view, /riskName:\s*String\(row\?\.riskName/)
  assert.ok(!view.includes('RISK_RULE_CATALOG'), 'risk meanings must not be redefined in the browser')
  assert.match(view, /风险队列仍按服务端返回展示，不使用前端静态目录替代/)

  for (const code of Array.from({ length: 13 }, (_, index) => `GD-R${String(index + 1).padStart(2, '0')}`)) {
    assert.ok(riskService.includes(`"${code}"`), `canonical server risk missing: ${code}`)
  }
  assert.match(riskService, /"byCode": by_code/)
})

test('G7 list stats and scan reads are latest-wins and batch-bound', () => {
  for (const token of ['riskLoadToken', 'scanToken', 'lastScanToken', 'riskStatsToken']) {
    assert.ok(view.includes(token), `missing stale-response guard ${token}`)
  }
  assert.match(view, /token !== this\.riskStatsToken \|\| batchId !== String\(this\.batchStore\.selectedBatchId/)
  assert.match(view, /token !== this\.riskLoadToken/)
  assert.match(view, /snapshot\.batchId !== String\(this\.batchStore\.selectedBatchId/)
  assert.match(view, /type: 'RISK_SCAN'/)
  assert.match(view, /routeQuery: this\.buildPanelQuery\('risk'\)/)
})

test('G8 freezes one preview token and passes it explicitly into the matching execute command', () => {
  assert.match(view, /archiveCommandSnapshot: null/)
  assert.match(view, /phase: 'READY'/)
  assert.match(view, /previewToken: data\.previewToken/)
  assert.match(view, /archiveBatchNo: data\.archiveBatchNo \|\| ''/)
  assert.match(view, /phase: 'EXECUTING'/)
  assert.match(view, /consumed: true/)
  assert.match(view, /body = \{ previewToken: executing\.previewToken, archiveBatchNo: executing\.archiveBatchNo \|\| undefined \}/)
  assert.match(view, /batchFileArchive\(params, body\)/)
  assert.match(view, /batchGenerateArchive\(params, body\)/)
  assert.match(view, /原始令牌不进入界面文本/)
})

test('G8 invalidates page credentials on cancel route batch and execute, and never blind-retries an unknown write', () => {
  assert.match(view, /onConfirmCancel\(\)/)
  assert.match(view, /invalidateArchivePreview\('user-cancel'\)/)
  assert.match(view, /invalidateArchivePreview\('batch-change'\)/)
  assert.match(view, /invalidateArchivePreview\('route-leave'\)/)
  assert.match(view, /invalidateArchivePreview\('executed'\)/)
  assert.match(view, /beforeRouteLeave\(to, from, next\)/)
  assert.match(view, /next\(false\)/)
  assert.match(view, /Number\(res\.code\) === 503002/)
  assert.match(view, /不要直接重复提交/)
  assert.match(view, /刷新台账核对/)
})

test('G8 single-student archive writes freeze object batch and return context before calling canonical APIs', () => {
  assert.match(view, /createSingleArchiveSnapshot\(action, row\)/)
  assert.match(view, /gdStudentId: String\(row\?\.gdStudentId/)
  assert.match(view, /batchId: String\(this\.batchStore\.selectedBatchId/)
  assert.match(view, /routeQuery: this\.buildPanelQuery\('archive'\)/)
  assert.match(view, /generateArchive\(snapshot\.gdStudentId, \{ batchId: snapshot\.batchId \}\)/)
  assert.match(view, /submitArchive\(snapshot\.gdStudentId, \{ batchId: snapshot\.batchId \}\)/)
  assert.match(view, /fileArchive\(snapshot\.gdStudentId, snapshot\.archiveBatchNo \|\| null, \{ batchId: snapshot\.batchId \}\)/)
  assert.match(view, /rejectArchive\(snapshot\.gdStudentId, reason \|\| '', \{ batchId: snapshot\.batchId \}\)/)
})
