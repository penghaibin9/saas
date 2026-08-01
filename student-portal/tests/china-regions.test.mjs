import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CHINA_PROVINCES,
  citiesForProvince,
  countiesForCity,
  regionLabel,
  resolveChinaRegion,
  searchChinaRegions
} from '../src/data/chinaRegions.js'

test('地区数据覆盖省、市、区县三级', () => {
  assert.equal(CHINA_PROVINCES.length, 34)
  assert.ok(citiesForProvince('430000').some((item) => item.code === '430100' && item.name === '长沙市'))
  assert.ok(countiesForCity('430100').some((item) => item.code === '430104' && item.name === '岳麓区'))
})

test('地区搜索返回完整路径并限制结果数量', () => {
  const results = searchChinaRegions('岳麓区', 5)
  assert.equal(results.length, 1)
  assert.deepEqual(results[0], {
    provinceCode: '430000',
    cityCode: '430100',
    countyCode: '430104',
    label: '湖南省 长沙市 岳麓区'
  })
  assert.ok(searchChinaRegions('市', 3).length <= 3)
})

test('直辖市路径去重且已有城市值可回填', () => {
  assert.equal(regionLabel('110000', '110100', '110101'), '北京市 东城区')
  assert.deepEqual(resolveChinaRegion('湖南省 长沙市 岳麓区'), {
    provinceCode: '430000',
    cityCode: '430100',
    countyCode: '430104',
    label: '湖南省 长沙市 岳麓区'
  })
})
