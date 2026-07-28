from __future__ import annotations

from pathlib import Path


def insert_once(text: str, anchor: str, insertion: str, label: str) -> str:
    if insertion.strip() in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"missing anchor for {label}: {anchor[:100]!r}")
    return text.replace(anchor, anchor + insertion, 1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"missing replacement anchor for {label}: {old[:120]!r}")
    return text.replace(old, new, 1)


def patch_student_portal() -> None:
    path = Path("student-portal/src/services/request.js")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "const INTERNSHIP_BATCH_KEY = 'student_portal_internship_batch_v1'\nconst API_PREFIX",
        "const INTERNSHIP_BATCH_KEY = 'student_portal_internship_batch_v1'\nconst GD_TEMP_FILES_KEY = 'sp_gd_temp_files_v1'\nconst API_PREFIX",
        "student portal graduation temp key",
    )
    text = replace_once(
        text,
        "    localStorage.removeItem(INTERNSHIP_BATCH_KEY)\n  } catch",
        "    localStorage.removeItem(INTERNSHIP_BATCH_KEY)\n    localStorage.removeItem(GD_TEMP_FILES_KEY)\n  } catch",
        "student portal clear graduation temps",
    )
    helper_block = '''\n\nfunction readTempFiles() {
  try { return JSON.parse(localStorage.getItem(GD_TEMP_FILES_KEY) || '{}') || {} } catch { return {} }
}
function writeTempFiles(value) {
  try { localStorage.setItem(GD_TEMP_FILES_KEY, JSON.stringify(value || {})) } catch { /* ignore */ }
}
function rememberTempFile(fileId) {
  if (!fileId) return
  const value = readTempFiles()
  value[String(fileId)] = Date.now()
  writeTempFiles(value)
}
function markTempFilesBound(fileIds) {
  const ids = new Set((fileIds || []).map(String))
  if (!ids.size) return
  const value = readTempFiles()
  ids.forEach((id) => delete value[id])
  writeTempFiles(value)
}

/** 学生放弃一个未绑定的毕业设计临时材料（已绑定的会 409，忽略即可）。 */
export async function abandonTemporaryGraduationMaterial(fileId) {
  if (!fileId) return null
  const data = await request(`/portal/graduation/materials/${fileId}/abandon`, { method: 'POST' })
  const value = readTempFiles()
  delete value[String(fileId)]
  writeTempFiles(value)
  return data
}

let cleanupStarted = false
/** 每个页面会话只清一次：超过 24 小时仍未绑定业务的毕设临时材料自动放弃。 */
function cleanupStaleGraduationTemps() {
  if (cleanupStarted) return
  cleanupStarted = true
  const now = Date.now()
  const cutoff = 24 * 60 * 60 * 1000
  const value = readTempFiles()
  Object.entries(value).forEach(([fileId, at]) => {
    if (now - Number(at || 0) < cutoff) return
    abandonTemporaryGraduationMaterial(fileId).catch(() => { /* 已绑定文件会 409 */ })
  })
}
'''
    text = insert_once(
        text,
        "}\n\nfunction selectedInternshipBatch(path)",
        helper_block + "\nfunction selectedInternshipBatch(path)",
        "student portal graduation temp helpers",
    )
    # insert_once above duplicates function name from anchor; normalize once.
    text = text.replace(
        "function selectedInternshipBatch(path)\nfunction selectedInternshipBatch(path)",
        "function selectedInternshipBatch(path)",
    )
    text = replace_once(
        text,
        "} = {}) {\n  const headers = { 'Content-Type': 'application/json' }",
        "} = {}) {\n  cleanupStaleGraduationTemps()\n  const headers = { 'Content-Type': 'application/json' }",
        "student portal request cleanup",
    )
    text = replace_once(
        text,
        "  if (payload.code !== 0) {\n    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e\n  }\n  return payload.data\n}\n\n/**\n * 学生门户的文件上传",
        "  if (payload.code !== 0) {\n    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e\n  }\n  const cleanPath = String(path || '').split('?')[0]\n  if (method === 'POST' && ['/portal/graduation/proposal', '/portal/graduation/final'].includes(cleanPath)) {\n    markTempFilesBound(body && body.attachments)\n  }\n  return payload.data\n}\n\n/**\n * 学生门户的文件上传",
        "student portal mark bound graduation files",
    )
    text = replace_once(
        text,
        "export async function uploadFile(path, file, { auth = true, _retried = false } = {}) {\n  const headers = {}",
        "export async function uploadFile(path, file, { auth = true, _retried = false } = {}) {\n  cleanupStaleGraduationTemps()\n  const headers = {}",
        "student portal upload cleanup",
    )
    text = replace_once(
        text,
        "  if (payload.code !== 0) {\n    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e\n  }\n  return payload.data\n}\n\n/** 下载受业务关系保护的文件",
        "  if (payload.code !== 0) {\n    const e = new Error(payload.message || `业务错误 ${payload.code}`); e.code = payload.code; e.biz = true; throw e\n  }\n  if (String(path).includes('bizType=GRADUATION_MATERIAL') && payload.data?.fileId) {\n    rememberTempFile(payload.data.fileId)\n  }\n  return payload.data\n}\n\n/** 下载受业务关系保护的文件",
        "student portal remember graduation upload",
    )
    path.write_text(text, encoding="utf-8")


