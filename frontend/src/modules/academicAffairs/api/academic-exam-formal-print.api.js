import { request } from '@/services/http/client'

const BASE = '/academic-affairs/exam'

/**
 * C-W3 正式打印只读客户端。
 *
 * 普通 roomSeats 属于排考编排工作区，可能读取未发布草稿；正式座位表/门贴/准考证
 * 只能消费后端 formal-print provider。这里故意不提供任何 fallback，业务门禁失败直接
 * 交给页面展示，禁止把草稿座位数据降级成“正式打印”。
 */
export const academicAffairsExamPrintApi = {
  formalRoomPrint(roomId) {
    const id = String(roomId || '').trim()
    if (!id) return Promise.reject(new Error('考场 ID 必填'))
    return request(`${BASE}/rooms/${encodeURIComponent(id)}/formal-print`)
  }
}
