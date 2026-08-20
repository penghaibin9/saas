import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewUrl = new URL('../src/modules/academicAffairs/views/AaEvaluationConsoleView.vue', import.meta.url)

test('D-W3 评价高风险确认必须显示明确动作并防重复提交', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    ':confirm-text="confirmText"',
    ':submitting="confirmSubmitting"',
    "confirmText: '确认操作'",
    'if (this.confirmSubmitting || !this.pendingAction) return',
    'this.confirmSubmitting = true',
    'this.confirmSubmitting = false',
    'if (ok) {',
    'this.confirmVisible = false'
  ]) assert.ok(source.includes(token), `missing evaluation confirmation guard: ${token}`)
})

test('D-W3 申诉两级审核保留真实意见与明确审核动作', async () => {
  const source = await readFile(viewUrl, 'utf8')
  for (const token of [
    "row.status === 'SUBMITTED' ? '学院初审通过' : '教务终审通过'",
    "const stageLabel = isCollegeStage ? '学院初审' : '教务终审'",
    'confirmReasonLabel = `${stageLabel}意见（≥5 字）`',
    "confirmReasonLabel = '驳回原因（≥5 字）'",
    "api.reviewAppeal(row.appealId, 'RESOLVE', note)",
    "api.reviewAppeal(id, 'REJECT', String(reason || '').trim())"
  ]) assert.ok(source.includes(token), `missing evaluation appeal audit token: ${token}`)
})

test('D-W3 评价控制台窄屏必须从双栏收成单栏且页签可横向滚动', async () => {
  const source = await readFile(viewUrl, 'utf8')
  assert.match(source, /\.aaev-layout \{ display: grid; grid-template-columns: 280px minmax\(0, 1fr\); gap: 16px; \}/)
  assert.match(source, /@media \(max-width: 900px\)/)
  assert.match(source, /\.aaev-layout \{ grid-template-columns: 1fr; \}/)
  assert.match(source, /@media \(max-width: 640px\)/)
  assert.match(source, /\.aaev-tabs \{ overflow-x: auto; \}/)
  assert.match(source, /\.aaev-tab \{ flex: 0 0 auto; white-space: nowrap; \}/)
})