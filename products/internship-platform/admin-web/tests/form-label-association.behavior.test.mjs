import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import {compile} from '@vue/compiler-dom'
import {renderToString} from '@vue/server-renderer'
function component(name){
 const source=fs.readFileSync(new URL('../src/components/common/form/'+name+'.vue',import.meta.url),'utf8')
 const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import.*$/gm,'').replace('export default','return')
 const c=new Function('AppHelpTooltip','AppFieldHint',script)({render:()=>null},{render:()=>null})
 c.render=new Function('Vue',compile(source.match(/<template>([\s\S]*?)<\/template>/)[1],{prefixIdentifiers:true}).code)(Vue)
 return c
}
for(const name of ['AppTextInput','AppNumberInput','AppTextarea','AppSelect'])test(name+' inherits field label id and respects explicit id',async()=>{
 const Field=component('AppFormItem'),Input=component(name)
 const out=await renderToString(Vue.createSSRApp({render:()=>Vue.h(Field,{label:'人数'},{default:()=>Vue.h(Input)})}))
 const id=out.match(/for="([^"]+)"/)[1];assert.ok(out.includes('id="'+id+'"'))
 const explicit=await renderToString(Vue.createSSRApp({render:()=>Vue.h(Field,{label:'人数'},{default:()=>Vue.h(Input,{id:'explicit'})})}))
 assert.ok(explicit.includes('id="explicit"'))
})
