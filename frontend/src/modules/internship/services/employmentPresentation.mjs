// The PC client renders the labels supplied by the authoritative declaration API.
export const employmentStatuses = Object.freeze([{value:'ALL',label:'全部'},{value:'SUBMITTED',label:'待实习老师核对'},{value:'RETURNED',label:'已退回补正'},{value:'APPROVED',label:'实习预审已通过'}])
const SOURCES={SCHOOL_PROFILE:'学校档案',SCHOOL_CONTACT:'学校联系方式',STUDENT_DECLARED:'学生本次填报',CURRENT_INTERNSHIP_COMPANY:'当前正式实习企业'}
const FIELD_GROUPS=[
  {label:'学生信息',keys:['studentName','studentNo','collegeName','majorName','grade','className','enrollmentYear','studentPhone']},
  {label:'就业与单位信息',keys:['employmentType','companyName','creditCode','companyAddress','companyScale','companyPhone','companyEmail','hrContact','companyNature','industry']},
  {label:'岗位与协议',keys:['jobCategory','positionName','majorMatch','salary','agreementNo']}
]
function versionView(version,labels,sensitiveVisible){
  if(!version)return null
  const fieldRows=Object.entries(labels).map(([key,label])=>({key,label,value:typeof version.fields?.[key]==='boolean'?(version.fields[key]?'是':'否'):String(version.fields?.[key]??'')||'尚未提供',sourceLabel:SOURCES[version.sources?.[key]]||'来源待核实'}))
  for(const field of fieldRows)if(!sensitiveVisible && ['studentPhone','companyAddress','companyPhone','companyEmail','hrContact','salary','agreementNo'].includes(field.key) && field.value==='已隐藏，请说明核验用途后查看')field.value='已隐藏'
  const groups=[...FIELD_GROUPS,{label:'其他信息',keys:fieldRows.filter(field=>!FIELD_GROUPS.some(group=>group.keys.includes(field.key))).map(field=>field.key)}]
  const fieldGroups=groups.map(group=>{
    const fields=fieldRows.filter(field=>group.keys.includes(field.key)),counts=new Map()
    for(const field of fields)counts.set(field.sourceLabel,(counts.get(field.sourceLabel)||0)+1)
    return {label:group.label,fields,source:[...counts].sort((a,b)=>b[1]-a[1])[0]?.[0]||'来源待核实'}
  }).filter(group=>group.fields.length)
  return {...version,id:String(version.id||''),modeLabel:({EMPLOYMENT:'就业上报',INTERNSHIP_TRANSFER:'实习转就业'})[version.registrationMode]||'登记方式待确认',
    fieldRows,fieldGroups,
    review:version.review?{...version.review,actionLabel:({APPROVE:'实习预审通过',RETURN:'退回补正'})[version.review.action]||'审核结果待确认'}:null}
}
export function employmentView(row){
  if(!row)return null
  const labels=row.fieldLabels||{}
  return {...row,id:String(row.id||''),batchId:String(row.batchId||''),internshipId:String(row.internshipId||''),
    statusLabel: row.summaryStatusLabel || (row.status === 'APPROVED' ? formalProgressLabel(row.formalSubmission) : employmentStatuses.find(x=>x.value===row.status)?.label) || '状态待确认',
    current:versionView(row.current,labels,row.sensitiveVisible),history:(row.history||[]).map(x=>versionView(x,labels,row.sensitiveVisible))}
}

export function formalProgressLabel(submission) {
  return ({ APPROVED: '就业审批已通过', RETURNED: '就业审批已退回', REJECTED: '就业审批未通过' })[submission?.status] || '待就业老师审批'
}
