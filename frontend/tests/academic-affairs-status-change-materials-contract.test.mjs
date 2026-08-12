import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const apiUrl = new URL(
  '../src/modules/academicAffairs/api/status-change-convenience.api.js',
  import.meta.url
)
const formUrl = new URL(
  '../src/modules/academicAffairs/views/AaStatusChangeFormView.vue',
  import.meta.url
)
const detailUrl = new URL(
  '../src/modules/academicAffairs/views/AaStatusChangeDetailView.vue',
  import.meta.url
)
const uploaderUrl = new URL('../src/components/file/FileUploader.vue', import.meta.url)

test('D3-U material API keeps one convenience submit and formal list/add routes', async () => {
  const source = await readFile(apiUrl, 'utf8')

  assert.match(source, /async submit\(body\)/)
  assert.match(source, /\$\{BASE\}\/convenience-submit/)
  assert.match(source, /async listMaterials\(changeId\)/)
  assert.match(source, /\$\{BASE\}\/\$\{encodeURIComponent\(changeId\)\}\/materials/)
  assert.match(source, /async addMaterials\(changeId, materialFileIds\)/)
  assert.match(source, /method: 'POST'/)
  assert.match(source, /body: \{ materialFileIds \}/)
})

test('D3-U form blocks active upload and unsafe scan before its single submit', async () => {
  const source = await readFile(formUrl, 'utf8')

  assert.match(source, /import FileUploader from '@\/components\/file\/FileUploader\.vue'/)
  assert.match(source, /import \{ fileSdk \} from '@\/services\/file\/fileSdk'/)
  assert.match(source, /materialFiles\.length >= 10/)
  assert.match(source, /@progress="onMaterialProgress"/)
  assert.match(source, /@cancelled="onMaterialUploadCancelled"/)
  assert.match(source, /materialUploadBusy/)
  assert.match(source, /hasPendingMaterial/)
  assert.match(source, /fileSdk\.metadata\(fileId\)/)
  assert.match(source, /materialFileIds: this\.materialFiles\.map/)
  assert.match(source, /statusChangeConvenienceApi\.submit\(this\.buildBody\(\)\)/)
  assert.doesNotMatch(source, /academicAffairsApi\.submitStatusChange\(/)
})

test('FileUploader emits progress=0 immediately when a real upload starts', async () => {
  const source = await readFile(uploaderUrl, 'utf8')
  const uploadingIndex = source.indexOf('uploading.value = true')
  const zeroIndex = source.indexOf("emit('progress', 0)")
  const sdkIndex = source.indexOf('activeTask = fileSdk.upload')

  assert.ok(uploadingIndex >= 0)
  assert.ok(zeroIndex > uploadingIndex)
  assert.ok(sdkIndex > zeroIndex)
})

test('D3-U detail renders only formal material enumeration through FilePreviewer', async () => {
  const source = await readFile(detailUrl, 'utf8')

  assert.match(source, /statusChangeConvenienceApi\.listMaterials\(this\.changeId\)/)
  assert.match(source, /import FilePreviewer from '@\/components\/file\/FilePreviewer\.vue'/)
  assert.match(source, /items\.map\(\(file\) => fileSdk\.normalize\(file\)\)/)
  assert.match(source, /<FilePreviewer/)
  assert.match(source, /:file="file"/)
  assert.doesNotMatch(source, /ownerUserId|createdBy/)
})
