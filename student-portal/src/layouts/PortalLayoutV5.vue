<template>
  <div class="sp-shell" :class="shellClasses">
    <aside class="sp-aside">
      <div class="sp-brand">
        <span class="sp-brand__logo">
          <svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8.5 12 4.5l9.5 4-9.5 4z" /><path d="M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13" /></svg>
        </span>
        <div class="sp-brand__text">
          <div class="sp-brand__school">{{ brand.schoolName || brand.platformName }}</div>
          <div class="sp-brand__portal">{{ portalName }}</div>
        </div>
      </div>

      <div class="sp-nav__label">门户导航</div>
      <nav class="sp-nav">
        <button v-for="m in nav" :key="m.key" type="button" class="sp-nav__item"
                :class="{ 'is-active': m.active, 'is-locked': m.locked }" :title="m.title" @click="onNav(m)">
          <span class="sp-nav__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="m.d1" /><path :d="m.d2" /></svg>
          </span>
          <span class="sp-nav__text">{{ m.title }}</span>
          <span v-if="m.badge" class="sp-nav__badge">{{ m.badge }}</span>
          <svg v-else-if="m.locked" class="sp-nav__lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
        </button>
      </nav>

      <section class="sp-theme" aria-label="门户主题">
        <div class="sp-theme__title">主题换色</div>
        <div class="sp-theme__grid">
          <button v-for="item in themes" :key="item.key" type="button" class="sp-theme__item"
                  :class="{ 'is-active': themeKey === item.key }" :title="item.label" @click="selectTheme(item.key)">
            <span class="sp-theme__dot" :style="{ background: item.color }" />
            <span class="sp-theme__label">{{ item.label }}</span>
          </button>
        </div>
      </section>

      <div class="sp-aside__foot">
        <span class="sp-version">学生门户 V5</span>
        <button type="button" class="sp-logout" title="退出登录" @click="logout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3M16 17l5-5-5-5M21 12H9" /></svg>
          <span>退出</span>
        </button>
      </div>
    </aside>

    <div class="sp-body">
      <header class="sp-header">
        <div class="sp-header__left">
          <div class="sp-header__heading">
            <span class="sp-header__eyebrow">STUDENT SERVICE PORTAL</span>
            <span class="sp-header__title">{{ pageTitle }}</span>
          </div>
          <button v-if="activeModulePath === 'internship'" class="sp-context-link" type="button" @click="toggleInternshipView">
            {{ route.name === 'internship-compliance' ? '返回实习工作台' : '上岗合规与安全教育' }}
          </button>
        </div>
        <div class="sp-header__right">
          <label class="sp-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
            <input v-model.trim="search" placeholder="搜索办事项、通知…" @keyup.enter="doSearch" />
          </label>
          <div class="sp-scope">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
            本人数据
          </div>
          <button class="sp-bell" type="button" title="消息通知" @click="goMsg">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            <span v-if="unread > 0" class="sp-bell__badge">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
          <div class="sp-user">
            <span class="sp-user__avatar">{{ initial }}</span>
            <div class="sp-user__meta">
              <div class="sp-user__name">{{ user?.realName || '同学' }}</div>
              <div class="sp-user__role">学生 · 数据范围本人</div>
            </div>
          </div>
        </div>
      </header>

      <main class="sp-main">
        <div v-if="showWatermark" class="sp-watermark" :style="{ backgroundImage: wmUri }" />
        <div class="sp-content" :class="{ 'has-academic-context': showAcademicContext }">
          <AcademicContextNav v-if="showAcademicContext" />
          <div class="sp-content__page"><router-view /></div>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AcademicContextNav from '../components/academic/AcademicContextNav.vue'
import { usePortalConfigStore } from '../stores/portalConfig'
import { useSessionStore } from '../stores/session'
import { useUiStore } from '../stores/ui'
import { portalApi } from '../services/portalApi'
import { MODULES, SERVICE_HALL } from '../platform/moduleRegistry'

const route = useRoute()
const router = useRouter()
const cfg = usePortalConfigStore()
const session = useSessionStore()
const ui = useUiStore()

const brand = computed(() => cfg.brand)
const portalName = computed(() => cfg.portalName)
const user = computed(() => session.user)
const initial = computed(() => (session.user?.realName || '同').slice(0, 1))
const search = ref('')
const unread = ref(0)
const themeKey = ref('blue')

