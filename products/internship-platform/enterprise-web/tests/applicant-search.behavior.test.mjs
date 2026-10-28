import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {ref,computed,reactive,effectScope,nextTick} from 'vue'
function mount(t,api){
 const route=reactive({params:{id:'old'}}),context=reactive({contextReady:true,applicationViewAllowed:true,contextEpoch:1}),handlers={}
 const router={async replace(path){route.params.id=path.split('/')[2]||''},push(){}}
 const src=fs.readFileSync(new URL('../src/views/ApplicantListView.vue',import.meta.url),'utf8').match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import.*$/gm,'')+'\nreturn {load,search,keyword,selectedId,items,loading,error,page}'
 const scope=effectScope();const vm=scope.run(()=>new Function('ref','computed','watch','onBeforeUnmount','useRoute','useRouter','useEnterpriseContextStore','enterpriseInternshipApi','window',src)(ref,computed,()=>{},f=>handlers.unmount=f,()=>route,()=>router,()=>context,api,{innerWidth:1200}))
 t.after(()=>{handlers.unmount();scope.stop()});return {vm,route,context}
}
test('changing search clears an out-of-result detail and keeps database pagination',async t=>{
 let params;const p=mount(t,{applications:async x=>{params=x;return {items:[{applicationId:'new'}],total:101}}})
 p.vm.keyword.value='测试岗位';p.vm.search();assert.equal(p.vm.selectedId.value,'');await nextTick();await new Promise(r=>setImmediate(r));assert.equal(p.route.params.id,'new');assert.equal(params.keyword,'测试岗位');assert.equal(params.pageSize,50)
})
test('stale response cannot replace a newer filter and initial deep link is retained',async t=>{
 let finish;let calls=0;const p=mount(t,{applications:()=>++calls===1?new Promise(r=>finish=r):Promise.resolve({items:[{applicationId:'new'}],total:1})})
 const old=p.vm.load(true);await p.vm.load(true);finish({items:[{applicationId:'old'}],total:1});await old;assert.equal(p.vm.items.value[0].applicationId,'new')
 p.route.params.id='deep';await p.vm.load();assert.equal(p.route.params.id,'deep')
})
