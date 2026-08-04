/**
 * 运行环境开关。P3：真实后端优先（失败自动回退 mock，不白屏）。
 * useMock=true 可整体回到纯 mock 演示模式。
 *
 * apiBaseUrl 取值优先级：
 *   1) 构建期环境变量 VITE_API_BASE_URL（H5/服务器/真机联调用，只填源，勿带 /api）
 *   2) 默认 http://localhost:8000（本地开发）
 * 说明：小程序（mp-weixin）无同源概念，必须是可达的绝对地址；服务器演示请设
 *       VITE_API_BASE_URL=https://你的域名（微信小程序正式环境强制 HTTPS；H5 经 Nginx /api/ 反代亦可）。
 *       生产构建若误填 http:// 非本机地址，将自动升级为 https://（后端须挂 TLS 证书）。
 */
function resolveApiBaseUrl() {
  try {
    const env = (import.meta && import.meta.env) || {}
    const v = env.VITE_API_BASE_URL
    if (v) {
      let url = String(v).replace(/\/+$/, '')
      // 兼容误配：VITE 只填源，勿带 /api；若运维误填 .../api/v1 则剥离避免双前缀
      url = url.replace(/\/api\/v1$/i, '')
      // 生产构建强制 HTTPS：微信小程序正式环境禁止 http 明文请求，且明文会暴露 Bearer 令牌与
      // 全部 PII。非本机地址若误配为 http:// 一律升级为 https://（后端须挂 TLS/反代）。
      if (env.PROD && /^http:\/\//i.test(url) && !/^http:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(url)) {
        url = url.replace(/^http:\/\//i, 'https://')
      }
      return url
    }
  } catch (e) { /* 某些编译目标无 import.meta，忽略 */ }
  return 'http://localhost:8000'
}

/**
 * useMock 开关取值优先级（不改变既有默认，保证无后端时仍可独立演示）：
 *   1) 构建期环境变量 VITE_USE_MOCK：'false'/'0' → 真实后端优先；'true'/'1' → 纯 mock
 *   2) 缺省 → true（纯 mock 演示）
 * 真实数据/MySQL 联调：在 miniapp/.env 设 VITE_USE_MOCK=false 且 VITE_API_BASE_URL=后端源地址，
 * 并确保后端(uvicorn)已启动+种子数据就绪，否则各页会等超时(requestTimeout)后回退 mock 骨架。
 */
function resolveUseMock() {
  try {
    const env = import.meta && import.meta.env
    // 生产构建的数据真实性是硬约束：即使运维误配 VITE_USE_MOCK=true，也不得展示演示数据。
    if (env && env.PROD) return false
    const v = env && env.VITE_USE_MOCK
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      const s = String(v).trim().toLowerCase()
      return !(s === 'false' || s === '0' || s === 'no' || s === 'off')
    }
  } catch (e) { /* 某些编译目标无 import.meta，忽略 */ }
  return true
}

/** 用户协议 / 隐私政策页面地址。仓库当前不存在这两份文档的公开路由，默认留空 →
 * 登录页对应文字不可点（不放虚假链接冒充已核定的协议正文）。学校确定正式文档后，
 * 通过 VITE_PRIVACY_URL / VITE_TERMS_URL 注入真实地址，与 frontend/portalConfig.js 同一约定。 */
function resolveDocUrl(key) {
  try {
    const env = (import.meta && import.meta.env) || {}
    const v = env[key]
    return v ? String(v).trim() : ''
  } catch (e) { return '' }
}

export const ENV = {
  // true=纯 mock 演示（无需后端，秒开，用于独立演示）；false=优先真实后端，失败回退 mock。
  // 可被构建期环境变量 VITE_USE_MOCK 覆盖（见 resolveUseMock）；默认保持纯 mock 演示。
  useMock: resolveUseMock(),
  privacyUrl: resolveDocUrl('VITE_PRIVACY_URL'),
  termsUrl: resolveDocUrl('VITE_TERMS_URL'),
  // Mock 回退仅是本地开发便利能力，不是离线产品能力。生产构建硬禁用。
  allowMockFallback: (() => {
    try {
      const env = import.meta && import.meta.env
      if (env && env.PROD) return false
      return !!(env && env.DEV)
    } catch (e) { return false }
  })(),
  // 演示账号仅允许显式的开发构建；生产包不展示、不填充、也不自动登录。
  apiBaseUrl: resolveApiBaseUrl(), // 后端地址（可被 VITE_API_BASE_URL 覆盖）
  apiPrefix: '/api/v1',
  requestTimeout: 8000, // 校园弱网下 4s 偏紧；8s 内无响应按网络失败处理（读兜底/写明确报错）
  mockLatency: 260
}

export default ENV
