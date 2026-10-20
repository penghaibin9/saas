export const CAMPAIGN_WINDOWS = [
  { label: '企业邀请', start: 'inviteStartAt', end: 'inviteEndAt', hint: '学校向企业发出本轮邀请' },
  { label: '岗位报送', start: 'positionSubmitStartAt', end: 'positionSubmitEndAt', hint: '企业准备并报送实习岗位' },
  { label: '学生选岗', start: 'studentSelectStartAt', end: 'studentSelectEndAt', hint: '学生浏览岗位并提交志愿' },
  { label: '企业决策', start: 'enterpriseDecisionStartAt', end: 'enterpriseDecisionEndAt', hint: '企业处理学生申请' },
  { label: '学校确认', start: 'schoolConfirmStartAt', end: 'schoolConfirmEndAt', hint: '学校完成录用结果确认' }
]
export const MATERIAL_SECTIONS = [
  { value: 'SELF_INTRO', label: '自我介绍' }, { value: 'SKILLS', label: '技能标签' },
  { value: 'AVAILABILITY', label: '可到岗时间' }, { value: 'LOCATION_PREFERENCES', label: '意向地区' }
]
export const MATERIAL_TYPES = [
  { value: 'SKILL_EVIDENCE', label: '技能证明' }, { value: 'CERTIFICATE', label: '证书' },
  { value: 'PROJECT', label: '项目经历' }, { value: 'PRACTICE', label: '实践经历' },
  { value: 'AWARD', label: '获奖记录' }, { value: 'PORTFOLIO', label: '作品集' }
]
export const CONTACT_MODES = [
  { value: 'MASKED_ONLY', label: '仅展示脱敏信息' },
  { value: 'AFTER_INTERVIEW', label: '进入面试阶段后共享' },
  { value: 'AFTER_ACCEPT_INTENT', label: '录用意向后共享' },
  { value: 'IMMEDIATE', label: '投递后立即共享' }
]
export function defaultMaterialPolicy() {
  return { schemaVersion: 'V1', profileRequired: false, requiredSections: [], requiredItemTypes: [],
    applicationStatementRequired: false, minStatementLength: 0, resumePdfEnabled: true,
    allowedContactSharingModes: ['MASKED_ONLY', 'AFTER_INTERVIEW', 'AFTER_ACCEPT_INTENT'] }
}
export function unsupportedMaterialPolicy(policy = {}) {
  const defaults = defaultMaterialPolicy()
  if (Object.keys(policy).some((key) => !(key in defaults)) || (policy.schemaVersion && policy.schemaVersion !== 'V1')) return true
  return [['requiredSections', MATERIAL_SECTIONS], ['requiredItemTypes', MATERIAL_TYPES], ['allowedContactSharingModes', CONTACT_MODES]]
    .some(([key, options]) => key in policy && (!Array.isArray(policy[key]) || policy[key].some((v) => !options.some((o) => o.value === v))))
}
export function localCampaignTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  const two = (v) => String(v).padStart(2, '0')
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}T${two(date.getHours())}:${two(date.getMinutes())}:${two(date.getSeconds())}`
}
export function campaignFormModel(detail = {}, batchId = '') {
  const form = { batchId: String(detail.batchId || batchId || ''), campaignCode: detail.campaignCode || '',
    campaignName: detail.campaignName || '', roundNo: detail.roundNo ?? 1, remark: detail.remark || '',
    enterpriseConfirmRequired: detail.enterpriseConfirmRequired ?? false, teacherConfirmSlaHours: detail.teacherConfirmSlaHours ?? 48,
    applicationMaterialPolicy: { ...defaultMaterialPolicy(), ...JSON.parse(JSON.stringify(detail.applicationMaterialPolicy || {})) } }
  for (const field of [...CAMPAIGN_WINDOWS.flatMap((w) => [w.start, w.end]), 'enterpriseAccessEndAt']) form[field] = localCampaignTime(detail[field])
  return form
}
export function campaignFormErrors(form, { preservePolicy = false } = {}) {
  const errors = {}
  if (!form.batchId) errors.batchId = '请选择所属实习批次'
  for (const [field, label, max] of [['campaignCode', '招聘季编码', 100], ['campaignName', '招聘季名称', 200]]) {
    const value = String(form[field] || '').trim()
    if (!value || value.length > max) errors[field] = `${label}须填写 1–${max} 个字符`
  }
  if (!Number.isInteger(Number(form.roundNo)) || Number(form.roundNo) < 1) errors.roundNo = '轮次须为大于零的整数'
  if (!Number.isInteger(Number(form.teacherConfirmSlaHours)) || Number(form.teacherConfirmSlaHours) < 1 || Number(form.teacherConfirmSlaHours) > 168) errors.teacherConfirmSlaHours = '教师确认时限须为 1–168 小时的整数'
  if (String(form.remark || '').length > 500) errors.remark = '备注不能超过 500 字'
  for (const w of CAMPAIGN_WINDOWS) {
    const start = form[w.start], end = form[w.end]
    if (!!start !== !!end) errors[start ? w.end : w.start] = `${w.label}的开始和结束时间需同时填写`
    else if (start && (!Number.isFinite(Date.parse(start)) || !Number.isFinite(Date.parse(end)))) errors[w.start] = `${w.label}时间无效`
    else if (start && Date.parse(start) > Date.parse(end)) errors[w.end] = `${w.label}结束时间不能早于开始时间`
  }
  if (form.enterpriseAccessEndAt) {
    const cutoff = Date.parse(form.enterpriseAccessEndAt)
    if (!Number.isFinite(cutoff)) errors.enterpriseAccessEndAt = '企业访问截止时间无效'
    else if (CAMPAIGN_WINDOWS.some((w) => form[w.end] && Date.parse(form[w.end]) > cutoff)) errors.enterpriseAccessEndAt = '企业访问截止不能早于任一已配置窗口的结束时间'
  }
  if (!preservePolicy) {
    const policy = form.applicationMaterialPolicy
    if (unsupportedMaterialPolicy(policy)) errors.applicationMaterialPolicy = '现有材料规则需按原配置保留'
    if (!Number.isInteger(Number(policy.minStatementLength)) || Number(policy.minStatementLength) < 0 || Number(policy.minStatementLength) > 5000) errors.minStatementLength = '申请说明最低字数须为 0–5000 的整数'
  }
  return errors
}
export function campaignFormBody(form, detail = null) {
  const preservePolicy = !!detail && unsupportedMaterialPolicy(detail.applicationMaterialPolicy || {})
  const errors = campaignFormErrors(form, { preservePolicy })
  if (Object.keys(errors).length) throw new Error(Object.values(errors)[0])
  const body = { batchId: String(form.batchId), campaignCode: form.campaignCode.trim(), campaignName: form.campaignName.trim(),
    roundNo: Number(form.roundNo), remark: form.remark.trim() || null,
    enterpriseConfirmRequired: form.enterpriseConfirmRequired, teacherConfirmSlaHours: Number(form.teacherConfirmSlaHours) }
  for (const field of [...CAMPAIGN_WINDOWS.flatMap((w) => [w.start, w.end]), 'enterpriseAccessEndAt']) {
    // Unchanged legacy values (including sub-second precision) survive a name/rule edit exactly.
    body[field] = detail && form[field] === localCampaignTime(detail[field]) ? (detail[field] || null) : (form[field] ? new Date(form[field]).toISOString() : null)
  }
  if (!preservePolicy) body.applicationMaterialPolicy = { ...JSON.parse(JSON.stringify(form.applicationMaterialPolicy)), minStatementLength: Number(form.applicationMaterialPolicy.minStatementLength) }
  if (detail) body.expectedVersion = detail.version
  return body
}
