import { request } from '@/services/http/client'
import { validateAcademicFlow } from '../config/academicFlowRegistry.js'

export const academicFlowApi = {
  async get({ termId, collegeId } = {}) {
    for (const value of [termId, collegeId]) {
      if (value != null && value !== '' && (typeof value !== 'string' || !/^[1-9]\d*$/.test(value))) {
        throw new Error('学期或学院参数无效，请从责任工作台重新进入')
      }
    }
    const data = await request('/academic-affairs/flow', { params: { termId, collegeId } })
    return validateAcademicFlow(data, { termId })
  }
}
