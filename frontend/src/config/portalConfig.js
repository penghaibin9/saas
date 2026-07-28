/**
 * 统一门户（公开首页 /）集中配置。
 * ────────────────────────────────────────────────────────────
 * 本文件是门户所有可部署配置的唯一来源，禁止把入口地址/二维码散落到组件里。
 *
 * 取值优先级：构建期环境变量（VITE_PORTAL_*）→ 本文件内置默认值。
 * 默认值只使用**同源相对路径**，因此生产构建产物中不会出现 localhost / 内网 IP：
 *   - 教师端与门户同属 frontend 应用，登录页固定为 /login
 *   - 学生端为独立 student-portal 应用，默认部署在 /portal/（见 deploy/nginx/nginx.portal.conf.example
 *     与 student-portal/vite.config.js 的 VITE_BASE 默认值），登录页即 /portal/login
 * 若学校把学生端部署到独立子域名，只需构建时提供 VITE_PORTAL_STUDENT_LOGIN_URL 覆盖。
 *
 * 安全：所有对外地址在使用前都会经 sanitizeEntryUrl() 校验，只放行同源相对路径与
 * http(s) 绝对地址，杜绝 javascript:/data: 等协议注入与开放重定向。
 */

const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}

function readEnv(key) {
  const raw = env[key]
  return typeof raw === 'string' && raw.trim() ? raw.trim() : ''
}

/**
 * 入口地址安全校验。
 * 放行：以单个 / 开头的同源相对路径；http:// 或 https:// 绝对地址。
 * 拒绝：空值、javascript:/data:/vbscript: 等危险协议、// 开头的协议相对地址（防跳到外站）。
 * 返回空字符串表示「未配置」，调用方据此把入口降级为禁用态。
 */
export function sanitizeEntryUrl(value) {
  const url = typeof value === 'string' ? value.trim() : ''
  if (!url) return ''
  if (url.startsWith('//')) return ''
  if (url.startsWith('/')) return url
  if (/^https?:\/\/[^\s]+$/i.test(url)) return url
  return ''
}

/** 教师 / 管理人员登录页：与门户同属 frontend 应用，真实路由见 router/index.js 的 /login */
export const TEACHER_LOGIN_URL = sanitizeEntryUrl(
  readEnv('VITE_PORTAL_TEACHER_LOGIN_URL') || '/login'
)

/** 学生登录页：student-portal 应用，默认子路径部署 /portal/ + 其路由 /login */
export const STUDENT_LOGIN_URL = sanitizeEntryUrl(
  readEnv('VITE_PORTAL_STUDENT_LOGIN_URL') || '/portal/login'
)

/** 教师端微信小程序码地址；未配置时门户显示「即将接入」占位，绝不展示伪造二维码 */
export const TEACHER_MINIPROGRAM_QR = sanitizeEntryUrl(readEnv('VITE_PORTAL_TEACHER_MP_QR'))

/** 学生端微信小程序码地址；同上 */
export const STUDENT_MINIPROGRAM_QR = sanitizeEntryUrl(readEnv('VITE_PORTAL_STUDENT_MP_QR'))

/**
 * 系统运行状态页。仓库当前不存在真实状态页，默认留空 →
 * 门户不渲染状态入口（不允许展示假的「系统运行正常」）。
 */
export const STATUS_PAGE_URL = sanitizeEntryUrl(readEnv('VITE_PORTAL_STATUS_URL'))

/**
 * 隐私政策 / 用户协议 / 技术支持页。仓库当前均不存在对应公开路由，
 * 默认留空 → 页脚不渲染这些链接（不放虚假链接）。
 */
export const PRIVACY_URL = sanitizeEntryUrl(readEnv('VITE_PORTAL_PRIVACY_URL'))
export const TERMS_URL = sanitizeEntryUrl(readEnv('VITE_PORTAL_TERMS_URL'))
export const SUPPORT_URL = sanitizeEntryUrl(readEnv('VITE_PORTAL_SUPPORT_URL'))

/** 客服联系方式：复用登录页既有的 VITE_SUPPORT_CONTACT，不新增重复配置 */
export const SUPPORT_CONTACT = readEnv('VITE_SUPPORT_CONTACT')

/** 默认品牌（租户品牌接口不可用时的降级值） */
export const DEFAULT_PLATFORM_NAME = '高校学生全生命周期管理平台'
export const DEFAULT_PLATFORM_SUBTITLE = '教务实践综合管理平台'

/** 主体与备案信息（ICP 为主体资质，随主体固定，不做环境变量） */
export const COMPANY_NAME = '湖南跃科信息工程有限公司'
export const ICP_NUMBER = '湘ICP备2026031107号'
export const ICP_QUERY_URL = 'https://beian.miit.gov.cn/'

/**
 * 四大业务系统。
 * relationshipMap 指向 frontend/public/help/ 下**仓库真实存在**的业务关系图静态页
 * （与 src/config/help/*.js 中 embed 字段同一份资源），门户以新窗口打开，不使用 iframe。
 * flowId 对应 src/config/helpContent.js 中 HELP_FLOWS 的真实流程，用于弹窗展示流程步骤。
 */
export const PORTAL_MODULES = [
  {
    key: 'graduation',
    mark: '毕',
    name: '毕业设计',
    desc: '选题、开题、指导、成果提交、答辩与成绩归档',
    stages: ['选题', '开题', '指导', '答辩'],
    color: '#2563eb',
    soft: '#eaf2ff',
    flowId: 'flow-graduation',
    relationshipMap: '/help/graduation-module-relationship-map.html'
  },
  {
    key: 'internship',
    mark: '实',
    name: '岗位实习',
    desc: '实习申请、企业对接、过程监管、风险处置与实习考核',
    stages: ['申请', '协议', '监管', '考核'],
    color: '#059669',
    soft: '#e7f8f2',
    flowId: 'flow-internship',
    relationshipMap: '/help/internship-module-relationship-map.html'
  },
  {
    key: 'affairs',
    mark: '学',
    name: '学工中心',
    desc: '学生事务、奖助资助、日常管理、风险关怀与辅导员工作',
    stages: ['事务', '奖助', '关怀', '档案'],
    color: '#d97706',
    soft: '#fff3df',
    flowId: 'flow-sa-risk',
    relationshipMap: '/help/student-affairs-relationship-overview.html'
  },
  {
    key: 'academic',
    mark: '教',
    name: '教务系统',
    desc: '培养方案、排课选课、考务成绩、学籍与教学运行',
    stages: ['方案', '排课', '考务', '成绩'],
    color: '#7c3aed',
    soft: '#f1eaff',
    flowId: 'flow-academic-warning',
    relationshipMap: '/help/academic-affairs-relationship-overview.html'
  }
]

/** 平台价值说明（纯能力描述，不含任何客户数/学校数/百分比等编造数据） */
export const PORTAL_VALUES = [
  '一个账号统一进入，按角色自动匹配权限',
  'PC 端与微信小程序协同办理',
  '覆盖学生培养全过程',
  '全程留痕、权限隔离、数据可追溯'
]
