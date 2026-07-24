/**
 * 消息中心选择器适配：班级/学院数据由后端按发布权限与数据范围收敛。
 */
import { request } from '@/services/http'

async function loadOptions(audienceType, keyword = '') {
  const data = await request('/admin/message-campaigns/audience-options', {
    params: { type: audienceType, keyword: keyword || undefined, pageSize: 200 }
  })
  const items = (data && data.items) || []
  return items.map((row) => ({
    value: String(row.id),
    label: row.name || `#${row.id}`,
    desc: row.desc || '',
    raw: row
  }))
}

function makeAdapter(audienceType) {
  const search = (keyword = '') => loadOptions(audienceType, keyword)
  const resolve = async (value) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await search('')
    const resolved = values
      .map((v) => options.find((o) => String(o.value) === String(v)))
      .filter(Boolean)
    return Array.isArray(value) ? resolved : resolved[0]
  }
  return { search, resolve }
}

export const messageCenterPickerAdapters = {
  class: makeAdapter('CLASS'),
  college: makeAdapter('COLLEGE')
}
