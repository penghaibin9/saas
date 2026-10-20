import { MAP_PATHS, REGION_ANCHORS, CORE_SVG } from './screen-visuals.mjs'
import { escapeHtml as e, formatCount as n, formatRate as p, FLOW, routeFor,
  createCoordinator, readSnapshot } from './screen-core.mjs'

const ICONS = {
  building: '<path d="M3 21V4l8-2v19m0-15h9v15M1 21h22M6 7h2M6 11h2M6 15h2m6-5h3m-3 4h3m-3 4h3"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/><circle cx="9" cy="7" r="4"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9S4 17 4 12V6z"/><path d="m8 12 3 3 5-6"/>',
  file: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0z"/><circle cx="12" cy="10" r="3"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18m-13 5 3 3 6-6"/>',
  star: '<path d="m12 2 3 6.5 7 1-5 5 1.2 7L12 18l-6.2 3.5 1.2-7-5-5 7-1z"/>',
  bars: '<path d="M3 21h19M5 17v-5m6 5V8m6 9V3M3 8l6-4 5 1 6-4"/>',
  briefcase: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M8 7V3h8v4M2 12c6 4 14 4 20 0M10 14h4"/>',
  warning: '<path d="m12 3 10 18H2zM12 8v6m0 3v1"/>',
  search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 7 7"/>',
  cap: '<path d="m2 8 10-5 10 5-10 5zM6 11v6l6 3 6-3v-6m4-3v9"/>',
  ring: '<circle cx="12" cy="12" r="9"/><path d="M12 3v9l6 5"/>'
}
function icon(key, cls = '') { return `<svg class="ix-icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[key] || ICONS.bars}</svg>` }
function panel(title, body, key = 'stats', cls = '') {
  return `<section class="ix-panel ${cls}"><header class="ix-panel-head"><h2>${e(title)}</h2><button type="button" data-go="${e(key)}" aria-label="查看${e(title)}相关台账">查看台账 ›</button></header>${body}</section>`
}
function metricValue(m) { return p(m?.rate) }
function metricHint(m) { return m?.state === 'ok' ? `${n(m.numerator)} / ${n(m.denominator)}` : ({ anomaly: '口径异常 · 不展示比率', empty: '无统计分母', missing: '暂无有效数据' }[m?.state] || '暂无数据') }
function donut(rows, big, label, cls = '') {
  const total = rows.reduce((sum, row) => sum + (row.value || 0), 0)
  let offset = 0
  const arcs = rows.map((row, index) => { const length = total > 0 ? row.value / total * 270.18 : 0; const path = `<circle class="s${index}" cx="55" cy="55" r="43" stroke-dasharray="${length} ${270.18-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 55 55)"/>`; offset += length; return path }).join('')
  return `<div class="ix-ring ix-donut ${cls}"><svg viewBox="0 0 110 110" aria-hidden="true"><circle class="ix-ring-track" cx="55" cy="55" r="43"/>${arcs}</svg><div><strong>${e(big)}</strong><small>${e(label)}</small></div></div>`
}
function sparkChart(points, { title, second = false, purple = false, monthly = false, id = 'chart' } = {}) {
  if (!points?.length) return `<div class="ix-spark-empty">${e(title)}<small>暂无有效序列</small></div>`
  const values = points.flatMap(pt => [pt.value, ...(second ? [pt.compliant] : [])]).filter(v => v !== null)
  const max = Math.max(4, Math.ceil(Math.max(...values, 0) / 4) * 4), w = 228, h = 91, left = 35, top = 15
  const x = i => left + i * w / Math.max(1, points.length-1), y = v => top+h - v/max*h
  const grid = [0,1,2,3,4].map(i => `<line x1="${left}" x2="${left+w}" y1="${top+h*i/4}" y2="${top+h*i/4}"/><text x="${left-5}" y="${top+h*i/4+4}" text-anchor="end">${n(max*(4-i)/4)}</text>`).join('')
  const make = (key, si) => {
    let d = '', segment = false
    for (let i=0;i<points.length;i++){const v=points[i][key];if(v===null||v===undefined){segment=false;continue}d+=`${segment?'L':'M'}${x(i)},${y(v)} `;segment=true}
    return `<g class="ix-series s${si}"><path d="${d}"/>${points.map((pt,i)=>pt[key]===null||pt[key]===undefined?'':`<circle cx="${x(i)}" cy="${y(pt[key])}" r="3"><title>${e(pt.date||pt.month)}：${n(pt[key])}</title></circle>`).join('')}</g>`
  }
  const area = points.every(pt=>pt.value!==null) ? `M${x(0)} ${top+h} ${points.map((pt,i)=>`L${x(i)} ${y(pt.value)}`).join(' ')} L${x(points.length-1)} ${top+h}Z` : ''
  return `<div class="ix-spark-chart ${purple?'ix-purple-chart':''}"><div class="ix-chart-caption">${e(title)}<small>${second?'总记录 / 合规':''}</small></div><svg viewBox="0 0 274 132" role="img" aria-label="${e(title)}"><defs><linearGradient id="ix-area-${id}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${purple?'#9961ff':'#079cf7'}" stop-opacity=".28"/><stop offset="1" stop-color="#04162b" stop-opacity="0"/></linearGradient></defs><g class="ix-grid">${grid}</g><path d="${area}" fill="url(#ix-area-${id})"/>${make('value',purple?1:0)}${second?make('compliant',2):''}<g class="ix-axis">${points.map((pt,i)=>`<text x="${x(i)}" y="124" text-anchor="middle">${e(monthly?(pt.month.slice(-2)+'月'):pt.date.slice(5))}</text>`).join('')}</g></svg></div>`
}
function mapSvg(regions, field = 'students', id = 'map') {
  const paths = MAP_PATHS.map(d=>`<path d="${d}"/>`).join('')
  const all = [...(regions||[])].filter(r => REGION_ANCHORS[r.code] && r[field] > 0).sort((a,b)=>b[field]-a[field])
  const visible = all.slice(0,14), peak = Math.max(...visible.map(r=>r[field]),1)
  const markers = visible.map((row,i) => {const pos=REGION_ANCHORS[row.code], r=4+Math.sqrt(row[field]/peak)*6, colour=i===0?'#ffac72':i<4?'#a27cff':'#2df0ec';return `<g class="ix-map-marker" data-region="${row.code}" role="button" tabindex="0" aria-label="${e(row.name)} ${n(row[field])}${field==='students'?'人':'家'}" transform="translate(${pos.x},${pos.y})" style="--ix-pin:${colour}"><circle r="${r*2.3}" fill="url(#ix-pin-${id}-${i%3})"/><circle class="ix-map-ripple" r="${r+5}" fill="none" stroke="${colour}" stroke-opacity=".6"/><circle r="${r}" fill="${colour}" fill-opacity=".18" stroke="${colour}"/><circle r="3" fill="#dafaff"/><title>${e(row.name)}：实习学生 ${n(row.students)} 人，关联企业 ${n(row.enterprises)} 家</title></g>`}).join('')
  const connections = visible.slice(1,9).map(r=>{const a=REGION_ANCHORS[r.code],b=REGION_ANCHORS[visible[0]?.code];return b?`<path d="M${a.x} ${a.y}Q${(a.x+b.x)/2-25} ${(a.y+b.y)/2-50} ${b.x} ${b.y}"/>`:''}).join('')
  return `<svg class="ix-geo-map" viewBox="0 0 600 360" role="img" aria-label="企业省域业务分布示意；不表示学生实时位置"><defs><linearGradient id="ix-land-${id}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#063c6c"/><stop offset="1" stop-color="#03182b"/></linearGradient><pattern id="ix-net-${id}" width="22" height="18" patternUnits="userSpaceOnUse"><path d="M0 0H22V18" fill="none" stroke="#1783ab" stroke-opacity=".18" stroke-width=".7"/></pattern>${['#41ebff','#968aff','#4ce7cf'].map((c,i)=>`<radialGradient id="ix-pin-${id}-${i}"><stop stop-color="${c}" stop-opacity=".65"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></radialGradient>`).join('')}</defs><g transform="translate(0,8)" fill="#032241" stroke="#0a4876" stroke-width="1.5">${paths}</g><g fill="url(#ix-land-${id})" stroke="#1977bb" stroke-width="1.5" class="ix-map-land">${paths}</g><g fill="url(#ix-net-${id})" stroke="none">${paths}</g><g fill="none" stroke="#318df4" stroke-opacity=".3" stroke-width="1.2">${connections}</g>${markers}<text x="576" y="350" text-anchor="end" fill="#6794b8" font-size="13">省域示意 · 非实时定位</text></svg>`
}
function geoRank(extra, field, id) {
  if (!extra.available) return '<div class="ix-geo-rank"><strong>TOP5 省域</strong><p class="ix-empty">待聚合接口返回<small>未连接不填 0</small></p></div>'
  const rows = [...extra.regions].sort((a,b)=>b[field]-a[field]).filter(r=>r[field]>0).slice(0,5)
  return `<div class="ix-geo-rank"><strong>TOP5 省域 · ${field==='students'?'人数':'企业'}</strong>${rows.map((row,i)=>`<button type="button" data-region="${e(row.code)}"><b class="ix-rank r${i}">${i+1}</b><span>${e(REGION_ANCHORS[row.code]?.name||row.name)}</span><em>${n(row[field])}</em></button>`).join('')}${!rows.length?'<p class="ix-empty ix-empty-sm">暂无已定位数据</p>':''}<small>${id==='companies'?'本批关联企业，不是全校企业库':'依据实习关联企业省域统计'}</small></div>`
}
function enterprisePanel(model) {
  const X=model.extra
  return `<div class="ix-geo-totals"><div>${icon('building')}<span>本批关联企业<strong>${n(X.totals.enterprises)}<small> 家</small></strong></span></div><div>${icon('briefcase')}<span>本批关联岗位<strong>${n(X.totals.positions)}<small> 个</small></strong></span></div></div><div class="ix-geo-body">${mapSvg(X.regions,'enterprises','companies')}${geoRank(X,'enterprises','companies')}${!X.available?'<div class="ix-map-wait">省域底图已就绪 · 等待真实聚合</div>':''}</div><div class="ix-map-foot"><span><i class="ix-cyan-dot"></i>标记显示最多14个主要省域</span><span>企业地区未识别：<b>${n(X.geography?.unlocatedEnterprises)}</b> 家</span></div>`
}
function majorPanel(model) {
  const X=model.extra, rows=X.majors, max=Math.max(...rows.map(r=>r.students),1)
  return `<div class="ix-rank-sub"><span class="is-active">实习人数 TOP8</span><small>专业组织口径 · 仅当前批次</small></div><div class="ix-major-head"><span>排名 / 专业名称</span><span>实习人数</span><span>关联企业</span></div><div class="ix-major-list">${rows.map((r,i)=>`<button type="button" data-major="${i}" title="${e(r.name)}"><span><b class="ix-rank r${i}">${i+1}</b><em>${e(r.name)}</em></span><div><i><b style="width:${r.students/max*100}%"></b></i><strong>${n(r.students)}</strong></div><small>${n(r.enterprises)} 家</small></button>`).join('')}</div>${!rows.length?`<div class="ix-empty">${X.available?'本批暂无实习学生':'等待专业聚合回执'}<small>不从前端分页列表拼排行</small></div>`:''}<div class="ix-ranking-note">其余专业 ${n(X.majorOther)} 人 · 点击专业查看当前聚合口径</div>`
}
function regionPanel(model, ui) {
  const X=model.extra, field=ui.regionMetric||'students', known=X.available?X.regions.reduce((s,r)=>s+r.students,0):null
  return `<div class="ix-region-tabs"><button type="button" data-region-tab="students" class="${field==='students'?'is-active':''}">学生分布</button><button type="button" data-region-tab="enterprises" class="${field==='enterprises'?'is-active':''}">企业分布</button><span>同一批次 · 两种观察维度</span></div><div class="ix-region-body">${mapSvg(X.regions,field,'students')}${geoRank(X,field,'students')}</div><div class="ix-region-footer"><div><span>已识别地区学生</span><strong>${n(known)}<small> 人</small></strong></div><div><span>地区待完善学生</span><strong>${n(X.geography?.unlocatedStudents)}<small> 人</small></strong></div><div><span>覆盖省级地区</span><strong>${X.available?n(X.regions.filter(r=>r.students>0).length):'—'}<small> 个</small></strong></div></div>`
}
function hero(model) {
  const positions=[[50,13],[76,23],[90,44],[86,65],[67,85],[33,85],[13,64],[10,42],[25,22]]
  return `<section class="ix-hero" aria-label="实习全过程业务入口"><div class="ix-hero-eyebrow">‹‹‹ 从实习到就业 · 全过程数字化管理 ›››</div>${CORE_SVG}<div class="ix-core-title"><span>实习</span><strong>运行中枢</strong><small>数据汇聚</small><small>协同联动</small><i>只读监管 · 真实业务</i></div>${FLOW.map(([label,hint,key,route,glyph],i)=>`<button class="ix-node" type="button" data-go="${e(route)}" style="--nx:${positions[i][0]}%;--ny:${positions[i][1]}%" title="${e(model.metrics[key].label)}：${metricValue(model.metrics[key])}；${e(hint)}">${icon(glyph)}<strong>${e(label)}</strong><small>${metricValue(model.metrics[key])}</small></button>`).join('')}<div class="ix-hero-footer">实践育人 · 精准管理 · 安全护航 · 成就未来</div></section>`
}
function kpis(model) {
  const X=model?.extra, T=X?.totals||{}
  const mentors=T.schoolMentors!==undefined&&T.enterpriseMentors!==undefined?T.schoolMentors+T.enterpriseMentors:null
  const rows=[
    ['实习学生总量',n(model?.total),'人','当前批次 · 授权范围','users','students'],
    ['本批关联企业',n(T.enterprises),'家','关联企业主档去重','building','enterprises'],
    ['校企导师关联',n(mentors),'个',X?.available?`校内 ${n(T.schoolMentors)} / 企业 ${n(T.enterpriseMentors)}`:'等待大屏聚合回执','users','guidance'],
    ['协议签署率',model?metricValue(model.metrics.agreementSignRate):'—','',model?metricHint(model.metrics.agreementSignRate):'等待统计回执','file',null,'agreementSignRate'],
    ['当前在岗学生',n(model?.onboard),'人','业务状态 · 非实时定位','briefcase','students'],
    ['待核实打卡异常',n(T.pendingExceptions),'条','待处理异常记录数','warning','exceptions'],
    ['近7日巡访记录',n(T.visits7d),'次','按巡访时间 · 含今日','pin','guidance'],
    ['就业台账落实率',model?metricValue(model.metrics.employmentRate):'—','',model?metricHint(model.metrics.employmentRate):'等待统计回执','bars',null,'employmentRate']
  ]
  return `<div class="ix-kpis">${rows.map(([label,value,unit,hint,glyph,route,metric])=>`<button type="button" class="ix-kpi ${glyph==='warning'?'ix-risk-kpi':''}" ${metric?`data-metric="${metric}"`:`data-go="${route}"`} title="${e(hint)}"><div class="ix-kpi-icon">${icon(glyph)}</div><div><span>${e(label)}</span><strong>${e(value)}<small>${e(unit)}</small></strong><em>${e(hint)}</em></div></button>`).join('')}</div>`
}
function riskPanel(model) {
  const X=model.extra, labels={HIGH:'高风险',MEDIUM:'中风险',LOW:'低风险',UNKNOWN:'等级待核实'}
  return `<div class="ix-risk-grid"><div class="ix-risk-left">${donut(X.riskLevels,n(X.totals.openRisks),'开放风险单','ix-risk-donut')}<div class="ix-risk-levels">${X.riskLevels.map((r,i)=>`<div><i class="s${i}"></i><span>${labels[r.key]}</span><strong>${n(r.value)}</strong></div>`).join('')}${!X.available?'<small>风险分布待返回</small>':''}</div></div>${sparkChart(X.riskNewDaily,{title:'近7日新增风险 · 条',purple:true,id:'risk'})}</div><p class="ix-note">开放风险与新增风险为不同口径；未把新增量当成历史存量。</p>`
}
function studentPanel(model) {
  const rows=model.states.length?model.states.map(s=>({label:s.label,value:s.value})):[]
  return `<div class="ix-students-grid"><div class="ix-students-left">${donut(rows,n(model.total),'本批实习学生')}<div class="ix-state-legend">${rows.map((s,i)=>`<div><i class="s${i}"></i><span>${e(s.label)}</span><strong>${n(s.value)}</strong></div>`).join('')}${!rows.length?'<small>状态分布待核实</small>':''}</div></div>${sparkChart(model.extra.attendanceDaily,{title:'近7日打卡记录 · 条',second:true,id:'attendance'})}</div><p class="ix-note">${e(model.stateIssue||'图表是打卡记录量，不是实时在岗率；合规沿用原统计定义。')}</p>`
}
function outcomePanel(model) {
  const m=model.metrics.employmentRate, rows=m.state==='ok'?[{value:m.numerator},{value:m.denominator-m.numerator}]:[]
  return `<div class="ix-outcome-grid"><div class="ix-outcome-left"><button type="button" class="ix-outcome-ring" data-metric="employmentRate">${donut(rows,metricValue(m),'台账落实率','ix-purple')}</button><div class="ix-outcome-facts"><div><span>已落实去向</span><b>${n(m.numerator)} 人</b></div><div><span>考核/归档队列</span><b>${n(m.denominator)} 人</b></div><button type="button" data-metric="scorePublishRate">成绩发布 <b>${metricValue(model.metrics.scorePublishRate)}</b></button><button type="button" data-metric="archiveRate">归档完成 <b>${metricValue(model.metrics.archiveRate)}</b></button></div></div>${sparkChart(model.extra.employmentMonths,{title:'已核验签约月份 · 人',monthly:true,purple:true,id:'employment'})}</div><p class="ix-note">台账落实含升学等去向，不等于实习企业留用；右图不是历史落实率。</p>`
}
function workPanel(model) {
  if (!model.dashboardAvailable) return '<div class="ix-empty ix-empty-sm">无工作台权限或待办未返回<small>统计可见不代表待办为零</small></div>'
  if (!model.work.length) return '<div class="ix-empty ix-empty-sm">当前权限下暂无优先待办</div>'
  return `<div class="ix-work-head"><span>事项类型</span><span>对象尾号</span><span>原业务办理</span></div><div class="ix-work-list">${model.work.slice(0,4).map((w,i)=>`<button type="button" data-work="${i}" ${!w.route?'disabled':''}><span><i class="${w.tone==='danger'?'ix-red-dot':'ix-amber-dot'}"></i>${e(w.label)}</span><small>···${e(w.objectId.slice(-4))}</small><em>${w.route?'进入办理 ›':'无查看权限'}</em></button>`).join('')}</div>`
}
function main(model, ui) {
  return `<main class="ix-main"><div class="ix-left">${panel('企业分布与岗位热力',enterprisePanel(model),'enterprises','ix-enterprise-panel')}${panel('专业对比排行',majorPanel(model),'stats','ix-major-panel')}</div><div class="ix-center">${hero(model)}${panel('区域分布',regionPanel(model,ui),'stats','ix-region-panel')}</div><div class="ix-right">${panel('风险雷达',riskPanel(model),'risks','ix-risk-panel')}${panel('学生动态与出勤',studentPanel(model),'attendance','ix-student-panel')}${panel('成果与转化分析',outcomePanel(model),'stats','ix-outcome-panel')}${panel('优先告警 / 任务清单',workPanel(model),'stats','ix-work-panel')}</div></main>`
}

