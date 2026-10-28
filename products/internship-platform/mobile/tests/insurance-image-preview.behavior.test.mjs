import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const source=fs.readFileSync(new URL('../src/pages/teacher-internship/insurance-verify/index.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*/gm,'').replace('export default','return')
const item={id:'41',fileId:'51',version:3}
function page(overrides={}){
 let generation=1,picture
 class Image {set src(value){this.url=value;picture=this}}
 const deps={currentSessionGeneration:()=>generation,Image,fileSdk:{openInline:async()=>({fileId:'51',readyForBusiness:true,canPreview:true,mimeType:'image/png',inlineUrl:'blob:proof'})},normalizeError:()=>({text:'读取失败'}),useInternshipContextStore:()=>({}),URL:{revokeObjectURL(){}},teacherInternshipInsurancePending:async()=>[],teacherInternshipInsuranceVerify:async()=>{},...overrides}
 const component=new Function(...Object.keys(deps),source)(...Object.values(deps)),vm={...component.data()};vm.batchId='21'
 for(const [name,fn] of Object.entries(component.methods))vm[name]=fn.bind(vm)
 return {vm,picture:()=>picture,logout:()=>generation++}
}
test('保单图片实际加载成功前不能通过，加载后绑定本保单原件及版本',async()=>{
 const p=page(),opening=p.vm.openEvidence(item);await new Promise(r=>setImmediate(r))
 assert.equal(p.vm.evidenceReady(item),false);assert.equal(p.picture().url,'blob:proof')
 p.picture().onload();await opening
 assert.equal(p.vm.evidenceReady(item),true);assert.deepEqual(p.vm.preview.pages,['blob:proof']);assert.equal(p.vm.preview.loading,false)
 assert.equal(p.vm.evidenceReady({...item,version:4}),false);assert.equal(p.vm.evidenceReady({...item,fileId:'other'}),false)
})
test('坏图片保留中文失败说明，无法核验通过',async()=>{
 const p=page(),opening=p.vm.openEvidence(item);await new Promise(r=>setImmediate(r));p.picture().onerror();await opening
 assert.equal(p.vm.evidenceReady(item),false);assert.match(p.vm.evidenceErrors[item.id],/图片无法读取/)
})
test('关闭预览、换批次或换会话后的旧图片加载不恢复核验权限',async()=>{
 for(const action of [p=>p.vm.closePreview(),p=>{p.vm.batchId='other';p.vm.loadSeq++},p=>p.logout()]){
  const p=page(),opening=p.vm.openEvidence(item);await new Promise(r=>setImmediate(r));action(p);p.picture().onload();await opening
  assert.equal(p.vm.evidenceReady(item),false)
 }
})

test('换会话后旧元数据返回，不创建原件预览或恢复核验权限',async()=>{
 let resolve;const p=page({fileSdk:{openInline:()=>new Promise(r=>resolve=r)}})
 const opening=p.vm.openEvidence(item);p.logout();resolve({fileId:'51',readyForBusiness:true,canPreview:true,mimeType:'image/png',inlineUrl:'blob:old'});await opening
 assert.equal(p.vm.preview,null);assert.equal(p.vm.evidenceReady(item),false)
})
