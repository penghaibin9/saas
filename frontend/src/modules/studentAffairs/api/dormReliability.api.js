import { request } from '@/services/http/client'

export const dormReliabilityApi = {
  async checkout(bedId, version) {
    if (version === undefined || version === null || version === '') {
      throw new Error('床位缺少version，请刷新后再办理退宿')
    }
    return request(`/student-affairs/dorm/beds/${bedId}/checkout`, {
      method: 'POST',
      body: { version }
    })
  }
}

export default dormReliabilityApi
