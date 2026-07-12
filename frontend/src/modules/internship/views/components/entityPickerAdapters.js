/**
 * 岗位实习 · 业务选择器适配层（模块内部）。
 *
 * 作用：给公共 AppStudentPicker / AppPositionPicker / AppCompanyPicker 等
 * （基座 AppRemoteSelect，见 @/components/common）注入岗位实习域的真实搜索接口，
 * 把「一次性加载 200 条的普通下拉」升级为「关键字远程搜索」。
 *
 * 铁律：
 * 1. 关键字过滤、数据范围一律由后端接口裁定（/students、/internship/* 均已支持 keyword），
 *    前端不放大可见范围、不使用 mock；
 * 2. 每次搜索只取前 20 条，不一次性拉全校数据；
 * 3. 失败 throw 给 AppRemoteSelect 展示错误与重试；
 * 4. 陈旧响应防护：被更新输入取代的旧请求永不返回（防止旧结果覆盖新结果）。
 */
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { matchApi } from '@/modules/internship/api/match.api'
import { positionApi } from '@/modules/internship/api/position.api'
import { internshipApi } from '@/modules/internship/api/internship.api'

const PAGE_SIZE = 20

/** 陈旧响应防护：仅让「最后一次发起」的请求把结果交给选择器 */
function latestOnly(fn) {
  let seq = 0
  return async (keyword) => {
    const my = ++seq
    const res = await fn(keyword)
    if (my !== seq) return new Promise(() => {}) // 已被更新的输入取代：永不返回
    return res
  }
}

function unwrap(res, mapper) {
  if (!res || res.code !== 0) throw new Error((res && res.message) || '搜索失败，请重试')
  return (res.data || []).map(mapper)
}

/** 建档用：学生主档搜索（姓名/学号，后端按数据范围过滤；已建档由后端建档校验拦截重复） */
export const searchMasterStudents = latestOnly(async (keyword) => {
  const res = await internStudentApi.getStudentOptions(keyword, PAGE_SIZE)
  return unwrap(res, (s) => ({ label: s.name, desc: `学号 ${s.studentNo}`, value: s.id }))
})

/** 匹配/关联用：未落实岗位的实习学生 */
export const searchUnassignedInternStudents = latestOnly(async (keyword) => {
  const res = await matchApi.getStudentOptions(keyword, PAGE_SIZE)
  return unwrap(res, (s) => ({
    label: s.name || s.studentName,
    desc: [s.studentNo, s.className].filter(Boolean).join(' · '),
    value: s.id
  }))
})

/** 全部实习学生（评价/成绩等录入场景） */
export const searchInternStudents = latestOnly(async (keyword) => {
  const res = await internshipApi.getStudents({ page: 1, pageSize: PAGE_SIZE, keyword: keyword || '' })
  if (!res || res.code !== 0) throw new Error((res && res.message) || '搜索失败，请重试')
  const list = (res.data && res.data.list) || []
  return list.map((s) => ({
    label: s.name || s.studentName,
    desc: [s.studentNo, s.className, s.enterpriseName].filter(Boolean).join(' · '),
    value: s.id
  }))
})

/** 已上架岗位搜索（显示企业与余量） */
export const searchPublishedPositions = latestOnly(async (keyword) => {
  const res = await internStudentApi.getPublishedPositions(keyword, PAGE_SIZE)
  return unwrap(res, (p) => ({
    label: p.title,
    desc: `${p.companyName} · 余 ${p.remaining}（${p.capacity}）`,
    value: p.id,
    disabled: p.remaining === 0
  }))
})

/** 合作企业搜索 */
export const searchEnterprises = latestOnly(async (keyword) => {
  const res = await positionApi.getEnterpriseOptions(keyword, PAGE_SIZE)
  return unwrap(res, (e) => ({ label: e.name, desc: e.industry || '', value: e.id }))
})
