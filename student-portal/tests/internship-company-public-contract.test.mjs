import test from 'node:test'
import assert from 'node:assert/strict'

import {
  ENTERPRISE_PUBLIC_FIELDS,
  normalizeEnterprisePublic
} from '../src/modules/internshipRecruitment/companyModel.js'

test('A03-4 enterprise public projection is a strict whitelist', () => {
  const company = normalizeEnterprisePublic({
    id: 18,
    logoUrl: '/logo.png',
    companyName: '湖湘智能制造有限公司',
    industry: '智能制造',
    companyNature: '民营企业',
    companyScale: '500-999人',
    city: '长沙市',
    district: '岳麓区',
    intro: '智能制造合作企业',
    businessScope: '工业机器人与数控设备',
    officialWebsite: 'https://example.com',
    currentInternCount: 23,
    activePositionCount: 6,
    verified: true,
    credit_code: 'SECRET',
    internalPhone: '13800000000',
    blacklistReason: 'SECRET',
    reviewComment: 'SECRET',
    remark: 'SECRET'
  })

  assert.deepEqual(Object.keys(company), ENTERPRISE_PUBLIC_FIELDS)
  assert.equal(company.name, '湖湘智能制造有限公司')
  assert.equal(company.schoolVerified, true)
  for (const forbidden of ['credit_code', 'internalPhone', 'blacklistReason', 'reviewComment', 'remark']) {
    assert.equal(Object.hasOwn(company, forbidden), false)
  }
})

test('A03-4 enterprise page never manufactures internal contact fields', () => {
  const company = normalizeEnterprisePublic({ name: '企业A', phone: '13800000000', contactName: '内部HR' })
  assert.equal(company.name, '企业A')
  assert.equal(Object.hasOwn(company, 'phone'), false)
  assert.equal(Object.hasOwn(company, 'contactName'), false)
})
