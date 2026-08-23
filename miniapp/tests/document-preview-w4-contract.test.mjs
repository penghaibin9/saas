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

test('W4 student graduation miniapp stays small-material-first and makes PC-only/high-sensitivity boundaries explicit', () => {
  assert.match(student, /\['THESIS_DRAFT', 'THESIS_FINAL', 'DESIGN_WORK', 'SOURCE_CODE', 'WORK_DESCRIPTION'\]/)
  assert.match(student, /大型论文、作品或源代码请到学生 PC 上传/)
  assert.match(student, /论文定稿、作品和源代码请使用学生 PC 上传/)
  assert.match(student, /8 \* 1024 \* 1024/)
  assert.match(student, /currentVersion\?\.versionNo \|\| '—'/)
  assert.match(student, /m\.rejectReason/)
  assert.match(student, /\(m\.currentVersion\.allowedActions \|\| \[\]\)\.includes\('preview'\)/)
  assert.match(student, /fileSdk\.openAuthorized\(/)
  assert.match(student, /\/mobile\/graduation\/material-center\/files\/\$\{encodeURIComponent\(fileId\)\}\/ticket/)
  assert.match(student, /openPath: `\/mobile\/graduation\/material-center\/files\/\$\{encodeURIComponent\(fileId\)\}\/preview`/)
  assert.doesNotMatch(student, /window\.open\(/)
})
