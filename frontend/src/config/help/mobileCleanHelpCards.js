import { MOBILE_HELP_CARDS } from './mobileHelpCards'
import { MOBILE_OPERATIONS_HELP_CARDS } from './mobileOperationsHelpCards'

/**
 * 微信小程序知识清洗 V2 正式正文。
 *
 * 既有 mobile*HelpCards 已逐项按当前页面行为核验；本层补齐所有正式任务卡都必须具备的
 * 前置条件与权限边界，并把已经真实落地的统一帮助入口纳入正式知识。
 * 通用教师审批中心仍不发布“退回/驳回”操作卡：当前两种 UI 文案共用 reject 后端动作，
 * 在产品状态机真正拆开前不能把它写成成熟的三动作审批能力。
 */
function isStudentCard(card) {
  const roles = Array.isArray(card?.roles) ? card.roles : []
  return roles.length > 0 && roles.every((role) => String(role).includes('学生'))
}

function withMobileOperationalContract(card) {
  const studentOnly = isStudentCard(card)
  return {
    ...card,
    prerequisites: card.prerequisites || [
      `已使用${studentOnly ? '学生' : '教师/辅导员等卡片所列'}身份登录微信小程序，并能从当前身份看到该业务入口。`,
      '正式写操作需要小程序能够连接真实后端；按钮状态、业务状态和最终结果均以服务器最新返回为准。',
      '网络、微信系统权限或隐私授权参与该操作时，需先满足页面当前提示的运行条件。'
    ],
    permissions: card.permissions || (studentOnly
      ? [
          '学生只能查看和操作本人在当前租户内可访问的业务记录，不能通过小程序参数切换到他人数据。',
          '页面是否显示按钮不是授权边界；服务端仍会校验登录身份、记录归属、当前状态、版本和业务规则。'
        ]
      : [
          '教师、辅导员和管理员只能查看、办理当前身份与数据范围覆盖的记录；跨范围操作由服务端拒绝。',
          '待办可见、页面可进入或按钮可见都不等于拥有最终动作权限；后端权限点、数据范围和状态机是最终边界。'
        ])
  }
}

const VERIFIED_EXISTING_MOBILE_CARDS = [
  ...MOBILE_HELP_CARDS,
  ...MOBILE_OPERATIONS_HELP_CARDS
].map(withMobileOperationalContract)

export const MOBILE_UNIFIED_HELP_CARD = {
  id: 'mobile-unified-help-entry',
  module: '微信小程序 · 帮助中心',
  title: '学生和教师如何从小程序进入统一帮助中心',
  roles: ['学生', '教师', '辅导员', '学校管理员'],
  platforms: ['微信小程序'],
  mobilePath: 'pages/common/help/index',
  entry: '学生小程序 / 教师小程序 → 我的 → 帮助与反馈',
  keywords: ['小程序帮助', '帮助与反馈', '统一帮助中心', 'VITE_HELP_CENTER_URL', 'web-view', '业务域名', 'role', 'source=miniapp'],
  summary: '学生端和教师端“我的 → 帮助与反馈”都进入同一个 pages/common/help/index 页面，再通过 web-view 打开 PC 统一维护的帮助正文；页面自动附带当前角色和 source=miniapp，不在小程序复制第二套帮助内容。',
  prerequisites: [
    '小程序当前已经登录并能进入“我的”页面；学生端和教师端都已配置“帮助与反馈”入口。',
    '正式构建需要配置 VITE_HELP_CENTER_URL，地址应指向可访问的 HTTPS 帮助中心页面。',
    '微信小程序正式环境使用 web-view 时，对应 HTTPS 域名还必须在微信公众平台登记为业务域名。'
  ],
  permissions: [
    '帮助入口本身不授予任何业务权限；帮助中心带入 role 只用于内容相关性筛选，不能代替后端授权。',
    '用户即使从帮助正文看到某项业务说明，真实页面和动作仍由当前登录身份、租户、权限点、数据范围和状态机决定。'
  ],
  steps: [
    '进入学生端或教师端“我的”，点击“帮助与反馈”。',
    '小程序进入 pages/common/help/index，并从当前 session 计算帮助角色：学生为 student；教师侧按当前身份归一化为 teacher / student-affairs / academic / school-admin。',
    '页面把 role 和 source=miniapp 作为查询参数附加到 VITE_HELP_CENTER_URL，再通过 web-view 打开统一帮助中心。',
    '如果没有配置帮助地址，页面不会跳到假链接，而是明确提示“帮助中心尚未配置访问地址”并给出正式环境配置要求。',
    '在统一帮助中心搜索当前问题，按照已发布且通过 verified-only 门的任务卡执行；未重新验真的旧知识不会因为历史文件存在而重新可搜。'
  ],
  successCriteria: [
    '学生端、教师端都能从“我的 → 帮助与反馈”进入同一帮助页面。',
    '生成的帮助 URL 带有正确 role 与 source=miniapp 参数，统一帮助中心可据此优先展示相关内容。',
    '正式微信环境的 HTTPS 地址和业务域名配置完成后，web-view 能正常打开；未配置时显示明确兜底说明。'
  ],
  troubleshooting: [
    '看到“帮助中心尚未配置访问地址”：检查构建环境 VITE_HELP_CENTER_URL，不要在小程序源码里硬编码生产域名。',
    '开发环境能开、正式微信打不开：检查 URL 是否为 HTTPS，并确认同一域名已在微信公众平台登记为业务域名。',
    '打开后内容角色不匹配：核对当前 session 身份与 role 归一化结果；帮助筛选只影响相关性，不修改业务授权。',
    '某篇旧帮助搜不到：先确认它是否已经通过 V2 重新验真；被 verified-only 发布门隔离的历史知识不会恢复展示。'
  ]
}

export const MOBILE_CLEAN_HELP_CARDS = [
  MOBILE_UNIFIED_HELP_CARD,
  ...VERIFIED_EXISTING_MOBILE_CARDS
]
