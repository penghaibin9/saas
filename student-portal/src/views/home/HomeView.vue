<template>
  <div class="sp-page sp-home-v5">
    <StateBlock v-if="loading" type="loading" text="正在加载工作台…" />
    <template v-else>
      <section class="home-hero">
        <div class="home-hero__orb home-hero__orb--one" />
        <div class="home-hero__orb home-hero__orb--two" />
        <div class="home-hero__top">
          <div class="home-hero__identity">
            <div class="home-hero__eyebrow">MY STUDENT JOURNEY</div>
            <h1>{{ greeting }}，{{ studentName }}</h1>
            <p>今天先完成最重要的一件事，其他事项已按影响程度和截止时间排好顺序。</p>
            <div class="home-hero__chips">
              <span v-for="c in identity" :key="c.label" class="home-chip"><small>{{ c.label }}</small><b>{{ c.value }}</b></span>
            </div>
          </div>
          <div class="home-stage">
            <span>当前成长阶段</span>
            <strong>{{ stageLabel }}</strong>
            <div class="home-stage__bar"><i /></div>
            <small>{{ domains.length ? `${domains.filter((d) => d.hasData).length} 个环节已有业务数据` : '等待学校发布阶段信息' }}</small>
          </div>
        </div>

        <div class="home-focus" :class="{ 'is-empty': !focusItem }">
          <span class="home-focus__icon">{{ focusItem ? '!' : '✓' }}</span>
          <div class="home-focus__body">
            <strong>{{ focusItem ? focusTitle : '今天暂无紧急事项' }}</strong>
            <small>{{ focusItem ? focusMeta : '可以查看课表、消息或继续关注成长进度。' }}</small>
          </div>
          <button v-if="focusItem && ctaModule" type="button" class="home-focus__button" @click="goTarget(ctaModule)">{{ ctaText }}</button>
        </div>
      </section>

      <section class="home-metrics">
        <article v-for="m in metrics" :key="m.title" class="home-metric">
          <span>{{ m.title }}</span>
          <div><strong :style="{ color: m.color }">{{ m.value }}</strong><em>{{ m.unit }}</em></div>
          <small>{{ m.sub }}</small>
        </article>
      </section>

      <section class="home-card home-journey">
        <div class="home-card__head">
          <div><h2>我的成长航线</h2><p>跨模块统一查看当前阶段和下一步。</p></div>
          <span>{{ journey.filter((item) => item.done).length }} / {{ journey.length }} 已完成</span>
        </div>
        <div class="home-journey__track">
          <button v-for="(item, index) in journey" :key="item.key" type="button" class="home-journey__item"
                  :class="{ 'is-done': item.done, 'is-current': item.current }" @click="goTarget(item.key)">
            <span class="home-journey__node">{{ item.done ? '✓' : index + 1 }}</span>
            <strong>{{ item.label }}</strong>
            <small>{{ item.state }}</small>
          </button>
        </div>
      </section>

      <div class="home-grid">
        <section class="home-card home-todos">
          <div class="home-card__head">
            <div><h2>我的下一步</h2><p>等我提交、确认、补充或整改的真实事项。</p></div>
            <span>{{ todos.length }} 项待办</span>
          </div>
          <StateBlock v-if="!todos.length" type="empty" text="暂无待办，一切就绪" />
          <div v-else class="home-todo-list">
            <button v-for="(t, index) in todos" :key="t.id || `${t.title}-${index}`" type="button" class="home-todo" @click="goTarget(t.route || t.link || t.module)">
              <span class="home-todo__index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="home-todo__main">
                <b>{{ t.title }}</b>
                <small>{{ modName(t.module) }} · {{ t.dueAt ? `截止 ${fmt(t.dueAt)}` : '待办理' }}</small>
              </span>
              <span class="home-todo__go">去处理
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6" /></svg>
              </span>
            </button>
          </div>
        </section>

        <div class="home-side">
          <section class="home-card">
            <div class="home-card__head">
              <div><h2>消息速览</h2><p>重要通知与业务结果。</p></div>
              <button type="button" class="home-link" @click="goMsg">全部消息</button>
            </div>
            <StateBlock v-if="!msgs.length" type="empty" text="暂无新消息" />
            <div v-else class="home-message-list">
              <button v-for="m in msgs" :key="m.id" type="button" class="home-message" @click="goTarget(m.link || m.module)">
                <span class="home-message__dot" :class="{ 'is-read': m.read }" />
                <span class="home-message__main">
                  <b :class="{ 'is-read': m.read }">{{ messageTitle(m.title) }}</b>
                  <small>{{ modName(m.module) }} · {{ fmt(m.time) }}</small>
                </span>
              </button>
            </div>
          </section>

          <section class="home-card">
            <div class="home-card__head">
              <div><h2>环节状态</h2><p>来自各业务域的真实状态。</p></div>
            </div>
            <StateBlock v-if="!domains.length" type="empty" text="暂无环节信息" />
            <div v-else class="home-domain-list">
              <div v-for="d in domains" :key="d.key" class="home-domain">
                <span class="home-domain__dot" :class="{ 'is-on': d.hasData }" />
                <span>{{ d.label }}</span>
                <StatusTag :text="d.hasData ? statusLabel(d.status) : '状态待同步'" :tone="d.hasData ? 'primary' : 'default'" />
              </div>
            </div>
          </section>
        </div>
      </div>

      <section class="home-card home-quick-card">
        <div class="home-card__head">
          <div><h2>快捷服务</h2><p>直接进入高频模块，不必逐层寻找。</p></div>
        </div>
        <div class="home-quick">
          <button v-for="q in quick" :key="q.key" type="button" class="home-quick__item" @click="goTarget(q.key)">
            <span class="home-quick__icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="q.d1" /><path :d="q.d2" /></svg>
            </span>
            <span><b>{{ q.label }}</b><small>进入模块</small></span>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { portalApi } from '../../services/portalApi'
