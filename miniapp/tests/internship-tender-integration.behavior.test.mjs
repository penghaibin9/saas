import assert from 'node:assert/strict'
import test from 'node:test'
import { internshipDraftScope, readInternshipDraft, writeInternshipDraft } from '../src/services/internshipDraftStorage.mjs'
import { clearSensitiveLocalDrafts } from '../src/services/sensitiveDraftStorage.js'
import { employmentProgressLabel, employmentView, validateEmployment } from '../src/services/employmentPresentation.mjs'
import { normalizeMobileVolunteerGroup } from '../src/modules/internshipVolunteerModel.js'

function storage(t) {
  const previous=globalThis.uni, values=new Map()
  globalThis.uni={getStorageSync:key=>values.get(key),setStorageSync:(key,value)=>values.set(key,value),
    getStorageInfoSync:()=>({keys:[...values.keys()]}),removeStorageSync:key=>values.delete(key)}
  t.after(()=>{globalThis.uni=previous})
  return values
}
const session=(tenant='1',user='2',role='STUDENT')=>({logged:true,realUser:{tenantId:tenant,currentRole:{contextId:'3'}},identity:{userId:user,roleCode:role}})

test('实习草稿与登录会话分离，切换学校、账号、身份或批次后不能读到旧正文',t=>{
  const values=storage(t),current=session(),context=['4','5'],draft={content:'仅属于本次实习的正文'}
  values.set('gx_session_v1',{logged:true,untouched:true})
  assert.equal(writeInternshipDraft(current,'weekly-report',context,draft),true)
  assert.deepEqual(readInternshipDraft(current,'weekly-report',context),draft)
  for(const other of [session('8'),session('1','9'),session('1','2','INTERN_MENTOR')]){
    assert.equal(readInternshipDraft(other,'weekly-report',context),null)
  }
  assert.equal(readInternshipDraft(current,'weekly-report',['6','5']),null)
  assert.equal(readInternshipDraft(current,'weekly-report',['4','7']),null)
  assert.deepEqual(values.get('gx_session_v1'),{logged:true,untouched:true})
})

test('缺少可信学校或已退出时不保存实习草稿',t=>{
  const values=storage(t)
  assert.equal(internshipDraftScope({logged:true,identity:{userId:'2',roleCode:'STUDENT'}}), '')
  assert.equal(writeInternshipDraft({...session(),logged:false},'weekly-report',['4','5'],{content:'未登录'}),false)
  assert.equal(values.size,0)
})

test('退出清理删除实习报告草稿，保留其他业务与登录配置',t=>{
  const values=storage(t)
  writeInternshipDraft(session(),'weekly-report',['4','5'],{content:'待清理'})
  writeInternshipDraft(session('1','9','INTERN_MENTOR'),'teacher-report-page',['4'],{page:2,total:30})
  values.set('unrelated-preference','preserved')
  clearSensitiveLocalDrafts()
  assert.deepEqual([...values.entries()],[['unrelated-preference','preserved']])
})

test('实习核对通过后显示等待就业审批，正式通过也不冒充材料核验',()=>{
  assert.equal(employmentProgressLabel({status:'SUBMITTED'}),'待实习老师核对')
  assert.equal(employmentProgressLabel({status:'APPROVED'}),'待就业老师审批')
  assert.equal(employmentProgressLabel({status:'APPROVED',formalSubmission:{status:'APPROVED'}}),'就业审批已通过')
  assert.equal(employmentProgressLabel({status:'APPROVED',formalSubmission:{status:'RETURNED'}}),'就业审批已退回')
  assert.equal(employmentProgressLabel({status:'APPROVED',formalSubmission:{status:'REJECTED'}}),'就业审批未通过')
  assert.equal(employmentView({id:'9007199254740993001',status:'APPROVED',formalSubmission:{submissionId:'9007199254740993002',status:'SUBMITTED'}}).statusLabel,'待就业老师审批')
  assert.equal(employmentProgressLabel({status:'RAW_INTERNAL_ENUM'}),'状态待确认')
})

test('就业类型只接受学校正式字典中的选项，不能默默猜测自由文本',()=>{
  const result=validateEmployment({fields:{employmentType:'自定义内部值'}},{employmentTypeOptions:[{value:'签约就业',label:'签约就业'}]})
  assert.deepEqual(result,{key:'employmentType',text:'请选择学校已启用的就业类型'})
})

test('招聘原志愿组保留稳定编号和退回原因，能继续进入同一办理结果',()=>{
  const row=normalizeMobileVolunteerGroup({id:'9007199254740993001',status:'NEEDS_REVISION',revisionReason:'请补齐对应岗位的材料',version:4})
  assert.equal(row.id,'9007199254740993001')
  assert.equal(row.revisionReason,'请补齐对应岗位的材料')
  assert.equal(row.version,4)
})
