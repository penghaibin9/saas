// The PC client renders the labels supplied by the authoritative declaration API.
export const employmentStatuses = Object.freeze([{value:'ALL',label:'全部'},{value:'SUBMITTED',label:'待教师审核'},{value:'RETURNED',label:'已退回补正'},{value:'APPROVED',label:'已核验'}])
const SOURCES={SCHOOL_PROFILE:'学校档案',SCHOOL_CONTACT:'学校联系方式',STUDENT_DECLARED:'学生本次填报',CURRENT_INTERNSHIP_COMPANY:'当前正式实习企业'}
function versionView(version,labels){
  if(!version)return null
  return {...version,id:String(version.id||''),modeLabel:({EMPLOYMENT:'就业上报',INTERNSHIP_TRANSFER:'实习转就业'})[version.registrationMode]||'登记方式待确认',
    fieldRows:Object.entries(labels).map(([key,label])=>({key,label,value:typeof version.fields?.[key]==='boolean'?(version.fields[key]?'是':'否'):String(version.fields?.[key]??'')||'尚未提供',sourceLabel:SOURCES[version.sources?.[key]]||'来源待核实'})),
    review:version.review?{...version.review,actionLabel:({APPROVE:'核验通过',RETURN:'退回补正'})[version.review.action]||'审核结果待确认'}:null}
}
export function employmentView(row){
  if(!row)return null
  const labels=row.fieldLabels||{}
  return {...row,id:String(row.id||''),batchId:String(row.batchId||''),internshipId:String(row.internshipId||''),
    statusLabel:employmentStatuses.find(x=>x.value===row.status)?.label||'状态待确认',current:versionView(row.current,labels),history:(row.history||[]).map(x=>versionView(x,labels))}
}
