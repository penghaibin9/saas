/**
 * 学生端移动高频接口适配（PR #24 + #26 能力，V3 从全局 bootstrap 拆出）。
 *
 * V3 S1.5 Bootstrap De-hoist：以前这些补丁写在 main.js 静态导入的
 * mobilePerformanceInstaller 里，教师用户冷启动也会连带装配学生 API 与学生 mock 图。
 * 现在改成学生分包页面首次进入时显式安装。
 *
 * 页面继续调用原 studentApi.*，实际只走统一高频接口。
 */
import { studentApi } from './studentApi'
import { mockRequest, realFirstStrict, realRequest } from './request'
import * as M from '@/mock'

const enc = (value) => encodeURIComponent(String(value ?? ''))

// 后端 read_messages_batch() 单批硬上限 100 条（超过整批 VALIDATION_ERROR，不做部分处理）。
// 此前前端把同一事件循环内排队的全部 id 一次性发送，学生未读通知超过 100 条时点"全部已读"，
// 整批请求会被拒绝——但页面早已乐观把这些消息标成已读，直到下次刷新才会变回未读，制造
// "已读点了却没生效"的假象（2026-08-04 复审新增发现，即 V2 报告 P1-05 提到的 100 条边界）。
// 改为按同样上限切片，分批发送，避免因超限导致整批白标。
const READ_BATCH_LIMIT = 100

let queuedIds = new Set()
let queuedWaiters = []
let flushScheduled = false

function flushReadBatch() {
  flushScheduled = false
  const messageIds = [...queuedIds]
  const waiters = queuedWaiters
  queuedIds = new Set()
  queuedWaiters = []
  if (!messageIds.length) {
    waiters.forEach(({ resolve }) => resolve({ affectedCount: 0 }))
    return
  }
  const chunks = []
  for (let i = 0; i < messageIds.length; i += READ_BATCH_LIMIT) {
    chunks.push(messageIds.slice(i, i + READ_BATCH_LIMIT))
  }
  Promise.all(chunks.map((chunk) =>
    realRequest('/mobile/performance/student/messages/read-batch', {
      method: 'POST', data: { messageIds: chunk }
    }).then((result) => ({ ok: true, result }), (error) => ({ ok: false, error }))
  )).then((outcomes) => {
    const failed = outcomes.find((o) => !o.ok)
    if (failed) {
      // 保守处理：任一分片失败就让全部等待方失败重试；已成功的分片在后端是幂等 UPDATE
      // （status != READ 过滤），重试不会重复计数或报错，只是多一次网络请求。
      waiters.forEach(({ reject }) => reject(failed.error))
      return
    }
    const affectedCount = outcomes.reduce((sum, o) => sum + (o.result.affectedCount || 0), 0)
    waiters.forEach(({ resolve }) => resolve({ affectedCount }))
  })
}

let installed = false

/** 幂等：学生分包页面可以放心重复调用。 */
export function ensureStudentPerformanceApi() {
  if (installed) return studentApi
  installed = true

  studentApi.getMessagesPage = (tab = 'todo', page = 1, pageSize = 20) =>
    realFirstStrict(
      'student.messages.performance',
      () => realRequest(
        `/mobile/performance/student/messages-page?tab=${enc(tab)}&page=${page}&pageSize=${pageSize}`
      ),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })
    )

  /**
   * 同一个事件循环里的逐条“已读”调用合并去重后按 READ_BATCH_LIMIT 切片发送。
   * 未读 ≤100 条时列表“全部已读”仍只产生一次HTTP写请求；超过 100 条会分多次请求，
   * 但不会再出现整批被后端拒绝、UI 却已乐观标成已读的情况。打开单条消息仍只更新该条。
   */
  studentApi.markMessageRead = (messageId) => {
    const raw = String(messageId || '').replace('msg-', '').trim()
    if (!/^\d+$/.test(raw)) return Promise.resolve({ affectedCount: 0 })
    queuedIds.add(raw)
    const pending = new Promise((resolve, reject) => {
      queuedWaiters.push({ resolve, reject })
    })
    if (!flushScheduled) {
      flushScheduled = true
      Promise.resolve().then(flushReadBatch)
    }
    return pending
  }

  return studentApi
}

export default ensureStudentPerformanceApi
