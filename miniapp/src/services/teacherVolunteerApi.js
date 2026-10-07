import { realRequest } from './request'

const root = '/mobile/teacher/internship/context'
const enc = value => encodeURIComponent(String(value ?? ''))
function path(suffix, scope) {
  for (const key of ['batchId', 'campaignId']) {
    if (!/^[1-9]\d*$/.test(String(scope[key] || ''))) throw new Error('请先选择有效的批次和招聘季')
  }
  return `${root}${suffix}?batchId=${enc(scope.batchId)}&campaignId=${enc(scope.campaignId)}`
}
export const teacherVolunteerApi = {
  campaigns: batchId => realRequest(`${root}/volunteer-campaigns?batchId=${enc(batchId)}`),
  list: scope => realRequest(path('/volunteer-groups', scope)+`&status=${enc(scope.status)}&keyword=${enc(scope.keyword)}&page=${enc(scope.page)}&pageSize=20`),
  detail: scope => realRequest(path(`/volunteer-groups/${enc(scope.groupId)}`, scope)),
  confirm: (scope, data) => realRequest(path(`/volunteer-groups/${enc(scope.groupId)}/confirm`, scope), { method: 'POST', data }),
  return: (scope, data) => realRequest(path(`/volunteer-groups/${enc(scope.groupId)}/return`, scope), { method: 'POST', data })
}
