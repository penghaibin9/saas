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
