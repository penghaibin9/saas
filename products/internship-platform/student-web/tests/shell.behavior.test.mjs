import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse } from '@vue/compiler-sfc'
import { computed,effectScope,nextTick,reactive,ref,watch } from 'vue'
import { INTERNSHIP_TABS,INTERNSHIP_TAB_GROUPS } from '../src/platform/internshipNavigation.js'
import { WORKSPACE_THEMES,normalizeTheme,themeTokens } from '../src/platform/workspaceTheme.js'

function page(t){
  const route=reactive({path:'/internship',fullPath:'/internship?view=report&batchId=77&reportType=DAILY&reportId=99',query:{view:'report',batchId:'77',reportType:'DAILY',reportId:'99'}}),session=reactive({user:{tenantId:'1',userId:'2',roleCode:'STUDENT'}}),pushes=[]
  const script=parse(fs.readFileSync(new URL('../src/layouts/PortalLayoutV5.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[^\n]+\n/gm,'')
  const deps={computed,ref,watch,onBeforeUnmount(){},defineEmits:()=>()=>{},fileSdk:{},portalApi:{messageCount:async()=>({unread:0})},currentSessionGeneration:()=>1,useRoute:()=>route,useRouter:()=>({push:value=>pushes.push(value)}),usePortalConfigStore:()=>({brand:{schoolName:'虚构学校'}}),useSessionStore:()=>session,WORKSPACE_THEMES,normalizeTheme,themeTokens,INTERNSHIP_TABS,INTERNSHIP_TAB_GROUPS,localStorage:{getItem:()=>null,setItem(){}}}
  const scope=effectScope(),vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {openPages,pageKey,selectedGroup,activeGroup,secondExpanded,thirdExpanded,commonOpen,openView,closePage}')(...Object.values(deps)))
  t.after(()=>scope.stop());return {vm,route,session,pushes}
}
test('双列菜单复用全部学生入口，默认选中真实分组且不存在教师管理菜单',()=>{
  const keys=INTERNSHIP_TAB_GROUPS.flatMap(g=>g.keys)
  assert.equal(new Set(keys).size,INTERNSHIP_TABS.length);assert.deepEqual(new Set(keys),new Set(INTERNSHIP_TABS.map(t=>t.key)))
  assert.equal(keys.includes('system'),false)
})
test('外壳页签保留批次与原单深链，切页不误带旧对象参数',async t=>{
  const {vm,route,pushes}=page(t);assert.equal(vm.selectedGroup.value,'process');assert.match(vm.openPages.value[0].destination,/reportId=99/)
  vm.openView('enterprises');assert.deepEqual(pushes.at(-1),{path:'/internship',query:{batchId:'77',view:'enterprises'}})
  route.query={view:'enterprises',batchId:'77'};route.fullPath='/internship?view=enterprises&batchId=77';await nextTick()
  assert.equal(vm.selectedGroup.value,'selection');assert.equal(vm.openPages.value.length,2)
  vm.closePage(vm.openPages.value[1]);assert.match(pushes.at(-1),/reportId=99/)
  vm.closePage(vm.openPages.value[0]);assert.equal(vm.openPages.value.length,1)
})
test('换学生身份后清除上一身份打开页签及常用区状态',async t=>{
  const {vm,session,route}=page(t);vm.commonOpen.value=true;vm.thirdExpanded.value=true
  route.query={view:'leave',batchId:'77'};route.fullPath='/internship?view=leave&batchId=77';await nextTick();assert.equal(vm.openPages.value.length,2)
  session.user={...session.user,tenantId:'3',userId:'4'};await nextTick()
  assert.equal(vm.openPages.value.length,1);assert.equal(vm.commonOpen.value,false);assert.equal(vm.thirdExpanded.value,false)
})
test('登录过渡和根路径不生成重复首页页签',async t=>{
  const {vm,route,session}=page(t);route.path='/login';route.fullPath='/login';session.user={...session.user,userId:'3'};await nextTick();assert.equal(vm.openPages.value.length,0)
  route.path='/';route.fullPath='/';await nextTick();assert.equal(vm.openPages.value.length,0)
  route.path='/internship';route.query={view:'overview'};route.fullPath='/internship?view=overview';await nextTick();assert.equal(vm.openPages.value.length,1)
})


test('独立办理页的菜单页签正确高亮，档案与选岗保留原季，跨事项不夹带原单',async t=>{
  const {vm,route,pushes}=page(t);route.path='/internship/selection';route.meta={internshipView:'selection'};route.query={batchId:'77',campaignId:'88',recordId:'99'};route.fullPath='/internship/selection?batchId=77&campaignId=88&recordId=99';await nextTick()
  assert.equal(vm.selectedGroup.value,'selection');vm.openView('profile');assert.deepEqual(pushes.at(-1),{path:'/internship/profile',query:{batchId:'77',campaignId:'88',recordId:'99'}})
  vm.openView('safety');assert.deepEqual(pushes.at(-1),{path:'/internship/compliance',query:{batchId:'77'}})
  vm.openView('materials');assert.deepEqual(pushes.at(-1),{path:'/internship/materials',query:{batchId:'77'}})
})
