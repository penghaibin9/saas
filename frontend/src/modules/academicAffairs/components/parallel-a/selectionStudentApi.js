import { request } from '@/services/http/client'

function errorResult(error) {
  if (error?.biz) {
    return {
      code: error.code || 1,
      status: error.status,
      data: null,
      message: error.message,
      bizCode: error.bizCode,
      details: error.details
    }
  }
  return { code: 503001, status: error?.status, data: null, message: error?.message || '网络连接失败' }
}

/** 学生选课写入前必须走正式 DecisionTrace 预检。 */
export async function preflightStudentSelection(selectionCourseId, isReselect = false, action = 'ENROLL') {
  try {
    const endpoint = action === 'DROP' ? 'drop-preflight' : 'preflight'
    const data = await request(`/academic-affairs/selection/student/${endpoint}`, {
      method: 'POST',
      body: { selectionCourseId, isReselect }
    })
    return { code: 0, data, message: 'ok' }
  } catch (error) {
    return errorResult(error)
  }
}
