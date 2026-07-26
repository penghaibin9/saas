/**
 * 组织选择器的公共数据适配层（学院 / 专业 / 班级 / 年级）。
 *
 * 为什么放在 components/common 而不是某个模块里：
 * AppOrgCascader、AppCollegePicker、AppMajorPicker、AppClassPicker 是公共组件，
 * 但此前只有教务在 pickerAdapters 里实现了喂它们数据的 adapter，学工/实习/毕设
 * 把组件放进页面就是空下拉。选人（实习批次、毕设批次、评奖）各写一份必然口径分裂，
 * 因此实现一次，各模块 spread 进自己的 adapter 集合即可。
 *
 * 数据源：`GET /directory/org-tree`（按调用者数据范围裁剪，学生/家长拒绝）
 *        `GET /directory/grades`
 * 数据范围一律由后端裁剪，前端不得自行放大可见范围。
 *
 * 用法（模块的 pickerAdapters.js）：
 *   import { createOrgPickerAdapters } from '@/components/common/picker/orgAdapters'
 *   export const xxxPickerAdapters = { ...createOrgPickerAdapters(), student, ... }
 */
import { request } from '@/services/http/client'

/** 组织树在一次页面停留内基本不变，缓存住避免四个选择器各拉一遍 */
let _treeCache = null
let _treePromise = null

export function clearOrgTreeCache() {
  _treeCache = null
  _treePromise = null
}

function firstDefined(row, keys, fallback = '') {
  for (const key of keys) {
    const v = row?.[key]
    if (v !== undefined && v !== null && v !== '') return v
  }
  return fallback
}

/**
 * 归一化组织节点。同时兼容两种后端形状：
 *  - 公共端点：{ value, label, children }
 *  - 教务旧接口：{ id, collegeName, majors:[{ id, majorName, classes:[...] }] }
 * 兼容而不是二选一，是为了让教务也能换用本适配器，不必先改它的接口。
 */
function normalizeNode(node, level = 0) {
  const value = firstDefined(node, ['value', 'id', ['collegeId', 'majorId', 'classId'][level] || 'id'])
  const label = firstDefined(node, ['label', 'name', ['collegeName', 'majorName', 'className'][level] || 'name'])
  const rawChildren = node?.children || node?.majors || node?.classes || []
  return {
    value: String(value ?? ''),
    label: String(label ?? ''),
    grade: node?.grade || '',
    studentCount: Number(node?.studentCount || 0),
    children: rawChildren.map((child) => normalizeNode(child, level + 1))
  }
}

async function loadTree() {
  if (_treeCache) return _treeCache
  if (_treePromise) return _treePromise
  _treePromise = (async () => {
    const data = await request('/directory/org-tree')
    const rows = Array.isArray(data) ? data : (data?.tree || data?.items || data?.colleges || [])
    _treeCache = rows.map((row) => normalizeNode(row))
    return _treeCache
  })()
  try {
    return await _treePromise
  } finally {
    _treePromise = null
  }
}

/** 把树摊平成某一层的选项（0=学院 1=专业 2=班级），带上父级路径便于同名区分 */
async function flatten(level) {
  const tree = await loadTree()
  const out = []
  const walk = (nodes, depth, path) => {
    for (const n of nodes) {
      if (depth === level) {
        out.push({
          value: n.value,
          label: n.label,
          desc: [path.join(' / '), n.grade, n.studentCount ? `${n.studentCount} 人` : '']
            .filter(Boolean).join(' · '),
          raw: n
        })
      } else if (n.children?.length) {
        walk(n.children, depth + 1, [...path, n.label])
      }
    }
  }
  walk(tree, 0, [])
  return out
}

function levelAdapter(level) {
  const search = async (keyword = '') => {
    const options = await flatten(level)
    if (!keyword) return options
    const kw = String(keyword).toLowerCase()
    return options.filter((o) => `${o.label} ${o.desc}`.toLowerCase().includes(kw))
  }
  const resolve = async (value) => {
    const values = Array.isArray(value) ? value : [value]
    const options = await flatten(level)
    const hit = values
      .map((v) => options.find((o) => String(o.value) === String(v)))
      .filter(Boolean)
    return Array.isArray(value) ? hit : hit[0]
  }
  return { search, resolve }
}

const gradeAdapter = {
  async search(keyword = '') {
    const data = await request('/directory/grades')
    const items = (Array.isArray(data) ? data : data?.items || []).map((g) => ({
      value: String(g.value ?? g),
      label: String(g.label ?? g.value ?? g),
      desc: g.studentCount ? `${g.studentCount} 人` : ''
    }))
    if (!keyword) return items
    const kw = String(keyword).toLowerCase()
    return items.filter((o) => o.label.toLowerCase().includes(kw))
  },
  async resolve(value) {
    const values = Array.isArray(value) ? value : [value]
    const items = await gradeAdapter.search('')
    const hit = values.map((v) => items.find((o) => String(o.value) === String(v))).filter(Boolean)
    return Array.isArray(value) ? hit : hit[0]
  }
}

/**
 * 生成组织类选择器适配器。key 与 entityPickers.js 中各 Picker 的 presets.key 对齐：
 * college / major / class / grade / orgCascade。
 */
export function createOrgPickerAdapters() {
  return {
    orgCascade: { load: loadTree },
    college: levelAdapter(0),
    major: levelAdapter(1),
    class: levelAdapter(2),
    grade: gradeAdapter
  }
}
