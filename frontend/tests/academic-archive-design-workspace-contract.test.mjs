import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const read = (name) => readFile(new URL(`../src/modules/academicAffairs/views/${name}`, import.meta.url), 'utf8')
const readApi = () => readFile(new URL('../src/modules/academicAffairs/api/academic-affairs.api.js', import.meta.url), 'utf8')

test('AA-260/262/264/265 archive console keeps the 13-domain workflow and object responsibility chain', async () => {
  const source = await read('AaArchiveConsoleView.vue')
  for (const token of [
    ':title="pageTitle"',
    "pageTitle(){return this.$route.query?.entry==='batch'?'批量归档':'归档与封存'}",
    '当前业务对象 · 学期归档批次',
    '当前责任',
    '当前阻断',
    '下一责任岗位',
    '十三域检查',
    '缺失处理',
    '正式封存',
    '受控纠错',
    'ARCHIVE_DOMAINS.length',
    'AaArchiveCorrectionWorkspace'
  ]) assert.ok(source.includes(token), `missing archive workflow token: ${token}`)
})

test('AA-261 keeps BLOCKED/UNKNOWN honest and routes the first missing domain to its owner', async () => {
  const [source, api] = await Promise.all([read('ArchivePrecheckView.vue'), readApi()])
  for (const token of [
    'title="归档缺失提醒"',
    "const DOMAIN_RESULTS = new Set(['PASS','BLOCKED','UNKNOWN','NOT_APPLICABLE'])",
    'blockedDomainRows',
    'firstBlockingDomain',
    '去处理首要阻断',
    'FALLBACK_ROUTE'
  ]) assert.ok(source.includes(token), `missing archive precheck token: ${token}`)
  assert.match(source, /termId\(\) \{ if \(!this\.syncingResolvedTerm\) this\.load\(\) \}/, 'resolved default term must not trigger a duplicate 13-domain scan')
  assert.match(api, /archive\/precheck[^\n]+timeoutMs: 30000/, '13-domain precheck needs a bounded large-dataset read budget')
})

test('AA-263 export binds an archived batch, purpose and server audit receipt before download completion', async () => {
  const source = await read('ArchiveExportView.vue')
  for (const token of [
    'title="归档导出"',
    '导出范围与用途',
    '三种范围不要混淆',
    '当前业务对象 · 学期归档批次',
    '至少5个字',
    'const before = await api.getBatch(frozen.batchId)',
    'await this.loadLog(frozen.batchId)',
    '正式下载记录待核实；请勿重复下载'
  ]) assert.ok(source.includes(token), `missing archive export token: ${token}`)
})
