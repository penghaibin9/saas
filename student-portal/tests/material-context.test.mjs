import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { computed, reactive, ref } from 'vue'

const source = readFileSync(new URL('../src/views/affairs/MaterialSupplementView.vue', import.meta.url), 'utf8')
const script = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .+$/gm, '')
function mount() {
  const route = reactive({ query: { bizType: 'AID', bizId: '1' } })
  const requests = [], notices = [], navigation = []
  let watchSource, watchCallback, dirtyCheck
  const api = { myMaterialRequirements: params => new Promise((resolve, reject) => requests.push({ params, resolve, reject })) }
  const fileSdk = { metadata: async fileId => ({fileId, readyForBusiness:true, scanStatus:'CLEAN'}) }
  const state = new Function('computed', 'nextTick', 'watch', 'reactive', 'ref', 'useRoute', 'useRouter', 'useUiStore', 'affairsFourEndApi', 'fileSdk', 'inject', 'onBeforeUnmount',
    script + '\nreturn { load, loadMore, items, total, page, loading, loadingMore, backToApplication, submit, prepareSubmit, cancelSubmission, submitDialog, pendingSubmission, submitting, selectedFiles, notes, submitError, fmtTime, uploadedFiles, selectFile, materialFileHint }')(
    computed, async () => {}, (get, run) => { watchSource = get; watchCallback = run }, reactive, ref,
    () => route, () => ({ push: target => navigation.push(target) }), () => ({ notify: text => notices.push(text) }), api, fileSdk, () => check => { dirtyCheck = check; return () => {} }, () => {})
  return { ...state, route, api, fileSdk, dirtyCheck, requests, notices, navigation, watchSource, watchCallback }
}

test('funding supplements keep the original application filter and return destination', async () => {
  const vm = mount()
  vm.route.query = { bizType: 'FUNDING', bizId: '41', materialRequirementId: '7' }
  const pending = vm.load()
  assert.equal(vm.requests[0].params.bizType, 'FUNDING')
  assert.equal(vm.requests[0].params.bizId, '41')
  assert.equal(vm.requests[0].params.requirementId, '7')
  vm.requests[0].resolve({ items: [], total: 0 }); await pending
  vm.backToApplication()
  assert.deepEqual(vm.navigation[0], { name: 'campus-service', query: { tab: 'funding', recordId: '41' } })
})

test('legacy material notification resolves a return route only from its authorized loaded requirement', () => {
  const vm = mount()
  vm.route.query = { materialRequirementId: '7', recordId: '7' }
  vm.backToApplication(); assert.equal(vm.navigation.length, 0)
  vm.items.value = [{ requirementId: '8', bizType: 'FUNDING', bizId: '90' }]
  vm.backToApplication(); assert.equal(vm.navigation.length, 0)
  vm.items.value.push({ requirementId: '7', bizType: 'FUNDING', bizId: '41' })
  vm.backToApplication()
  assert.deepEqual(vm.navigation[0], { name: 'campus-service', query: { tab: 'funding', recordId: '41' } })
  assert.deepEqual(vm.watchSource(), ['7', undefined, undefined])
})

test('material business changes include type and old list responses cannot overwrite the new application', async () => {
  const vm = mount()
  const first = vm.load()
  vm.route.query = { bizType: 'LEAVE', bizId: '1' }
  assert.deepEqual(vm.watchSource(), ['', 'LEAVE', '1'])
  const second = vm.load()
  vm.requests[1].resolve({ items: [{ requirementId: 'leave' }], total: 1 })
  await second
  vm.requests[0].resolve({ items: [{ requirementId: 'aid' }], total: 40 })
  await first
  assert.equal(vm.items.value[0].requirementId, 'leave')
  assert.equal(vm.total.value, 1)
  assert.equal(vm.loading.value, false)
  vm.backToApplication()
  assert.deepEqual(vm.navigation[0], { name: 'campus-service', query: { tab: 'leave', recordId: '1' } })
})

test('an old load-more cannot append materials after navigation, and the new page remains loadable', async () => {
  const vm = mount()
  const first = vm.load()
  vm.requests[0].resolve({ items: [{ requirementId: 'old' }], total: 30 })
  await first
  const more = vm.loadMore()
  vm.route.query.bizId = '2'
  const second = vm.load()
  vm.requests[2].resolve({ items: [{ requirementId: 'new' }], total: 1 })
  await second
  vm.requests[1].resolve({ items: [{ requirementId: 'old-next-page' }], total: 30 })
  await more
  assert.deepEqual(vm.items.value.map(x => x.requirementId), ['new'])
  assert.equal(vm.page.value, 1)
  assert.equal(vm.loadingMore.value, false)
})

