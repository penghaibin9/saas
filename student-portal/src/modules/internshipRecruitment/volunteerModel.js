import { buildVolunteerDraftPayload } from './selectionContract.js'
import { normalizePosition } from './positionModel.js'

export const VOLUNTEER_EDITABLE_STATES = Object.freeze(['DRAFT', 'NEEDS_REVISION'])

function emptySlot(volunteerNo) {
  return { volunteerNo, positionId: null, position: null, applicationStatement: '', applicationVersion: 0 }
}

function cloneSlots(slots = []) {
  return [1, 2, 3].map((volunteerNo) => {
    const source = slots.find((slot) => Number(slot.volunteerNo) === volunteerNo) || emptySlot(volunteerNo)
    return { ...source, volunteerNo, position: source.position ? { ...source.position } : null }
  })
}

export function normalizeVolunteerGroup(raw = {}) {
  const sourceItems = Array.isArray(raw.items) ? raw.items : Array.isArray(raw.volunteers) ? raw.volunteers : []
  const byNo = new Map(sourceItems.map((item) => [Number(item.volunteerNo), item]))
  const slots = [1, 2, 3].map((volunteerNo) => {
    const item = byNo.get(volunteerNo)
    if (!item) return emptySlot(volunteerNo)
    const positionRaw = item.position || item.positionSummary || {
      id: item.positionId,
      title: item.positionName,
      companyName: item.companyName,
      workLocation: item.workLocation,
      remunerationDisplay: item.remuneration
    }
    return {
      volunteerNo,
      positionId: item.positionId ?? positionRaw.id ?? null,
      position: item.positionId || positionRaw.id ? normalizePosition(positionRaw) : null,
      applicationStatement: String(item.applicationStatement || item.statement || ''),
      applicationVersion: Number(item.version || item.applicationVersion || 0)
    }
  })
  const status = String(raw.status || raw.groupStatus || 'UNAVAILABLE').toUpperCase()
  return {
    id: raw.id || raw.groupId || null,
    status,
    version: Number(raw.version || raw.groupVersion || 0),
    recordVersion: Number(raw.recordVersion || raw.internshipRecordVersion || 0),
    batchId: raw.batchId || null,
    internshipId: raw.internshipId || raw.recordId || null,
    selectedCount: slots.filter((slot) => slot.positionId).length,
    teacherConfirmDeadline: raw.teacherConfirmDeadline || '',
    lockedCompanyName: raw.lockedCompanyName || '',
    slots
  }
}

export function canEditVolunteerGroup(group) {
  return VOLUNTEER_EDITABLE_STATES.includes(String(group?.status || '').toUpperCase())
}

export function addVolunteer(slots, position) {
  const next = cloneSlots(slots)
  if (!position?.id) throw new Error('岗位信息无效')
  if (next.some((slot) => String(slot.positionId) === String(position.id))) return next
  const empty = next.find((slot) => !slot.positionId)
  if (!empty) throw new Error('三志愿已满，请选择要替换的志愿')
  empty.positionId = position.id
  empty.position = normalizePosition(position)
  empty.applicationStatement = ''
  return next
}

export function replaceVolunteer(slots, volunteerNo, position) {
  const next = cloneSlots(slots)
  const index = Number(volunteerNo) - 1
  if (index < 0 || index > 2 || !position?.id) throw new Error('替换志愿参数无效')
  const duplicatedAt = next.findIndex((slot) => String(slot.positionId) === String(position.id))
  if (duplicatedAt >= 0 && duplicatedAt !== index) throw new Error('同一岗位不能重复加入志愿')
  next[index] = { ...next[index], volunteerNo: index + 1, positionId: position.id, position: normalizePosition(position), applicationStatement: '' }
  return next
}

export function removeVolunteer(slots, volunteerNo) {
  const active = cloneSlots(slots)
    .filter((slot) => slot.positionId && slot.volunteerNo !== Number(volunteerNo))
    .map((slot, index) => ({ ...slot, volunteerNo: index + 1 }))
  while (active.length < 3) active.push(emptySlot(active.length + 1))
  return active
}

export function moveVolunteer(slots, volunteerNo, direction) {
  const next = cloneSlots(slots)
  const from = Number(volunteerNo) - 1
  const to = direction === 'UP' ? from - 1 : from + 1
  if (from < 0 || from > 2 || to < 0 || to > 2 || !next[from]?.positionId || !next[to]?.positionId) return next
  const fromValue = { ...next[from] }
  const toValue = { ...next[to] }
  next[from] = { ...toValue, volunteerNo: from + 1 }
  next[to] = { ...fromValue, volunteerNo: to + 1 }
  return next
}

export function updateVolunteerStatement(slots, volunteerNo, statement) {
  const next = cloneSlots(slots)
  const index = Number(volunteerNo) - 1
  if (index < 0 || index > 2) return next
  next[index].applicationStatement = String(statement || '')
  return next
}

export function buildVolunteerGroupSaveRequest(group, slots) {
  return buildVolunteerDraftPayload({
    batchId: group.batchId,
    internshipId: group.internshipId,
    items: cloneSlots(slots).filter((slot) => slot.positionId).map((slot) => ({
      volunteerNo: slot.volunteerNo,
      positionId: slot.positionId,
      applicationStatement: slot.applicationStatement
    })),
    expectedRecordVersion: group.recordVersion,
    expectedApplicationVersions: Object.fromEntries(cloneSlots(slots).map((slot) => [String(slot.volunteerNo), Number(slot.applicationVersion || 0)]))
  })
}
