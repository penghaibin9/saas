import { request } from './request'

export const graduationExtensionApi = {
  my: () => request('/portal/graduation/extensions/my'),
  applyDelay: (reason, evidence = []) => request('/portal/graduation/defense-delay/apply', {
    method: 'POST', body: { reason, evidence }
  })
}

export default graduationExtensionApi
