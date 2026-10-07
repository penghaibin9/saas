import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
for (const [name,method] of [['OrientationMaterialReviewView','getMaterialReviewList'],['OrientationGreenChannelView','getGreenChannelApplications'],['OrientationExceptionView','getExceptionStudents']]) {
 test(name+' preserves batch filtering and ignores the old response',async()=>{
  const s=fs.readFileSync(new URL('../src/views/admin/orientation/'+name+'.vue',import.meta.url),'utf8')
  const start=s.indexOf('    async load() {'),end=s.indexOf('\n    },',start)
  const script=s.slice(start,end+6).trim().replace('async load()','async function load()')
  let resolveOld
  const api={ [method]:p=>p.batchId==='1'?new Promise(r=>{resolveOld=r}):Promise.resolve({code:0,data:{list:[{id:'batch2'}],total:1}}) }
  const load=new Function('api','return '+script)(api)
  const vm={filters:{},page:1,pageSize:20,$route:{query:{batchId:'1'}}}
  const old=load.call(vm);vm.$route.query.batchId='2';await load.call(vm)
  resolveOld({code:0,data:{list:[{id:'batch1'}],total:99}});await old
  assert.equal(vm.rows[0].id,'batch2');assert.equal(vm.total,1);assert.equal(vm.loading,false)
 })
}
