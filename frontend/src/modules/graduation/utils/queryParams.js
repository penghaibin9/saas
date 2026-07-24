/**
 * 毕业设计列表 / 导出共用查询参数构造。
 * 空字符串不传；布尔字符串转 boolean；page/pageSize 仅列表使用。
 */

function omitEmpty(obj) {
  const out = {}
  Object.keys(obj || {}).forEach((k) => {
    const v = obj[k]
    if (v === '' || v === null || v === undefined) return
    out[k] = v
  })
  return out
}

function coerceBool(v) {
  if (v === true || v === 'true') return true
  if (v === false || v === 'false') return false
  return undefined
}

/**
 * 毕设学生统一查询对象（列表与导出共用）。
 * @param {object} filters 页面筛选
 * @param {{ page?: number, pageSize?: number, batchId?: string }} extra
 */
export function buildStudentQuery(filters = {}, extra = {}) {
  const f = { ...filters }
  const boolKeys = ['hasTopic', 'hasDefenseGroup', 'materialComplete']
  boolKeys.forEach((k) => {
    const b = coerceBool(f[k])
    if (b === undefined) delete f[k]
    else f[k] = b
  })
  const batchId = extra.batchId !== undefined ? extra.batchId : f.batchId
  const p = omitEmpty({
    keyword: f.keyword,
    batchId,
    classId: f.classId,
    stage: f.stage,
    riskLevel: f.riskLevel,
    advisorName: f.advisorName,
    hasTopic: f.hasTopic,
    eligibility: f.eligibility,
    studentGroup: f.studentGroup,
    hasDefenseGroup: f.hasDefenseGroup,
    gradQualStatus: f.gradQualStatus,
    materialComplete: f.materialComplete,
    archiveView: f.archiveView
  })
  if (extra.page != null) p.page = extra.page
  if (extra.pageSize != null) p.pageSize = extra.pageSize
  return p
}

/** 题目库统一查询 */
export function buildTopicLibQuery(filters = {}, extra = {}) {
  const f = { ...filters }
  const batchId = extra.batchId !== undefined ? extra.batchId : f.batchId
  const p = omitEmpty({
    keyword: f.keyword,
    batchId,
    sourceType: f.sourceType,
    category: f.category && f.category !== '__uncat__' ? f.category : undefined,
    missingCategory: f.category === '__uncat__' || f.missingCategory === 'true' || f.missingCategory === true ? true : undefined,
    reviewStatus: f.reviewStatus,
    status: f.status,
    isFull: coerceBool(f.isFull),
    archiveView: f.archiveView,
    hasRequirements: coerceBool(f.hasRequirements),
    hasAttachments: coerceBool(f.hasAttachments),
    topicId: f.topicId,
    action: f.action
  })
  if (extra.page != null) p.page = extra.page
  if (extra.pageSize != null) p.pageSize = extra.pageSize
  return p
}

/** 开题 / 成果统一查询 */
export function buildMaterialQuery(filters = {}, extra = {}) {
  const f = { ...filters }
  const batchId = extra.batchId !== undefined ? extra.batchId : f.batchId
  const p = omitEmpty({
    keyword: f.keyword,
    status: f.status,
    batchId
  })
  if (extra.page != null) p.page = extra.page
  if (extra.pageSize != null) p.pageSize = extra.pageSize
  return p
}

/** 风险归档统一查询 */
export function buildRiskArchiveQuery(filters = {}, extra = {}) {
  const f = { ...filters }
  const batchId = extra.batchId !== undefined ? extra.batchId : f.batchId
  const p = omitEmpty({
    keyword: f.keyword,
    status: f.status,
    level: f.level,
    riskCode: f.riskCode,
    batchId
  })
  if (extra.page != null) p.page = extra.page
  if (extra.pageSize != null) p.pageSize = extra.pageSize
  return p
}

/** 导出文件名片段：批次名 + 视图 */
export function exportFilenameHint(batchName, viewLabel) {
  const b = (batchName || '未选批次').replace(/[\\/:*?"<>|]/g, '_')
  const v = (viewLabel || '台账').replace(/[\\/:*?"<>|]/g, '_')
  return `${b}_${v}`
}
