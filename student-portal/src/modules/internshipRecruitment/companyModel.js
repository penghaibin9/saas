export const ENTERPRISE_PUBLIC_FIELDS = Object.freeze([
  'id',
  'logo',
  'name',
  'industry',
  'nature',
  'scale',
  'city',
  'region',
  'shortIntro',
  'mainBusiness',
  'website',
  'internCount',
  'activeJobs',
  'schoolVerified'
])

function first(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null) return raw[key]
  }
  return null
}

export function normalizeEnterprisePublic(raw = {}) {
  return {
    id: first(raw, 'id', 'companyId'),
    logo: first(raw, 'logo', 'logoUrl') || '',
    name: first(raw, 'name', 'companyName') || '企业名称待完善',
    industry: first(raw, 'industry') || '',
    nature: first(raw, 'nature', 'companyNature') || '',
    scale: first(raw, 'scale', 'companyScale') || '',
    city: first(raw, 'city') || '',
    region: first(raw, 'region', 'district') || '',
    shortIntro: first(raw, 'shortIntro', 'intro', 'companyIntro') || '',
    mainBusiness: first(raw, 'mainBusiness', 'businessScope') || '',
    website: first(raw, 'website', 'officialWebsite') || '',
    internCount: Number(first(raw, 'internCount', 'currentInternCount') || 0),
    activeJobs: Number(first(raw, 'activeJobs', 'activePositionCount') || 0),
    schoolVerified: Boolean(first(raw, 'schoolVerified', 'verified'))
  }
}
