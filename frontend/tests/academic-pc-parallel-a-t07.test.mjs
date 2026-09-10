import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import * as status from '../src/modules/academicAffairs/constants/course-program.js'

function instance(file, deps = {}, options = {}) {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/' + file + '.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const imports = [...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm)]
  const names = imports.flatMap(([,binding]) => binding.trim().startsWith('{') ? binding.replace(/[{}]/g,'').split(',').map(x=>x.trim()).filter(Boolean) : [binding.trim()])
  const defaults = { ...status, ...results, matchPermission: (patterns,key)=>patterns.includes('*')||patterns.includes(key), toast: {success(){},error(){}}, courseMaterialReaderApi: {list: async()=>[],createPreviewProvider:()=>({})}, ...deps }
  const clean = script.replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"]\s*$/gm,'').replace('export default','return')
  const component = new Function(...names, clean)(...names.map(name=>defaults[name] ?? {}))
  const vm = { ...component.data(), ctx: {permissionPatterns:['*']}, $route:{params:{id:'a'},query:{},fullPath:'/admin/academic-affairs/programs/a'}, $router:{push(){},replace:async()=>{}}, ...options }
  Object.entries(component.methods||{}).forEach(([name,method])=>vm[name]=method.bind(vm))
  Object.entries(component.computed||{}).forEach(([name,get])=>Object.defineProperty(vm,name,{get:()=>get.call(vm)}))
  Object.defineProperty(vm,'__component',{value:component})
  return vm
}
const ok = data=>({code:0,data})
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}

test('T07 old program and validation responses cannot replace the selected identity',async()=>{
  const a=deferred(),b=deferred()
  const vm=instance('AaProgramEditorView',{academicAffairsApi:{getProgram:id=>id==='a'?a.promise:b.promise},programQualityApi:{validate:async id=>ok({object:id,issues:[]})}})
  const first=vm.load();vm.$route.params.id='b';const second=vm.load()
  b.resolve(ok({programId:'b',programName:'同名方案',status:'DRAFT'}));await second
  a.resolve(ok({programId:'a',programName:'同名方案',status:'PUBLISHED'}));await first
  assert.equal(vm.program.programId,'b');assert.equal(vm.validation.object,'b');assert.equal(vm.loading,false)
})
test('T07 denied governance query clears previous rows and never falls back to a second permission path',async()=>{
  let fallbacks=0
  const vm=instance('AaProgramListView',{programQualityApi:{governanceSummary:async()=>({code:403,message:'无权限'})},academicAffairsApi:{getPrograms:async()=>{fallbacks++;return ok({list:[]})}}})
  vm.rows=[{programName:'旧内容'}];vm.allRows=vm.rows;vm.summary={totalPrograms:1};await vm.load()
  assert.deepEqual(vm.rows,[]);assert.equal(vm.summary,null);assert.equal(fallbacks,0);assert.equal(vm.error,'无权限')
})
test('T07 review-only identity sees evidence but cannot edit or submit a program',async()=>{
  let writes=0
  const vm=instance('AaProgramEditorView',{academicAffairsApi:{submitProgram:async()=>{writes++;return ok({})}}},{ctx:{permissionPatterns:['academicAffairs.program.review']}})
  vm.program={status:'DRAFT'};assert.equal(vm.editable,false);await vm.doSubmit();assert.equal(writes,0)
})
test('T07 course submission receipt follows the exact version readback',async()=>{
  const calls=[]
  const vm=instance('AaCourseDetailView',{academicAffairsApi:{submitCourse:async id=>{calls.push('POST:'+id);return ok({})},getCourse:async id=>{calls.push('GET:'+id);return ok({courseId:id,courseName:'同名课程',status:'COLLEGE_REVIEW',version:2})},getCourseReferences:async()=>ok({items:[]})}})
  vm.course={status:'DRAFT'};await vm.doSubmit()
  assert.deepEqual(calls,['POST:a','GET:a']);assert.equal(vm.receipt.status,'学院审核中');assert.equal(vm.course.version,2);assert.equal(vm.receipt.time,undefined)
})
test('T07 course read permission never grants approve or manage',async()=>{
  let calls=0
  const vm=instance('AaCourseDetailView',{academicAffairsApi:{disableCourse:async()=>{calls++}}},{ctx:{permissionPatterns:['academicAffairs.course.view']}})
  vm.course={status:'ENABLED'};assert.equal(vm.editable,false);await vm.doDisable();assert.equal(calls,0)
})
test('T07 old course material request cannot leak into another course version',async()=>{
  const material=deferred()
  const vm=instance('AaCourseDetailView',{courseMaterialReaderApi:{list:()=>material.promise}})
  const request=vm.loadMaterials();vm.revision++;vm.$route.params.id='b';vm.materials=[];material.resolve([{fileId:'old'}]);await request
  assert.deepEqual(vm.materials,[])
})
test('T07 changing opening term while reading never renders a previous term result',async()=>{
  const a=deferred(),b=deferred()
  const vm=instance('AaOpeningPlanDiffView',{programQualityApi:{openingDifferences:p=>p.termId==='a'?a.promise:b.promise}})
  vm.filters.termId='a';const first=vm.load();vm.filters.termId='b';const second=vm.load()
  b.resolve(ok({items:[{termId:'b'}],summary:{total:1}}));await second;a.resolve(ok({items:[{termId:'a'}],summary:{total:10}}));await first
  assert.equal(vm.rows[0].termId,'b');assert.equal(vm.summary.total,1)
})
test('T07 source return preserves a safe exact academic object and rejects external routes',()=>{
  let destination
  const vm=instance('AaCourseDetailView',{},{$router:{push:value=>{destination=value}},$route:{params:{id:'1'},query:{returnTo:'/admin/academic-affairs/programs/2?tab=courses'}}})
  vm.returnToSource();assert.equal(destination,'/admin/academic-affairs/programs/2?tab=courses')
  vm.$route.query.returnTo='https://outside.invalid';vm.returnToSource();assert.equal(destination,'/admin/academic-affairs/courses')
})

