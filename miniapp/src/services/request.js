/**
 * 统一请求封装（mock 版）
 * ------------------------------------------------------------
 * V1 恒为 mock：不接真实后端、不连数据库。
 * mockRequest() 用 Promise + 延时模拟网络，页面据此演示 loading / error / empty。
 * 预留 request()：以后接后端时改这里即可，页面无需改动。
 */
import { ENV } from '@/config/env'

/** 模拟一次数据请求。fail=true 时用于演示 error 态。 */
export function mockRequest(payload, { latency = ENV.mockLatency, fail = false } = {}) {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) {
        reject({ code: 'MOCK_ERROR', message: '数据加载失败（模拟）' })
      } else {
        // 深拷贝，避免页面改动污染 mock 源
        resolve(JSON.parse(JSON.stringify(payload)))
      }
    }, latency)
  })
}

/** 预留：真实后端请求（V1 未启用） */
export function request(options) {
  if (ENV.useMock) {
    return Promise.reject({ code: 'MOCK_ONLY', message: '当前为 mock 模式' })
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: ENV.apiBaseUrl + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      success: (res) => resolve(res.data),
      fail: reject
    })
  })
}

export default { mockRequest, request }
