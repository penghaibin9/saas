import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

const sdk = read('src/services/fileSdk.js')
const teacher = read('src/pages/teacher/graduation-guide/index.vue')
const student = read('src/pages/student/graduation/index.vue')

test('W4 miniapp native preview keeps ticket authority and exposes the shared preview descriptor', () => {
  assert.match(sdk, /export function previewIdentity\(file = \{\}\)/)
  assert.match(sdk, /file\.fileVersionId \|\| file\.versionId/)
  assert.match(sdk, /file\.sourceSha256 \|\| file\.sourceSha \|\| file\.sha256/)
  assert.match(sdk, /code: 'PREVIEW_UNSUPPORTED'/)
  assert.match(sdk, /code: 'PREVIEW_TICKET_MISSING'/)
  assert.match(sdk, /surface: 'MINIAPP'/)
  assert.match(sdk, /event: 'document_preview_return'/)
  assert.match(sdk, /uni\.previewImage\(/)
  assert.match(sdk, /uni\.openDocument\(/)
  assert.match(sdk, /strictNative: true/)
  assert.match(sdk, /realRequest\(ticketPath, \{ method: 'POST', data: \{ action \} \}\)/)
  assert.match(sdk, /realDownload\(`\$\{openPath\}\?ticket=\$\{raw\}`\)/)
  assert.doesNotMatch(sdk, /window\.open\(/)
})

test('W4 teacher graduation preview preserves review context and stays locked until canonical version revalidation', () => {
  assert.match(teacher, /function reviewIdentity\(kind, recordId, detail = \{\}\)/)
  assert.match(teacher, /previewVersionConflict: false/)
  assert.match(teacher, /previewReturnPending: false/)
  assert.match(teacher, /else if \(this\.previewReturnPending\) this\.revalidatePreviewContext\(\)/)
  assert.match(teacher, /this\.detail\.reviewReady === true && !this\.previewVersionConflict && !this\.previewReturnPending/)
  assert.match(teacher, /beforeIdentity = reviewIdentity\(kind, recordId, this\.detail \|\| \{\}\)/)
  assert.match(teacher, /selectedIdentity = fileSdk\.identity\(/)
  assert.match(teacher, /fileVersionId: item\.fileVersionId \|\| item\.versionId/)
  assert.match(teacher, /sourceSha: item\.sourceSha256 \|\| item\.sourceSha \|\| item\.sha256/)
  assert.match(teacher, /this\.previewReturnPending = kind === 'proposal' \|\| kind === 'final'/)
  assert.match(teacher, /async revalidatePreviewContext\(\)/)
  assert.match(teacher, /this\.reviewKind !== context\.kind \|\| this\.queueIndex !== context\.queueIndex/)
  assert.match(teacher, /const fresh = await api\(\)/)
  assert.match(teacher, /freshIdentity !== context\.beforeIdentity \|\| fresh\.reviewReady !== true/)
  assert.match(teacher, /this\.detail = fresh/)
  assert.match(teacher, /this\.previewReturnPending = false/)
  assert.match(teacher, /@click\.stop="revalidatePreviewContext\(\)"/)
  assert.match(teacher, /确认当前版本/)
  assert.match(teacher, /reviewFinal\([^\n]+this\.detail\.materialVersion, this\.detail\.fileVersionId\)/)
  assert.match(teacher, /reviewProposal\([^\n]+this\.detail\.materialVersion, this\.detail\.fileVersionId\)/)
  assert.match(teacher, /\/mobile\/graduation\/material-center\/files\/\$\{encodeURIComponent\(fileId\)\}\/ticket/)
  assert.match(teacher, /旧版审核已锁定/)
})

test('W4 student graduation miniapp allows thesis PDF/Word on phone and keeps large-package boundaries explicit', () => {
  // 产品决定（2026-09-28）：学生可在手机提交论文初稿/定稿（PDF/Word ≤20MB）；设计作品包、源代码仍走电脑端
  assert.match(student, /const PC_ONLY_MATERIAL_CODES = \['DESIGN_WORK', 'SOURCE_CODE'\]/)
  assert.match(student, /const MOBILE_DOC_EXTENSIONS = \['pdf', 'doc', 'docx'\]/)
  assert.match(student, /20 \* 1024 \* 1024/)
  assert.match(student, /设计作品包、源代码等大型文件请到电脑端上传/)
  assert.doesNotMatch(student, /#ifdef MP-WEIXIN[\s\S]*?请使用学生 PC 上传/)
  assert.match(student, /materialVersionText\(m\)/)
  assert.match(student, /const version = material && material\.currentVersion && material\.currentVersion\.versionNo/)
  assert.match(student, /m\.rejectReason/)
  assert.match(student, /\(m\.currentVersion\.allowedActions \|\| \[\]\)\.includes\('preview'\)/)
  assert.match(student, /fileSdk\.openAuthorized\(/)
  assert.match(student, /\/mobile\/graduation\/material-center\/files\/\$\{encodeURIComponent\(fileId\)\}\/ticket/)
  assert.match(student, /openPath: `\/mobile\/graduation\/material-center\/files\/\$\{encodeURIComponent\(fileId\)\}\/preview`/)
  assert.doesNotMatch(student, /window\.open\(/)
})
