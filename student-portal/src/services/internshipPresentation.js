export function internshipLeaveStage(row = {}) {
  if (row.status === 'RETURNED') return row.returnAcknowledged === true
    ? { label:'销假办结', tone:'success', next:'指导教师已确认返岗，本次请假已结束。' }
    : row.returnAcknowledged === false
      ? { label:'待导师核实返岗', tone:'warn', next:'已登记返岗，下一步由指导教师核实。' }
      : { label:'返岗确认待核对', tone:'warn', next:'请重新读取原单核对导师确认结果。' }
  const labels={PENDING:'审批中',APPROVED:'已通过',REJECTED:'已驳回',NEEDS_REVISION:'已退回，请补正',WITHDRAWN:'已撤回',OVERDUE:'超期未返岗'}
  const next={PENDING:'等待学校配置的审批流程办理。',APPROVED:'返岗后沿原单登记销假。',NEEDS_REVISION:'请按原意见补正后沿原单重交。',OVERDUE:'请及时登记返岗或联系指导教师核对。'}
  return {label:labels[row.status] || '状态待核对',tone:row.status==='APPROVED'?'success':row.status==='REJECTED'?'danger':'warn',next:next[row.status] || '原单与历次办理记录继续保留。'}
}

