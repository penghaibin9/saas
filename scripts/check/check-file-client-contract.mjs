import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const expected = {
  NOT_REQUIRED: '无需扫描',
  PENDING: '等待安全扫描',
  RUNNING: '正在安全扫描',
  CLEAN: '安全可用',
  INFECTED: '检测到风险，已拒绝',
  ERROR: '安全扫描失败'
}

const sdkFiles = [
  'frontend/src/services/file/fileSdk.js',
  'student-portal/src/services/fileSdk.js',
  'miniapp/src/services/fileSdk.js'
]

const componentFiles = [
  ...['FileUploader.vue', 'SecureFileList.vue', 'FilePreviewer.vue', 'FileVersionTimeline.vue']
    .map((name) => `frontend/src/components/file/${name}`),
  ...['FileUploader.vue', 'SecureFileList.vue', 'FilePreviewer.vue', 'FileVersionTimeline.vue']
    .map((name) => `student-portal/src/components/file/${name}`),
  ...['FileUploader.vue', 'SecureFileList.vue', 'FilePreviewer.vue', 'FileVersionTimeline.vue']
    .map((name) => `miniapp/src/components/file/${name}`)
]

function read(relative) {
  const absolute = path.join(root, relative)
  if (!fs.existsSync(absolute)) throw new Error(`missing Stage 2 file: ${relative}`)
  return fs.readFileSync(absolute, 'utf8')
}

for (const relative of sdkFiles) {
  const source = read(relative)
  for (const [status, text] of Object.entries(expected)) {
    if (!source.includes(`${status}: '${text}'`)) {
      throw new Error(`${relative} status wording drift: ${status} must be “${text}”`)
    }
  }
  for (const method of ['upload', 'metadata', 'versions', 'download']) {
    if (!source.includes(`${method}(`) && !source.includes(`${method}:`)) {
      throw new Error(`${relative} missing File SDK method: ${method}`)
    }
  }
}

for (const relative of componentFiles) read(relative)

const adminSdk = read(sdkFiles[0])
if (!adminSdk.includes('xhr.upload.onprogress')) throw new Error('admin upload must expose progress')
if (!adminSdk.includes('xhr.abort()')) throw new Error('admin upload must support cancel')
if (!adminSdk.includes("await request('/auth/me')")) throw new Error('admin upload must retry after shared 401 refresh')
if (!adminSdk.includes('!retried')) throw new Error('admin upload 401 retry must be bounded to one retry')

const miniCompat = read('miniapp/src/services/fileApi.js')
if (!miniCompat.includes("from './fileSdk'")) throw new Error('miniapp fileApi.js must be a File SDK compatibility layer')
if (miniCompat.includes('uni.uploadFile(') || miniCompat.includes('uni.downloadFile(')) {
  throw new Error('miniapp fileApi.js must not retain duplicate transport implementation')
}

const apiFiles = [
  read('backend/app/api/v1/file.py'),
  read('backend/app/api/v1/files.py')
]
if (!apiFiles.every((source) => source.includes('upload_contract'))) {
  throw new Error('formal and compatibility upload APIs must delegate to upload_contract')
}

console.log('Stage 2 four-client File SDK and component contract passed')
