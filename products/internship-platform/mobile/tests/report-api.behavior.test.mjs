import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

test('report PDF helper validates original identity and bytes before downloading', async () => {
  let clicks=0, current=true
  const original={reportId:'9007199254741001',reportKind:'PROCESS',batchId:'18',internshipId:'18',mediaType:'application/pdf',contentBase64:Buffer.from('%PDF-1.4\n').toString('base64')}
  let response=original
  const source=fs.readFileSync(new URL('../src/services/studentApi.js',import.meta.url),'utf8')
    .replace(/^import[^\n]*\n/gm,'').replace('export const studentApi','const studentApi').replace('export default studentApi','return studentApi')
  const api=new Function('realRequest','realDownload','internship','uni','document','URL','setTimeout',source)(
    async()=>response,()=>{}, {}, {base64ToArrayBuffer:value=>Uint8Array.from(Buffer.from(value,'base64')).buffer},
    {createElement:()=>({click(){clicks++},remove(){}}),body:{appendChild(){}}},
    {createObjectURL:()=> 'blob:synthetic',revokeObjectURL(){}},fn=>fn())
  const download=()=>api.downloadInternshipReportPdf('18','18','PROCESS',original.reportId,()=>current)
  await download();assert.equal(clicks,1)
  response={...original,internshipId:'other'};await assert.rejects(download,/来源不一致/)
  response={...original,contentBase64:Buffer.from('not a pdf').toString('base64')};await assert.rejects(download,/内容无效/)
  current=false;response=original;await download();assert.equal(clicks,1)
})
