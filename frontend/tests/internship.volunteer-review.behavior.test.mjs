import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, ref, reactive } from 'vue'

const source = parse(fs.readFileSync(new URL('../src/modules/internship/views/InternshipVolunteerReviewView.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
function view(api, query = { batchId: '1', campaignId: '2', page: '3', keyword: '陈' }, params = {}, ctx = { permissionPatterns: ['internship.application.review'] }) {
  const route = reactive({ query, params, path: '/admin/internship/volunteer-review' }), navigations = [], cleanups = []
  const router = { push: async r => { navigations.push(r) }, replace: async r => { navigations.push(r) } }
  const page = new Function('computed','ref','watch','onBeforeUnmount','useRoute','useRouter','schoolVolunteerApi','downloadAttachment','defineProps','canCode', `${source}\nreturn { loadContext, loadData, navigate, changeSection, selectedSection, campaigns, rows, detail, error, contextError, loading, contextLoading, selectedApplication, action, actionBusy, actionError, actionStale, askAction, submitAction, canHandle, confirmBlock, studentRecordLocation }`)(computed,ref,()=>{},fn=>cleanups.push(fn),()=>route,()=>router,api,async()=>{},()=>({ctx}),(context,code)=>context.permissionPatterns.includes(code))
  return { page, route, navigations, cleanup: () => cleanups.forEach(fn=>fn()) }
}
const context = { items: [{ id:'2', name:'虚构招聘季' }] }

test('confirmed placement links to the record ID with original context and requires student viewing permission', () => {
  const { page, route } = view({}, undefined, { groupId: '8' }, { permissionPatterns: ['internship.student.view'] })
  route.fullPath = '/admin/internship/volunteer-review/8?batchId=1&campaignId=2&page=3'
  page.detail.value = { id: '8', recordId: '90071992547409939' }
  assert.deepEqual(page.studentRecordLocation.value, { path: '/admin/internship/students/90071992547409939', query: { batchId: '1', section: 'placement', returnTo: route.fullPath } })
  page.detail.value = { id: '8' }
  assert.equal(page.studentRecordLocation.value, null)
  const readOnly = view({}).page
  readOnly.detail.value = { recordId: '31' }
  assert.equal(readOnly.studentRecordLocation.value, null)
})

test('detail and section deep links preserve queue filters; back removes only detail section', async () => {
  const { page, navigations } = view({}, { batchId:'1',campaignId:'2',status:'ALL',keyword:'陈',page:'3',section:'history' }, {groupId:'8'})
  assert.equal(page.selectedSection.value, 'history')
  await page.navigate()
  assert.equal(navigations[0].path, '/admin/internship/volunteer-review')
  assert.deepEqual(navigations[0].query,{batchId:'1',campaignId:'2',status:'ALL',keyword:'陈',page:'3',section:undefined})
  page.changeSection('materials')
  assert.equal(navigations[1].query.section,'materials')
  assert.equal(navigations[1].query.page,'3')
})

const writable = { id:'8', studentName:'虚构学生', status:'LOCKED', recordStatus:'PREPARING',
  version:3, recordVersion:7, positionId:'', advisorUserId:'9', eligibilityStatus:'QUALIFIED',
  enterpriseConfirmRequired:true, lockedApplicationId:'11', volunteers:[{ id:'11', version:2,
    currentSubmission:true, positionAvailable:true, status:'PENDING_REVIEW', companyName:'虚构企业',positionName:'实习岗位' }] }
function readyAction(api, ctx) {
  const result = view(api,undefined,{groupId:'8'},ctx)
  result.page.campaigns.value=[{id:'2',status:'OPEN',schoolConfirmStartAt:'2026-01-01',schoolConfirmEndAt:'2027-01-01'}]
  result.page.detail.value=structuredClone(writable); result.page.selectedApplication.value='11'
  return result
}

test('confirmation freezes reviewed versions and prevents duplicate clicks',async()=>{
  const pending=deferred(), calls=[]
  const {page}=readyAction({confirm:async(...args)=>{calls.push(args);return pending.promise}})
  page.askAction('confirm')
  const first=page.submitAction(); await page.submitAction()
  assert.equal(calls.length,1)
  assert.deepEqual(calls[0],['2','8',{expectedGroupVersion:3,expectedRecordVersion:7,applicationId:'11',expectedApplicationVersion:2}])
  pending.resolve({...writable,status:'APPROVED',version:4,positionId:'20'}); await first
  assert.equal(page.action.value,null); assert.equal(page.detail.value.status,'APPROVED')
  assert.equal(page.canHandle.value,false)
})

test('return keeps reason on failure; version conflict requires a fresh read',async()=>{
  const calls=[]
  const {page}=readyAction({return:async(...args)=>{calls.push(args);throw Object.assign(new Error('投递已变化'),{code:409001})}})
  page.askAction('return'); await page.submitAction({reason:'请补充实训经历'})
  assert.equal(calls[0][2].reason,'请补充实训经历'); assert.equal(page.action.value.kind,'return')
  assert.equal(page.actionError.value,'投递已变化'); assert.equal(page.actionStale.value,true)
  await page.submitAction({reason:'请补充实训经历'}); assert.equal(calls.length,1)
})

test('late write response does not replace a newer student or refresh of the same object',async()=>{
  for(const switched of [false,true]) {
    const pending=deferred()
    const {page,route}=readyAction({confirm:()=>pending.promise,detail:async()=>({...writable,studentName:'重新读取的学生',version:8})})
    page.askAction('confirm'); const work=page.submitAction()
    if(switched) route.params.groupId='9'
    await page.loadData(); pending.resolve({...writable,status:'APPROVED'}); await work
    assert.equal(page.detail.value.studentName,'重新读取的学生')
    assert.equal(page.detail.value.version,8)
  }
})

test('read-only reviewers and incomplete qualification cannot confirm',()=>{
  const readOnly=readyAction({}, {permissionPatterns:['internship.application.view']}).page
  readOnly.askAction('return'); assert.equal(readOnly.action.value,null)
  const {page}=readyAction({}); page.detail.value.eligibilityStatus='PENDING'
  page.askAction('confirm'); assert.equal(page.action.value,null)
  assert.match(page.confirmBlock.value,/资格未通过/)
})

test('late detail response cannot replace newly selected student', async () => {
  const first = deferred(), second = deferred()
  const { page, route } = view({ detail:(_,id)=>id==='8'?first.promise:second.promise }, undefined, {groupId:'8'})
  page.campaigns.value=context.items
  const a=page.loadData(); route.params.groupId='9'; const b=page.loadData()
  second.resolve({id:'9',studentName:'新同学'}); await b
  first.resolve({id:'8',studentName:'旧同学'}); await a
  assert.equal(page.detail.value.id,'9')
})

test('batch switch clears old student immediately and late response remains discarded', async () => {
  const pending = deferred()
  const { page, route } = view({ context:async()=>({items:[]}), detail:()=>pending.promise }, undefined, {groupId:'8'})
  page.campaigns.value=context.items; page.detail.value={id:'old'}
  const a=page.loadData(); route.query.batchId='other'; await page.loadContext()
  pending.resolve({id:'8'}); await a
  assert.equal(page.detail.value,null); assert.deepEqual(page.rows.value,[])
})

test('failure remains an error and stale campaign links do not select another round', async () => {
  let calls=0
  const {page}=view({context:async()=>context,list:async()=>{calls++;throw new Error('服务暂不可用')}})
  await page.loadContext()
  assert.equal(page.error.value,'服务暂不可用'); assert.equal(calls,1)
  const invalid=view({context:async()=>context,list:async()=>{throw new Error('must not be called')}},{batchId:'1',campaignId:'missing'})
  await invalid.page.loadContext()
  assert.equal(invalid.page.error.value,''); assert.equal(invalid.navigations.length,0); assert.deepEqual(invalid.page.rows.value,[])
})
