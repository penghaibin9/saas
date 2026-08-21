import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()

function read(relative) {
  const absolute = path.join(root, relative)
  if (!fs.existsSync(absolute)) throw new Error(`missing document preview contract file: ${relative}`)
  return fs.readFileSync(absolute, 'utf8')
}

function walk(relative, output = []) {
  const absolute = path.join(root, relative)
  if (!fs.existsSync(absolute)) return output
  for (const entry of fs.readdirSync(absolute, { withFileTypes: true })) {
    const child = path.join(relative, entry.name)
    if (entry.isDirectory()) walk(child, output)
    else if (/\.(?:js|mjs|ts|vue)$/.test(entry.name)) output.push(child.replaceAll('\\', '/'))
  }
  return output
}

const contract = read('docs/architecture/document-preview-contract.md')
for (const marker of [
  'document-preview-contract/v1',
  '`preview` permission **is not** `download` permission',
  'GRADUATION_MATERIAL',
  'BUSINESS_TICKET',
  'fileVersionId',
  'sourceSha256',
  'PREVIEW_VERSION_CHANGED',
  'YUEKE E2E SYNTHETIC DOCUMENT',
  'Mobile Reader Return Contract',
  'presentationSafety'
]) {
  if (!contract.includes(marker)) throw new Error(`document preview contract drift: missing ${marker}`)
}

const componentBoundaries = {
  'frontend/src/components/file/FilePreviewer.vue': [
    'window.open(', 'URL.createObjectURL(', "request('/files", 'uni.openDocument(', 'uni.downloadFile('
  ],
  'frontend/src/components/common/AppFilePreview.vue': [
    'window.open(', 'URL.createObjectURL(', "request('/files", 'uni.openDocument(', 'uni.downloadFile('
  ],
  'student-portal/src/components/file/FilePreviewer.vue': [
    'window.open(', 'URL.createObjectURL(', "request('/files", 'uni.openDocument(', 'uni.downloadFile('
  ],
  'miniapp/src/components/file/FilePreviewer.vue': [
    'realRequest(', 'realDownload(', 'uni.openDocument(', 'uni.previewImage(', 'uni.downloadFile('
  ]
}

for (const [relative, forbidden] of Object.entries(componentBoundaries)) {
  const source = read(relative)
  for (const token of forbidden) {
    if (source.includes(token)) throw new Error(`${relative} owns forbidden preview transport primitive: ${token}`)
  }
}

const miniappLegacyNativeOpen = new Set([
  'miniapp/src/pages/student/me/index.vue',
  'miniapp/src/pages/student/affairs/index.vue',
  'miniapp/src/pages/teacher/affairs/index.vue'
])
for (const relative of walk('miniapp/src')) {
  const source = read(relative)
  const ownsNativeOpen = source.includes('uni.openDocument(') || source.includes('uni.previewImage(')
  if (ownsNativeOpen && relative !== 'miniapp/src/services/fileSdk.js' && !miniappLegacyNativeOpen.has(relative)) {
    throw new Error(`${relative} adds a native preview bypass; route through miniapp File SDK`)
  }
  if (source.includes('uni.downloadFile(') && relative !== 'miniapp/src/services/request.js') {
    throw new Error(`${relative} adds a raw download bypass; route through miniapp request/File SDK`)
  }
}

const accessContract = read('backend/app/api/v1/file_contract.py')
if (!accessContract.includes('_requires_audited_business_download')) {
  throw new Error('graduation high-sensitivity generic URL guard is missing')
}
if (!accessContract.includes('GRADUATION_MATERIAL')) {
  throw new Error('graduation material must remain high-sensitivity file-center policy')
}

const graduationRouter = read('backend/app/modules/graduation/routers/graduation_material_center.py')
if (!graduationRouter.includes('/material-center/files/{file_id}/ticket')) {
  throw new Error('graduation business preview ticket endpoint is missing')
}
if (!graduationRouter.includes('/material-center/files/{file_id}/preview')) {
  throw new Error('graduation audited preview byte endpoint is missing')
}

const viewerRoot = 'frontend/src/components/file/viewer'
for (const relative of walk(viewerRoot)) {
  const source = read(relative)
  for (const token of ['realRequest(', "request('/graduation", '/material-center/files/', 'submitReview(', 'reviewFinal(', 'reviewProposal(']) {
    if (source.includes(token)) throw new Error(`${relative} bypasses Viewer presentation boundary: ${token}`)
  }
}

