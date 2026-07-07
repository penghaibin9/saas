/**
 * 岗位实习中心 · 岗位库 API（独立文件，隔离并行的「实习批次」任务）。
 * 真实优先 /api/v1/internship/positions/*；后端不可达回退 mock。
 * 岗位复用企业库：企业选择器走 /internship/enterprises，导师走 /enterprises/:id/contacts。
 */
import { request, shouldTryReal } from '@/services/http/client'
import { positionList, positionDetailMap, positionMeta, enterpriseOptions, enterpriseMentorMap } from '@/mocks/internship/position.mock'

const DELAY = 100
function ok(data) { return new Promise((r) => setTimeout(() => r({ code: 0, data, message: 'ok' }), DELAY)) }
function fail(message) { return Promise.resolve({ code: 1, data: null, message }) }
function paginate(list, { page = 1, pageSize = 10 } = {}) {
  return { list: list.slice((page - 1) * pageSize, (page - 1) * pageSize + pageSize), total: list.length, page, pageSize }
}
async function real(realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try { return { code: 0, data: await realFn(), message: 'ok' } } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}
async function realList(path, params, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    const d = await request(path, { params })
    return { code: 0, message: 'ok', data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) { if (e.biz) return { code: e.code || 1, data: null, message: e.message }; return mockFn() }
}
function applyMeta(p) { const m = positionMeta(p.status); p.statusLabel = m.label; p.statusTone = m.tone; p.updatedAt = '刚刚'; return p }