import { localizeStatusSuffixText } from '../../services/visibleEnumLocalization'
import { MODULES, moduleByKey } from '../../platform/moduleRegistry'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'

const router = useRouter()
const session = useSessionStore()
const loading = ref(true)
const home = ref({})
const audit = ref({})
const msgs = ref([])

const studentName = computed(() => home.value.student?.name || session.user?.realName || '同学')
const stageLabel = computed(() => home.value.stage?.label || '在校')
const todos = computed(() => home.value.todos || [])
const alerts = computed(() => home.value.alerts || [])
const domains = computed(() => home.value.domains || [])
const topAlert = computed(() => alerts.value[0] || null)
const focusItem = computed(() => topAlert.value || todos.value[0] || null)
const focusTitle = computed(() => focusItem.value?.title || '')
const focusMeta = computed(() => {
  const item = focusItem.value || {}
  const parts = [modName(item.module || item.domain)]
  if (item.dueAt) parts.push(`截止 ${fmt(item.dueAt)}`)
  return parts.filter(Boolean).join(' · ') || '请及时处理'
})

const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 11 ? '上午好' : h < 13 ? '中午好' : h < 18 ? '下午好' : '晚上好'
})

const identity = computed(() => {
  const s = home.value.student || {}
  return [
    { label: '学号', value: s.studentNo || '—' },
    { label: '年级', value: s.grade || '—' },
    { label: '班级', value: s.className || '—' }
  ].filter((c) => c.value !== '—')
})

const metrics = computed(() => {
  const c = audit.value.credits || {}
  return [
    { title: '已修学分', value: c.obtainedCredits ?? 0, unit: '', sub: `培养要求 ${c.requiredCredits ?? '—'}`, color: 'var(--t1)' },
    { title: '平均绩点 GPA', value: c.gpa ?? '—', unit: '', sub: '截至最新学期', color: 'var(--t1)' },
    { title: '待办事项', value: todos.value.length, unit: '项', sub: '待我处理', color: todos.value.length ? 'var(--pri-text, var(--pri))' : 'var(--t1)' },
    { title: '预警提醒', value: alerts.value.length, unit: '项', sub: '需跟进', color: alerts.value.length ? 'var(--danger-fg)' : 'var(--ok-fg)' }
  ]
})

const ctaModule = computed(() => topAlert.value?.route || topAlert.value?.domain || todos.value[0]?.route || todos.value[0]?.module || null)
const ctaText = computed(() => (topAlert.value ? '立即处理' : todos.value.length ? '去办理' : ''))
const quick = computed(() => MODULES.filter((m) => m.key !== 'dashboard').slice(0, 8))

