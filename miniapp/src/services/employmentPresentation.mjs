// Pure presentation contract shared by the student/teacher clients.
export const employmentFields = Object.freeze([
  {key:'studentName',label:'姓名',group:'identity',school:true},
  {key:'studentNo',label:'学号',group:'identity',school:true},
  {key:'collegeName',label:'院系',group:'identity',school:true},
  {key:'majorName',label:'专业',group:'identity',school:true},
  {key:'grade',label:'年级',group:'identity',school:true},
  {key:'className',label:'班级',group:'identity',school:true},
  {key:'enrollmentYear',label:'入校年份',group:'identity',max:4},
  {key:'studentPhone',label:'学生手机',group:'identity',max:30},
  {key:'employmentType',label:'就业类型',group:'company',max:50},
  {key:'companyName',label:'单位名称',group:'company',max:200},
  {key:'creditCode',label:'统一社会信用代码',group:'company',max:18},
  {key:'companyAddress',label:'企业所在地址',group:'company',max:300},
  {key:'companyScale',label:'企业规模',group:'company',max:50},
  {key:'companyPhone',label:'企业电话',group:'company',max:50},
  {key:'companyEmail',label:'企业邮箱',group:'company',max:200},
  {key:'hrContact',label:'企业人事联系人',group:'company',max:100},
  {key:'companyNature',label:'企业性质',group:'company',max:50},
  {key:'industry',label:'所属行业',group:'company',max:100},
  {key:'jobCategory',label:'岗位类别',group:'job',max:100},
  {key:'positionName',label:'岗位名称',group:'job',max:100},
  {key:'majorMatch',label:'专业是否对口',group:'job',boolean:true},
  {key:'salary',label:'月薪（元）',group:'job',max:12},
  {key:'agreementNo',label:'协议书编号',group:'job',max:100}
])
export const employmentGroups = Object.freeze([{key:'identity',label:'学生信息'},{key:'company',label:'就业与单位信息'},{key:'job',label:'岗位与协议'}])
export const employmentStatuses = Object.freeze([{value:'ALL',label:'全部'},{value:'SUBMITTED',label:'待实习老师核对'},{value:'RETURNED',label:'已退回补正'},{value:'APPROVED',label:'实习核对已通过'}])
const SOURCES = {SCHOOL_PROFILE:'学校档案',SCHOOL_CONTACT:'学校联系方式',STUDENT_DECLARED:'学生本次填报',CURRENT_INTERNSHIP_COMPANY:'当前正式实习企业'}
export const employmentStatusLabel = status => employmentStatuses.find(x=>x.value===status)?.label || '状态待确认'
export function employmentProgressLabel(row) {
  if (row?.status !== 'APPROVED') return employmentStatusLabel(row?.status)
  return ({APPROVED:'就业审批已通过',RETURNED:'就业审批已退回',REJECTED:'就业审批未通过'})[row.formalSubmission?.status] || '待就业老师审批'
}
export const employmentModeLabel = mode => ({EMPLOYMENT:'就业上报',INTERNSHIP_TRANSFER:'实习转就业'})[mode] || '登记方式待确认'
export const employmentSourceLabel = source => SOURCES[source] || '来源待核实'
export function employmentVersionView(value) {
  if (!value) return null
  const fields=value.fields||{}
  return {...value,id:String(value.id||''),modeLabel:employmentModeLabel(value.registrationMode),
    fieldRows:employmentFields.map(field=>({...field,value:field.boolean ? (fields[field.key]===true?'是':fields[field.key]===false?'否':'尚未提供') : String(fields[field.key]??'')||'尚未提供',sourceLabel:employmentSourceLabel(value.sources?.[field.key])})),
    review:value.review ? {...value.review,actionLabel:({APPROVE:'实习核对通过',RETURN:'退回补正'})[value.review.action]||'核对结果待确认'} : null}
}
export function employmentView(row) {
  if (!row) return null
  return {...row,id:String(row.id||''),batchId:String(row.batchId||''),internshipId:String(row.internshipId||''),statusLabel:employmentProgressLabel(row),
    current:employmentVersionView(row.current),history:(row.history||[]).map(employmentVersionView)}
}
export function employmentDraft(prefill={},row=null) {
  const fields=Object.fromEntries(employmentFields.map(field=>[field.key,field.boolean?null:'']))
  Object.assign(fields,prefill.identity||{},row?.current?.fields||{})
  for(const field of employmentFields.filter(x=>x.school)) fields[field.key]=prefill.identity?.[field.key]||''
  if(prefill.identityEditable?.enrollmentYear===false) fields.enrollmentYear=prefill.identity?.enrollmentYear||''
  return {mode:row?.current?.registrationMode||'EMPLOYMENT',fields,attachments:[...(row?.current?.attachments||[])],correctionReason:''}
}
export function validateEmployment(form,prefill={}) {
  if (Array.isArray(prefill.employmentTypeOptions) && !prefill.employmentTypeOptions.some(option=>option.value===form.fields.employmentType)) return {key:'employmentType',text:'请选择学校已启用的就业类型'}
  for(const field of employmentFields) {
    const value=form.fields[field.key]
    if(field.boolean ? typeof value!=='boolean' : !String(value??'').trim()) return {key:field.key,text:(field.school?'学校档案缺少':'请填写')+field.label+(field.school?'，请联系学校补齐':'')}
    if(field.max && String(value).trim().length>field.max) return {key:field.key,text:field.label+'最多'+field.max+'字'}
  }
  if(!/^\d{4}$/.test(form.fields.enrollmentYear)) return {key:'enrollmentYear',text:'入校年份应为四位年份'}
  if(!/^\+?[0-9 ()-]{6,30}$/.test(form.fields.studentPhone)) return {key:'studentPhone',text:'请核对学生手机格式'}
  if(!/^[0-9A-HJ-NPQRTUWXY]{18}$/i.test(form.fields.creditCode)) return {key:'creditCode',text:'统一社会信用代码应为18位合法字符'}
  if(!/^\+?[0-9 ()-]{6,50}$/.test(form.fields.companyPhone)) return {key:'companyPhone',text:'请核对企业电话格式'}
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.fields.companyEmail)) return {key:'companyEmail',text:'请核对企业邮箱格式'}
  if(!/^\d+(\.\d{1,2})?$/.test(String(form.fields.salary)) || Number(form.fields.salary)>999999999.99) return {key:'salary',text:'月薪应为非负金额，最多保留两位小数'}
  if(form.mode==='INTERNSHIP_TRANSFER' && (!prefill.canTransfer || form.fields.companyName!==prefill.transfer?.companyName || form.fields.creditCode.toUpperCase()!==(prefill.transfer?.creditCode||'').toUpperCase())) return {key:'companyName',text:'请核对当前正式实习企业后再转就业'}
  return null
}
