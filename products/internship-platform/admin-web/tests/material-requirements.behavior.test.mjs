import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const batch = '9007199254740993001'
function page({ initialized = true, selectedBatchId = batch, loadError = null, manage = false, apiOverrides = {} } = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipMaterialRequirementView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const calls = []
  const store = { initialized, selectedBatchId, availableBatches: [], ensureLoaded: async options => { calls.push(['batch', options]); store.initialized = true } }
  const api = { requirements: async options => { calls.push(['requirements', options]); if (loadError) throw loadError; return [{ id: '1', materialName: '接收函' }] }, ...apiOverrides }
  const component = new Function('useInternshipBatchStore', 'internshipMaterialCenterApi', 'canCode', 'normalizeUiError', script)(() => store, api, (ctx, code) => !!ctx && manage && code === 'internship.archive.manage', normalizeUiError)
  const vm = { ...component.data(), ctx: { permissionPatterns: [] }, $route: { query: { batchId: batch } } }
  for (const [key, fn] of Object.entries(component.methods)) vm[key] = (...args) => fn.apply(vm, args)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(vm, key, { get: () => fn.call(vm) })
  return { vm, component, calls }
}

test('父布局已解析深链批次，子页不再加载批次而触发反复卸载', async () => {
  const p = page(); await p.component.mounted.call(p.vm)
  assert.deepEqual(p.calls, [['requirements', { batchId: batch, status: 'ALL' }]])
  assert.equal(p.vm.rows[0].materialName, '接收函')
})
test('独立挂载时先初始化批次，再查询当前批次要求', async () => {
  const p = page({ initialized: false }); await p.component.mounted.call(p.vm)
  assert.deepEqual(p.calls.map(([name]) => name), ['batch', 'requirements'])
  assert.equal(p.calls[0][1].batchIdFromUrl, batch)
})
test('无有效批次时不发业务查询，不把深链参数自行当作授权批次', async () => {
  const p = page({ selectedBatchId: '' }); await p.component.mounted.call(p.vm)
  assert.deepEqual(p.calls, []); assert.deepEqual(p.vm.rows, [])
})
test('查询失败保留明确中文错误，不能伪装成空数据', async () => {
  const p = page({ loadError: new Error('SQLSTATE SELECT secret FROM table') }); await p.vm.load()
  assert.equal(p.vm.error, '收件要求加载失败'); assert.equal(p.vm.loading, false)
})
test('教师只有查看权限时不能进入配置动作', () => {
  const p = page(); assert.equal(p.vm.canManage, false); p.vm.openCreate(); assert.equal(p.vm.form.visible, false)
})
test('已授权学校管理员可以打开收件配置', () => {
  const p = page({ manage: true }); assert.equal(p.vm.canManage, true); p.vm.openCreate(); assert.equal(p.vm.form.visible, true)
})
test('未知状态与组织类型不显示程序枚举，常用文件格式以中文说明', () => {
  const p = page(); assert.equal(p.vm.statusText('INTERNAL_STATE'), '状态待确认')
  assert.equal(p.vm.batchStatusText('RUNNING'), '进行中'); assert.equal(p.vm.batchStatusText('UNKNOWN'), '状态待确认')
  assert.equal(p.vm.audienceText({ audienceType: 'UNKNOWN' }), '收件范围待确认')
  assert.equal(p.vm.formatText(['png', 'pdf', 'docx', 'xlsx', 'zip', 'mp4']), '图片 / 便携文档 / 文字文档 / 电子表格 / 压缩文件 / 视频')
})
test('指定学生配置以字符串传递大编号，不发生数值舍入', async () => {
  let body
  const p = page({ manage: true, apiOverrides: { createRequirement: async value => { body = value } } })
  p.vm.openCreate(); Object.assign(p.vm.form, { materialCode: 'JSH001', materialName: '企业接收函', audienceType: 'SELECTED_STUDENTS', studentIds: batch + ',0,invalid,001' })
  await p.vm.create()
  assert.deepEqual(body.audienceFilter.studentIds, [batch, '1']); assert.equal(body.batchId, batch)
})
test('只读身份不发起新建、模板绑定和发布请求', async () => {
  const denyRequest = async () => assert.fail('只读身份不得发送配置请求')
  const p = page({ apiOverrides: { createRequirement: denyRequest, uploadRequirementTemplate: denyRequest, publishRequirement: denyRequest } })
  await p.vm.create(); await p.vm.publish({ template: {} }); await p.vm.pickTemplate({ target: { files: [{}], value: 'file' } }, { id: '1' })
  assert.equal(p.vm.saving, false); assert.equal(p.vm.templateBusyId, '')
})
