/**
 * 中国行政区划（省 / 市 / 区县）数据与查询工具。
 * ────────────────────────────────────────────────────────────
 * 数据来源：@vant/area-data（依据国家统计局行政区划代码维护的开源包），
 * 不在仓库里手抄一份区划表——手抄的表没人维护，撤县设区后就会失真。
 *
 * 区划代码规则（6 位）：前 2 位省、前 4 位市、完整 6 位区县，
 * 因此父子关系用前缀匹配即可，无需再建一张关系表。
 *
 * 本文件与 student-portal/src/data/chinaRegions.js 保持同一套导出契约，
 * 两个应用各自独立打包（仓库未建立跨应用 JS 共享机制），修改时请同步。
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

/** 直辖市的省级名与市级名重复（如「北京市 北京市」），显示时去重 */
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

/** 全量「省 市 区县」路径，供关键词搜索用 */
export const CHINA_REGION_PATHS = CHINA_COUNTIES.map((county) => {
  const provinceCode = `${county.code.slice(0, 2)}0000`
  const cityCode = `${county.code.slice(0, 4)}00`
  return {
    provinceCode,
    cityCode,
    countyCode: county.code,
    label: regionLabel(provinceCode, cityCode, county.code)
  }
}).filter((item) => item.label)

export function searchChinaRegions(keyword, limit = 40) {
  const query = String(keyword || '').trim().toLowerCase()
  if (!query) return []
  return CHINA_REGION_PATHS.filter((item) => item.label.toLowerCase().includes(query)).slice(0, limit)
}

/**
 * 把历史遗留的自由文本反解析成区划三级码，用于「老数据打开编辑页时能定位到已选项」。
 * 解析不出来时返回 null——调用方须保留原始文本，不得因为解析失败就清空用户已有数据。
 */
export function resolveChinaRegion(value) {
  const text = String(value || '').trim()
  if (!text) return null

  const countyPath = CHINA_REGION_PATHS.find((item) => item.label === text)
  if (countyPath) return countyPath

  const city = CHINA_CITIES.find((item) => text.includes(item.name) || item.name.includes(text))
  if (city) {
    const provinceCode = `${city.code.slice(0, 2)}0000`
    return { provinceCode, cityCode: city.code, countyCode: '', label: regionLabel(provinceCode, city.code) }
  }

  const province = CHINA_PROVINCES.find((item) => text.includes(item.name) || item.name.includes(text))
  if (province) return { provinceCode: province.code, cityCode: '', countyCode: '', label: province.name }
  return null
}