test('T07 denied review clears loaded course, materials, receipt and dialog',async()=>{
 const vm=instance('AaCourseDetailView',{academicAffairsApi:{reviewCourse:async()=>({code:403001,bizCode:'NO_PERMISSION',message:'无权限'})}})
 vm.course={courseName:'旧课程',status:'COLLEGE_REVIEW'};vm.materials=[{fileId:'private'}];vm.references=[{programId:'private'}];vm.dlg.visible=true
 await vm.doReview({reason:''});assert.equal(vm.course,null);assert.deepEqual(vm.materials,[]);assert.equal(vm.dlg.visible,false);assert.match(vm.error,/清除/)
})
test('T07 conflict review preserves reason and leaves a visible recheck receipt',async()=>{
 const vm=instance('AaCourseDetailView',{academicAffairsApi:{reviewCourse:async()=>({code:409001,bizCode:'DATA_CONFLICT',message:'状态已变化'})}})
 vm.course={courseName:'当前课程',status:'COLLEGE_REVIEW'};vm.dlg.visible=true
 await vm.doReview({reason:'保留审核意见'});assert.equal(vm.dlg.visible,true);assert.equal(vm.receipt.pending,true);assert.match(vm.receipt.status,/保留输入/)
})

test('T07 program and course rows with the same numeric id keep their issue counts separate',()=>{
 const vm=instance('AaProgramEditorView')
 vm.validation={issues:[{objectId:'1',fieldPath:'courseId'},{objectId:'1',fieldPath:'majorId'},{objectId:'1',fieldPath:'graduationRequirements'}]}
 assert.equal(vm.courseIssueCount({programCourseId:'1'}),1)
})

test('T07 direct program deep link selects the exact version after the program list loads',async()=>{
  const program={programId:988,programName:'软件技术专业2024级人才培养方案',status:'COLLEGE_REVIEW'}
  const vm=instance('AaProgramConsoleView',{academicAffairsApi:{getPrograms:async()=>ok({list:[program]})}},{$route:{query:{tab:'courseModules',programId:'988'}}})
  let reloads=0;vm.reload=async()=>{reloads++}
  await vm.__component.created.call(vm)
  assert.equal(vm.selectedProgramId,988);assert.equal(vm.selectedProgram,program);assert.equal(reloads,1)
})

test('T07 same-component program navigation reloads the requested workspace instead of retaining the old tab',async()=>{
  const vm=instance('AaProgramConsoleView',{},{$route:{query:{tab:'archive'}}})
  vm.tab='authoring';let reloads=0;vm.reload=async()=>{reloads++}
  await vm.__component.watch['$route.query.tab'].call(vm,'archive')
  assert.equal(vm.tab,'archive');assert.equal(reloads,1)
})

test('T07 course governance consoles cap each rendered page for large course libraries',()=>{
  const vm=instance('AaCourseConsoleView')
  vm.rows=Array.from({length:120},(_,index)=>({courseId:index+1,status:'ENABLED',category:'MAJOR_CORE'}))
  vm.viewPage=2
  assert.equal(vm.totalPages,3);assert.equal(vm.displayRows.length,50);assert.equal(vm.displayRows[0].courseId,51)
})
