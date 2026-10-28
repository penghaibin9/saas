import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const batch = '9007199254740993001'
function page({ initialized = true, selectedBatchId = batch, loadError = null, manage = false, apiOverrides = {}, fileOverrides = {} } = {}) {
  const source = fs.readFileSync(new URL('../src/modules/internship/views/InternshipMaterialRequirementView.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm, '').replace('export default', 'return')
  const calls = []
  const store = { initialized, selectedBatchId, availableBatches: [], selectBatch(id) { this.selectedBatchId = id }, withBatchQuery() { return { batchId: this.selectedBatchId } }, ensureLoaded: async options => { calls.push(['batch', options]); store.initialized = true } }
  const api = { requirements: async options => { calls.push(['requirements', options]); if (loadError) throw loadError; return [{ id: '1', materialName: '接收函' }] }, ...apiOverrides }
  const component = new Function('useInternshipBatchStore', 'internshipMaterialCenterApi', 'canCode', 'normalizeUiError', 'AppOrgCascader', 'fileSdk', script)(() => store, api, (ctx, code) => !!ctx && manage && code === 'internship.archive.manage', normalizeUiError, {}, fileOverrides)
  const vm = { ...component.data(), ctx: { permissionPatterns: [] }, $route: { path: '/admin/internship/material-requirements', query: { batchId: batch } }, $router: { replace: async () => {} } }
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
test('模板下载指定页面显示的版本编号，不把新当前版替代旧模板', async () => {
  const downloads = []
  const p = page({ apiOverrides: { downloadRequirementTemplate: async (...args) => downloads.push(args) } })
  await p.vm.downloadTemplate({ id: '8', template: { versionId: batch, versionNo: 1 } })
  assert.deepEqual(downloads, [['8', batch]]); assert.equal(p.vm.templateBusyId, '')
})
test('按组织名称配置保留大编号，改选学院清除旧专业班级，空范围不发请求', async () => {
  const created = []
  const p = page({ manage: true, apiOverrides: { createRequirement: async body => created.push(body) } })
  p.vm.openCreate(); Object.assign(p.vm.form, { materialCode: 'C_ORG', materialName: '并行C-材料组织配置', audienceType: 'FILTERED' })
  p.vm.selectAudienceOrganization(['00011', '0012', batch]); await p.vm.create()
  assert.deepEqual(created[0].audienceFilter, { collegeIds: ['11'], majorIds: ['12'], classIds: [batch] })
  p.vm.openCreate(); Object.assign(p.vm.form, { materialCode: 'C_ORG', materialName: '并行C-材料组织配置', audienceType: 'FILTERED', majorIds: '12', classIds: batch })
  p.vm.selectAudienceOrganization(['11']); await p.vm.create()
  assert.deepEqual(created[1].audienceFilter, { collegeIds: ['11'], majorIds: [], classIds: [] })
  p.vm.openCreate(); Object.assign(p.vm.form, { materialCode: 'C_ORG', materialName: '并行C-材料组织配置', audienceType: 'FILTERED' })
  p.vm.selectAudienceOrganization([]); await p.vm.create()
  assert.equal(created.length, 2); assert.equal(p.vm.form.error, '请填写必交人群范围')
})

test('组织、状态和关键词同时用于名单、统计和文件包，不局限于当前分页', async () => {
  const reads = [], stats = [], packages = []
  const p = page({ apiOverrides: {
    requirementStudents: async (id, params) => { reads.push([id, params]); return { items: [{ submission: { files: [{}] } }], hasMore: true } },
    requirementCoverage: async (id, params) => { stats.push([id, params]); return { requiredStudents: 42 } },
    downloadRequirementPackage: async (...args) => packages.push(args)
  } })
  p.vm.students = { visible: true, requirement: { id: '8' }, state: 'RETURNED', organization: ['11', '12', batch], keyword: '并行C-材料', rows: [], page: 1 }
  await p.vm.loadStudents(true); await p.vm.downloadPackage()
  const expected = { state: 'RETURNED', keyword: '并行C-材料', collegeId: '11', majorId: '12', classId: batch }
  assert.deepEqual(reads[0], ['8', { ...expected, page: 1, pageSize: 50 }])
  assert.deepEqual(stats[0], ['8', expected]); assert.deepEqual(packages[0], ['8', expected])
  assert.equal(p.vm.students.coverage.requiredStudents, 42)
})

test('未确认的新搜索条件不能改变文件包或混入下一页，搜索后按已确认范围下载', async () => {
  const reads = [], packages = []
  const p = page({ apiOverrides: {
    requirementStudents: async (id, params) => { reads.push(params); return { items: [{ submission: { files: [{}] } }], hasMore: true } },
    requirementCoverage: async () => ({}), downloadRequirementPackage: async (...args) => packages.push(args)
  } })
  p.vm.openStudents({ id: '8' }, 'SUBMITTED'); await p.vm.loadStudents(true)
  const count = reads.length
  p.vm.students.keyword = '并行C-材料新条件'
  await p.vm.downloadPackage(); await p.vm.loadStudents(false)
  assert.deepEqual(packages, []); assert.equal(reads.length, count)
  assert.match(p.vm.students.error, /请先点击搜索/)
  await p.vm.loadStudents(true); await p.vm.loadStudents(false); await p.vm.downloadPackage()
  assert.equal(reads.at(-1).page, 2); assert.equal(reads.at(-1).keyword, '并行C-材料新条件')
  assert.equal(packages[0][1].keyword, '并行C-材料新条件')
  p.vm.batchStore.selectBatch('另一批次'); await p.vm.downloadPackage()
  assert.equal(packages.length, 1)
})

test('名单读取期间输入新关键词，迟到回执不能授权下载未经确认的范围', async () => {
  let finish
  const p = page({ apiOverrides: {
    requirementStudents: () => new Promise(resolve => { finish = resolve }),
    requirementCoverage: async () => ({}), downloadRequirementPackage: async () => assert.fail('未经搜索确认不能下载')
  } })
  p.vm.students = { visible: true, requirement: { id: '8' }, state: 'SUBMITTED', keyword: '', organization: [], rows: [], page: 1 }
  const work = p.vm.loadStudents(true); p.vm.students.keyword = '并行C-材料新条件'
  finish({ items: [{ submission: { files: [{}] } }] }); await work; await p.vm.downloadPackage()
  assert.match(p.vm.students.error, /请先点击搜索/)
})
test('迟到的材料名单不能覆盖新状态，失败用中文说明', async () => {
  let finish, reads = 0
  const old = new Promise(resolve => { finish = resolve })
  const p = page({ apiOverrides: {
    requirementStudents: async () => ++reads === 1 ? old : { items: [{ studentName: '最新状态学生' }] },
    requirementCoverage: async () => ({ requiredStudents: 1 })
  } })
  p.vm.students = { visible: true, requirement: { id: '8' }, state: 'ALL', organization: [], rows: [], page: 1 }
  const first = p.vm.loadStudents(true); p.vm.students.state = 'APPROVED'; await p.vm.loadStudents(true)
  finish({ items: [{ studentName: '旧状态学生' }] }); await first
  assert.equal(p.vm.students.rows[0].studentName, '最新状态学生')
  p.vm.students.organization = []; p.vm.students.state = 'MISSING'
  const q = page({ apiOverrides: { requirementStudents: async () => { throw Error('SQLSTATE secret') } } })
  q.vm.students = { visible: true, requirement: { id: '8' }, state: 'ALL', organization: [], rows: [], page: 1 }
  await q.vm.loadStudents(true); assert.equal(q.vm.students.error, '学生名单或统计读取失败，请重试')
})

const waitingTemplate = { fileId: batch, fileName: '并行C-材料模板.pdf', status: 'STORED', scanStatus: 'PENDING', readyForBusiness: false }
const safeTemplate = { ...waitingTemplate, scanStatus: 'CLEAN', readyForBusiness: true }
const templateEvent = () => ({ target: { files: [{ name: waitingTemplate.fileName }], value: 'selected' } })

test('格式拒绝用中文说明，不把服务故障显示为文件格式错误', async () => {
  for (const [code, expected] of [[1, '文件内容与所选格式不符或已损坏，请重新导出正确格式后上传'], [400001, '文件内容与所选格式不符或已损坏，请重新导出正确格式后上传'], [500001, '系统暂时无法完成该操作，请稍后重试']]) {
    const row = { id: '1' }, p = page({ manage: true, apiOverrides: {
      uploadRequirementTemplate: () => ({ promise: Promise.reject(Object.assign(Error('ZIP 内容损坏或非合法 ZIP'), { bizCode: 'FILE_TYPE_MISMATCH', code })) }),
      attachRequirementTemplate: async () => assert.fail('被拒绝的上传不能绑定')
    } })
    p.vm.rows = [row]; await p.vm.pickTemplate(templateEvent(), row)
    assert.equal(p.vm.error, expected); assert.deepEqual(p.vm.pendingTemplates, {}); assert.equal(p.vm.templateBusyId, '')
  }
})

test('模板等待扫描时保留原文件，回读安全就绪后只绑定同一文件编号', async () => {
  const binds = [], reads = [], row = { id: '1' }
  const p = page({ manage: true, apiOverrides: {
    uploadRequirementTemplate: () => ({ promise: Promise.resolve(waitingTemplate) }),
    attachRequirementTemplate: async (...args) => binds.push(args)
  }, fileOverrides: { metadata: async id => { reads.push(id); return safeTemplate } } })
  p.vm.rows = [row]
  await p.vm.pickTemplate(templateEvent(), row)
  assert.deepEqual(binds, []); assert.equal(p.vm.pendingTemplates[row.id].fileId, batch)
  assert.match(p.vm.templatePendingText(p.vm.pendingTemplates[row.id]), /等待安全扫描/)
  await p.vm.refreshTemplate(row)
  assert.deepEqual(reads, [batch]); assert.deepEqual(binds, [['1', batch]])
  assert.equal(p.vm.pendingTemplates[row.id], undefined)
})

test('模板安全字段必须真实完整，未知或风险状态不能触发绑定', async () => {
  const row = { id: '1' }, p = page({ manage: true, apiOverrides: { attachRequirementTemplate: async () => assert.fail('未安全就绪不能绑定') } })
  p.vm.rows = [row]
  for (const change of [{ readyForBusiness: 'true' }, { status: '' }, { scanStatus: '' }, { scanStatus: 'INFECTED' }, { scanStatus: 'ERROR' }]) {
    p.vm.pendingTemplates[row.id] = { ...safeTemplate, ...change }
    await p.vm.bindReadyTemplate(row, batch)
    assert.equal(p.vm.templateReady(p.vm.pendingTemplates[row.id]), false)
  }
})

test('绑定失败保留已上传模板，扫描回读缺字段不能继承旧安全状态', async () => {
  let attempts = 0
  const row = { id: '1' }, p = page({ manage: true, apiOverrides: {
    uploadRequirementTemplate: () => ({ promise: Promise.resolve(safeTemplate) }),
    attachRequirementTemplate: async () => { attempts++; throw Error('SQLSTATE secret') }
  }, fileOverrides: { metadata: async () => ({ fileId: batch }) } })
  p.vm.rows = [row]; await p.vm.pickTemplate(templateEvent(), row)
  assert.equal(p.vm.pendingTemplates[row.id].fileId, batch); assert.doesNotMatch(p.vm.error, /SQLSTATE|secret/)
  await p.vm.refreshTemplate(row)
  assert.equal(attempts, 1); assert.equal(p.vm.pendingTemplates[row.id].readyForBusiness, undefined)
})

test('扫描回读编号不一致时保留本人的原文件，不绑定其他文件', async () => {
  const row = { id: '1' }, p = page({ manage: true, apiOverrides: { attachRequirementTemplate: async () => assert.fail('错误编号不得绑定') },
    fileOverrides: { metadata: async () => ({ ...safeTemplate, fileId: 'other' }) } })
  p.vm.rows = [row]; p.vm.pendingTemplates[row.id] = waitingTemplate
  await p.vm.refreshTemplate(row)
  assert.equal(p.vm.pendingTemplates[row.id].fileId, batch); assert.match(p.vm.error, /仍保留/)
})

test('页面重开后回读原上传文件，扫描未就绪不绑定，安全就绪后续办同一编号', async () => {
  const row = { id: '1' }, reads = [], binds = []
  let fresh = waitingTemplate
  const p = page({ manage: true, apiOverrides: { attachRequirementTemplate: async (...args) => binds.push(args) },
    fileOverrides: { metadata: async id => { reads.push(id); return fresh } } })
  p.vm.rows = [row]
  await p.vm.refreshTemplate(row, batch)
  assert.deepEqual(reads, [batch]); assert.deepEqual(binds, [])
  assert.equal(p.vm.pendingTemplates[row.id].fileId, batch)
  fresh = safeTemplate; await p.vm.refreshTemplate(row)
  assert.deepEqual(binds, [['1', batch]]); assert.equal(p.vm.pendingTemplates[row.id], undefined)
})

test('恢复模板拒绝非法编号、无权和不同文件回执，不能回填未经授权的文件', async () => {
  const row = { id: '1' }, p = page({ manage: true, fileOverrides: { metadata: async () => assert.fail('非法编号不读取') } })
  p.vm.rows = [row]
  for (const id of ['0', '-1', 'invalid', batch + ',1']) await p.vm.refreshTemplate(row, id)
  assert.deepEqual(p.vm.pendingTemplates, {}); assert.match(p.vm.error, /有效的模板文件编号/)
  const denied = page({ fileOverrides: { metadata: async () => assert.fail('教师不可恢复模板') } })
  denied.vm.rows = [row]; await denied.vm.refreshTemplate(row, batch)
  for (const metadata of [async () => ({ ...safeTemplate, fileId: 'other' }), async () => { throw Object.assign(Error('secret'), { httpStatus: 403 }) }]) {
    const q = page({ manage: true, fileOverrides: { metadata }, apiOverrides: { attachRequirementTemplate: async () => assert.fail('无效回执不能绑定') } })
    q.vm.rows = [row]; await q.vm.refreshTemplate(row, batch)
    assert.deepEqual(q.vm.pendingTemplates, {}); assert.ok(q.vm.error); assert.doesNotMatch(q.vm.error, /secret/)
  }
})

test('恢复模板的迟到回执不能进入另一批次或已卸载页面', async () => {
  for (const leave of ['batch', 'unmount']) {
    let finish, reads = 0
    const response = new Promise(resolve => { finish = resolve }), row = { id: '1' }
    const p = page({ manage: true, fileOverrides: { metadata: async () => { reads++; return response } },
      apiOverrides: { attachRequirementTemplate: async () => assert.fail('旧上下文不得绑定') } })
    p.vm.rows = [row]; const work = p.vm.refreshTemplate(row, batch); assert.equal(reads, 1)
    if (leave === 'batch') p.vm.batchStore.selectBatch('another-batch')
    else p.component.beforeUnmount.call(p.vm)
    finish(safeTemplate); await work
    assert.deepEqual(p.vm.pendingTemplates, {}); assert.equal(p.vm.error, '')
  }
})

test('模板上传完成时已经切换批次或卸载，不绑定和回填迟到文件', async () => {
  for (const leave of ['batch', 'unmount']) {
    let finish
    const upload = new Promise(resolve => { finish = resolve }), row = { id: '1' }
    const p = page({ manage: true, apiOverrides: { uploadRequirementTemplate: () => ({ promise: upload }),
      attachRequirementTemplate: async () => assert.fail('旧上下文不得绑定') } })
    p.vm.rows = [row]; const work = p.vm.pickTemplate(templateEvent(), row)
    if (leave === 'batch') p.vm.batchStore.selectBatch('new-batch')
    else p.component.beforeUnmount.call(p.vm)
    finish(safeTemplate); await work
    assert.deepEqual(p.vm.pendingTemplates, {}); assert.equal(p.vm.error, '')
  }
})

test('清空批次终止旧加载状态，换批次清除旧配置表单和待绑定视图', async () => {
  let finish
  const response = new Promise(resolve => { finish = resolve })
  const p = page({ manage: true, apiOverrides: { requirements: async () => response } })
  const work = p.vm.load(); p.vm.batchStore.selectBatch(''); await p.vm.load()
  assert.equal(p.vm.loading, false); finish([{ id: 'old' }]); await work; assert.deepEqual(p.vm.rows, [])
  p.vm.openCreate(); p.vm.form.materialName = '旧批次配置'; p.vm.pendingTemplates['1'] = waitingTemplate
  await p.vm.changeBatch({ target: { value: '' } })
  assert.equal(p.vm.form.visible, false); assert.equal(p.vm.form.materialName, ''); assert.deepEqual(p.vm.pendingTemplates, {})
})

test('旧批次统计失败不能在新批次显示错误', async () => {
  let fail
  const stats = new Promise((resolve, reject) => { fail = reject }), row = { id: '1' }
  const p = page({ apiOverrides: { requirementCoverage: async () => stats } }); p.vm.rows = [row]
  const work = p.vm.loadCoverage(row); p.vm.batchStore.selectBatch('new-batch'); p.vm.rows = []
  fail(Error('旧批次错误')); await work
  assert.equal(p.vm.error, ''); assert.equal(row.coverage, undefined)
})