const STATUS_LABELS = { CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约', WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验', UNEMPLOYED: '暂未就业', EMPLOYED: '已就业', JOB_SEEKING: '求职中', NOT_STARTED: '尚未开始' }
const DONE_STATES = new Set(['DONE', 'APPROVED', 'VERIFIED', 'CHECKED_IN', 'SIGNED'])
const journey = computed(() => {
  const defs = [
    { key: 'orientation', aliases: ['orientation'], label: '迎新入学' },
    { key: 'academic', aliases: ['academic', 'academic-affairs'], label: '学习生活' },
    { key: 'campusService', aliases: ['campusService', 'campus-service', 'student-affairs'], label: '成长事务' },
    { key: 'internship', aliases: ['internship'], label: '岗位实习' },
    { key: 'graduation', aliases: ['graduation'], label: '毕业设计' },
    { key: 'employment', aliases: ['employment'], label: '就业离校' }
  ]
  return defs.map((def) => {
    const domain = domains.value.find((item) => def.aliases.includes(item.key) || def.aliases.includes(item.domain)) || {}
    const done = !!domain.hasData && DONE_STATES.has(String(domain.status || '').toUpperCase())
    const current = !!domain.hasData && !done
    return { ...def, done, current, state: domain.hasData ? statusLabel(domain.status) : '状态待同步' }
  })
})

function statusLabel(s) {
  const raw = String(s || '').trim()
  if (!raw) return '状态待确认'
  const key = raw.toUpperCase()
  if (STATUS_LABELS[key]) return STATUS_LABELS[key]
  return /^[A-Z0-9_]+$/.test(raw) ? '状态待确认' : raw
}
function messageTitle(value) { return localizeStatusSuffixText(value || '系统通知') }
function modName(key) { return moduleByKey(key)?.title || (String(key || '').includes('academic') ? '教务学业' : key ? '系统' : '') }
function fmt(t) { return t ? String(t).replace('T', ' ').slice(5, 16) : '' }
function goTarget(target) {
  const raw = String(target || 'home').trim()
  if (raw.startsWith('/')) {
    router.push(raw)
    return
  }
  const mod = MODULES.find((m) => m.key === raw || m.path === raw)
  router.push('/' + (mod ? mod.path : raw.replace(/^\/+/, '')))
}
function goMsg() { router.push('/messages') }