const themes = computed(() => [
  { key: 'blue', label: '深海蓝', color: brand.value?.primaryColor || '#2f6bff' },
  { key: 'purple', label: '科技紫', color: '#7b61ff' },
  { key: 'green', label: '薄荷绿', color: '#16a078' },
  { key: 'orange', label: '活力橙', color: '#f59b23' },
  { key: 'pink', label: '樱花粉', color: '#f36ca5' },
  { key: 'dark', label: '深邃黑', color: '#1e2433' }
])

const rawPath = computed(() => {
  const value = route.path.replace(/^\//, '')
  return value === '' ? 'home' : value.split('/')[0]
})
const activeModulePath = computed(() => route.meta?.modulePath || rawPath.value)
const showAcademicContext = computed(() => activeModulePath.value === 'academic')
const shellClasses = computed(() => ({
  'is-home': route.name === 'home',
  'is-compact': route.name !== 'home',
  [`route-${String(activeModulePath.value || 'home').replace(/[^a-z0-9-]/gi, '-')}`]: true,
  [`view-${String(route.name || 'page').replace(/[^a-z0-9-]/gi, '-')}`]: true
}))

const nav = computed(() => {
  const items = MODULES.map((m) => {
    const enabled = m.key === 'dashboard' || cfg.isModuleEnabled(m.key)
    return {
      key: m.key,
      title: m.title,
      d1: m.d1,
      d2: m.d2,
      to: '/' + m.path,
      active: activeModulePath.value === m.path,
      locked: !enabled,
      badge: m.key === 'messages' && unread.value > 0 ? (unread.value > 99 ? '99+' : unread.value) : ''
    }
  })
  items.push({ ...SERVICE_HALL, to: '/' + SERVICE_HALL.path, active: activeModulePath.value === SERVICE_HALL.path, locked: false, badge: '' })
  return items
})

const TITLES = {
  home: '首页工作台', profile: '我的档案', academic: '教务学业', graduation: '毕业设计',
  internship: '岗位实习', employment: '就业服务', 'campus-service': '学工事务',
  orientation: '迎新报到', messages: '消息通知', 'service-hall': '办事大厅'
}
const SPECIAL_TITLES = {
  'material-supplement': '材料补交中心',
  'internship-compliance': '上岗合规与安全教育',
  'module-disabled': '模块未开通',
  'not-enabled': '门户未开通'
}
const pageTitle = computed(() => SPECIAL_TITLES[route.name] || TITLES[activeModulePath.value] || '学生服务门户')

const showWatermark = computed(() => true)
const wmUri = computed(() => {
  const name = session.user?.realName || '同学'
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='270' height='175'><text x='0' y='95' fill='%231D2129' fill-opacity='0.025' font-size='15' font-family='sans-serif' transform='rotate(-24 0 95)'>${name} · 数据范围:本人</text></svg>`
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`
})

function onNav(m) {
  if (m.locked) {
    ui.notify('该模块未开通，请联系学校管理员')
    return
  }
  router.push(m.to)
}
function selectTheme(key) {
  themeKey.value = key
  window.localStorage.setItem('student-portal-theme', key)
  window.dispatchEvent(new CustomEvent('student-portal-theme-change', { detail: key }))
}
function toggleInternshipView() {
  router.push(route.name === 'internship-compliance' ? '/internship' : '/internship/compliance')
}
function goMsg() { router.push('/messages') }
function doSearch() {
  if (!search.value) return
  router.push({ path: '/service-hall', query: { kw: search.value } })
}
function logout() {
  session.logout()
  cfg.reset()
  router.replace('/login')
}

onMounted(async () => {
  themeKey.value = window.localStorage.getItem('student-portal-theme') || 'blue'
  window.dispatchEvent(new CustomEvent('student-portal-theme-change', { detail: themeKey.value }))
  try {
    const data = await portalApi.messagesInbox(1, 1)
    unread.value = data?.unreadCount || 0
  } catch (e) { /* 铃铛角标非关键，失败静默 */ }
})
</script>

<style scoped>
.sp-shell { display:flex; height:100vh; width:100%; overflow:hidden; background:var(--bg); }
.sp-aside { position:relative; width:224px; flex:none; overflow:hidden; display:flex; flex-direction:column; color:#fff; background:linear-gradient(180deg, color-mix(in srgb,var(--pri) 45%,#071b47) 0%, var(--pri) 57%, color-mix(in srgb,var(--pri) 58%,#fff) 100%); transition:width .18s ease; }
.sp-aside::before { content:""; position:absolute; width:260px; height:260px; right:-150px; top:-120px; border-radius:50%; background:rgba(255,255,255,.08); pointer-events:none; }
.sp-shell.is-compact .sp-aside { width:76px; }
.sp-brand { position:relative; display:flex; align-items:center; gap:11px; padding:18px 14px 16px; min-height:72px; }
.sp-brand__logo { width:43px; height:43px; flex:none; border-radius:14px; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.2); box-shadow:0 8px 24px rgba(0,0,0,.12); }
.sp-brand__text { min-width:0; }
.sp-brand__school { font-size:14px; font-weight:700; line-height:1.25; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.sp-brand__portal { margin-top:3px; font-size:11px; color:rgba(255,255,255,.7); }
.sp-nav__label { position:relative; padding:3px 18px 7px; font-size:10.5px; letter-spacing:.12em; color:rgba(255,255,255,.54); }
.sp-nav { position:relative; flex:1; overflow-y:auto; padding:0 11px 12px; }
.sp-nav::-webkit-scrollbar { width:0; }
.sp-nav__item { all:unset; box-sizing:border-box; cursor:pointer; width:100%; min-height:43px; margin:3px 0; padding:0 11px; border-radius:13px; display:flex; align-items:center; gap:10px; color:rgba(255,255,255,.8); font-size:13.5px; transition:background .15s ease,color .15s ease,transform .15s ease; }
.sp-nav__item:hover { background:rgba(255,255,255,.09); color:#fff; }
.sp-nav__item.is-active { background:#fff; color:var(--pri-text,var(--pri)); font-weight:750; box-shadow:0 10px 26px rgba(3,18,56,.18); }
.sp-nav__item.is-locked { color:rgba(255,255,255,.38); cursor:not-allowed; }
.sp-nav__item.is-locked:hover { background:transparent; }
.sp-nav__icon { width:28px; height:28px; flex:none; display:grid; place-items:center; }
.sp-nav__text { flex:1; white-space:nowrap; }
.sp-nav__lock { flex:none; opacity:.65; }
.sp-nav__badge { min-width:19px; height:19px; padding:0 5px; border-radius:10px; display:inline-flex; align-items:center; justify-content:center; background:#ff5d67; color:#fff; font-size:10px; font-weight:700; }
.sp-shell.is-compact :where(.sp-brand__text,.sp-nav__label,.sp-nav__text,.sp-nav__lock) { display:none; }
.sp-shell.is-compact .sp-brand { justify-content:center; padding-inline:0; }
.sp-shell.is-compact .sp-nav { padding-inline:10px; }
.sp-shell.is-compact .sp-nav__item { justify-content:center; padding:0; }
.sp-shell.is-compact .sp-nav__badge { position:absolute; top:2px; right:1px; }
.sp-theme { position:relative; padding:13px 11px 12px; border-top:1px solid rgba(255,255,255,.14); }
.sp-theme__title { padding:0 4px 9px; font-size:11.5px; font-weight:650; color:rgba(255,255,255,.78); }
.sp-theme__grid { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
.sp-theme__item { all:unset; box-sizing:border-box; cursor:pointer; min-height:31px; padding:0 8px; border-radius:10px; display:flex; align-items:center; gap:7px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.07); color:rgba(255,255,255,.78); font-size:10.5px; }
.sp-theme__item:hover,.sp-theme__item.is-active { background:#fff; color:var(--pri-text,var(--pri)); }
.sp-theme__dot { width:12px; height:12px; flex:none; border-radius:50%; border:2px solid rgba(255,255,255,.48); box-shadow:0 0 0 1px rgba(0,0,0,.07); }
.sp-shell.is-compact .sp-theme { padding:11px 15px; }
.sp-shell.is-compact .sp-theme__title,.sp-shell.is-compact .sp-theme__label { display:none; }
.sp-shell.is-compact .sp-theme__grid { grid-template-columns:1fr; gap:7px; }
.sp-shell.is-compact .sp-theme__item { min-height:25px; padding:0; justify-content:center; border:0; background:transparent; }
.sp-shell.is-compact .sp-theme__item.is-active { background:rgba(255,255,255,.16); }
.sp-aside__foot { position:relative; min-height:50px; padding:10px 14px; border-top:1px solid rgba(255,255,255,.14); display:flex; align-items:center; justify-content:space-between; gap:8px; }
.sp-version { font-size:10.5px; color:rgba(255,255,255,.62); }
.sp-logout { all:unset; cursor:pointer; display:inline-flex; align-items:center; gap:6px; color:rgba(255,255,255,.72); font-size:12px; }
.sp-logout:hover { color:#fff; }
.sp-shell.is-compact .sp-version,.sp-shell.is-compact .sp-logout span { display:none; }
.sp-shell.is-compact .sp-aside__foot { justify-content:center; padding-inline:0; }
.sp-body { flex:1; min-width:0; display:flex; flex-direction:column; }
.sp-header { height:72px; flex:none; display:flex; align-items:center; justify-content:space-between; gap:18px; padding:0 26px; background:var(--surface,#fff); border-bottom:1px solid var(--line); }
.sp-header__left,.sp-header__right { display:flex; align-items:center; gap:12px; min-width:0; }
.sp-header__right { flex:none; gap:11px; }
.sp-header__heading { min-width:0; display:flex; flex-direction:column; }
.sp-header__eyebrow { color:var(--t4); font-size:9.5px; letter-spacing:.12em; line-height:1; }
.sp-header__title { margin-top:5px; color:var(--t1); font-size:20px; font-weight:750; line-height:1.15; white-space:nowrap; }
.sp-context-link { height:33px; padding:0 12px; border:1px solid var(--pri); border-radius:9px; background:var(--pri-50); color:var(--pri-text,var(--pri)); font-size:12px; font-weight:700; cursor:pointer; white-space:nowrap; }
.sp-search { width:280px; height:40px; padding:0 12px; display:flex; align-items:center; gap:8px; border:1px solid var(--line); border-radius:12px; background:var(--field-bg,#f8faff); color:var(--t4); }
.sp-search input { width:100%; border:0; outline:0; background:transparent; color:var(--t1); font-size:13px; }
.sp-scope { height:31px; padding:0 10px; display:flex; align-items:center; gap:6px; border-radius:9px; background:var(--pri-50); color:var(--pri-text,var(--pri)); font-size:11.5px; font-weight:700; white-space:nowrap; }
.sp-bell { all:unset; position:relative; cursor:pointer; width:38px; height:38px; border:1px solid var(--line); border-radius:11px; display:grid; place-items:center; color:var(--t2); }
.sp-bell:hover { background:var(--field-bg,#f6f8fc); }
.sp-bell__badge { position:absolute; top:-4px; right:-4px; min-width:17px; height:17px; padding:0 4px; border-radius:9px; display:grid; place-items:center; background:var(--danger-fg); color:#fff; border:2px solid var(--surface,#fff); font-size:9px; font-weight:700; }
.sp-user { display:flex; align-items:center; gap:9px; padding-left:11px; border-left:1px solid var(--line); }
.sp-user__avatar { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; background:linear-gradient(135deg,var(--pri-50),var(--pri-100)); color:var(--pri-text,var(--pri)); border:1px solid var(--pri-100); font-size:14px; font-weight:800; }
.sp-user__name { color:var(--t1); font-size:12.5px; font-weight:700; }
.sp-user__role { margin-top:3px; color:var(--t3); font-size:10.5px; }
.sp-main { flex:1; overflow-y:auto; position:relative; background:var(--bg); }
.sp-watermark { position:absolute; inset:0; pointer-events:none; background-repeat:repeat; z-index:0; }
.sp-content { position:relative; z-index:1; margin:0 auto; }
.sp-content.has-academic-context { display:grid; grid-template-columns:208px minmax(0,1fr); gap:18px; align-items:start; }
.sp-content__page { min-width:0; }
@media(max-width:1180px){.sp-search{width:210px}.sp-user__meta{display:none}.sp-user{border-left:0;padding-left:0}.sp-scope{display:none}.sp-content.has-academic-context{grid-template-columns:196px minmax(0,1fr)}}
@media(max-width:900px){.sp-aside,.sp-shell.is-home .sp-aside{width:64px}.sp-brand__text,.sp-nav__label,.sp-nav__text,.sp-nav__lock,.sp-theme__title,.sp-theme__label,.sp-version,.sp-logout span{display:none}.sp-brand{justify-content:center;padding-inline:0}.sp-nav{padding-inline:7px}.sp-nav__item{justify-content:center;padding:0}.sp-theme{padding-inline:10px}.sp-theme__grid{grid-template-columns:1fr}.sp-theme__item{justify-content:center;padding:0;border:0;background:transparent}.sp-aside__foot{justify-content:center;padding-inline:0}.sp-header{padding:0 16px}.sp-search{width:160px}.sp-context-link{display:none}}
@media(max-width:820px){.sp-content.has-academic-context{display:block}.sp-content.has-academic-context > :first-child{margin-bottom:14px}}
@media(max-width:700px){.sp-header__eyebrow,.sp-search{display:none}.sp-header{height:62px}.sp-header__title{font-size:17px}.sp-user__avatar{width:34px;height:34px}}
</style>
