import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { loadReportMedia, releasePreview } from '../src/services/reportMedia.mjs'

function page(request,sdk,t){
  const source=fs.readFileSync(new URL('../src/components/SchoolServiceInfo.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import [^\n]*\n/gm,'').replace('export default','return')
  let generation=1;const released=[]
  t.mock.method(URL,'revokeObjectURL',url=>released.push(url))
  const component=new Function('realRequest','currentSessionGeneration','fileSdk','loadReportMedia','releasePreview',script)(
    request,()=>generation,sdk,loadReportMedia,releasePreview)
  const vm={...Object.fromEntries(Object.entries(component.props||{}).map(([key,prop])=>[key,prop.default])),...component.data()};for(const [key,method] of Object.entries(component.methods))vm[key]=method.bind(vm)
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const render=compile(template,{isCustomElement:tag=>['view','text','image'].includes(tag)})
  return {vm,released,tree:()=>render(vm,[]),html:()=>renderToString(createSSRApp({render:()=>render(vm,[])})),switchIdentity:()=>generation++,unmount:()=>component.beforeUnmount.call(vm)}
}
function findNode(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of Array.isArray(node.children)?node.children:[]){const found=findNode(child,predicate);if(found)return found}return null}
const service=id=>({brand:{schoolName:'合成学校',platformName:'合成实习平台',logoFileId:id},service:{faq:[]}})
const meta=id=>({fileId:id,fileName:'校徽.png',ext:'png',mimeType:'image/png',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['download','preview']})

test('学校服务紧凑入口点击展开真实联系方式与授权校徽，收起不重复品牌',async t=>{
  const config=service('11');config.service={contactPhone:'0731-12345678',supervisionPhone:'0731-87654321',responsibleName:'合成承办人',reminderText:'合成学校服务说明',faq:[{question:'怎么联系老师？',answer:'从实习求助提交问题。'}]}
  const p=page(async()=>config,{metadata:async id=>meta(id),download:async()=>({tempFilePath:'blob:logo'})},t);p.vm.compact=true;await p.vm.load()
  let html=await p.html();assert.match(html,/咨询与帮助/);assert.doesNotMatch(html,/合成实习平台|0731-12345678|blob:logo/)
  const toggle=findNode(p.tree(),node=>node.type==='button'&&node.props?.onClick);assert.ok(toggle);toggle.props.onClick()
  assert.equal(p.vm.expanded,true);html=await p.html()
  for(const text of ['合成学校','0731-12345678','0731-87654321','合成承办人','怎么联系老师？','从实习求助提交问题。','blob:logo'])assert.ok(html.includes(text),text)
  assert.doesNotMatch(html,/合成实习平台/)
  findNode(p.tree(),node=>node.type==='button'&&node.props?.onClick).props.onClick();assert.equal(p.vm.expanded,false)
  assert.doesNotMatch(await p.html(),/0731-12345678|blob:logo/);assert.equal(p.vm.logoUrl,'blob:logo')
})

test('学校服务默认仍展示原品牌和校徽且可展开',async t=>{
  const p=page(async()=>service('11'),{metadata:async id=>meta(id),download:async()=>({tempFilePath:'blob:logo'})},t);await p.vm.load()
  assert.equal(p.vm.compact,false);const html=await p.html();assert.match(html,/合成实习平台/);assert.match(html,/blob:logo/)
  findNode(p.tree(),node=>node.props?.class==='school-service-head').props.onClick();assert.equal(p.vm.expanded,true);assert.match(await p.html(),/合成学校/)
})

test('学校服务紧凑展开保留失败回执与真实重试，校徽失败不隐藏电话',async t=>{
  let fail=true;const config=service('11');config.service.contactPhone='0731-12345678'
  const p=page(async()=>{if(fail)throw Error('offline');return config},{metadata:async id=>({...meta(id),readyForBusiness:false})},t);p.vm.compact=true;await p.vm.load()
  findNode(p.tree(),node=>node.type==='button'&&node.props?.onClick).props.onClick();let html=await p.html();assert.match(html,/学校服务暂时无法读取，请重试/);assert.match(html,/重新读取/)
  fail=false;const retry=findNode(p.tree(),node=>node.type==='button'&&node.props?.onClick===p.vm.load);assert.ok(retry);await retry.props.onClick()
  html=await p.html();assert.match(html,/校徽暂时无法读取/);assert.match(html,/0731-12345678/);assert.doesNotMatch(html,/学校服务暂时无法读取，请重试/);assert.equal(p.vm.expanded,true)
})

test('移动端校徽沿受控文件读取，重读释放旧图片，扫描或权限拒绝不阻断学校服务',async t=>{
  let allowed=true,downloaded=0
  const p=page(async()=>service('11'),{metadata:async id=>({...meta(id),readyForBusiness:allowed}),download:async()=>{downloaded++;return {tempFilePath:'blob:logo'}}},t)
  await p.vm.load();assert.equal(p.vm.logoUrl,'blob:logo');assert.equal(downloaded,1)
  allowed=false;await p.vm.load();assert.equal(p.vm.logoUrl,'');assert.deepEqual(p.released,['blob:logo'])
  assert.equal(downloaded,1);assert.equal(p.vm.config.brand.schoolName,'合成学校');assert.match(p.vm.logoError,/校徽暂时无法读取/)
  allowed=true;await p.vm.load();p.unmount();assert.equal(p.vm.logoUrl,'');assert.equal(p.released.length,2)
})

test('更换身份期间迟到校徽和服务失败均不写入当前页面',async t=>{
  let finishDownload,startDownload
  const downloadStarted=new Promise(resolve=>{startDownload=resolve})
  const p=page(async()=>service('12'),{metadata:async id=>meta(id),download:()=>new Promise(resolve=>{finishDownload=resolve;startDownload()})},t)
  const first=p.vm.load();await downloadStarted
  p.switchIdentity();finishDownload({tempFilePath:'blob:old-school'});await first
  assert.equal(p.vm.logoUrl,'');assert.deepEqual(p.released,['blob:old-school'])
  let rejectService
  const failing=page(()=>new Promise((_,reject)=>{rejectService=reject}),{},t)
  const old=failing.vm.load();failing.switchIdentity();rejectService(new Error('offline'));await old
  assert.equal(failing.vm.error,'');assert.equal(failing.vm.config,null)
})

test('旧加载不覆盖新学校校徽，图片解析失败释放预览并保留服务文字',async t=>{
  let index=0,startOld,startNew;const replies=[]
  const oldStarted=new Promise(resolve=>{startOld=resolve}),newStarted=new Promise(resolve=>{startNew=resolve})
  const p=page(async()=>service(String(++index)),{metadata:async id=>meta(id),download:id=>new Promise(resolve=>{replies.push({id,resolve});(id==='1'?startOld:startNew)()})},t)
  const old=p.vm.load();await oldStarted
  const current=p.vm.load();await newStarted
  replies[1].resolve({tempFilePath:'blob:new-school'});await current
  replies[0].resolve({tempFilePath:'blob:old-school'});await old
  assert.equal(p.vm.logoUrl,'blob:new-school');assert.equal(p.vm.config.brand.logoFileId,'2')
  assert.deepEqual(p.released,['blob:old-school'])
  p.vm.logoFailed();assert.equal(p.vm.logoUrl,'');assert.equal(p.vm.config.brand.schoolName,'合成学校')
  assert.deepEqual(p.released,['blob:old-school','blob:new-school'])
})