async function load() {
  loading.value = true
  try {
    const [h, a, m] = await Promise.all([
      portalApi.homeOverview().catch(() => ({})),
      portalApi.academicGraduationAudit().catch(() => ({})),
      portalApi.messagesInbox(1, 4).catch(() => ({}))
    ])
    home.value = h || {}
    audit.value = a || {}
    msgs.value = (m && m.list) ? m.list.slice(0, 4) : []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.sp-home-v5 { max-width:1480px; margin:0 auto; }
.home-hero { position:relative; overflow:hidden; padding:28px 30px; border-radius:26px; color:#fff; background:linear-gradient(118deg,color-mix(in srgb,var(--pri) 40%,#102d6d) 0%,var(--pri) 58%,color-mix(in srgb,var(--pri) 55%,#fff) 100%); box-shadow:0 20px 44px rgba(var(--sp-primary-rgb),.22); }
.home-hero__orb { position:absolute; border-radius:50%; border:52px solid rgba(255,255,255,.09); pointer-events:none; }
.home-hero__orb--one { width:330px; height:330px; right:-100px; top:-180px; }
.home-hero__orb--two { width:190px; height:190px; right:260px; bottom:-150px; border-width:34px; }
.home-hero__top { position:relative; z-index:1; display:flex; justify-content:space-between; gap:30px; }
.home-hero__identity { min-width:0; }
.home-hero__eyebrow { margin-bottom:8px; font-size:10px; letter-spacing:.14em; color:rgba(255,255,255,.65); }
.home-hero h1 { margin:0; font-size:28px; line-height:1.25; }
.home-hero p { margin:8px 0 0; color:rgba(255,255,255,.76); font-size:13px; }
.home-hero__chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:17px; }
.home-chip { min-height:31px; padding:0 10px; display:inline-flex; align-items:center; gap:6px; border:1px solid rgba(255,255,255,.14); border-radius:10px; background:rgba(255,255,255,.11); font-size:12px; }
.home-chip small { color:rgba(255,255,255,.65); }
.home-stage { width:250px; flex:none; padding:16px; border:1px solid rgba(255,255,255,.17); border-radius:18px; background:rgba(255,255,255,.12); }
.home-stage span,.home-stage small { display:block; color:rgba(255,255,255,.7); font-size:11.5px; }
.home-stage strong { display:block; margin-top:5px; font-size:16px; }
.home-stage__bar { height:7px; margin:15px 0 8px; overflow:hidden; border-radius:8px; background:rgba(255,255,255,.18); }
.home-stage__bar i { display:block; width:62%; height:100%; border-radius:8px; background:#fff; }
.home-focus { position:relative; z-index:1; margin-top:21px; padding:14px 15px; display:flex; align-items:center; gap:13px; border-radius:18px; background:#fff; color:var(--t1); box-shadow:0 13px 30px rgba(8,24,69,.17); }
.home-focus.is-empty { background:rgba(255,255,255,.94); }
.home-focus__icon { width:39px; height:39px; flex:none; border-radius:12px; display:grid; place-items:center; background:var(--danger-bg); color:var(--danger-fg); font-weight:850; }
.home-focus.is-empty .home-focus__icon { background:var(--ok-bg); color:var(--ok-fg); }
.home-focus__body { flex:1; min-width:0; }
.home-focus__body strong,.home-focus__body small { display:block; }
.home-focus__body strong { font-size:13.5px; }
.home-focus__body small { margin-top:4px; color:var(--t3); font-size:11.5px; }
.home-focus__button { min-height:37px; padding:0 14px; border:0; border-radius:11px; background:var(--pri); color:#fff; font-size:12px; font-weight:750; cursor:pointer; }
.home-metrics { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-top:16px; }
.home-metric { padding:18px; border:1px solid var(--line); border-radius:18px; background:#fff; box-shadow:0 5px 18px rgba(31,63,120,.045); }
.home-metric > span { color:var(--t3); font-size:12px; }
.home-metric div { margin:7px 0 3px; display:flex; align-items:baseline; gap:4px; }
.home-metric strong { font-size:27px; line-height:1; }
.home-metric em { color:var(--t3); font-size:13px; font-style:normal; }
.home-metric small { color:var(--t4); font-size:11.5px; }
.home-card { padding:19px 20px; border:1px solid var(--line); border-radius:20px; background:#fff; box-shadow:0 6px 22px rgba(31,63,120,.045); }
.home-card__head { margin-bottom:14px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.home-card__head h2 { margin:0; color:var(--t1); font-size:15.5px; }
.home-card__head p { margin:5px 0 0; color:var(--t3); font-size:11.5px; }
.home-card__head > span { color:var(--pri); font-size:11.5px; font-weight:700; white-space:nowrap; }
.home-journey { margin-top:16px; }
.home-journey__track { position:relative; display:grid; grid-template-columns:repeat(6,1fr); gap:8px; }
.home-journey__track::before { content:""; position:absolute; left:8%; right:8%; top:21px; height:2px; background:var(--line); }
.home-journey__item { all:unset; cursor:pointer; position:relative; z-index:1; min-width:0; display:flex; flex-direction:column; align-items:center; text-align:center; }
.home-journey__node { width:42px; height:42px; display:grid; place-items:center; border:4px solid #fff; border-radius:50%; background:#eef2f8; color:#667085; box-shadow:0 0 0 1px var(--line); font-size:12px; font-weight:800; }
.home-journey__item.is-current .home-journey__node { background:var(--pri); color:#fff; box-shadow:0 0 0 5px var(--pri-50); }
.home-journey__item.is-done .home-journey__node { background:var(--ok-fg); color:#fff; }
.home-journey__item strong { margin-top:9px; color:var(--t1); font-size:12.5px; }
.home-journey__item small { margin-top:3px; color:var(--t3); font-size:10.5px; }
.home-grid { display:grid; grid-template-columns:minmax(0,1.45fr) minmax(340px,.78fr); gap:16px; margin-top:16px; }
.home-side { display:flex; flex-direction:column; gap:16px; }
.home-todo-list { display:flex; flex-direction:column; }
.home-todo { all:unset; box-sizing:border-box; cursor:pointer; width:100%; padding:13px 0; display:grid; grid-template-columns:42px 1fr auto; align-items:center; gap:12px; border-top:1px solid var(--line2); }
.home-todo:first-child { border-top:0; }
.home-todo:hover .home-todo__go { background:var(--pri); color:#fff; }
.home-todo__index { width:38px; height:38px; display:grid; place-items:center; border-radius:12px; background:var(--pri-50); color:var(--pri); font-size:12px; font-weight:800; }
.home-todo__main { min-width:0; }
.home-todo__main b,.home-todo__main small { display:block; }
.home-todo__main b { overflow:hidden; color:var(--t1); font-size:13px; text-overflow:ellipsis; white-space:nowrap; }
.home-todo__main small { margin-top:4px; color:var(--t3); font-size:11.5px; }
.home-todo__go { min-height:32px; padding:0 10px; display:flex; align-items:center; gap:3px; border-radius:9px; background:var(--pri-50); color:var(--pri); font-size:11.5px; font-weight:700; transition:.15s; }
.home-link { all:unset; cursor:pointer; color:var(--pri); font-size:11.5px; font-weight:700; }
.home-message-list,.home-domain-list { display:flex; flex-direction:column; }
.home-message { all:unset; box-sizing:border-box; cursor:pointer; padding:11px 0; display:grid; grid-template-columns:10px 1fr; gap:10px; border-top:1px solid var(--line2); }
.home-message:first-child { border-top:0; }
.home-message__dot { width:7px; height:7px; margin-top:6px; border-radius:50%; background:var(--pri); }
.home-message__dot.is-read { background:#c9ced6; }
.home-message__main { min-width:0; }
.home-message__main b,.home-message__main small { display:block; }
.home-message__main b { overflow:hidden; color:var(--t1); font-size:12.5px; text-overflow:ellipsis; white-space:nowrap; }
.home-message__main b.is-read { font-weight:400; }
.home-message__main small { margin-top:4px; color:var(--t4); font-size:10.5px; }
.home-domain { min-height:39px; display:grid; grid-template-columns:10px 1fr auto; align-items:center; gap:9px; border-top:1px solid var(--line2); color:var(--t1); font-size:12.5px; }
.home-domain:first-child { border-top:0; }
.home-domain__dot { width:7px; height:7px; border-radius:50%; background:#c9ced6; }
.home-domain__dot.is-on { background:var(--pri); }
.home-quick-card { margin-top:16px; }
.home-quick { display:grid; grid-template-columns:repeat(8,1fr); gap:10px; }
.home-quick__item { all:unset; box-sizing:border-box; cursor:pointer; min-height:68px; padding:10px; display:flex; align-items:center; gap:9px; border:1px solid var(--line); border-radius:15px; background:#fff; }
.home-quick__item:hover { border-color:var(--pri-100); background:var(--pri-50); transform:translateY(-1px); }
.home-quick__icon { width:37px; height:37px; flex:none; display:grid; place-items:center; border-radius:11px; background:var(--pri-50); color:var(--pri); }
.home-quick__item b,.home-quick__item small { display:block; }
.home-quick__item b { color:var(--t1); font-size:11.5px; }
.home-quick__item small { margin-top:3px; color:var(--t4); font-size:9.5px; }
html[data-sp-theme='dark'] .home-metric,html[data-sp-theme='dark'] .home-card,html[data-sp-theme='dark'] .home-quick__item { background:#1b2231; }
@media(max-width:1280px){.home-grid{grid-template-columns:1fr}.home-side{display:grid;grid-template-columns:1fr 1fr}.home-quick{grid-template-columns:repeat(4,1fr)}}
@media(max-width:900px){.home-hero__top{display:block}.home-stage{width:100%;margin-top:18px}.home-metrics{grid-template-columns:repeat(2,1fr)}.home-journey__track{grid-template-columns:repeat(3,1fr);row-gap:18px}.home-journey__track::before{display:none}.home-side{grid-template-columns:1fr}.home-quick{grid-template-columns:repeat(2,1fr)}}
@media(max-width:620px){.home-hero{padding:22px 18px}.home-hero h1{font-size:23px}.home-focus{align-items:flex-start;flex-wrap:wrap}.home-focus__button{width:100%}.home-metrics{grid-template-columns:1fr}.home-journey__track{grid-template-columns:repeat(2,1fr)}}
</style>
