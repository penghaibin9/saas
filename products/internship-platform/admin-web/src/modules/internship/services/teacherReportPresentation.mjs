export const teacherReportTypes = Object.freeze([
  {value:'WEEKLY',label:'周报',minimum:30,maximumKey:'weeklyMaxWords'},
  {value:'MONTHLY',label:'月报',minimum:100,maximumKey:'monthlyMaxWords'},
  {value:'SUMMARY',label:'总结',minimum:300,maximumKey:'summaryMaxWords'}
])
export function periodText(type, key) {
  if(type==='SUMMARY') return '实习总结'
  const week=/^(\d{4})-W(\d{2})$/.exec(String(key||''))
  if(type==='WEEKLY' && week) return `${week[1]}年第${Number(week[2])}周`
  const month=/^(\d{4})-(\d{2})$/.exec(String(key||''))
  if(type==='MONTHLY' && month) return `${month[1]}年${Number(month[2])}月`
  return '周期待核实'
}
export function teacherReportView(row={}) {
  return {...row,id:String(row.id||''),batchId:String(row.batchId||''),
    typeLabel:teacherReportTypes.find(t=>t.value===row.reportType)?.label||'类型待确认',
    periodLabel:periodText(row.reportType,row.periodKey),edition:Number(row.version||0)+1,
    attachments:(row.attachments||[]).filter(Boolean).map(f=>({...f,fileId:String(f.fileId)}))}
}
export function reportValidation(form,rules={}) {
  const type=teacherReportTypes.find(t=>t.value===form.reportType)
  if(!type) return '请选择报告类型'
  if(form.reportType!=='SUMMARY' && !String(form.periodKey||'').trim()) return '请选择报告周期'
  const length=Array.from(String(form.content||'').trim()).length
  if(length<type.minimum) return `${type.label}正文至少填写${type.minimum}个字`
  if(length>Number(rules[type.maximumKey]||12000)) return `${type.label}正文超过当前批次字数上限`
  if(form.studentCount!=='' && (!/^\d+$/.test(String(form.studentCount)) || Number(form.studentCount)>2147483647)) return '涉及学生人数请填写非负整数'
  return ''
}
