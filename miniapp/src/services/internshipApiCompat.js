const optionalServiceModules = import.meta.glob('./*.js')
let internshipModulePromise

function unavailable(method) {
  return Promise.reject({
    code: 'INTERNSHIP_API_NOT_AVAILABLE',
    biz: true,
    message: `当前分支尚未接入岗位实习接口：${method}`
  })
}

function loadInternshipModule() {
  if (internshipModulePromise) return internshipModulePromise
  const loader = optionalServiceModules['./internshipApi.js']
  internshipModulePromise = loader ? loader() : Promise.resolve(null)
  return internshipModulePromise
}

export function callOptionalInternship(method, args = [], fallback) {
  return loadInternshipModule().then((api) => {
    const handler = api && api[method]
    if (typeof handler === 'function') return handler(...args)
    if (typeof fallback === 'function') return fallback()
    return unavailable(method)
  })
}

export function mapInternshipDashboard(result) {
  const r = result || {}
  if (!r.hasData) {
    return {
      hasBatch: false,
      needSelect: !!r.needSelect,
      candidates: r.candidates || [],
      message: r.message || '暂无实习记录',
      _real: true,
      company: '', post: '', schoolMentor: '', companyMentor: '', batch: '', batchId: '',
      timeline: [], weekly: { week: '第 1 周', submitted: false, lastFeedback: '' },
      checkin: { done: false, time: '', totalDays: 0, place: '', note: '仅在点击时采集定位，不后台定位' },
      status: { todayCheckin: 'PENDING', weekly: 'PENDING_SUBMIT', agreement: 'PENDING', insurance: 'PENDING', onboard: 'PENDING', leave: 'NONE' }
    }
  }
  return {
    hasBatch: true,
    needSelect: false,
    candidates: r.candidates || [],
    historyMode: !!r.historyMode,
    recordId: r.recordId || '',
    batchId: r.batchId || '',
    batch: r.batchName || '实习批次',
    company: r.enterpriseName || '',
    post: r.positionName || '',
    schoolMentor: r.advisorName || '待分配',
    companyMentor: r.enterpriseMentor || '待分配',
    statusText: r.recordStatus || '',
    timeline: r.timeline || [],
    _real: true,
    weekly: {
      week: `第 ${Number((r.weekly && r.weekly.weekNumber) || 1)} 周`,
      submitted: !!(r.weekly && r.weekly.submitted),
      lastFeedback: (r.weekly && r.weekly.lastFeedback) || ''
    },
    checkin: {
      done: !!(r.todayCheckin && r.todayCheckin.done),
      time: (r.todayCheckin && r.todayCheckin.time) || '',
      totalDays: Number((r.todayCheckin && r.todayCheckin.totalDays) || 0),
      place: r.workLocation || r.enterpriseName || '实习地点待定',
      note: '仅在点击时采集定位，不后台定位'
    },
    status: {
      todayCheckin: r.todayCheckin && r.todayCheckin.done ? 'COMPLETED' : 'PENDING',
      weekly: r.weekly && r.weekly.submitted ? 'COMPLETED' : 'PENDING_SUBMIT',
      agreement: r.agreementStatus || 'PENDING',
      insurance: r.insuranceStatus || 'PENDING',
      onboard: r.recordStatus || 'PENDING',
      leave: r.leaveStatus || 'NONE'
    }
  }
}

export function loadInternshipDashboard(batchId, legacyFallback) {
  return loadInternshipModule().then((api) => {
    if (api && typeof api.studentInternshipDashboard === 'function') {
      return api.studentInternshipDashboard(batchId).then(mapInternshipDashboard)
    }
    return legacyFallback()
  })
}
