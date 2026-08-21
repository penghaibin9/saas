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
  'preview permission **is not** `download` permission',
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
  if (
    ownsNativeOpen &&
    relative !== 'miniapp/src/services/fileSdk.js' &&
    !miniappLegacyNativeOpen.has(relative)
  ) {
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

const viewerRoot = 'frontend/src/components/file/DocumentViewer'
for (const relative of walk(viewerRoot)) {
  const source = read(relative)
  for (const token of ['realRequest(', "request('/graduation", '/material-center/files/']) {
    if (source.includes(token)) {
      throw new Error(`${relative} bypasses Preview Provider boundary: ${token}`)
    }
  }
}

console.log('W0 document-preview-contract/v1 owner, transport and high-sensitivity boundaries passed')
