/**
 * 中国行政区划（省 / 市 / 区县）数据与查询工具（小程序端）。
 * 数据来源 @vant/area-data（国家统计局区划码维护），不在仓库手抄区划表。
 *
 * 与 frontend/src/utils/chinaRegions.js、student-portal 与 enterprise-portal 的
 * src/data/chinaRegions.js 保持同一套导出契约（各端独立打包，仓库未建立跨应用 JS 共享），
 * 另额外提供 multiSelector 所需的索引换算，供 uni-app 原生 <picker mode="multiSelector"> 使用。
 */
import { areaList } from '@vant/area-data'

function toOptions(record) {
  return Object.entries(record).map(([code, name]) => ({ code, name }))
}

const provinceMap = areaList.province_list
const cityMap = areaList.city_list
const countyMap = areaList.county_list

export const CHINA_PROVINCES = toOptions(provinceMap)
export const CHINA_CITIES = toOptions(cityMap)
export const CHINA_COUNTIES = toOptions(countyMap)

export function citiesForProvince(provinceCode) {
  const prefix = String(provinceCode || '').slice(0, 2)
  return prefix ? CHINA_CITIES.filter((item) => item.code.startsWith(prefix)) : []
}

export function countiesForCity(cityCode) {
  const prefix = String(cityCode || '').slice(0, 4)
  return prefix ? CHINA_COUNTIES.filter((item) => item.code.startsWith(prefix)) : []
}

/** 直辖市省名与市名重复（北京市 北京市），展示时去重 */
function uniqueNames(names) {
  return names.filter((name, index) => name && name !== names[index - 1])
}

export function regionLabel(provinceCode, cityCode, countyCode = '') {
  return uniqueNames([
    provinceMap[provinceCode],
    cityMap[cityCode],
    countyMap[countyCode]
  ]).join(' ')
}

/**
 * 把自由文本反解析成三级下标，供 multiSelector 定位已选项。
 * 解析不到返回 [0,0,0]，调用方须保留原文本不清空。
 */
export function resolveRegionIndex(value) {
  const text = String(value || '').trim()
  if (!text) return [0, 0, 0]

  for (let pi = 0; pi < CHINA_PROVINCES.length; pi += 1) {
    const province = CHINA_PROVINCES[pi]
    if (!text.includes(province.name)) continue
    const cities = citiesForProvince(province.code)
    for (let ci = 0; ci < cities.length; ci += 1) {
      const city = cities[ci]
      if (!text.includes(city.name)) continue
      const counties = countiesForCity(city.code)
      const idx = counties.findIndex((county) => text.includes(county.name))
      return [pi, ci, idx >= 0 ? idx : 0]
    }
    return [pi, 0, 0]
  }
  return [0, 0, 0]
}

/** 由三级下标取出展示文本 */
export function labelFromIndex(indexes) {
  const [pi = 0, ci = 0, di = 0] = indexes || []
  const province = CHINA_PROVINCES[pi]
  if (!province) return ''
  const cities = citiesForProvince(province.code)
  const city = cities[ci]
  if (!city) return province.name
  const counties = countiesForCity(city.code)
  const county = counties[di]
  return regionLabel(province.code, city.code, county ? county.code : '')
}

/** 由三级下标生成 multiSelector 的 range（三列名称数组） */
export function rangeFromIndex(indexes) {
  const [pi = 0, ci = 0] = indexes || []
  const province = CHINA_PROVINCES[pi]
  const cities = province ? citiesForProvince(province.code) : []
  const city = cities[ci]
  const counties = city ? countiesForCity(city.code) : []
  return [
    CHINA_PROVINCES.map((item) => item.name),
    cities.map((item) => item.name),
    counties.map((item) => item.name)
  ]
}
