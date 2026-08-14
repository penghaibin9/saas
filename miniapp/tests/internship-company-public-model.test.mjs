import test from 'node:test'
import assert from 'node:assert/strict'

import { mobileCompanyLocation, normalizeMobilePublicCompany } from '../src/modules/internshipCompanyPublicModel.js'

test('student mobile company DTO keeps only public fields', () => {
  const company = normalizeMobilePublicCompany({
    id: 7,
    name: '跃科合作企业',
    industry: '软件和信息技术服务业',
    nature: '民营企业',
    scale: '100-499人',
    city: '长沙市',
    region: '岳麓区',
    shortIntro: '校企合作单位',
    mainBusiness: '软件研发',
    website: 'https://example.test',
    internCount: 18,
    activeJobs: 6,
    schoolVerified: true,
    credit_code: 'SHOULD_NOT_LEAK',
    internalPhone: '13800000000',
    blacklistReason: 'SHOULD_NOT_LEAK',
    reviewComment: 'SHOULD_NOT_LEAK',
    remark: 'SHOULD_NOT_LEAK'
  })

  assert.deepEqual(Object.keys(company).sort(), [
    'activeJobs', 'city', 'id', 'industry', 'internCount', 'logo', 'mainBusiness',
    'name', 'nature', 'region', 'scale', 'schoolVerified', 'shortIntro', 'website'
  ].sort())
  assert.equal(company.name, '跃科合作企业')
  assert.equal(company.schoolVerified, true)
  assert.equal('credit_code' in company, false)
  assert.equal('internalPhone' in company, false)
  assert.equal('blacklistReason' in company, false)
  assert.equal('reviewComment' in company, false)
  assert.equal('remark' in company, false)
})

test('company public location is compact and safe', () => {
  assert.equal(mobileCompanyLocation({ city: '长沙市', region: '岳麓区' }), '长沙市 · 岳麓区')
  assert.equal(mobileCompanyLocation({}), '地区待完善')
})