function reason(status) { return ({ 'no-batch': '选择批次', loading: '加载真实统计', denied: '访问受限', error: '数据服务不可用' })[status] || '等待数据' }

/** Same DOM/SVG renderer is used by Vue and the single-file offline acceptance preview. */
export function mountScreen(host, options) {
  if (!(host instanceof HTMLElement)) throw new TypeError('mountScreen requires a DOM host')
  const ui = { regionMetric: 'students' }
  let context = { ...options.context }, state = { status: 'loading' }, model = null, stale = '', destroyed = false
  let auto = false, refreshTimer = null, toastTimer = null, busy = false, lastRequestAt = 0
  const oldOverflow = document.body.style.overflow, focusedBefore = document.activeElement
  const inertBackup = [...document.body.children].filter(el => !el.contains(host)).map(el => [el, el.inert])
  inertBackup.forEach(([el]) => { el.inert = true })
  document.body.style.overflow = 'hidden'
  host.classList.add('ix-root'); host.setAttribute('role', 'dialog'); host.setAttribute('aria-modal', 'true')
  host.setAttribute('aria-label', '岗位实习智慧监管指挥大屏'); host.tabIndex = -1

  function setToast(text) { const box = host.querySelector('.ix-toast'); if (box) { box.textContent = text; box.classList.add('is-visible'); clearTimeout(toastTimer); toastTimer = setTimeout(() => { if (!destroyed) box.classList.remove('is-visible') }, 4000) } }
  function resize() { const scale = Math.min(host.clientWidth / 1920, host.clientHeight / 1080); host.style.setProperty('--ix-scale', String(scale)) }
  function clock() {
    const now = new Date(options.clockNow?.() || Date.now()), time = host.querySelector('[data-clock]'), date = host.querySelector('[data-date]')
    if (time) time.textContent = now.toLocaleTimeString('zh-CN', { hour12: false })
    if (date) date.textContent = now.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long' })
  }
  function paint() {
    if (destroyed) return
    const active = document.activeElement, focusAction = host.contains(active) ? active?.getAttribute('data-action') : null
    const scope = model?.scopeMode === 'ADMIN_TENANT' ? '本校授权范围' : context.scopeName || '按后端数据范围'
    const statusText = stale ? '更新失败 · 保留上次快照' : model?.issues.length ? '部分数据不可用' : model ? '统计快照已载入' : reason(state.status)
    const content = model ? main(model, ui) : `<main class="ix-data-state"><div class="ix-state-symbol">${icon(state.status === 'denied' ? 'shield' : 'ring')}</div><h2>${reason(state.status)}</h2><p>${e(state.message || '正在读取当前批次的真实统计接口，请稍候')}</p>${state.status === 'loading' ? '<div class="ix-loading-line"></div>' : '<button type="button" data-action="refresh">重新核验</button>'}<small>未获得有效数据前，不显示合成数字，也不会把接口错误显示成 0。</small></main>`
    host.innerHTML = `<div class="ix-stage"><div class="ix-top-traces"></div><header class="ix-header"><div class="ix-brand">${icon('cap')}<div><strong title="${e(context.schoolName)}">${e(context.schoolName || '学校品牌待返回')}</strong><small>厚德强技 知行合一</small></div></div><div class="ix-title"><h1>岗位实习智慧监管指挥大屏</h1><p>过程管控 · 安全预警 · 校企协同 · 就业转化</p></div><div class="ix-clock"><small data-date></small><strong data-clock></strong><span>统计展示 · 非实时定位</span></div></header>
    ${kpis(model)}<div class="ix-controls"><div class="ix-context"><span class="ix-online ${stale || model?.issues.length ? 'is-warn' : ''}"></span><b>${e(statusText)}</b><span class="ix-divider"></span><span>批次</span><select data-action="batch" aria-label="选择实习批次"><option value="">请选择批次</option>${(context.batches || []).map(b => `<option value="${e(b.id)}" ${String(b.id) === String(context.batchId) ? 'selected' : ''}>${e(b.batchName || b.name || b.id)}</option>`).join('')}</select><span class="ix-scope" title="${e(scope)}">${e(scope)}</span></div><div class="ix-tools"><button data-action="refresh" type="button" ${busy ? 'disabled' : ''}>${busy ? '读取中…' : '刷新'}</button><button data-action="auto" type="button" aria-pressed="${auto}">${auto ? '自动刷新：5分钟' : '自动刷新：关闭'}</button><button data-go="stats" type="button">统计与导出</button><button data-action="definitions" type="button">指标口径</button><button data-action="fullscreen" type="button">${document.fullscreenElement === host ? '退出全屏' : '全屏'}</button><button data-action="close" type="button" aria-label="关闭监管大屏">关闭 ×</button></div></div>
    ${content}<footer class="ix-footer"><span>${e(context.previewLabel || '只读统计 · 原接口同源 · 办理仍在原业务页面')}</span><span class="ix-footer-middle" title="${e(stale || model?.issues.join('；') || '')}">${e(stale || model?.issues.join('；') || (model ? `生成于 ${model.generatedAt || '接口未返回时间'} · ${model.metricVersion}` : '未连接有效统计回执'))}</span><span>数据范围与批次一致 · 不展示学生姓名</span></footer><div class="ix-bottom-traces"></div><div class="ix-toast" role="status"></div></div>`
    host.querySelectorAll('[data-go]').forEach(button => { if (!routeFor(button.dataset.go, context)) { button.disabled = true; button.title = '当前身份无该台账查看权限，或尚未选择批次' } })
    resize(); clock()
    if (focusAction) host.querySelector(`[data-action="${CSS.escape(focusAction)}"]`)?.focus({ preventScroll: true })
  }
  function schedule() {
    clearTimeout(refreshTimer)
    if (auto && !destroyed && !document.hidden && state.status !== 'denied') refreshTimer = setTimeout(() => { if (host.querySelector('dialog[open]')) { schedule(); return }; refresh() }, 300000)
  }
  const coordinator = createCoordinator(ctx => readSnapshot(options.loaders, ctx), result => {
    busy = false; state = result
    if (result.status === 'ready') { model = result.model; stale = '' }
    else if (result.status === 'error' && model) { stale = `${result.message}；快照时间 ${model.generatedAt || '未知'}` }
    else { model = null; stale = '' }
    if (result.status === 'denied') auto = false
    paint(); schedule()
  })
  function refresh() {
    if (destroyed || busy) return
    busy = true; lastRequestAt = Date.now()
    if (!model) state = { status: 'loading' }
    paint(); return coordinator.run({ ...context })
  }
  function navigate(url) { if (url) options.onNavigate?.(url); else setToast('当前权限或批次不允许打开此台账') }
  function dialog(metricKey) {
    if (!model) { setToast('获得统计回执后可查看口径'); return }
    const metric = model.metrics[metricKey]
    const content = metric ? `<h2>${e(metric.label)}</h2><div class="ix-dialog-value">${metricValue(metric)}</div><dl><div><dt>分子 / 分母</dt><dd>${n(metric.numerator)} / ${n(metric.denominator)}</dd></div><div><dt>状态</dt><dd>${e(({ok:'有效统计',empty:'无统计分母',anomaly:'口径异常',missing:'缺少有效数据'})[metric.state] || metric.state)}</dd></div><div><dt>指标键</dt><dd>${e(metric.key)}</dd></div><div><dt>统计版本</dt><dd>${e(model.metricVersion)}</dd></div></dl><p>${e(metric.note)}</p>${metric.definitionIssue ? '<strong class="ix-definition-warning">此项分母说明存在源码不一致，不能视为已经完成口径验收。</strong>' : ''}` : `<h2>大屏统计口径</h2><p>所有数值来自当前批次的原有统计与工作台接口；分母为零显示“—”，数值异常不强行截成 100%。</p><p>巡访覆盖率不是巡访任务完成率；周报覆盖率不是按应交周次计算的提交率；就业转化不是企业留用率。</p><p>地图按企业主档省域聚合，固定标记不代表企业或学生位置。校企导师是两种关联ID分别去重后相加，不是跨系统自然人去重总数。风险曲线为每日新增风险，签约曲线为当前已核验台账的签约月份分布，均不是历史比率。</p><p>姓名、学号、电话、详细地址不会渲染到投屏。待办是最多8条的优先对象，本屏最多显示4条，并非全量任务清单。</p><p>大屏聚合 ${e(model.extra.snapshotAt || '未返回')}；时区 ${e(model.extra.timezone || '待返回')}。地图中地区待完善人数单列，不伪造省份；排行只展示人数前8专业。</p><p>当前批次：${e(model.batchName)}；统计生成时间：${e(model.generatedAt)}。不同只读接口不是数据库原子快照。</p>`
    const el = document.createElement('dialog'); el.className = 'ix-dialog'; el.setAttribute('aria-label', metric ? metric.label : '大屏统计口径'); el.innerHTML = `${content}<button type="button" data-dialog-close>关闭说明</button>`
    host.append(el); el.querySelector('button').addEventListener('click', () => el.close()); el.addEventListener('close', () => el.remove(), { once: true }); el.showModal()
  }
  function aggregateDialog(kind, key) {
    if (!model) return
    const row = kind === 'region' ? model.extra.regions.find(r=>r.code===key) : model.extra.majors[Number(key)]
    if (!row) return
    const el=document.createElement('dialog'); el.className='ix-dialog'; el.setAttribute('aria-label',row.name)
    el.innerHTML=`<h2>${e(row.name)}</h2><dl><div><dt>本批实习学生</dt><dd>${n(row.students)} 人</dd></div><div><dt>本批关联企业</dt><dd>${n(row.enterprises)} 家</dd></div><div><dt>聚合生成时间</dt><dd>${e(model.extra.snapshotAt)}</dd></div></dl><p>${kind==='region'?'按企业主档省域字段归组，省域标记是固定示意点，不是实时定位。':'优先采用学生直挂专业，缺失时按班级专业兜底。这里只统计当前批次与当前授权范围。'}</p><p>本弹窗是聚合说明，不冒充已按该地区/专业筛选的业务台账。</p><button type="button">关闭说明</button>`
    host.append(el);el.querySelector('button').addEventListener('click',()=>el.close());el.addEventListener('close',()=>el.remove(),{once:true});el.showModal()
  }
  async function onClick(event) {
    const button = event.target.closest('button,[data-region]'); if (!button || button.disabled || !host.contains(button)) return
    if (button.dataset.region) { aggregateDialog('region', button.dataset.region); return }
    if (button.dataset.major !== undefined) { aggregateDialog('major', button.dataset.major); return }
    if (button.dataset.regionTab) { ui.regionMetric = button.dataset.regionTab; paint(); host.querySelector(`[data-region-tab="${ui.regionMetric}"]`)?.focus({ preventScroll: true }); return }
    if (button.dataset.metric) { dialog(button.dataset.metric); return }
    if (button.dataset.go) { navigate(routeFor(button.dataset.go, context)); return }
    if (button.dataset.work !== undefined) { navigate(model?.work[Number(button.dataset.work)]?.route); return }
    switch (button.dataset.action) {
      case 'refresh': refresh(); break
      case 'auto': auto = !auto; paint(); schedule(); break
      case 'definitions': dialog(); break
      case 'close': options.onClose?.(); break
      case 'fullscreen':
        try { if (document.fullscreenElement === host) await document.exitFullscreen(); else if (host.requestFullscreen) await host.requestFullscreen(); else setToast('此浏览器不支持全屏，请使用 F11') }
        catch { setToast('浏览器未允许全屏，页面仍可正常使用') }
        break
    }
  }
  function onChange(event) { if (event.target.matches('[data-action="batch"]')) options.onBatchChange?.(event.target.value) }
  function onKey(event) {
    if (host.querySelector('dialog[open]')) return
    if (['Enter',' '].includes(event.key) && event.target.matches('[data-region]')) { event.preventDefault(); aggregateDialog('region',event.target.dataset.region); return }
    if (event.key === 'Escape' && document.fullscreenElement !== host) { event.preventDefault(); options.onClose?.(); return }
    if (event.key !== 'Tab') return
    const focusable = [...host.querySelectorAll('button:not(:disabled),select:not(:disabled),[data-region][tabindex]')].filter(el => el.getClientRects().length)
    const first = focusable[0], last = focusable.at(-1)
    if (event.shiftKey && (document.activeElement === first || document.activeElement === host)) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }
  function visible() { if (document.hidden) clearTimeout(refreshTimer); else if (auto && Date.now() - lastRequestAt >= 300000) refresh(); else schedule() }
  function fullscreenChanged() { const el = host.querySelector('[data-action="fullscreen"]'); if (el) el.textContent = document.fullscreenElement === host ? '退出全屏' : '全屏'; resize() }
  host.addEventListener('click', onClick); host.addEventListener('change', onChange); host.addEventListener('keydown', onKey)
  document.addEventListener('visibilitychange', visible); document.addEventListener('fullscreenchange', fullscreenChanged)
  const observer = new ResizeObserver(resize); observer.observe(host)
  const clockTimer = setInterval(clock, 1000)
  paint(); host.focus({ preventScroll: true }); refresh()
  return {
    refresh,
    updateContext(next) {
      coordinator.invalidate(); context = { ...next }; model = null; stale = ''; busy = false
      clearTimeout(refreshTimer); host.querySelector('dialog[open]')?.close(); refresh()
    },
    destroy() {
      destroyed = true; coordinator.destroy(); observer.disconnect(); clearInterval(clockTimer); clearTimeout(refreshTimer); clearTimeout(toastTimer)
      host.removeEventListener('click', onClick); host.removeEventListener('change', onChange); host.removeEventListener('keydown', onKey)
      document.removeEventListener('visibilitychange', visible); document.removeEventListener('fullscreenchange', fullscreenChanged)
      if (document.fullscreenElement === host) document.exitFullscreen().catch(() => {})
      host.innerHTML = ''; document.body.style.overflow = oldOverflow
      inertBackup.forEach(([el, old]) => { if (el.isConnected) el.inert = old })
      if (focusedBefore instanceof HTMLElement && focusedBefore.isConnected) focusedBefore.focus({ preventScroll: true })
    }
  }
}
