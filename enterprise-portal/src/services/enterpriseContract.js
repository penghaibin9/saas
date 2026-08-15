const COMPANY_EDITABLE = new Set([
  'logoFileId','coverFileId','shortName','shortIntro','website','mainBusiness','establishedYear','address',
])

const POSITION_EDITABLE = new Set([
  'title','category','majorRequirement','gradeRequirement','workLocation','headcount','mentorContactId',
  'workContent','workAddress','dailyHours','weeklyHours','shiftType','nightShift','overtimeAllowed','restDaysPerWeek',
  'remunerationType','remunerationAmount','remunerationCycle','salaryRange','subsidy','accommodationProvided','mealProvided',
  'hazardousFlag','specialEquipment','prohibitedReason','remark',
])

function pickEditable(source, allowed) {
  const result = {}
  for (const [key,value] of Object.entries(source || {})) {
    if (allowed.has(key) && value !== undefined) result[key] = value
  }
  return result
}

export function sanitizeCompanyPatch(source) {
  return pickEditable(source, COMPANY_EDITABLE)
}

export function sanitizePositionPayload(source) {
  return pickEditable(source, POSITION_EDITABLE)
}
