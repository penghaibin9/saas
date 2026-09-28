import { resolveSecurityDataScope } from './menu.guard'

export function checkRecordScope(record = {}) {
  if (record && record.inScope === false) {
    return { allowed: false, reason: '记录超出当前授权范围' }
  }
  return { allowed: true, reason: '' }
}

export function filterRecordsByScope(records = []) {
  return records.filter((record) => checkRecordScope(record).allowed)
}

export function getScopeDescription() {
  return resolveSecurityDataScope()
}
