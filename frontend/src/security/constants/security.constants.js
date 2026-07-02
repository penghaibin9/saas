/**
 * 00-SEC 前端安全基线 — 集中常量
 * 依据：docs/security/00-等保三级安全基线总册.md（§3 数据分级 / §4 会话 / §9 上传下载导出）
 * 声明：本目录为前端 mock/预留实现，不代表系统已通过等保三级。
 */

/** 会话策略（总册 §4：PC 30 分钟无操作超时；移动端 7 天；并发 3；首登强制改密） */
export const SESSION_POLICY = Object.freeze({
  PC_TIMEOUT_MS: 30 * 60 * 1000,
  MOBILE_TIMEOUT_MS: 7 * 24 * 60 * 60 * 1000,
  MAX_CONCURRENT_SESSIONS: 3,
  WARNING_BEFORE_MS: 5 * 60 * 1000
})

/** 安全相关 HTTP 状态语义 */
export const SECURITY_HTTP_STATUS = Object.freeze({
  UNAUTHORIZED: 401, // 未登录 / 会话失效
  FORBIDDEN: 403, // 无权限
  SESSION_EXPIRED: 419, // 会话超时 / CSRF 失效（自定义语义）
  SERVER_ERROR: 500
})

/** 安全错误页路由 */
export const SECURITY_ERROR_ROUTES = Object.freeze({
  401: '/security/401',
  403: '/security/403',
  419: '/security/419',
  500: '/security/500'
})

/** 敏感数据分级（总册 §3：学生个人信息分级清单） */
export const SENSITIVE_LEVEL = Object.freeze({
  PUBLIC: 'PUBLIC', // 可公开
  INTERNAL: 'INTERNAL', // 校内可见
  SENSITIVE: 'SENSITIVE', // 默认脱敏展示
  SECRET: 'SECRET' // 禁止前端明文出现（如密码/完整身份证）
})

/** 上传策略（总册 §9） */
export const UPLOAD_POLICY = Object.freeze({
  ALLOWED_EXTENSIONS: ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'zip', 'rar', 'xlsx', 'pptx'],
  MAX_FILE_SIZE_BYTES: 50 * 1024 * 1024, // 50MB
  /** 高风险扩展名黑名单（双保险，白名单之外一律拒绝） */
  BLOCKED_EXTENSIONS: ['exe', 'js', 'bat', 'sh', 'php', 'jsp', 'html', 'svg']
})

/** 导出限制（总册 §9：三档导出 + 审计） */
export const EXPORT_POLICY = Object.freeze({
  MAX_ROWS_DEFAULT: 5000,
  TYPES: Object.freeze({
    LIST: 'LIST', // 台账导出
    ENCRYPTED_ARCHIVE: 'ENCRYPTED_ARCHIVE', // 加密档案
    DESENSITIZED: 'DESENSITIZED' // 脱敏外发
  }),
  /** 各导出类型所需权限点（复用 workflow 权限体系命名规范 module.resource.action） */
  REQUIRED_PERMISSION: Object.freeze({
    LIST: 'security.export.list',
    ENCRYPTED_ARCHIVE: 'security.export.archive',
    DESENSITIZED: 'security.export.desensitized'
  })
})

/** 审计事件类型（总册 §8 必审计行为） */
export const AUDIT_EVENT_TYPE = Object.freeze({
  LOGIN: 'LOGIN',
  LOGOUT: 'LOGOUT',
  PERMISSION_DENIED: 'PERMISSION_DENIED',
  PERMISSION_CHANGE: 'PERMISSION_CHANGE',
  EXPORT: 'EXPORT',
  DOWNLOAD: 'DOWNLOAD',
  UPLOAD: 'UPLOAD',
  APPROVAL: 'APPROVAL',
  SENSITIVE_VIEW: 'SENSITIVE_VIEW',
  SESSION_EXPIRED: 'SESSION_EXPIRED'
})

/** detail 中禁止明文出现的字段名（sanitize 强制处理） */
export const AUDIT_FORBIDDEN_KEYS = Object.freeze([
  'password',
  'token',
  'accessToken',
  'refreshToken',
  'idCard',
  'idcard',
  'phone',
  'mobile',
  'bankCard',
  'salary'
])

/** CSRF 需要保护的方法 */
export const CSRF_PROTECTED_METHODS = Object.freeze(['POST', 'PUT', 'PATCH', 'DELETE'])
export const CSRF_HEADER_NAME = 'X-CSRF-Token'
export const REQUEST_ID_HEADER = 'X-Request-Id'
