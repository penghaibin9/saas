const GRADE_STATES = Object.freeze({
  RESOLVED: { label: '来源已核对', type: 'success' },
  NOT_GENERATED: { label: '尚未生成正式成绩', type: 'default' },
  SOURCE_GRADE_UNRESOLVED: { label: '来源成绩待治理', type: 'warning' },
  CHAIN_INVALID: { label: '成绩版本链异常', type: 'danger' },
  NOT_EFFECTIVE_FAILED: { label: '已不再是有效挂科成绩', type: 'danger' }
})

const EVIDENCE_STATES = Object.freeze({
  VALID: { label: '证据清单有效', type: 'success' },
  MISSING: { label: '证据清单缺失', type: 'warning' },
  INVALID: { label: '证据已经失效', type: 'danger' }
})

export function stateMeta(state, kind = 'grade') {
  const key = String(state || '').toUpperCase()
  const source = kind === 'evidence' ? EVIDENCE_STATES : GRADE_STATES
  return source[key] || { label: '正式状态待核对', type: 'warning' }
}

export function hasFormalAction(row, action) {
  const actions = Array.isArray(row?.allowedActions) ? row.allowedActions : []
  return actions.some((value) => String(value || '').toUpperCase() === String(action || '').toUpperCase())
}

export function rowRevision(row, kind) {
  const value = kind === 'retake' ? row?.applicationVersion : row?.exemptionVersion
  if (value === null || value === undefined || value === '') return null
  return Number.isInteger(Number(value)) && Number(value) >= 0 ? Number(value) : null
}

export function formatMoment(value) {
  if (!value) return '时间未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

export function shortHash(value) {
  const text = String(value || '').trim()
  return text ? `${text.slice(0, 12)}${text.length > 12 ? '…' : ''}` : '未记录'
}

export function gradeIdentity(grade) {
  if (!grade?.gradeId) return '未返回正式成绩ID'
  const parts = [`成绩 #${grade.gradeId}`]
  if (grade.courseCode) parts.push(grade.courseCode)
  if (grade.courseVersion != null) parts.push(`课程V${grade.courseVersion}`)
  if (grade.attemptNo != null) parts.push(`第${grade.attemptNo}次修读`)
  return parts.join(' · ')
}

export function gradeResult(grade) {
  if (!grade?.gradeId) return '正式成绩事实待核对'
  const score = grade.score == null ? '无数值分' : `${grade.score}分`
  return `${score} · ${grade.passStatus || '通过状态待核对'} · ${grade.recordStatus || '记录状态待核对'}`
}

export function gradeSource(grade) {
  if (!grade?.gradeId) return '操作来源未返回'
  const source = grade.sourceBizType || grade.source || '来源待核对'
  const id = grade.sourceBizId ? ` #${grade.sourceBizId}` : ''
  const policy = grade.effectivePolicyCode
    ? ` · ${grade.effectivePolicyCode}${grade.effectivePolicyVersion == null ? '' : ` V${grade.effectivePolicyVersion}`}`
    : ''
  return `${source}${id}${policy}`
}

export function evidenceVersion(file) {
  if (file?.fileVersionId && file?.fileVersionNo != null) return `文件版本 V${file.fileVersionNo} · #${file.fileVersionId}`
  if (file?.versionCoverage === 'FILE_OBJECT_SNAPSHOT_ONLY' && file?.frozenFileObjectVersion != null) {
    return `内容快照 r${file.frozenFileObjectVersion}（未登记文档版本）`
  }
  return '文件版本未登记'
}

export function evidenceFiles(row) {
  return Array.isArray(row?.evidenceFiles) ? row.evidenceFiles.filter((item) => item?.fileId) : []
}