export const positionApi = {
  getPositions(params = {}) {
    return realList('/internship/positions', params, () => {
      let list = [...positionList]
      if (params.keyword) { const k = params.keyword.trim(); list = list.filter((p) => p.title.includes(k) || p.companyName.includes(k) || (p.majorRequirement || '').includes(k)) }
      if (params.status) list = list.filter((p) => p.status === params.status)
      if (params.companyId) list = list.filter((p) => p.companyId === params.companyId)
      if (params.risk !== undefined && params.risk !== '') list = list.filter((p) => p.riskFlag === (params.risk === true || params.risk === 'true'))
      return ok(paginate(list, params))
    })
  },
  getPositionDetail(id) {
    return real(() => request(`/internship/positions/${id}`), () => {
      const d = positionDetailMap[id]
      return d ? ok(JSON.parse(JSON.stringify(d))) : fail('岗位不存在或不在当前数据范围内')
    })
  },
  createPosition(body) {
    return real(() => request('/internship/positions', { method: 'POST', body }), () => {
      if (!(body.title || '').trim()) return fail('岗位名称必填')
      const ent = enterpriseOptions.find((e) => e.id === body.companyId)
      if (!ent) return fail('岗位必须关联企业')
      const mentor = (enterpriseMentorMap[body.companyId] || []).find((m) => m.id === body.mentorContactId)
      const p = applyMeta({ id: 'pos-' + Date.now(), companyId: ent.id, companyName: ent.name, batchId: body.batchId || '', title: body.title.trim(), category: body.category || '', majorRequirement: body.majorRequirement || '', gradeRequirement: body.gradeRequirement || '', workLocation: body.workLocation || '', salaryRange: body.salaryRange || '', subsidy: body.subsidy || '', headcount: Number(body.headcount || 1), allocatedCount: 0, remaining: Number(body.headcount || 1), mentorContactId: body.mentorContactId || '', mentorName: mentor ? mentor.name : '', riskFlag: false, riskNote: '', status: 'DRAFT', remark: body.remark || '' })
      positionList.unshift(p)
      positionDetailMap[p.id] = { ...p, company: { id: ent.id, name: ent.name, coopStatus: ent.coopStatus, coopStatusLabel: ent.coopStatus === 'ACTIVE' ? '合作中' : '待审核', blacklist: ent.blacklist }, auditTrail: [] }
      return ok(p)
    })
  },
  updatePosition(id, body) {
    return real(() => request(`/internship/positions/${id}`, { method: 'PUT', body }), () => {
      const p = positionList.find((x) => x.id === id)
      if (!p) return fail('岗位不存在')
      if (p.status === 'ARCHIVED') return fail('已归档岗位不可编辑')
      Object.assign(p, { title: body.title ?? p.title, majorRequirement: body.majorRequirement ?? p.majorRequirement, gradeRequirement: body.gradeRequirement ?? p.gradeRequirement, workLocation: body.workLocation ?? p.workLocation, salaryRange: body.salaryRange ?? p.salaryRange, headcount: body.headcount ?? p.headcount, remark: body.remark ?? p.remark })
      p.remaining = Math.max(0, p.headcount - p.allocatedCount)
      return ok(JSON.parse(JSON.stringify(applyMeta(p))))
    })
  },
  setPositionStatus(id, { action, reason }) {
    return real(() => request(`/internship/positions/${id}/status`, { method: 'POST', body: { action, reason } }), () => {
      const p = positionList.find((x) => x.id === id)
      if (!p) return fail('岗位不存在')
      if (p.status === 'ARCHIVED') return fail('已归档岗位不可再变更状态')
      const ent = enterpriseOptions.find((e) => e.id === p.companyId) || {}
      if (action === 'SUBMIT') { if (p.status !== 'DRAFT') return fail('仅草稿可提交'); p.status = 'PENDING' }
      else if (action === 'PUBLISH') {
        if (!['PENDING', 'OFFLINE', 'SUSPENDED'].includes(p.status)) return fail('仅待审核/已下架/已暂停可上架')
        if (ent.blacklist || ent.coopStatus === 'BLACKLIST') return fail('黑名单企业不能发布岗位')
        if (ent.coopStatus !== 'ACTIVE') return fail('仅「合作中」企业可上架岗位')
        p.status = 'PUBLISHED'
      } else if (action === 'OFFLINE') { if (!['PUBLISHED', 'SUSPENDED', 'FULL'].includes(p.status)) return fail('仅上架/暂停/满员可下架'); p.status = 'OFFLINE' }
      else if (action === 'SUSPEND') { if (p.status !== 'PUBLISHED') return fail('仅已上架可暂停'); p.status = 'SUSPENDED' }
      else if (action === 'ARCHIVE') { p.status = 'ARCHIVED' }
      else return fail('非法动作')
      return ok(JSON.parse(JSON.stringify(applyMeta(p))))
    })
  },
  markPositionRisk(id, { on, note }) {
    return real(() => request(`/internship/positions/${id}/risk`, { method: 'POST', body: { on, note } }), () => {
      const p = positionList.find((x) => x.id === id)
      if (!p) return fail('岗位不存在')
      if (on) { if (!(note || '').trim()) return fail('标记风险岗位必须填写风险说明'); p.riskFlag = true; p.riskNote = note.trim(); p.status = 'RISK' }
      else { p.riskFlag = false; p.riskNote = ''; p.status = 'OFFLINE' }
      return ok(JSON.parse(JSON.stringify(applyMeta(p))))
    })
  },
  getPositionStats() {
    return real(() => request('/internship/positions/stats'), () => {
      const byStatus = ['DRAFT', 'PENDING', 'PUBLISHED', 'OFFLINE', 'SUSPENDED', 'FULL', 'RISK', 'ARCHIVED'].map((s) => ({ status: s, label: positionMeta(s).label, count: positionList.filter((p) => p.status === s).length }))
      return ok({ total: positionList.length, byStatus, riskCount: positionList.filter((p) => p.riskFlag).length, publishedCapacity: 0, publishedAllocated: 0 })
    })
  },
  importPositionsDryRun(rows) {
    return real(() => request('/internship/positions/import/dry-run', { method: 'POST', body: { rows } }), () => {
      const names = new Set(enterpriseOptions.map((e) => e.name))
      const errors = []; let valid = 0
      rows.forEach((r, i) => {
        if (!(r.title || '').trim()) { errors.push({ rowNo: i + 1, field: 'title', message: '岗位名称必填' }); return }
        if (!names.has((r.company || '').trim())) { errors.push({ rowNo: i + 1, field: 'company', message: `未匹配到企业：${r.company || '空'}` }); return }
        valid++
      })
      return ok({ total: rows.length, validRows: valid, invalidRows: errors.length, errors })
    })
  },
  importPositionsConfirm(rows) {
    return real(() => request('/internship/positions/import/confirm', { method: 'POST', body: { rows } }), () => ok({ created: rows.length }))
  },
  exportPositions(params = {}) {
    return real(() => request('/internship/positions/export', { method: 'POST', params }), () => ok({ filename: '岗位库导出.csv', content: '岗位名称,所属企业,状态\n（mock 导出）', rowCount: positionList.length }))
  },
  // 企业选择器 / 企业导师（复用企业库接口）
  getEnterpriseOptions() {
    return real(() => request('/internship/enterprises', { params: { page: 1, pageSize: 200 } }).then((d) => (d.items || []).map((e) => ({ id: e.id, name: e.name, coopStatus: e.coopStatus, blacklist: e.blacklist }))), () => ok(JSON.parse(JSON.stringify(enterpriseOptions))))
  },
  getEnterpriseMentors(companyId) {
    return real(() => request(`/internship/enterprises/${companyId}/contacts`).then((d) => (d.items || []).filter((c) => c.contactType === 'MENTOR')), () => ok(JSON.parse(JSON.stringify(enterpriseMentorMap[companyId] || []))))
  }
}

export default positionApi
