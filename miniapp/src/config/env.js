/**
 * 运行环境开关。P3：真实后端优先（失败自动回退 mock，不白屏）。
 * useMock=true 可整体回到纯 mock 本地开发模式。
 *
 * apiBaseUrl 只接受构建期环境变量 VITE_API_BASE_URL（只填源，勿带 /api）。
 * 生产构建没有显式 API 地址时直接失败，禁止把 localhost 开发地址编进正式包。
 * 本地真实后端联调请在 miniapp/.env 显式设置 VITE_API_BASE_URL。
 * 微信小程序无同源概念，正式环境必须使用可达的 HTTPS 绝对地址。
 */
function resolveApiBaseUrl() {
  let env = {}
  try {
    env = (import.meta && import.meta.env) || {}
  } catch (e) { /* 某些非 Vite 测试环境没有 import.meta.env */ }

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

  if (env.PROD) {
    throw new Error('VITE_API_BASE_URL is required for production miniapp builds')
  }
  // 纯 mock 本地开发不需要 API；真实后端联调必须通过 .env 显式声明地址。
  return ''
}

/**
 * useMock 开关取值优先级（不改变既有默认，保证无后端时仍可独立开发）：
 *   1) 构建期环境变量 VITE_USE_MOCK：'false'/'0' → 真实后端优先；'true'/'1' → 纯 mock
 *   2) 缺省 → true（纯 mock 本地开发）
 * 真实数据/MySQL 联调：在 miniapp/.env 设 VITE_USE_MOCK=false 且 VITE_API_BASE_URL=后端源地址，
 * 并确保后端(uvicorn)已启动+种子数据就绪，否则各页会等超时(requestTimeout)后回退 mock 骨架。
 */
function resolveUseMock() {
  try {
    const env = import.meta && import.meta.env
    // 生产构建的数据真实性是硬约束：即使运维误配 VITE_USE_MOCK=true，也不得展示 mock 数据。
    if (env && env.PROD) return false
    const v = env && env.VITE_USE_MOCK
    if (v !== undefined && v !== null && String(v).trim() !== '') {
      const s = String(v).trim().toLowerCase()
      return !(s === 'false' || s === '0' || s === 'no' || s === 'off')
    }
  } catch (e) { /* 某些编译目标无 import.meta，忽略 */ }
  return true
}

/**
 * 用户协议 / 隐私政策 / 统一帮助中心页面地址。
 * 协议正文仓库当前不存在公开路由，默认留空；帮助中心不硬编码 SaaS 域名，
 * 由 VITE_HELP_CENTER_URL 注入。生产环境的非本机 http 地址自动升级为 https。
 */
function resolveDocUrl(key) {
  try {
    const env = (import.meta && import.meta.env) || {}
    const v = env[key]
    if (!v) return ''
    let url = String(v).trim()
    if (env.PROD && /^http:\/\//i.test(url) && !/^http:\/\/(localhost|127\.0\.0\.1)(:|\/|$)/i.test(url)) {
      url = url.replace(/^http:\/\//i, 'https://')
    }
    return url
  } catch (e) { return '' }
}

export const ENV = {
  // true=纯 mock 本地开发；false=优先真实后端。生产构建始终强制 false。
  useMock: resolveUseMock(),
  privacyUrl: resolveDocUrl('VITE_PRIVACY_URL'),
  termsUrl: resolveDocUrl('VITE_TERMS_URL'),
  // 小程序“帮助与反馈”唯一正文入口。正式环境配置 HTTPS /help 地址并登记微信业务域名。
  helpCenterUrl: resolveDocUrl('VITE_HELP_CENTER_URL'),
  // Mock 回退仅是本地开发便利能力，不是离线产品能力。生产构建硬禁用。
  allowMockFallback: (() => {
    try {
      const env = import.meta && import.meta.env
      if (env && env.PROD) return false
      return !!(env && env.DEV)
    } catch (e) { return false }
  })(),
  apiBaseUrl: resolveApiBaseUrl(),
  apiPrefix: '/api/v1',
  requestTimeout: 8000, // 校园弱网下 4s 偏紧；8s 内无响应按网络失败处理（读兜底/写明确报错）
  mockLatency: 260
}

export default ENV
