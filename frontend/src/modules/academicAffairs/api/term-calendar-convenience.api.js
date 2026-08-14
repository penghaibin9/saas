/**
 * D1-U 学期/校历/作息便利性辅助 API。
 *
 * 这里只暴露 preview/read-side；正式确认继续调用 academicAffairsApi 原有
 * addCalendarEvent/createTimeSlot 写入口，确保 server final recheck 与 canonical 事实链不变。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(error) {
  if (error?.biz) return fail(error.message, error.code || 1)
  return fail(error?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return toErr(error) }
}

const BASE = '/academic-affairs'

export const termCalendarConvenienceApi = {
  previewCalendarCopy(targetTermId, sourceTermId) {
    return call(() => request(`${BASE}/terms/${targetTermId}/calendar/copy-preview`, {
      method: 'POST',
      body: { sourceTermId }
    }))
  },
  previewTimeSlotTemplate(templateKey) {
    return call(() => request(`${BASE}/time-slots/template-preview`, {
      method: 'POST',
      body: { templateKey }
    }))
  }
}

export default termCalendarConvenienceApi
