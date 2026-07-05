/**
 * 运行环境开关。P3：真实后端优先（失败自动回退 mock，不白屏）。
 * useMock=true 可整体回到纯 mock 演示模式。
 *
 * apiBaseUrl 取值优先级：
 *   1) 构建期环境变量 VITE_API_BASE_URL（H5/服务器/真机联调用，只填源，勿带 /api）
 *   2) 默认 http://localhost:8000（本地开发）
 * 说明：小程序（mp-weixin）无同源概念，必须是可达的绝对地址；服务器演示请设
 *       VITE_API_BASE_URL=http://服务器IP（H5 经 Nginx /api/ 反代亦可）。
 */
function resolveApiBaseUrl() {
  try {
    const v = import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL
    if (v) return String(v).replace(/\/+$/, '')
  } catch (e) { /* 某些编译目标无 import.meta，忽略 */ }
  return 'http://localhost:8000'
}

export const ENV = {
  useMock: false, // false=优先真实后端，失败回退 mock；true=纯 mock
  apiBaseUrl: resolveApiBaseUrl(), // 后端地址（可被 VITE_API_BASE_URL 覆盖）
  apiPrefix: '/api/v1',
  requestTimeout: 8000, // 校园弱网下 4s 偏紧；8s 内无响应按网络失败处理（读兜底/写明确报错）
  mockLatency: 260
}

export default ENV