test('material confirmation retains the file and explanation on failure and prevents duplicate requests', async () => {
  const vm = mount(), item = {requirementId:'1',itemName:'测试材料',version:3}
  let finish, shown = 0, closed = 0, uploads = 0, submissions = 0
  vm.submitDialog.value = {showModal:()=>shown++,close:()=>closed++}
  vm.selectedFiles['1'] = {name:'proof.pdf'}
  vm.notes['1'] = '补充说明保留'
  vm.api.uploadMaterialFile = () => { uploads++; return new Promise(resolve => { finish = resolve }) }
  vm.api.submitMaterialVersion = async (...args) => { submissions++; assert.deepEqual(args,['1','88',3,'补充说明保留']); throw new Error('版本已更新，请刷新核对') }
  vm.prepareSubmit(item)
  assert.equal(shown,1)
  const first = vm.submit(item)
  await vm.submit(item)
  let prevented = false
  vm.cancelSubmission({preventDefault:()=>{prevented=true}})
  assert.equal(prevented,true)
  finish({fileId:'88'}); await first
  assert.equal(uploads,1); assert.equal(submissions,1); assert.equal(closed,0)
  assert.equal(vm.selectedFiles['1'].name,'proof.pdf')
  assert.equal(vm.notes['1'],'补充说明保留')
  assert.match(vm.submitError.value,/刷新核对/)
  assert.equal(vm.submitting.value,'')
})

test('UTC material version timestamps display in the local school day', () => {
  process.env.TZ = 'Asia/Shanghai'
  assert.match(mount().fmtTime('2026-09-05T18:53:00Z'), /2026\/9\/6 02:53/)
})


test('pending scans reuse the uploaded file and never submit until the server reports ready', async () => {
  const vm=mount(), item={requirementId:'1',version:4};let uploads=0, submits=0, ready=false
  vm.selectedFiles['1']={name:'proof.pdf'};vm.notes['1']='尚未提交'
  vm.api.uploadMaterialFile=async()=>{uploads++;return {fileId:'77'}}
  vm.fileSdk.metadata=async fileId=>({fileId,readyForBusiness:ready,status:ready?'AVAILABLE':'QUARANTINED',scanStatus:ready?'CLEAN':'PENDING'})
  vm.api.submitMaterialVersion=async()=>{submits++}
  vm.api.myMaterialRequirements=async()=>({items:[],total:0})
  await vm.submit(item);await vm.submit(item)
  assert.equal(uploads,1);assert.equal(submits,0);assert.equal(vm.dirtyCheck(),true)
  assert.match(vm.materialFileHint(vm.uploadedFiles['1']),/无需重复上传/)
  ready=true;await vm.submit(item)
  assert.equal(uploads,1);assert.equal(submits,1);assert.equal(vm.dirtyCheck(),false)
})

test('one successful material clears only that form and retains other unsaved materials',async()=>{
  const vm=mount();vm.selectedFiles['1']={name:'a.pdf'};vm.selectedFiles['2']={name:'b.pdf'}
  vm.api.uploadMaterialFile=async()=>({fileId:'1'});vm.api.submitMaterialVersion=async()=>({})
  vm.api.myMaterialRequirements=async()=>({items:[],total:0})
  await vm.submit({requirementId:'1',version:1})
  assert.equal(vm.dirtyCheck(),true);assert.equal(vm.selectedFiles['2'].name,'b.pdf')
  vm.selectFile({requirementId:'2'},{target:{files:[{name:'replacement.pdf'}]}})
  assert.equal(vm.uploadedFiles['2'],undefined)
})

test('failed, infected and missing readiness never grant client submission',async()=>{
  for(const scanStatus of ['ERROR','INFECTED','RUNNING',undefined]){
    const vm=mount();vm.selectedFiles['1']={name:'a.pdf'};let submits=0
    vm.api.uploadMaterialFile=async()=>({fileId:'1'})
    vm.fileSdk.metadata=async()=>({fileId:'1',scanStatus})
    vm.api.submitMaterialVersion=async()=>{submits++}
    await vm.submit({requirementId:'1',version:1})
    assert.equal(submits,0);assert.equal(vm.dirtyCheck(),true)
  }
})

test('confirmed navigation to another application clears only the previous page drafts',async()=>{
  const vm=mount()
  vm.selectedFiles['1']={name:'old.pdf'};vm.notes['1']='old';vm.uploadedFiles['1']={fileId:'88'}
  vm.route.query.bizId='2'
  vm.watchCallback()
  assert.equal(vm.dirtyCheck(),false)
  assert.deepEqual(Object.keys(vm.uploadedFiles),[])
  assert.equal(vm.requests[0].params.bizId,'2')
  vm.requests[0].resolve({items:[],total:0})
  await Promise.resolve()
})
