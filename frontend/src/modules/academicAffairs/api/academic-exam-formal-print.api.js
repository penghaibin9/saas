import { request } from '@/services/http/client'

const BASE = '/academic-affairs/exam'

/**
 * C-W3 正式打印客户端。
 *
 * 普通 roomSeats 属于排考编排工作区，可能读取未发布草稿；正式座位表/门贴/准考证
 * 只能消费后端 formal-print provider。预览保持只读；真正调用浏览器打印前必须先走
 * issueFormalPrint() 写 EXAM_TICKET_PRINT 审计，禁止“看起来能打印但没有签发证据”的第二条路径。
 */
export const academicAffairsExamPrintApi = {
  formalRoomPrint(roomId) {
    const id = String(roomId || '').trim()
    if (!id) return Promise.reject(new Error('考场 ID 必填'))
    return request(`${BASE}/rooms/${encodeURIComponent(id)}/formal-print`)
  },
  issueFormalPrint(roomId, body = {}) {
    const id = String(roomId || '').trim()
    if (!id) return Promise.reject(new Error('考场 ID 必填'))
    return request(`${BASE}/rooms/${encodeURIComponent(id)}/formal-print/issue`, {
      method: 'POST',
      body: {
        documentKind: body.documentKind,
        studentNo: body.studentNo || undefined,
        reason: body.reason || undefined
      }
    })
  }
}