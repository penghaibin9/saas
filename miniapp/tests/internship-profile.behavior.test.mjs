import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { selectionScope, selectionScopePath } from '../../shared/internshipSelectionScope.mjs'
const source = fs.readFileSync(new URL('../src/pages/student/internship/profile/index.vue', import.meta.url),'utf8').split('<script>')[1].split('</script>')[0].replace(/^import .*$/gm,'').replace('export default','return')
const projection = () => ({profile:{profileVersion:3,selfIntro:'原介绍',skillTags:['PLC']},schoolFacts:{realName:'测试学生'},items:[]})
function fixture(overrides={}) {
  const calls=[]; const api={profile:async()=>projection(),profileCompleteness:async()=>({percent:100}),updateProfile:async data=>{calls.push(data);return projection()},createProfileItem:async data=>{calls.push(data);return projection()},...overrides}
  const options=new Function('internshipSelectionApi','selectionScope','selectionScopePath','chooseSingleFile','uploadBusinessFile','openBusinessFile','uni',source)({forScope:()=>api},selectionScope,selectionScopePath,async()=>null,async()=>({}),async()=>{},{showModal:({success})=>success({confirm:true}),redirectTo:data=>calls.push(data)})
  const page=options.data(); for(const [key,fn] of Object.entries(options.methods))page[key]=fn.bind(page)
  for(const [key,fn] of Object.entries(options.computed))Object.defineProperty(page,key,{get:()=>fn.call(page)})
  return {page,calls,options}
}
test('profile saves version and student fields only',async()=>{
  const {page,calls}=fixture();await page.load();page.draft.selfIntro='新介绍';await page.saveProfile()
  assert.equal(calls[0].expectedProfileVersion,3);assert.equal(calls[0].selfIntro,'新介绍');assert.equal(calls[0].schoolFacts,undefined);assert.equal(page.profileDirty,false)
})
test('invalid original scope remains rejected on retry',async()=>{
  const {page}=fixture({profile:()=>assert.fail('invalid scope request')});await page.applyQuery({batchId:'1'});await page.reload();assert.equal(page.state,'error')
})
test('return preserves all original scope identifiers',async()=>{
  const {page,calls}=fixture();await page.applyQuery({batchId:'1',campaignId:'2',recordId:'3'});await page.returnToSelection();assert.match(calls[0].url,/batchId=1&campaignId=2&recordId=3$/)
})
test('uncertain item creation retains draft and prevents duplicate retries',async()=>{
  let count=0;const {page}=fixture({createProfileItem:async()=>{count++;throw new Error('响应丢失')}});await page.load();page.editItem();page.itemDraft.title='实践';await page.saveItem();await page.saveItem();assert.equal(count,1);assert.equal(page.itemDraft.title,'实践');assert.equal(page.uncertain,true)
})
test('unsaved introduction prevents changing material editor',async()=>{
  const {page}=fixture();await page.load();page.draft.selfIntro='未保存';page.editItem();assert.equal(page.itemDraft,null)
})
test('old save response cannot reset new page data',async()=>{
  let resolve;const {page}=fixture({updateProfile:()=>new Promise(r=>{resolve=r})});await page.load();page.draft.selfIntro='修改';const pending=page.saveProfile();page.sequence++;page.draft.selfIntro='新页面';resolve(projection());await pending;assert.equal(page.draft.selfIntro,'新页面')
})
test('school-sourced items never open student editor',async()=>{
  const {page}=fixture();await page.load();page.editItem({id:'1',sourceType:'SCHOOL_FACT'});assert.equal(page.itemDraft,null)
})
