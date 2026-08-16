const valueOf = (raw, ...keys) => {
  for (const key of keys) {
    if (raw && raw[key] !== undefined && raw[key] !== null && raw[key] !== '') return raw[key]
  }
  return null
}

/**
 * 学生侧企业公开 DTO：只投影学校允许公开的字段。
 * 禁止用 {...raw} 或返回原对象，避免 credit_code / 内部联系方式 / 黑名单与审核备注泄漏。
 */
export function normalizeMobilePublicCompany(raw = {}) {
  return {
    id: valueOf(raw, 'id', 'companyId'),
    logo: String(valueOf(raw, 'logo', 'logoUrl') || ''),
    name: String(valueOf(raw, 'name', 'companyName') || '企业信息待完善'),
    industry: String(valueOf(raw, 'industry', 'industryName') || '行业待完善'),
    nature: String(valueOf(raw, 'nature', 'companyNature') || '性质待完善'),
    scale: String(valueOf(raw, 'scale', 'companyScale') || '规模待完善'),
    city: String(valueOf(raw, 'city') || ''),
    region: String(valueOf(raw, 'region', 'district') || ''),
    shortIntro: String(valueOf(raw, 'shortIntro', 'intro', 'description') || '企业简介待完善'),
    mainBusiness: String(valueOf(raw, 'mainBusiness', 'businessScopePublic') || '主营业务待完善'),
    website: String(valueOf(raw, 'website', 'officialWebsite') || ''),
    internCount: Math.max(0, Number(valueOf(raw, 'internCount', 'currentInternCount') || 0) || 0),
    activeJobs: Math.max(0, Number(valueOf(raw, 'activeJobs', 'activeJobCount') || 0) || 0),
    schoolVerified: Boolean(valueOf(raw, 'schoolVerified', 'verified'))
  }
}

export function mobileCompanyLocation(company) {
  return [company?.city, company?.region].filter(Boolean).join(' · ') || '地区待完善'
}
