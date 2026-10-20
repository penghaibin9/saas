import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor
function load(name, end) {
  const source = readFileSync(new URL(`../src/modules/studentAffairs/views/aid/${name}.vue`, import.meta.url),'utf8').replaceAll('\r','')
  const start = source.indexOf('    async load() {')
  const finish = source.indexOf(end,start)
  return new AsyncFunction('studentAffairsApi',source.slice(start+'    async load() {'.length,finish))
}
const library = load('DifficultStudentsView','\n    },\n    setLevel')
const ledger = load('AidLedgerView','\n    },\n    displayTime')
const stats = load('AidStatsView','\n    }\n  }\n}')
test('library grades use full SQL counts instead of the current page sample', async()=>{
  const calls=[]
  const vm={loadSeq:0,pagination:{page:3,pageSize:20},activeLevel:'GENERAL'}
  await library.call(vm,{getDifficultStudents:async p=>{
    calls.push(p);return {code:0,data:{items:[{studentId:'1',level:'GENERAL'}],total:({SPECIAL:230,DIFFICULT:150,GENERAL:300})[p.level]||680}}
  }})
  assert.equal(vm.total,680);assert.deepEqual(vm.byLevel,{SPECIAL:230,DIFFICULT:150,GENERAL:300})
  assert.equal(vm.pagination.total,300);assert.equal(vm.items.length,1)
  assert.ok(calls.every(p=>p.pageSize!==200))
})
test('result workspaces release loading and offer retry after a network failure',async()=>{
  const api={getAidStats:async()=>{throw Error('offline')},getAidApplications:async()=>{throw Error('offline')},getDifficultStudents:async()=>{throw Error('offline')}}
  for(const invoke of [library,ledger,stats]){
    const vm={loadSeq:0,pagination:{page:1,pageSize:20},activeLevel:'',activeStatus:''}
    await invoke.call(vm,api);assert.equal(vm.loading,false);assert.match(vm.errorMessage,/重试/)
  }
})
test('late ledger response cannot overwrite a newer status filter',async()=>{
  let a,b,calls=0
  const api={getAidApplications:()=>new Promise(r=>{if(++calls===1)a=r;else b=r})}
  const vm={loadSeq:0,pagination:{page:1,pageSize:20},activeStatus:'',activeLevel:''}
  const first=ledger.call(vm,api), latest=ledger.call(vm,api)
  b({code:0,data:{items:[{applyId:'new'}],total:1}});await latest
  a({code:0,data:{items:[{applyId:'old'}],total:1}});await first
  assert.equal(vm.items[0].applyId,'new')
})
