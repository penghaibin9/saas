import { OFFICIAL_SALES_PAGE_MAP } from './officialSalesPages.js'

import catalog from '../../../products.json' with { type: 'json' }

// 元数据统一供导航、预约意向和新闻关联；已确认原介绍仍来自原详情页。
export const PRODUCT_DOMAINS = Object.freeze(catalog.domains.map(Object.freeze))
export const COMPANY_PRODUCTS = Object.freeze(catalog.products.filter(product => product.public).map(product => Object.freeze({ ...product, children: Object.freeze(product.children || []), introduction: OFFICIAL_SALES_PAGE_MAP[product.path]?.description || '' })))

export const PRODUCT_INTEREST_BY_SLUG = Object.freeze({
  ...Object.fromEntries(COMPANY_PRODUCTS.map(product => [product.key, product.interest || product.name])),
  'academic-affairs': '教务系统', 'student-affairs': '学工中心', graduation: '毕业设计',
  'wechat-academic': '教务与微信小程序', all: '整体解决方案', deployment: '私有化部署与系统集成', orientation: '数字迎新'
})
export const PRODUCT_INTERESTS = Object.freeze([...new Set(Object.values(PRODUCT_INTEREST_BY_SLUG))])
export const COMPANY_NAVIGATION = Object.freeze([
  { path: '/products', label: '产品中心' }, { path: '/solutions', label: '解决方案' },
  { path: '/news', label: '新闻资讯', external: true },
  { path: '/services/delivery', label: '实施服务' }, { path: '/about', label: '关于跃科' }
])
export function productsInDomain(domain) {
  return COMPANY_PRODUCTS.filter(product => !domain || product.domain === domain)
}

export const SOLUTION_CONTACTS = Object.freeze({
  'student-lifecycle': { product: 'platform', name: '学生全生命周期' },
  orientation: { product: 'orientation', name: '数字迎新' },
  'multi-terminal': { product: 'all', name: '多端协同' },
  'teacher-workbench': { product: 'all', name: '教师工作台' },
  'student-services': { product: 'all', name: '学生服务门户' },
  'security-governance': { product: 'deployment', name: '安全与数据治理' },
  integration: { product: 'deployment', name: '统一身份与集成' },
  deployment: { product: 'deployment', name: '部署上线' }
})
export function solutionContactRoute(path) {
  const slug = path.startsWith('/solutions/') ? path.split('/').at(-1) : ''
  const solution = Object.hasOwn(SOLUTION_CONTACTS, slug) ? SOLUTION_CONTACTS[slug] : undefined
  return solution ? { path: '/contact', query: { product: solution.product, solution: slug } } : { path: '/contact' }
}
export function consultationContext(query = {}) {
  const slug = String(query.solution || '')
  const product = String(query.product || '')
  const solution = Object.hasOwn(SOLUTION_CONTACTS, slug) ? SOLUTION_CONTACTS[slug] : undefined
  return { interest: Object.hasOwn(PRODUCT_INTEREST_BY_SLUG, product) ? PRODUCT_INTEREST_BY_SLUG[product] : '', message: solution ? `关注方案：${solution.name}` : '' }
}
