import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/dorm/DormCheckView.vue', import.meta.url), 'utf8')
function view(api, sdk = {}, stubLoad = true) {
  const names = []
  const script = parse(source).descriptor.script.content
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, list) => { names.push(...list.split(',').map(s => s.trim())); return '' })
    .replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g, (_, name) => { names.push(name); return '' })
    .replace('export default', 'return')
  const component = new Function(...names, script)(...names.map(name => name === 'studentAffairsApi' ? api : name === 'fileSdk' ? sdk : {}))
  const vm = component.data()
  for (const [name, fn] of Object.entries(component.methods)) vm[name] = fn.bind(vm)
  if (stubLoad) vm.load = async () => {}
  return vm
}

test('inspection workspace restores status and page after refresh and keeps route context',async()=>{
 const vm=view({})
 vm.$route={query:{workspace:'rectifications',rectStatus:'CLOSED',rectPage:'3',buildingId:'9007199254740993'}}
 vm.applyWorkspaceRoute()
 assert.equal(vm.workspace,'rectifications');assert.equal(vm.rectStatus,'CLOSED');assert.equal(vm.rectPage.page,3)
 let saved
 vm.$router={replace:async r=>{saved=r}}
 await vm.saveWorkspaceRoute()
 assert.equal(saved.query.buildingId,'9007199254740993');assert.equal(saved.query.rectPage,'3')
 vm.$route.query={workspace:'invalid',rectStatus:'invalid',rectPage:'-1'}
 vm.applyWorkspaceRoute()
 assert.equal(vm.workspace,'tasks');assert.equal(vm.rectStatus,'WAITING_RECHECK');assert.equal(vm.rectPage.page,1)
})

test('closed rectification evidence can be opened without permitting submission',async()=>{
 const vm=view({recheckDormRectification:()=>assert.fail('read-only view wrote data')})
 const row={rectificationId:'1',status:'CLOSED',rectifyNote:'整改说明',recheckNote:'复检通过',rectificationFiles:[{fileId:'8'}]}
 vm.openRectification(row,'VIEW')
 assert.equal(vm.rectDlg.row,row);assert.equal(vm.rectDlg.visible,true)
 vm.rectDlg.note='足够长度的意外表单内容'
 await vm.submitRectificationAction()
 assert.equal(vm.rectDlg.visible,true)
})

test('retry keeps the same rectification submission identity and preserves the evidence', async () => {
  const sent = []
  const vm = view({ submitDormRectification: async (id, body) => {
    sent.push({ id, body }); if (sent.length === 1) throw new Error('网络断开')
  } })
  vm.openRectification({ rectificationId: '42', version: 3 }, 'SUBMIT')
  vm.rectDlg.note = '已完成整改并上传照片'
  vm.rectDlg.files = [{ fileId: '9' }]
  await vm.submitRectificationAction()
  assert.equal(vm.rectDlg.visible, true)
  assert.equal(vm.rectDlg.files[0].fileId, '9')
  await vm.submitRectificationAction()
  assert.deepEqual(sent[0], sent[1])
  assert.ok(sent[0].body.clientRequestId)
  assert.equal(vm.rectDlg.visible, false)
})

test('evidence preview uses authorized file SDK and displays access errors', async () => {
  const ids = []
  const vm = view({}, { preview: async id => { ids.push(id); throw new Error('当前身份不可查看此文件') } })
  await vm.previewEvidence({ fileId: 'private-photo', url: 'untrusted-url' })
  assert.deepEqual(ids, ['private-photo'])
  assert.equal(vm.rectDlg.error, '当前身份不可查看此文件')
})


test('rectification workspace filters pending review before pagination and avoids loading unrelated tasks', async () => {
  let query
  const vm = view({listDormRectifications: async q => { query = q; return {data: {items: [{rectificationId: 'review-21'}], total: 41}} }}, {}, false)
  vm.workspace = 'rectifications'; vm.rectPage.page = 2
  await vm.load()
  assert.deepEqual(query, {page: 2, pageSize: 20, status: 'WAITING_RECHECK'})
  assert.equal(vm.rectPage.total, 41)
  assert.equal(vm.errorMessage, '')
})

test('opening another inspection task ignores a late response from the previous task', async () => {
  let finishOld
  const vm = view({listDormCheckRecords: id => id === 'old' ? new Promise(resolve => {finishOld = resolve}) : Promise.resolve({data: {items: [{recordId: 'current'}], total: 32}})})
  const old = vm.openTask({taskId: 'old', taskName: '旧任务'})
  await vm.openTask({taskId: 'new', taskName: '新任务'})
  finishOld({data: {items: [{recordId: 'stale'}], total: 1}})
  await old
  assert.equal(vm.curTask, 'new')
  assert.equal(vm.records[0].recordId, 'current')
  assert.equal(vm.recordPage.total, 32)
})
