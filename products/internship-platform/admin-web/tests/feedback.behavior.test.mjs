import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { inferPreviewKind } from '../src/components/file/viewer/viewer-contract.js'
import { formatDateTime } from '../src/utils/dateUtils.js'

const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipFeedbackView.vue', import.meta.url), 'utf8')
const template = source.slice(source.indexOf('<template>') + 10, source.indexOf('\n<script>')).replace(/<\/template>\s*$/, '')
const metadata = () => ({ fileId: '234', fileName: '合成反馈原图.png', ext: 'png', mimeType: 'image/png',
  status: 'AVAILABLE', scanStatus: 'CLEAN', readyForBusiness: true, canPreview: true, canDownload: true, allowedActions: ['preview', 'download'] })
const detail = () => ({ id: '5', category: 'STUDENT_FEEDBACK', status: 'RESOLVED', statusLabel: '已办结', version: 4,
  imageFileIds: ['234'], content: '合成学生反馈', createdAt: '2026-10-13T03:20:00Z', conclusion: '学校已处理' })
function page(sdk = {}) {
  const names = ['ModulePageShell','DataTable','LoadingState','ErrorState','EmptyState','AppStatusTag','AppSelect','AppDescriptionList','AppFilePreview','AppAuditTrail','AppConfirmDialog','AppButton','FilePreviewer']
  const scope = Object.fromEntries(names.map(name => [name, {}])), errors = []
  const store = { selectedBatchId: '18', withBatchQuery: query => ({ ...query, batchId: '18' }) }
  Object.assign(scope, { formatDateTime, useInternshipBatchStore: () => store, canCode: () => false,
    fileSdk: { metadata: async () => metadata(), blob: async () => new Blob(['image bytes'], { type: 'image/png' }), ...sdk },
    internshipApi: { getStudentFeedbackDetail: async () => ({ code: 0, data: detail() }), getStudentFeedback: async () => ({ code: 0, data: { list: [], total: 0 } }) }, toast: { error: value => errors.push(value) } })
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\r?\n/gm, '').replace('export default', 'return')
  const component = new Function(...Object.keys(scope), script)(...Object.values(scope))
  const vm = { ...component.data(), ctx: { ctxKey: 'school-role' }, $route: { query: { id: '5' } }, $router: { replace: () => Promise.resolve() } }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm, args)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, component, store, errors }
}

test('反馈详情按真实元信息选择图片组件并复核授权字节，不走旧框架预览', async () => {
  let reads = 0
  const p = page({ metadata: async () => { reads++; return metadata() }, preview: () => { throw new Error('禁止旧框架路线') } })
  await p.vm.loadDetail('5')
  assert.equal(p.vm.imageFiles[0].fileName, '合成反馈原图.png')
  assert.equal(inferPreviewKind(p.vm.imageFiles[0]), 'IMAGE')
  assert.equal(await (await p.vm.imageProvider.fetchBytes(p.vm.imageFiles[0])).text(), 'image bytes')
  assert.equal(reads, 2)
  const children = [], shell = { setup: (_, { slots }) => () => h('main', slots.default?.()) }
  const components = Object.fromEntries(Object.keys(p.component.components).map(name => [name, { render: () => null }]))
  Object.assign(components, { ModulePageShell: shell, FilePreviewer: { props: { file: Object, inline: Boolean, provider: Object }, setup: props => { children.push(props); return () => h('span', props.file.fileName) } } })
  const vm = Object.defineProperties({}, Object.fromEntries(Object.entries(Object.getOwnPropertyDescriptors(p.vm)).filter(([key]) => !key.startsWith('$'))))
  await renderToString(createSSRApp({ components, setup: () => vm, render: compile(template) }))
  assert.equal(children.length, 1); assert.equal(children[0].inline, true)
  assert.equal(inferPreviewKind(children[0].file), 'IMAGE'); assert.equal(typeof children[0].provider.fetchBytes, 'function')
})

test('反馈图片编号安全状态或权限不符时拒绝读取，下载用真实文件名', async () => {
  let current = metadata(), downloaded, blobs = 0
  const p = page({ metadata: async () => current, blob: async () => { blobs++; return new Blob() }, download: async (...args) => { downloaded = args } })
  await p.vm.loadDetail('5')
  for (const values of [{ fileId: '999' }, { readyForBusiness: false }, { scanStatus: 'PENDING' }, { canDownload: false }, { canPreview: false }]) {
    current = { ...metadata(), ...values }
    await assert.rejects(p.vm.imageProvider.fetchBytes(p.vm.imageFiles[0]))
    assert.equal(blobs, 0)
  }
  current = metadata()
  await assert.rejects(p.vm.imageProvider.fetchBytes({ fileId: '999' }))
  await p.vm.downloadImage(p.vm.imageFiles[0]); assert.deepEqual(downloaded, ['234', '合成反馈原图.png'])
  assert.equal(p.vm.detail.data.status, 'RESOLVED'); assert.equal(p.vm.detail.data.version, 4)
})

test('反馈图片迟到元信息在切单批次身份及离页后不进入新页面', async () => {
  for (const action of ['record', 'batch', 'role', 'leave']) {
    let resolve; const waiting = new Promise(done => { resolve = done }), p = page({ metadata: () => waiting })
    const pending = p.vm.loadDetail('5'); await Promise.resolve(); await Promise.resolve()
    if (action === 'record') { p.vm.$route.query.id = '6'; p.vm.resetImages() }
    if (action === 'batch') { p.store.selectedBatchId = '19'; p.component.watch['batchStore.selectedBatchId'].call(p.vm) }
    if (action === 'role') { p.vm.ctx.ctxKey = 'new-role'; p.component.watch['ctx.ctxKey'].call(p.vm) }
    if (action === 'leave') p.component.beforeUnmount.call(p.vm)
    resolve(metadata()); await pending; assert.deepEqual(p.vm.imageFiles, [], action)
  }
})

test('反馈时间按现有本地格式显示且保留原时间值', async t => {
  const previous = process.env.TZ; process.env.TZ = 'Asia/Shanghai'
  t.after(() => { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous })
  const p = page(); await p.vm.loadDetail('5')
  assert.equal(p.vm.detailItems.find(row => row.label === '提交时间').value, '2026-10-13 11:20')
  assert.equal(p.vm.formatDateTime(p.vm.detail.data.createdAt), '2026-10-13 11:20')
  assert.equal(p.vm.detail.data.createdAt, '2026-10-13T03:20:00Z')
})
