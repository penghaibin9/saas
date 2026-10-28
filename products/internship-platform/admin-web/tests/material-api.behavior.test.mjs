import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

test('material client sends supported template purpose, version and shared filters', async () => {
  const reads=[],uploads=[],downloads=[]
  const source=fs.readFileSync(new URL('../src/modules/internship/api/material-center.api.js',import.meta.url),'utf8')
    .replace(/^import[^\n]*\n/gm,'').replace('export const internshipMaterialCenterApi','const internshipMaterialCenterApi')
    .replace('export default internshipMaterialCenterApi','return internshipMaterialCenterApi')
  const api=new Function('request','fileSdk','buildPreviewDescriptorFromFile',source)(
    (path,options)=>{reads.push({path,options})},
    {upload:(file,options)=>uploads.push(options),downloadFrom:path=>downloads.push(path)},()=>{})
  api.uploadRequirementTemplate({name:'合成.xlsx'})
  assert.equal(uploads[0].bizType,'INTERNSHIP_MATERIAL_TEMPLATE')
  api.downloadRequirementTemplate('9007199254741001','9007199254741002')
  assert.match(downloads[0],/9007199254741001\/template\/download\?templateVersionId=9007199254741002$/)
  const filters={state:'RETURNED',keyword:'合成 & 学生',collegeId:'11',majorId:'12',classId:'13',unused:''}
  api.requirementCoverage('2',filters);api.downloadRequirementPackage('2',filters)
  assert.equal(reads[0].options.params,filters)
  const query=new URL(downloads[1],'http://127.0.0.1').searchParams
  assert.equal(query.get('state'),'RETURNED');assert.equal(query.get('keyword'),filters.keyword)
  assert.equal(query.get('classId'),'13');assert.equal(query.has('unused'),false)
})
