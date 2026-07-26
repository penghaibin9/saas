<template>
  <div class="sp-shell">
    <aside class="sp-aside">
      <div class="sp-brand">
        <span class="sp-brand__logo">
          <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8.5 12 4.5l9.5 4-9.5 4z" /><path d="M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13" /></svg>
        </span>
        <div style="min-width:0">
          <div class="sp-brand__school">{{ brand.schoolName || brand.platformName }}</div>
          <div class="sp-brand__portal">{{ portalName }}</div>
        </div>
      </div>

      <nav class="sp-nav">
        <a v-for="m in nav" :key="m.key" class="sp-nav__item" :class="{ 'is-active': m.active, 'is-locked': m.locked }"
           @click="onNav(m)">
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path :d="m.d1" /><path :d="m.d2" /></svg>
          <span style="flex:1">{{ m.title }}</span>
          <span v-if="m.badge" class="sp-nav__badge">{{ m.badge }}</span>
          <svg v-else-if="m.locked" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#C6CCD6" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
        </a>
      </nav>

      <div class="sp-aside__foot">
        <span style="font-size:11.5px;color:#A9B0BD">门户 v1.0</span>
        <a class="sp-logout" @click="logout">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3M16 17l5-5-5-5M21 12H9" /></svg>
          退出
        </a>
      </div>
    </aside>

    <div class="sp-body">
      <header class="sp-header">
        <div style="display:flex;align-items:center;gap:12px;min-width:0">
          <div style="min-width:0">
            <span class="sp-header__title">{{ pageTitle }}</span>
            <span class="sp-header__sub">{{ brand.platformName || '学生服务门户' }}</span>
          </div>
          <button v-if="activePath === 'internship'" class="sp-context-link" @click="toggleInternshipView">
            {{ route.name === 'internship-compliance' ? '返回实习工作台' : '上岗合规与安全教育' }}
          </button>
        </div>
        <div style="display:flex;align-items:center;gap:14px;flex:none">
          <div class="sp-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#98A0AE" stroke-width="1.8" stroke-linecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>
            <input v-model.trim="search" placeholder="搜索办事项、通知…" @keyup.enter="doSearch" />
          </div>
          <div class="sp-scope">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
            数据范围 · 本人
          </div>
          <button class="sp-bell" @click="goMsg">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            <span v-if="unread > 0" class="sp-bell__badge">{{ unread > 99 ? '99+' : unread }}</span>
          </button>
          <div class="sp-user">
            <span class="sp-user__avatar">{{ initial }}</span>
            <div style="line-height:1.25">
              <div class="sp-user__name">{{ user?.realName || '同学' }}</div>
              <div class="sp-user__role">学生 · 本人</div>
            </div>
          </div>
        </div>
      </header>

      <main class="sp-main">
        <div v-if="showWatermark" class="sp-watermark" :style="{ backgroundImage: wmUri }" />
        <div class="sp-content"><router-view /></div>
      </main>
    </div>

    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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

