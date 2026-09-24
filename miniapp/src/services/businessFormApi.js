import { realRequest } from './request'

export const businessFormApi = {
  load: (body) => realRequest('/business-forms/runtime/load', { method: 'POST', body }),
  submit: (body) => realRequest('/business-forms/runtime/submit', { method: 'POST', body })
}

export default businessFormApi