def patch_miniapp() -> None:
    path = Path("miniapp/src/services/request.js")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "const INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'\nconst state",
        "const INTERNSHIP_BATCH_KEY = 'gx_student_internship_batch_v1'\nconst GD_TEACHER_BATCH_KEY = 'gx_gd_teacher_batch_v1'\nconst state",
        "miniapp teacher graduation key",
    )
    teacher_storage = '''\n\n/** 教师小程序当前毕业设计批次。对象形状：{ id, name, status }。 */
export function setTeacherGraduationBatch(batch) {
  try {
    const value = batch && batch.id
      ? { id: String(batch.id), name: batch.name || batch.batchName || '', status: batch.status || '' }
      : null
    if (value) uni.setStorageSync(GD_TEACHER_BATCH_KEY, value)
    else uni.removeStorageSync(GD_TEACHER_BATCH_KEY)
  } catch (e) { /* 忽略本地缓存失败 */ }
}

export function getTeacherGraduationBatch() {
  try {
    const value = uni.getStorageSync(GD_TEACHER_BATCH_KEY)
    return value && value.id ? value : null
  } catch (e) { return null }
}
'''
    text = insert_once(
        text,
        "export function getRefreshToken() {\n  try { return uni.getStorageSync(REFRESH_KEY) || '' } catch (e) { return '' }\n}",
        teacher_storage,
        "miniapp teacher graduation storage",
    )
    text = replace_once(
        text,
        "export function clearTokens() {\n  setToken('')\n  setRefreshToken('')\n}",
        "export function clearTokens() {\n  setToken('')\n  setRefreshToken('')\n  setTeacherGraduationBatch(null)\n}",
        "miniapp clear teacher graduation batch",
    )
    gd_block = '''\n\n/* ── 教师毕业设计批次上下文与分页 ── */
const GD_TEACHER_PREFIX = '/mobile/teacher/graduation'
const GD_TASKBOOK_PATH = `${GD_TEACHER_PREFIX}/taskbooks`
const GD_TEACHER_PAGED_PATHS = new Set([
  GD_TEACHER_PREFIX,
  `${GD_TEACHER_PREFIX}/my-students`,
  `${GD_TEACHER_PREFIX}/midterm/queue`,
  `${GD_TEACHER_PREFIX}/reviews/my`,
  `${GD_TEACHER_PREFIX}/defense/arrangements`,
  `${GD_TEACHER_PREFIX}/grade/queue`,
  `${GD_TEACHER_PREFIX}/choices/pending`,
  `${GD_TEACHER_PREFIX}/change-requests/pending`,
  GD_TASKBOOK_PATH,
  `${GD_TEACHER_PREFIX}/defense/pending`
])
const GD_MAX_AUTO_PAGES = 20

function appendQuery(path, key, value) {
  if (new RegExp(`[?&]${key}=`).test(path)) return path
  return `${path}${path.includes('?') ? '&' : '?'}${key}=${encodeURIComponent(value)}`
}
function replaceQuery(path, key, value) {
  const re = new RegExp(`([?&])${key}=[^&]*`)
  if (re.test(path)) return path.replace(re, `$1${key}=${encodeURIComponent(value)}`)
  return appendQuery(path, key, value)
}
function withTeacherGraduationContext(path) {
  if (!path.startsWith(GD_TEACHER_PREFIX) || path.startsWith(`${GD_TEACHER_PREFIX}/batches`)) return path
  const batch = getTeacherGraduationBatch()
  if (!batch || !batch.id) throw { code: 422001, biz: true, message: '请先选择毕业设计批次' }
  let value = appendQuery(path, 'batchId', batch.id)
  const pathname = value.split('?')[0]
  if (GD_TEACHER_PAGED_PATHS.has(pathname)) {
    value = appendQuery(value, 'page', 1)
    value = appendQuery(value, 'pageSize', 100)
  }
  return value
}
function attachPageMeta(items, meta) {
  Object.defineProperty(items, '_pageMeta', { value: meta, enumerable: false, configurable: true })
  return items
}
function normalizeTeacherGraduationData(path, data) {
  const pathname = path.split('?')[0]
  if (pathname === GD_TASKBOOK_PATH && data && Array.isArray(data.items)) {
    return { list: data.items, total: data.total || data.items.length, page: data.page || 1,
      pageSize: data.pageSize || data.items.length, hasMore: !!data.hasMore, truncated: !!data.truncated }
  }
  if (GD_TEACHER_PAGED_PATHS.has(pathname) && pathname !== GD_TEACHER_PREFIX && data && Array.isArray(data.items)) {
    return attachPageMeta(data.items, { total: data.total || data.items.length, page: data.page || 1,
      pageSize: data.pageSize || data.items.length, hasMore: !!data.hasMore, truncated: !!data.truncated })
  }
  return data
}
async function collectTeacherGraduationPages(path, first, options) {
  const pathname = path.split('?')[0]
  if (!GD_TEACHER_PAGED_PATHS.has(pathname) || !first || !first.hasMore) {
    return normalizeTeacherGraduationData(path, first)
  }
  let page = Number(first.page || 1)
  let current = first
  let calls = 1
  if (pathname === GD_TEACHER_PREFIX) {
    const merged = { ...first, students: [...(first.students || [])],
      reviewDetail: [...(first.reviewDetail || [])], finalDetail: [...(first.finalDetail || [])] }
    while (current.hasMore && calls < GD_MAX_AUTO_PAGES) {
      page += 1; calls += 1
      current = await realRequest(replaceQuery(path, 'page', page), { ...options, _rawPage: true })
      merged.students.push(...((current && current.students) || []))
      merged.reviewDetail.push(...((current && current.reviewDetail) || []))
      merged.finalDetail.push(...((current && current.finalDetail) || []))
    }
    merged.hasMore = !!(current && current.hasMore)
    merged.truncated = merged.hasMore
    return merged
  }
  const items = [...(first.items || [])]
  while (current.hasMore && calls < GD_MAX_AUTO_PAGES) {
    page += 1; calls += 1
    current = await realRequest(replaceQuery(path, 'page', page), { ...options, _rawPage: true })
    items.push(...((current && current.items) || []))
  }
  return normalizeTeacherGraduationData(path, { ...first, items, total: Number(first.total || items.length),
    page: 1, pageSize: items.length, hasMore: !!(current && current.hasMore),
    truncated: !!(current && current.hasMore) })
}
'''
    text = insert_once(
        text,
        "function selectedInternshipBatchId(path) {\n  if (!String(path || '').startsWith('/mobile/internship')) return ''\n  try {\n    const value = String(uni.getStorageSync(INTERNSHIP_BATCH_KEY) || '').trim()\n    return /^\\d+$/.test(value) ? value : ''\n  } catch (e) {\n    return ''\n  }\n}",
        gd_block,
        "miniapp teacher graduation paging",
    )
    text = replace_once(
        text,
        "export function realRequest(path, { method = 'GET', data, auth = true, _retried = false } = {}) {\n  return new Promise((resolve, reject) => {",
        "export function realRequest(path, { method = 'GET', data, auth = true, _retried = false, _rawPage = false } = {}) {\n  let effectivePath\n  try { effectivePath = withTeacherGraduationContext(path) } catch (e) { return Promise.reject(e) }\n  return new Promise((resolve, reject) => {",
        "miniapp real request context signature",
    )
    text = replace_once(
        text,
        "url: ENV.apiBaseUrl + ENV.apiPrefix + path,",
        "url: ENV.apiBaseUrl + ENV.apiPrefix + effectivePath,",
        "miniapp effective graduation path",
    )
    text = replace_once(
        text,
        ".then(() => realRequest(path, { method, data, auth, _retried: true }))",
        ".then(() => realRequest(path, { method, data, auth, _retried: true, _rawPage }))",
        "miniapp retry raw page",
    )
    text = replace_once(
        text,
        "        state.warned = false\n        resolve(body.data)",
        "        state.warned = false\n        if (_rawPage || method !== 'GET') { resolve(body.data); return }\n        collectTeacherGraduationPages(effectivePath, body.data, { method, data, auth, _retried })\n          .then(resolve).catch(reject)",
        "miniapp collect graduation pages",
    )
    path.write_text(text, encoding="utf-8")


def audit() -> None:
    student = Path("student-portal/src/services/request.js").read_text(encoding="utf-8")
    for needle in ("refreshOnce", "X-Internship-Batch-Id", "GD_TEMP_FILES_KEY", "cleanupStaleGraduationTemps", "rememberTempFile"):
        assert needle in student, needle
    mini = Path("miniapp/src/services/request.js").read_text(encoding="utf-8")
    for needle in ("realUpload", "realDownload", "_refreshOnce", "X-Internship-Batch-Id", "GD_TEACHER_BATCH_KEY", "withTeacherGraduationContext", "collectTeacherGraduationPages"):
        assert needle in mini, needle


if __name__ == "__main__":
    patch_student_portal()
    patch_miniapp()
    audit()
    print("request conflict resolution passed", flush=True)
