import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { normalizeFileReadiness } from '../src/services/fileReadiness.mjs'

const script = fs.readFileSync(new URL('../src/services/fileSdk.js', import.meta.url), 'utf8')
  .replace(/^import[^\n]+\n/gm, '').replace(/^export default[^\n]+$/gm, '').replace(/export (const|function|async function)/g, '$1')
function chooser(api) { return new Function('uni', 'FILE_SCAN_TEXT', 'normalizeFileReadiness', script + '\nreturn chooseSingleFile')(api, {}, normalizeFileReadiness) }
test('真实图片原文件名及扩展名保留，不能把PNG改名为JPEG', async () => {
  for (const name of ['合成原图.png', '合成原图.jpeg', '合成原图.jpg']) {
    const choose = chooser({ chooseImage: x => x.success({ tempFilePaths: ['blob:original'], tempFiles: [{ name, size: 100 }] }) })
    assert.deepEqual(await choose({ kind: 'image' }), { path: 'blob:original', name, size: 100 })
  }
})
test('原生照片无扩展名时按设备真实图片类型命名；未知类型拒绝', async () => {
  const image = { tempFilePaths: ['wxfile://temporary-image'], tempFiles: [{ size: 100 }] }
  const choose = chooser({ chooseImage: x => x.success(image), getImageInfo: x => x.success({ type: 'png' }) })
  assert.equal((await choose({ kind: 'image' })).name, '实习照片.png')
  const denied = chooser({ chooseImage: x => x.success(image), getImageInfo: x => x.success({ type: 'unknown' }) })
  await assert.rejects(denied({ kind: 'image' }), e => /格式无法识别/.test(e.message))
})
test('文件选择器退化到选图也保留原图文件名', async () => {
  const choose = chooser({ chooseImage: x => x.success({ tempFilePaths: ['camera.png'], tempFiles: [{ size: 80 }] }) })
  assert.equal((await choose()).name, 'camera.png')
})

test('计划附件下载途中切换页面，原文件不会在另一计划中打开',async()=>{
  let resolve,current=true,opens=0
  const open=new Function('uni','FILE_SCAN_TEXT','normalizeFileReadiness','realRequest','realDownload',script+';return openBusinessFile')(
    {openDocument:()=>{opens++}}, {}, normalizeFileReadiness,
    async()=>({fileId:'9',fileName:'计划.xlsx',status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,allowedActions:['preview','download']}),
    ()=>new Promise(r=>resolve=r))
  const work=open('9','计划.xlsx',{isCurrent:()=>current})
  await new Promise(r=>setImmediate(r));current=false;resolve({tempFilePath:'local-file'});assert.equal(await work,null);assert.equal(opens,0)
})

test('页内原件在元数据回读后离页，不续发旧下载',async()=>{
 let resolve,current=true,downloads=0
 const open=new Function('uni','FILE_SCAN_TEXT','normalizeFileReadiness','realRequest','realDownload',script+';return openBusinessFileInline')({}, {}, normalizeFileReadiness,()=>new Promise(r=>resolve=r),async()=>{downloads++})
 const work=open('9',{isCurrent:()=>current});current=false
 resolve({fileId:'9',fileName:'保单.png',status:'AVAILABLE',scanStatus:'CLEAN',allowedActions:['preview','download']})
 assert.equal(await work,null);assert.equal(downloads,0)
})