const activePath = computed(() => {
  const p = route.path.replace(/^\//, '')
  return p === '' ? 'home' : p.split('/')[0]
})

const nav = computed(() => {
  const items = MODULES.map((m) => {
    const enabled = m.key === 'dashboard' || cfg.isModuleEnabled(m.key)
    const path = m.path === 'home' ? 'home' : m.path
    return {
      key: m.key, title: m.title, d1: m.d1, d2: m.d2,
      to: '/' + path, active: activePath.value === path,
      locked: !enabled,
      badge: m.key === 'messages' && unread.value > 0 ? (unread.value > 99 ? '99+' : unread.value) : ''
    }
  })
  items.push({ ...SERVICE_HALL, to: '/' + SERVICE_HALL.path, active: activePath.value === SERVICE_HALL.path, locked: false, badge: '' })
  return items
})

const TITLES = {
  home: '首页工作台', profile: '我的档案', academic: '教务学业', graduation: '毕业设计',
  internship: '岗位实习', employment: '就业服务', 'campus-service': '学工事务',
  orientation: '迎新报到', messages: '消息通知', 'service-hall': '办事大厅'
}
const pageTitle = computed(() => TITLES[activePath.value] || '学生服务门户')

const showWatermark = computed(() => true)
const wmUri = computed(() => {
  const name = session.user?.realName || '同学'
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='260' height='170'><text x='0' y='95' fill='%231D2129' fill-opacity='0.028' font-size='15' font-family='sans-serif' transform='rotate(-24 0 95)'>${name} · 数据范围:本人</text></svg>`
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`
})

function onNav(m) {
  if (m.locked) { ui.notify('该模块未开通，请联系学校管理员'); return }
  router.push(m.to)
}
function toggleInternshipView() {
  router.push(route.name === 'internship-compliance' ? '/internship' : '/internship/compliance')
}
function goMsg() { router.push('/messages') }
function doSearch() { if (search.value) router.push('/service-hall') }
function logout() {
  session.logout()
  cfg.reset()
  router.replace('/login')
}

onMounted(async () => {
  try {
    const data = await portalApi.messagesInbox(1, 1)
    unread.value = data?.unreadCount || 0
  } catch (e) { /* 铃铛角标非关键，失败静默 */ }
})
</script>

<style scoped>
.sp-shell { display: flex; height: 100vh; width: 100%; overflow: hidden; background: var(--bg); }
.sp-aside { width: 248px; flex: none; background: #fff; border-right: 1px solid var(--line); display: flex; flex-direction: column; }
.sp-brand { display: flex; align-items: center; gap: 11px; padding: 18px 18px 16px; }
.sp-brand__logo { width: 38px; height: 38px; flex: none; border-radius: 11px; background: linear-gradient(135deg, var(--g2), var(--g1)); display: flex; align-items: center; justify-content: center; box-shadow: 0 3px 8px rgba(37,99,235,.28); }
.sp-brand__school { font-size: 14px; font-weight: 600; color: var(--t1); line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sp-brand__portal { font-size: 11.5px; color: var(--t3); margin-top: 1px; }
.sp-nav { flex: 1; overflow-y: auto; padding: 6px 12px 12px; }
.sp-nav__item { position: relative; display: flex; align-items: center; gap: 12px; padding: 10px 12px; margin: 2px 0; border-radius: 10px; font-size: 14px; cursor: pointer; transition: background .15s, color .15s; color: var(--t2); }
.sp-nav__item:hover { background: #F3F5F8; }
.sp-nav__item.is-active { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.sp-nav__item.is-locked { color: #C6CCD6; cursor: not-allowed; }
.sp-nav__item.is-locked:hover { background: transparent; }
.sp-nav__badge { min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: var(--danger-fg); color: #fff; font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; justify-content: center; }
.sp-aside__foot { padding: 12px 16px; border-top: 1px solid var(--line2); display: flex; align-items: center; justify-content: space-between; }
.sp-logout { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--t3); cursor: pointer; }
.sp-logout:hover { color: var(--danger-fg); }
.sp-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.sp-header { height: 62px; flex: none; background: #fff; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; padding: 0 26px; gap: 20px; }
.sp-header__title { font-size: 20px; font-weight: 600; color: var(--t1); white-space: nowrap; }
.sp-header__sub { font-size: 12.5px; color: #A9B0BD; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-left: 12px; }
.sp-context-link { border:1px solid var(--pri);background:var(--pri-50);color:var(--pri);height:32px;padding:0 12px;border-radius:8px;font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap; }
.sp-context-link:hover { background:#E8F1FF; }
.sp-search { display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 12px; background: #F5F7FA; border: 1px solid #EDEFF3; border-radius: 9px; width: 230px; }
.sp-search input { border: none; background: transparent; outline: none; font-size: 13px; color: var(--t2); width: 100%; }
.sp-scope { display: flex; align-items: center; gap: 6px; height: 30px; padding: 0 11px; background: var(--pri-50); border-radius: 15px; color: var(--pri); font-size: 12.5px; font-weight: 500; flex: none; white-space: nowrap; }
.sp-bell { all: unset; position: relative; cursor: pointer; width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--t2); }
.sp-bell:hover { background: #F3F5F8; }
.sp-bell__badge { position: absolute; top: 6px; right: 4px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px; background: var(--danger-fg); color: #fff; font-size: 10px; font-weight: 600; display: flex; align-items: center; justify-content: center; border: 1.5px solid #fff; }
.sp-user { display: flex; align-items: center; gap: 10px; padding-left: 2px; }
.sp-user__avatar { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg, #DCE9FF, #EEF4FF); color: var(--pri); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 700; border: 1px solid #D6E5FF; }
.sp-user__name { font-size: 13.5px; font-weight: 600; color: var(--t1); }
.sp-user__role { font-size: 11.5px; color: var(--t3); }
.sp-main { flex: 1; overflow-y: auto; position: relative; }
.sp-watermark { position: absolute; inset: 0; pointer-events: none; background-repeat: repeat; z-index: 0; }
.sp-content { position: relative; z-index: 1; max-width: 1280px; margin: 0 auto; padding: 26px 32px 40px; }
@media (max-width: 980px) {
  .sp-aside { width: 60px; }
  .sp-brand__school, .sp-brand__portal, .sp-nav__item span, .sp-logout { display: none; }
  .sp-search { width: 120px; }
  .sp-context-link { display:none; }
}
</style>