const studentSdk = read('student-portal/src/services/fileSdk.js')
const studentRequest = read('student-portal/src/services/request.js')
const studentMaterials = read('student-portal/src/views/graduation/GraduationMaterialsView.vue')
const studentWorkbench = read('student-portal/src/views/graduation/GraduationWorkbenchView.vue')
const peerPreviewRouter = read('backend/app/api/v1/mobile_graduation_material_center.py')
const peerPreviewService = read('backend/app/modules/graduation/services/graduation_peer_consistency.py')

if (!studentRequest.includes('export async function fetchFileBlob(')) {
  throw new Error('student PC request layer is missing authenticated preview Blob transport')
}
if (!studentRequest.includes("error?.name === 'AbortError'")) {
  throw new Error('student PC preview Blob transport must preserve AbortError cancellation')
}
if (!studentSdk.includes('async fetchPreviewBlob(') || !studentSdk.includes('async fetchPreviewBlobFrom(')) {
  throw new Error('student PC File SDK must expose preview-only Blob methods')
}
if (/async preview\([^)]*\)[\s\S]{0,180}?this\.download\(/.test(studentSdk)
    || /async previewFrom\([^)]*\)[\s\S]{0,180}?this\.downloadFrom\(/.test(studentSdk)) {
  throw new Error('student PC preview regressed to download side effect')
}
if (!studentMaterials.includes("issueGraduationMaterialTicket(file.fileId, 'preview')")
    || !studentMaterials.includes('预览我将提交的文件')
    || !studentMaterials.includes('查看历史版')) {
  throw new Error('student graduation material library is missing audited current/history/pending Reader flow')
}
if (!studentWorkbench.includes('查看当前版')
    || !studentWorkbench.includes('预览我将提交的文件')
    || !studentWorkbench.includes("issueGraduationMaterialTicket(file.fileId, 'preview')")) {
  throw new Error('student graduation workbench is missing current-version Reader or submit preflight')
}
for (const marker of [
  '互查文件只允许走任务专用授权',
  'openPeerReader(',
  'fileSdk.fetchPeerPreviewBlob(file.peerId, file.fileId, options)'
]) {
  if (!studentWorkbench.includes(marker)) throw new Error(`student peer-review Reader contract drift: missing ${marker}`)
}
if (!studentSdk.includes('async fetchPeerPreviewBlob(peerId, fileId, options = {})')
    || !studentSdk.includes('/mobile/graduation/peer/${enc(peerId)}/files/${enc(fileId)}/preview')) {
  throw new Error('student peer-review preview transport must stay task-bound to peerId + fileId')
}
for (const marker of [
  '/peer/{peer_id}/files/{file_id}/preview',
  'peer_files.resolve_peer_preview(peer_id, file_id, user)',
  'STUDENT_GRADUATION_PEER_MATERIAL_PREVIEW',
  '"taskBound": True'
]) {
  if (!peerPreviewRouter.includes(marker)) throw new Error(`peer-review preview route drift: missing ${marker}`)
}
for (const marker of [
  'def resolve_peer_preview(peer_id, file_id, user):',
  'resolve_current_gd_student(db, user)',
  'int(current.id) not in {int(peer.gd_student_id), int(peer.reviewer_gd_student_id)}',
  'final = _bound_final(db, peer)',
  'target_file_id not in _attachment_ids(final)',
  'FileObject.tenant_id == _tid()',
  'FileObject.biz_type == "GRADUATION_MATERIAL"',
  'is_downloadable_status(file_row.status)'
]) {
  if (!peerPreviewService.includes(marker)) throw new Error(`peer-review preview authorization drift: missing ${marker}`)
}

const studentViewerRoot = 'student-portal/src/components/file/viewer'
const studentViewerFiles = walk(studentViewerRoot)
if (!studentViewerFiles.length) throw new Error('student PC Reader implementation is missing')
for (const relative of studentViewerFiles) {
  const source = read(relative)
  for (const token of ['portalApi', 'issueGraduationMaterialTicket', '/material-center/', 'downloadGraduationMaterial', 'window.open(']) {
    if (source.includes(token)) throw new Error(`${relative} bypasses student Viewer presentation boundary: ${token}`)
  }
}
const studentSession = read('student-portal/src/components/file/viewer/useStudentPreviewSession.js')
for (const marker of ['file.fileId', 'file.fileVersionId || file.versionId', 'file.sourceSha256 || file.sha256', 'new AbortController()', 'URL.revokeObjectURL(objectUrl.value)']) {
  if (!studentSession.includes(marker)) throw new Error(`student Reader session lifecycle drift: missing ${marker}`)
}

console.log('W0-W4 document-preview-contract/v1 owner, transport, task-bound Reader and high-sensitivity boundaries passed')
