const STEP_LABELS = {
  ACTIVATE: '账号激活', INFO: '信息核对', MATERIAL: '材料审核', PAYMENT: '缴费 / 绿色通道',
  DORM: '宿舍安排', CHECKIN: '现场报到', CONFIRM: '学院确认',
  IDENTITY: '身份核验', FINANCE: '绿色通道'
}

export function orientationStepLabel(step) {
  const label = typeof step?.label === 'string' ? step.label.trim() : ''
  return /[\u3400-\u9fff]/.test(label) ? label : (STEP_LABELS[step?.key] || '报到事项')
}
