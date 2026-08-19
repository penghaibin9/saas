import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join, relative } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const picker = read('src/components/MobileAttachmentPicker.vue')
const serviceApply = read('src/pages/student/service-apply/index.vue')
const greenChannel = read('src/pages/student/orientation/green-channel/index.vue')

test('S6 附件组件只走既有 fileSdk，不自建第二套上传', () => {
  assert.match(picker, /import \{ fileSdk \} from '@\/services\/fileSdk'/)
  assert.match(picker, /fileSdk\.choose\(\)/)
  assert.match(picker, /fileSdk\.upload\(/)
  assert.match(picker, /fileSdk\.metadata\(/)
  assert.match(picker, /fileSdk\.open\(/)
  // 不得绕过 SDK 直接发上传/下载请求
  assert.doesNotMatch(picker, /uni\.uploadFile|uni\.downloadFile|realUpload|realRequest/)
})

test('S6 上传只产出 TEMP_PRIVATE，客户端不得指定正式业务绑定', () => {
  assert.match(picker, /bizId: ''/, '上传时不得携带业务主键，正式归属由服务端绑定')
  // 只看可执行代码：注释里说明「绑定由服务端做」是应该保留的，不能因为出现这个词就判违规。
  const code = picker
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
    .join('\n')
  assert.doesNotMatch(code, /bindTo|createBinding|FileBinding/i,
    '客户端代码里不得出现任何建立业务绑定的动作')
})

test('S6 扫描未通过时禁止业务提交', () => {
  assert.match(picker, /\['PENDING', 'RUNNING'\]\.includes\(file\.scanStatus\)/)
  assert.match(picker, /\['INFECTED', 'ERROR'\]\.includes\(file\.scanStatus\)/)
  assert.match(picker, /files\.value\.every\(\(file\) => file\.readyForBusiness\)/)
  assert.match(picker, /emit\('update:ready', value\)/)
  // 扫描中必须按 metadata 复核真实状态，不能在客户端猜"应该扫完了"
  assert.match(picker, /return await fileSdk\.metadata\(file\.fileId\)/)
})

test('S6 组件如实显示扫描状态，不把未知当可用', () => {
  assert.match(picker, /statusText/)
  assert.match(picker, /is-bad|is-wait|is-ok/)
  assert.match(picker, /blockedReason/)
})

test('S6 接入页面提交前必须检查附件就绪，并把 fileIds 交给业务命令', () => {
  for (const [name, source] of [['service-apply', serviceApply], ['green-channel', greenChannel]]) {
    assert.match(source, /<MobileAttachmentPicker/, `${name} 未接入统一附件组件`)
    assert.match(source, /attachmentsReady/, `${name} 未跟踪附件就绪状态`)
    assert.match(source, /if \(!this\.attachmentsReady\)/, `${name} 未在提交前拦截未就绪附件`)
    assert.match(source, /fileIds: this\.fileIds/, `${name} 未把 fileIds 交给业务命令`)
  }
})

test('S6 生产包不得再用“请携带纸质材料”冒充附件能力', () => {
  const files = []
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) walk(full)
      else if (entry.endsWith('.vue')) files.push(full)
    }
  }
  walk(resolve(root, 'src/pages'))
  const offenders = files.filter((file) => /请携带纸质材料|附件上传暂未开放/.test(readFileSync(file, 'utf8')))
  assert.deepEqual(offenders.map((file) => relative(root, file)), [],
    '这些页面仍以纸质材料作为附件能力的替代品')
})
